"""Output helpers for Huly CLI — supports human-readable and JSON modes."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Module-level JSON mode flag
_json_mode: bool = False

# Rich console — respects NO_COLOR env var
console = Console(no_color=bool(os.environ.get("NO_COLOR")))
err_console = Console(no_color=bool(os.environ.get("NO_COLOR")), stderr=True)


def set_json_mode(enabled: bool) -> None:
    global _json_mode
    _json_mode = enabled


def is_json_mode() -> bool:
    return _json_mode


def print_item(data: dict[str, Any], title: str = "") -> None:
    """Print a single item. JSON: envelope with data object. Human: Rich panel."""
    if _json_mode:
        print(json.dumps({"ok": True, "data": data}))
    else:
        from rich.pretty import Pretty

        if title:
            console.print(Panel(Pretty(data), title=title))
        else:
            console.print(Pretty(data))


def print_list(items: list[dict[str, Any]], columns: list[str], title: str = "") -> None:
    """Print a list of items. JSON: envelope with data array. Human: Rich table."""
    if _json_mode:
        print(json.dumps({"ok": True, "data": items}))
    else:
        table = Table(title=title or None, show_header=True, header_style="bold")
        for col in columns:
            table.add_column(col)
        for item in items:
            row = [str(item.get(col, "")) for col in columns]
            table.add_row(*row)
        console.print(table)


def print_success(message: str) -> None:
    """Print a success message. JSON: status envelope. Human: green text."""
    if _json_mode:
        print(json.dumps({"status": "ok", "message": message}))
    else:
        console.print(f"[bold green]✓[/bold green] {message}")


def print_error(message: str, hint: str | None = None) -> None:
    """Print an error message — ALWAYS to stderr."""
    if _json_mode:
        payload: dict[str, Any] = {"ok": False, "error": message}
        if hint:
            payload["hint"] = hint
        print(json.dumps(payload), file=sys.stderr)
    else:
        body = message
        if hint:
            body += f"\n\n[dim]{hint}[/dim]"
        err_console.print(Panel(body, title="[bold red]Error[/bold red]", border_style="red"))


def print_warning(message: str) -> None:
    """Print a warning — always to stderr."""
    if _json_mode:
        print(json.dumps({"warning": message}), file=sys.stderr)
    else:
        err_console.print(f"[bold yellow]⚠[/bold yellow]  {message}")
