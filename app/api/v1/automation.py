import os
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, model_validator
from starlette.concurrency import run_in_threadpool
from app.workflow.graph import build_workflow
from app.persistence.workflow_store import WorkflowRunStore, get_execution_status

router = APIRouter()

EXPECTED_TOKEN = os.getenv("WORKFLOW_RUN_TOKEN")
security = HTTPBearer()
workflow_store = WorkflowRunStore()


def _enrich_demo_sut_context(request: "AutomationRunRequest") -> Optional[Dict[str, Any]]:
    context = dict(request.sut_context or {})
    if request.sut_id == "demo-app" and context.get("route") == "/hello":
        context.setdefault("greeting_template", "Hello, {name}!")
        context.setdefault("empty_name_behavior", "Hello, Stranger!")
    return context or None


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if EXPECTED_TOKEN is None:
        raise HTTPException(status_code=500, detail="WORKFLOW_RUN_TOKEN not set")
    if credentials.credentials != EXPECTED_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

class AutomationRunRequest(BaseModel):
    requirement: str
    base_url: Optional[str] = None
    sut_id: Optional[str] = None
    sut_context: Optional[Dict[str, Any]] = None
    test_data: Optional[Dict[str, Any]] = None

    @model_validator(mode='after')
    def validate_requirement(self) -> 'AutomationRunRequest':
        if not self.requirement or not self.requirement.strip():
            raise ValueError('requirement must not be empty or whitespace-only')
        return self

class ApprovalRequest(BaseModel):
    run_id: str
    approved: bool

@router.post("/test/run")
async def run_automation_test(request: AutomationRunRequest, token: str = Security(verify_token)):
    """
    Trigger the LangGraph workflow for n8n automation.
    Returns a summary of the workflow execution and the run ID.
    """
    try:
        workflow = build_workflow()
        final_state = await run_in_threadpool(
            workflow.invoke,
            {
                "requirement": request.requirement,
                "base_url": request.base_url,
                "sut_id": request.sut_id,
                "sut_context": _enrich_demo_sut_context(request),
                "test_data": request.test_data,
            },
        )

        errors = final_state.get("errors", [])
        execution_result = final_state.get("execution_result")
        execution_status = get_execution_status(final_state)
        missing_context = final_state.get("missing_context") or {}
        if missing_context.get("status") in {"unsupported", "clarification_needed"}:
            workflow_status = missing_context["status"]
        elif errors:
            workflow_status = "completed_with_errors"
        elif execution_status in ("pass", "fail"):
            workflow_status = execution_status
        elif execution_status:
            workflow_status = f"execution_{execution_status}"
        else:
            workflow_status = "not_executed"

        # Persist the workflow run
        run_id = workflow_store.create_run(request.requirement, final_state)

        # Build response with run_id and important workflow outputs
        response = {
            "run_id": run_id,
            "requirement": final_state.get("requirement"),
            "requirement_understanding": final_state.get("requirement_understanding"),
            "missing_context": final_state.get("missing_context"),
            "test_scenarios": final_state.get("test_scenarios"),
            "test_cases": final_state.get("test_cases"),
            "test_case": final_state.get("test_case"),
            "generated_test_codes": final_state.get("generated_test_codes"),
            "generated_test_code": final_state.get("generated_test_code"),
            "execution_results": final_state.get("execution_results"),
            "execution_summary": final_state.get("execution_summary"),
            "execution_result": final_state.get("execution_result"),
            "primary_execution_result": final_state.get("primary_execution_result"),
            "regression_execution_result": final_state.get("regression_execution_result"),
            "retrieved_knowledge": final_state.get("retrieved_knowledge"),
            "failure_analysis": final_state.get("failure_analysis"),
            "failure_analyses": final_state.get("failure_analyses"),
            "verification_result": final_state.get("verification_result"),
            "verification_results": final_state.get("verification_results"),
            "bug_report": final_state.get("bug_report"),
            "bug_reports": final_state.get("bug_reports"),
            "regression_test": final_state.get("regression_test"),
            "regression_tests": final_state.get("regression_tests"),
            "human_approval_required": final_state.get("human_approval_required"),
            "bug_report_approved": final_state.get("bug_report_approved"),
            "regression_test_approved": final_state.get("regression_test_approved"),
            # Summary fields for backward compatibility
            "workflow_status": workflow_status,
            "test_case_generated": final_state.get("test_case") is not None,
            "test_executed": final_state.get("generated_test_path") is not None,
            "execution_status": execution_status,
            "failure_detected": final_state.get("failure_analysis") is not None,
            "errors": errors,
        }
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/approve")
async def approve_test(request: ApprovalRequest, token: str = Security(verify_token)):
    """
    Record human approval for the bug report and regression test for a specific workflow run.
    """
    run_data = workflow_store.get_run(request.run_id)
    if not run_data:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    # Update the approval state
    success = workflow_store.update_approval(request.run_id, request.approved)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update approval")

    # Retrieve the updated run to return the current state
    updated_run = workflow_store.get_run(request.run_id)
    return {
        "message": "Approval recorded",
        "run_id": request.run_id,
        "approved": request.approved,
        "bug_report_approved": updated_run["workflow_state"].get("bug_report_approved"),
        "regression_test_approved": updated_run["workflow_state"].get("regression_test_approved"),
    }