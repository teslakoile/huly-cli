"""Issues commands: list, get, create, update, describe."""

from __future__ import annotations

import asyncio
import json
import secrets
from typing import Annotated, Any

import typer

from huly_cli.auth import ensure_auth
from huly_cli.client import HulyClient
from huly_cli.config import load_config
from huly_cli.errors import AuthError, HulyError, NotFoundError
from huly_cli.issue_utils import (
    IssueStatusIndex,
    load_issue_status_index,
    next_rank,
    resolve_status_id,
    resolve_status_ids,
    status_label,
)
from huly_cli.models import PRIORITY_FROM_NAME, STATUS_IDS, Issue, Person, Project
from huly_cli.output import (
    console,
    is_json_mode,
    print_error,
    print_item,
    print_list,
    print_success,
    print_warning,
)

app = typer.Typer(help="Manage Huly issues.", no_args_is_help=True)


# ── Shared helpers ────────────────────────────────────────────────────────────


async def _fetch_person_map(client: HulyClient) -> dict[str, str]:
    """Return map of person_id → display_name."""
    raw = await client.find_all("contact:class:Person", options={"limit": 500})
    persons = [Person.model_validate(doc) for doc in raw]
    return {p.id: p.display_name for p in persons}


def _normalize_issue_doc(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce live issue documents into the local model's shape."""
    normalized = dict(raw)
    if normalized.get("description") is None:
        normalized["description"] = ""
    return normalized


def _issue_from_raw(raw: dict[str, Any]) -> Issue:
    return Issue.model_validate(_normalize_issue_doc(raw))


async def _resolve_project_by_identifier(client: HulyClient, identifier: str) -> Project:
    projects = await client.find_all(
        "tracker:class:Project",
        query={"identifier": identifier.upper()},
        options={"limit": 1},
    )
    if not projects:
        raise NotFoundError(f"Project '{identifier}' not found.")
    return Project.model_validate(projects[0])


async def _find_issue_by_identifier_or_id(client: HulyClient, identifier: str) -> Issue:
    lookup = identifier.upper()
    raw_docs = await client.find_all(
        "tracker:class:Issue",
        query={"identifier": lookup},
        options={"limit": 1},
    )
    if not raw_docs:
        raw_docs = await client.find_all(
            "tracker:class:Issue",
            query={"_id": identifier},
            options={"limit": 1},
        )
    if not raw_docs:
        raise NotFoundError(f"Issue '{identifier}' not found.")
    return _issue_from_raw(raw_docs[0])


def _format_status_label(issue: Issue, status_index: IssueStatusIndex | None = None) -> str:
    """Prefer the live status index when the built-in mapping cannot resolve a value."""
    label = issue.status_name
    if label == issue.status:
        return status_label(issue.status, status_index)
    return label


async def _resolve_person_by_name(client: HulyClient, name: str) -> str:
    """Fuzzy-match a person by name and return their ID."""
    raw = await client.find_all("contact:class:Person", options={"limit": 500})
    needle = name.lower()
    for doc in raw:
        person = Person.model_validate(doc)
        if needle in person.display_name.lower() or needle in person.name.lower():
            return person.id
    raise NotFoundError(f"Person '{name}' not found.")


def _resolve_priority_value(priority: str) -> int:
    """Resolve a priority name or numeric string to the tracker integer value."""
    try:
        return int(priority)
    except ValueError:
        priority_int = PRIORITY_FROM_NAME.get(priority.lower())
        if priority_int is None:
            valid = ", ".join(PRIORITY_FROM_NAME.keys())
            raise HulyError(f"Unknown priority '{priority}'. Valid values: {valid}") from None
        return priority_int


async def _resolve_issue_status_id(
    client: HulyClient,
    raw_status: str | None,
    *,
    preferred: str | None = None,
) -> str:
    """Resolve a status name/id to the concrete status id used by the workspace."""
    if raw_status is None:
        return preferred or STATUS_IDS["backlog"]

    status_index = await load_issue_status_index(client)
    try:
        return resolve_status_id(raw_status, status_index, preferred=preferred)
    except ValueError as exc:
        valid = ", ".join(status_index.available_labels())
        raise HulyError(f"Unknown status '{raw_status}'. Valid values: {valid}") from exc


async def _next_issue_number_and_rank(
    client: HulyClient,
    project: Project,
) -> tuple[int, str, str]:
    """Increment the project sequence and derive the new issue identifier and rank."""
    raw = await client.find_all(
        "tracker:class:Issue",
        query={"space": project.id},
        options={"limit": 1, "sort": {"rank": -1}},
    )
    last_rank = raw[0].get("rank") if raw else None

    increment_result = await client.tx(
        {
            "_class": "core:class:TxUpdateDoc",
            "objectClass": "tracker:class:Project",
            "objectSpace": "core:space:Space",
            "objectId": project.id,
            "operations": {"$inc": {"sequence": 1}},
            "retrieve": True,
        }
    )
    number = increment_result.get("object", {}).get("sequence")
    if not isinstance(number, int):
        number = project.sequence + 1

    identifier = f"{project.identifier}-{number}" if project.identifier else str(number)
    return number, identifier, next_rank(last_rank)


def _issue_to_row(
    issue: Issue,
    person_map: dict[str, str],
    status_index: IssueStatusIndex | None = None,
) -> dict[str, Any]:
    assignee_name = person_map.get(issue.assignee, issue.assignee) if issue.assignee else ""
    return {
        "identifier": issue.identifier or issue.id,
        "title": issue.title,
        "status": _format_status_label(issue, status_index),
        "priority": issue.priority_name,
        "assignee": assignee_name,
    }


def _issue_to_detail(
    issue: Issue,
    person_map: dict[str, str],
    status_index: IssueStatusIndex | None = None,
) -> dict[str, Any]:
    assignee_name = person_map.get(issue.assignee, issue.assignee) if issue.assignee else ""
    return {
        "identifier": issue.identifier or issue.id,
        "title": issue.title,
        "status": _format_status_label(issue, status_index),
        "status_id": issue.status,
        "priority": issue.priority_name,
        "assignee": assignee_name,
        "id": issue.id,
        "space": issue.space,
        "description_ref": issue.description,
        "comments": issue.comments,
        "sub_issues": issue.sub_issues,
        "estimation": issue.estimation,
        "due_date": issue.due_date,
        "created_by": issue.created_by,
        "created_on": issue.created_on,
        "modified_by": issue.modified_by,
        "modified_on": issue.modified_on,
    }


# ── Commands ──────────────────────────────────────────────────────────────────


@app.command("list")
def issues_list(
    ctx: typer.Context,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Filter by project identifier (e.g. ROA)."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option(
            "--status",
            "-s",
            help="Filter by status: backlog, todo, in-progress, done, canceled.",
        ),
    ] = None,
    assignee: Annotated[
        str | None,
        typer.Option("--assignee", "-a", help="Filter by assignee name (fuzzy match)."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of issues to return."),
    ] = 50,
) -> None:
    """List issues, with optional filters."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> list[dict[str, Any]]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            query: dict[str, Any] = {}
            status_index: IssueStatusIndex | None = None
            status_ids: list[str] = []

            if project:
                project_doc = await _resolve_project_by_identifier(client, project)
                query["space"] = project_doc.id

            if status:
                status_ids = resolve_status_ids(status, status_index)
                if not status_ids:
                    status_index = await load_issue_status_index(client)
                    status_ids = resolve_status_ids(status, status_index)
                if not status_ids:
                    valid = ", ".join(
                        status_index.available_labels() if status_index else STATUS_IDS.keys()
                    )
                    raise HulyError(f"Unknown status '{status}'. Valid values: {valid}")

            if len(status_ids) <= 1:
                if status_ids:
                    query["status"] = status_ids[0]
                raw = await client.find_all(
                    "tracker:class:Issue",
                    query=query,
                    options={"limit": limit},
                )
            else:
                raw = []
                seen: set[str] = set()
                for status_id in status_ids:
                    scoped_query = {**query, "status": status_id}
                    scoped_rows = await client.find_all(
                        "tracker:class:Issue",
                        query=scoped_query,
                        options={"limit": limit},
                    )
                    for doc in scoped_rows:
                        doc_id = doc.get("_id")
                        if not isinstance(doc_id, str) or doc_id in seen:
                            continue
                        seen.add(doc_id)
                        raw.append(doc)
                        if len(raw) >= limit:
                            break
                    if len(raw) >= limit:
                        break
            issues = [_issue_from_raw(doc) for doc in raw]

            person_map = await _fetch_person_map(client)
            if status_index is None and any(issue.status_name == issue.status for issue in issues):
                status_index = await load_issue_status_index(client)

        if assignee:
            needle = assignee.lower()
            issues = [
                i for i in issues if i.assignee and needle in person_map.get(i.assignee, "").lower()
            ]

        return [_issue_to_row(i, person_map, status_index) for i in issues]

    try:
        rows = asyncio.run(_run())
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    print_list(
        rows,
        columns=["identifier", "title", "status", "priority", "assignee"],
        title="Issues",
    )


@app.command("get")
def issues_get(
    ctx: typer.Context,
    identifier: str = typer.Argument(..., help="Issue identifier (e.g. ROA-1)."),
) -> None:
    """Get details of an issue."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> dict[str, Any]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            issue = await _find_issue_by_identifier_or_id(client, identifier)
            person_map = await _fetch_person_map(client)
            status_index = None
            if issue.status_name == issue.status:
                status_index = await load_issue_status_index(client)
        return _issue_to_detail(issue, person_map, status_index)

    try:
        data = asyncio.run(_run())
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    print_item(data, title=f"Issue: {data.get('identifier', identifier)}")


