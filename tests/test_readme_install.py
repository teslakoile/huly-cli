"""Validate that README.md recommends pipx as the primary install method.

Background: On PEP 668-compliant environments (e.g. modern macOS with
Homebrew-managed Python), bare `pip install` is blocked with
"externally-managed-environment". The Python Packaging Authority recommends
`pipx` for installing standalone CLI tools. The README must therefore lead
with `pipx install huly-cli` rather than `pip install huly-cli`.
"""

from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"


def _read_readme() -> str:
    return README.read_text(encoding="utf-8")


def _slice_install_section(text: str) -> str:
    """Return the text of the PyPI install subsection.

    The section starts at `### Option 1` (Install from PyPI) and ends at the
    next top-level or sibling heading (`### Option 2` or `## `).
    """
    start_marker = "### Option 1"
    start = text.find(start_marker)
    assert start != -1, "README is missing '### Option 1' install heading"

    # Find the next sibling/ancestor heading after the start.
    rest = text[start + len(start_marker) :]
    end_candidates = [rest.find("\n### "), rest.find("\n## ")]
    end_offsets = [c for c in end_candidates if c != -1]
    assert end_offsets, "Could not find end of Option 1 section"
    end = start + len(start_marker) + min(end_offsets)
    return text[start:end]


def test_pipx_appears_before_pip_in_install_section() -> None:
    """pipx install huly-cli must be documented before pip install huly-cli."""
    section = _slice_install_section(_read_readme())

    pipx_idx = section.find("pipx install huly-cli")
    pip_idx = section.find("pip install huly-cli")

    assert pipx_idx != -1, (
        "Option 1 section does not mention `pipx install huly-cli`. "
        "pipx is the recommended install method for standalone CLI tools."
    )
    assert pip_idx != -1, (
        "Option 1 section does not mention `pip install huly-cli`. "
        "pip should still be documented as a secondary option."
    )
    assert pipx_idx < pip_idx, (
        "`pipx install huly-cli` must appear BEFORE `pip install huly-cli` "
        "in the Option 1 install section. pipx is the primary recommendation "
        "for end-users; pip is secondary (virtualenv/CI)."
    )


def test_pipx_upgrade_command_documented() -> None:
    """The README should document `pipx upgrade huly-cli` for pipx users."""
    text = _read_readme()
    assert "pipx upgrade huly-cli" in text, (
        "README is missing `pipx upgrade huly-cli`. pipx users need a "
        "documented upgrade command alongside the pipx install instruction."
    )


def test_packaging_section_leads_with_pipx() -> None:
    """The 'Packaging And PyPI' section at the bottom should also lead with pipx."""
    text = _read_readme()
    marker = "## Packaging and PyPI"
    start = text.find(marker)
    assert start != -1, "README is missing the 'Packaging And PyPI' section"

    # Section ends at the next `## ` heading.
    rest = text[start + len(marker) :]
    end_offset = rest.find("\n## ")
    end = start + len(marker) + (end_offset if end_offset != -1 else len(rest))
    section = text[start:end]

    pipx_idx = section.find("pipx install huly-cli")
    pip_idx = section.find("pip install huly-cli")

    assert pipx_idx != -1, (
        "'Packaging And PyPI' section does not mention "
        "`pipx install huly-cli`. It should be consistent with Option 1."
    )
    if pip_idx != -1:
        assert pipx_idx < pip_idx, (
            "In 'Packaging And PyPI', `pipx install huly-cli` must appear "
            "before `pip install huly-cli`."
        )
