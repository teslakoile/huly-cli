"""Regression tests for issue write-path compatibility with live Huly semantics."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from huly_cli.commands import issues as issues_cmd
from huly_cli.issue_utils import IssueStatusIndex
from huly_cli.main import app
from huly_cli.models import Issue

runner = CliRunner()


def _raw_issue(**overrides: object) -> dict[str, object]:
    issue: dict[str, object] = {
        "_id": "issue-1",
        "title": "Existing issue",
        "identifier": "DEMO-1",
        "number": 1,
        "status": "tracker:status:Backlog",
        "priority": 2,
        "assignee": None,
        "description": "",
        "kind": "tracker:taskTypes:Issue",
        "createdBy": "",
        "createdOn": 0,
        "modifiedBy": "",
        "modifiedOn": 0,
        "estimation": 0,
        "labels": 0,
        "comments": 0,
        "subIssues": 0,
        "space": "project-1",
        "dueDate": None,
    }
    issue.update(overrides)
    return issue


async def test_find_issue_by_identifier_or_id_falls_back_to_internal_id():
    client = AsyncMock()
    client.find_all = AsyncMock(
        side_effect=[[], [_raw_issue(identifier="", _id="69d30187cac655019948a821")]]
    )

    issue = await issues_cmd._find_issue_by_identifier_or_id(client, "69d30187cac655019948a821")

    assert issue.id == "69d30187cac655019948a821"
    assert client.find_all.await_args_list[1].kwargs["query"] == {"_id": "69d30187cac655019948a821"}


async def test_create_impl_increments_project_sequence_and_uses_blob_ref(fake_config, fake_auth):
    project_doc = {
        "_id": "project-1",
        "name": "My Project",
        "identifier": "DEMO",
        "sequence": 16,
        "members": [],
        "owners": [],
        "description": "",
        "defaultIssueStatus": "tracker:status:Backlog",
        "private": False,
        "archived": False,
    }
    find_all_mock = AsyncMock(
        side_effect=[
            [project_doc],
            [{"_id": "issue-16", "rank": "0|i0002f:", "space": "project-1"}],
        ]
    )
    tx_mock = AsyncMock(side_effect=[{"object": {"sequence": 17}}, {}, {}])
    create_description_mock = AsyncMock(return_value="blob-description-1")

    with (
        patch("huly_cli.commands.issues.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch("huly_cli.client.HulyClient.find_all", find_all_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
        patch("huly_cli.client.HulyClient.create_description", create_description_mock),
    ):
        message = await issues_cmd._create_impl(
            fake_config,
            title="Fix auth drift",
            project="DEMO",
            status=None,
            priority="high",
            assignee=None,
            description="# Heading",
        )

    increment_tx = tx_mock.await_args_list[0].args[0]
    create_tx = tx_mock.await_args_list[1].args[0]
    description_tx = tx_mock.await_args_list[2].args[0]

    assert increment_tx["objectClass"] == "tracker:class:Project"
    assert increment_tx["objectId"] == "project-1"
    assert increment_tx["operations"] == {"$inc": {"sequence": 1}}
    assert increment_tx["retrieve"] is True

    assert create_tx["objectClass"] == "tracker:class:Issue"
    assert create_tx["objectSpace"] == "project-1"
    assert create_tx["attributes"]["number"] == 17
    assert create_tx["attributes"]["identifier"] == "DEMO-17"
    assert create_tx["attributes"]["rank"] == "0|i0002g:"
    assert create_tx["attributes"]["description"] is None
    assert create_tx["attributes"]["status"] == "tracker:status:Backlog"
    assert create_tx["attributes"]["priority"] == 2
    assert description_tx["objectClass"] == "tracker:class:Issue"
    assert description_tx["objectId"] == create_tx["objectId"]
    assert description_tx["operations"] == {"description": "blob-description-1"}
    assert "DEMO-17" in message
    create_description_mock.assert_awaited_once()


async def test_create_impl_falls_back_to_inline_markup_when_blob_create_fails(
    fake_config, fake_auth
):
    """When create_description returns None, _create_impl writes inline ProseMirror markup."""
    project_doc = {
        "_id": "project-1",
        "name": "My Project",
        "identifier": "DEMO",
        "sequence": 16,
        "members": [],
        "owners": [],
        "description": "",
        "defaultIssueStatus": "tracker:status:Backlog",
        "private": False,
        "archived": False,
    }
    find_all_mock = AsyncMock(
        side_effect=[
            [project_doc],
            [{"_id": "issue-16", "rank": "0|i0002f:", "space": "project-1"}],
        ]
    )
    tx_mock = AsyncMock(side_effect=[{"object": {"sequence": 17}}, {}, {}])
    # create_description returns None → fallback to inline markup
    create_description_mock = AsyncMock(return_value=None)

    with (
        patch("huly_cli.commands.issues.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch("huly_cli.client.HulyClient.find_all", find_all_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
        patch("huly_cli.client.HulyClient.create_description", create_description_mock),
    ):
        message = await issues_cmd._create_impl(
            fake_config,
            title="Fix auth drift",
            project="DEMO",
            status=None,
            priority="high",
            assignee=None,
            description="# Heading",
        )

    description_tx = tx_mock.await_args_list[2].args[0]
    description_value = description_tx["operations"]["description"]
    # Fallback should write inline ProseMirror JSON, not a blob ref
    assert isinstance(description_value, str)
    assert description_value.startswith("{")
    assert "doc" in description_value  # the ProseMirror dict has a "doc" type
    assert "DEMO-17" in message
    create_description_mock.assert_awaited_once()


async def test_create_impl_skips_description_tx_when_no_description_provided(
    fake_config, fake_auth
):
    """When description is None/empty, _create_impl should only emit increment + create txs."""
    project_doc = {
        "_id": "project-1",
        "name": "My Project",
        "identifier": "DEMO",
        "sequence": 16,
        "members": [],
        "owners": [],
        "description": "",
        "defaultIssueStatus": "tracker:status:Backlog",
        "private": False,
        "archived": False,
    }
    find_all_mock = AsyncMock(
        side_effect=[
            [project_doc],
            [{"_id": "issue-16", "rank": "0|i0002f:", "space": "project-1"}],
        ]
    )
    tx_mock = AsyncMock(side_effect=[{"object": {"sequence": 17}}, {}])
    create_description_mock = AsyncMock(return_value="blob-description-x")

    with (
        patch("huly_cli.commands.issues.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch("huly_cli.client.HulyClient.find_all", find_all_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
        patch("huly_cli.client.HulyClient.create_description", create_description_mock),
    ):
        await issues_cmd._create_impl(
            fake_config,
            title="No description",
            project="DEMO",
            status=None,
            priority="medium",
            assignee=None,
            description=None,
        )

    # Only two tx calls: increment, then create (no description tx)
    assert tx_mock.await_count == 2
    create_description_mock.assert_not_awaited()


async def test_update_impl_resolves_custom_status_and_unassigns(fake_config, fake_auth):
    issue = Issue.model_validate(_raw_issue(space="project-1"))
    tx_mock = AsyncMock(return_value={})

    with (
        patch("huly_cli.commands.issues.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch(
            "huly_cli.commands.issues._find_issue_by_identifier_or_id",
            new=AsyncMock(return_value=issue),
        ),
        patch(
            "huly_cli.commands.issues._resolve_issue_status_id",
            new=AsyncMock(return_value="69d4da9e2afab311abc0e8f7"),
        ),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        await issues_cmd._update_impl(
            fake_config,
            identifier="DEMO-1",
            title="Updated title",
            status="UAT",
            priority="high",
            assignee="",
        )

    update_tx = tx_mock.await_args.args[0]
    assert update_tx["objectClass"] == "tracker:class:Issue"
    assert update_tx["objectSpace"] == "project-1"
    assert update_tx["objectId"] == "issue-1"
    assert update_tx["operations"] == {
        "title": "Updated title",
        "status": "69d4da9e2afab311abc0e8f7",
        "priority": 2,
        "assignee": None,
    }


def test_issues_describe_set_creates_blob_ref_when_missing(fake_auth):
    tx_mock = AsyncMock(return_value={})
    create_description_mock = AsyncMock(return_value="blob-description-2")

    with (
        patch("huly_cli.commands.issues.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(return_value=[_raw_issue(description=None)]),
        ),
        patch("huly_cli.client.HulyClient.create_description", create_description_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["issues", "describe", "DEMO-1", "--set", "hello world"])

    assert result.exit_code == 0, result.output
    assert "Description updated for DEMO-1." in result.output
    assert tx_mock.await_args.args[0]["operations"] == {"description": "blob-description-2"}


def test_issues_describe_set_falls_back_to_inline_markup_when_blob_create_fails(fake_auth):
    tx_mock = AsyncMock(return_value={})
    create_description_mock = AsyncMock(return_value=None)

    with (
        patch("huly_cli.commands.issues.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(return_value=[_raw_issue(description=None)]),
        ),
        patch("huly_cli.client.HulyClient.create_description", create_description_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["issues", "describe", "DEMO-1", "--set", "hello world"])

    assert result.exit_code == 0, result.output
    assert "Description updated for DEMO-1." in result.output
    description_value = tx_mock.await_args.args[0]["operations"]["description"]
    assert isinstance(description_value, str)
    assert description_value.startswith("{")


def test_documents_describe_set_creates_blob_ref_when_missing(fake_auth):
    tx_mock = AsyncMock(return_value={})
    create_content_mock = AsyncMock(return_value="blob-content-2")

    with (
        patch("huly_cli.commands.documents.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(
                return_value=[
                    {
                        "_id": "doc-1",
                        "title": "My Doc",
                        "content": None,
                        "space": "space-1",
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
            ),
        ),
        patch("huly_cli.client.HulyClient.create_content", create_content_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["documents", "describe", "doc-1", "--set", "hello world"])

    assert result.exit_code == 0, result.output
    assert "Content updated for 'My Doc'." in result.output
    create_content_mock.assert_awaited_once()
    assert tx_mock.await_args.args[0]["operations"] == {"content": "blob-content-2"}


def test_documents_describe_set_falls_back_to_inline_markup_when_blob_create_fails(fake_auth):
    tx_mock = AsyncMock(return_value={})
    create_content_mock = AsyncMock(return_value=None)

    with (
        patch("huly_cli.commands.documents.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(
                return_value=[
                    {
                        "_id": "doc-1",
                        "title": "My Doc",
                        "content": None,
                        "space": "space-1",
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
            ),
        ),
        patch("huly_cli.client.HulyClient.create_content", create_content_mock),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["documents", "describe", "doc-1", "--set", "hello world"])

    assert result.exit_code == 0, result.output
    assert "Content updated for 'My Doc'." in result.output
    content_value = tx_mock.await_args.args[0]["operations"]["content"]
    assert isinstance(content_value, str)
    assert content_value.startswith("{")


def test_issues_describe_reads_inline_markup_without_collaborator(fake_auth):
    inline_markup = (
        '{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"hello"}]}]}'
    )
    with (
        patch("huly_cli.commands.issues.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(return_value=[_raw_issue(description=inline_markup)]),
        ),
    ):
        result = runner.invoke(app, ["--json", "issues", "describe", "DEMO-1"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["description"] == "hello"


def test_documents_describe_reads_inline_markup_without_collaborator(fake_auth):
    inline_markup = (
        '{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"hello"}]}]}'
    )

    with (
        patch("huly_cli.commands.documents.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(
                return_value=[
                    {
                        "_id": "doc-1",
                        "title": "My Doc",
                        "content": inline_markup,
                        "space": "space-1",
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
            ),
        ),
    ):
        result = runner.invoke(app, ["--json", "documents", "describe", "doc-1"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["content"] == "hello"


def test_issues_delete_removes_issue(fake_auth):
    tx_mock = AsyncMock(return_value={})
    issue = Issue.model_validate(_raw_issue(space="project-1"))

    with (
        patch("huly_cli.commands.issues.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch(
            "huly_cli.commands.issues._find_issue_by_identifier_or_id",
            new=AsyncMock(return_value=issue),
        ),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["issues", "delete", "DEMO-1"])

    assert result.exit_code == 0, result.output
    assert "Issue DEMO-1 deleted." in result.output
    assert tx_mock.await_args.args[0] == {
        "_class": "core:class:TxRemoveDoc",
        "objectClass": "tracker:class:Issue",
        "objectSpace": "project-1",
        "objectId": "issue-1",
    }


def test_documents_delete_removes_document(fake_auth):
    tx_mock = AsyncMock(return_value={})

    with (
        patch("huly_cli.commands.documents.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(
                return_value=[
                    {
                        "_id": "doc-1",
                        "title": "My Doc",
                        "content": "blob-ref-1",
                        "space": "space-1",
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
            ),
        ),
        patch("huly_cli.client.HulyClient.tx", tx_mock),
    ):
        result = runner.invoke(app, ["documents", "delete", "doc-1"])

    assert result.exit_code == 0, result.output
    assert "Document doc-1 deleted." in result.output
    assert tx_mock.await_args.args[0] == {
        "_class": "core:class:TxRemoveDoc",
        "objectClass": "document:class:Document",
        "objectSpace": "space-1",
        "objectId": "doc-1",
    }


def test_issues_get_formats_workspace_specific_status(fake_auth):
    captured: dict[str, object] = {}

    def capture(data: dict[str, object], title: str) -> None:
        captured["data"] = data
        captured["title"] = title

    with (
        patch("huly_cli.commands.issues.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch(
            "huly_cli.client.HulyClient.find_all",
            new=AsyncMock(
                side_effect=[
                    [_raw_issue(status="69d4da9e2afab311abc0e8f7")],
                    [],
                    [{"_id": "cat-1", "defaultStatusName": "UAT"}],
                    [{"_id": "69d4da9e2afab311abc0e8f7", "name": "UAT", "category": "cat-1"}],
                ]
            ),
        ),
        patch("huly_cli.commands.issues.print_item", side_effect=capture),
    ):
        result = runner.invoke(app, ["issues", "get", "DEMO-1"])

    assert result.exit_code == 0, result.output
    assert captured["data"]["status"] == "uat"
    assert captured["data"]["status_id"] == "69d4da9e2afab311abc0e8f7"


def test_issues_list_fans_out_multi_status_queries(fake_auth):
    captured: dict[str, object] = {}
    find_all_mock = AsyncMock(
        side_effect=[
            [_raw_issue(_id="issue-1", identifier="DEMO-1", status="status-1")],
            [_raw_issue(_id="issue-2", identifier="DEMO-2", status="status-2")],
            [],
        ]
    )
    status_index = IssueStatusIndex(
        labels_by_id={"status-1": "ready", "status-2": "ready"},
        by_id={"status-1": {"name": "Ready"}, "status-2": {"name": "Ready"}},
    )

    def capture(items: list[dict[str, object]], columns: list[str], title: str) -> None:
        captured["items"] = items
        captured["columns"] = columns
        captured["title"] = title

    with (
        patch("huly_cli.commands.issues.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch(
            "huly_cli.commands.issues.load_issue_status_index",
            new=AsyncMock(return_value=status_index),
        ),
        patch(
            "huly_cli.commands.issues.resolve_status_ids",
            side_effect=[[], ["status-1", "status-2"]],
        ),
        patch("huly_cli.client.HulyClient.find_all", find_all_mock),
        patch("huly_cli.commands.issues.print_list", side_effect=capture),
    ):
        result = runner.invoke(app, ["issues", "list", "--status", "ready", "--limit", "10"])

    assert result.exit_code == 0, result.output
    assert find_all_mock.await_args_list[0].kwargs["query"] == {"status": "status-1"}
    assert find_all_mock.await_args_list[1].kwargs["query"] == {"status": "status-2"}
    assert [item["identifier"] for item in captured["items"]] == ["DEMO-1", "DEMO-2"]
    assert [item["status"] for item in captured["items"]] == ["ready", "ready"]
