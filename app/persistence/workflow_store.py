from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import SessionLocal
from app.persistence.workflow_run_model import WorkflowRun
import uuid
from typing import Dict, Any, Optional


class WorkflowRunStore:
    """PostgreSQL-based persistence for workflow runs."""

    def __init__(self):
        # We do not create tables here; they should be created via migrations.
        pass

    def _get_session(self) -> Session:
        return SessionLocal()

    def create_run(self, requirement: str, workflow_state: Dict[str, Any]) -> str:
        """Create a new workflow run and persist it.

        Args:
            requirement: The requirement that triggered the workflow.
            workflow_state: The initial workflow state (after workflow execution).

        Returns:
            The unique run ID.
        """
        run_id = str(uuid.uuid4())
        # Determine status from workflow_state
        execution_result = workflow_state.get("execution_result", {})
        status = execution_result.get("status", "unknown")

        with self._get_session() as session:
            db_run = WorkflowRun(
                id=run_id,
                requirement=requirement,
                status=status,
                workflow_state=workflow_state,
            )
            session.add(db_run)
            session.commit()
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a workflow run by ID.

        Args:
            run_id: The unique run ID.

        Returns:
            The run data if found, None otherwise.
        """
        with self._get_session() as session:
            db_run = session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if db_run is None:
                return None
            return {
                "id": db_run.id,
                "requirement": db_run.requirement,
                "status": db_run.status,
                "workflow_state": db_run.workflow_state,
                "created_at": db_run.created_at,
                "updated_at": db_run.updated_at,
            }

    def update_run(self, run_id: str, workflow_state: Dict[str, Any]) -> bool:
        """Update an existing workflow run with new state.

        Args:
            run_id: The unique run ID.
            workflow_state: The updated workflow state.

        Returns:
            True if the run was updated, False if not found.
        """
        execution_state = workflow_state.get("execution_result", {})
        status = execution_state.get("status", "unknown")
        with self._get_session() as session:
            db_run = session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if db_run is None:
                return False
            db_run.workflow_state = workflow_state
            db_run.status = status
            # updated_at will be updated automatically via onupdate
            session.commit()
            return True

    def update_approval(self, run_id: str, approved: bool) -> bool:
        """Update the approval status of a workflow run.

        Args:
            run_id: The unique run ID.
            approved: The approval value (True for approved, False for rejected).

        Returns:
            True if the run was updated, False if not found.
        """
        with self._get_session() as session:
            db_run = session.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if db_run is None:
                return False
            # Update the approval fields in the workflow state
            workflow_state = db_run.workflow_state.copy() if db_run.workflow_state else {}
            workflow_state["bug_report_approved"] = approved
            workflow_state["regression_test_approved"] = approved
            db_run.workflow_state = workflow_state
            # updated_at will be updated automatically via onupdate
            session.commit()
            return True