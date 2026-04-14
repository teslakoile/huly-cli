"""Pydantic model validation tests."""

from __future__ import annotations

from huly_cli.models import (
    PRIORITY_FROM_NAME,
    STATUS_IDS,
    STATUS_NAMES,
    Issue,
    Person,
    PersonAccount,
    Project,
    TagReference,
)

# ── Issue ──────────────────────────────────────────────────────────────────────


class TestIssue:
    def test_issue_from_api(self):
        raw = {
            "_id": "abc123",
            "title": "Test",
            "identifier": "DEMO-1",
            "number": 1,
            "status": "tracker:status:Backlog",
            "priority": 2,
        }
        issue = Issue.model_validate(raw)
        assert issue.id == "abc123"
        assert issue.status_name == "backlog"
        assert issue.priority_name == "High"

    def test_issue_defaults(self):
        raw = {"_id": "x", "title": "T"}
        issue = Issue.model_validate(raw)
        assert issue.description == ""
        assert issue.assignee is None
        assert issue.sub_issues == 0

    def test_issue_priority_none(self):
        raw = {"_id": "x", "title": "T", "priority": 0}
        issue = Issue.model_validate(raw)
        assert issue.priority_name == "None"

    def test_issue_priority_urgent(self):
        raw = {"_id": "x", "title": "T", "priority": 1}
        issue = Issue.model_validate(raw)
        assert issue.priority_name == "Urgent"

    def test_issue_priority_medium(self):
        raw = {"_id": "x", "title": "T", "priority": 3}
        issue = Issue.model_validate(raw)
        assert issue.priority_name == "Medium"

    def test_issue_priority_low(self):
        raw = {"_id": "x", "title": "T", "priority": 4}
        issue = Issue.model_validate(raw)
        assert issue.priority_name == "Low"

    def test_issue_status_todo(self):
        raw = {"_id": "x", "title": "T", "status": "tracker:status:Todo"}
        issue = Issue.model_validate(raw)
        assert issue.status_name == "todo"

    def test_issue_status_in_progress(self):
        raw = {"_id": "x", "title": "T", "status": "tracker:status:InProgress"}
        issue = Issue.model_validate(raw)
        assert issue.status_name == "in-progress"

    def test_issue_status_done(self):
        raw = {"_id": "x", "title": "T", "status": "tracker:status:Done"}
        issue = Issue.model_validate(raw)
        assert issue.status_name == "done"

    def test_issue_status_canceled(self):
        raw = {"_id": "x", "title": "T", "status": "tracker:status:Canceled"}
        issue = Issue.model_validate(raw)
        assert issue.status_name == "canceled"

    def test_issue_unknown_status_returns_raw(self):
        raw = {"_id": "x", "title": "T", "status": "some:custom:Status"}
        issue = Issue.model_validate(raw)
        assert issue.status_name == "some:custom:Status"

    def test_issue_due_date_alias(self):
        raw = {"_id": "x", "title": "T", "dueDate": 1700000000000}
        issue = Issue.model_validate(raw)
        assert issue.due_date == 1700000000000

    def test_issue_sub_issues_alias(self):
        raw = {"_id": "x", "title": "T", "subIssues": 3}
        issue = Issue.model_validate(raw)
        assert issue.sub_issues == 3

    def test_issue_created_by_alias(self):
        raw = {"_id": "x", "title": "T", "createdBy": "user1"}
        issue = Issue.model_validate(raw)
        assert issue.created_by == "user1"

    def test_issue_accepts_null_created_by(self):
        """Regression test for issue #16: API may return null for createdBy."""
        raw = {"_id": "x", "title": "T", "createdBy": None}
        issue = Issue.model_validate(raw)
        assert issue.created_by is None

    def test_issue_accepts_null_modified_by(self):
        """Regression test for issue #16: API may return null for modifiedBy."""
        raw = {"_id": "x", "title": "T", "modifiedBy": None}
        issue = Issue.model_validate(raw)
        assert issue.modified_by is None


# ── Person ─────────────────────────────────────────────────────────────────────


class TestPerson:
    def test_person_display_name(self):
        p = Person.model_validate({"_id": "p1", "name": "Doe,Jane"})
        assert p.display_name == "Jane Doe"

    def test_person_single_name(self):
        p = Person.model_validate({"_id": "p2", "name": "Admin"})
        assert p.display_name == "Admin"

    def test_person_display_name_with_spaces(self):
        p = Person.model_validate({"_id": "p3", "name": "Smith , John "})
        assert p.display_name == "John Smith"

    def test_person_id_field(self):
        p = Person.model_validate({"_id": "person-id-123", "name": "Doe,Jane"})
        assert p.id == "person-id-123"
        assert p.display_name == "Jane Doe"

    def test_person_accepts_null_name(self):
        """Regression test for issue #16: API may return null for name."""
        p = Person.model_validate({"_id": "p4", "name": None})
        assert p.name is None

    def test_person_display_name_with_null_name(self):
        """Regression test for issue #16: display_name must not crash on None."""
        p = Person.model_validate({"_id": "p5", "name": None})
        assert p.display_name == ""


