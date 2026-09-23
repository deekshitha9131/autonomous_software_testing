import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app

# If using SQLite for testing, create tables
if os.getenv("DATABASE_URL", "").startswith("sqlite"):
    from app.core.database import Base, engine
    Base.metadata.create_all(bind=engine)

client = TestClient(app)


def test_workflow_run_missing_token():
    response = client.post("/api/v1/workflow/run", json={"requirement": "test"})
    assert response.status_code == 401


def test_workflow_run_invalid_token():
    # Set an expected token so that the token validation proceeds to check the token
    with patch("app.api.v1.workflow.EXPECTED_TOKEN", "expectedtoken"):
        response = client.post(
            "/api/v1/workflow/run",
            json={"requirement": "test"},
            headers={"Authorization": "Bearer wrongtoken"}
        )
        assert response.status_code == 401


def test_workflow_run_valid_token():
    # Mock the expected token in the workflow module
    with patch("app.api.v1.workflow.EXPECTED_TOKEN", "testtoken"):
        # Mock the workflow to avoid actual execution
        with patch("app.api.v1.workflow.build_workflow") as mock_build:
            mock_workflow = mock_build.return_value
            # Mock the state returned by the workflow
            mock_workflow.invoke.return_value = {
                "requirement": "test",
                "errors": [],
                "execution_result": {"status": "pass"},
                "test_case": {"test_id": "TC1"},  # non-None -> test_case_generated True
                "generated_test_path": "/fake/path.py",  # non-None -> test_executed True
                "failure_analysis": None,  # None -> failure_detected False
            }
            response = client.post(
                "/api/v1/workflow/run",
                json={"requirement": "test"},
                headers={"Authorization": "Bearer testtoken"}
            )
            assert response.status_code == 200


def test_automation_test_run_missing_token():
    response = client.post("/api/v1/automation/test/run", json={"requirement": "test"})
    assert response.status_code == 401


def test_automation_test_run_invalid_token():
    # Set an expected token so that the token validation proceeds to check the token
    with patch("app.api.v1.automation.EXPECTED_TOKEN", "expectedtoken"):
        response = client.post(
            "/api/v1/automation/test/run",
            json={"requirement": "test"},
            headers={"Authorization": "Bearer wrongtoken"}
        )
        assert response.status_code == 401


def test_automation_test_run_valid_token():
    # Mock the expected token in the automation module
    with patch("app.api.v1.automation.EXPECTED_TOKEN", "testtoken"):
        # Mock the workflow to avoid actual execution
        with patch("app.api.v1.automation.build_workflow") as mock_build:
            mock_workflow = mock_build.return_value
            # Mock the state returned by the workflow
            mock_workflow.invoke.return_value = {
                "requirement": "test",
                "errors": [],
                "execution_result": {"status": "pass"},
                "test_case": {"test_id": "TC1"},  # non-None -> test_case_generated True
                "generated_test_path": "/fake/path.py",  # non-None -> test_executed True
                "failure_analysis": None,  # None -> failure_detected False
            }
            response = client.post(
                "/api/v1/automation/test/run",
                json={"requirement": "test"},
                headers={"Authorization": "Bearer testtoken"}
            )
            if response.status_code != 200:
                print(f"Response status: {response.status_code}")
                print(f"Response body: {response.json()}")
            assert response.status_code == 200
            data = response.json()
            assert data["workflow_status"] == "pass"
            assert "run_id" in data  # New field: run_id should be present


def test_automation_test_approve_missing_token():
    response = client.post("/api/v1/automation/test/approve", json={"run_id": "dummy", "approved": True})
    assert response.status_code == 401


def test_automation_test_approve_invalid_token():
    # Set an expected token so that the token validation proceeds to check the token
    with patch("app.api.v1.automation.EXPECTED_TOKEN", "expectedtoken"):
        response = client.post(
            "/api/v1/automation/test/approve",
            json={"run_id": "dummy", "approved": True},
            headers={"Authorization": "Bearer wrongtoken"}
        )
        assert response.status_code == 401


