# Release Guide

This repo is set up to publish `huly-cli` to PyPI using GitHub Actions Trusted
Publishing.

## Current release setup

- Builds a wheel and sdist with `python -m build`
- Validates package metadata with `twine check`
- Verifies packaging in CI
- Includes a publish workflow at
  `.github/workflows/publish-pypi.yml`
- Publishes the `huly-cli` package to PyPI through GitHub Actions Trusted
  Publishing

Key identifiers for this repo:

- PyPI project name: `huly-cli`
- Repository owner: `teslakoile`
- Repository name: `huly-cli`
- Workflow filename: `publish-pypi.yml`
- GitHub environment: `pypi`

## One-time checks

These are not normal per-release tasks. Revisit them only if you change the
repository owner, repository name, workflow filename, or environment.

1. Confirm Trusted Publishing still points at the correct repository and
workflow.

The expected publisher configuration is:

- Repository owner: `teslakoile`
- Repository name: `huly-cli`
- Workflow filename: `publish-pypi.yml`
- GitHub environment: `pypi`
- PyPI project name: `huly-cli`

2. Confirm the GitHub environment still exists and has the protection rules you
want.

Use a GitHub environment named `pypi`. If you want manual approval before every
publish, require reviewers there.

3. Keep PyPI account security in good standing.

- Create an account at `https://pypi.org/account/register/`
- Enable 2FA on the account

Official references:

- `https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/`
- `https://docs.pypi.org/trusted-publishers/using-a-publisher/`

## Manual steps for each release

1. Update the version in `src/huly_cli/__init__.py`

Example:

```python
__version__ = "0.1.1"
```

2. Run the release checks locally.

```bash
uv sync --extra dev
uv run ruff check .
uv run --extra dev pytest -q
uv run python -m build
uv run twine check dist/*
```

3. If you want a live workspace validation before release, rerun the CLI smoke
checks against a disposable Huly workspace or disposable project.

The repo includes a helper for this:

```bash
uv run python scripts/live_smoke.py
uv run python scripts/live_smoke.py --allow-writes
```

4. Commit the version bump and changelog/docs updates.

5. Tag the release and push the tag.

```bash
git tag v0.1.1
git push origin v0.1.1
```

That tag triggers `.github/workflows/publish-pypi.yml`.

## Optional first-release dry run

If you want a dress rehearsal before publishing to PyPI, add a similar Trusted
Publisher on TestPyPI and publish there first. The packaging guide for GitHub
Actions covers that setup:

- `https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/`
