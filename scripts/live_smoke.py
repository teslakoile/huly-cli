#!/usr/bin/env python3
"""Live smoke runner for the huly CLI.

Read-only checks run by default. Pass --allow-writes to exercise CRUD flows that
create and then clean up disposable issues, documents, components, and milestones.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

ISSUE_ID_RE = re.compile(r"Issue ([A-Z0-9-]+) created")
OBJECT_ID_RE = re.compile(r"\(id: ([a-f0-9]+)\)")


@dataclass
class CreatedArtifacts:
    issue_identifier: str | None = None
    document_id: str | None = None
    component_id: str | None = None
    milestone_id: str | None = None


class SmokeFailure(RuntimeError):
    pass


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def run_json(*cli_args: str) -> dict[str, Any]:
    cmd = ["uv", "run", "huly", "--json", *cli_args]
    result = _run(cmd)
    if result.returncode != 0:
        raise SmokeFailure(
            f"Command failed: {' '.join(cmd)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SmokeFailure(
            f"Command returned non-JSON output: {' '.join(cmd)}\nstdout:\n{result.stdout}"
        ) from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def parse_created_ids(message: str) -> tuple[str | None, str | None]:
    issue_match = ISSUE_ID_RE.search(message)
    object_match = OBJECT_ID_RE.search(message)
    return (
        issue_match.group(1) if issue_match else None,
        object_match.group(1) if object_match else None,
    )


def read_only_checks(project: str) -> None:
    auth = run_json("auth", "status")
    require(
        auth["ok"] is True and auth["data"]["authenticated"] is True,
        "auth status did not report authenticated=true",
    )

    projects = run_json("projects", "list")
    require(projects["data"], "projects list returned no projects")
    project_info = run_json("projects", "get", project)
    require(project_info["data"]["identifier"] == project, f"project {project} not found")

    issues = run_json("issues", "list", "--project", project, "--limit", "5")
    require(issues["data"], f"issues list returned no issues for project {project}")
    issue_identifier = issues["data"][0]["identifier"]
    issue_get = run_json("issues", "get", issue_identifier)
    require(issue_get["data"]["identifier"] == issue_identifier, "issues get mismatch")
    issue_desc = run_json("issues", "describe", issue_identifier)
    require("description" in issue_desc, "issues describe did not return description")

    components = run_json("components", "list", "--project", project, "--limit", "5")
    require(components["data"], f"components list returned no components for project {project}")
    component_id = components["data"][0]["id"]
    component_get = run_json("components", "get", component_id)
    require(component_get["data"]["id"] == component_id, "components get mismatch")

    members = run_json("members", "list")
    require(members["data"], "members list returned no members")

    labels = run_json("labels", "list")
    require(isinstance(labels["data"], list), "labels list did not return a list")

    documents = run_json("documents", "list", "--limit", "5")
    require(documents["data"], "documents list returned no documents")
    document_id = documents["data"][0]["id"]
    document_get = run_json("documents", "get", document_id)
    require(document_get["data"]["id"] == document_id, "documents get mismatch")
    if document_get["data"].get("content_ref"):
        document_desc = run_json("documents", "describe", document_id)
        require("content" in document_desc, "documents describe did not return content")

    templates = run_json("templates", "list", "--project", project, "--limit", "5")
    require(templates["data"], f"templates list returned no templates for project {project}")
    template_id = templates["data"][0]["id"]
    template_get = run_json("templates", "get", template_id)
    require(template_get["data"]["id"] == template_id, "templates get mismatch")
    template_desc = run_json("templates", "describe", template_id)
    require("description" in template_desc, "templates describe did not return description")

    milestones = run_json("milestones", "list", "--project", project, "--limit", "5")
    if milestones["data"]:
        milestone_id = milestones["data"][0]["id"]
        milestone_get = run_json("milestones", "get", milestone_id)
        require(milestone_get["data"]["id"] == milestone_id, "milestones get mismatch")


def write_checks(project: str, teamspace: str, artifacts: CreatedArtifacts) -> None:
    suffix = str(int(time.time()))

    issue_create = run_json(
        "issues",
        "create",
        "--project",
        project,
        "--title",
        f"CODEX Smoke Issue {suffix}",
        "--priority",
        "medium",
        "--description",
        "Initial live smoke issue description.",
    )
    issue_identifier, _ = parse_created_ids(issue_create["message"])
    require(issue_identifier is not None, "failed to parse created issue identifier")
    artifacts.issue_identifier = issue_identifier
    issue_get = run_json("issues", "get", issue_identifier)
    require(issue_get["data"]["identifier"] == issue_identifier, "issue create/get mismatch")
    issue_desc = run_json("issues", "describe", issue_identifier)
    require(
        issue_desc["description"] == "Initial live smoke issue description.",
        "issue description did not round-trip",
    )
    run_json(
        "issues",
        "update",
        issue_identifier,
        "--title",
        f"CODEX Smoke Issue {suffix} updated",
        "--priority",
        "high",
        "--status",
        "done",
    )
    run_json("issues", "describe", issue_identifier, "--set", "Updated live smoke issue description.")

    document_create = run_json(
        "documents",
        "create",
        "--space",
        teamspace,
        "--title",
        f"CODEX Smoke Document {suffix}",
    )
    _, document_id = parse_created_ids(document_create["message"])
    require(document_id is not None, "failed to parse created document id")
    artifacts.document_id = document_id
    run_json("documents", "update", document_id, "--title", f"CODEX Smoke Document {suffix} updated")
    run_json("documents", "describe", document_id, "--set", "Updated live smoke document content.")
    document_desc = run_json("documents", "describe", document_id)
    require(
        document_desc["content"] == "Updated live smoke document content.",
        "document content did not round-trip",
    )

    component_create = run_json(
        "components",
        "create",
        "--project",
        project,
        "--label",
        f"CODEX Smoke Component {suffix}",
        "--description",
        "Temporary live smoke component.",
    )
    _, component_id = parse_created_ids(component_create["message"])
    require(component_id is not None, "failed to parse created component id")
    artifacts.component_id = component_id
    run_json(
        "components",
        "update",
        component_id,
        "--label",
        f"CODEX Smoke Component {suffix} updated",
        "--description",
        "Temporary live smoke component updated.",
    )
    component_get = run_json("components", "get", component_id)
    require(
        component_get["data"]["label"] == f"CODEX Smoke Component {suffix} updated",
        "component update did not round-trip",
    )

    milestone_create = run_json(
        "milestones",
        "create",
        "--project",
        project,
        "--label",
        f"CODEX Smoke Milestone {suffix}",
        "--status",
        "planned",
        "--target-date",
        "2026-05-15",
    )
    _, milestone_id = parse_created_ids(milestone_create["message"])
    require(milestone_id is not None, "failed to parse created milestone id")
    artifacts.milestone_id = milestone_id
    run_json(
        "milestones",
        "update",
        milestone_id,
        "--label",
        f"CODEX Smoke Milestone {suffix} updated",
        "--status",
        "completed",
        "--target-date",
        "2026-06-15",
    )
    milestone_get = run_json("milestones", "get", milestone_id)
    require(
        milestone_get["data"]["label"] == f"CODEX Smoke Milestone {suffix} updated",
        "milestone update did not round-trip",
    )


def cleanup_writes(artifacts: CreatedArtifacts) -> None:
    cleanup_steps = [
        ("issues", "delete", artifacts.issue_identifier),
        ("documents", "delete", artifacts.document_id),
        ("components", "delete", artifacts.component_id),
        ("milestones", "delete", artifacts.milestone_id),
    ]
    for group, action, identifier in cleanup_steps:
        if not identifier:
            continue
        result = _run(["uv", "run", "huly", "--json", group, action, identifier])
        if result.returncode != 0:
            print(
                f"WARNING: cleanup failed for {group} {identifier}\nstdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}",
                file=sys.stderr,
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="ROA", help="Project identifier for smoke tests.")
    parser.add_argument(
        "--teamspace",
        default="RoA - Staff Augmentation",
        help="Teamspace name used for document write checks.",
    )
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        help="Exercise create/update/delete flows in addition to read-only checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts = CreatedArtifacts()
    try:
        print("Running read-only smoke checks...")
        read_only_checks(args.project)
        print("Read-only smoke checks passed.")
        if args.allow_writes:
            print("Running write smoke checks...")
            write_checks(args.project, args.teamspace, artifacts)
            print("Write smoke checks passed.")
        return 0
    except SmokeFailure as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected smoke failure: {exc}", file=sys.stderr)
        return 1
    finally:
        if args.allow_writes:
            cleanup_writes(artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