@app.command("create")
def issues_create(
    ctx: typer.Context,
    title: Annotated[str, typer.Option("--title", help="Issue title.")] = ...,
    project: Annotated[
        str, typer.Option("--project", help='Project identifier (e.g. "ROA").')
    ] = ...,
    status: Annotated[str | None, typer.Option("--status", help="Status name or id.")] = None,
    priority: Annotated[str, typer.Option("--priority", help="Priority name or number.")] = "none",
    assignee: Annotated[
        str | None, typer.Option("--assignee", help="Assignee person name (fuzzy match).")
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", help="Markdown description text.")
    ] = None,
) -> None:
    """Create a new issue."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )
    try:
        result = asyncio.run(
            _create_impl(config, title, project, status, priority, assignee, description)
        )
        print_success(result)
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1) from e


async def _create_impl(
    config,
    title: str,
    project: str,
    status: str | None,
    priority: str,
    assignee: str | None,
    description: str | None,
) -> str:
    auth = await ensure_auth(config)
    async with HulyClient(config, auth) as client:
        project_doc = await _resolve_project_by_identifier(client, project)
        status_id = await _resolve_issue_status_id(
            client,
            status,
            preferred=project_doc.default_issue_status or None,
        )
        priority_int = _resolve_priority_value(priority)
        person_id = await _resolve_person_by_name(client, assignee) if assignee else None
        new_id = secrets.token_hex(12)
        number, identifier_value, rank = await _next_issue_number_and_rank(client, project_doc)

        description_ref: str | None = None
        if description:
            from huly_cli.markup import markdown_to_prosemirror

            markup = markdown_to_prosemirror(description)
            description_ref = await client.create_description(new_id, markup)
            if not description_ref:
                raise HulyError("Failed to create issue description content via Collaborator RPC.")

        transaction = {
            "_class": "core:class:TxCreateDoc",
            "objectClass": "tracker:class:Issue",
            "objectSpace": project_doc.id,
            "objectId": new_id,
            "attributes": {
                "title": title,
                "description": description_ref,
                "status": status_id,
                "priority": priority_int,
                "assignee": person_id,
                "kind": "tracker:taskTypes:Issue",
                "component": None,
                "milestone": None,
                "number": number,
                "estimation": 0,
                "remainingTime": 0,
                "reportedTime": 0,
                "reports": 0,
                "relations": [],
                "identifier": identifier_value,
                "attachedTo": "tracker:ids:NoParent",
                "parents": [],
                "childInfo": [],
                "dueDate": None,
                "rank": rank,
                "comments": 0,
                "subIssues": 0,
                "labels": 0,
            },
        }

        await client.tx(transaction)
        return (
            f"Issue {identifier_value} created in project {project_doc.identifier} (id: {new_id})"
        )


@app.command("update")
def issues_update(
    ctx: typer.Context,
    identifier: str = typer.Argument(..., help="Issue identifier (e.g. ROA-1)."),
    title: Annotated[str | None, typer.Option("--title", help="New issue title.")] = None,
    status: Annotated[str | None, typer.Option("--status", help="New status name.")] = None,
    priority: Annotated[
        str | None, typer.Option("--priority", help="New priority name or number.")
    ] = None,
    assignee: Annotated[
        str | None,
        typer.Option(
            "--assignee", help='New assignee person name (fuzzy match). Use "" to unassign.'
        ),
    ] = None,
) -> None:
    """Update an existing issue."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )
    try:
        asyncio.run(_update_impl(config, identifier, title, status, priority, assignee))
        print_success(f"Issue {identifier} updated.")
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1) from e


