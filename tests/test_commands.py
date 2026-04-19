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
        "huly_cli.commands.labels",
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


def test_issues_list_handles_null_person_name():
    """issues list must not crash when a workspace person has name=None."""
    issue_with_assignee = [
        {
            "_id": "i2",
            "title": "Null name issue",
            "identifier": "TP-2",
            "number": 2,
            "status": "tracker:status:Backlog",
            "priority": 0,
            "assignee": "person-null",
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
    persons_with_null_name = [{"_id": "person-null", "name": None}]
    find_mock = AsyncMock(side_effect=[issue_with_assignee, persons_with_null_name])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["issues", "list"])
    assert result.exit_code == 0, result.output
    assert "Null name issue" in result.output


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


def test_labels_list_handles_null_title():
    """labels list must not crash when a TagReference has title=None."""
    tag_data = [
        {"_id": "t1", "tag": "tag1", "title": "Real Label", "attachedTo": "i1"},
        {"_id": "t2", "tag": "tag2", "title": None, "attachedTo": "i2"},
    ]
    find_mock = AsyncMock(return_value=tag_data)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["labels", "list"])
    assert result.exit_code == 0, result.output
    assert "Real Label" in result.output


# ── labels CRUD ───────────────────────────────────────────────────────────────

TAG_DETAIL_DATA = [
    {
        "_id": "t1",
        "tag": "tag1",
        "title": "Bug",
        "color": 1,
        "attachedTo": "i1",
        "space": "p1",
        "createdBy": "",
        "createdOn": 0,
        "modifiedBy": "",
        "modifiedOn": 0,
    }
]

PROJECT_DATA = [
    {
        "_id": "proj1",
        "name": "Test",
        "identifier": "TP",
        "members": [],
        "owners": [],
        "sequence": 5,
        "description": "",
        "defaultIssueStatus": "tracker:status:Backlog",
        "private": False,
        "archived": False,
    }
]


def test_labels_get_returns_detail():
    find_mock = AsyncMock(return_value=TAG_DETAIL_DATA)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["labels", "get", "t1"])
    assert result.exit_code == 0, result.output
    assert "Bug" in result.output


def test_labels_get_not_found_exits_nonzero():
    find_mock = AsyncMock(return_value=[])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["labels", "get", "t1"])
    assert result.exit_code == 1


def test_labels_create_writes_create_doc_tx():
    tx_mock = AsyncMock(return_value={})
    find_mock = AsyncMock(return_value=PROJECT_DATA)

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["labels", "create", "--title", "Bug", "--project", "TP"])

    assert result.exit_code == 0, result.output
    create_tx = tx_mock.await_args.args[0]
    assert create_tx["_class"] == "core:class:TxCreateDoc"
    assert create_tx["objectClass"] == "tags:class:TagReference"


def test_labels_create_project_not_found_exits_nonzero():
    find_mock = AsyncMock(return_value=[])
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["labels", "create", "--title", "Bug", "--project", "MISSING"])

    assert result.exit_code == 1
    tx_mock.assert_not_awaited()


def test_labels_update_writes_update_doc_tx():
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=TAG_DETAIL_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["labels", "update", "t1", "--title", "Feature"])

    assert result.exit_code == 0, result.output
    update_tx = tx_mock.await_args.args[0]
    assert update_tx["_class"] == "core:class:TxUpdateDoc"
    assert update_tx["objectClass"] == "tags:class:TagReference"
    assert update_tx["operations"]["title"] == "Feature"


def test_labels_update_no_fields_warns():
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=TAG_DETAIL_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["labels", "update", "t1"])

    assert result.exit_code == 0, result.output
    tx_mock.assert_not_awaited()


def test_labels_update_not_found_exits_nonzero():
    find_mock = AsyncMock(return_value=[])
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["labels", "update", "missing-id", "--title", "X"])

    assert result.exit_code == 1
    tx_mock.assert_not_awaited()


def test_labels_delete_removes_label():
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=TAG_DETAIL_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["labels", "delete", "t1"])

    assert result.exit_code == 0, result.output
    assert "deleted" in result.output.lower()
    delete_tx = tx_mock.await_args.args[0]
    assert delete_tx["_class"] == "core:class:TxRemoveDoc"
    assert delete_tx["objectClass"] == "tags:class:TagReference"
    assert delete_tx["objectId"] == "t1"


