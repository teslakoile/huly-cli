"""Auth commands: login, login-otp, status."""

from __future__ import annotations

import asyncio
import sys
from typing import Annotated

import typer

from huly_cli.auth import check_auth_status, login, login_otp, send_otp
from huly_cli.config import load_config, save_config
from huly_cli.errors import AuthError
from huly_cli.output import print_error, print_item, print_success

app = typer.Typer(help="Authentication commands.", no_args_is_help=True)


@app.command("login")
def auth_login(
    ctx: typer.Context,
    email: Annotated[
        str | None,
        typer.Option("--email", "-e", help="Huly account email.", envvar="HULY_EMAIL"),
    ] = None,
    password: Annotated[
        str | None,
        typer.Option(
            "--password",
            "-p",
            help="Huly account password.",
            envvar="HULY_PASSWORD",
        ),
    ] = None,
) -> None:
    """Log in to Huly and cache authentication tokens."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    # Resolve email
    resolved_email = email or config.email
    if not resolved_email:
        if sys.stdin.isatty():
            resolved_email = typer.prompt("Email")
        else:
            raise AuthError("Email required. Set --email or HULY_EMAIL env var.")

    # Resolve password
    resolved_password = password or config.password
    if not resolved_password:
        if sys.stdin.isatty():
            resolved_password = typer.prompt("Password", hide_input=True)
        else:
            raise AuthError("Password required. Set --password or HULY_PASSWORD env var.")

    # Resolve workspace
    if not config.workspace:
        if sys.stdin.isatty():
            config.workspace = typer.prompt("Workspace slug")
        else:
            raise AuthError("Workspace required. Set HULY_WORKSPACE env var.")

    config.email = resolved_email
    config.password = resolved_password

    try:
        auth = asyncio.run(login(config))
    except AuthError as e:
        print_error(e.message)
        raise typer.Exit(2) from e
    except Exception as e:
        print_error(f"Login failed: {e}")
        raise typer.Exit(1) from e

    save_config(config)
    print_success(
        f"Logged in as [bold]{auth.email}[/bold] to workspace [bold]{auth.workspace_slug}[/bold]"
    )


@app.command("login-otp")
def auth_login_otp(
    ctx: typer.Context,
    email: Annotated[
        str | None,
        typer.Option("--email", "-e", help="Huly account email.", envvar="HULY_EMAIL"),
    ] = None,
    code: Annotated[
        str | None,
        typer.Option("--code", "-c", help="OTP code from email."),
    ] = None,
) -> None:
    """Log in via email OTP code. Sends a code to your email, then validates it."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    # Resolve email
    resolved_email = email or config.email
    if not resolved_email:
        if sys.stdin.isatty():
            resolved_email = typer.prompt("Email")
        else:
            raise AuthError("Email required. Set --email or HULY_EMAIL env var.")

    # Resolve workspace
    if not config.workspace:
        if sys.stdin.isatty():
            config.workspace = typer.prompt("Workspace slug")
        else:
            raise AuthError("Workspace required. Set HULY_WORKSPACE env var.")

    config.email = resolved_email

    if not code:
        # Send OTP, then prompt for code
        try:
            asyncio.run(send_otp(config))
        except AuthError as e:
            print_error(e.message)
            raise typer.Exit(2) from e

        typer.echo(f"OTP code sent to {config.email}")
        if sys.stdin.isatty():
            code = typer.prompt("Code")
        else:
            raise AuthError("OTP code required. Pass --code.")

    try:
        auth = asyncio.run(login_otp(config, code))
    except AuthError as e:
        print_error(e.message)
        raise typer.Exit(2) from e
    except Exception as e:
        print_error(f"OTP login failed: {e}")
        raise typer.Exit(1) from e

    save_config(config)
    print_success(
        f"Logged in as [bold]{auth.email}[/bold] to workspace [bold]{auth.workspace_slug}[/bold]"
    )


@app.command("status")
def auth_status(ctx: typer.Context) -> None:
    """Show current authentication status."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    result = asyncio.run(check_auth_status(config))
    print_item(result, title="Auth Status")
