"""Milestones commands: list, get, create, update."""

from __future__ import annotations

import asyncio
import datetime
import secrets
import time
from typing import Annotated, Any

import typer

from huly_cli.auth import ensure_auth
from huly_cli.client import HulyClient
from huly_cli.config import load_config
from huly_cli.errors import AuthError, HulyError, NotFoundError
from huly_cli.models import MILESTONE_STATUS_FROM_NAME, Milestone
from huly_cli.output import print_error, print_item, print_list, print_success, print_warning

app = typer.Typer(help="Manage Huly milestones.", no_args_is_help=True)


# ── Shared helpers ────────────────────────────────────────────────────────────


async def _resolve_project_by_identifier(client: HulyClient, identifier: str) -> str:
    """Return project_id for the given identifier."""
    projects = await client.find_all(
        "tracker:class:Project",
        query={"identifier": identifier.upper()},
        options={"limit": 1},
    )
    if not projects:
        raise NotFoundError(f"Project '{identifier}' not found.")
    return projects[0]["_id"]


def _parse_date_ms(date_str: str) -> int:
    """Parse a YYYY-MM-DD date string and return a UTC millisecond timestamp."""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=datetime.UTC)
    return int(dt.timestamp() * 1000)


def _format_date(ms: int | None) -> str:
    """Format a millisecond UTC timestamp as YYYY-MM-DD, or '' if None."""
    if ms is None:
        return ""
    dt = datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.UTC)
    return dt.strftime("%Y-%m-%d")


def _milestone_to_row(m: Milestone) -> dict[str, Any]:
    return {
        "label": m.label,
        "status": m.status_name,
        "target_date": _format_date(m.target_date),
        "id": m.id,
    }


def _milestone_to_detail(m: Milestone) -> dict[str, Any]:
    return {
        "label": m.label,
        "id": m.id,
        "space": m.space,
        "status": m.status_name,
        "status_int": m.status,
        "target_date": _format_date(m.target_date),
        "target_date_ms": m.target_date,
        "comments": m.comments,
        "created_by": m.created_by,
        "modified_by": m.modified_by,
    }


def _resolve_status(status_name: str) -> int:
    key = status_name.lower().replace(" ", "-")
    val = MILESTONE_STATUS_FROM_NAME.get(key)
    if val is None:
        valid = ", ".join(MILESTONE_STATUS_FROM_NAME.keys())
        raise HulyError(f"Unknown milestone status '{status_name}'. Valid values: {valid}")
    return val


# ── Commands ──────────────────────────────────────────────────────────────────


@app.command("list")
def milestones_list(
    ctx: typer.Context,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Filter by project identifier (e.g. DEMO)."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", "-s", help="Filter by status: planned, in-progress, completed."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of milestones to return."),
    ] = 50,
) -> None:
    """List milestones, with optional project and status filters."""
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
                status_int = _resolve_status(status)
                query["status"] = status_int

            if project:
                project_id = await _resolve_project_by_identifier(client, project)
                query["space"] = project_id

            raw = await client.find_all(
                "tracker:class:Milestone",
                query=query,
                options={"limit": limit},
            )
            milestones = [Milestone.model_validate(doc) for doc in raw]

        return [_milestone_to_row(m) for m in milestones]

    try:
        rows = asyncio.run(_run())
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    print_list(rows, columns=["label", "status", "target_date", "id"], title="Milestones")


