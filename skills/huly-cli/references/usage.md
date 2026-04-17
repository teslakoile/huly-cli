# Huly CLI usage reference

## Detect whether it is already installed

Try the executable first:

```bash
huly --version
```

If that fails and you are inside a source checkout, use:

```bash
uv run huly --version
```

## Install modes

### PyPI install (recommended: pipx)

```bash
pipx install huly-cli
huly --help
```

Upgrade:

```bash
pipx upgrade huly-cli
# or from within the CLI:
huly upgrade
```

### PyPI install (pip)

Use when `pipx` is not available:

```bash
pip install huly-cli
huly --help
```

Upgrade:

```bash
pip install --upgrade huly-cli
```

If `huly` is not found after installing, the install directory is likely not on
`PATH`. The most common fix:

```bash
# macOS / Linux — add to shell profile (~/.zshrc, ~/.bashrc):
export PATH="$HOME/.local/bin:$PATH"

# Or use pipx which handles PATH automatically:
pipx install huly-cli
```

### Source checkout

Use when the user is working in this repository:

```bash
uv sync --extra dev
uv run huly --help
```

## Auth setup

Required environment:

```bash
HULY_URL=https://your-huly-host
HULY_WORKSPACE=your-workspace-slug
```

Optional for non-interactive login or automatic re-auth:

```bash
HULY_EMAIL=you@example.com
HULY_PASSWORD=your-password
```

Interactive login:

```bash
huly auth login
huly auth status
```

Repo-local:

```bash
uv run huly auth login
uv run huly auth status
```

If the skill is guiding a user who installed from PyPI, prefer `huly ...`.
If the skill is guiding a user inside this repo, prefer `uv run huly ...`.

## Quick smoke checks

Minimal:

```bash
huly auth status
huly projects list
```

Repo-local read-only smoke:

```bash
uv run python scripts/live_smoke.py
```

Repo-local CRUD smoke with cleanup:

```bash
uv run python scripts/live_smoke.py --allow-writes
```

## Common command patterns

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

# Create with all options
huly issues create --project DEMO --title "Fix login bug" \
  --priority high --status todo --assignee "Jane" \
  --due-date 2025-06-01 --component "Auth" --label "bug" \
  --description "Detailed markdown description here"

# Update
huly issues update DEMO-1 --title "Updated title" --status done
huly issues update DEMO-1 --due-date 2025-07-01 --component "API"
huly issues update DEMO-1 --label "sprint-3"
huly issues update DEMO-1 --assignee ""  # unassign
huly issues update DEMO-1 --due-date ""  # clear due date
huly issues update DEMO-1 --component "" # unset component

# Read/write descriptions
huly issues describe DEMO-1
huly issues describe DEMO-1 --raw  # raw ProseMirror JSON
huly issues describe DEMO-1 --set "## New description"
huly issues describe DEMO-1 --set-file ./description.md

# Delete
huly issues delete DEMO-1
```

### Documents

```bash
huly documents list --space "Engineering" --limit 5
huly documents create --space "Engineering" --title "Design Doc"
huly documents describe DOC_ID --set "# Content here"
huly documents describe DOC_ID --set-file ./doc.md
huly documents update DOC_ID --title "Updated title"
huly documents delete DOC_ID
```

### Components

```bash
huly components list --project DEMO --limit 5
huly components create --project DEMO --label "Auth Service" --description "Handles auth"
huly components update COMPONENT_ID --label "Renamed" --description "Updated"
huly components delete COMPONENT_ID
```

### Milestones

```bash
huly milestones list --project DEMO --limit 5
huly milestones create --project DEMO --label "v1.0" --status planned --target-date 2025-06-01
huly milestones update MILESTONE_ID --status completed
huly milestones delete MILESTONE_ID
```

### Labels

```bash
huly labels list
huly labels get LABEL_ID
huly labels create --title "bug" --color 1
huly labels update LABEL_ID --title "critical-bug"
huly labels delete LABEL_ID
```

### Templates

```bash
huly templates list --project DEMO --limit 5
huly templates get TEMPLATE_ID
huly templates describe TEMPLATE_ID
huly templates describe TEMPLATE_ID --set "Updated template description"
```

### Members

```bash
huly members list
```

## Output mode

Prefer JSON for agent workflows:

```bash
huly --json projects list
huly --json issues get DEMO-1
huly --json issues describe DEMO-1
```

## Troubleshooting

- Install package name: `huly-cli`
- Executable name: `huly`
- Workspace slug is not the same thing as a project identifier
- If cached auth expires, ensure `HULY_EMAIL` and `HULY_PASSWORD` are available
- In this repo, prefer `uv run huly ...` over invoking `huly` directly
- Use `huly upgrade` to self-update to the latest PyPI release
