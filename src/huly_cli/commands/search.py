"""Top-level ``huly search`` command — fulltext search across the workspace."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

import typer

from huly_cli.auth import ensure_auth
from huly_cli.client import HulyClient
from huly_cli.config import load_config
from huly_cli.errors import AuthError, HulyError
from huly_cli.output import is_json_mode, print_error, print_list

# ── Shared helpers ────────────────────────────────────────────────────────────


def _hit_to_row(hit: dict[str, Any]) -> dict[str, Any]:
    """Flatten a fulltext hit for the default human-readable table."""
    inner = hit.get("doc") if isinstance(hit.get("doc"), dict) else {}
    doc_id = inner.get("_id") or hit.get("id") or ""
    cls = inner.get("_class") or ""
    score = hit.get("score")
    score_str = f"{float(score):.1f}" if isinstance(score, (int, float)) else ""
    return {
        "class": cls,
        "id": str(doc_id),
        "title": hit.get("title") or "",
        "score": score_str,
    }


def _hit_to_json(hit: dict[str, Any]) -> dict[str, Any]:
    """Structured envelope for ``--json`` — id, class, score, title."""
    inner = hit.get("doc") if isinstance(hit.get("doc"), dict) else {}
    return {
        "id": inner.get("_id") or hit.get("id") or "",
        "class": inner.get("_class") or "",
        "title": hit.get("title") or "",
        "score": hit.get("score"),
    }


async def _run_search(
    ctx: typer.Context,
    query: str,
    limit: int,
    classes: list[str] | None,
) -> list[dict[str, Any]]:
    """Fetch fulltext results from the server.

    Returns the raw hit list so the caller can decide how to format.
    """
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )
    auth = await ensure_auth(config)
    async with HulyClient(config, auth) as client:
        return await client.fulltext_search(query, limit=limit, classes=classes)


def _emit(hits: list[dict[str, Any]], title: str) -> None:
    """Emit hits — JSON envelope in ``--json`` mode, otherwise a table."""
    if is_json_mode():
        payload = [_hit_to_json(hit) for hit in hits]
        print_list(payload, columns=["class", "id", "title", "score"], title=title)
        return
    rows = [_hit_to_row(hit) for hit in hits]
    print_list(rows, columns=["class", "id", "title", "score"], title=title)


# ── Command ──────────────────────────────────────────────────────────────────


def search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search query."),
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of hits to return."),
    ] = 25,
    class_filter: Annotated[
        list[str] | None,
        typer.Option(
            "--class",
            help=(
                "Filter results by fully qualified class (e.g. "
                "'tracker:class:Issue'). Repeatable. Filtered client-side."
            ),
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emit structured JSON output (id, class, title, score).",
        ),
    ] = False,
) -> None:
    """Fulltext search across the workspace.

    Returns ranked results mixing all classes (issues, documents, templates,
    etc.) by descending relevance score. Use ``--class`` to restrict to one
    or more classes — filtering happens client-side because the server's
    equivalent query parameter is unreliable.
    """
    if json_output:
        from huly_cli.output import set_json_mode

        set_json_mode(True)

    try:
        hits = asyncio.run(_run_search(ctx, query, limit, class_filter))
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    _emit(hits, title=f"Search: {query}")
