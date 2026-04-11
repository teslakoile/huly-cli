"""Components commands: list, get, create, update."""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Annotated, Any

import typer

from huly_cli.auth import ensure_auth
from huly_cli.client import HulyClient
from huly_cli.config import load_config
from huly_cli.errors import AuthError, HulyError, NotFoundError
from huly_cli.models import Component
from huly_cli.output import print_error, print_item, print_list, print_success, print_warning

app = typer.Typer(help="Manage Huly components.", no_args_is_help=True)


# ── Shared helpers ────────────────────────────────────────────────────────────


async def _resolve_project_by_identifier(client: HulyClient, identifier: str) -> tuple[str, str]:
    """Return (project_id, project_name) for the given identifier."""
    projects = await client.find_all(
        "tracker:class:Project",
        query={"identifier": identifier.upper()},
        options={"limit": 1},
    )
    if not projects:
        raise NotFoundError(f"Project '{identifier}' not found.")
    proj = projects[0]
    return proj["_id"], proj.get("name", identifier)


async def _fetch_person_map(client: HulyClient) -> dict[str, str]:
    """Return map of person_id → display_name."""
    raw = await client.find_all("contact:class:Person", options={"limit": 500})
    result: dict[str, str] = {}
    for p in raw:
        name: str = p.get("name", "")
        parts = name.split(",", 1)
        display = f"{parts[1].strip()} {parts[0].strip()}" if len(parts) == 2 else name
        result[p["_id"]] = display
    return result


async def _resolve_person_by_name(client: HulyClient, name: str) -> str:
    """Fuzzy-match a person by name and return their ID."""
    persons = await client.find_all("contact:class:Person", options={"limit": 500})
    query_lower = name.lower()
    for p in persons:
        raw_name: str = p.get("name", "")
        parts = raw_name.split(",", 1)
        display = f"{parts[1].strip()} {parts[0].strip()}" if len(parts) == 2 else raw_name
        if query_lower in display.lower() or query_lower in raw_name.lower():
            return p["_id"]
    raise NotFoundError(f"Person '{name}' not found.")


def _truncate(text: str, max_len: int = 60) -> str:
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def _component_to_row(comp: Component, person_map: dict[str, str]) -> dict[str, Any]:
    lead_name = person_map.get(comp.lead, comp.lead) if comp.lead else ""
    return {
        "label": comp.label,
        "description": _truncate(comp.description),
        "lead": lead_name,
        "id": comp.id,
    }


def _component_to_detail(comp: Component, person_map: dict[str, str]) -> dict[str, Any]:
    lead_name = person_map.get(comp.lead, comp.lead) if comp.lead else ""
    return {
        "label": comp.label,
        "id": comp.id,
        "space": comp.space,
        "description": comp.description,
        "lead": lead_name,
        "lead_id": comp.lead,
        "created_by": comp.created_by,
        "modified_by": comp.modified_by,
    }


# ── Commands ──────────────────────────────────────────────────────────────────


@app.command("list")
def components_list(
    ctx: typer.Context,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Filter by project identifier (e.g. ROA)."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of components to return."),
    ] = 50,
) -> None:
    """List components, with optional project filter."""
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
                project_id, _ = await _resolve_project_by_identifier(client, project)
                query["space"] = project_id

            raw = await client.find_all(
                "tracker:class:Component",
                query=query,
                options={"limit": limit},
            )
            components = [Component.model_validate(doc) for doc in raw]
            person_map = await _fetch_person_map(client)

        return [_component_to_row(c, person_map) for c in components]

    try:
        rows = asyncio.run(_run())
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    print_list(rows, columns=["label", "description", "lead", "id"], title="Components")


@app.command("get")
def components_get(
    ctx: typer.Context,
    component_id: str = typer.Argument(..., help="Component internal ID."),
) -> None:
    """Get details of a component."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> dict[str, Any]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw = await client.find_all(
                "tracker:class:Component",
                query={"_id": component_id},
                options={"limit": 1},
            )
            if not raw:
                raise NotFoundError(f"Component '{component_id}' not found.")
            comp = Component.model_validate(raw[0])
            person_map = await _fetch_person_map(client)
        return _component_to_detail(comp, person_map)

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

    print_item(data, title=f"Component: {data.get('label', component_id)}")


@app.command("create")
def components_create(
    ctx: typer.Context,
    label: Annotated[str, typer.Option("--label", help="Component label.")] = ...,
    project: Annotated[
        str, typer.Option("--project", help='Project identifier (e.g. "ROA").')
    ] = ...,
    lead: Annotated[
        str | None, typer.Option("--lead", help="Lead person name (fuzzy match).")
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", help="Component description.")
    ] = None,
) -> None:
    """Create a new component."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> str:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            project_id, _ = await _resolve_project_by_identifier(client, project)

            lead_id: str | None = None
            if lead:
                lead_id = await _resolve_person_by_name(client, lead)

            new_id = secrets.token_hex(12)

            transaction = {
                "_class": "core:class:TxCreateDoc",
                "objectClass": "tracker:class:Component",
                "objectSpace": project_id,
                "objectId": new_id,
                "attributes": {
                    "label": label,
                    "description": description or "",
                    "lead": lead_id,
                },
                "modifiedBy": auth.account_id,
                "modifiedOn": int(time.time() * 1000),
            }

            await client.tx(transaction)
        return new_id

    try:
        new_id = asyncio.run(_run())
        print_success(f"Component created in project '{project}' (id: {new_id})")
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
def components_update(
    ctx: typer.Context,
    component_id: str = typer.Argument(..., help="Component internal ID."),
    label: Annotated[str | None, typer.Option("--label", help="New component label.")] = None,
    lead: Annotated[
        str | None, typer.Option("--lead", help='New lead person name. Use "" to unassign.')
    ] = None,
    description: Annotated[
        str | None, typer.Option("--description", help="New description.")
    ] = None,
) -> None:
    """Update an existing component."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> None:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw = await client.find_all(
                "tracker:class:Component",
                query={"_id": component_id},
                options={"limit": 1},
            )
            if not raw:
                raise NotFoundError(f"Component '{component_id}' not found.")
            comp = Component.model_validate(raw[0])

            operations: dict = {}

            if label is not None:
                operations["label"] = label

            if description is not None:
                operations["description"] = description

            if lead is not None:
                if lead == "":
                    operations["lead"] = None
                else:
                    lead_id = await _resolve_person_by_name(client, lead)
                    operations["lead"] = lead_id

            if not operations:
                print_warning(
                    "No fields to update — provide at least one of --label, --lead, --description."
                )
                return

            transaction = {
                "_class": "core:class:TxUpdateDoc",
                "objectClass": "tracker:class:Component",
                "objectSpace": comp.space,
                "objectId": comp.id,
                "operations": operations,
                "modifiedBy": auth.account_id,
                "modifiedOn": int(time.time() * 1000),
            }

            await client.tx(transaction)

    try:
        asyncio.run(_run())
        print_success(f"Component {component_id} updated.")
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
