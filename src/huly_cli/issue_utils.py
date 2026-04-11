"""Issue-specific helpers for status lookup and rank generation."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from huly_cli.models import STATUS_IDS, STATUS_NAMES

ISSUE_STATUS_CLASS = "tracker:class:IssueStatus"
STATUS_CATEGORY_CLASS = "core:class:StatusCategory"
RANK_FALLBACK = "0|hzzzzz:"

_STATUS_RE = re.compile(r"^(?P<bucket>[^|]+)\|(?P<body>[0-9a-z]+):(?P<suffix>.*)$")
_NON_ALNUM_RE = re.compile(r"[^0-9A-Za-z]+")
_CAMEL_RE_1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_RE_2 = re.compile(r"([A-Z]+)([A-Z][a-z])")
_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def normalize_status_key(value: str) -> str:
    """Normalize a status/category name or identifier into a stable slug."""
    text = value.strip()
    text = _CAMEL_RE_1.sub(r"\1-\2", text)
    text = _CAMEL_RE_2.sub(r"\1-\2", text)
    text = text.replace("_", "-")
    text = _NON_ALNUM_RE.sub("-", text)
    text = re.sub(r"-+", "-", text).strip("-").lower()
    return "todo" if text == "to-do" else text


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _normalize_label(value: str) -> str:
    label = normalize_status_key(value)
    return label or value


def _increment_rank_body(body: str) -> str:
    digits = list(body)
    idx = len(digits) - 1
    carry = 1
    while idx >= 0 and carry:
        current = _ALPHABET.index(digits[idx]) if digits[idx] in _ALPHABET else 0
        current += carry
        digits[idx] = _ALPHABET[current % 36]
        carry = current // 36
        idx -= 1
    if carry:
        digits.insert(0, "1")
    return "".join(digits)


@dataclass(slots=True)
class IssueStatusIndex:
    """Live issue-status lookup data."""

    by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    ids_by_name: dict[str, list[str]] = field(default_factory=dict)
    ids_by_category_name: dict[str, list[str]] = field(default_factory=dict)
    labels_by_id: dict[str, str] = field(default_factory=dict)

    def resolve_ids(self, raw_status: str) -> list[str]:
        """Return live status ids that match a name, category name, or raw ref."""
        raw_key = normalize_status_key(raw_status)
        tail_key = normalize_status_key(raw_status.rsplit(":", 1)[-1])

        candidates: list[str] = []
        if raw_status in self.by_id:
            candidates.append(raw_status)

        for key in (raw_key, tail_key):
            candidates.extend(self.ids_by_name.get(key, []))
            candidates.extend(self.ids_by_category_name.get(key, []))
            fallback = STATUS_IDS.get(key)
            if fallback:
                candidates.append(fallback)

        return _dedupe(candidates)

    def label_for(self, status_id: str) -> str:
        """Return a readable label for a status id."""
        if status_id in STATUS_NAMES:
            return STATUS_NAMES[status_id]

        if status_id in self.labels_by_id:
            return self.labels_by_id[status_id]

        status_doc = self.by_id.get(status_id)
        if status_doc is not None:
            name = str(status_doc.get("name") or status_id.rsplit(":", 1)[-1])
            return _normalize_label(name)

        return _normalize_label(status_id.rsplit(":", 1)[-1] if ":" in status_id else status_id)

    def available_labels(self) -> list[str]:
        labels = {
            *self.labels_by_id.values(),
            *self.ids_by_name.keys(),
            *self.ids_by_category_name.keys(),
            *STATUS_IDS.keys(),
        }
        return sorted(labels)


async def load_issue_status_index(client: Any) -> IssueStatusIndex:
    """Load live issue statuses and their category defaults."""
    category_rows = await client.find_all(STATUS_CATEGORY_CLASS, options={"limit": 500})
    category_labels_by_id: dict[str, str] = {}
    for row in category_rows:
        category_id = row.get("_id")
        if not category_id:
            continue
        category_label = str(row.get("defaultStatusName") or row.get("name") or category_id)
        category_labels_by_id[category_id] = _normalize_label(category_label)

    status_rows = await client.find_all(ISSUE_STATUS_CLASS, options={"limit": 500})

    by_id: dict[str, dict[str, Any]] = {}
    ids_by_name: dict[str, list[str]] = defaultdict(list)
    ids_by_category_name: dict[str, list[str]] = defaultdict(list)
    labels_by_id: dict[str, str] = {}

    for row in status_rows:
        status_id = row.get("_id")
        if not status_id:
            continue

        by_id[status_id] = row
        status_label = _normalize_label(str(row.get("name") or status_id.rsplit(":", 1)[-1]))
        labels_by_id[status_id] = status_label
        ids_by_name[status_label].append(status_id)

        category_id = row.get("category")
        if category_id:
            category_label = category_labels_by_id.get(category_id)
            if category_label:
                ids_by_category_name[category_label].append(status_id)

    return IssueStatusIndex(
        by_id=by_id,
        ids_by_name={k: _dedupe(v) for k, v in ids_by_name.items()},
        ids_by_category_name={k: _dedupe(v) for k, v in ids_by_category_name.items()},
        labels_by_id=labels_by_id,
    )


def resolve_status_ids(
    raw_status: str,
    status_index: IssueStatusIndex | None = None,
    *,
    prefer_live: bool = True,
) -> list[str]:
    """Resolve a human status input to one or more status ids."""
    candidates: list[str] = []
    if status_index is not None and prefer_live:
        candidates.extend(status_index.resolve_ids(raw_status))

    hardcoded = STATUS_IDS.get(normalize_status_key(raw_status))
    if hardcoded:
        candidates.append(hardcoded)

    tail_hardcoded = STATUS_IDS.get(normalize_status_key(raw_status.rsplit(":", 1)[-1]))
    if tail_hardcoded:
        candidates.append(tail_hardcoded)

    if status_index is not None and not prefer_live:
        candidates.extend(status_index.resolve_ids(raw_status))

    return _dedupe(candidates)


def resolve_status_id(
    raw_status: str,
    status_index: IssueStatusIndex | None = None,
    *,
    preferred: str | None = None,
) -> str:
    """Resolve a human status input to a single status id."""
    candidates = resolve_status_ids(raw_status, status_index)
    if not candidates:
        raise ValueError(raw_status)

    if preferred and preferred in candidates:
        return preferred
    return candidates[0]


def status_label(status_id: str, status_index: IssueStatusIndex | None = None) -> str:
    """Return a readable label for a status id, using the live index if needed."""
    if status_id in STATUS_NAMES:
        return STATUS_NAMES[status_id]
    if status_index is not None:
        return status_index.label_for(status_id)
    return _normalize_label(status_id.rsplit(":", 1)[-1] if ":" in status_id else status_id)


def next_rank(previous_rank: str | None) -> str:
    """Generate the next lexorank-like value after ``previous_rank``."""
    if previous_rank:
        match = _STATUS_RE.fullmatch(previous_rank)
        if match:
            body = _increment_rank_body(match.group("body"))
            return f"{match.group('bucket')}|{body}:{match.group('suffix')}"
    return RANK_FALLBACK