@app.command("get")
def milestones_get(
    ctx: typer.Context,
    milestone_id: str = typer.Argument(..., help="Milestone internal ID."),
) -> None:
    """Get details of a milestone."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> dict[str, Any]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw = await client.find_all(
                "tracker:class:Milestone",
                query={"_id": milestone_id},
                options={"limit": 1},
            )
            if not raw:
                raise NotFoundError(f"Milestone '{milestone_id}' not found.")
            milestone = Milestone.model_validate(raw[0])
        return _milestone_to_detail(milestone)

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

    print_item(data, title=f"Milestone: {data.get('label', milestone_id)}")


@app.command("create")
def milestones_create(
    ctx: typer.Context,
    label: Annotated[str, typer.Option("--label", help="Milestone label.")] = ...,
    project: Annotated[
        str, typer.Option("--project", help='Project identifier (e.g. "DEMO").')
    ] = ...,
    status: Annotated[
        str, typer.Option("--status", help="Status: planned, in-progress, completed.")
    ] = "planned",
    target_date: Annotated[
        str | None, typer.Option("--target-date", help="Target date (YYYY-MM-DD).")
    ] = None,
) -> None:
    """Create a new milestone."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> str:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            project_id = await _resolve_project_by_identifier(client, project)

            status_int = _resolve_status(status)

            target_date_ms: int | None = None
            if target_date:
                try:
                    target_date_ms = _parse_date_ms(target_date)
                except ValueError:
                    raise HulyError(
                        f"Invalid date format '{target_date}'. Use YYYY-MM-DD."
                    ) from None

            new_id = secrets.token_hex(12)

            transaction = {
                "_class": "core:class:TxCreateDoc",
                "objectClass": "tracker:class:Milestone",
                "objectSpace": project_id,
                "objectId": new_id,
                "attributes": {
                    "label": label,
                    "status": status_int,
                    "targetDate": target_date_ms,
                    "comments": 0,
                },
                "modifiedBy": auth.account_id,
                "modifiedOn": int(time.time() * 1000),
            }

            await client.tx(transaction)
        return new_id

    try:
        new_id = asyncio.run(_run())
        print_success(f"Milestone created in project '{project}' (id: {new_id})")
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e


@app.command("update")
def milestones_update(
    ctx: typer.Context,
    milestone_id: str = typer.Argument(..., help="Milestone internal ID."),
    label: Annotated[str | None, typer.Option("--label", help="New milestone label.")] = None,
    status: Annotated[
        str | None, typer.Option("--status", help="New status: planned, in-progress, completed.")
    ] = None,
    target_date: Annotated[
        str | None, typer.Option("--target-date", help="New target date (YYYY-MM-DD).")
    ] = None,
) -> None:
    """Update an existing milestone."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> None:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw = await client.find_all(
                "tracker:class:Milestone",
                query={"_id": milestone_id},
                options={"limit": 1},
            )
            if not raw:
                raise NotFoundError(f"Milestone '{milestone_id}' not found.")
            milestone = Milestone.model_validate(raw[0])

            operations: dict = {}

            if label is not None:
                operations["label"] = label

            if status is not None:
                operations["status"] = _resolve_status(status)

            if target_date is not None:
                try:
                    operations["targetDate"] = _parse_date_ms(target_date)
                except ValueError:
                    raise HulyError(
                        f"Invalid date format '{target_date}'. Use YYYY-MM-DD."
                    ) from None

            if not operations:
                print_warning(
                    "No fields to update — provide at least one of --label, --status, --target-date."
                )
                return

            transaction = {
                "_class": "core:class:TxUpdateDoc",
                "objectClass": "tracker:class:Milestone",
                "objectSpace": milestone.space,
                "objectId": milestone.id,
                "operations": operations,
                "modifiedBy": auth.account_id,
                "modifiedOn": int(time.time() * 1000),
            }

            await client.tx(transaction)

    try:
        asyncio.run(_run())
        print_success(f"Milestone {milestone_id} updated.")
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e


@app.command("delete")
def milestones_delete(
    ctx: typer.Context,
    milestone_id: str = typer.Argument(..., help="Milestone internal ID."),
) -> None:
    """Delete an existing milestone."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> None:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw = await client.find_all(
                "tracker:class:Milestone",
                query={"_id": milestone_id},
                options={"limit": 1},
            )
            if not raw:
                raise NotFoundError(f"Milestone '{milestone_id}' not found.")
            milestone = Milestone.model_validate(raw[0])

            await client.tx(
                {
                    "_class": "core:class:TxRemoveDoc",
                    "objectClass": "tracker:class:Milestone",
                    "objectSpace": milestone.space,
                    "objectId": milestone.id,
                }
            )

    try:
        asyncio.run(_run())
        print_success(f"Milestone {milestone_id} deleted.")
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
