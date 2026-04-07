"""Tests for output.py — dual-mode JSON + Rich output helpers."""

from __future__ import annotations

import json

from huly_cli.output import (
    is_json_mode,
    print_error,
    print_item,
    print_list,
    print_success,
    set_json_mode,
)


class TestJsonModeToggle:
    def setup_method(self):
        set_json_mode(False)

    def teardown_method(self):
        set_json_mode(False)

    def test_default_is_false(self):
        assert not is_json_mode()

    def test_set_true(self):
        set_json_mode(True)
        assert is_json_mode()

    def test_set_false(self):
        set_json_mode(True)
        set_json_mode(False)
        assert not is_json_mode()

    def test_toggle_idempotent(self):
        set_json_mode(True)
        set_json_mode(True)
        assert is_json_mode()


class TestPrintItemJson:
    def setup_method(self):
        set_json_mode(True)

    def teardown_method(self):
        set_json_mode(False)

    def test_basic(self, capsys):
        print_item({"key": "value"}, title="Test")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["data"]["key"] == "value"

    def test_nested_data(self, capsys):
        print_item({"a": 1, "b": [1, 2, 3]})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["data"]["a"] == 1
        assert data["data"]["b"] == [1, 2, 3]

    def test_empty_dict(self, capsys):
        print_item({})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["data"] == {}


class TestPrintListJson:
    def setup_method(self):
        set_json_mode(True)

    def teardown_method(self):
        set_json_mode(False)

    def test_basic(self, capsys):
        print_list([{"a": 1}, {"a": 2}], columns=["a"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert len(data["data"]) == 2

    def test_empty_list(self, capsys):
        print_list([], columns=["a", "b"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["data"] == []

    def test_preserves_all_fields(self, capsys):
        items = [{"name": "Alice", "email": "a@b.com"}, {"name": "Bob", "email": "b@c.com"}]
        print_list(items, columns=["name", "email"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["data"][0]["name"] == "Alice"
        assert data["data"][1]["email"] == "b@c.com"


class TestPrintSuccessJson:
    def setup_method(self):
        set_json_mode(True)

    def teardown_method(self):
        set_json_mode(False)

    def test_basic(self, capsys):
        print_success("done")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "ok"

    def test_message_included(self, capsys):
        print_success("operation complete")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["message"] == "operation complete"


class TestPrintErrorJson:
    def setup_method(self):
        set_json_mode(True)

    def teardown_method(self):
        set_json_mode(False)

    def test_basic(self, capsys):
        print_error("oops", hint="try again")
        captured = capsys.readouterr()
        data = json.loads(captured.err)
        assert data["ok"] is False
        assert "oops" in data["error"]

    def test_hint_included(self, capsys):
        print_error("error message", hint="helpful hint")
        captured = capsys.readouterr()
        data = json.loads(captured.err)
        assert data["hint"] == "helpful hint"

    def test_no_hint(self, capsys):
        print_error("bare error")
        captured = capsys.readouterr()
        data = json.loads(captured.err)
        assert data["ok"] is False
        assert data["error"] == "bare error"
        assert "hint" not in data

    def test_error_goes_to_stderr(self, capsys):
        print_error("err")
        captured = capsys.readouterr()
        # Should be on stderr, not stdout
        assert captured.out == ""
        assert captured.err != ""
