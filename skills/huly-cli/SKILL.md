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
huly --help
```

Interpretation:

- if `huly --help` works, the installed-package flow is available
- if `huly` is missing but the user is inside this repository, prefer
  `uv run huly ...`
- if neither is available, install `huly-cli` from PyPI or set up the repo

### 1. Choose the install mode

If the user only wants to use the CLI, prefer the published package:

```bash
pip install huly-cli
huly --help
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

Current implemented command groups:

- `auth`
- `projects`
- `issues`
- `documents`
- `components`
- `milestones`
- `templates`
- `members`
- `labels`

Current live-validated CRUD coverage:

- issues: create, get, describe, update, delete
- documents: create, get, describe, update, delete
- components: create, get, update, delete
- milestones: create, get, update, delete
- templates: list, get, describe, set description

### 5. Use repo facts when relevant

This repo currently targets Huly platform `v0.6.504`.

If operating from a clone of this repository:

- main human docs: `README.md`
- release docs: `RELEASE.md`
- live smoke runner: `scripts/live_smoke.py`

For concrete commands and a compact usage cookbook, read
`references/usage.md`.
