"""Tests for the read-only "Shared With" collaborators feature:
app.google_sheets.list_collaborators/_map_permission and the
GET /sheets/{id}/collaborators endpoint.
"""

from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

import app.main as main_module
from app.google_sheets import Collaborator, SheetsAccessError, _map_permission, list_collaborators


class _FakeResp:
    def __init__(self, status: int):
        self.status = status
        self.reason = "error"


def _http_error(status: int) -> HttpError:
    return HttpError(_FakeResp(status), b"{}", uri="https://www.googleapis.com/drive/v3/files/x/permissions")


def _service_returning(*pages: dict) -> MagicMock:
    """A fake googleapiclient Drive service whose permissions().list().execute()
    returns each of `pages` in order across successive calls — used to
    exercise pagination via nextPageToken."""
    service = MagicMock()
    responses = iter(pages)
    service.permissions.return_value.list.return_value.execute.side_effect = lambda: next(responses)
    return service


# ---------------------------------------------------------------------------
# _map_permission — pure mapping, one Drive permission type at a time
# ---------------------------------------------------------------------------


def test_map_permission_handles_user_type():
    collaborator = _map_permission(
        {"id": "1", "type": "user", "role": "writer", "emailAddress": "alice@example.com", "displayName": "Alice"}
    )
    assert collaborator == Collaborator(
        type="user", role="writer", email="alice@example.com", display_name="Alice", domain=None
    )


def test_map_permission_handles_anyone_type():
    # "Anyone with the link" permissions carry no emailAddress/displayName.
    collaborator = _map_permission({"id": "2", "type": "anyone", "role": "reader"})
    assert collaborator.type == "anyone"
    assert collaborator.email is None
    assert collaborator.display_name is None
    assert collaborator.domain is None


def test_map_permission_handles_domain_type():
    collaborator = _map_permission({"id": "3", "type": "domain", "role": "commenter", "domain": "example.com"})
    assert collaborator.type == "domain"
    assert collaborator.domain == "example.com"
    assert collaborator.email is None


# ---------------------------------------------------------------------------
# list_collaborators — full Drive API call + mapping + pagination + errors
# ---------------------------------------------------------------------------


@patch("app.google_sheets.build")
def test_list_collaborators_maps_a_mix_of_user_roles(mock_build):
    mock_build.return_value = _service_returning(
        {
            "permissions": [
                {"id": "1", "type": "user", "role": "owner", "emailAddress": "owner@example.com", "displayName": "Owner Person"},
                {"id": "2", "type": "user", "role": "writer", "emailAddress": "editor@example.com", "displayName": "Editor Person"},
                {"id": "3", "type": "user", "role": "commenter", "emailAddress": "commenter@example.com", "displayName": "Commenter Person"},
                {"id": "4", "type": "user", "role": "reader", "emailAddress": "viewer@example.com", "displayName": "Viewer Person"},
            ]
        }
    )

    collaborators = list_collaborators("token", "sheet-id")

    assert len(collaborators) == 4
    assert [c.role for c in collaborators] == ["owner", "writer", "commenter", "reader"]
    assert collaborators[0].email == "owner@example.com"


@patch("app.google_sheets.build")
def test_list_collaborators_handles_anyone_with_link(mock_build):
    mock_build.return_value = _service_returning(
        {
            "permissions": [
                {"id": "1", "type": "user", "role": "owner", "emailAddress": "owner@example.com", "displayName": "Owner"},
                {"id": "2", "type": "anyone", "role": "reader"},
            ]
        }
    )

    collaborators = list_collaborators("token", "sheet-id")

    assert len(collaborators) == 2
    anyone = next(c for c in collaborators if c.type == "anyone")
    assert anyone.role == "reader"
    assert anyone.email is None
    assert anyone.domain is None


