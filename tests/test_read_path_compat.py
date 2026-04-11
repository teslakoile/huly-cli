"""Compatibility tests for read-path normalization and model shapes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import respx
from typer.testing import CliRunner

from huly_cli.client import HulyClient
from huly_cli.main import app
from huly_cli.models import Document, IssueTemplate

runner = CliRunner()


async def test_find_all_normalizes_scalar_query_values_and_lookup_map(fake_config, fake_auth):
    response = {
        "value": [
            {
                "title": "Bug report",
                "$lookup": {
                    "assignee": "person-1",
                    "reviewers": ["person-1", "person-2"],
                },
            }
        ],
        "lookupMap": {
            "person-1": {"_id": "person-1", "name": "Doe,John"},
            "person-2": {"_id": "person-2", "name": "Smith,Jane"},
        },
        "total": 1,
    }
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            json=response
        )
        async with HulyClient(fake_config, fake_auth) as client:
            result = await client.find_all(
                "tracker:class:Issue",
                query={"_id": "issue-1", "identifier": "ROA-1"},
            )

    assert result[0]["_class"] == "tracker:class:Issue"
    assert result[0]["_id"] == "issue-1"
    assert result[0]["identifier"] == "ROA-1"
    assert result[0]["$lookup"]["assignee"] == {"_id": "person-1", "name": "Doe,John"}
    assert result[0]["$lookup"]["reviewers"] == [
        {"_id": "person-1", "name": "Doe,John"},
        {"_id": "person-2", "name": "Smith,Jane"},
    ]


def test_document_model_accepts_null_content():
    doc = Document.model_validate({"_id": "doc-1", "title": "Doc", "content": None})
    assert doc.content is None


def test_issue_template_model_accepts_list_labels():
    template = IssueTemplate.model_validate(
        {
            "_id": "tmpl-1",
            "title": "Template",
            "labels": [{"_id": "label-1", "title": "Bug"}],
        }
    )
    assert template.labels == [{"_id": "label-1", "title": "Bug"}]


def test_documents_get_handles_null_content_and_restored_id(fake_auth):
    captured: dict[str, object] = {}

    def capture(data: dict[str, object], title: str) -> None:
        captured["data"] = data
        captured["title"] = title

    response = {
        "value": [
            {
                "title": "Doc Zero",
                "content": None,
                "space": "space-1",
                "labels": [{"_id": "label-1", "title": "Bug"}],
                "comments": 0,
                "attachments": 0,
                "rank": "",
                "createdBy": "user-1",
                "createdOn": 1,
                "modifiedBy": "user-1",
                "modifiedOn": 2,
            }
        ],
        "total": 1,
    }

    with (
        respx.mock,
        patch("huly_cli.commands.documents.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch("huly_cli.commands.documents._fetch_teamspace_map", new=AsyncMock(return_value={})),
        patch("huly_cli.commands.documents.print_item", side_effect=capture),
    ):
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            json=response
        )
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test.example.com",
                "--workspace",
                "test-ws",
                "documents",
                "get",
                "doc-1",
            ],
        )

    assert result.exit_code == 0, result.output
    assert captured["data"]["id"] == "doc-1"
    assert captured["data"]["content_ref"] is None
    assert captured["data"]["labels"] == [{"_id": "label-1", "title": "Bug"}]


def test_templates_get_handles_list_labels_and_restored_id(fake_auth):
    captured: dict[str, object] = {}

    def capture(data: dict[str, object], title: str) -> None:
        captured["data"] = data
        captured["title"] = title

    response = {
        "value": [
            {
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
                "labels": [{"_id": "label-1", "title": "Bug"}],
                "kind": "",
                "relations": [],
                "space": "space-1",
            }
        ],
        "total": 1,
    }

    with (
        respx.mock,
        patch("huly_cli.commands.templates.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch("huly_cli.commands.templates.print_item", side_effect=capture),
    ):
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            json=response
        )
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test.example.com",
                "--workspace",
                "test-ws",
                "templates",
                "get",
                "tmpl-1",
            ],
        )

    assert result.exit_code == 0, result.output
    assert captured["data"]["id"] == "tmpl-1"
    assert captured["data"]["labels"] == [{"_id": "label-1", "title": "Bug"}]


def test_components_get_handles_filtered_find_all_response(fake_auth):
    captured: dict[str, object] = {}

    def capture(data: dict[str, object], title: str) -> None:
        captured["data"] = data
        captured["title"] = title

    response = {
        "value": [
            {
                "label": "Core",
                "description": "Core component",
                "lead": None,
                "space": "project-1",
                "createdBy": "user-1",
                "createdOn": 1,
                "modifiedBy": "user-1",
                "modifiedOn": 2,
            }
        ],
        "total": 1,
    }

    with (
        respx.mock,
        patch("huly_cli.commands.components.ensure_auth", new=AsyncMock(return_value=fake_auth)),
        patch("huly_cli.commands.components._fetch_person_map", new=AsyncMock(return_value={})),
        patch("huly_cli.commands.components.print_item", side_effect=capture),
    ):
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            json=response
        )
        result = runner.invoke(
            app,
            [
                "--url",
                "https://test.example.com",
                "--workspace",
                "test-ws",
                "components",
                "get",
                "comp-1",
            ],
        )

    assert result.exit_code == 0, result.output
    assert captured["data"]["id"] == "comp-1"
    assert captured["data"]["label"] == "Core"
