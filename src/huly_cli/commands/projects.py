"""Projects commands: list, get."""

from __future__ import annotations

import asyncio
from typing import Any

import typer

from huly_cli.client import HulyClient
from huly_cli.config import load_config
from huly_cli.errors import AuthError, HulyError, NotFoundError
from huly_cli.models import Project
from huly_cli.output import print_error, print_item, print_list

app = typer.Typer(help="Manage Huly projects.", no_args_is_help=True)


# ── Async helpers ─────────────────────────────────────────────────────────────


async def _fetch_projects(config: Any, auth: Any) -> list[Project]:
    async with HulyClient(config, auth) as client:
        raw = await client.find_all("tracker:class:Project", options={"limit": 200})
    return [Project.model_validate(doc) for doc in raw]


# ── Commands ──────────────────────────────────────────────────────────────────


@app.command("list")
def projects_list(ctx: typer.Context) -> None:
    """List all projects."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> list[Project]:
        from huly_cli.auth import ensure_auth

        auth = await ensure_auth(config)
        return await _fetch_projects(config, auth)

    try:
        projects = asyncio.run(_run())
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    rows = [
        {
            "identifier": p.identifier or p.id,
            "name": p.name,
            "members": str(len(p.members)),
            "archived": "yes" if p.archived else "no",
        }
        for p in projects
    ]
    print_list(rows, columns=["identifier", "name", "members", "archived"], title="Projects")


@app.command("get")
def projects_get(
    ctx: typer.Context,
    identifier: str = typer.Argument(..., help="Project identifier (e.g. ROA) or internal ID."),
) -> None:
    """Get details of a project."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> Project:
        from huly_cli.auth import ensure_auth

        auth = await ensure_auth(config)
        projects = await _fetch_projects(config, auth)
        # Match by identifier or internal ID
        ident_upper = identifier.upper()
        for p in projects:
            if p.identifier.upper() == ident_upper or p.id == identifier:
                return p
        raise NotFoundError(f"Project '{identifier}' not found.")

    try:
        project = asyncio.run(_run())
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    data = {
        "identifier": project.identifier,
        "name": project.name,
        "id": project.id,
        "description": project.description,
        "sequence": project.sequence,
        "members": project.members,
        "owners": project.owners,
        "default_issue_status": project.default_issue_status,
        "private": project.private,
        "archived": project.archived,
    }
    print_item(data, title=f"Project: {project.identifier or project.name}")
