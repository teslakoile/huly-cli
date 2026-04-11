"""Members commands: list."""

from __future__ import annotations

import asyncio
from typing import Any

import typer

from huly_cli.client import HulyClient
from huly_cli.config import load_config
from huly_cli.errors import AuthError, HulyError
from huly_cli.models import Person, PersonAccount
from huly_cli.output import print_error, print_list

app = typer.Typer(help="Manage workspace members.", no_args_is_help=True)


@app.command("list")
def members_list(ctx: typer.Context) -> None:
    """List workspace members with emails."""
    overrides: dict = ctx.obj or {}
    config = load_config(
        url_override=overrides.get("url"),
        workspace_override=overrides.get("workspace"),
    )

    async def _run() -> list[dict[str, Any]]:
        from huly_cli.auth import ensure_auth

        auth = await ensure_auth(config)
        async with HulyClient(config, auth) as client:
            raw_persons = await client.find_all("contact:class:Person", options={"limit": 500})
            raw_accounts = await client.find_all(
                "contact:class:PersonAccount", options={"limit": 500}
            )

        persons = [Person.model_validate(doc) for doc in raw_persons]
        accounts = [PersonAccount.model_validate(doc) for doc in raw_accounts]

        # Build map from person._id → email (from PersonAccount)
        person_email: dict[str, str] = {}
        for acc in accounts:
            if acc.person and acc.email:
                # Keep first email found per person
                person_email.setdefault(acc.person, acc.email)

        rows: list[dict[str, Any]] = []
        for person in sorted(persons, key=lambda p: p.display_name):
            rows.append(
                {
                    "name": person.display_name,
                    "email": person_email.get(person.id, ""),
                    "id": person.id,
                }
            )
        return rows

    try:
        rows = asyncio.run(_run())
    except AuthError as e:
        print_error(e.message, hint="Run 'huly auth login' to authenticate.")
        raise typer.Exit(2) from e
    except HulyError as e:
        print_error(e.message)
        raise typer.Exit(1) from e

    print_list(rows, columns=["name", "email", "id"], title="Members")