def test_automation_test_approve_valid_token_approved_true():
    # Mock the expected token in the automation module
    with patch("app.api.v1.automation.EXPECTED_TOKEN", "testtoken"):
        # First, create a run to get a valid run_id
        with patch("app.api.v1.automation.build_workflow") as mock_build:
            mock_workflow = mock_build.return_value
            # Mock the state returned by the workflow for a failed test (so that approval is relevant)
            mock_workflow.invoke.return_value = {
                "requirement": "test",
                "errors": [],
                "execution_result": {"status": "fail"},
                "test_case": {"test_id": "TC1"},
                "generated_test_path": "/fake/path.py",
                "generated_test_code": "assert False",
                "failure_analysis": {"failure_summary": "Test failed"},
                "verification_result": {"verdict": "confirmed"},
                "retrieved_knowledge": [{"id": "kb1", "content": "knowledge"}],
                "bug_report": {
                    "requirement": "test",
                    "test_case": {"test_id": "TC1"},
                    "execution_result": {"status": "fail"},
                    "failure_analysis": {"failure_summary": "Test failed"},
                    "verification_result": {"verdict": "confirmed"},
                    "retrieved_knowledge": [{"id": "kb1", "content": "knowledge"}],
                    "summary": "Bug report generated from test failure.",
                },
                "regression_test": {"test_id": "REG001"},
                "human_approval_required": True,
                "bug_report_approved": None,
                "regression_test_approved": None,
            }
            run_response = client.post(
                "/api/v1/automation/test/run",
                json={"requirement": "test"},
                headers={"Authorization": "Bearer testtoken"}
            )
            assert run_response.status_code == 200
            run_data = run_response.json()
            run_id = run_data["run_id"]

            # Now, approve the run
            response = client.post(
                "/api/v1/automation/test/approve",
                json={"run_id": run_id, "approved": True},
                headers={"Authorization": "Bearer testtoken"}
            )
            assert response.status_code == 200
            data = response.json()
            # Debug: get the run from the store to see the workflow state
            from app.persistence.workflow_store import WorkflowRunStore
            store = WorkflowRunStore()
            debug_run = store.get_run(run_id)
            print(f"Debug workflow state: {debug_run['workflow_state'] if debug_run else 'None'}")
            assert data["message"] == "Approval recorded"
            assert data["approved"] == True
            assert data["run_id"] == run_id
            assert data["bug_report_approved"] == True
            assert data["regression_test_approved"] == True


def test_automation_test_approve_valid_token_approved_false():
    # Mock the expected token in the automation module
    with patch("app.api.v1.automation.EXPECTED_TOKEN", "testtoken"):
        # First, create a run to get a valid run_id
        with patch("app.api.v1.automation.build_workflow") as mock_build:
            mock_workflow = mock_build.return_value
            # Mock the state returned by the workflow for a failed test (so that approval is relevant)
            mock_workflow.invoke.return_value = {
                "requirement": "test",
                "errors": [],
                "execution_result": {"status": "fail"},
                "test_case": {"test_id": "TC1"},
                "generated_test_path": "/fake/path.py",
                "generated_test_code": "assert False",
                "failure_analysis": {"failure_summary": "Test failed"},
                "verification_result": {"verdict": "confirmed"},
                "retrieved_knowledge": [{"id": "kb1", "content": "knowledge"}],
                "bug_report": {
                    "requirement": "test",
                    "test_case": {"test_id": "TC1"},
                    "execution_result": {"status": "fail"},
                    "failure_analysis": {"failure_summary": "Test failed"},
                    "verification_result": {"verdict": "confirmed"},
                    "retrieved_knowledge": [{"id": "kb1", "content": "knowledge"}],
                    "summary": "Bug report generated from test failure.",
                },
                "regression_test": {"test_id": "REG001"},
                "human_approval_required": True,
                "bug_report_approved": None,
                "regression_test_approved": None,
            }
            run_response = client.post(
                "/api/v1/automation/test/run",
                json={"requirement": "test"},
                headers={"Authorization": "Bearer testtoken"}
            )
            assert run_response.status_code == 200
            run_data = run_response.json()
            run_id = run_data["run_id"]

            # Now, reject the run
            response = client.post(
                "/api/v1/automation/test/approve",
                json={"run_id": run_id, "approved": False},
                headers={"Authorization": "Bearer testtoken"}
            )
            assert response.status_code == 200
            data = response.json()
            # Debug: get the run from the store to see the workflow state
            from app.persistence.workflow_store import WorkflowRunStore
            store = WorkflowRunStore()
            debug_run = store.get_run(run_id)
            print(f"Debug workflow state: {debug_run['workflow_state'] if debug_run else 'None'}")
            assert data["message"] == "Approval recorded"
            assert data["approved"] == False
            assert data["run_id"] == run_id
            assert data["bug_report_approved"] == False
            assert data["regression_test_approved"] == False