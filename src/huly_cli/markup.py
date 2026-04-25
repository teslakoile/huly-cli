"""ProseMirror / Markup conversion helpers."""

from __future__ import annotations

import json
import re
from typing import Any

# ── ProseMirror → plain text ──────────────────────────────────────────────────


def prosemirror_to_text(json_str: str) -> str:
    """Convert ProseMirror JSON to plain text (strips all formatting)."""
    try:
        doc = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return json_str or ""
    return _node_to_text(doc).strip()


def _node_to_text(node: Any) -> str:
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type", "")
    if node_type == "text":
        return node.get("text", "")
    if node_type == "hardBreak":
        return "\n"
    children = node.get("content", [])
    parts = [_node_to_text(c) for c in children]
    text = "".join(parts)
    # Block-level nodes get a newline appended
    if node_type in (
        "paragraph",
        "heading",
        "bulletList",
        "orderedList",
        "taskList",
        "blockquote",
        "codeBlock",
        "table",
        "tableRow",
        "listItem",
        "taskItem",
    ):
        text = text.rstrip("\n") + "\n"
    return text


# ── ProseMirror → markdown ────────────────────────────────────────────────────


def prosemirror_to_markdown(json_str: str) -> str:
    """Best-effort conversion of ProseMirror JSON to markdown."""
    try:
        doc = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return json_str or ""
    lines = _node_to_md(doc, depth=0)
    return "\n".join(lines).strip()


def _node_to_md(node: Any, depth: int = 0, ordered: bool = False, index: int = 1) -> list[str]:
    """Recursively convert a ProseMirror node to markdown lines."""
    if not isinstance(node, dict):
        return []
    node_type = node.get("type", "")
    children = node.get("content", [])

    if node_type == "doc":
        lines: list[str] = []
        for child in children:
            lines.extend(_node_to_md(child, depth=depth))
        return lines

    if node_type == "paragraph":
        inline = _inline_to_md(children)
        return [inline, ""]

    if node_type == "heading":
        level = node.get("attrs", {}).get("level", 1)
        inline = _inline_to_md(children)
        return [f"{'#' * level} {inline}", ""]

    if node_type == "bulletList":
        lines = []
        for child in children:
            lines.extend(_node_to_md(child, depth=depth, ordered=False))
        return lines

    if node_type == "orderedList":
        lines = []
        for idx, child in enumerate(children, start=1):
            lines.extend(_node_to_md(child, depth=depth, ordered=True, index=idx))
        return lines

    if node_type == "taskList":
        lines = []
        for child in children:
            lines.extend(_node_to_md(child, depth=depth, ordered=False))
        return lines

    if node_type == "listItem":
        marker = f"{index}." if ordered else "-"
        prefix = "  " * depth + marker + " "
        inner: list[str] = []
        for child in children:
            inner.extend(_node_to_md(child, depth=depth + 1))
        # Merge first paragraph inline, rest as continuation
        result: list[str] = []
        for i, line in enumerate(inner):
            if line == "":
                continue
            if i == 0:
                result.append(prefix + line)
            else:
                result.append("  " * (depth + 1) + line)
        return result

    if node_type == "taskItem":
        checked = node.get("attrs", {}).get("checked", False)
        box = "[x]" if checked else "[ ]"
        prefix = "  " * depth + f"- {box} "
        inner = []
        for child in children:
            inner.extend(_node_to_md(child, depth=depth + 1))
        result = []
        for i, line in enumerate(inner):
            if line == "":
                continue
            if i == 0:
                result.append(prefix + line)
            else:
                result.append("  " * (depth + 1) + line)
        return result

    if node_type == "blockquote":
        inner = []
        for child in children:
            inner.extend(_node_to_md(child, depth=depth))
        return ["> " + line if line else ">" for line in inner]

    if node_type == "codeBlock":
        lang = node.get("attrs", {}).get("language", "") or ""
        code = _node_to_text(node).rstrip("\n")
        return [f"```{lang}", code, "```", ""]

    if node_type == "table":
        return _table_to_md(node)

    if node_type == "hardBreak":
        return ["  "]  # trailing spaces = line break in markdown

    # Fallback: extract inline text
    inline = _inline_to_md(children)
    if inline:
        return [inline, ""]
    return []


