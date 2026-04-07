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
