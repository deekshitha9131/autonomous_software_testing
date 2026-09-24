"""Tests for WorkflowRunStore PostgreSQL persistence (uses SQLite in-memory for CI)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.persistence.workflow_run_model import WorkflowRun
from app.persistence.workflow_store import WorkflowRunStore


@pytest.fixture()
def store(monkeypatch):
    """Create a WorkflowRunStore backed by an in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Patch get_session_local to return our test session factory
    monkeypatch.setattr(
        "app.persistence.workflow_store.get_session_local", lambda: _SessionLocal
    )
    return WorkflowRunStore()


class TestWorkflowRunStore:
    def test_create_and_get_run(self, store):
        state = {
            "requirement": "Login must work",
            "execution_result": {"status": "passed", "details": "ok"},
        }
        run_id = store.create_run("Login must work", state)

        result = store.get_run(run_id)
        assert result is not None
        assert result["id"] == run_id
        assert result["requirement"] == "Login must work"
        assert result["status"] == "passed"
        assert result["workflow_state"] == state

    def test_get_run_not_found(self, store):
        assert store.get_run("nonexistent-id") is None

    def test_update_run(self, store):
        state = {"execution_result": {"status": "running"}}
        run_id = store.create_run("Req", state)

        new_state = {
            "execution_result": {"status": "passed", "details": "all green"},
            "test_code": "def test(): pass",
        }
        assert store.update_run(run_id, new_state) is True

        result = store.get_run(run_id)
        assert result["status"] == "passed"
        assert result["workflow_state"]["test_code"] == "def test(): pass"

    def test_update_run_not_found(self, store):
        assert store.update_run("bad-id", {}) is False

    def test_update_approval(self, store):
        state = {"execution_result": {"status": "pending_approval"}}
        run_id = store.create_run("Req", state)

        assert store.update_approval(run_id, True) is True

        result = store.get_run(run_id)
        ws = result["workflow_state"]
        assert ws["bug_report_approved"] is True
        assert ws["regression_test_approved"] is True

    def test_update_approval_reject(self, store):
        state = {"execution_result": {"status": "pending_approval"}}
        run_id = store.create_run("Req", state)

        assert store.update_approval(run_id, False) is True

        result = store.get_run(run_id)
        ws = result["workflow_state"]
        assert ws["bug_report_approved"] is False
        assert ws["regression_test_approved"] is False

    def test_update_approval_not_found(self, store):
        assert store.update_approval("bad-id", True) is False

    def test_workflow_state_jsonb_serializable(self, store):
        """Full workflow state with nested dicts/lists must round-trip."""
        state = {
            "requirement": "Complex test",
            "test_cases": [{"name": "tc1", "steps": ["s1", "s2"]}],
            "execution_result": {"status": "passed", "metrics": {"time": 1.23}},
            "bug_report_approved": None,
            "regression_test_approved": None,
        }
        run_id = store.create_run("Complex test", state)
        result = store.get_run(run_id)
        assert result["workflow_state"] == state
