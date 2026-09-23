import os
from fastapi import APIRouter, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.workflow.graph import build_workflow
from app.persistence.workflow_store import WorkflowRunStore

router = APIRouter()

EXPECTED_TOKEN = os.getenv("WORKFLOW_RUN_TOKEN")
security = HTTPBearer()
workflow_store = WorkflowRunStore()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if EXPECTED_TOKEN is None:
        raise HTTPException(status_code=500, detail="WORKFLOW_RUN_TOKEN not set")
    if credentials.credentials != EXPECTED_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

class AutomationRunRequest(BaseModel):
    requirement: str

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
        final_state = workflow.invoke({"requirement": request.requirement})

        errors = final_state.get("errors", [])
        execution_result = final_state.get("execution_result")
        if errors:
            workflow_status = "completed_with_errors"
        elif execution_result:
            exec_status = execution_result.get("status", "unknown")
            if exec_status == "pass":
                workflow_status = "pass"
            elif exec_status == "fail":
                workflow_status = "fail"
            else:
                workflow_status = f"execution_{exec_status}"
        else:
            workflow_status = "not_executed"

        # Persist the workflow run
        run_id = workflow_store.create_run(request.requirement, final_state)

        # Build response with run_id and important workflow outputs
        response = {
            "run_id": run_id,
            "requirement": final_state.get("requirement"),
            "test_case": final_state.get("test_case"),
            "generated_test_code": final_state.get("generated_test_code"),
            "execution_result": final_state.get("execution_result"),
            "retrieved_knowledge": final_state.get("retrieved_knowledge"),
            "failure_analysis": final_state.get("failure_analysis"),
            "verification_result": final_state.get("verification_result"),
            "bug_report": final_state.get("bug_report"),
            "regression_test": final_state.get("regression_test"),
            "human_approval_required": final_state.get("human_approval_required"),
            "bug_report_approved": final_state.get("bug_report_approved"),
            "regression_test_approved": final_state.get("regression_test_approved"),
            # Summary fields for backward compatibility
            "workflow_status": workflow_status,
            "test_case_generated": final_state.get("test_case") is not None,
            "test_executed": final_state.get("generated_test_path") is not None,
            "execution_status": execution_result.get("status") if execution_result else None,
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