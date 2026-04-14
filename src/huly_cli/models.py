"""Data models for Huly API responses."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field


class Priority(IntEnum):
    NO_PRIORITY = 0
    URGENT = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


PRIORITY_LABELS: dict[int, str] = {
    0: "None",
    1: "Urgent",
    2: "High",
    3: "Medium",
    4: "Low",
}

PRIORITY_FROM_NAME: dict[str, int] = {v.lower(): k for k, v in PRIORITY_LABELS.items()}

STATUS_IDS: dict[str, str] = {
    "backlog": "tracker:status:Backlog",
    "todo": "tracker:status:Todo",
    "in-progress": "tracker:status:InProgress",
    "done": "tracker:status:Done",
    "canceled": "tracker:status:Canceled",
}

STATUS_NAMES: dict[str, str] = {v: k for k, v in STATUS_IDS.items()}


class Issue(BaseModel):
    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id")
    title: str
    description: str = ""  # blob ref (not inline text)
    identifier: str = ""  # "DEMO-1"
    number: int = 0
    status: str = ""
    priority: int = 0
    kind: str = ""
    assignee: str | None = None
    due_date: int | None = Field(None, alias="dueDate")
    created_by: str | None = Field(None, alias="createdBy")
    created_on: int = Field(0, alias="createdOn")
    modified_by: str | None = Field(None, alias="modifiedBy")
    modified_on: int = Field(0, alias="modifiedOn")
    estimation: int = 0
    labels: Any = 0
    comments: int = 0
    sub_issues: int = Field(0, alias="subIssues")
    space: str = ""

    @property
    def status_name(self) -> str:
        return STATUS_NAMES.get(self.status, self.status)

    @property
    def priority_name(self) -> str:
        return PRIORITY_LABELS.get(self.priority, str(self.priority))


class Project(BaseModel):
    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id")
    name: str
    identifier: str = ""
    description: str = ""
    sequence: int = 0
    members: list[str] = []
    owners: list[str] = []
    default_issue_status: str = Field("", alias="defaultIssueStatus")
    private: bool = False
    archived: bool = False


class Person(BaseModel):
    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id")
    name: str | None = None  # "LastName,FirstName"

    @property
    def display_name(self) -> str:
        if not self.name:
            return ""
        parts = self.name.split(",", 1)
        return f"{parts[1].strip()} {parts[0].strip()}" if len(parts) == 2 else self.name


# IMPORTANT: Person._id is the Person ID (used for issue.assignee)
# Account IDs are different (used for project.members/owners)
# The member list from PersonAccount maps account_id → person_id


class PersonAccount(BaseModel):
    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id")  # Account ID
    person: str  # Person ID (Ref to contact:class:Person)
    email: str | None = None


class TagReference(BaseModel):
    model_config = {"populate_by_name": True}

    tag: str | None = None
    title: str | None = None
    attached_to: str = Field("", alias="attachedTo")


# ── Document / Teamspace ──────────────────────────────────────────────────────


class Teamspace(BaseModel):
    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id")
    name: str
    description: str = ""
    private: bool = False
    archived: bool = False
    members: list[str] = []
    owners: list[str] = []


class Document(BaseModel):
    """A Huly document stored in a Teamspace (document:class:Document)."""

    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id")
    title: str = ""
    content: str | None = ""  # blob ref (empty string or null if no content yet)
    space: str = ""
    parent: str = Field("", alias="parent")
    attachments: int = 0
    labels: Any = 0
    comments: int = 0
    rank: str = ""
    created_by: str = Field("", alias="createdBy")
    created_on: int = Field(0, alias="createdOn")
    modified_by: str = Field("", alias="modifiedBy")
    modified_on: int = Field(0, alias="modifiedOn")


# ── Component ─────────────────────────────────────────────────────────────────


class Component(BaseModel):
    """A tracker component scoped to a project (tracker:class:Component)."""

    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id")
    label: str = ""
    description: str = ""
    lead: str | None = None  # Person ID
    space: str = ""
    created_by: str = Field("", alias="createdBy")
    created_on: int = Field(0, alias="createdOn")
    modified_by: str = Field("", alias="modifiedBy")
    modified_on: int = Field(0, alias="modifiedOn")


# ── Milestone ─────────────────────────────────────────────────────────────────


class MilestoneStatus(IntEnum):
    PLANNED = 0
    IN_PROGRESS = 1
    COMPLETED = 2
    CANCELLED = 3


MILESTONE_STATUS_LABELS: dict[int, str] = {
    0: "planned",
    1: "in-progress",
    2: "completed",
    3: "cancelled",
}

MILESTONE_STATUS_FROM_NAME: dict[str, int] = {v: k for k, v in MILESTONE_STATUS_LABELS.items()}


class Milestone(BaseModel):
    """A tracker milestone scoped to a project (tracker:class:Milestone)."""

    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id")
    label: str = ""
    status: int = 0
    target_date: int | None = Field(None, alias="targetDate")
    comments: int = 0
    space: str = ""
    created_by: str = Field("", alias="createdBy")
    created_on: int = Field(0, alias="createdOn")
    modified_by: str = Field("", alias="modifiedBy")
    modified_on: int = Field(0, alias="modifiedOn")

    @property
    def status_name(self) -> str:
        return MILESTONE_STATUS_LABELS.get(self.status, str(self.status))


# ── IssueTemplate ─────────────────────────────────────────────────────────────


class IssueTemplate(BaseModel):
    """An issue template (tracker:class:IssueTemplate).

    The description field stores inline ProseMirror JSON (dict), not a blob ref.
    """

    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id")
    title: str = ""
    description: Any = None  # inline ProseMirror dict or empty string
    assignee: str | None = None
    component: str | None = None
    milestone: str | None = None
    priority: int = 0
    estimation: int = 0
    children: list[Any] = []
    comments: int = 0
    attachments: int = 0
    labels: Any = 0
    kind: str = ""
    relations: list[Any] = []
    space: str = ""

    @property
    def priority_name(self) -> str:
        return PRIORITY_LABELS.get(self.priority, str(self.priority))