def test_labels_delete_not_found_exits_nonzero():
    find_mock = AsyncMock(return_value=[])
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["labels", "delete", "missing-id"])

    assert result.exit_code == 1
    tx_mock.assert_not_awaited()


# ── issues create with new flags ──────────────────────────────────────────────


def _issue_create_find_side_effects(*, extra_finds=None):
    """Build find_all side_effect list for a minimal issues create invocation.

    Order: project lookup, issues-for-rank.
    extra_finds are inserted after project lookup (before rank).
    """
    result = [PROJECT_DATA]
    if extra_finds:
        result.extend(extra_finds)
    # issues for rank (empty → fallback rank)
    result.append([])
    return result


def test_issues_create_with_due_date():
    find_mock = AsyncMock(side_effect=_issue_create_find_side_effects())
    tx_mock = AsyncMock(
        side_effect=[
            {"object": {"sequence": 5}},  # sequence increment
            {},  # issue create
        ]
    )

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["issues", "create", "--title", "Test", "--project", "TP", "--due-date", "2024-06-15"],
        )

    assert result.exit_code == 0, result.output
    # The issue create tx is the second tx call
    create_tx = tx_mock.await_args_list[1].args[0]
    assert create_tx["attributes"]["dueDate"] == 1718409600000


def test_issues_create_with_component():
    component_find = [{"_id": "comp1", "label": "Auth Service", "space": "proj1"}]
    find_mock = AsyncMock(side_effect=_issue_create_find_side_effects(extra_finds=[component_find]))
    tx_mock = AsyncMock(
        side_effect=[
            {"object": {"sequence": 5}},
            {},
        ]
    )

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            [
                "issues",
                "create",
                "--title",
                "Test",
                "--project",
                "TP",
                "--component",
                "Auth Service",
            ],
        )

    assert result.exit_code == 0, result.output
    create_tx = tx_mock.await_args_list[1].args[0]
    assert create_tx["attributes"]["component"] == "comp1"


def test_issues_create_with_label():
    # Label resolve returns [] (no existing tag), then attach emits a tx
    label_find = [{"_id": "tr1", "tag": "tag-bug", "title": "Bug", "attachedTo": "other"}]
    find_mock = AsyncMock(
        side_effect=[
            PROJECT_DATA,  # project lookup
            [],  # issues for rank
            label_find,  # _resolve_label_tag
        ]
    )
    tx_mock = AsyncMock(
        side_effect=[
            {"object": {"sequence": 5}},  # sequence increment
            {},  # issue create
            {},  # tag attach
        ]
    )

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["issues", "create", "--title", "Test", "--project", "TP", "--label", "Bug"],
        )

    assert result.exit_code == 0, result.output
    # Third tx call is the tag attachment
    tag_tx = tx_mock.await_args_list[2].args[0]
    assert tag_tx["_class"] == "core:class:TxCreateDoc"
    assert tag_tx["objectClass"] == "tags:class:TagReference"
    assert tag_tx["attributes"]["title"] == "Bug"


# ── issues update with new flags ──────────────────────────────────────────────


def test_issues_update_with_due_date():
    find_mock = AsyncMock(return_value=ISSUE_DATA)
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["issues", "update", "TP-1", "--due-date", "2024-06-15"])

    assert result.exit_code == 0, result.output
    update_tx = tx_mock.await_args.args[0]
    assert update_tx["operations"]["dueDate"] == 1718409600000


def test_issues_update_clear_due_date():
    find_mock = AsyncMock(return_value=ISSUE_DATA)
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["issues", "update", "TP-1", "--due-date", ""])

    assert result.exit_code == 0, result.output
    update_tx = tx_mock.await_args.args[0]
    assert update_tx["operations"]["dueDate"] is None


def test_issues_update_with_component():
    component_find = [{"_id": "comp1", "label": "Auth Service", "space": "proj1"}]
    find_mock = AsyncMock(side_effect=[ISSUE_DATA, component_find])
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["issues", "update", "TP-1", "--component", "Auth Service"])

    assert result.exit_code == 0, result.output
    update_tx = tx_mock.await_args.args[0]
    assert update_tx["operations"]["component"] == "comp1"


def test_issues_update_clear_component():
    find_mock = AsyncMock(return_value=ISSUE_DATA)
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["issues", "update", "TP-1", "--component", ""])

    assert result.exit_code == 0, result.output
    update_tx = tx_mock.await_args.args[0]
    assert update_tx["operations"]["component"] is None


