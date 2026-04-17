# huly-cli

Python CLI for interacting with a Huly workspace from the terminal.

## Features

Full CRUD support for the core Huly entities:

| Command       | list | get | create | update | delete | describe |
|---------------|:----:|:---:|:------:|:------:|:------:|:--------:|
| `projects`    |  x   |  x  |        |        |        |          |
| `issues`      |  x   |  x  |   x    |   x    |   x    |    x     |
| `documents`   |  x   |  x  |   x    |   x    |   x    |    x     |
| `components`  |  x   |  x  |   x    |   x    |   x    |          |
| `milestones`  |  x   |  x  |   x    |   x    |   x    |          |
| `templates`   |  x   |  x  |        |        |        |    x     |
| `labels`      |  x   |  x  |   x    |   x    |   x    |          |
| `members`     |  x   |     |        |        |        |          |

Additional capabilities:

- **Issue descriptions & document content**: read and write rich-text content
  via the Collaborator RPC. Markdown is converted to/from ProseMirror JSON
  automatically.
- **Issue fields**: priority, status, assignee, due date, component, and labels
  (repeatable `--label` flag on create/update)
- **Status filtering**: `issues list --status <name>` resolves against the live
  workspace status index, supporting custom statuses
- **JSON mode**: `huly --json <command>` for machine-readable output
- **Self-upgrade**: `huly upgrade` to update from PyPI
- **Shell completion**: `huly --install-completion`

## Prerequisites

- Python `3.11+`
- [`uv`](https://docs.astral.sh/uv/) (only needed for source-checkout development)
- A Huly account with access to the target workspace

## Install

### Option 1: Install from PyPI

The package name is `huly-cli`. The executable is `huly`.

#### Recommended: `pipx` (standalone CLI install)

[`pipx`](https://pipx.pypa.io/) creates an isolated environment per tool and
puts the executable on `PATH` automatically.

```bash
pipx install huly-cli
huly --help
```

Upgrade:

```bash
pipx upgrade huly-cli
# or: huly upgrade
```

#### Alternative: `pip` (virtualenv or CI)

```bash
pip install huly-cli
```

### Option 2: Use from a source checkout

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

4. Run commands with `uv run huly` instead of `huly`.

## Environment Variables

The CLI loads config in this order:

1. CLI flags (`--url`, `--workspace`)
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

The token cache is reused automatically. If the cached token expires, the CLI
needs `HULY_EMAIL` and `HULY_PASSWORD` available to re-authenticate.

## Login

> **Source checkout?** Replace `huly` below with `uv run huly`.

### Interactive login

```bash
huly --url https://huly.example.com --workspace my-ws auth login
```

You will be prompted for email and password. Then confirm:

```bash
huly auth status
```

### Login using `.env`

Put all four values in `.env`:

```bash
HULY_URL=https://huly.example.com
HULY_WORKSPACE=my-ws
HULY_EMAIL=you@example.com
HULY_PASSWORD=your-password
```

Then run:

```bash
huly auth login
huly auth status
```

## Usage Examples

### Projects

```bash
huly projects list
huly projects get DEMO
```

### Issues

```bash
# List and filter
huly issues list --project DEMO --limit 10
huly issues list --status backlog --assignee john

# Create
huly issues create --project DEMO --title "Fix login bug" \
  --priority high --status todo --assignee "Jane" \
  --due-date 2025-06-01 --component "Auth" --label "bug"

# Update
huly issues update DEMO-1 --status done --priority low
huly issues update DEMO-1 --due-date 2025-07-01 --component "API"
huly issues update DEMO-1 --label "sprint-3"

# Read/write descriptions
huly issues describe DEMO-1
huly issues describe DEMO-1 --set "## Updated description"
huly issues describe DEMO-1 --set-file ./description.md
huly issues describe DEMO-1 --raw  # show ProseMirror JSON

# Delete
huly issues delete DEMO-1
```

### Documents

```bash
huly documents list --space "Engineering"
huly documents create --space "Engineering" --title "Design Doc"
huly documents describe DOC_ID --set "# Design\n\nContent here."
huly documents describe DOC_ID --set-file ./doc.md
huly documents update DOC_ID --title "Updated Title"
huly documents delete DOC_ID
```

### Components

```bash
huly components list --project DEMO
huly components create --project DEMO --label "Auth Service" --description "Handles auth"
huly components update COMP_ID --label "Renamed" --description "Updated"
huly components delete COMP_ID
```

### Milestones

```bash
huly milestones list --project DEMO
huly milestones create --project DEMO --label "v1.0" --status planned --target-date 2025-06-01
huly milestones update MS_ID --status completed
huly milestones delete MS_ID
```

### Labels

```bash
huly labels list
huly labels create --title "bug" --color 1
huly labels update LABEL_ID --title "critical-bug"
huly labels delete LABEL_ID
```

### Templates

```bash
huly templates list --project DEMO
huly templates get TEMPLATE_ID
huly templates describe TEMPLATE_ID
huly templates describe TEMPLATE_ID --set "## Template description"
```

### Members

```bash
huly members list
```

### JSON mode

```bash
huly --json projects list
huly --json issues list --project DEMO --limit 5
huly --json issues describe DEMO-1
```

## Smoke Testing

The repo includes an automated smoke runner:

```bash
uv run python scripts/live_smoke.py                  # read-only checks
uv run python scripts/live_smoke.py --allow-writes    # CRUD checks with cleanup
```

## Local Test Suite

```bash
uv run --extra dev pytest -q
```

## Packaging and PyPI

The package is published on PyPI as `huly-cli`.

```bash
pipx install huly-cli
```

Or with `pip` in a virtualenv or CI:

```bash
pip install huly-cli
```

For the maintainer release checklist, see [RELEASE.md](RELEASE.md).

## CLI Help

```bash
huly --help
huly issues --help
huly issues create --help
```

## License

MIT
