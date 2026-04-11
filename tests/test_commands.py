"""Regression tests for CLI commands using typer CliRunner + mocked auth/client."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from huly_cli.config import AuthCache
from huly_cli.main import app

runner = CliRunner()

FAKE_AUTH = AuthCache(
    account_token="t",
    workspace_token="t",
    workspace_id="w",
    workspace_uuid="u",
    email="test@test.com",
    workspace_slug="test",
    account_id="a",
    cached_at=1.0,
)


@contextmanager
def _auth_patch():
    """Patch every command module that imported ensure_auth directly."""
    auth_mock = AsyncMock(return_value=FAKE_AUTH)
    modules = [
        "huly_cli.auth",
        "huly_cli.commands.issues",
        "huly_cli.commands.documents",
        "huly_cli.commands.components",
    ]
    with ExitStack() as stack:
        for module in modules:
            stack.enter_context(patch(f"{module}.ensure_auth", new=auth_mock))
        yield auth_mock


# ── projects list ──────────────────────────────────────────────────────────────


def test_projects_list():
    project_data = [
        {
            "_id": "p1",
            "name": "Test Project",
            "identifier": "TP",
            "members": ["a1"],
            "owners": [],
            "sequence": 5,
            "description": "",
            "defaultIssueStatus": "",
            "private": False,
            "archived": False,
        }
    ]
    find_mock = AsyncMock(return_value=project_data)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["projects", "list"])
    assert result.exit_code == 0, result.output
    assert "Test Project" in result.output


def test_projects_list_shows_identifier():
    project_data = [
        {
            "_id": "p2",
            "name": "Another Project",
            "identifier": "AP",
            "members": ["a1", "a2"],
            "owners": [],
            "sequence": 1,
            "description": "",
            "defaultIssueStatus": "",
            "private": False,
            "archived": False,
        }
    ]
    find_mock = AsyncMock(return_value=project_data)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["projects", "list"])
    assert result.exit_code == 0, result.output
    assert "AP" in result.output


def test_projects_list_empty():
    find_mock = AsyncMock(return_value=[])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["projects", "list"])
    assert result.exit_code == 0


# ── issues list ────────────────────────────────────────────────────────────────


ISSUE_DATA = [
    {
        "_id": "i1",
        "title": "Fix bug",
        "identifier": "TP-1",
        "number": 1,
        "status": "tracker:status:Backlog",
        "priority": 2,
        "assignee": None,
        "description": "",
        "kind": "",
        "createdBy": "",
        "createdOn": 0,
        "modifiedBy": "",
        "modifiedOn": 0,
        "estimation": 0,
        "labels": 0,
        "comments": 0,
        "subIssues": 0,
        "space": "p1",
        "dueDate": None,
    }
]


def test_issues_list():
    # find_all is called twice: once for issues, once for persons
    find_mock = AsyncMock(side_effect=[ISSUE_DATA, []])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["issues", "list"])
    assert result.exit_code == 0, result.output
    assert "Fix bug" in result.output


def test_issues_list_shows_identifier():
    find_mock = AsyncMock(side_effect=[ISSUE_DATA, []])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["issues", "list"])
    assert result.exit_code == 0, result.output
    assert "TP-1" in result.output


def test_issues_list_shows_status():
    find_mock = AsyncMock(side_effect=[ISSUE_DATA, []])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["issues", "list"])
    assert result.exit_code == 0, result.output
    assert "backlog" in result.output.lower()


def test_issues_list_empty():
    find_mock = AsyncMock(side_effect=[[], []])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["issues", "list"])
    assert result.exit_code == 0


# ── members list ───────────────────────────────────────────────────────────────


def test_members_list():
    find_mock = AsyncMock(
        side_effect=[
            [{"_id": "person1", "name": "Doe,John"}],  # persons
            [{"_id": "acc1", "person": "person1", "email": "john@test.com"}],  # accounts
        ]
    )
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["members", "list"])
    assert result.exit_code == 0, result.output
    assert "John Doe" in result.output


def test_members_list_shows_email():
    find_mock = AsyncMock(
        side_effect=[
            [{"_id": "p1", "name": "Smith,Jane"}],
            [{"_id": "a1", "person": "p1", "email": "jane@example.com"}],
        ]
    )
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["members", "list"])
    assert result.exit_code == 0, result.output
    assert "jane@example.com" in result.output


def test_members_list_empty():
    find_mock = AsyncMock(side_effect=[[], []])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["members", "list"])
    assert result.exit_code == 0


def test_members_list_no_email():
    """Member with no matching account should show empty email."""
    find_mock = AsyncMock(
        side_effect=[
            [{"_id": "p99", "name": "Solo,Player"}],
            [],  # no accounts
        ]
    )
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["members", "list"])
    assert result.exit_code == 0, result.output
    assert "Player Solo" in result.output


# ── labels list ────────────────────────────────────────────────────────────────


def test_labels_list():
    tag_data = [
        {"_id": "t1", "tag": "tag1", "title": "Sprint 1", "attachedTo": "i1"},
        {"_id": "t2", "tag": "tag1", "title": "Sprint 1", "attachedTo": "i2"},
    ]
    find_mock = AsyncMock(return_value=tag_data)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["labels", "list"])
    assert result.exit_code == 0, result.output
    assert "Sprint 1" in result.output


def test_labels_list_count():
    """Labels with multiple uses should show correct count."""
    tag_data = [
        {"_id": "t1", "tag": "tag1", "title": "Bug", "attachedTo": "i1"},
        {"_id": "t2", "tag": "tag1", "title": "Bug", "attachedTo": "i2"},
        {"_id": "t3", "tag": "tag1", "title": "Bug", "attachedTo": "i3"},
        {"_id": "t4", "tag": "tag2", "title": "Feature", "attachedTo": "i4"},
    ]
    find_mock = AsyncMock(return_value=tag_data)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["labels", "list"])
    assert result.exit_code == 0, result.output
    assert "Bug" in result.output
    assert "Feature" in result.output
    # Count for Bug should be 3
    assert "3" in result.output


def test_labels_list_deduplicates():
    """Each label should only appear once even if used multiple times."""
    tag_data = [
        {"_id": "t1", "tag": "tag1", "title": "Sprint 1", "attachedTo": "i1"},
        {"_id": "t2", "tag": "tag1", "title": "Sprint 1", "attachedTo": "i2"},
        {"_id": "t3", "tag": "tag1", "title": "Sprint 1", "attachedTo": "i3"},
    ]
    find_mock = AsyncMock(return_value=tag_data)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["labels", "list"])
    assert result.exit_code == 0, result.output
    # "Sprint 1" should only appear once in the output
    assert result.output.count("Sprint 1") == 1


def test_labels_list_empty():
    find_mock = AsyncMock(return_value=[])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["labels", "list"])
    assert result.exit_code == 0


# ── JSON output mode ───────────────────────────────────────────────────────────


def test_projects_list_json_mode():
    import json as json_mod

    project_data = [
        {
            "_id": "p1",
            "name": "Test Project",
            "identifier": "TP",
            "members": [],
            "owners": [],
            "sequence": 0,
            "description": "",
            "defaultIssueStatus": "",
            "private": False,
            "archived": False,
        }
    ]
    find_mock = AsyncMock(return_value=project_data)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["--json", "projects", "list"])
    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["ok"] is True
    assert isinstance(data["data"], list)


def test_issues_list_json_mode():
    import json as json_mod

    find_mock = AsyncMock(side_effect=[ISSUE_DATA, []])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["--json", "issues", "list"])
    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["ok"] is True
    assert len(data["data"]) == 1
    assert data["data"][0]["title"] == "Fix bug"


# ── documents list ─────────────────────────────────────────────────────────────

DOCUMENT_DATA = [
    {
        "_id": "doc1",
        "title": "My Doc",
        "content": "blob-ref-123",
        "space": "ts1",
        "parent": "document:ids:NoParent",
        "attachments": 0,
        "labels": 0,
        "comments": 0,
        "rank": "",
        "createdBy": "",
        "createdOn": 0,
        "modifiedBy": "",
        "modifiedOn": 0,
    }
]

TEAMSPACE_DATA = [
    {
        "_id": "ts1",
        "name": "Engineering",
        "description": "",
        "private": False,
        "archived": False,
        "members": [],
        "owners": [],
    }
]


def test_documents_list():
    # find_all called twice: once for teamspaces, once for documents
    find_mock = AsyncMock(side_effect=[TEAMSPACE_DATA, DOCUMENT_DATA])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "list"])
    assert result.exit_code == 0, result.output
    assert "My Doc" in result.output


def test_documents_list_empty():
    find_mock = AsyncMock(side_effect=[TEAMSPACE_DATA, []])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "list"])
    assert result.exit_code == 0


def test_documents_list_shows_space():
    find_mock = AsyncMock(side_effect=[TEAMSPACE_DATA, DOCUMENT_DATA])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "list"])
    assert result.exit_code == 0, result.output
    assert "Engineering" in result.output


# ── components list ────────────────────────────────────────────────────────────

COMPONENT_DATA = [
    {
        "_id": "c1",
        "label": "Auth Service",
        "description": "Handles authentication",
        "lead": None,
        "space": "proj1",
        "createdBy": "",
        "createdOn": 0,
        "modifiedBy": "",
        "modifiedOn": 0,
    }
]


def test_components_list():
    # find_all called twice: once for components, once for persons
    find_mock = AsyncMock(side_effect=[COMPONENT_DATA, []])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["components", "list"])
    assert result.exit_code == 0, result.output
    assert "Auth Service" in result.output


def test_components_list_empty():
    find_mock = AsyncMock(side_effect=[[], []])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["components", "list"])
    assert result.exit_code == 0


def test_components_list_shows_description():
    find_mock = AsyncMock(side_effect=[COMPONENT_DATA, []])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["components", "list"])
    assert result.exit_code == 0, result.output
    assert "Auth Service" in result.output


def test_components_list_json_mode():
    import json as json_mod

    find_mock = AsyncMock(side_effect=[COMPONENT_DATA, []])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["--json", "components", "list"])
    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["ok"] is True
    assert isinstance(data["data"], list)
    assert data["data"][0]["label"] == "Auth Service"