def test_issues_update_with_label():
    label_find = [{"_id": "tr1", "tag": "tag-bug", "title": "Bug", "attachedTo": "other"}]
    find_mock = AsyncMock(side_effect=[ISSUE_DATA, label_find])
    tx_mock = AsyncMock(
        side_effect=[
            {},  # tag attach
            {},  # (no update tx since only labels, no operations)
        ]
    )

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["issues", "update", "TP-1", "--label", "Bug"])

    assert result.exit_code == 0, result.output
    # First tx call is the tag attachment
    tag_tx = tx_mock.await_args_list[0].args[0]
    assert tag_tx["_class"] == "core:class:TxCreateDoc"
    assert tag_tx["objectClass"] == "tags:class:TagReference"
    assert tag_tx["attributes"]["title"] == "Bug"


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


# ── documents discovery filters (#37) ─────────────────────────────────────────


def _doc(doc_id: str, title: str, parent: str = "document:ids:NoParent") -> dict:
    return {
        "_id": doc_id,
        "title": title,
        "content": "",
        "space": "ts1",
        "parent": parent,
        "attachments": 0,
        "labels": 0,
        "comments": 0,
        "rank": "",
        "createdBy": "",
        "createdOn": 0,
        "modifiedBy": "",
        "modifiedOn": 0,
    }


def test_documents_list_title_contains_filters_case_insensitive():
    """--title-contains should be a case-insensitive substring filter on title."""
    docs = [
        _doc("doc-1", "RAG Template"),
        _doc("doc-2", "Unrelated note"),
        _doc("doc-3", "lower rag match"),
    ]
    find_mock = AsyncMock(side_effect=[TEAMSPACE_DATA, docs])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "list", "--title-contains", "RAG"])
    assert result.exit_code == 0, result.output
    assert "RAG Template" in result.output
    assert "lower rag match" in result.output
    assert "Unrelated note" not in result.output


def test_documents_list_parent_filter_passes_parent_to_find_all():
    """--parent PARENT_ID should forward parent into the find-all query."""
    find_mock = AsyncMock(
        side_effect=[TEAMSPACE_DATA, [_doc("doc-child", "Child doc", "doc-parent")]]
    )
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "list", "--parent", "doc-parent"])
    assert result.exit_code == 0, result.output
    assert "Child doc" in result.output
    # Second find_all call is the documents query; it should include parent in its query arg
    docs_call = find_mock.await_args_list[1]
    assert docs_call.kwargs["query"]["parent"] == "doc-parent"


def test_documents_get_by_title_resolves_unique_match():
    """documents get --title TITLE returns the doc when exactly one match exists."""
    docs = [
        _doc("doc-1", "My RAG Template"),
        _doc("doc-2", "Something else"),
    ]
    # Order in docs_get: _resolve_document_by_title find_all, then teamspace find_all
    find_mock = AsyncMock(side_effect=[docs, TEAMSPACE_DATA])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "get", "--title", "my rag template"])
    assert result.exit_code == 0, result.output
    assert "My RAG Template" in result.output
    assert "doc-1" in result.output


def test_documents_get_by_title_errors_on_multiple_matches():
    """Multiple title matches must error with a table of (title, id) pairs — no silent pick."""
    docs = [
        _doc("doc-1", "Design Doc"),
        _doc("doc-2", "Design Doc"),
    ]
    find_mock = AsyncMock(return_value=docs)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "get", "--title", "Design Doc"])
    assert result.exit_code == 1
    assert "multiple" in result.output.lower()
    assert "doc-1" in result.output
    assert "doc-2" in result.output


def test_documents_get_by_title_not_found_exits_nonzero():
    """documents get --title with no match should exit 1 with a clear message."""
    find_mock = AsyncMock(return_value=[_doc("doc-1", "Something")])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "get", "--title", "nonexistent"])
    assert result.exit_code == 1
    assert "no document matched" in result.output.lower()


def test_documents_get_requires_doc_id_or_title():
    """documents get called with neither DOC_ID nor --title must exit 1."""
    with _auth_patch():
        result = runner.invoke(app, ["documents", "get"])
    assert result.exit_code == 1
    assert "either" in result.output.lower()


