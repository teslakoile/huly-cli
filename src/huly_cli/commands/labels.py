"""Labels commands: list, get, create, update, delete."""

from __future__ import annotations

import asyncio
import secrets
import time
from collections import Counter
from typing import Annotated, Any

import typer

from huly_cli.auth import ensure_auth
from huly_cli.client import HulyClient
from huly_cli.config import load_config
from huly_cli.errors import AuthError, HulyError, NotFoundError
from huly_cli.models import TagReference
from huly_cli.output import print_error, print_item, print_list, print_success, print_warning

app = typer.Typer(help="Manage issue labels.", no_args_is_help=True)


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


# ── Commands ──────────────────────────────────────────────────────────────────


@app.command("list")
def labels_list(ctx: typer.Context) -> None:
    """List available labels and how many issues use each."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> list[dict[str, Any]]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw = await client.find_all("tags:class:TagReference", options={"limit": 1000})

        tags = [TagReference.model_validate(doc) for doc in raw]

        # Count how many issues reference each tag title
        counts: Counter[str] = Counter(t.title for t in tags)

        # Deduplicate by title, sorted alphabetically
        seen: set[str | None] = set()
        rows: list[dict[str, Any]] = []
        for t in sorted(tags, key=lambda x: (x.title or "").lower()):
            if t.title in seen:
                continue
            seen.add(t.title)
            rows.append(
                {
                    "title": t.title or "",
                    "count": str(counts[t.title]),
                }
            )
        return rows

    try:
        rows = asyncio.run(_run())
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    print_list(rows, columns=["title", "count"], title="Labels")


@app.command("get")
def labels_get(
    ctx: typer.Context,
    label_id: str = typer.Argument(..., help="Label internal ID."),
) -> None:
    """Get details of a label."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> dict[str, Any]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw = await client.find_all(
                "tags:class:TagReference",
                query={"_id": label_id},
                options={"limit": 1},
            )
            if not raw:
                raise NotFoundError(f"Label '{label_id}' not found.")
            tag = TagReference.model_validate(raw[0])
        return {
            "title": tag.title or "",
            "id": tag.id,
            "tag": tag.tag or "",
            "color": tag.color,
            "attached_to": tag.attached_to,
            "space": tag.space,
            "created_by": tag.created_by,
            "modified_by": tag.modified_by,
        }

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

    print_item(data, title=f"Label: {data.get('title', label_id)}")


@app.command("create")
def labels_create(
    ctx: typer.Context,
    title: Annotated[str, typer.Option("--title", help="Label title.")] = ...,
    project: Annotated[
        str, typer.Option("--project", help='Project identifier (e.g. "DEMO").')
    ] = ...,
    color: Annotated[
        int | None, typer.Option("--color", help="Label color (integer).")
    ] = None,
) -> None:
    """Create a new label."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> str:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            project_id, _ = await _resolve_project_by_identifier(client, project)

            new_id = secrets.token_hex(12)

            transaction = {
                "_class": "core:class:TxCreateDoc",
                "objectClass": "tags:class:TagReference",
                "objectSpace": project_id,
                "objectId": new_id,
                "attributes": {
                    "tag": "",
                    "title": title,
                    "color": color,
                    "attachedTo": "",
                },
                "modifiedBy": auth.account_id,
                "modifiedOn": int(time.time() * 1000),
            }

            await client.tx(transaction)
        return new_id

    try:
        new_id = asyncio.run(_run())
        print_success(f"Label created in project '{project}' (id: {new_id})")
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
def labels_update(
    ctx: typer.Context,
    label_id: str = typer.Argument(..., help="Label internal ID."),
    title: Annotated[str | None, typer.Option("--title", help="New label title.")] = None,
    color: Annotated[int | None, typer.Option("--color", help="New label color (integer).")] = None,
) -> None:
    """Update an existing label."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> None:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw = await client.find_all(
                "tags:class:TagReference",
                query={"_id": label_id},
                options={"limit": 1},
            )
            if not raw:
                raise NotFoundError(f"Label '{label_id}' not found.")
            tag = TagReference.model_validate(raw[0])

            operations: dict = {}

            if title is not None:
                operations["title"] = title

            if color is not None:
                operations["color"] = color

            if not operations:
                print_warning(
                    "No fields to update — provide at least one of --title, --color."
                )
                return

            transaction = {
                "_class": "core:class:TxUpdateDoc",
                "objectClass": "tags:class:TagReference",
                "objectSpace": tag.space,
                "objectId": tag.id,
                "operations": operations,
                "modifiedBy": auth.account_id,
                "modifiedOn": int(time.time() * 1000),
            }

            await client.tx(transaction)

    try:
        asyncio.run(_run())
        print_success(f"Label {label_id} updated.")
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
def labels_delete(
    ctx: typer.Context,
    label_id: str = typer.Argument(..., help="Label internal ID."),
) -> None:
    """Delete an existing label."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> None:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw = await client.find_all(
                "tags:class:TagReference",
                query={"_id": label_id},
                options={"limit": 1},
            )
            if not raw:
                raise NotFoundError(f"Label '{label_id}' not found.")
            tag = TagReference.model_validate(raw[0])

            await client.tx(
                {
                    "_class": "core:class:TxRemoveDoc",
                    "objectClass": "tags:class:TagReference",
                    "objectSpace": tag.space,
                    "objectId": tag.id,
                }
            )

    try:
        asyncio.run(_run())
        print_success(f"Label {label_id} deleted.")
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
