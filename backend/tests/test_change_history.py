import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from analysis.change_history import (
    ActivityAction,
    summarize_change_history,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "drive_activity_sample.json"

WINDOW_START = datetime(2024, 5, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2024, 5, 6, tzinfo=timezone.utc)


@pytest.fixture
def activity_response() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


@pytest.fixture
def report(activity_response):
    return summarize_change_history(activity_response, "mock-spreadsheet-id", WINDOW_START, WINDOW_END)


def test_window_is_echoed_back(report):
    assert report.spreadsheet_id == "mock-spreadsheet-id"
    assert report.window_start == WINDOW_START
    assert report.window_end == WINDOW_END


def test_degrades_to_file_level_with_limited_data_warning(report):
    # The Drive Activity API never carries range info for Sheets today, so
    # this should always come back file_level with an explicit warning.
    assert report.data_granularity == "file_level"
    assert report.limited_data_warning is not None
    assert "file-level" in report.limited_data_warning
    assert report.touched_ranges == []


def test_total_edits_counts_only_edit_actions(report):
    # 5 edits by people/200 + 1 edit by "you" = 6; create/rename/permission
    # change/delete don't count as edits.
    assert report.total_edits == 6


def test_contributors_sorted_by_edit_count_desc(report):
    assert [c.identifier for c in report.contributors] == ["people/200", "you"]

    bob = report.contributors[0]
    assert bob.edit_count == 5
    assert bob.total_actions == 7  # 5 edits + 1 permission change + 1 delete
    assert bob.display_name is None  # unresolvable without the People API

    you = report.contributors[1]
    assert you.edit_count == 1
    assert you.total_actions == 3  # create + edit + rename
    assert you.display_name == "You"


def test_bulk_edit_burst_flagged(report):
    bulk_flags = [f for f in report.unusual_activity if "bulk edit" in f.description.lower()]
    assert len(bulk_flags) == 1
    flag = bulk_flags[0]
    assert flag.severity == "medium"
    assert flag.actor == "people/200"
    assert "5 edits" in flag.description


def test_delete_flagged_high_severity(report):
    delete_flags = [f for f in report.unusual_activity if f.severity == "high"]
    assert len(delete_flags) == 1
    assert "deleted" in delete_flags[0].description.lower()


def test_permission_change_flagged_low_severity(report):
    permission_flags = [f for f in report.unusual_activity if "permission" in f.description.lower()]
    assert len(permission_flags) == 1
    assert permission_flags[0].severity == "low"


def test_unusual_activity_sorted_chronologically(report):
    timestamps = [f.timestamp for f in report.unusual_activity]
    assert timestamps == sorted(timestamps)


def test_events_include_every_activity_for_who_and_when(report):
    # Even in file-level (degraded) mode, callers can still answer "who
    # edited this and when" from the raw event list.
    assert len(report.events) == 10
    assert all(e.actors for e in report.events)
    assert {e.action for e in report.events} == {
        ActivityAction.CREATE,
        ActivityAction.EDIT,
        ActivityAction.RENAME,
        ActivityAction.PERMISSION_CHANGE,
        ActivityAction.DELETE,
    }


def test_no_activity_produces_empty_but_valid_report():
    report = summarize_change_history({"activities": []}, "empty-id", WINDOW_START, WINDOW_END)
    assert report.total_edits == 0
    assert report.contributors == []
    assert report.unusual_activity == []
    assert report.events == []
    assert report.data_granularity == "file_level"


def test_activity_missing_timestamp_is_skipped_not_crashed():
    response = {
        "activities": [
            {"primaryActionDetail": {"edit": {}}, "actors": []},  # no timestamp at all
            {
                "primaryActionDetail": {"edit": {}},
                "actors": [{"user": {"knownUser": {"personName": "people/1", "isCurrentUser": False}}}],
                "timestamp": "2024-05-01T00:00:00Z",
            },
        ]
    }
    report = summarize_change_history(response, "id", WINDOW_START, WINDOW_END)
    assert report.total_edits == 1
    assert len(report.events) == 1


def test_anonymous_and_system_actors_are_labeled():
    response = {
        "activities": [
            {"primaryActionDetail": {"edit": {}}, "actors": [{"anonymous": {}}], "timestamp": "2024-05-01T00:00:00Z"},
            {
                "primaryActionDetail": {"edit": {}},
                "actors": [{"system": {"type": "DRIVE_FILE_STREAM"}}],
                "timestamp": "2024-05-01T01:00:00Z",
            },
        ]
    }
    report = summarize_change_history(response, "id", WINDOW_START, WINDOW_END)
    identifiers = {c.identifier for c in report.contributors}
    assert "anonymous" in identifiers
    assert "system:drive_file_stream" in identifiers

    system_contributor = next(c for c in report.contributors if c.identifier == "system:drive_file_stream")
    assert system_contributor.display_name == "Automated (drive_file_stream)"