def test_documents_get_rejects_both_doc_id_and_title():
    """documents get with both DOC_ID and --title must exit 1."""
    with _auth_patch():
        result = runner.invoke(app, ["documents", "get", "doc-1", "--title", "Thing"])
    assert result.exit_code == 1
    assert "either" in result.output.lower()


def test_documents_describe_by_title_resolves_unique_match():
    """documents describe --title TITLE reads the doc content when exactly one match exists."""
    docs = [
        _doc("doc-1", "My RAG Template"),
    ]
    # describe read path: resolve title, then since content is empty, it short-circuits
    find_mock = AsyncMock(return_value=docs)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "describe", "--title", "my rag template"])
    # Empty content triggers "No content available" error; we still verified the title resolved
    assert result.exit_code == 1
    assert "My RAG Template" in result.output


def test_documents_describe_by_title_errors_on_multiple_matches():
    """documents describe --title with duplicate titles must surface all matches."""
    docs = [
        _doc("doc-1", "Design Doc"),
        _doc("doc-2", "Design Doc"),
    ]
    find_mock = AsyncMock(return_value=docs)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "describe", "--title", "Design Doc"])
    assert result.exit_code == 1
    assert "multiple" in result.output.lower()
    assert "doc-1" in result.output
    assert "doc-2" in result.output


def test_documents_search_filters_by_title_substring():
    """documents search QUERY wraps list with a client-side title-substring filter."""
    docs = [
        _doc("doc-1", "RAG Template"),
        _doc("doc-2", "Unrelated note"),
        _doc("doc-3", "Another RAG doc"),
    ]
    # search calls find_all twice: once for teamspaces, once for documents
    find_mock = AsyncMock(side_effect=[TEAMSPACE_DATA, docs])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "search", "rag"])
    assert result.exit_code == 0, result.output
    assert "RAG Template" in result.output
    assert "Another RAG doc" in result.output
    assert "Unrelated note" not in result.output


def test_documents_search_empty_result_exits_zero():
    """documents search with no title matches should still exit 0."""
    docs = [_doc("doc-1", "Unrelated note")]
    find_mock = AsyncMock(side_effect=[TEAMSPACE_DATA, docs])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["documents", "search", "nothing matches"])
    assert result.exit_code == 0, result.output
    assert "Unrelated note" not in result.output


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


def test_components_list_handles_null_person_name():
    """components list must not crash when a person in the API response has name=None."""
    component_with_lead = [
        {
            "_id": "c2",
            "label": "Null Lead Component",
            "description": "Has a lead with null name",
            "lead": "person-null",
            "space": "proj1",
            "createdBy": "",
            "createdOn": 0,
            "modifiedBy": "",
            "modifiedOn": 0,
        }
    ]
    persons_with_null_name = [{"_id": "person-null", "name": None}]
    find_mock = AsyncMock(side_effect=[component_with_lead, persons_with_null_name])
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["components", "list"])
    assert result.exit_code == 0, result.output
    assert "Null Lead Component" in result.output


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


def test_components_delete_removes_component():
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=COMPONENT_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["components", "delete", "c1"])

    assert result.exit_code == 0, result.output
    assert "Component c1 deleted." in result.output
    assert tx_mock.await_args.args[0] == {
        "_class": "core:class:TxRemoveDoc",
        "objectClass": "tracker:class:Component",
        "objectSpace": "proj1",
        "objectId": "c1",
    }


# ── projects get ───────────────────────────────────────────────────────────────


def test_projects_get_by_identifier():
    """projects get DEMO returns project details when identifier matches (case-insensitive)."""
    project_data = [
        {
            "_id": "p-demo",
            "name": "Demo Project",
            "identifier": "DEMO",
            "members": ["a1", "a2"],
            "owners": ["a1"],
            "sequence": 17,
            "description": "A demo project.",
            "defaultIssueStatus": "tracker:status:Backlog",
            "private": False,
            "archived": False,
        }
    ]
    find_mock = AsyncMock(return_value=project_data)
    with _auth_patch(), patch("huly_cli.client.HulyClient.find_all", find_mock):
        result = runner.invoke(app, ["projects", "get", "demo"])
    assert result.exit_code == 0, result.output
    assert "DEMO" in result.output
    assert "Demo Project" in result.output


