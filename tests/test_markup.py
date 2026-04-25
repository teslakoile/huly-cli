"""Pure unit tests for markup.py — no mocking required."""

from __future__ import annotations

import json

from huly_cli.markup import (
    markdown_to_prosemirror,
    prosemirror_to_markdown,
    prosemirror_to_text,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def doc(*nodes):
    """Build a ProseMirror doc JSON string."""
    return json.dumps({"type": "doc", "content": list(nodes)})


def paragraph(*inline):
    return {"type": "paragraph", "content": list(inline)}


def heading(level, *inline):
    return {"type": "heading", "attrs": {"level": level}, "content": list(inline)}


def text(t, **marks):
    node = {"type": "text", "text": t}
    if marks:
        node["marks"] = [{"type": k} for k in marks if marks[k]]
    return node


def bold_text(t):
    return {"type": "text", "text": t, "marks": [{"type": "bold"}]}


def italic_text(t):
    return {"type": "text", "text": t, "marks": [{"type": "italic"}]}


def link_text(t, href):
    return {
        "type": "text",
        "text": t,
        "marks": [{"type": "link", "attrs": {"href": href, "target": "_blank"}}],
    }


def bullet_list(*items):
    return {"type": "bulletList", "content": list(items)}


def ordered_list(*items):
    return {"type": "orderedList", "content": list(items)}


def list_item(*content):
    return {"type": "listItem", "content": list(content)}


def task_list(*items):
    return {"type": "taskList", "content": list(items)}


def task_item(checked, *content):
    return {"type": "taskItem", "attrs": {"checked": checked}, "content": list(content)}


def code_block(code, lang=None):
    node = {
        "type": "codeBlock",
        "content": [{"type": "text", "text": code}],
    }
    if lang:
        node["attrs"] = {"language": lang}
    return node


def blockquote(*content):
    return {"type": "blockquote", "content": list(content)}


def table(*rows):
    return {"type": "table", "content": list(rows)}


def table_row(*cells):
    return {"type": "tableRow", "content": list(cells)}


def table_header(t):
    return {"type": "tableHeader", "content": [paragraph(text(t))]}


def table_cell(t):
    return {"type": "tableCell", "content": [paragraph(text(t))]}


# ── prosemirror_to_text ────────────────────────────────────────────────────────


class TestProsemirrorToText:
    def test_simple_paragraph(self):
        pm = doc(paragraph(text("Hello world")))
        assert prosemirror_to_text(pm) == "Hello world"

    def test_heading_no_hashes(self):
        pm = doc(heading(2, text("Section Title")))
        result = prosemirror_to_text(pm)
        assert result == "Section Title"
        assert "#" not in result

    def test_nested_bullet_list(self):
        pm = doc(
            bullet_list(
                list_item(paragraph(text("Item one"))),
                list_item(paragraph(text("Item two"))),
            )
        )
        result = prosemirror_to_text(pm)
        assert "Item one" in result
        assert "Item two" in result

    def test_empty_string_input(self):
        assert prosemirror_to_text("") == ""

    def test_null_input(self):
        assert prosemirror_to_text(None) == ""

    def test_malformed_json(self):
        # Should not raise, returns the input or empty string
        result = prosemirror_to_text("{not valid json")
        assert isinstance(result, str)

    def test_empty_doc(self):
        pm = json.dumps({"type": "doc", "content": []})
        assert prosemirror_to_text(pm) == ""

    def test_multiple_paragraphs(self):
        pm = doc(paragraph(text("First")), paragraph(text("Second")))
        result = prosemirror_to_text(pm)
        assert "First" in result
        assert "Second" in result


# ── prosemirror_to_markdown ────────────────────────────────────────────────────


class TestProsemirrorToMarkdown:
    def test_heading(self):
        pm = doc(heading(2, text("Title")))
        result = prosemirror_to_markdown(pm)
        assert result.startswith("## Title")

    def test_bold_text(self):
        pm = doc(paragraph(bold_text("bold")))
        result = prosemirror_to_markdown(pm)
        assert "**bold**" in result

    def test_italic_text(self):
        pm = doc(paragraph(italic_text("italic")))
        result = prosemirror_to_markdown(pm)
        assert "*italic*" in result

    def test_link(self):
        pm = doc(paragraph(link_text("click here", "https://example.com")))
        result = prosemirror_to_markdown(pm)
        assert "[click here](https://example.com)" in result

    def test_bullet_list(self):
        pm = doc(
            bullet_list(
                list_item(paragraph(text("item1"))),
                list_item(paragraph(text("item2"))),
            )
        )
        result = prosemirror_to_markdown(pm)
        assert "- item1" in result
        assert "- item2" in result

    def test_ordered_list(self):
        pm = doc(
            ordered_list(
                list_item(paragraph(text("item1"))),
                list_item(paragraph(text("item2"))),
            )
        )
        result = prosemirror_to_markdown(pm)
        assert "1. item1" in result
        assert "2. item2" in result

    def test_task_list_unchecked(self):
        pm = doc(
            task_list(
                task_item(False, paragraph(text("unchecked"))),
            )
        )
        result = prosemirror_to_markdown(pm)
        assert "- [ ] unchecked" in result

    def test_task_list_checked(self):
        pm = doc(
            task_list(
                task_item(True, paragraph(text("checked"))),
            )
        )
        result = prosemirror_to_markdown(pm)
        assert "- [x] checked" in result

    def test_task_list_mixed(self):
        pm = doc(
            task_list(
                task_item(False, paragraph(text("unchecked"))),
                task_item(True, paragraph(text("checked"))),
            )
        )
        result = prosemirror_to_markdown(pm)
        assert "- [ ] unchecked" in result
        assert "- [x] checked" in result

    def test_code_block_with_language(self):
        pm = doc(code_block("print('hi')", lang="python"))
        result = prosemirror_to_markdown(pm)
        assert "```python" in result
        assert "print('hi')" in result
        assert result.count("```") >= 2

    def test_blockquote(self):
        pm = doc(blockquote(paragraph(text("text"))))
        result = prosemirror_to_markdown(pm)
        assert "> " in result
        assert "text" in result

    def test_table(self):
        pm = doc(
            table(
                table_row(table_header("Col1"), table_header("Col2")),
                table_row(table_cell("A"), table_cell("B")),
            )
        )
        result = prosemirror_to_markdown(pm)
        assert "Col1" in result
        assert "Col2" in result
        assert "---" in result
        assert "A" in result
        assert "B" in result
        assert "|" in result

    def test_nested_heading_list_paragraph(self):
        pm = doc(
            heading(1, text("Main")),
            bullet_list(list_item(paragraph(text("point")))),
            paragraph(text("End")),
        )
        result = prosemirror_to_markdown(pm)
        assert "# Main" in result
        assert "- point" in result
        assert "End" in result

    def test_empty_doc(self):
        pm = json.dumps({"type": "doc", "content": []})
        result = prosemirror_to_markdown(pm)
        assert result == ""

    def test_null_input(self):
        result = prosemirror_to_markdown(None)
        assert isinstance(result, str)


# ── markdown_to_prosemirror ────────────────────────────────────────────────────


class TestMarkdownToProsemirror:
    def _parse(self, md: str) -> dict:
        return json.loads(markdown_to_prosemirror(md))

    def test_round_trip_heading(self):
        md = "## Hello World"
        doc = self._parse(md)
        assert doc["type"] == "doc"
        headings = [n for n in doc["content"] if n["type"] == "heading"]
        assert len(headings) == 1
        assert headings[0]["attrs"]["level"] == 2
        # Text content
        texts = [c["text"] for c in headings[0]["content"] if c["type"] == "text"]
        assert "Hello World" in texts

    def test_round_trip_bullet_list(self):
        md = "- alpha\n- beta"
        doc = self._parse(md)
        lists = [n for n in doc["content"] if n["type"] == "bulletList"]
        assert len(lists) == 1
        items = lists[0]["content"]
        assert len(items) == 2
        # Each item is a listItem
        assert all(i["type"] == "listItem" for i in items)

    def test_round_trip_bold(self):
        md = "**bold text**"
        doc = self._parse(md)
        paragraphs = [n for n in doc["content"] if n["type"] == "paragraph"]
        assert len(paragraphs) >= 1
        inline = paragraphs[0]["content"]
        bold_nodes = [n for n in inline if any(m["type"] == "bold" for m in n.get("marks", []))]
        assert len(bold_nodes) >= 1
        assert bold_nodes[0]["text"] == "bold text"

    def test_round_trip_code_block(self):
        md = "```python\nprint('hi')\n```"
        doc = self._parse(md)
        code_blocks = [n for n in doc["content"] if n["type"] == "codeBlock"]
        assert len(code_blocks) == 1
        assert code_blocks[0].get("attrs", {}).get("language") == "python"
        texts = [c["text"] for c in code_blocks[0]["content"] if c["type"] == "text"]
        assert "print('hi')" in texts

    def test_round_trip_link(self):
        md = "[click here](https://example.com)"
        doc = self._parse(md)
        paragraphs = [n for n in doc["content"] if n["type"] == "paragraph"]
        assert len(paragraphs) >= 1
        inline = paragraphs[0]["content"]
        link_nodes = [n for n in inline if any(m["type"] == "link" for m in n.get("marks", []))]
        assert len(link_nodes) >= 1
        link_mark = next(m for m in link_nodes[0]["marks"] if m["type"] == "link")
        assert link_mark["attrs"]["href"] == "https://example.com"
        assert link_nodes[0]["text"] == "click here"

    def test_heading_level_1(self):
        doc = self._parse("# H1")
        h = next(n for n in doc["content"] if n["type"] == "heading")
        assert h["attrs"]["level"] == 1

    def test_heading_level_6(self):
        doc = self._parse("###### H6")
        h = next(n for n in doc["content"] if n["type"] == "heading")
        assert h["attrs"]["level"] == 6

    def test_ordered_list(self):
        md = "1. first\n2. second"
        doc = self._parse(md)
        lists = [n for n in doc["content"] if n["type"] == "orderedList"]
        assert len(lists) == 1
        assert len(lists[0]["content"]) == 2

    def test_task_list(self):
        md = "- [ ] todo\n- [x] done"
        doc = self._parse(md)
        task_lists = [n for n in doc["content"] if n["type"] == "taskList"]
        assert len(task_lists) == 1
        items = task_lists[0]["content"]
        assert items[0]["type"] == "taskItem"
        assert items[0]["attrs"]["checked"] is False
        assert items[1]["attrs"]["checked"] is True

    def test_italic_mark(self):
        md = "*italic text*"
        doc = self._parse(md)
        paragraphs = [n for n in doc["content"] if n["type"] == "paragraph"]
        inline = paragraphs[0]["content"]
        italic_nodes = [n for n in inline if any(m["type"] == "italic" for m in n.get("marks", []))]
        assert len(italic_nodes) >= 1

    def test_round_trip_markdown(self):
        """Markdown → ProseMirror → Markdown should preserve key structure."""
        md = "## Title\n\n- item1\n- item2\n\nSome paragraph text."
        pm_json = markdown_to_prosemirror(md)
        back = prosemirror_to_markdown(pm_json)
        assert "## Title" in back
        assert "item1" in back
        assert "item2" in back
        assert "Some paragraph text." in back

    def test_empty_string(self):
        doc = self._parse("")
        assert doc["type"] == "doc"
        assert doc["content"] == []

    def test_paragraph(self):
        doc = self._parse("Hello world")
        paras = [n for n in doc["content"] if n["type"] == "paragraph"]
        assert len(paras) >= 1
        texts = [c["text"] for c in paras[0]["content"] if c["type"] == "text"]
        assert "Hello world" in texts


# ── Markdown → ProseMirror autolinks (#49) ───────────────────────────────────


def _link_marks(inline_nodes: list[dict]) -> list[dict]:
    """Pull every `link` mark off a list of inline ProseMirror nodes."""
    return [m for n in inline_nodes for m in n.get("marks", []) if m.get("type") == "link"]


def _link_hrefs(inline_nodes: list[dict]) -> list[str]:
    return [m.get("attrs", {}).get("href", "") for m in _link_marks(inline_nodes)]


class TestMarkdownAutolinks:
    """Bare ``https://...`` URLs should each become a ProseMirror link mark.

    Regression for #49: previously only the first URL in a pasted body was
    linked; the rest stayed as plain text.
    """

    def _inline(self, md: str) -> list[dict]:
        doc = json.loads(markdown_to_prosemirror(md))
        paras = [n for n in doc["content"] if n["type"] == "paragraph"]
        # Flatten inline content from every paragraph into one list.
        return [c for p in paras for c in p.get("content", [])]

    def test_single_bare_url_becomes_link(self):
        inline = self._inline("see https://example.com please")
        hrefs = _link_hrefs(inline)
        assert hrefs == ["https://example.com"]
        # Surrounding text is preserved.
        all_text = "".join(n.get("text", "") for n in inline)
        assert all_text == "see https://example.com please"

    def test_two_urls_on_same_line_both_linked(self):
        # Mirrors the bug's exact " | " separator shape.
        md = "Subject: A | link: https://a.example.com/x | link: https://b.example.com/y"
        inline = self._inline(md)
        assert _link_hrefs(inline) == [
            "https://a.example.com/x",
            "https://b.example.com/y",
        ]

    def test_three_urls_across_lines_all_linked(self):
        md = (
            "- Subject: A | Gmail link: https://mail.google.com/mail/#all/19d91c48eb9ff376\n"
            "- Subject: B | Gmail link: https://mail.google.com/mail/#all/19d8f9739e371daf\n"
            "- Subject: C | Gmail link: https://mail.google.com/mail/#all/19d8c8389dde5065\n"
        )
        doc = json.loads(markdown_to_prosemirror(md))
        # Each line becomes a bullet listItem; flatten all link hrefs from all items.
        bullet = next(n for n in doc["content"] if n["type"] == "bulletList")
        all_hrefs: list[str] = []
        for item in bullet["content"]:
            for para in item["content"]:
                if para.get("type") == "paragraph":
                    all_hrefs.extend(_link_hrefs(para["content"]))
        assert all_hrefs == [
            "https://mail.google.com/mail/#all/19d91c48eb9ff376",
            "https://mail.google.com/mail/#all/19d8f9739e371daf",
            "https://mail.google.com/mail/#all/19d8c8389dde5065",
        ]

    def test_trailing_period_not_part_of_href(self):
        inline = self._inline("Visit https://example.com.")
        assert _link_hrefs(inline) == ["https://example.com"]
        all_text = "".join(n.get("text", "") for n in inline)
        assert all_text.endswith(".")

    def test_trailing_comma_not_part_of_href(self):
        inline = self._inline("see https://a.example.com, then https://b.example.com")
        assert _link_hrefs(inline) == [
            "https://a.example.com",
            "https://b.example.com",
        ]

    def test_unbalanced_closing_paren_not_part_of_href(self):
        # "(see https://example.com)" — the trailing ')' belongs to the prose.
        inline = self._inline("(see https://example.com)")
        assert _link_hrefs(inline) == ["https://example.com"]
        all_text = "".join(n.get("text", "") for n in inline)
        assert all_text == "(see https://example.com)"

    def test_balanced_parens_kept_in_href(self):
        # Wikipedia-style URLs with balanced parens are preserved verbatim.
        inline = self._inline("ref: https://en.wikipedia.org/wiki/Foo_(bar)")
        assert _link_hrefs(inline) == ["https://en.wikipedia.org/wiki/Foo_(bar)"]

    def test_explicit_markdown_link_still_uses_label(self):
        # `[click](url)` must NOT be misparsed as a bare URL — the label must win.
        inline = self._inline("[click](https://example.com)")
        link_nodes = [n for n in inline if _link_marks([n])]
        assert len(link_nodes) == 1
        assert link_nodes[0]["text"] == "click"
        assert _link_hrefs(inline) == ["https://example.com"]

    def test_http_scheme_also_autolinked(self):
        inline = self._inline("see http://example.com here")
        assert _link_hrefs(inline) == ["http://example.com"]

    def test_bare_url_round_trips_back_to_bare_url(self):
        # Markdown → ProseMirror → Markdown should keep "https://x.com" as-is,
        # not expand it to "[https://x.com](https://x.com)".
        md = "see https://example.com here"
        pm_json = markdown_to_prosemirror(md)
        back = prosemirror_to_markdown(pm_json)
        assert "https://example.com" in back
        assert "[https://example.com]" not in back


# ── Markdown → ProseMirror tables (#42) ──────────────────────────────────────


class TestMarkdownTableParsing:
    """GFM pipe tables should parse into ProseMirror `table` nodes."""

    def _parse(self, md: str) -> dict:
        return json.loads(markdown_to_prosemirror(md))

    def test_basic_table_produces_table_node(self):
        md = "| Category | Status |\n| --- | --- |\n| Schedule | Green |"
        doc = self._parse(md)
        tables = [n for n in doc["content"] if n["type"] == "table"]
        assert len(tables) == 1, f"expected one table node, got {doc['content']}"

    def test_first_row_is_header_body_rows_are_cells(self):
        md = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
        doc = self._parse(md)
        table = next(n for n in doc["content"] if n["type"] == "table")
        rows = table["content"]
        assert len(rows) == 3  # 1 header + 2 body (alignment row consumed)
        header_row = rows[0]
        assert all(c["type"] == "tableHeader" for c in header_row["content"])
        for body_row in rows[1:]:
            assert all(c["type"] == "tableCell" for c in body_row["content"])

    def test_cells_contain_paragraph_with_text(self):
        md = "| Hello |\n| --- |\n| World |"
        doc = self._parse(md)
        table = next(n for n in doc["content"] if n["type"] == "table")
        header_cell = table["content"][0]["content"][0]
        assert header_cell["content"][0]["type"] == "paragraph"
        assert header_cell["content"][0]["content"][0]["text"] == "Hello"
        body_cell = table["content"][1]["content"][0]
        assert body_cell["content"][0]["type"] == "paragraph"
        assert body_cell["content"][0]["content"][0]["text"] == "World"

    def test_cells_have_default_colspan_rowspan(self):
        md = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        doc = self._parse(md)
        table = next(n for n in doc["content"] if n["type"] == "table")
        for row in table["content"]:
            for cell in row["content"]:
                assert cell["attrs"] == {"colspan": 1, "rowspan": 1}

    def test_alignment_row_with_colons_consumed(self):
        md = "| A | B |\n| :--- | ---: |\n| 1 | 2 |"
        doc = self._parse(md)
        table = next(n for n in doc["content"] if n["type"] == "table")
        # alignment row is not stored as a tableRow
        assert len(table["content"]) == 2
        assert all(c["type"] == "tableHeader" for c in table["content"][0]["content"])

    def test_cell_inline_marks_preserved(self):
        md = "| Name |\n| --- |\n| **bold** |"
        doc = self._parse(md)
        table = next(n for n in doc["content"] if n["type"] == "table")
        body_cell = table["content"][1]["content"][0]
        inline = body_cell["content"][0]["content"]
        bold = [n for n in inline if any(m["type"] == "bold" for m in n.get("marks", []))]
        assert len(bold) == 1
        assert bold[0]["text"] == "bold"

    def test_table_with_escaped_pipe(self):
        md = "| Col |\n| --- |\n| a \\| b |"
        doc = self._parse(md)
        table = next(n for n in doc["content"] if n["type"] == "table")
        body_cell = table["content"][1]["content"][0]
        text = body_cell["content"][0]["content"][0]["text"]
        assert text == "a | b"

    def test_round_trip_markdown_to_pm_to_markdown(self):
        """Markdown table → ProseMirror → Markdown preserves structure."""
        md = "| Category | Status | Notes |\n| --- | --- | --- |\n| Schedule | Green | ok |\n| Scope | Green | none |"
        pm_json = markdown_to_prosemirror(md)
        back = prosemirror_to_markdown(pm_json)
        # Header row preserved
        assert "| Category | Status | Notes |" in back
        # Alignment row preserved
        assert "| --- | --- | --- |" in back
        # Body rows preserved
        assert "| Schedule | Green | ok |" in back
        assert "| Scope | Green | none |" in back

    def test_round_trip_exact_equality_after_strip(self):
        md = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        pm_json = markdown_to_prosemirror(md)
        back = prosemirror_to_markdown(pm_json).strip()
        assert back == md.strip()

    def test_table_followed_by_paragraph(self):
        md = "| A | B |\n| --- | --- |\n| 1 | 2 |\n\nBelow the table."
        doc = self._parse(md)
        types = [n["type"] for n in doc["content"]]
        assert "table" in types
        # Paragraph after table still present
        paras = [n for n in doc["content"] if n["type"] == "paragraph"]
        all_text = "".join(c.get("text", "") for p in paras for c in p.get("content", []))
        assert "Below the table." in all_text

    def test_non_table_markdown_unchanged(self):
        """Regression guard: bullets, bold, links, headings still work after table support."""
        md = "## Heading\n\n- item\n- **bold** item\n- [link](https://example.com)\n\nPlain text."
        doc = self._parse(md)
        # Heading
        headings = [n for n in doc["content"] if n["type"] == "heading"]
        assert len(headings) == 1
        # Bullet list
        lists = [n for n in doc["content"] if n["type"] == "bulletList"]
        assert len(lists) == 1
        assert len(lists[0]["content"]) == 3
        # Bold
        items = lists[0]["content"]
        bold_item_inline = items[1]["content"][0]["content"]
        assert any(any(m["type"] == "bold" for m in n.get("marks", [])) for n in bold_item_inline)
        # Link
        link_item_inline = items[2]["content"][0]["content"]
        link_marks = [
            m for n in link_item_inline for m in n.get("marks", []) if m["type"] == "link"
        ]
        assert len(link_marks) == 1
        # Plain paragraph
        paras = [n for n in doc["content"] if n["type"] == "paragraph"]
        plain = "".join(c.get("text", "") for p in paras for c in p.get("content", []))
        assert "Plain text." in plain

    def test_no_table_when_separator_missing(self):
        """A single | row without a --- separator must not be interpreted as a table."""
        md = "| not | a | table |"
        doc = self._parse(md)
        assert not any(n["type"] == "table" for n in doc["content"])
        # Falls back to paragraph
        assert any(n["type"] == "paragraph" for n in doc["content"])

    def test_pipe_in_plain_text_not_promoted_to_table(self):
        """A standalone paragraph containing | must remain a paragraph."""
        md = "Hello | world"
        doc = self._parse(md)
        assert not any(n["type"] == "table" for n in doc["content"])

    def test_uneven_rows_padded_by_round_trip(self):
        """A row with fewer cells than the header is tolerated; round-trip pads cells."""
        md = "| A | B |\n| --- | --- |\n| 1 |"
        pm_json = markdown_to_prosemirror(md)
        back = prosemirror_to_markdown(pm_json)
        # The parser emits one body cell; the renderer pads to column count.
        assert "| A | B |" in back
        assert "| 1 |  |" in back