def _inline_to_md(nodes: list[Any]) -> str:
    """Convert inline content nodes to a markdown string."""
    result = ""
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = node.get("type", "")
        if node_type == "text":
            original = node.get("text", "")
            text = original
            marks = node.get("marks", [])
            mark_types = {m.get("type") for m in marks}
            if "code" in mark_types:
                text = f"`{text}`"
            if "bold" in mark_types:
                text = f"**{text}**"
            if "italic" in mark_types:
                text = f"*{text}*"
            if "strike" in mark_types:
                text = f"~~{text}~~"
            if "underline" in mark_types:
                text = f"<u>{text}</u>"
            for m in marks:
                if m.get("type") == "link":
                    href = m.get("attrs", {}).get("href", "")
                    if mark_types == {"link"} and original == href:
                        text = href
                    else:
                        text = f"[{text}]({href})"
            result += text
        elif node_type == "hardBreak":
            result += "\n"
        else:
            # Nested inline (e.g. nested marks)
            result += _inline_to_md(node.get("content", []))
    return result


def _table_to_md(node: dict) -> list[str]:
    """Convert a ProseMirror table node to GFM markdown table."""
    rows_data: list[list[str]] = []
    for row in node.get("content", []):
        if row.get("type") != "tableRow":
            continue
        cells: list[str] = []
        for cell in row.get("content", []):
            cell_type = cell.get("type", "")
            if cell_type not in ("tableCell", "tableHeader"):
                continue
            inner = _inline_to_md(
                [item for child in cell.get("content", []) for item in child.get("content", [])]
            )
            cells.append(inner.strip())
        rows_data.append(cells)

    if not rows_data:
        return []

    # Determine column count
    col_count = max(len(r) for r in rows_data)
    # Pad rows
    for row in rows_data:
        while len(row) < col_count:
            row.append("")

    lines: list[str] = []
    header = rows_data[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * col_count) + " |")
    for row in rows_data[1:]:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return lines


# ── Markdown → ProseMirror JSON ───────────────────────────────────────────────


