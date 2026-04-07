"""Data models for Huly API responses."""

from __future__ import annotations

from enum import IntEnum

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
    identifier: str = ""  # "ROA-1"
    number: int = 0
    status: str = ""
    priority: int = 0
    kind: str = ""
    assignee: str | None = None
    due_date: int | None = Field(None, alias="dueDate")
    created_by: str = Field("", alias="createdBy")
    created_on: int = Field(0, alias="createdOn")
    modified_by: str = Field("", alias="modifiedBy")
    modified_on: int = Field(0, alias="modifiedOn")
    estimation: int = 0
    labels: int = 0
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
    name: str  # "LastName,FirstName"

    @property
    def display_name(self) -> str:
        parts = self.name.split(",", 1)
        return f"{parts[1].strip()} {parts[0].strip()}" if len(parts) == 2 else self.name


# IMPORTANT: Person._id is the Person ID (used for issue.assignee)
# Account IDs are different (used for project.members/owners)
# The member list from PersonAccount maps account_id → person_id


class PersonAccount(BaseModel):
    model_config = {"populate_by_name": True}

    id: str = Field(alias="_id")  # Account ID
    person: str  # Person ID (Ref to contact:class:Person)
    email: str = ""


class TagReference(BaseModel):
    model_config = {"populate_by_name": True}

    tag: str
    title: str
    attached_to: str = Field("", alias="attachedTo")
