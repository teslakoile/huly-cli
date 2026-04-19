"""Entry point for Huly CLI."""

from __future__ import annotations

from typing import Annotated

import typer

from huly_cli import __version__
from huly_cli.commands import (
    auth_cmd,
    components,
    documents,
    issues,
    labels,
    members,
    milestones,
    projects,
    search,
    templates,
)
from huly_cli.commands import upgrade as upgrade_cmd
from huly_cli.errors import HulyError, handle_error
from huly_cli.output import set_json_mode

app = typer.Typer(
    name="huly",
    help="CLI for Huly project management.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

app.add_typer(auth_cmd.app, name="auth")
app.add_typer(projects.app, name="projects")
app.add_typer(issues.app, name="issues")
app.add_typer(members.app, name="members")
app.add_typer(labels.app, name="labels")
app.add_typer(documents.app, name="documents")
app.add_typer(components.app, name="components")
app.add_typer(milestones.app, name="milestones")
app.add_typer(templates.app, name="templates")
app.command(
    "search",
    help="Fulltext search across the workspace (issues, documents, templates, ...).",
)(search.search)
app.command("upgrade", help="Upgrade huly-cli to the latest version from PyPI.")(
    upgrade_cmd.upgrade
)


def _version_callback(value: bool) -> None:
    if value:
        print(f"huly-cli {__version__}")
        raise typer.Exit()


@app.callback()
def global_callback(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON.", is_eager=False),
    ] = False,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Huly server URL.", envvar="HULY_URL"),
    ] = None,
    workspace: Annotated[
        str | None,
        typer.Option("--workspace", "-w", help="Workspace slug.", envvar="HULY_WORKSPACE"),
    ] = None,
) -> None:
    """Huly CLI — interact with your Huly workspace from the terminal."""
    if json_output:
        set_json_mode(True)
    ctx.ensure_object(dict)
    if url:
        ctx.obj["url"] = url
    if workspace:
        ctx.obj["workspace"] = workspace


def main() -> None:
    try:
        app()
    except HulyError as e:
        handle_error(e)


if __name__ == "__main__":
    main()
