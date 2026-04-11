# huly-cli

Python CLI for interacting with a Huly workspace from the terminal.

## Status

This repo is currently a Python `typer` CLI, not a Node or `pnpm` project.

It has been checked against `hcengineering/platform@v0.6.504` and smoke-tested against
`https://huly.ingenuity.ph` workspace `efs`.

What is verified today:

- Authentication flow via `/_accounts`
- Read-only access for projects, issues, components, documents, templates, members, labels, and issue descriptions
- Workspace-specific issue status display and status filtering
- Local unit/CLI test suite
- CI-equivalent local checks:
  `uv sync --extra dev`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest tests/ -v`

What is not fully verified yet:

- Live write commands were not executed against the shared workspace
- Issue create/update semantics are aligned to the upstream client flow, but still only verified locally with mocked tests

Known live compatibility gaps at the time of writing:

- No known read-path breakage remains from the `v0.6.504` comparison and smoke tests
- Write paths should still be exercised in a disposable project before you rely on them for production changes
- The test suite now patches auth correctly; it no longer depends on a developer's local cached login state

## Compatibility Target

- Huly platform tag: `v0.6.504`
- Example workspace URL used during verification:
  `https://huly.ingenuity.ph/workbench/efs/tracker/69cb986a2df46a01935af670/issues`

Important distinction:

- `efs` is the workspace slug
- `ROA` is the project identifier in that workspace

If you run `huly issues list --project EFS`, it will fail because `EFS` is not a project ID.

## Prerequisites

- Python `3.11+`
- [`uv`](https://docs.astral.sh/uv/)
- A Huly account with access to the target workspace

## Setup

1. Install dependencies, including dev tools:

```bash
uv sync --extra dev
```

2. Copy the example environment file:

```bash
cp .env.example .env
```

3. Edit `.env` with at least:

- `HULY_URL`
- `HULY_WORKSPACE`

4. Choose one auth approach:

- Interactive login: preferred for local use
- Environment-based login: useful for non-interactive runs and token refresh

## Environment Variables

The CLI loads config in this order:

1. CLI flags
2. Environment variables
3. `.env` in the current directory
4. `~/.config/huly/config.toml`

Supported variables:

- `HULY_URL`
- `HULY_WORKSPACE`
- `HULY_EMAIL`
- `HULY_PASSWORD`

Auth cache location:

- Config: `~/.config/huly/config.toml`
- Tokens: `~/.config/huly/auth.json`

The token cache is reused automatically. If the cached token expires, the CLI needs
`HULY_EMAIL` and `HULY_PASSWORD` available in order to re-authenticate automatically.

## Login Walkthrough

### Option 1: Interactive login

This is the simplest flow if you are testing locally and do not want to keep your password
in `.env`.

```bash
uv run huly --url https://huly.ingenuity.ph --workspace efs auth login
```

You will be prompted for:

- Email
- Password
- Workspace slug, if it was not passed on the command line or set in `.env`

Then confirm auth is valid:

```bash
uv run huly auth status
```

### Option 2: Login using `.env`

Put all four values in `.env`:

```bash
HULY_URL=https://huly.ingenuity.ph
HULY_WORKSPACE=efs
HULY_EMAIL=you@example.com
HULY_PASSWORD=your-password
```

Then run:

```bash
uv run huly auth login
uv run huly auth status
```

## Hands-On Smoke Test

These commands are the safest live checks to run today.

1. Confirm auth:

```bash
uv run huly auth status
```

2. List projects:

```bash
uv run huly projects list
```

3. Inspect the verified sample project:

```bash
uv run huly projects get ROA
```

4. List a few issues from that project:

```bash
uv run huly issues list --project ROA --limit 5
```

5. Inspect one issue:

```bash
uv run huly issues get ROA-1
```

6. Read the issue description:

```bash
uv run huly issues describe ROA-1
```

7. List project components:

```bash
uv run huly components list --project ROA --limit 5
```

8. Inspect a component by internal ID:

```bash
uv run huly components get 16e202fa79377835295c79eb
```

9. List a few documents:

```bash
uv run huly documents list --limit 5
```

10. List issue templates:

```bash
uv run huly templates list --limit 5
```

11. Verify status filtering:

```bash
uv run huly issues list --status backlog --limit 5
```

12. List workspace members:

```bash
uv run huly members list
```

13. List labels:

```bash
uv run huly labels list
```

### JSON mode

If you want machine-readable output for quick inspection:

```bash
uv run huly --json projects list
uv run huly --json issues list --project ROA --limit 5
uv run huly --json auth status
```

## Commands That Currently Need Caution

Avoid treating the following as production-safe until you have exercised them in a disposable project:

- `huly issues create`
- `huly issues update`
- `huly issues describe --set ...`
- Any other create or update command against a real workspace

If you are doing live validation, stay on read-only commands first.

## Local Test Suite

Run the unit and CLI regression tests with:

```bash
uv run --extra dev pytest -q
```

Expected result at the time of verification:

- `146 passed`

## CLI Help

Top-level help:

```bash
uv run huly --help
```

Auth help:

```bash
uv run huly auth login --help
```

## License

MIT