def markdown_to_prosemirror(md: str) -> str:
    """Convert markdown to ProseMirror JSON string (best-effort).

    Supports: headings, bullet/ordered lists, task lists, bold, italic,
    inline code, code blocks, blockquotes, paragraphs, blank lines.
    """
    content: list[dict] = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # Fenced code block
        m = re.match(r"^```(\w*)$", line)
        if m:
            lang = m.group(1)
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            node: dict = {
                "type": "codeBlock",
                "content": [{"type": "text", "text": "\n".join(code_lines)}],
            }
            if lang:
                node["attrs"] = {"language": lang}
            content.append(node)
            continue

        # Heading
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            content.append(
                {
                    "type": "heading",
                    "attrs": {"level": level},
                    "content": _parse_inline(m.group(2)),
                }
            )
            i += 1
            continue

        # Blockquote (simple single-level)
        if line.startswith("> "):
            bq_lines: list[str] = []
            while i < len(lines) and (lines[i].startswith("> ") or lines[i] == ">"):
                bq_lines.append(lines[i][2:] if lines[i].startswith("> ") else "")
                i += 1
            inner_doc = json.loads(markdown_to_prosemirror("\n".join(bq_lines)))
            content.append({"type": "blockquote", "content": inner_doc.get("content", [])})
            continue

        # Task list item (- [ ] or - [x])
        m = re.match(r"^\s*[-*]\s+\[([ xX])\]\s+(.*)", line)
        if m:
            # Collect consecutive task items
            task_items: list[dict] = []
            while i < len(lines):
                tm = re.match(r"^\s*[-*]\s+\[([ xX])\]\s+(.*)", lines[i])
                if not tm:
                    break
                checked = tm.group(1).lower() == "x"
                task_items.append(
                    {
                        "type": "taskItem",
                        "attrs": {"checked": checked},
                        "content": [{"type": "paragraph", "content": _parse_inline(tm.group(2))}],
                    }
                )
                i += 1
            content.append({"type": "taskList", "content": task_items})
            continue

        # Bullet list
        if re.match(r"^\s*[-*]\s", line):
            items: list[dict] = []
            while i < len(lines) and re.match(r"^\s*[-*]\s", lines[i]):
                text = re.sub(r"^\s*[-*]\s+", "", lines[i])
                items.append(
                    {
                        "type": "listItem",
                        "content": [{"type": "paragraph", "content": _parse_inline(text)}],
                    }
                )
                i += 1
            content.append({"type": "bulletList", "content": items})
            continue

        # Ordered list
        if re.match(r"^\s*\d+\.\s", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s", lines[i]):
                text = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                items.append(
                    {
                        "type": "listItem",
                        "content": [{"type": "paragraph", "content": _parse_inline(text)}],
                    }
                )
                i += 1
            content.append({"type": "orderedList", "content": items})
            continue

        # GFM pipe table. Requires at least 2 consecutive lines:
        #   | a | b |
        #   | --- | --- |
        # (optional alignment colons), followed by zero or more body rows.
        if _is_table_row(line) and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
            header_cells = _split_table_cells(line)
            # Skip alignment row entirely (attrs not stored; non-goal per issue).
            i += 2
            body_rows: list[list[str]] = []
            while i < len(lines) and _is_table_row(lines[i]):
                body_rows.append(_split_table_cells(lines[i]))
                i += 1

            rows: list[dict] = []
            # Header row
            rows.append(
                {
                    "type": "tableRow",
                    "content": [_cell_node("tableHeader", c) for c in header_cells],
                }
            )
            # Body rows
            for body in body_rows:
                rows.append(
                    {
                        "type": "tableRow",
                        "content": [_cell_node("tableCell", c) for c in body],
                    }
                )
            content.append({"type": "table", "content": rows})
            continue

        # Empty line
        if not line.strip():
            i += 1
            continue

        # Paragraph
        content.append({"type": "paragraph", "content": _parse_inline(line)})
        i += 1

    return json.dumps({"type": "doc", "content": content})


# ── GFM table helpers ─────────────────────────────────────────────────────────


_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$")


def _is_table_row(line: str) -> bool:
    return bool(_TABLE_ROW_RE.match(line))


def _is_table_separator(line: str) -> bool:
    return bool(_TABLE_SEPARATOR_RE.match(line))


def _split_table_cells(line: str) -> list[str]:
    """Split a GFM pipe-table row into cell strings.

    Drops the leading/trailing empty segments produced by the enclosing pipes
    (``| a | b |`` → ``["a", "b"]``) and strips each cell. Escaped pipes
    (``\\|``) inside a cell are preserved as literal pipes.
    """
    stripped = line.strip()
    # Strip outer pipes if present.
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]

    # Split on unescaped pipes.
    cells: list[str] = []
    buf = ""
    k = 0
    while k < len(stripped):
        ch = stripped[k]
        if ch == "\\" and k + 1 < len(stripped) and stripped[k + 1] == "|":
            buf += "|"
            k += 2
            continue
        if ch == "|":
            cells.append(buf.strip())
            buf = ""
            k += 1
            continue
        buf += ch
        k += 1
    cells.append(buf.strip())
    return cells


def _cell_node(cell_type: str, text: str) -> dict:
    """Build a ``tableCell`` or ``tableHeader`` node wrapping a single paragraph."""
    return {
        "type": cell_type,
        "attrs": {"colspan": 1, "rowspan": 1},
        "content": [{"type": "paragraph", "content": _parse_inline(text)}],
    }


