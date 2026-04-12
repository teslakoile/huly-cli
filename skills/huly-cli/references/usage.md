# Huly CLI usage reference

## Detect whether it is already installed

Try the executable first:

```bash
huly --help
```

If that fails and you are inside a source checkout, use:

```bash
uv run huly --help
```

## Install modes

### PyPI install

Use when the user just needs the tool:

```bash
pip install huly-cli
huly --help
```

Upgrade an existing PyPI install:

```bash
pip install --upgrade huly-cli
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
huly projects get ROA
```

### Issues

```bash
huly issues list --project ROA --limit 5
huly issues get ROA-1
huly issues describe ROA-1
huly issues create --project ROA --title "Example" --description "Example description"
huly issues update ROA-1 --title "Updated title" --status done
huly issues delete ROA-1
```

### Documents

```bash
huly documents list --limit 5
huly documents create --space "RoA - Staff Augmentation" --title "Example Doc"
huly documents describe DOC_ID --set "Example content"
huly documents update DOC_ID --title "Updated title"
huly documents delete DOC_ID
```

### Components

```bash
huly components list --project ROA --limit 5
huly components create --project ROA --label "Example Component"
huly components update COMPONENT_ID --label "Updated Component"
huly components delete COMPONENT_ID
```

### Milestones

```bash
huly milestones list --project ROA --limit 5
huly milestones create --project ROA --label "Example Milestone" --status planned
huly milestones update MILESTONE_ID --status completed
huly milestones delete MILESTONE_ID
```

### Templates

```bash
huly templates list --project ROA --limit 5
huly templates get TEMPLATE_ID
huly templates describe TEMPLATE_ID
huly templates describe TEMPLATE_ID --set "Updated description"
```

### Members and labels

```bash
huly members list
huly labels list
```

## Output mode

Prefer JSON for agent workflows:

```bash
huly --json projects list
huly --json issues get ROA-1
```

## Troubleshooting

- Install package name: `huly-cli`
- Executable name: `huly`
- Workspace slug is not the same thing as a project identifier
- If cached auth expires, ensure `HULY_EMAIL` and `HULY_PASSWORD` are available
- In this repo, prefer `uv run huly ...` over invoking `huly` directly