@patch("app.google_sheets.build")
def test_list_collaborators_handles_domain_wide_permission(mock_build):
    mock_build.return_value = _service_returning(
        {
            "permissions": [
                {"id": "1", "type": "user", "role": "owner", "emailAddress": "owner@example.com", "displayName": "Owner"},
                {"id": "2", "type": "domain", "role": "writer", "domain": "example.com"},
            ]
        }
    )

    collaborators = list_collaborators("token", "sheet-id")

    domain_permission = next(c for c in collaborators if c.type == "domain")
    assert domain_permission.domain == "example.com"
    assert domain_permission.role == "writer"
    assert domain_permission.email is None


@patch("app.google_sheets.build")
def test_list_collaborators_single_owner_only(mock_build):
    mock_build.return_value = _service_returning(
        {"permissions": [{"id": "1", "type": "user", "role": "owner", "emailAddress": "solo@example.com", "displayName": "Solo Owner"}]}
    )

    collaborators = list_collaborators("token", "sheet-id")

    assert len(collaborators) == 1
    assert collaborators[0].role == "owner"


@patch("app.google_sheets.build")
def test_list_collaborators_follows_pagination(mock_build):
    mock_build.return_value = _service_returning(
        {
            "nextPageToken": "page-2",
            "permissions": [{"id": "1", "type": "user", "role": "owner", "emailAddress": "a@example.com", "displayName": "A"}],
        },
        {"permissions": [{"id": "2", "type": "user", "role": "reader", "emailAddress": "b@example.com", "displayName": "B"}]},
    )

    collaborators = list_collaborators("token", "sheet-id")

    assert [c.email for c in collaborators] == ["a@example.com", "b@example.com"]


@patch("app.google_sheets.build")
def test_list_collaborators_maps_http_403_like_other_sheets_calls(mock_build):
    service = MagicMock()
    service.permissions.return_value.list.return_value.execute.side_effect = _http_error(403)
    mock_build.return_value = service

    with pytest.raises(SheetsAccessError) as exc_info:
        list_collaborators("token", "sheet-id")

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == "You don't have access to this spreadsheet."


@patch("app.google_sheets.build")
def test_list_collaborators_maps_http_404(mock_build):
    service = MagicMock()
    service.permissions.return_value.list.return_value.execute.side_effect = _http_error(404)
    mock_build.return_value = service

    with pytest.raises(SheetsAccessError) as exc_info:
        list_collaborators("token", "sheet-id")

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# GET /sheets/{spreadsheet_id}/collaborators
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(main_module.app)


def test_collaborators_endpoint_returns_list_and_total_count(client, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "list_collaborators",
        lambda token, sid: [
            Collaborator(type="user", role="owner", email="owner@example.com", display_name="Owner"),
            Collaborator(type="user", role="writer", email="editor@example.com", display_name="Editor"),
            Collaborator(type="anyone", role="reader"),
        ],
    )

    response = client.get(
        "/sheets/mock-id/collaborators", headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 3
    assert len(body["collaborators"]) == 3
    assert body["collaborators"][2]["type"] == "anyone"
    assert body["collaborators"][2]["email"] is None


def test_collaborators_endpoint_single_owner(client, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "list_collaborators",
        lambda token, sid: [Collaborator(type="user", role="owner", email="solo@example.com", display_name="Solo")],
    )

    response = client.get("/sheets/mock-id/collaborators", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json()["total_count"] == 1


@pytest.mark.parametrize("status_code", [401, 403, 404])
def test_collaborators_endpoint_reuses_the_existing_error_mapping(client, monkeypatch, status_code):
    def boom(token, sid):
        raise SheetsAccessError(status_code, "mapped error message")

    monkeypatch.setattr(main_module, "list_collaborators", boom)

    response = client.get("/sheets/mock-id/collaborators", headers={"Authorization": "Bearer bad-token"})
    assert response.status_code == status_code
    assert response.json()["detail"] == "mapped error message"


def test_collaborators_endpoint_requires_authorization_header(client):
    response = client.get("/sheets/mock-id/collaborators")
    assert response.status_code == 401  # HTTPBearer's own rejection of a missing header
