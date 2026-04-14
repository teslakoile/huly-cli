"""Templates commands: list, get, describe."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any

import typer

from huly_cli.auth import ensure_auth
from huly_cli.client import HulyClient
from huly_cli.config import load_config
from huly_cli.errors import AuthError, HulyError, NotFoundError
from huly_cli.models import IssueTemplate
from huly_cli.output import (
    console,
    is_json_mode,
    print_error,
    print_item,
    print_list,
    print_success,
    print_warning,
)

app = typer.Typer(help="Manage Huly issue templates.", no_args_is_help=True)


# ── Shared helpers ────────────────────────────────────────────────────────────


def _template_to_row(t: IssueTemplate) -> dict[str, Any]:
    return {
        "title": t.title,
        "priority": t.priority_name,
        "kind": t.kind,
        "id": t.id,
    }


def _template_to_detail(t: IssueTemplate) -> dict[str, Any]:
    return {
        "title": t.title,
        "id": t.id,
        "space": t.space,
        "priority": t.priority_name,
        "priority_int": t.priority,
        "kind": t.kind,
        "assignee": t.assignee,
        "component": t.component,
        "milestone": t.milestone,
        "estimation": t.estimation,
        "comments": t.comments,
        "attachments": t.attachments,
        "labels": t.labels,
        "children": len(t.children),
        "relations": len(t.relations),
    }


# ── Commands ──────────────────────────────────────────────────────────────────


@app.command("list")
def templates_list(
    ctx: typer.Context,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Filter by project identifier (e.g. DEMO)."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of templates to return."),
    ] = 50,
) -> None:
    """List issue templates, with optional project filter."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> list[dict[str, Any]]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            query: dict[str, Any] = {}
            if project:
                projects = await client.find_all(
                    "tracker:class:Project",
                    query={"identifier": project.upper()},
                    options={"limit": 1},
                )
                if not projects:
                    raise NotFoundError(f"Project '{project}' not found.")
                query["space"] = projects[0]["_id"]

            raw = await client.find_all(
                "tracker:class:IssueTemplate",
                query=query,
                options={"limit": limit},
            )
            templates = [IssueTemplate.model_validate(doc) for doc in raw]

        return [_template_to_row(t) for t in templates]

    try:
        rows = asyncio.run(_run())
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    print_list(rows, columns=["title", "priority", "kind", "id"], title="Issue Templates")


@app.command("get")
def templates_get(
    ctx: typer.Context,
    template_id: str = typer.Argument(..., help="Template internal ID."),
) -> None:
    """Get details of an issue template."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> dict[str, Any]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw = await client.find_all(
                "tracker:class:IssueTemplate",
                query={"_id": template_id},
                options={"limit": 1},
            )
            if not raw:
                raise NotFoundError(f"Template '{template_id}' not found.")
            template = IssueTemplate.model_validate(raw[0])
        return _template_to_detail(template)

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

    print_item(data, title=f"Template: {data.get('title', template_id)}")


@app.command("describe")
def templates_describe(
    ctx: typer.Context,
    template_id: str = typer.Argument(..., help="Template internal ID."),
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
    """Read or update the description of an issue template.

    Template descriptions are stored as inline ProseMirror JSON (not a blob ref).
    By default, reads and displays the description. Use --set or --set-file to write.
    """
    if set_text is not None and set_file is not None:
        print_error("Use either --set or --set-file, not both.")
        raise typer.Exit(1)

    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

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

        async def _write() -> str:
            import time as time_mod

            from huly_cli.markup import markdown_to_prosemirror

            auth = await ensure_auth(config)
            async with HulyClient(config, auth) as client:
                raw_docs = await client.find_all(
                    "tracker:class:IssueTemplate",
                    query={"_id": template_id},
                    options={"limit": 1},
                )
                if not raw_docs:
                    raise NotFoundError(f"Template '{template_id}' not found.")
                template = IssueTemplate.model_validate(raw_docs[0])

                # Safety: detect if description looks like a blob ref string
                if (
                    isinstance(template.description, str)
                    and "-description-" in template.description
                ):
                    raise HulyError(
                        f"Template '{template_id}' description looks like a blob ref "
                        f"(contains '-description-'). Aborting to avoid corruption."
                    )

                markup_json_str = markdown_to_prosemirror(markdown_content or "")
                description_dict = json.loads(markup_json_str)

                transaction = {
                    "_class": "core:class:TxUpdateDoc",
                    "objectClass": "tracker:class:IssueTemplate",
                    "objectSpace": template.space,
                    "objectId": template.id,
                    "operations": {"description": description_dict},
                    "modifiedBy": auth.account_id,
                    "modifiedOn": int(time_mod.time() * 1000),
                }
                await client.tx(transaction)
            return template.title or template_id

        try:
            title_label = asyncio.run(_write())
        except NotFoundError as e:
            print_error(e.message)
            raise typer.Exit(1) from e
        except AuthError as e:
            print_error(e.message, hint="Run 'huly auth login' to authenticate.")
            raise typer.Exit(2) from e
        except HulyError as e:
            print_error(e.message)
            raise typer.Exit(1) from e

        print_success(f"Description updated for '{title_label}'.")
        return

    # ── Read path ─────────────────────────────────────────────────────────
    async def _run() -> tuple[str, Any]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw_docs = await client.find_all(
                "tracker:class:IssueTemplate",
                query={"_id": template_id},
                options={"limit": 1},
            )
            if not raw_docs:
                raise NotFoundError(f"Template '{template_id}' not found.")
            template = IssueTemplate.model_validate(raw_docs[0])
        return template.title or template_id, template.description

    try:
        title_label, description = asyncio.run(_run())
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    if not description:
        print_error(f"No description available for template '{title_label}'.")
        raise typer.Exit(1)

    # Safety: detect blob ref string
    if isinstance(description, str) and "-description-" in description:
        print_warning(
            f"Template '{title_label}' description looks like a blob ref — "
            "this template may use a non-standard storage format."
        )

    # Normalise: description may be a dict (from API) or a string
    if isinstance(description, dict):
        raw_json_str = json.dumps(description)
    else:
        raw_json_str = str(description)

    if is_json_mode():
        if raw:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "id": template_id,
                        "description_raw": json.loads(raw_json_str)
                        if isinstance(description, dict)
                        else raw_json_str,
                    }
                )
            )
        else:
            from huly_cli.markup import prosemirror_to_markdown

            md = prosemirror_to_markdown(raw_json_str)
            print(json.dumps({"ok": True, "id": template_id, "description": md}))
        return

    if raw:
        try:
            parsed = json.loads(raw_json_str)
            console.print_json(json.dumps(parsed, indent=2))
        except (json.JSONDecodeError, TypeError):
            console.print(raw_json_str)
    else:
        from rich.markdown import Markdown
        from rich.panel import Panel

        from huly_cli.markup import prosemirror_to_markdown

        md_text = prosemirror_to_markdown(raw_json_str)
        if md_text.strip():
            console.print(Panel(Markdown(md_text), title=f"Description: {title_label}"))
        else:
            from huly_cli.markup import prosemirror_to_text

            plain = prosemirror_to_text(raw_json_str)
            console.print(
                Panel(plain or "(empty description)", title=f"Description: {title_label}")
            )