async def _update_impl(
    config,
    identifier: str,
    title: str | None,
    status: str | None,
    priority: str | None,
    assignee: str | None,
) -> None:
    auth = await ensure_auth(config)
    async with HulyClient(config, auth) as client:
        issue = await _find_issue_by_identifier_or_id(client, identifier)

        operations: dict = {}

        if title is not None:
            operations["title"] = title

        if status is not None:
            operations["status"] = await _resolve_issue_status_id(client, status)

        if priority is not None:
            operations["priority"] = _resolve_priority_value(priority)

        if assignee is not None:
            if assignee == "":
                operations["assignee"] = None
            else:
                operations["assignee"] = await _resolve_person_by_name(client, assignee)

        if not operations:
            print_warning(
                "No fields to update — provide at least one of --title, --status, --priority, --assignee."
            )
            return

        transaction = {
            "_class": "core:class:TxUpdateDoc",
            "objectClass": "tracker:class:Issue",
            "objectSpace": issue.space,
            "objectId": issue.id,
            "operations": operations,
        }

        await client.tx(transaction)


@app.command("describe")
def issues_describe(
    ctx: typer.Context,
    identifier: str = typer.Argument(..., help="Issue identifier (e.g. ROA-1)."),
    raw: Annotated[
        bool,
        typer.Option("--raw", help="Show raw ProseMirror JSON instead of rendered markdown."),
    ] = False,
    set_text: Annotated[
        str | None,
        typer.Option("--set", help="Set description from markdown string."),
    ] = None,
    set_file: Annotated[
        str | None,
        typer.Option("--set-file", help="Set description from a markdown file path."),
    ] = None,
) -> None:
    """Read or update the description of an issue.

    By default, reads and displays the description. Use --set or --set-file to write.
    """
    if set_text and set_file:
        print_error("Use either --set or --set-file, not both.")
        raise typer.Exit(1)

    # ── Write path ────────────────────────────────────────────────────────
    if set_text is not None or set_file is not None:
        markdown_content = set_text
        if set_file is not None:
            import pathlib

            p = pathlib.Path(set_file)
            if not p.exists():
                print_error(f"File not found: {set_file}")
                raise typer.Exit(1)
            markdown_content = p.read_text(encoding="utf-8")

        overrides: dict = ctx.obj or {}
        config = load_config(
            url_override=overrides.get("url"),
            workspace_override=overrides.get("workspace"),
        )

        async def _write() -> str:
            from huly_cli.markup import markdown_to_prosemirror

            auth = await ensure_auth(config)
            async with HulyClient(config, auth) as client:
                markup = markdown_to_prosemirror(markdown_content or "")
                issue = await _find_issue_by_identifier_or_id(client, identifier)
                if issue.description:
                    ok = await client.set_description(issue.id, issue.description, markup)
                    if not ok:
                        raise HulyError("Failed to update description via Collaborator RPC.")
                else:
                    blob_ref = await client.create_description(issue.id, markup)
                    if not blob_ref:
                        raise HulyError(
                            "Failed to create description content via Collaborator RPC."
                        )
                    await client.tx(
                        {
                            "_class": "core:class:TxUpdateDoc",
                            "objectClass": "tracker:class:Issue",
                            "objectSpace": issue.space,
                            "objectId": issue.id,
                            "operations": {"description": blob_ref},
                        }
                    )
            return issue.identifier or identifier

        try:
            ident = asyncio.run(_write())
        except NotFoundError as e:
            print_error(e.message)
            raise typer.Exit(1) from e
        except AuthError as e:
            print_error(e.message, hint="Run 'huly auth login' to authenticate.")
            raise typer.Exit(2) from e
        except HulyError as e:
            print_error(e.message)
            raise typer.Exit(1) from e

        print_success(f"Description updated for {ident}.")
        return

    # ── Read path ─────────────────────────────────────────────────────────
    overrides = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> tuple[str, str | None]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            issue = await _find_issue_by_identifier_or_id(client, identifier)
            if not issue.description:
                return issue.identifier or identifier, None
            content = await client.get_description(issue.id, issue.description)
        return issue.identifier or identifier, content

    try:
        ident, content = asyncio.run(_run())
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    if content is None:
        print_error(f"No description available for issue '{ident}'.")
        raise typer.Exit(1)

    if is_json_mode():
        if raw:
            print(json.dumps({"ok": True, "identifier": ident, "description_raw": content}))
        else:
            from huly_cli.markup import prosemirror_to_markdown

            md = prosemirror_to_markdown(content)
            print(json.dumps({"ok": True, "identifier": ident, "description": md}))
        return

    if raw:
        try:
            parsed = json.loads(content)
            console.print_json(json.dumps(parsed, indent=2))
        except (json.JSONDecodeError, TypeError):
            console.print(content)
    else:
        from rich.markdown import Markdown
        from rich.panel import Panel

        from huly_cli.markup import prosemirror_to_markdown

        md_text = prosemirror_to_markdown(content)
        if md_text.strip():
            console.print(Panel(Markdown(md_text), title=f"Description: {ident}"))
        else:
            from huly_cli.markup import prosemirror_to_text

            plain = prosemirror_to_text(content)
            console.print(Panel(plain or "(empty description)", title=f"Description: {ident}"))
