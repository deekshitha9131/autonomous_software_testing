"""LangGraph workflow: Requirement -> TestCase -> Selenium Test -> Execution.

Chains the existing agents into a LangGraph StateGraph:
  1. generate_test_case    - RequirementToTestCaseGenerator
  2. generate_selenium_test - TestAutomationAgent
  3. execute_test           - ExecutionService
  4. investigate_failure    - FailureInvestigationAgent (only on FAIL)
  5. verify_failure         - VerificationAgent (only on FAIL)

Flow:
  generate_test_case -> generate_selenium_test -> execute_test
    -> if PASS -> END
    -> if FAIL -> investigate_failure -> verify_failure -> generate_regression_test -> END
"""
import importlib
import importlib.util
import os
import traceback
from typing import Any, Dict

from langgraph.graph import StateGraph, END

from app.requirement_to_testcase.generator import RequirementToTestCaseGenerator
from app.requirement_to_testcase.schema import TestCase
from app.test_automation_agent.service import TestAutomationAgent
from app.selenium_engine.execution_service import ExecutionService
from app.failure_investigation_agent.service import FailureInvestigationAgent
from app.verification_agent.service import VerificationAgent
from app.bug_report_agent.service import BugReportAgent
from app.regression_test_agent.service import RegressionTestAgent
from app.llm.client import LLMClient

from pathlib import Path
from app.rag.retriever import KnowledgeRetriever

from .state import WorkflowState


# ---------------------------------------------------------------------------
# Node functions - each takes the WorkflowState and returns a partial update
# ---------------------------------------------------------------------------

def generate_test_case(state: WorkflowState) -> Dict[str, Any]:
    """Node 1: Convert requirement -> structured TestCase via LLM."""
    print("generate_test_case: start")
    try:
        llm_client = _get_llm_client()
        generator = RequirementToTestCaseGenerator(llm_client=llm_client)
        test_case: TestCase = generator.generate(state.requirement)
        print("generate_test_case: returning test_case")
        return {"test_case": test_case.model_dump()}
    except Exception as exc:
        print("generate_test_case: exception:", exc)
        return {"errors": (state.errors or []) + [f"generate_test_case: {exc}"]}


def generate_selenium_test(state: WorkflowState) -> Dict[str, Any]:
    """Node 2: Convert TestCase -> Selenium pytest file via LLM."""
    if state.test_case is None:
        return {"errors": (state.errors or []) + ["generate_selenium_test: no test_case in state"]}
    try:
        llm_client = _get_llm_client()
        agent = TestAutomationAgent(llm_client=llm_client)
        # Reconstruct TestCase from dict
        test_case = TestCase(**state.test_case)
        file_path = agent.generate_test(test_case)
        with open(file_path, "r") as f:
            code = f.read()
        return {"generated_test_path": file_path, "generated_test_code": code}
    except Exception as exc:
        return {"errors": (state.errors or []) + [f"generate_selenium_test: {exc}"]}


