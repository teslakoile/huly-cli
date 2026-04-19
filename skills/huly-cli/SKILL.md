---
name: huly-cli
description: Use this skill when a user needs to install, configure, authenticate, smoke-test, or operate the huly-cli package from PyPI or from this repository. It covers package installation, source-checkout usage, login and env setup, validation, and the implemented command surfaces for projects, issues, documents, components, milestones, templates, members, and labels.
---

# Huly CLI

## Overview

This skill helps an agent get `huly-cli` working from either a PyPI install or a
source checkout, then use the CLI safely and predictably.

Use this skill for:

- installing `huly-cli`
- deciding between PyPI usage and repo-local development usage
- configuring auth and environment variables
- running smoke checks
- operating the supported CLI surfaces

## Workflow

### 0. Detect whether the CLI is already available

Check whether the executable is already present before giving install steps:

```bash
huly --version
```

Interpretation:

- if `huly --version` works, the installed-package flow is available
- if `huly` is missing but the user is inside this repository, prefer
  `uv run huly ...`
- if neither is available, install `huly-cli` from PyPI or set up the repo

### 1. Choose the install mode

If the user only wants to use the CLI, prefer the published package:

```bash
pipx install huly-cli
huly --help
```

If `pipx` is not available:

```bash
pip install huly-cli
```

If `huly` is not found after installing, the install directory may not be on
`PATH`. Suggest:

```bash
# Add pip's user bin to PATH (macOS / Linux):
export PATH="$HOME/.local/bin:$PATH"
# Or use pipx which handles PATH automatically:
pipx install huly-cli
```

If the user is working inside this repository or needs the unreleased source
version, prefer the repo-local flow:

```bash
uv sync --extra dev
uv run huly --help
```

Rule:

- installed package: use `huly ...`
- source checkout: use `uv run huly ...`

Do not tell users to run `pip install huly cli`. The package name is
`huly-cli` and the executable is `huly`.

### 2. Configure authentication

Required config:

- `HULY_URL`
- `HULY_WORKSPACE`

Optional but useful for non-interactive login or token refresh:

- `HULY_EMAIL`
- `HULY_PASSWORD`

The simplest local auth flow is:

```bash
huly auth login
huly auth status
```

or in a repo checkout:

```bash
uv run huly auth login
uv run huly auth status
```

Important distinction:

- workspace slug and project identifier are not the same thing
- example: workspace `my-ws`, project `DEMO`

### 3. Validate the installation

Start with:

```bash
huly auth status
huly projects list
```

If the user is in a repo checkout, use the repo-local executable instead:

```bash
uv run huly auth status
uv run huly projects list
```

If you are in the repo, prefer the bundled smoke runner:

```bash
uv run python scripts/live_smoke.py
```

Only use write-mode smoke checks when disposable data is acceptable:

```bash
uv run python scripts/live_smoke.py --allow-writes
```

The write-mode smoke runner creates and cleans up temporary issues, documents,
components, and milestones.

### 4. Operate the CLI

Prefer `--json` when an agent needs stable machine-readable output.

Agent-friendly read paths for document content:

- `huly documents describe DOC_ID --markdown` — plain GFM to stdout, no Rich
  box and no reflow. Preferred over the default rendered output when the agent
  will diff, grep, or re-emit the content. Also safe to pipe into
  `--set-file` for round-trips.
- `huly documents describe DOC_ID --raw` — raw ProseMirror JSON (structural,
  not line-diffable).
- `huly documents describe DOC_ID` (no flag) — rendered Rich panel, for humans.

`--raw` and `--markdown` are mutually exclusive.

ID columns in list output (`huly documents list`, `huly components list`, etc.)
always show the full ID — agents can copy values directly into follow-up
`huly ... get <ID>` calls without re-querying with `--json`.

Current implemented command groups:

- `auth` — login, status
- `projects` — list, get
- `issues` — list, get, create, update, delete, describe
- `documents` — list, get, create, update, delete, describe
- `components` — list, get, create, update, delete
- `milestones` — list, get, create, update, delete
- `templates` — list, get, describe (read/write)
- `labels` — list, get, create, update, delete
- `members` — list
- `upgrade` — self-upgrade from PyPI

Current live-validated CRUD coverage:

| Command      | list | get | create | update | delete | describe |
|--------------|:----:|:---:|:------:|:------:|:------:|:--------:|
| projects     |  x   |  x  |        |        |        |          |
| issues       |  x   |  x  |   x    |   x    |   x    |    x     |
| documents    |  x   |  x  |   x    |   x    |   x    |    x     |
| components   |  x   |  x  |   x    |   x    |   x    |          |
| milestones   |  x   |  x  |   x    |   x    |   x    |          |
| templates    |  x   |  x  |        |        |        |    x     |
| labels       |  x   |  x  |   x    |   x    |   x    |          |
| members      |  x   |     |        |        |        |          |

Issue-specific fields supported on create/update:

- `--priority` — name or number
- `--status` — name or id (resolves against live workspace index)
- `--assignee` — fuzzy name match
- `--due-date` — YYYY-MM-DD format (use "" to clear on update)
- `--component` — name or ID (use "" to unset on update)
- `--label` — repeatable flag to attach labels
- `--description` — markdown text (create only)

### 5. Use repo facts when relevant

If operating from a clone of this repository:

- main human docs: `README.md`
- release docs: `RELEASE.md`
- live smoke runner: `scripts/live_smoke.py`

For concrete commands and a compact usage cookbook, read
`references/usage.md`.
