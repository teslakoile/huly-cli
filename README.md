# huly-cli

Python CLI for interacting with a Huly workspace from the terminal.

## Status

This repo is currently a Python `typer` CLI, not a Node or `pnpm` project.

It has been checked against `hcengineering/platform@v0.6.504` and smoke-tested against
`https://huly.ingenuity.ph` workspace `efs`.

What is verified today:

- Authentication flow via `/_accounts`
- Read access for projects, issues, components, documents, templates, members, labels, and issue descriptions
- Live CRUD for issues, documents, components, and milestones on `https://huly.ingenuity.ph` workspace `efs`
- Live template description update and restore flow
- Workspace-specific issue status display and status filtering
- Local unit/CLI test suite
- CI-equivalent local checks:
  `uv sync --extra dev`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run pytest tests/ -v`, `uv run python -m build`, and `uv run twine check dist/*`

What is not fully verified yet:

- Automated live-workspace CI has not been added
- You should still prefer a disposable project or disposable teamspace for release-time live smoke tests

Known live compatibility gaps at the time of writing:

- No known read-path breakage remains from the `v0.6.504` comparison and smoke tests
- No known CLI CRUD gap remains on the currently implemented issue, document, component, and milestone surfaces
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

## Install

### Option 1: Install from PyPI

Use this if you only want the CLI and are not modifying the source:

```bash
pip install huly-cli
huly --help
```

Upgrade an existing install:

```bash
pip install --upgrade huly-cli
```

The package name is `huly-cli`. The executable is `huly`.

### Option 2: Use from a source checkout

Use this if you are developing in this repository:

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

If you installed from PyPI, replace `uv run huly` below with `huly`.

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

## Agent Skill

This repo includes a Codex skill for agents that need to install or operate the
CLI:

- skill path: `skills/huly-cli`
- explicit invocation: `$huly-cli`

If you want to install that skill into a Codex skills directory outside this
repo, copy or symlink it into `${CODEX_HOME:-$HOME/.codex}/skills`:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -s "$(pwd)/skills/huly-cli" "${CODEX_HOME:-$HOME/.codex}/skills/huly-cli"
```

If you prefer a copy instead of a symlink:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R skills/huly-cli "${CODEX_HOME:-$HOME/.codex}/skills/"
```

## Hands-On Smoke Test

These commands are the safest live checks to run today.

If you want the repo to drive the same smoke pass for you:

```bash
uv run python scripts/live_smoke.py
```

To include live CRUD checks with automatic cleanup:

```bash
uv run python scripts/live_smoke.py --allow-writes
```

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

The CLI write paths were exercised live during verification, but you should still
prefer a disposable project or disposable teamspace when doing release-time smoke
tests against a real workspace.

## Local Test Suite

Run the unit and CLI regression tests with:

```bash
uv run --extra dev pytest -q
```

Expected result at the time of verification:

- `155 passed`

## Packaging And PyPI

The package is published on PyPI as `huly-cli`.

Install it with:

```bash
pip install huly-cli
```

The repo also builds a wheel and sdist cleanly and CI validates the
distribution metadata.

For the maintainer release checklist and publisher configuration notes, see
[RELEASE.md](RELEASE.md).

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
