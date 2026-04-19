"""Documents commands: list, get, create, update, describe."""

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
from huly_cli.models import Document
from huly_cli.output import (
    console,
    is_json_mode,
    print_error,
    print_item,
    print_list,
    print_success,
    print_warning,
)

app = typer.Typer(help="Manage Huly documents.", no_args_is_help=True)


# ── Shared helpers ────────────────────────────────────────────────────────────


async def _fetch_teamspace_map(client: HulyClient) -> dict[str, str]:
    """Return map of teamspace_id → name."""
    raw = await client.find_all("document:class:Teamspace", options={"limit": 200})
    return {ts["_id"]: ts.get("name", ts["_id"]) for ts in raw}


async def _resolve_teamspace_by_name(client: HulyClient, name: str) -> str:
    """Resolve a teamspace name to its ID. Raises NotFoundError if not found."""
    raw = await client.find_all("document:class:Teamspace", options={"limit": 200})
    name_lower = name.lower()
    for ts in raw:
        if ts.get("name", "").lower() == name_lower:
            return ts["_id"]
    raise NotFoundError(f"Teamspace '{name}' not found.")


def _doc_to_row(doc: Document, space_map: dict[str, str]) -> dict[str, Any]:
    space_name = space_map.get(doc.space, doc.space)
    parent = "" if doc.parent in ("document:ids:NoParent", "") else doc.parent
    return {
        "title": doc.title,
        "space": space_name,
        "parent": parent,
        "id": doc.id,
    }


def _doc_to_detail(doc: Document, space_map: dict[str, str]) -> dict[str, Any]:
    space_name = space_map.get(doc.space, doc.space)
    parent = "" if doc.parent in ("document:ids:NoParent", "") else doc.parent
    return {
        "title": doc.title,
        "id": doc.id,
        "space": space_name,
        "space_id": doc.space,
        "parent": parent,
        "content_ref": doc.content,
        "attachments": doc.attachments,
        "labels": doc.labels,
        "comments": doc.comments,
        "rank": doc.rank,
        "created_by": doc.created_by,
        "created_on": doc.created_on,
        "modified_by": doc.modified_by,
        "modified_on": doc.modified_on,
    }


def _is_inline_markup(value: str | None) -> bool:
    return isinstance(value, str) and value.lstrip().startswith("{")


async def _find_document_by_id(client: HulyClient, doc_id: str) -> Document:
    raw = await client.find_all(
        "document:class:Document",
        query={"_id": doc_id},
        options={"limit": 1},
    )
    if not raw:
        raise NotFoundError(f"Document '{doc_id}' not found.")
    return Document.model_validate(raw[0])


async def _resolve_document_by_title(client: HulyClient, title: str) -> Document:
    """Resolve a document by case-insensitive exact title match.

    Raises NotFoundError if no match, or HulyError with a formatted match table
    if multiple documents share the same title.
    """
    raw = await client.find_all(
        "document:class:Document",
        options={"limit": 500},
    )
    title_lower = title.lower()
    matches = [d for d in raw if (d.get("title") or "").lower() == title_lower]
    if not matches:
        raise NotFoundError(f"No document matched title '{title}'.")
    if len(matches) > 1:
        rows = "\n".join(f"  - {d.get('title', '')}  (id: {d['_id']})" for d in matches)
        raise HulyError(
            f"Multiple documents matched title '{title}':\n{rows}\n"
            "Pass the document ID directly to disambiguate."
        )
    return Document.model_validate(matches[0])


# ── Commands ──────────────────────────────────────────────────────────────────