def test_projects_get_by_internal_id():
    """projects get matches by internal _id when identifier doesn't match."""
    project_data = [
        {
            "_id": "p-demo",
            "name": "Demo Project",
            "identifier": "DEMO",
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
        result = runner.invoke(app, ["projects", "get", "p-demo"])
    assert result.exit_code == 0, result.output
    assert "Demo Project" in result.output


def test_projects_get_not_found_exits_nonzero():
    """projects get raises NotFoundError when no project matches the identifier."""
    project_data = [
        {
            "_id": "p1",
            "name": "Other Project",
            "identifier": "OTHER",
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
        result = runner.invoke(app, ["projects", "get", "MISSING"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower() or "MISSING" in result.output


def test_projects_get_json_mode():
    """projects get emits JSON envelope when --json is set."""
    import json as json_mod

    project_data = [
        {
            "_id": "p-demo",
            "name": "Demo Project",
            "identifier": "DEMO",
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
        result = runner.invoke(app, ["--json", "projects", "get", "DEMO"])
    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["ok"] is True
    assert data["data"]["identifier"] == "DEMO"
    assert data["data"]["name"] == "Demo Project"


# ── components create / update ────────────────────────────────────────────────


def test_components_create_writes_create_doc_tx():
    """components create resolves project, generates an id, and emits a TxCreateDoc."""
    project_data = [
        {
            "_id": "proj1",
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
    tx_mock = AsyncMock(return_value={})
    find_mock = AsyncMock(return_value=project_data)

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            [
                "components",
                "create",
                "--label",
                "Auth Service",
                "--project",
                "TP",
                "--description",
                "Handles auth",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Component created" in result.output
    create_tx = tx_mock.await_args.args[0]
    assert create_tx["_class"] == "core:class:TxCreateDoc"
    assert create_tx["objectClass"] == "tracker:class:Component"
    assert create_tx["objectSpace"] == "proj1"
    assert create_tx["attributes"]["label"] == "Auth Service"
    assert create_tx["attributes"]["description"] == "Handles auth"
    assert create_tx["attributes"]["lead"] is None


def test_components_create_with_lead_resolves_person():
    """components create with --lead fuzzy-matches the lead person and stores the person id."""
    project_data = [
        {
            "_id": "proj1",
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
    person_data = [{"_id": "person-1", "name": "Doe,John"}]
    find_mock = AsyncMock(side_effect=[project_data, person_data])
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            [
                "components",
                "create",
                "--label",
                "Auth Service",
                "--project",
                "TP",
                "--lead",
                "john",
            ],
        )

    assert result.exit_code == 0, result.output
    create_tx = tx_mock.await_args.args[0]
    assert create_tx["attributes"]["lead"] == "person-1"


def test_components_create_project_not_found_exits_nonzero():
    """components create exits with code 1 when the project identifier does not resolve."""
    find_mock = AsyncMock(return_value=[])  # no projects
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["components", "create", "--label", "X", "--project", "MISSING"],
        )

    assert result.exit_code == 1
    tx_mock.assert_not_awaited()


def test_components_update_writes_update_doc_tx():
    """components update applies provided fields as a TxUpdateDoc."""
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=COMPONENT_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["components", "update", "c1", "--label", "Renamed", "--description", "Updated"],
        )

    assert result.exit_code == 0, result.output
    assert "Component c1 updated." in result.output
    update_tx = tx_mock.await_args.args[0]
    assert update_tx["_class"] == "core:class:TxUpdateDoc"
    assert update_tx["objectClass"] == "tracker:class:Component"
    assert update_tx["objectSpace"] == "proj1"
    assert update_tx["objectId"] == "c1"
    assert update_tx["operations"] == {"label": "Renamed", "description": "Updated"}


def test_components_update_unassigns_lead_with_empty_string():
    """components update --lead "" should null out the lead field."""
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=COMPONENT_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["components", "update", "c1", "--lead", ""])

    assert result.exit_code == 0, result.output
    update_tx = tx_mock.await_args.args[0]
    assert update_tx["operations"] == {"lead": None}


def test_components_update_no_fields_warns_and_skips_tx():
    """components update with no fields prints a warning and does not emit a tx."""
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=COMPONENT_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["components", "update", "c1"])

    assert result.exit_code == 0, result.output
    tx_mock.assert_not_awaited()


def test_components_update_not_found_exits_nonzero():
    """components update exits with code 1 when the component is not found."""
    find_mock = AsyncMock(return_value=[])
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["components", "update", "missing-id", "--label", "X"])

    assert result.exit_code == 1
    tx_mock.assert_not_awaited()
