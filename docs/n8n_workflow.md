# N8N Workflow for Automated Testing Pipeline

This document describes the n8n workflow to automate the existing testing pipeline using the provided backend endpoints.

## Workflow Overview

1. **Trigger**: The workflow can be triggered by various n8n trigger nodes (e.g., Webhook, Cron, etc.) depending on the use case.
2. **Receive a testing requirement**: The requirement is obtained from the trigger or a previous node.
3. **HTTP POST to `/api/v1/automation/test/run`**: Sends the requirement to the backend to execute the LangGraph workflow.
4. **Capture the returned `run_id` and workflow result**: The backend returns a run ID and the workflow execution summary.
5. **Conditional Approval Step**: If the workflow result indicates a failure and human-in-the-loop (HITL) approval is required, the workflow proceeds to an approval step.
6. **Approval Request**: Calls `/api/v1/automation/test/approve` with the captured `run_id` and an approval decision.

## Detailed Steps

### Step 1: Trigger
- Use an appropriate n8n trigger node (e.g., **Webhook** for external requests, **Cron** for scheduled runs, etc.).
- The trigger should provide or make available a `requirement` field (string) that describes the test to be run.

### Step 2: Prepare Request to `/api/v1/automation/test/run`
- **URL**: `http://fastapi:8000/api/v1/automation/test/run`  
  (When both the n8n and FastAPI containers are on the same Docker network, use the service name `fastapi` and port `8000`. Adjust if using different host/port.)
- **HTTP Method**: `POST`
- **Headers**:
  - `Authorization: Bearer <WORKFLOW_RUN_TOKEN>`  
    (The token must match the `WORKFLOW_RUN_TOKEN` environment variable set in the backend.)
  - `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "requirement": "The requirement string from the trigger or previous node."
  }
  ```

### Step 3: Handle Response from `/api/v1/automation/test/run`
The backend returns a JSON object with the following fields:
- `run_id` (string): Unique identifier for the workflow run. **Capture this for the approval step.**
- `workflow_status` (string): Overall status (e.g., "pass", "fail", "completed_with_errors", "not_executed").
- `requirement` (string): Echoed requirement.
- `test_case_generated` (boolean): Whether a test case was generated.
- `test_executed` (boolean): Whether the test was executed.
- `execution_status` (string or null): The execution status (e.g., "pass", "fail") if a test was executed.
- `failure_detected` (boolean): Whether a failure was detected (i.e., `failure_analysis` is not null).
- `errors` (list): Any errors encountered during workflow execution.

### Step 4: Conditional Logic for Approval
- If `failure_detected` is `true` (or equivalently, if `workflow_status` is "fail"), then human approval is required.
- Use an n8n **IF** node to check the condition:
  - Condition: `{{ $json["failure_detected"] }}` is `true`
  - Alternatively, check `workflow_status` equals `"fail"`.
- If the condition is met, proceed to the approval step. Otherwise, the workflow can end or take an alternative path.

### Step 5: Prepare Request to `/api/v1/automation/test/approve`
- **URL**: `http://fastapi:8000/api/v1/automation/test/approve`
- **HTTP Method**: `POST`
- **Headers**:
  - `Authorization: Bearer <WORKFLOW_RUN_TOKEN>`
  - `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "run_id": "<captured_run_id_from_step_3>",
    "approved": true   // or false, depending on the manual decision; in an automated context, this might be set based on some criteria.
  }
  ```
  > **Note**: In a fully automated pipeline, the `approved` value might be determined by another process. For a manual approval step, you can use an n8n **Manual Approval** node to pause the workflow and obtain the approval decision.

### Step 6: Handle Response from `/api/v1/automation/test/approve`
The backend returns a JSON object with:
- `message` (string): "Approval recorded"
- `run_id` (string): The same run ID that was sent in the request.
- `approved` (boolean): The approval value that was sent.
- `bug_report_approved` (boolean): The updated approval status for the bug report.
- `regression_test_approved` (boolean): The updated approval status for the regression test.

## Docker Networking Note
When running both the n8n and FastAPI containers in the same Docker network (e.g., using Docker Compose), the backend service is accessible at `fastapi:8000` (assuming the FastAPI service is named `fastapi` and exposes port 8000). If using a different setup, adjust the host and port accordingly.

## Example n8n Workflow Structure
1. **Trigger** (e.g., Webhook)
2. **Set Node** (optional, to prepare the requirement if needed)
3. **HTTP Request Node** (to `/api/v1/automation/test/run`)
   - Method: POST
   - URL: `http://fastapi:8000/api/v1/automation/test/run`
   - Headers: Authorization and Content-Type
   - Body: JSON with `requirement`
4. **IF Node** (to check for failure)
   - Condition: `{{ $json["failure_detected"] }}` === `true`
5. **False Path**: (Optional) Handle pass scenario (e.g., send notification, end).
6. **True Path** (failure detected):
   - **Manual Approval Node** (to get human decision) **OR** **Set Node** (to set `approved` automatically)
   - **HTTP Request Node** (to `/api/v1/automation/test/approve`)
     - Method: POST
     - URL: `http://fastapi:8000/api/v1/automation/test/approve`
     - Headers: Authorization and Content-Type
     - Body: JSON with `run_id` (from step 3) and `approved` (from manual approval or set node)
   - **Optional**: Further steps to handle the approval result.

## Security Note
Ensure that the `WORKFLOW_RUN_TOKEN` environment variable is set in the backend and that the same token is used in the Authorization header of the HTTP requests. Treat this token as a secret.

---
*This documentation is for the backend as implemented. Do not modify the backend; only use the existing endpoints as described.*