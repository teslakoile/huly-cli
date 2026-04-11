"""Issues commands: list, get, create, update, describe."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from typing import Annotated, Any

import typer

from huly_cli.auth import ensure_auth
from huly_cli.client import HulyClient
from huly_cli.config import load_config
from huly_cli.errors import AuthError, HulyError, NotFoundError
from huly_cli.models import (
    PRIORITY_FROM_NAME,
    STATUS_IDS,
    Issue,
    Person,
)
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


def _resolve_status_filter(status_name: str) -> str | None:
    key = status_name.lower().replace(" ", "-")
    return STATUS_IDS.get(key)


def _issue_to_row(issue: Issue, person_map: dict[str, str]) -> dict[str, Any]:
    assignee_name = person_map.get(issue.assignee, issue.assignee) if issue.assignee else ""
    return {
        "identifier": issue.identifier or issue.id,
        "title": issue.title,
        "status": issue.status_name,
        "priority": issue.priority_name,
        "assignee": assignee_name,
    }


def _issue_to_detail(issue: Issue, person_map: dict[str, str]) -> dict[str, Any]:
    assignee_name = person_map.get(issue.assignee, issue.assignee) if issue.assignee else ""
    return {
        "identifier": issue.identifier or issue.id,
        "title": issue.title,
        "status": issue.status_name,
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
            if status:
                status_id = _resolve_status_filter(status)
                if not status_id:
                    valid = ", ".join(STATUS_IDS.keys())
                    raise HulyError(f"Unknown status '{status}'. Valid values: {valid}")
                query["status"] = status_id

            raw = await client.find_all(
                "tracker:class:Issue",
                query=query,
                options={"limit": limit},
            )
            issues = [Issue.model_validate(doc) for doc in raw]

            if project:
                prefix = project.upper() + "-"
                issues = [i for i in issues if i.identifier.upper().startswith(prefix)]

            person_map = await _fetch_person_map(client)

        if assignee:
            needle = assignee.lower()
            issues = [
                i for i in issues if i.assignee and needle in person_map.get(i.assignee, "").lower()
            ]

        return [_issue_to_row(i, person_map) for i in issues]

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
            raw = await client.find_all(
                "tracker:class:Issue",
                query={"identifier": identifier.upper()},
                options={"limit": 1},
            )
            if not raw:
                raise NotFoundError(f"Issue '{identifier}' not found.")
            issue = Issue.model_validate(raw[0])
            person_map = await _fetch_person_map(client)
        return _issue_to_detail(issue, person_map)

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
    status: Annotated[str, typer.Option("--status", help="Status name.")] = "backlog",
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
    status: str,
    priority: str,
    assignee: str | None,
    description: str | None,
) -> str:
    auth = await ensure_auth(config)
    async with HulyClient(config, auth) as client:
        # Resolve project by identifier (normalise to uppercase, e.g. "roa" → "ROA")
        projects = await client.find_all("tracker:class:Project", {"identifier": project.upper()})
        if not projects:
            raise NotFoundError(f"Project '{project}' not found.")
        proj = projects[0]
        project_id: str = proj["_id"]

        # Resolve status
        status_key = status.lower().replace(" ", "-")
        status_id = STATUS_IDS.get(status_key)
        if status_id is None:
            raise NotFoundError(
                f"Unknown status '{status}'. Valid values: {', '.join(STATUS_IDS.keys())}"
            )

        # Resolve priority
        try:
            priority_int = int(priority)
        except ValueError:
            priority_int = PRIORITY_FROM_NAME.get(priority.lower())
            if priority_int is None:
                raise NotFoundError(
                    f"Unknown priority '{priority}'. Valid values: {', '.join(PRIORITY_FROM_NAME.keys())}"
                ) from None

        # Resolve assignee
        person_id: str | None = None
        if assignee:
            persons = await client.find_all("contact:class:Person")
            query_lower = assignee.lower()
            match = None
            for p in persons:
                name: str = p.get("name", "")
                # Build display name for matching: "LastName,FirstName" -> "FirstName LastName"
                parts = name.split(",", 1)
                display = f"{parts[1].strip()} {parts[0].strip()}" if len(parts) == 2 else name
                if query_lower in display.lower() or query_lower in name.lower():
                    match = p
                    break
            if match is None:
                raise NotFoundError(f"Person '{assignee}' not found.")
            person_id = match["_id"]

        # Generate new issue ID
        new_id = secrets.token_hex(12)

        transaction = {
            "_class": "core:class:TxCreateDoc",
            "objectClass": "tracker:class:Issue",
            "objectSpace": project_id,
            "objectId": new_id,
            "attributes": {
                "title": title,
                "description": "",
                "status": status_id,
                "priority": priority_int,
                "assignee": person_id,
                "kind": "tracker:taskTypes:Issue",
                "component": None,
                "milestone": None,
                "number": 0,
                "estimation": 0,
                "remainingTime": 0,
                "reportedTime": 0,
                "reports": 0,
                "relations": [],
                "parents": [],
                "childInfo": [],
                "dueDate": None,
                "rank": "",
                "comments": 0,
                "subIssues": 0,
                "labels": 0,
                "attachedTo": "tracker:ids:NoParent",
                "attachedToClass": "tracker:class:Issue",
                "collection": "subIssues",
            },
            "modifiedBy": auth.account_id,
            "modifiedOn": int(time.time() * 1000),
        }

        await client.tx(transaction)

        # Set description if provided (requires issue to exist first so it has a blob ref)
        if description:
            # Re-fetch the created issue to get its blob ref
            created = await client.find_all(
                "tracker:class:Issue", {"_id": new_id}, options={"limit": 1}
            )
            if created and created[0].get("description"):
                from huly_cli.markup import markdown_to_prosemirror

                markup = markdown_to_prosemirror(description)
                ok = await client.set_description(new_id, created[0]["description"], markup)
                if not ok:
                    print_warning("Issue created but description could not be set.")

        return f"Issue created in project {project} (id: {new_id})"


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
        # Find existing issue by identifier (normalise to uppercase, e.g. "roa-1" → "ROA-1")
        issues = await client.find_all("tracker:class:Issue", {"identifier": identifier.upper()})
        if not issues:
            raise NotFoundError(f"Issue '{identifier}' not found.")
        issue = issues[0]
        issue_id: str = issue["_id"]
        issue_space: str = issue.get("space", "")

        operations: dict = {}

        if title is not None:
            operations["title"] = title

        if status is not None:
            status_key = status.lower().replace(" ", "-")
            status_id = STATUS_IDS.get(status_key)
            if status_id is None:
                raise NotFoundError(
                    f"Unknown status '{status}'. Valid values: {', '.join(STATUS_IDS.keys())}"
                )
            operations["status"] = status_id

        if priority is not None:
            try:
                priority_int = int(priority)
            except ValueError:
                priority_int = PRIORITY_FROM_NAME.get(priority.lower())
                if priority_int is None:
                    raise NotFoundError(
                        f"Unknown priority '{priority}'. Valid values: {', '.join(PRIORITY_FROM_NAME.keys())}"
                    ) from None
            operations["priority"] = priority_int

        if assignee is not None:
            if assignee == "":
                # Unassign
                operations["assignee"] = None
            else:
                persons = await client.find_all("contact:class:Person")
                query_lower = assignee.lower()
                match = None
                for p in persons:
                    name: str = p.get("name", "")
                    parts = name.split(",", 1)
                    display = f"{parts[1].strip()} {parts[0].strip()}" if len(parts) == 2 else name
                    if query_lower in display.lower() or query_lower in name.lower():
                        match = p
                        break
                if match is None:
                    raise NotFoundError(f"Person '{assignee}' not found.")
                operations["assignee"] = match["_id"]

        if not operations:
            print_warning(
                "No fields to update — provide at least one of --title, --status, --priority, --assignee."
            )
            return

        transaction = {
            "_class": "core:class:TxUpdateDoc",
            "objectClass": "tracker:class:Issue",
            "objectSpace": issue_space,
            "objectId": issue_id,
            "operations": operations,
            "modifiedBy": auth.account_id,
            "modifiedOn": int(time.time() * 1000),
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
                raw_docs = await client.find_all(
                    "tracker:class:Issue",
                    query={"identifier": identifier.upper()},
                    options={"limit": 1},
                )
                if not raw_docs:
                    raise NotFoundError(f"Issue '{identifier}' not found.")
                issue = Issue.model_validate(raw_docs[0])
                if not issue.description:
                    raise HulyError(
                        f"Issue '{identifier}' has no description blob ref. "
                        "Cannot update a description that was never created."
                    )
                markup = markdown_to_prosemirror(markdown_content or "")
                ok = await client.set_description(issue.id, issue.description, markup)
                if not ok:
                    raise HulyError("Failed to update description via Collaborator RPC.")
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
            raw_docs = await client.find_all(
                "tracker:class:Issue",
                query={"identifier": identifier.upper()},
                options={"limit": 1},
            )
            if not raw_docs:
                raise NotFoundError(f"Issue '{identifier}' not found.")
            issue = Issue.model_validate(raw_docs[0])
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
