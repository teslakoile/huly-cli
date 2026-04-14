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


def test_milestones_delete_removes_milestone():
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=MILESTONE_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["milestones", "delete", "m1"])

    assert result.exit_code == 0, result.output
    assert "Milestone m1 deleted." in result.output
    assert tx_mock.await_args.args[0] == {
        "_class": "core:class:TxRemoveDoc",
        "objectClass": "tracker:class:Milestone",
        "objectSpace": "p1",
        "objectId": "m1",
    }


# ── _parse_date_ms unit tests ─────────────────────────────────────────────────


def test_parse_date_ms_valid_date_returns_utc_milliseconds():
    """_parse_date_ms parses YYYY-MM-DD and returns UTC ms timestamp."""
    from huly_cli.commands.milestones import _parse_date_ms

    # 2024-06-15 00:00:00 UTC == 1718409600 seconds == 1718409600000 ms
    assert _parse_date_ms("2024-06-15") == 1718409600000


def test_parse_date_ms_invalid_format_raises_value_error():
    """_parse_date_ms raises ValueError for malformed date strings."""
    import pytest

    from huly_cli.commands.milestones import _parse_date_ms

    with pytest.raises(ValueError):
        _parse_date_ms("not-a-date")


def test_parse_date_ms_empty_string_raises_value_error():
    """_parse_date_ms rejects empty strings (caller handles None separately)."""
    import pytest

    from huly_cli.commands.milestones import _parse_date_ms

    with pytest.raises(ValueError):
        _parse_date_ms("")


def test_parse_date_ms_wrong_format_raises_value_error():
    """_parse_date_ms rejects formats other than YYYY-MM-DD."""
    import pytest

    from huly_cli.commands.milestones import _parse_date_ms

    with pytest.raises(ValueError):
        _parse_date_ms("06/15/2024")


# ── milestones create ─────────────────────────────────────────────────────────


PROJECT_DATA = [
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


def test_milestones_create_writes_create_doc_tx():
    """milestones create resolves project, generates id, and emits a TxCreateDoc."""
    find_mock = AsyncMock(return_value=PROJECT_DATA)
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            [
                "milestones",
                "create",
                "--label",
                "Sprint 1",
                "--project",
                "TP",
                "--status",
                "planned",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Milestone created" in result.output
    create_tx = tx_mock.await_args.args[0]
    assert create_tx["_class"] == "core:class:TxCreateDoc"
    assert create_tx["objectClass"] == "tracker:class:Milestone"
    assert create_tx["objectSpace"] == "p1"
    assert create_tx["attributes"]["label"] == "Sprint 1"
    assert create_tx["attributes"]["status"] == 0  # planned
    assert create_tx["attributes"]["targetDate"] is None


def test_milestones_create_with_target_date_parses_to_ms():
    """milestones create --target-date 2024-06-15 stores UTC ms in targetDate."""
    find_mock = AsyncMock(return_value=PROJECT_DATA)
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            [
                "milestones",
                "create",
                "--label",
                "Sprint 1",
                "--project",
                "TP",
                "--target-date",
                "2024-06-15",
            ],
        )

    assert result.exit_code == 0, result.output
    create_tx = tx_mock.await_args.args[0]
    assert create_tx["attributes"]["targetDate"] == 1718409600000


def test_milestones_create_invalid_date_format_exits_nonzero():
    """milestones create --target-date invalid surfaces a HulyError and exits 1."""
    find_mock = AsyncMock(return_value=PROJECT_DATA)
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            [
                "milestones",
                "create",
                "--label",
                "Sprint 1",
                "--project",
                "TP",
                "--target-date",
                "not-a-date",
            ],
        )

    assert result.exit_code == 1
    assert "Invalid date" in result.output or "format" in result.output.lower()
    tx_mock.assert_not_awaited()


def test_milestones_create_invalid_status_exits_nonzero():
    """milestones create with an unknown --status raises HulyError and exits 1."""
    find_mock = AsyncMock(return_value=PROJECT_DATA)
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            [
                "milestones",
                "create",
                "--label",
                "Sprint 1",
                "--project",
                "TP",
                "--status",
                "bogus",
            ],
        )

    assert result.exit_code == 1
    tx_mock.assert_not_awaited()


def test_milestones_create_project_not_found_exits_nonzero():
    """milestones create exits with code 1 when the project identifier does not resolve."""
    find_mock = AsyncMock(return_value=[])
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["milestones", "create", "--label", "Sprint 1", "--project", "MISSING"],
        )

    assert result.exit_code == 1
    tx_mock.assert_not_awaited()


# ── milestones update ─────────────────────────────────────────────────────────


def test_milestones_update_writes_update_doc_tx():
    """milestones update applies provided fields as a TxUpdateDoc."""
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=MILESTONE_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["milestones", "update", "m1", "--label", "Renamed", "--status", "completed"],
        )

    assert result.exit_code == 0, result.output
    assert "Milestone m1 updated." in result.output
    update_tx = tx_mock.await_args.args[0]
    assert update_tx["_class"] == "core:class:TxUpdateDoc"
    assert update_tx["objectClass"] == "tracker:class:Milestone"
    assert update_tx["objectSpace"] == "p1"
    assert update_tx["objectId"] == "m1"
    assert update_tx["operations"]["label"] == "Renamed"
    assert update_tx["operations"]["status"] == 2  # completed


