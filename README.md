# huly-cli

A command-line interface for interacting with [Huly](https://huly.io) project management — built for agents and humans alike.

## Overview

`huly-cli` provides terminal access to your Huly instance for managing issues, projects, and workflows. It supports both Huly Cloud and self-hosted instances.

### Features

- **Authentication** — Login, workspace selection, and token management
- **Issues** — List, create, update, and query issues with full filter support
- **Projects** — Browse projects and their configurations
- **Statuses & Labels** — View and manage workflow states and tags

## Prerequisites

- Node.js 18+
- A Huly account (cloud or self-hosted)

## Setup

```bash
# Install dependencies
pnpm install

# Build
pnpm build

# Login to your Huly instance
huly login --url https://your-instance.example.com
```

## Usage

```bash
# List issues in a project
huly issues list --project EFS

# Create a new issue
huly issues create --project EFS --title "Fix login bug" --priority urgent

# View issue details
huly issues get EFS-123
```

## License

MIT
