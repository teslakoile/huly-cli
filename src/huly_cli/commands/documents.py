"""Documents commands: list, get, create, update, describe, tree."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from typing import Annotated, Any

import typer
from rich.tree import Tree

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

NO_PARENT = "document:ids:NoParent"

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


async def _read_doc_markdown(client: HulyClient, doc: Document) -> str:
    """Read a document's content and return it as markdown.

    Mirrors the non-raw read path used by ``documents describe``:
    honors the inline-vs-blob branch and falls through to an empty string
    when the doc has no content.
    """
    from huly_cli.markup import prosemirror_to_markdown

    if not doc.content:
        return ""
    if _is_inline_markup(doc.content):
        content = doc.content
    else:
        content = await client.get_content(
            "document:class:Document", doc.id, "content", doc.content
        )
    if not content:
        return ""
    return prosemirror_to_markdown(content)


async def _write_markdown_to_doc(
    client: HulyClient, auth: Any, doc: Document, markdown_content: str
) -> None:
    """Write markdown content to an existing document.

    Mirrors the write path used by ``documents describe --set-file``:
    uses ``set_content`` when a blob ref already exists, otherwise
    calls ``create_content`` then patches the ``content`` field via tx.
    """
    from huly_cli.markup import markdown_to_prosemirror

    markup = markdown_to_prosemirror(markdown_content or "")
    if doc.content and not _is_inline_markup(doc.content):
        ok = await client.set_content(
            "document:class:Document", doc.id, "content", doc.content, markup
        )
        if not ok:
            raise HulyError("Failed to update content via Collaborator RPC.")
        return

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


# ── Commands ──────────────────────────────────────────────────────────────────


@app.command("list")
def docs_list(
    ctx: typer.Context,
    space: Annotated[
        str | None,
        typer.Option("--space", "-s", help="Filter by teamspace name."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of documents to return."),
    ] = 50,
) -> None:
    """List documents, with optional teamspace filter."""
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

            raw = await client.find_all(
                "document:class:Document",
                query=query,
                options={"limit": limit},
            )
            docs = [Document.model_validate(doc) for doc in raw]

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


# ── tree helpers ─────────────────────────────────────────────────────────────


def _normalize_parent(parent: str | None) -> str:
    """Treat empty string and the sentinel NoParent value as 'no parent'."""
    if not parent or parent == NO_PARENT:
        return ""
    return parent


def _build_children_index(docs: list[Document]) -> dict[str, list[Document]]:
    """Group docs by normalized parent id.

    Orphans (parent points to an ID that isn't in the fetched set) are bucketed
    under "" (no parent) so they render under their space root instead of
    vanishing.
    """
    ids = {d.id for d in docs}
    index: dict[str, list[Document]] = {}
    for doc in docs:
        parent = _normalize_parent(doc.parent)
        if parent and parent not in ids:
            parent = ""  # orphan → attach to synthetic root
        index.setdefault(parent, []).append(doc)
    # Sort siblings by rank ascending (same order as Huly UI).
    for siblings in index.values():
        siblings.sort(key=lambda d: (d.rank or "", d.title or ""))
    return index


def _doc_to_tree_node(
    doc: Document,
    children_index: dict[str, list[Document]],
    *,
    remaining: int | None,
    visited: set[str],
) -> dict[str, Any]:
    """Recursively build a {id, title, children: [...]} node.

    ``remaining`` is the number of document levels still allowed starting at
    this node (``None`` = unlimited). When it reaches ``1`` the current doc is
    emitted with no children; when ``0`` the node is still emitted but recursion
    below it stops. Cycles are broken on first re-visit.
    """
    node: dict[str, Any] = {"id": doc.id, "title": doc.title, "children": []}
    if doc.id in visited:
        return node
    visited = visited | {doc.id}

    if remaining is not None and remaining <= 1:
        return node

    next_remaining = None if remaining is None else remaining - 1
    for child in children_index.get(doc.id, []):
        node["children"].append(
            _doc_to_tree_node(
                child,
                children_index,
                remaining=next_remaining,
                visited=visited,
            )
        )
    return node


def _render_tree_node(node: dict[str, Any], parent: Tree) -> None:
    branch = parent.add(f"{node['title']} [dim]({node['id']})[/dim]")
    for child in node["children"]:
        _render_tree_node(child, branch)


@app.command("tree")
def docs_tree(
    ctx: typer.Context,
    space: Annotated[
        str | None,
        typer.Option("--space", "-s", help="Filter by teamspace name."),
    ] = None,
    root: Annotated[
        str | None,
        typer.Option("--root", help="Render subtree rooted at this document ID."),
    ] = None,
    depth: Annotated[
        int | None,
        typer.Option(
            "--depth",
            help=(
                "Cap recursion. Without --root, N = number of document levels "
                "under each space (1 = top-level docs only). With --root, the "
                "root itself counts as level 1 (tree -L N semantics)."
            ),
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of documents to fetch for building the tree.",
        ),
    ] = 1000,
) -> None:
    """Render documents hierarchically via the existing parent field.

    Without flags, renders all spaces, grouped by teamspace root. ``--space``
    narrows to one teamspace; ``--root`` renders a subtree under a single
    document (takes precedence over ``--space``). ``--depth`` caps recursion.
    """
    if depth is not None and depth < 1:
        print_error("--depth must be >= 1.")
        raise typer.Exit(1)

    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> tuple[list[dict[str, Any]] | dict[str, Any], bool]:
        """Return (payload, is_single_root)."""
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            space_map = await _fetch_teamspace_map(client)

            query: dict[str, Any] = {}
            filter_space_id: str | None = None
            if root is not None:
                # --root takes precedence; fetch just that document's space.
                root_doc = await _find_document_by_id(client, root)
                query["space"] = root_doc.space
                filter_space_id = root_doc.space
            elif space:
                filter_space_id = await _resolve_teamspace_by_name(client, space)
                query["space"] = filter_space_id

            raw = await client.find_all(
                "document:class:Document",
                query=query,
                options={"limit": limit},
            )
            docs = [Document.model_validate(d) for d in raw]

        children_index = _build_children_index(docs)

        if root is not None:
            # Single subtree rooted at the requested document.
            root_doc = next((d for d in docs if d.id == root), None)
            if root_doc is None:
                raise NotFoundError(f"Document '{root}' not found.")
            node = _doc_to_tree_node(
                root_doc,
                children_index,
                remaining=depth,
                visited=set(),
            )
            return node, True

        # All-spaces or --space: group by space, each space is a root.
        if filter_space_id is not None:
            space_ids = [filter_space_id]
        else:
            space_ids = sorted({d.space for d in docs})

        roots: list[dict[str, Any]] = []
        for sid in space_ids:
            space_name = space_map.get(sid, sid)
            space_node: dict[str, Any] = {
                "id": sid,
                "title": space_name,
                "children": [],
            }
            top_docs = [d for d in children_index.get("", []) if d.space == sid]
            for doc in top_docs:
                space_node["children"].append(
                    _doc_to_tree_node(
                        doc,
                        children_index,
                        remaining=depth,
                        visited=set(),
                    )
                )
            roots.append(space_node)

        return roots, False

    try:
        payload, single_root = asyncio.run(_run())
    except NotFoundError as e:
        print_error(e.message)
        raise typer.Exit(1) from e
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    if is_json_mode():
        envelope: dict[str, Any] = {"ok": True, "data": payload}
        print(json.dumps(envelope))
        return

    if single_root:
        assert isinstance(payload, dict)
        tree = Tree(f"{payload['title']} [dim]({payload['id']})[/dim]")
        for child in payload["children"]:
            _render_tree_node(child, tree)
        console.print(tree)
        return

    assert isinstance(payload, list)
    if not payload:
        console.print("[dim](no documents)[/dim]")
        return
    for space_node in payload:
        tree = Tree(f"[bold]{space_node['title']}[/bold] [dim]({space_node['id']})[/dim]")
        for child in space_node["children"]:
            _render_tree_node(child, tree)
        console.print(tree)


@app.command("get")
def docs_get(
    ctx: typer.Context,
    doc_id: str = typer.Argument(..., help="Document internal ID."),
) -> None:
    """Get details of a document."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> dict[str, Any]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            doc = await _find_document_by_id(client, doc_id)
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

    print_item(data, title=f"Document: {data.get('title', doc_id)}")


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
    doc_id: str = typer.Argument(..., help="Document internal ID."),
    raw: Annotated[
        bool,
        typer.Option("--raw", help="Show raw ProseMirror JSON instead of rendered markdown."),
    ] = False,
    markdown: Annotated[
        bool,
        typer.Option(
            "--markdown",
            help="Emit plain GFM markdown to stdout (no Rich box/reflow) — agent-friendly.",
        ),
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
    """Read or update the content of a document.

    By default, reads and displays the content. Use --set or --set-file to write.
    Use --markdown to emit plain GFM (no Rich panel), which is safe to diff,
    grep, or feed back into `--set-file`.
    """
    if set_text is not None and set_file is not None:
        print_error("Use either --set or --set-file, not both.")
        raise typer.Exit(1)
    if raw and markdown:
        print_error("Use either --raw or --markdown, not both.")
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
            auth = await ensure_auth(config)
            async with HulyClient(config, auth) as client:
                doc = await _find_document_by_id(client, doc_id)
                await _write_markdown_to_doc(client, auth, doc, markdown_content or "")
            return doc.title or doc_id

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
    async def _run() -> tuple[str, str | None]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            doc = await _find_document_by_id(client, doc_id)
            if not doc.content:
                return doc.title or doc_id, None
            if _is_inline_markup(doc.content):
                content = doc.content
            else:
                content = await client.get_content(
                    "document:class:Document", doc.id, "content", doc.content
                )
        return doc.title or doc_id, content

    try:
        title_label, content = asyncio.run(_run())
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
            print(json.dumps({"ok": True, "id": doc_id, "content_raw": content}))
        else:
            from huly_cli.markup import prosemirror_to_markdown

            md = prosemirror_to_markdown(content)
            print(json.dumps({"ok": True, "id": doc_id, "content": md}))
        return

    if raw:
        try:
            parsed = json.loads(content)
            console.print_json(json.dumps(parsed, indent=2))
        except (json.JSONDecodeError, TypeError):
            console.print(content)
    elif markdown:
        # Plain GFM to stdout — no Rich box, no reflow. Agent-friendly and safe
        # to round-trip back through `--set` / `--set-file`.
        from huly_cli.markup import prosemirror_to_markdown

        md_text = prosemirror_to_markdown(content)
        print(md_text)
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


@app.command("duplicate")
def docs_duplicate(
    ctx: typer.Context,
    doc_id: str = typer.Argument(..., help="Source document internal ID."),
    title: Annotated[str, typer.Option("--title", help="Title for the new document.")] = ...,
    space: Annotated[
        str | None,
        typer.Option("--space", help="Teamspace name. Defaults to the source's space."),
    ] = None,
    parent: Annotated[
        str | None,
        typer.Option(
            "--parent",
            help="Parent document ID. Defaults to the source's parent.",
        ),
    ] = None,
) -> None:
    """Duplicate a document, copying its content into a new document.

    Reads the source document's metadata and markdown content, creates a new
    document in the target (or inherited) space/parent, and writes the content
    into it. Prints the new document ID; with ``--json`` returns the full record.
    """
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> dict[str, Any]:
        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            source = await _find_document_by_id(client, doc_id)

            # Resolve target space: inherit source when --space not given.
            if space is None:
                target_space_id = source.space
            else:
                target_space_id = await _resolve_teamspace_by_name(client, space)

            # Resolve target parent: inherit source when --parent not given.
            target_parent_id = parent if parent is not None else source.parent
            if not target_parent_id:
                target_parent_id = "document:ids:NoParent"

            # Read source content as markdown (same path as describe non-raw).
            markdown_content = await _read_doc_markdown(client, source)

            # Create the new doc shell.
            new_id = secrets.token_hex(12)
            await client.tx(
                {
                    "_class": "core:class:TxCreateDoc",
                    "objectClass": "document:class:Document",
                    "objectSpace": target_space_id,
                    "objectId": new_id,
                    "attributes": {
                        "title": title,
                        "content": "",
                        "parent": target_parent_id,
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
            )

            # Copy content into the new doc (same path as --set-file).
            if markdown_content:
                new_doc = await _find_document_by_id(client, new_id)
                await _write_markdown_to_doc(client, auth, new_doc, markdown_content)

            if is_json_mode():
                new_doc = await _find_document_by_id(client, new_id)
                space_map = await _fetch_teamspace_map(client)
                return _doc_to_detail(new_doc, space_map)
            return {"id": new_id}

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

    if is_json_mode():
        print_item(data, title=f"Document: {data.get('title', data.get('id', ''))}")
    else:
        print_success(f"Document duplicated (id: {data['id']})")


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