def test_milestones_update_with_target_date_parses_to_ms():
    """milestones update --target-date 2024-06-15 stores UTC ms in targetDate."""
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=MILESTONE_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["milestones", "update", "m1", "--target-date", "2024-06-15"],
        )

    assert result.exit_code == 0, result.output
    update_tx = tx_mock.await_args.args[0]
    assert update_tx["operations"]["targetDate"] == 1718409600000


def test_milestones_update_invalid_date_format_exits_nonzero():
    """milestones update --target-date invalid surfaces a HulyError and exits 1."""
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=MILESTONE_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["milestones", "update", "m1", "--target-date", "not-a-date"],
        )

    assert result.exit_code == 1
    assert "Invalid date" in result.output or "format" in result.output.lower()
    tx_mock.assert_not_awaited()


def test_milestones_update_no_fields_warns_and_skips_tx():
    """milestones update with no fields prints a warning and does not emit a tx."""
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=MILESTONE_DATA)),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["milestones", "update", "m1"])

    assert result.exit_code == 0, result.output
    tx_mock.assert_not_awaited()


def test_milestones_update_not_found_exits_nonzero():
    """milestones update exits with code 1 when the milestone is not found."""
    find_mock = AsyncMock(return_value=[])
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", find_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["milestones", "update", "missing-id", "--label", "X"])

    assert result.exit_code == 1
    tx_mock.assert_not_awaited()


# ── templates describe --set / --set-file ─────────────────────────────────────


def _template_doc(**overrides):
    base = {
        "_id": "tmpl-1",
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
    base.update(overrides)
    return base


def test_templates_describe_set_writes_inline_prosemirror_dict():
    """templates describe --set converts markdown to an inline ProseMirror dict via TxUpdateDoc."""
    tx_mock = AsyncMock(return_value={})
    template_doc = _template_doc(description="")

    with (
        _auth_patch(),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(return_value=[template_doc]),
        ),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["templates", "describe", "tmpl-1", "--set", "Hello world"],
        )

    assert result.exit_code == 0, result.output
    assert "Description updated" in result.output
    update_tx = tx_mock.await_args.args[0]
    assert update_tx["_class"] == "core:class:TxUpdateDoc"
    assert update_tx["objectClass"] == "tracker:class:IssueTemplate"
    assert update_tx["objectSpace"] == "p1"
    assert update_tx["objectId"] == "tmpl-1"
    # Description is stored as an inline ProseMirror dict, not a blob ref string
    description = update_tx["operations"]["description"]
    assert isinstance(description, dict)
    assert description.get("type") == "doc"


def test_templates_describe_set_aborts_on_blob_ref_heuristic():
    """templates describe --set refuses to overwrite a description that looks like a blob ref."""
    tx_mock = AsyncMock(return_value={})
    # Description contains "-description-" → blob-ref heuristic should trip
    template_doc = _template_doc(description="abc-description-xyz")

    with (
        _auth_patch(),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(return_value=[template_doc]),
        ),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["templates", "describe", "tmpl-1", "--set", "Hello world"],
        )

    assert result.exit_code == 1
    assert "blob ref" in result.output.lower() or "corruption" in result.output.lower()
    tx_mock.assert_not_awaited()


def test_templates_describe_set_file_reads_from_disk_and_writes(tmp_path):
    """templates describe --set-file reads markdown from disk and writes inline ProseMirror."""
    tx_mock = AsyncMock(return_value={})
    md_file = tmp_path / "body.md"
    md_file.write_text("# Heading\n\nBody text.", encoding="utf-8")

    template_doc = _template_doc(description="")

    with (
        _auth_patch(),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(return_value=[template_doc]),
        ),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["templates", "describe", "tmpl-1", "--set-file", str(md_file)],
        )

    assert result.exit_code == 0, result.output
    assert "Description updated" in result.output
    description = tx_mock.await_args.args[0]["operations"]["description"]
    assert isinstance(description, dict)
    assert description.get("type") == "doc"


def test_templates_describe_set_file_missing_exits_nonzero():
    """templates describe --set-file exits 1 when the source file does not exist."""
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(return_value=[_template_doc()]),
        ),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["templates", "describe", "tmpl-1", "--set-file", "/nonexistent/path.md"],
        )

    assert result.exit_code == 1
    assert "not found" in result.output.lower()
    tx_mock.assert_not_awaited()


def test_templates_describe_rejects_both_set_and_set_file():
    """Passing both --set and --set-file should error out before any IO."""
    result = runner.invoke(
        app,
        [
            "templates",
            "describe",
            "tmpl-1",
            "--set",
            "x",
            "--set-file",
            "/tmp/whatever.md",
        ],
    )
    assert result.exit_code == 1
    assert "either" in result.output.lower() or "not both" in result.output.lower()


def test_templates_describe_set_not_found_exits_nonzero():
    """templates describe --set exits with code 1 when the template is not found."""
    tx_mock = AsyncMock(return_value={})

    with (
        _auth_patch(),
        patch("huly_cli.client.HulyClient.find_all", new=AsyncMock(return_value=[])),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(
            app,
            ["templates", "describe", "missing-id", "--set", "x"],
        )

    assert result.exit_code == 1
    tx_mock.assert_not_awaited()