def _start_sut():
    """Start the demo SUT as a subprocess and wait until it accepts connections."""
    import subprocess
    import socket
    import time as _time

    sut_url = os.getenv("TEST_APP_URL", "http://127.0.0.1:8001")
    # Parse host and port from the URL
    from urllib.parse import urlparse
    parsed = urlparse(sut_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8001

    # Check if the SUT is already running
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(1)
        sock.connect((host, port))
        sock.close()
        return None  # SUT already running, nothing to manage
    except (ConnectionRefusedError, OSError):
        sock.close()

    # Start the demo app
    demo_app_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "demo_app")
    demo_app_dir = os.path.normpath(demo_app_dir)
    proc = subprocess.Popen(
        ["python", "-m", "uvicorn", "main:app", "--host", host, "--port", str(port)],
        cwd=demo_app_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for the server to be ready (up to 15 seconds)
    deadline = _time.time() + 15
    while _time.time() < deadline:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((host, port))
            s.close()
            return proc
        except (ConnectionRefusedError, OSError):
            _time.sleep(0.5)

    # If we get here, the server didn't start in time – return the proc anyway
    # so the caller can clean it up; execution will likely fail.
    return proc


def _stop_sut(proc):
    """Terminate the SUT subprocess if we started it."""
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def execute_test(state: WorkflowState) -> Dict[str, Any]:
    """Node 3: Execute the generated Selenium test via ExecutionService."""
    if state.generated_test_path is None:
        return {"errors": (state.errors or []) + ["execute_test: no generated_test_path in state"]}

    sut_proc = None
    try:
        # Ensure the SUT is running before Selenium tries to connect
        sut_proc = _start_sut()

        file_path = state.generated_test_path
        # Dynamically import the generated test module
        module_name = file_path.replace("/", ".").replace("\\", ".").removesuffix(".py")
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the test function (first function starting with 'test_')
        test_func = None
        for attr_name in dir(module):
            if attr_name.startswith("test_"):
                candidate = getattr(module, attr_name)
                if callable(candidate):
                    test_func = candidate
                    break

        if test_func is None:
            return {"errors": (state.errors or []) + ["execute_test: no test_ function found in generated file"]}

        with ExecutionService() as service:
            result = service.execute_test(test_func)

        return {"execution_result": result, "requirement": state.requirement}
    except Exception as exc:
        return {
            "errors": (state.errors or []) + [f"execute_test: {exc}"],
            "execution_result": {
                "status": "error",
                "exception": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
                "duration": 0,
                "screenshot": None,
            },
            "requirement": state.requirement,
        }
    finally:
        _stop_sut(sut_proc)


def investigate_failure(state: WorkflowState) -> Dict[str, Any]:
    """Node 4: Analyze test failure using the existing FailureInvestigationAgent."""
    result = state.execution_result
    if result is None:
        return {"errors": (state.errors or []) + ["investigate_failure: no execution_result in state"]}

    try:
        # Build query for knowledge retrieval
        query_parts = [
            state.requirement,
            str(state.test_case) if state.test_case else "",
            state.generated_test_code or "",
        ]
        if result.get("exception"):
            query_parts.append(str(result["exception"]))
        if result.get("stdout"):
            query_parts.append(result["stdout"])
        if result.get("stderr"):
            query_parts.append(result["stderr"])
        query = " ".join(part for part in query_parts if part)

        # Retrieve knowledge
        kb_path = Path(__file__).resolve().parent.parent.parent / "knowledge_base"
        retriever = KnowledgeRetriever(str(kb_path))
        retrieved_knowledge = retriever.retrieve(query, top_k=3)

        llm_client = _get_llm_client()
        agent = FailureInvestigationAgent(llm_client=llm_client)

        analysis = agent.investigate(
            requirement=state.requirement,
            test_case=state.test_case or {},
            generated_test_code=state.generated_test_code or "",
            exception=result.get("exception", {}),
            stdout=result.get("stdout"),
            stderr=result.get("stderr"),
            screenshot_path=result.get("screenshot"),
            execution_metadata={"duration": result.get("duration", 0)},
            retrieved_knowledge=retrieved_knowledge,
        )

        return {"failure_analysis": analysis.model_dump(), "retrieved_knowledge": retrieved_knowledge}
    except Exception as exc:
        return {"errors": (state.errors or []) + [f"investigate_failure: {exc}"]}


def verify_failure(state: WorkflowState) -> Dict[str, Any]:
    """Node 5: Cross-check failure analysis against evidence using VerificationAgent."""
    if state.failure_analysis is None:
        return {"errors": (state.errors or []) + ["verify_failure: no failure_analysis in state"]}

    try:
        llm_client = _get_llm_client()
        agent = VerificationAgent(llm_client=llm_client)

        verification = agent.verify(
            requirement=state.requirement,
            test_case=state.test_case or {},
            generated_test_code=state.generated_test_code or "",
            execution_result=state.execution_result or {},
            failure_analysis=state.failure_analysis,
        )

        return {"verification_result": verification.model_dump()}
    except Exception as exc:
        return {"errors": (state.errors or []) + [f"verify_failure: {exc}"]}


def generate_bug_report(state: WorkflowState) -> Dict[str, Any]:
    """Node 6: Generate bug report using the BugReportAgent."""
    if state.verification_result is None:
        # This node should only be called after verification, but guard anyway.
        return {"errors": (state.errors or []) + ["generate_bug_report: no verification_result in state"]}
    try:
        llm_client = _get_llm_client()
        agent = BugReportAgent(llm_client=llm_client)

        bug_report = agent.generate(
            requirement=state.requirement,
            test_case=state.test_case or {},
            execution_result=state.execution_result or {},
            failure_analysis=state.failure_analysis or {},
            verification_result=state.verification_result or {},
            retrieved_knowledge=state.retrieved_knowledge or [],
        )

        return {"bug_report": bug_report}
    except Exception as exc:
        return {"errors": (state.errors or []) + [f"generate_bug_report: {exc}"]}


def generate_regression_test(state: WorkflowState) -> Dict[str, Any]:
    """Node 6: Generate regression test using RegressionTestAgent."""
    if state.verification_result is None:
        # This node should only be called after verification, but guard anyway.
        return {"errors": (state.errors or []) + ["generate_regression_test: no verification_result in state"]}
    try:
        llm_client = _get_llm_client()
        agent = RegressionTestAgent(llm_client=llm_client)

        regression_test = agent.generate(
            requirement=state.requirement,
            test_case=state.test_case or {},
            failure_analysis=state.failure_analysis,
            verification_result=state.verification_result,
        )

        return {"regression_test": regression_test.model_dump()}
    except Exception as exc:
        return {"errors": (state.errors or []) + [f"generate_regression_test: {exc}"]}


def request_human_approval(state: WorkflowState) -> Dict[str, Any]:
    """Node 7: Request human approval for bug report and regression test."""
    # Set human_approval_required to True, leave approval fields as None
    return {
        "human_approval_required": True,
        # bug_report_approved and regression_test_approved remain None (not set)
    }


# ---------------------------------------------------------------------------
# Conditional routing after execute_test
# ---------------------------------------------------------------------------

def route_after_execution(state: WorkflowState) -> str:
    """Route to investigate_failure on FAIL/ERROR, or END on PASS."""
    result = state.execution_result
    if result and result.get("status") == "pass":
        return "end"
    return "investigate_failure"


# ---------------------------------------------------------------------------
# LLM client helper
# ---------------------------------------------------------------------------

def _get_llm_client() -> LLMClient:
    """Return the best available LLM client.

    Prefers OpenAI when OPENAI_API_KEY is set; otherwise falls back to the
    deterministic SUT-aware client for the login demo.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        from app.llm.client import OpenAIClient
        print(f"Using LLM client: OpenAIClient (API key set)")
        return OpenAIClient(api_key=api_key)
    else:
        from app.workflow.sut_llm_client import SUTAwareLLMClient
        print("Using LLM client: SUTAwareLLMClient (no API key)")
        return SUTAwareLLMClient()


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_workflow() -> StateGraph:
    """Build and return the compiled LangGraph workflow.

    Flow:
      generate_test_case -> generate_selenium_test -> execute_test
        -> if PASS -> END
        -> if FAIL -> investigate_failure -> verify_failure -> generate_bug_report -> generate_regression_test -> request_human_approval -> END
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("generate_test_case", generate_test_case)
    graph.add_node("generate_selenium_test", generate_selenium_test)
    graph.add_node("execute_test", execute_test)
    graph.add_node("investigate_failure", investigate_failure)
    graph.add_node("verify_failure", verify_failure)
    graph.add_node("generate_bug_report", generate_bug_report)
    graph.add_node("generate_regression_test", generate_regression_test)
    graph.add_node("request_human_approval", request_human_approval)

    graph.set_entry_point("generate_test_case")
    graph.add_edge("generate_test_case", "generate_selenium_test")
    graph.add_edge("generate_selenium_test", "execute_test")

    # Conditional edge: PASS -> END, FAIL -> investigate_failure
    graph.add_conditional_edges(
        "execute_test",
        route_after_execution,
        {
            "end": END,
            "investigate_failure": "investigate_failure",
        },
    )

    graph.add_edge("investigate_failure", "verify_failure")
    graph.add_edge("verify_failure", "generate_bug_report")
    graph.add_edge("generate_bug_report", "generate_regression_test")
    graph.add_edge("generate_regression_test", "request_human_approval")
    graph.add_edge("request_human_approval", END)

    return graph.compile()