"""Labels commands: list."""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

import typer

from huly_cli.client import HulyClient
from huly_cli.config import load_config
from huly_cli.errors import AuthError, HulyError
from huly_cli.models import TagReference
from huly_cli.output import print_error, print_list

app = typer.Typer(help="Manage issue labels.", no_args_is_help=True)


@app.command("list")
def labels_list(ctx: typer.Context) -> None:
    """List available labels and how many issues use each."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> list[dict[str, Any]]:
        from huly_cli.auth import ensure_auth

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