@app.command("list")
def docs_list(
    ctx: typer.Context,
    space: Annotated[
        str | None,
        typer.Option("--space", "-s", help="Filter by teamspace name."),
    ] = None,
    title_contains: Annotated[
        str | None,
        typer.Option(
            "--title-contains",
            help=(
                "Case-insensitive substring match on title. Applied client-side "
                "after fetching --limit records; bump -n for larger workspaces."
            ),
        ),
    ] = None,
    parent: Annotated[
        str | None,
        typer.Option("--parent", help="List only direct children of this document ID."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of documents to return."),
    ] = 50,
) -> None:
    """List documents, with optional teamspace / parent / title filters."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> list[dict[str, Any]]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            space_map = await _fetch_teamspace_map(client)

            query: dict[str, Any] = {}
            if space:
                space_id = await _resolve_teamspace_by_name(client, space)
                query["space"] = space_id
            if parent:
                query["parent"] = parent

            raw = await client.find_all(
                "document:class:Document",
                query=query,
                options={"limit": limit},
            )
            docs = [Document.model_validate(doc) for doc in raw]

            if title_contains:
                needle = title_contains.lower()
                docs = [d for d in docs if needle in (d.title or "").lower()]

        return [_doc_to_row(d, space_map) for d in docs]

    try:
        rows = asyncio.run(_run())
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    print_list(rows, columns=["title", "space", "parent", "id"], title="Documents")


@app.command("get")
def docs_get(
    ctx: typer.Context,
    doc_id: str | None = typer.Argument(
        None,
        help="Document internal ID (omit when using --title).",
    ),
    title: Annotated[
        str | None,
        typer.Option(
            "--title",
            help="Resolve by case-insensitive exact title match instead of ID.",
        ),
    ] = None,
) -> None:
    """Get details of a document by ID or by --title."""
    if (doc_id is None) == (title is None):
        print_error("Provide either DOC_ID or --title, not both.")
        raise typer.Exit(1)

    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> dict[str, Any]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            if title is not None:
                doc = await _resolve_document_by_title(client, title)
            else:
                doc = await _find_document_by_id(client, doc_id)  # type: ignore[arg-type]
            space_map = await _fetch_teamspace_map(client)
        return _doc_to_detail(doc, space_map)

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

    print_item(data, title=f"Document: {data.get('title', doc_id or title)}")


@app.command("create")
def docs_create(
    ctx: typer.Context,
    title: Annotated[str, typer.Option("--title", help="Document title.")] = ...,
    space: Annotated[str, typer.Option("--space", help="Teamspace name.")] = ...,
    parent: Annotated[str | None, typer.Option("--parent", help="Parent document ID.")] = None,
) -> None:
    """Create a new document."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> str:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            space_id = await _resolve_teamspace_by_name(client, space)

            parent_id = parent if parent else "document:ids:NoParent"
            new_id = secrets.token_hex(12)

            transaction = {
                "_class": "core:class:TxCreateDoc",
                "objectClass": "document:class:Document",
                "objectSpace": space_id,
                "objectId": new_id,
                "attributes": {
                    "title": title,
                    "content": "",
                    "parent": parent_id,
                    "attachments": 0,
                    "embeddings": 0,
                    "labels": 0,
                    "comments": 0,
                    "references": 0,
                    "rank": "",
                },
                "modifiedBy": auth.account_id,
                "modifiedOn": int(time.time() * 1000),
            }

            await client.tx(transaction)
        return new_id

    try:
        new_id = asyncio.run(_run())
        print_success(f"Document created in teamspace '{space}' (id: {new_id})")
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
def docs_update(
    ctx: typer.Context,
    doc_id: str = typer.Argument(..., help="Document internal ID."),
    title: Annotated[str | None, typer.Option("--title", help="New document title.")] = None,
) -> None:
    """Update an existing document."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> None:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            doc = await _find_document_by_id(client, doc_id)

            operations: dict = {}
            if title is not None:
                operations["title"] = title

            if not operations:
                print_warning("No fields to update — provide at least one of --title.")
                return

            transaction = {
                "_class": "core:class:TxUpdateDoc",
                "objectClass": "document:class:Document",
                "objectSpace": doc.space,
                "objectId": doc.id,
                "operations": operations,
                "modifiedBy": auth.account_id,
                "modifiedOn": int(time.time() * 1000),
            }

            await client.tx(transaction)

    try:
        asyncio.run(_run())
        print_success(f"Document {doc_id} updated.")
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e


@app.command("describe")
def docs_describe(
    ctx: typer.Context,
    doc_id: str | None = typer.Argument(
        None,
        help="Document internal ID (omit when using --title).",
    ),
    title: Annotated[
        str | None,
        typer.Option(
            "--title",
            help="Resolve by case-insensitive exact title match instead of ID.",
        ),
    ] = None,
    raw: Annotated[
        bool,
        typer.Option("--raw", help="Show raw ProseMirror JSON instead of rendered markdown."),
    ] = False,
    set_text: Annotated[
        str | None,
        typer.Option("--set", help="Set content from markdown string."),
    ] = None,
    set_file: Annotated[
        str | None,
        typer.Option("--set-file", help="Set content from a markdown file path."),
    ] = None,
) -> None:
    """Read or update the content of a document by ID or by --title.

    By default, reads and displays the content. Use --set or --set-file to write.
    """
    if set_text is not None and set_file is not None:
        print_error("Use either --set or --set-file, not both.")
        raise typer.Exit(1)

    if (doc_id is None) == (title is None):
        print_error("Provide either DOC_ID or --title, not both.")
        raise typer.Exit(1)

    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _resolve(client: HulyClient) -> Document:
        if title is not None:
            return await _resolve_document_by_title(client, title)
        return await _find_document_by_id(client, doc_id)  # type: ignore[arg-type]

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
            from huly_cli.markup import markdown_to_prosemirror

            auth = await ensure_auth(config)
            async with HulyClient(config, auth) as client:
                markup = markdown_to_prosemirror(markdown_content or "")
                doc = await _resolve(client)
                if doc.content and not _is_inline_markup(doc.content):
                    ok = await client.set_content(
                        "document:class:Document", doc.id, "content", doc.content, markup
                    )
                    if not ok:
                        raise HulyError("Failed to update content via Collaborator RPC.")
                else:
                    blob_ref = await client.create_content(
                        "document:class:Document",
                        doc.id,
                        "content",
                        markup,
                        warn_on_error=False,
                    )
                    if blob_ref is None:
                        raise HulyError("Failed to create content via Collaborator.")
                    await client.tx(
                        {
                            "_class": "core:class:TxUpdateDoc",
                            "objectClass": "document:class:Document",
                            "objectSpace": doc.space,
                            "objectId": doc.id,
                            "operations": {"content": blob_ref},
                            "modifiedBy": auth.account_id,
                            "modifiedOn": int(time.time() * 1000),
                        }
                    )
            return doc.title or doc.id

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

        print_success(f"Content updated for '{title_label}'.")
        return

    # ── Read path ─────────────────────────────────────────────────────────
    async def _run() -> tuple[str, str, str | None]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            doc = await _resolve(client)
            if not doc.content:
                return doc.id, doc.title or doc.id, None
            if _is_inline_markup(doc.content):
                content = doc.content
            else:
                content = await client.get_content(
                    "document:class:Document", doc.id, "content", doc.content
                )
        return doc.id, doc.title or doc.id, content

    try:
        resolved_id, title_label, content = asyncio.run(_run())
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
        print_error(f"No content available for document '{title_label}'.")
        raise typer.Exit(1)

    if is_json_mode():
        if raw:
            print(json.dumps({"ok": True, "id": resolved_id, "content_raw": content}))
        else:
            from huly_cli.markup import prosemirror_to_markdown

            md = prosemirror_to_markdown(content)
            print(json.dumps({"ok": True, "id": resolved_id, "content": md}))
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
            console.print(Panel(Markdown(md_text), title=f"Content: {title_label}"))
        else:
            from huly_cli.markup import prosemirror_to_text

            plain = prosemirror_to_text(content)
            console.print(Panel(plain or "(empty content)", title=f"Content: {title_label}"))


@app.command("search")
def docs_search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Case-insensitive title substring to match."),
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of documents to scan."),
    ] = 200,
) -> None:
    """Search documents by title substring.

    Currently a client-side title-substring filter over `find-all`. The backend
    will swap to the workspace fulltext endpoint once that command lands.
    """
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> list[dict[str, Any]]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            space_map = await _fetch_teamspace_map(client)
            raw = await client.find_all(
                "document:class:Document",
                options={"limit": limit},
            )
            docs = [Document.model_validate(doc) for doc in raw]
            needle = query.lower()
            docs = [d for d in docs if needle in (d.title or "").lower()]
        return [_doc_to_row(d, space_map) for d in docs]

    try:
        rows = asyncio.run(_run())
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    print_list(rows, columns=["title", "space", "parent", "id"], title=f"Search: {query}")


@app.command("delete")
def docs_delete(
    ctx: typer.Context,
    doc_id: str = typer.Argument(..., help="Document internal ID."),
) -> None:
    """Delete a document."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> None:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            doc = await _find_document_by_id(client, doc_id)
            await client.tx(
                {
                    "_class": "core:class:TxRemoveDoc",
                    "objectClass": "document:class:Document",
                    "objectSpace": doc.space,
                    "objectId": doc.id,
                }
            )

    try:
        asyncio.run(_run())
        print_success(f"Document {doc_id} deleted.")
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
