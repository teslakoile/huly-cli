"""Regression tests for milestones and templates CLI commands."""

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
        "huly_cli.commands.milestones",
        "huly_cli.commands.templates",
    ]
    with ExitStack() as stack:
        for module in modules:
            stack.enter_context(patch(f"{module}.ensure_auth", new=auth_mock))
        yield auth_mock


# ── milestones list ────────────────────────────────────────────────────────────

MILESTONE_DATA = [
    {
        "_id": "m1",
        "label": "Sprint 1",
        "status": 0,
        "targetDate": None,
        "comments": 0,
        "space": "p1",
        "createdBy": "",
        "createdOn": 0,
        "modifiedBy": "",
        "modifiedOn": 0,
    }
]


def test_milestones_list():
    find_mock = AsyncMock(return_value=MILESTONE_DATA)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["milestones", "list"])
    assert result.exit_code == 0, result.output
    assert "Sprint 1" in result.output


def test_milestones_list_shows_status():
    find_mock = AsyncMock(return_value=MILESTONE_DATA)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["milestones", "list"])
    assert result.exit_code == 0, result.output
    assert "planned" in result.output.lower()


def test_milestones_list_empty():
    find_mock = AsyncMock(return_value=[])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["milestones", "list"])
    assert result.exit_code == 0


def test_milestones_list_json_mode():
    import json as json_mod

    find_mock = AsyncMock(return_value=MILESTONE_DATA)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["--json", "milestones", "list"])
    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["ok"] is True
    assert isinstance(data["data"], list)


def test_milestones_list_with_project_filter():
    project_data = [{"_id": "p1", "identifier": "TP", "name": "Test Project"}]
    find_mock = AsyncMock(side_effect=[project_data, MILESTONE_DATA])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["milestones", "list", "--project", "TP"])
    assert result.exit_code == 0, result.output
    assert "Sprint 1" in result.output


# ── templates list ─────────────────────────────────────────────────────────────

TEMPLATE_DATA = [
    {
        "_id": "tmpl1",
        "title": "Bug Report",
        "description": "",
        "assignee": None,
        "component": None,
        "milestone": None,
        "priority": 1,
        "estimation": 0,
        "children": [],
        "comments": 0,
        "attachments": 0,
        "labels": 0,
        "kind": "",
        "relations": [],
        "space": "p1",
    }
]


def test_templates_list():
    find_mock = AsyncMock(return_value=TEMPLATE_DATA)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["templates", "list"])
    assert result.exit_code == 0, result.output
    assert "Bug Report" in result.output


def test_templates_list_shows_priority():
    find_mock = AsyncMock(return_value=TEMPLATE_DATA)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["templates", "list"])
    assert result.exit_code == 0, result.output
    assert "Urgent" in result.output


def test_templates_list_empty():
    find_mock = AsyncMock(return_value=[])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["templates", "list"])
    assert result.exit_code == 0


def test_templates_list_json_mode():
    import json as json_mod

    find_mock = AsyncMock(return_value=TEMPLATE_DATA)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["--json", "templates", "list"])
    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["ok"] is True
    assert len(data["data"]) == 1
    assert data["data"][0]["title"] == "Bug Report"


def test_templates_list_multiple():
    template_data = [
        {
            "_id": "t1",
            "title": "Template A",
            "description": "",
            "priority": 0,
            "kind": "",
            "space": "p1",
            "assignee": None,
            "component": None,
            "milestone": None,
            "estimation": 0,
            "children": [],
            "comments": 0,
            "attachments": 0,
            "labels": 0,
            "relations": [],
        },
        {
            "_id": "t2",
            "title": "Template B",
            "description": "",
            "priority": 2,
            "kind": "",
            "space": "p1",
            "assignee": None,
            "component": None,
            "milestone": None,
            "estimation": 0,
            "children": [],
            "comments": 0,
            "attachments": 0,
            "labels": 0,
            "relations": [],
        },
    ]
    find_mock = AsyncMock(return_value=template_data)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["templates", "list"])
    assert result.exit_code == 0, result.output
    assert "Template A" in result.output
    assert "Template B" in result.output


def test_templates_list_with_project_filter():
    project_data = [{"_id": "p1", "identifier": "TP", "name": "Test Project"}]
    find_mock = AsyncMock(side_effect=[project_data, TEMPLATE_DATA])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["templates", "list", "--project", "TP"])
    assert result.exit_code == 0, result.output
    assert "Bug Report" in result.output


def test_milestones_list_multiple_statuses():
    """Milestones with different statuses should all appear."""
    milestone_data = [
        {
            "_id": "m1",
            "label": "Sprint 1",
            "status": 0,
            "targetDate": None,
            "comments": 0,
            "space": "p1",
            "createdBy": "",
            "createdOn": 0,
            "modifiedBy": "",
            "modifiedOn": 0,
        },
        {
            "_id": "m2",
            "label": "Sprint 2",
            "status": 2,
            "targetDate": 1700000000000,
            "comments": 0,
            "space": "p1",
            "createdBy": "",
            "createdOn": 0,
            "modifiedBy": "",
            "modifiedOn": 0,
        },
    ]
    find_mock = AsyncMock(return_value=milestone_data)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["milestones", "list"])
    assert result.exit_code == 0, result.output
    assert "Sprint 1" in result.output
    assert "Sprint 2" in result.output
    assert "completed" in result.output.lower()
