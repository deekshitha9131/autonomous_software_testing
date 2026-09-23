import os
from fastapi import APIRouter, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.workflow.graph import build_workflow

router = APIRouter()

EXPECTED_TOKEN = os.getenv("WORKFLOW_RUN_TOKEN")
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if EXPECTED_TOKEN is None:
        raise HTTPException(status_code=500, detail="WORKFLOW_RUN_TOKEN not set")
    if credentials.credentials != EXPECTED_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

class WorkflowRunRequest(BaseModel):
    requirement: str


@router.post("/run")
async def run_workflow(request: WorkflowRunRequest, token: str = Security(verify_token)):
    """
    Trigger the LangGraph workflow with a natural language requirement.
    Returns a summary of the workflow execution.
    """
    try:
        workflow = build_workflow()
        # Invoke the workflow with the requirement
        final_state = workflow.invoke({"requirement": request.requirement})

        # Determine workflow status based on final state
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

        # Build a small summary
        summary = {
            "workflow_status": workflow_status,
            "requirement": request.requirement,
            "test_case_generated": final_state.get("test_case") is not None,
            "test_executed": final_state.get("generated_test_path") is not None,
            "execution_status": execution_result.get("status") if execution_result else None,
            "failure_detected": final_state.get("failure_analysis") is not None,
            "errors": errors,
        }
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))