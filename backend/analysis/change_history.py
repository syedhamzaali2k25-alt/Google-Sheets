"""Change history analytics for a spreadsheet, backed by the Google Drive
Activity API (requires the drive.activity.readonly scope).

fetch_change_activity() calls the API (Drive Activity API v2's single
`activity:query` method) for a time window. summarize_change_history() is a
pure function over that raw response — kept separate so it can be unit
tested with fixture data, without mocking the Google API client.

Important limitation: the Drive Activity API reports file-level activity
only (who touched the file, when, and what kind of action). It does not
expose which sheet or cell range was edited — that level of detail simply
isn't in the API's data model for Sheets files. summarize_change_history()
degrades gracefully to a file-level summary whenever no range-level detail
is present (which, with today's API, is always), and says so explicitly via
`data_granularity` / `limited_data_warning` rather than silently pretending
otherwise.
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Literal

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel

from app.cache import RevisionCache, token_fingerprint

# Unlike the raw-sheet cache, there's no cheap "has this changed" check for
# Drive activity (querying activity *is* the expensive call), so this is a
# short pure-TTL cache — just long enough to absorb back-to-back requests
# for the same window (e.g. loading the dashboard, then immediately
# exporting a PDF for the same spreadsheet) without serving stale data for
# long if something genuinely changed. The cache key is scoped to a
# fingerprint of the caller's token (see app/cache.py) for the same
# authorization reason as the raw-sheet cache.
_ACTIVITY_CACHE_TTL_SECONDS = 120
_activity_cache: RevisionCache[dict] = RevisionCache(_ACTIVITY_CACHE_TTL_SECONDS)


class ChangeHistoryAccessError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ActivityAction(str, Enum):
    CREATE = "create"
    EDIT = "edit"
    MOVE = "move"
    RENAME = "rename"
    DELETE = "delete"
    RESTORE = "restore"
    PERMISSION_CHANGE = "permission_change"
    COMMENT = "comment"
    OTHER = "other"


Severity = Literal["low", "medium", "high"]


class ActivityEvent(BaseModel):
    timestamp: datetime
    actors: list[str]
    action: ActivityAction


class Contributor(BaseModel):
    identifier: str
    display_name: str | None
    edit_count: int
    total_actions: int
    last_active_at: datetime | None


class TouchedRange(BaseModel):
    sheet_name: str | None
    range_a1: str | None
    edit_count: int


class UnusualActivityFlag(BaseModel):
    timestamp: datetime
    actor: str | None
    description: str
    severity: Severity


class ChangeHistoryReport(BaseModel):
    spreadsheet_id: str
    window_start: datetime
    window_end: datetime
    data_granularity: Literal["file_level", "range_level"]
    limited_data_warning: str | None
    total_edits: int
    contributors: list[Contributor]
    touched_ranges: list[TouchedRange]
    unusual_activity: list[UnusualActivityFlag]
    events: list[ActivityEvent]


# ---------------------------------------------------------------------------
# Fetching (Drive Activity API)
# ---------------------------------------------------------------------------


def fetch_change_activity(
    access_token: str,
    spreadsheet_id: str,
    since: datetime,
    until: datetime | None = None,
) -> dict[str, Any]:
    """Fetches every Drive activity event for one file within [since, until].

    Runs synchronously (googleapiclient is not async) — call it from a sync
    FastAPI route so Starlette runs it in a worker thread.
    """
    credentials = Credentials(token=access_token)
    service = build("driveactivity", "v2", credentials=credentials, cache_discovery=False)

    time_filter = f'time >= "{_format_rfc3339(since)}"'
    if until is not None:
        time_filter += f' AND time <= "{_format_rfc3339(until)}"'

    activities: list[dict[str, Any]] = []
    page_token: str | None = None

    try:
        while True:
            body: dict[str, Any] = {
                "itemName": f"items/{spreadsheet_id}",
                "filter": time_filter,
                "pageSize": 100,
            }
            if page_token:
                body["pageToken"] = page_token

            result = service.activity().query(body=body).execute()
            activities.extend(result.get("activities", []))

            page_token = result.get("nextPageToken")
            if not page_token:
                break
    except HttpError as exc:
        raise _map_http_error(exc) from exc
    except RefreshError as exc:
        # A bare access token (no refresh_token) that Google rejects with
        # 401 makes google-auth try to refresh it, which fails with this
        # instead of surfacing the original HttpError (see app/google_sheets.py).
        raise ChangeHistoryAccessError(401, "Google access token is invalid or expired.") from exc

    return {"activities": activities}


def fetch_change_activity_cached(
    access_token: str,
    spreadsheet_id: str,
    since: datetime,
    until: datetime | None = None,
) -> dict[str, Any]:
    """Like fetch_change_activity, but serves a recent identical request
    (same token, spreadsheet, and window) from cache instead of re-querying
    the Drive Activity API. See the module-level cache comment for why the
    TTL is short and the key includes a token fingerprint."""
    cache_key = (
        f"{token_fingerprint(access_token)}:{spreadsheet_id}:"
        f"{_format_rfc3339(since)}:{_format_rfc3339(until) if until else ''}"
    )
    cached = _activity_cache.get(cache_key)
    if cached is not None:
        return cached

    result = fetch_change_activity(access_token, spreadsheet_id, since, until)
    _activity_cache.set(cache_key, result)
    return result


def _format_rfc3339(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _map_http_error(exc: HttpError) -> ChangeHistoryAccessError:
    status_code = exc.resp.status if exc.resp else 500

    if status_code == 401:
        return ChangeHistoryAccessError(401, "Google access token is invalid or expired.")
    if status_code == 403:
        return ChangeHistoryAccessError(403, "You don't have access to this file's activity history.")
    if status_code == 404:
        return ChangeHistoryAccessError(404, "File not found.")
    return ChangeHistoryAccessError(502, "Google Drive Activity API request failed.")


# ---------------------------------------------------------------------------
# Summarization (pure — no network calls)
# ---------------------------------------------------------------------------

_ACTION_KEY_MAP: dict[str, ActivityAction] = {
    "create": ActivityAction.CREATE,
    "edit": ActivityAction.EDIT,
    "move": ActivityAction.MOVE,
    "rename": ActivityAction.RENAME,
    "delete": ActivityAction.DELETE,
    "restore": ActivityAction.RESTORE,
    "permissionChange": ActivityAction.PERMISSION_CHANGE,
    "comment": ActivityAction.COMMENT,
}

# Burst-edit heuristic: this many (or more) edits by the same actor within
# this rolling window are flagged as a likely bulk change (e.g. a large
# paste or find-and-replace). The Drive Activity API can't tell us *what*
# changed, only that a lot of editing happened quickly.
_BURST_THRESHOLD = 5
_BURST_WINDOW = timedelta(minutes=10)


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _activity_timestamp(activity: dict[str, Any]) -> datetime | None:
    if "timestamp" in activity:
        return _parse_timestamp(activity["timestamp"])
    time_range = activity.get("timeRange")
    if time_range and "endTime" in time_range:
        return _parse_timestamp(time_range["endTime"])
    return None


def _action_type(primary_action_detail: dict[str, Any]) -> ActivityAction:
    for key, action in _ACTION_KEY_MAP.items():
        if key in primary_action_detail:
            return action
    return ActivityAction.OTHER


def _actor_identifier(actor: dict[str, Any]) -> str:
    if "user" in actor:
        known = actor["user"].get("knownUser")
        if known:
            return "you" if known.get("isCurrentUser") else known.get("personName", "unknown-user")
        if "deletedUser" in actor["user"]:
            return "deleted-user"
        return "unknown-user"
    if "anonymous" in actor:
        return "anonymous"
    if "impersonation" in actor:
        impersonated = actor["impersonation"].get("impersonatedUser", {}).get("knownUser", {})
        return impersonated.get("personName", "unknown-impersonated-user")
    if "system" in actor:
        return f"system:{actor['system'].get('type', 'unknown').lower()}"
    return "unknown"


def _display_name_for(identifier: str) -> str | None:
    if identifier == "you":
        return "You"
    if identifier == "anonymous":
        return "Anonymous user"
    if identifier.startswith("system:"):
        return f"Automated ({identifier.split(':', 1)[1]})"
    # A bare "people/123..." resource name can't be turned into a real name
    # or email without an additional People API call/scope, which this
    # endpoint doesn't request — left unresolved rather than guessed at.
    return None


def _extract_touched_ranges(activity_response: dict[str, Any]) -> list[TouchedRange]:
    """The Drive Activity API v2 does not currently expose per-sheet or
    per-cell range information for Google Sheets edits — 'edit' actions
    carry no location detail, only that a file-level edit occurred. This
    function is a forward-compatible placeholder for if that ever changes;
    today it always returns an empty list.
    """
    del activity_response  # unused until the API exposes range-level detail
    return []


def _extract_events(activity_response: dict[str, Any]) -> list[ActivityEvent]:
    events = []
    for activity in activity_response.get("activities", []):
        timestamp = _activity_timestamp(activity)
        if timestamp is None:
            continue
        actors = [_actor_identifier(actor) for actor in activity.get("actors", [])] or ["unknown"]
        action = _action_type(activity.get("primaryActionDetail", {}))
        events.append(ActivityEvent(timestamp=timestamp, actors=actors, action=action))
    return sorted(events, key=lambda e: e.timestamp)


def _summarize_contributors(events: list[ActivityEvent]) -> list[Contributor]:
    edit_counts: dict[str, int] = defaultdict(int)
    total_counts: dict[str, int] = defaultdict(int)
    last_active: dict[str, datetime] = {}

    for event in events:
        for actor_id in event.actors:
            total_counts[actor_id] += 1
            if event.action == ActivityAction.EDIT:
                edit_counts[actor_id] += 1
            if actor_id not in last_active or event.timestamp > last_active[actor_id]:
                last_active[actor_id] = event.timestamp

    contributors = [
        Contributor(
            identifier=actor_id,
            display_name=_display_name_for(actor_id),
            edit_count=edit_counts.get(actor_id, 0),
            total_actions=total_count,
            last_active_at=last_active[actor_id],
        )
        for actor_id, total_count in total_counts.items()
    ]
    return sorted(contributors, key=lambda c: (c.edit_count, c.total_actions), reverse=True)


def _detect_unusual_activity(events: list[ActivityEvent]) -> list[UnusualActivityFlag]:
    flags: list[UnusualActivityFlag] = []

    for event in events:
        actor = event.actors[0] if event.actors else None
        if event.action == ActivityAction.DELETE:
            flags.append(
                UnusualActivityFlag(
                    timestamp=event.timestamp,
                    actor=actor,
                    description="The file was deleted (moved to trash).",
                    severity="high",
                )
            )
        elif event.action == ActivityAction.PERMISSION_CHANGE:
            flags.append(
                UnusualActivityFlag(
                    timestamp=event.timestamp,
                    actor=actor,
                    description="Sharing or permissions were changed.",
                    severity="low",
                )
            )

    edits_by_actor: dict[str, list[datetime]] = defaultdict(list)
    for event in events:
        if event.action != ActivityAction.EDIT:
            continue
        for actor_id in event.actors:
            edits_by_actor[actor_id].append(event.timestamp)

    for actor_id, timestamps in edits_by_actor.items():
        timestamps.sort()
        window: deque[datetime] = deque()
        for ts in timestamps:
            window.append(ts)
            while window and ts - window[0] > _BURST_WINDOW:
                window.popleft()
            if len(window) >= _BURST_THRESHOLD:
                minutes = int(_BURST_WINDOW.total_seconds() // 60)
                flags.append(
                    UnusualActivityFlag(
                        timestamp=ts,
                        actor=actor_id,
                        description=(
                            f"Possible bulk edit: {len(window)} edits by "
                            f"{_display_name_for(actor_id) or actor_id} within {minutes} minutes."
                        ),
                        severity="medium",
                    )
                )
                window.clear()  # don't re-flag every subsequent edit in the same burst

    return sorted(flags, key=lambda f: f.timestamp)


def summarize_change_history(
    activity_response: dict[str, Any],
    spreadsheet_id: str,
    window_start: datetime,
    window_end: datetime,
) -> ChangeHistoryReport:
    """Pure summarization over an already-fetched Drive Activity API response."""
    events = _extract_events(activity_response)
    touched_ranges = _extract_touched_ranges(activity_response)
    granularity: Literal["file_level", "range_level"] = "range_level" if touched_ranges else "file_level"

    limited_data_warning = None
    if granularity == "file_level":
        limited_data_warning = (
            "The Drive Activity API only reports file-level activity for this spreadsheet "
            "(who edited it and when) — it does not expose which sheets or cell ranges were "
            "changed. Showing a file-level summary."
        )

    return ChangeHistoryReport(
        spreadsheet_id=spreadsheet_id,
        window_start=window_start,
        window_end=window_end,
        data_granularity=granularity,
        limited_data_warning=limited_data_warning,
        total_edits=sum(1 for e in events if e.action == ActivityAction.EDIT),
        contributors=_summarize_contributors(events),
        touched_ranges=touched_ranges,
        unusual_activity=_detect_unusual_activity(events),
        events=events,
    )