def _parse_inline(text: str) -> list[dict]:
    """Parse inline markdown (bold, italic, code, links) into ProseMirror inline nodes."""
    # Pattern order matters: code > bold+italic > bold > italic > link > autolink.
    # The bare-URL autolink (group 10) intentionally comes after the explicit
    # ``[text](url)`` link form so a markdown link is preferred when both could match.
    pattern = re.compile(
        r"(`[^`]+`)"  # 1: inline code
        r"|(\*\*\*[^*]+\*\*\*)"  # 2: bold+italic ***
        r"|(\*\*[^*]+\*\*)"  # 3: bold **
        r"|(\*[^*]+\*)"  # 4: italic *
        r"|(_[^_]+_)"  # 5: italic _
        r"|(~~[^~]+~~)"  # 6: strikethrough
        r"|(\[([^\]]+)\]\(([^)]+)\))"  # 7,8,9: link [text](url)
        r"|(https?://[^\s<>\[\]`]+)"  # 10: bare URL autolink
    )

    runs: list[dict] = []
    last = 0
    for m in pattern.finditer(text):
        # Plain text before this match
        if m.start() > last:
            runs.append({"type": "text", "text": text[last : m.start()]})
        last = m.end()

        if m.group(1):  # inline code
            runs.append({"type": "text", "text": m.group(1)[1:-1], "marks": [{"type": "code"}]})
        elif m.group(2):  # bold+italic
            runs.append(
                {
                    "type": "text",
                    "text": m.group(2)[3:-3],
                    "marks": [{"type": "bold"}, {"type": "italic"}],
                }
            )
        elif m.group(3):  # bold
            runs.append({"type": "text", "text": m.group(3)[2:-2], "marks": [{"type": "bold"}]})
        elif m.group(4):  # italic *
            runs.append({"type": "text", "text": m.group(4)[1:-1], "marks": [{"type": "italic"}]})
        elif m.group(5):  # italic _
            runs.append({"type": "text", "text": m.group(5)[1:-1], "marks": [{"type": "italic"}]})
        elif m.group(6):  # strikethrough
            runs.append({"type": "text", "text": m.group(6)[2:-2], "marks": [{"type": "strike"}]})
        elif m.group(7):  # link
            link_text = m.group(8)
            href = m.group(9)
            runs.append(
                {
                    "type": "text",
                    "text": link_text,
                    "marks": [{"type": "link", "attrs": {"href": href, "target": "_blank"}}],
                }
            )
        elif m.group(10):  # bare URL autolink
            url, trailing = _split_url_trailing_punct(m.group(10))
            runs.append(
                {
                    "type": "text",
                    "text": url,
                    "marks": [{"type": "link", "attrs": {"href": url, "target": "_blank"}}],
                }
            )
            if trailing:
                runs.append({"type": "text", "text": trailing})

    # Trailing plain text
    if last < len(text):
        runs.append({"type": "text", "text": text[last:]})

    return runs if runs else [{"type": "text", "text": text}]


def _split_url_trailing_punct(url: str) -> tuple[str, str]:
    """Split sentence-level punctuation off the tail of an autolinked URL.

    Greedy URL matching pulls in trailing characters that almost certainly
    belong to the surrounding prose, not the URL itself: a period at the end
    of a sentence, a comma in a list, an unbalanced closing bracket from
    ``(see https://x.com)``. Strip those, but leave balanced brackets intact
    so URLs like ``https://en.wikipedia.org/wiki/Foo_(bar)`` survive.
    """
    trailing = ""
    while url:
        last = url[-1]
        if last in ".,;:!?":
            trailing = last + trailing
            url = url[:-1]
        elif last == ")" and url.count("(") < url.count(")"):
            trailing = last + trailing
            url = url[:-1]
        elif last == "]" and url.count("[") < url.count("]"):
            trailing = last + trailing
            url = url[:-1]
        else:
            break
    return url, trailing