# ── Project ────────────────────────────────────────────────────────────────────


class TestProject:
    def test_project_from_api(self):
        raw = {
            "_id": "proj1",
            "name": "My Project",
            "identifier": "MP",
            "members": ["a1", "a2"],
        }
        proj = Project.model_validate(raw)
        assert proj.identifier == "MP"
        assert len(proj.members) == 2

    def test_project_defaults(self):
        raw = {"_id": "p1", "name": "Minimal"}
        proj = Project.model_validate(raw)
        assert proj.identifier == ""
        assert proj.members == []
        assert proj.owners == []
        assert proj.private is False
        assert proj.archived is False

    def test_project_default_issue_status_alias(self):
        raw = {"_id": "p1", "name": "P", "defaultIssueStatus": "tracker:status:Backlog"}
        proj = Project.model_validate(raw)
        assert proj.default_issue_status == "tracker:status:Backlog"

    def test_project_null_default_issue_status(self):
        """Regression: API may return defaultIssueStatus=null; model must accept it.

        Previously `default_issue_status: str` raised a ValidationError when the
        API returned `null`, crashing `huly projects list`. See issue #11.
        """
        raw = {
            "_id": "p1",
            "identifier": "CORE",
            "name": "Test",
            "defaultIssueStatus": None,
            "archived": False,
        }
        proj = Project.model_validate(raw)
        assert proj.default_issue_status is None


# ── PersonAccount ──────────────────────────────────────────────────────────────


class TestPersonAccount:
    def test_person_account_from_api(self):
        raw = {"_id": "acc1", "person": "person1", "email": "john@test.com"}
        acc = PersonAccount.model_validate(raw)
        assert acc.id == "acc1"
        assert acc.person == "person1"
        assert acc.email == "john@test.com"

    def test_person_account_default_email(self):
        raw = {"_id": "acc2", "person": "person2"}
        acc = PersonAccount.model_validate(raw)
        assert acc.email is None

    def test_person_account_accepts_null_email(self):
        """Regression test for issue #16: API may return null for email."""
        raw = {"_id": "acc3", "person": "person3", "email": None}
        acc = PersonAccount.model_validate(raw)
        assert acc.email is None


# ── TagReference ───────────────────────────────────────────────────────────────


class TestTagReference:
    def test_tag_reference_from_api(self):
        raw = {"_id": "t1", "tag": "tag-id", "title": "Sprint 1", "attachedTo": "issue1"}
        # TagReference does not have _id in current model — it uses tag/title/attachedTo
        tag = TagReference.model_validate(raw)
        assert tag.tag == "tag-id"
        assert tag.title == "Sprint 1"
        assert tag.attached_to == "issue1"

    def test_tag_reference_defaults(self):
        raw = {"tag": "t", "title": "Label"}
        tag = TagReference.model_validate(raw)
        assert tag.attached_to == ""

    def test_tag_reference_accepts_null_tag(self):
        """Regression test for issue #16: API may return null for tag."""
        raw = {"tag": None, "title": "Label"}
        tag = TagReference.model_validate(raw)
        assert tag.tag is None

    def test_tag_reference_accepts_null_title(self):
        """Regression test for issue #16: API may return null for title."""
        raw = {"tag": "t", "title": None}
        tag = TagReference.model_validate(raw)
        assert tag.title is None


# ── Dict constants ─────────────────────────────────────────────────────────────


class TestDictConstants:
    def test_status_ids_keys(self):
        expected_keys = {"backlog", "todo", "in-progress", "done", "canceled"}
        assert set(STATUS_IDS.keys()) == expected_keys

    def test_status_ids_values(self):
        assert STATUS_IDS["backlog"] == "tracker:status:Backlog"
        assert STATUS_IDS["todo"] == "tracker:status:Todo"
        assert STATUS_IDS["in-progress"] == "tracker:status:InProgress"
        assert STATUS_IDS["done"] == "tracker:status:Done"
        assert STATUS_IDS["canceled"] == "tracker:status:Canceled"

    def test_status_names_is_inverse(self):
        for k, v in STATUS_IDS.items():
            assert STATUS_NAMES[v] == k

    def test_priority_from_name(self):
        assert PRIORITY_FROM_NAME["none"] == 0
        assert PRIORITY_FROM_NAME["urgent"] == 1
        assert PRIORITY_FROM_NAME["high"] == 2
        assert PRIORITY_FROM_NAME["medium"] == 3
        assert PRIORITY_FROM_NAME["low"] == 4
