# Release Guide

This repo is set up to publish `huly-cli` to PyPI using GitHub Actions Trusted
Publishing.

## What the repo now handles

- Builds a wheel and sdist with `python -m build`
- Validates package metadata with `twine check`
- Verifies packaging in CI
- Includes a publish workflow at
  `.github/workflows/publish-pypi.yml`

## Manual steps you still need to do once

1. Decide the final PyPI project name.

The current package name is `huly-cli`. Before the first release, confirm it is
the name you want to keep and that it is available on PyPI.

2. Create and secure a PyPI account.

- Create an account at `https://pypi.org/account/register/`
- Enable 2FA on the account

3. Configure Trusted Publishing on PyPI.

Use PyPI's GitHub Actions Trusted Publisher flow and register this repository:

- Repository owner: `teslakoile`
- Repository name: `huly-cli`
- Workflow filename: `publish-pypi.yml`
- GitHub environment: `pypi`
- PyPI project name: `huly-cli`

For a brand new package, create a pending publisher first. PyPI will create the
project on first successful publish.

Official references:

- `https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/`
- `https://docs.pypi.org/trusted-publishers/using-a-publisher/`

4. Add environment protection in GitHub.

Create a GitHub environment named `pypi` and, if you want approval before every
publish, require reviewers there.

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
