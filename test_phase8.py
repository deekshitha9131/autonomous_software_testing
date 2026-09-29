import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the modules we need to test
import app.workflow.graph as graph
import app.workflow.state as state
from app.workflow.state import WorkflowState

# We'll mock the agents and retriever
class MockFailureInvestigationAgent:
    calls = []  # list of call arguments dicts
    def __init__(self, llm_client=None):
        pass
    def investigate(self, requirement, test_case, generated_test_code, exception, stdout=None, stderr=None, screenshot_path=None, execution_metadata=None, retrieved_knowledge=None, test_id=None, scenario_id=None, base_url=None, sut_id=None, sut_context=None):
        call = {
            "requirement": requirement,
            "test_case": test_case,
            "generated_test_code": generated_test_code,
            "exception": exception,
            "stdout": stdout,
            "stderr": stderr,
            "screenshot_path": screenshot_path,
            "execution_metadata": execution_metadata,
            "retrieved_knowledge": retrieved_knowledge,
            "test_id": test_id,
            "scenario_id": scenario_id,
            "base_url": base_url,
            "sut_id": sut_id,
            "sut_context": sut_context,
        }
        MockFailureInvestigationAgent.calls.append(call)
        # Return a dummy FailureAnalysis
        from app.failure_investigation_agent.schema import FailureAnalysis
        return FailureAnalysis(
            failure_summary="dummy summary",
            probable_root_cause="dummy root cause",
            evidence=["dummy evidence"],
            severity="medium",
            suggested_owner="dummy-team",
            confidence=0.8
        )

class MockVerificationAgent:
    calls = []  # list of call arguments dicts
    def __init__(self, llm_client=None):
        pass
    def verify(self, requirement, test_case, generated_test_code, execution_result, failure_analysis, test_id=None, scenario_id=None, base_url=None, sut_id=None, sut_context=None):
        call = {
            "requirement": requirement,
            "test_case": test_case,
            "generated_test_code": generated_test_code,
            "execution_result": execution_result,
            "failure_analysis": failure_analysis,
            "test_id": test_id,
            "scenario_id": scenario_id,
            "base_url": base_url,
            "sut_id": sut_id,
            "sut_context": sut_context,
        }
        MockVerificationAgent.calls.append(call)
        # Return a dummy VerificationResult
        from app.verification_agent.schema import VerificationResult
        return VerificationResult(
            verdict="confirmed",
            reasoning="dummy reasoning",
            evidence_gaps=[],
            recommended_action="none"
        )

class MockKnowledgeRetriever:
    last_query = None
    def __init__(self, knowledge_base_dir):
        self.knowledge_base_dir = knowledge_base_dir
    def retrieve(self, query, top_k=3):
        MockKnowledgeRetriever.last_query = query
        # Return empty list by default; can be overridden in tests
        return []

# Now replace the agents in the modules
# We need to replace the classes in the modules where they are used.
# Since the graph.py imports the agents, we can replace the imported objects.
# However, the graph.py imports the classes at the top level.
# We'll replace the classes in the modules.

# Backup original classes
from app.failure_investigation_agent import service as fi_service
from app.verification_agent import service as v_service
from app.rag import retriever as rag_ret

original_fi_agent = fi_service.FailureInvestigationAgent
original_v_agent = v_service.VerificationAgent
original_rag = rag_ret.KnowledgeRetriever

# Replace with mocks
fi_service.FailureInvestigationAgent = MockFailureInvestigationAgent
v_service.VerificationAgent = MockVerificationAgent
rag_ret.KnowledgeRetriever = MockKnowledgeRetriever

# Also need to re-import the graph module to pick up the mocked classes?
# Since graph.py already imported the agents at module load time, we need to re-import graph after patching.
# Let's reload the graph module.
import importlib
importlib.reload(graph)
# Also need to reload state? Not necessary.
# Now we have graph with mocked agents.

def reset_mocks():
    MockFailureInvestigationAgent.calls.clear()
    MockVerificationAgent.calls.clear()
    MockKnowledgeRetriever.last_query = None

def test_A_all_pass():
    print("Testing Scenario A: ALL PASS")
    reset_mocks()
    # Create a state with execution_results all pass
    ws = WorkflowState(
        requirement="Test requirement",
        execution_results=[
            {"status": "pass", "test_id": "t1", "scenario_id": "s1", "exception": None, "screenshot": None, "stdout": None, "stderr": None, "duration": 0.1},
            {"status": "pass", "test_id": "t2", "scenario_id": "s2", "exception": None, "screenshot": None, "stdout": None, "stderr": None, "duration": 0.2},
        ],
        # Also need to set execution_result (singular) for backward compatibility; it will be set by the execute_test node, but we can set it to the first result.
        execution_result={"status": "pass", "test_id": "t1", "scenario_id": "s1", "exception": None, "screenshot": None, "stdout": None, "stderr": None, "duration": 0.1},
        # Set test_cases and generated_test_codes for completeness
        test_cases=[
            {"test_id": "t1", "scenario_id": "s1"},
            {"test_id": "t2", "scenario_id": "s2"},
        ],
        generated_test_codes=[
            {"test_id": "t1", "code": "print('pass')"},
            {"test_id": "t2", "code": "print('pass')"},
        ],
    )
    # Call route_after_execution
    route_decision = graph.route_after_execution(ws)
    print(f"Route decision: {route_decision}")
    assert route_decision == "end", f"Expected 'end', got '{route_decision}'"
    # Since route is end, investigate_failure should not be called.
    # We can check that the mock agent's calls list is empty.
    assert len(MockFailureInvestigationAgent.calls) == 0, "FailureInvestigationAgent should not be called"
    assert len(MockVerificationAgent.calls) == 0, "VerificationAgent should not be called"
    print("PASS: ALL PASS")

def test_B_first_pass_later_failure():
    print("\nTesting Scenario B: FIRST PASS, LATER FAILURE")
    reset_mocks()
    ws = WorkflowState(
        requirement="Test requirement",
        execution_results=[
            {"status": "pass", "test_id": "t1", "scenario_id": "s1", "exception": None, "screenshot": None, "stdout": None, "stderr": None, "duration": 0.1},
            {"status": "fail", "test_id": "t2", "scenario_id": "s2", "exception": {"type": "AssertionError", "message": "fail"}, "screenshot": "/tmp/shot.png", "stdout": "out", "stderr": "err", "duration": 0.2},
        ],
        execution_result={"status": "pass", "test_id": "t1", "scenario_id": "s1", "exception": None, "screenshot": None, "stdout": None, "stderr": None, "duration": 0.1},  # first test result
        test_cases=[
            {"test_id": "t1", "scenario_id": "s1"},
            {"test_id": "t2", "scenario_id": "s2"},
        ],
        generated_test_codes=[
            {"test_id": "t1", "code": "print('pass')"},
            {"test_id": "t2", "code": "print('fail')"},
        ],
    )
    # Call route_after_execution
    route_decision = graph.route_after_execution(ws)
    print(f"Route decision: {route_decision}")
    assert route_decision == "investigate_failure", f"Expected 'investigate_failure', got '{route_decision}'"
    # Now call investigate_failure
    result = graph.investigate_failure(ws)
    print(f"Investigate result keys: {result.keys()}")
    # Check that failure_analyses list has one entry
    assert "failure_analyses" in result
    assert len(result["failure_analyses"]) == 1, f"Expected 1 failure analysis, got {len(result['failure_analyses'])}"
    fa = result["failure_analyses"][0]
    assert fa["test_id"] == "t2", f"Expected test_id t2, got {fa['test_id']}"
    assert fa["scenario_id"] == "s2", f"Expected scenario_id s2, got {fa['scenario_id']}"
    assert fa["execution_status"] == "fail", f"Expected status fail, got {fa['execution_status']}"
    # Check that the mock agent was called with the correct arguments for test 2
    assert len(MockFailureInvestigationAgent.calls) == 1, f"Expected 1 call to FailureInvestigationAgent, got {len(MockFailureInvestigationAgent.calls)}"
    call = MockFailureInvestigationAgent.calls[0]
    assert call["test_id"] == "t2", f"Expected test_id t2 in agent call, got {call['test_id']}"
    assert call["scenario_id"] == "s2", f"Expected scenario_id s2 in agent call, got {call['scenario_id']}"
    assert call["requirement"] == "Test requirement"
    assert call["test_case"] == {"test_id": "t2", "scenario_id": "s2"}
    assert call["generated_test_code"] == "print('fail')"
    assert call["exception"] == {"type": "AssertionError", "message": "fail"}
    assert call["stdout"] == "out"
    assert call["stderr"] == "err"
    assert call["screenshot_path"] == "/tmp/shot.png"
    # Now call verify_failure
    # We need to set the state with the investigation results first.
    # We'll create a new state that includes the output of investigate_failure.
    ws2 = WorkflowState(
        requirement=ws.requirement,
        execution_results=ws.execution_results,
        execution_result=ws.execution_result,
        test_cases=ws.test_cases,
        generated_test_codes=ws.generated_test_codes,
        failure_analyses=result["failure_analyses"],
        failure_analysis=result.get("failure_analysis"),  # singular backward compatibility
        retrieved_knowledge=result.get("retrieved_knowledge"),
    )
    verify_result = graph.verify_failure(ws2)
    print(f"Verify result keys: {verify_result.keys()}")
    assert "verification_results" in verify_result
    assert len(verify_result["verification_results"]) == 1, f"Expected 1 verification result, got {len(verify_result['verification_results'])}"
    vr = verify_result["verification_results"][0]
    assert vr["test_id"] == "t2", f"Expected test_id t2 in verification, got {vr['test_id']}"
    assert vr["scenario_id"] == "s2", f"Expected scenario_id s2 in verification, got {vr['scenario_id']}"
    # Check that the mock verification agent was called with the correct arguments
    assert len(MockVerificationAgent.calls) == 1, f"Expected 1 call to VerificationAgent, got {len(MockVerificationAgent.calls)}"
    vcall = MockVerificationAgent.calls[0]
    assert vcall["test_id"] == "t2", f"Expected test_id t2 in verification agent call, got {vcall['test_id']}"
    assert vcall["scenario_id"] == "s2", f"Expected scenario_id s2 in verification agent call, got {vcall['scenario_id']}"
    assert vcall["requirement"] == "Test requirement"
    assert vcall["test_case"] == {"test_id": "t2", "scenario_id": "s2"}
    assert vcall["generated_test_code"] == "print('fail')"
    assert vcall["execution_result"] == {"status": "fail", "test_id": "t2", "scenario_id": "s2", "exception": {"type": "AssertionError", "message": "fail"}, "screenshot": "/tmp/shot.png", "stdout": "out", "stderr": "err", "duration": 0.2}
    assert vcall["failure_analysis"] is not None
    print("PASS: FIRST PASS, LATER FAILURE")

def test_C_multiple_failures():
    print("\nTesting Scenario C: MULTIPLE FAILURES")
    reset_mocks()
    ws = WorkflowState(
        requirement="Test requirement",
        execution_results=[
            {"status": "pass", "test_id": "t1", "scenario_id": "s1", "exception": None, "screenshot": None, "stdout": None, "stderr": None, "duration": 0.1},
            {"status": "fail", "test_id": "t2", "scenario_id": "s2", "exception": {"type": "AssertionError", "message": "fail2"}, "screenshot": "/tmp/shot2.png", "stdout": "out2", "stderr": "err2", "duration": 0.2},
            {"status": "error", "test_id": "t3", "scenario_id": "s3", "exception": {"type": "ValueError", "message": "error3"}, "screenshot": None, "stdout": "out3", "stderr": "err3", "duration": 0.3},
        ],
        execution_result={"status": "pass", "test_id": "t1", "scenario_id": "s1", "exception": None, "screenshot": None, "stdout": None, "stderr": None, "duration": 0.1},  # first test result (pass)
        test_cases=[
            {"test_id": "t1", "scenario_id": "s1"},
            {"test_id": "t2", "scenario_id": "s2"},
            {"test_id": "t3", "scenario_id": "s3"},
        ],
        generated_test_codes=[
            {"test_id": "t1", "code": "print('pass')"},
            {"test_id": "t2", "code": "print('fail2')"},
            {"test_id": "t3", "code": "print('error3')"},
        ],
    )
    # Call route_after_execution
    route_decision = graph.route_after_execution(ws)
    print(f"Route decision: {route_decision}")
    assert route_decision == "investigate_failure", f"Expected 'investigate_failure', got '{route_decision}'"
    # Call investigate_failure
    result = graph.investigate_failure(ws)
    print(f"Number of failure analyses: {len(result.get('failure_analyses', []))}")
    assert len(result["failure_analyses"]) == 2, f"Expected 2 failure analyses, got {len(result['failure_analyses'])}"
    # Check that we have analyses for t2 and t3
    test_ids_in_analyses = {fa["test_id"] for fa in result["failure_analyses"]}
    assert test_ids_in_analyses == {"t2", "t3"}, f"Expected test_ids {{'t2','t3'}}, got {test_ids_in_analyses}"
    scenario_ids_in_analyses = {fa["scenario_id"] for fa in result["failure_analyses"]}
    assert scenario_ids_in_analyses == {"s2", "s3"}, f"Expected scenario_ids {{'s2','s3'}}, got {scenario_ids_in_analyses}"
    # Check that the mock agent was called twice
    assert len(MockFailureInvestigationAgent.calls) == 2, f"Expected 2 calls to FailureInvestigationAgent, got {len(MockFailureInvestigationAgent.calls)}"
    # We could check each call's test_id, but we trust the failure_analyses mapping.
    # Now test verification
    ws2 = WorkflowState(
        requirement=ws.requirement,
        execution_results=ws.execution_results,
        execution_result=ws.execution_result,
        test_cases=ws.test_cases,
        generated_test_codes=ws.generated_test_codes,
        failure_analyses=result["failure_analyses"],
        failure_analysis=result.get("failure_analysis"),
        retrieved_knowledge=result.get("retrieved_knowledge"),
    )
    # Note: I made a mistake above: I set test_cases=ws.test_codes incorrectly; it should be ws.test_cases. Let's fix.
    # Actually, I wrote ws.test_codes by mistake. Let's correct in the code.
    # We'll rewrite this part.
    # Instead of fixing in the middle, we'll just rewrite the test later. For now, we'll continue and see if it passes.
    # We'll adjust the mock to allow multiple calls and then check.
    # We'll proceed and see.
    verify_result = graph.verify_failure(ws2)
    assert len(verify_result["verification_results"]) == 2, f"Expected 2 verification results, got {len(verify_result['verification_results'])}"
    test_ids_in_verification = {vr["test_id"] for vr in verify_result["verification_results"]}
    assert test_ids_in_verification == {"t2", "t3"}, f"Expected test_ids {{'t2','t3'}}, got {test_ids_in_verification}"
    print("PASS: MULTIPLE FAILURES")

def test_D_empty_rag():
    print("\nTesting Scenario D: EMPTY RAG")
    reset_mocks()
    # We'll make the mock retriever return empty list
    # Already default is empty list.
    ws = WorkflowState(
        requirement="Test requirement",
        execution_results=[
            {"status": "fail", "test_id": "t1", "scenario_id": "s1", "exception": {"type": "RuntimeError", "message": "x"}, "screenshot": "/tmp/shot.png", "stdout": "out", "stderr": "err", "duration": 0.5},
        ],
        execution_result={"status": "fail", "test_id": "t1", "scenario_id": "s1", "exception": {"type": "RuntimeError", "message": "x"}, "screenshot": "/tmp/shot.png", "stdout": "out", "stderr": "err", "duration": 0.5},
        test_cases=[{"test_id": "t1", "scenario_id": "s1"}],
        generated_test_codes=[{"test_id": "t1", "code": "print('fail')"}],
    )
    route_decision = graph.route_after_execution(ws)
    assert route_decision == "investigate_failure"
    result = graph.investigate_failure(ws)
    assert len(result["failure_analyses"]) == 1
    fa = result["failure_analyses"][0]
    assert fa["test_id"] == "t1"
    assert fa["scenario_id"] == "s1"
    # Check that the mock agent was called with retrieved_knowledge empty list
    assert len(MockFailureInvestigationAgent.calls) == 1
    call = MockFailureInvestigationAgent.calls[0]
    assert call["retrieved_knowledge"] == []  # because our mock returns empty list
    print("PASS: EMPTY RAG")

def test_E_incomplete_evidence():
    print("\nTesting Scenario E: INCOMPLETE EVIDENCE")
    reset_mocks()
    # Test with missing exception, missing screenshot, etc.
    ws = WorkflowState(
        requirement="Test requirement",
        execution_results=[
            {"status": "fail", "test_id": "t1", "scenario_id": "s1", "exception": None, "screenshot": None, "stdout": "someout", "stderr": None, "duration": 0.3},
        ],
        execution_result={"status": "fail", "test_id": "t1", "scenario_id": "s1", "exception": None, "screenshot": None, "stdout": "someout", "stderr": None, "duration": 0.3},
        test_cases=[{"test_id": "t1", "scenario_id": "s1"}],
        generated_test_codes=[{"test_id": "t1", "code": "print('fail')"}],
    )
    route_decision = graph.route_after_execution(ws)
    assert route_decision == "investigate_failure"
    result = graph.investigate_failure(ws)
    assert len(result["failure_analyses"]) == 1
    fa = result["failure_analyses"][0]
    # Check that the mock agent was called with the given evidence
    assert len(MockFailureInvestigationAgent.calls) == 1
    call = MockFailureInvestigationAgent.calls[0]
    # In our code we pass exception or {} if exception is None
    assert call["exception"] == {}
    assert call["stdout"] == "someout"
    assert call["stderr"] is None
    assert call["screenshot_path"] is None
    # The agent should still produce an analysis; we don't check the confidence here because it's dummy.
    # But we can check that the analysis is present.
    assert fa["failure_analysis"] is not None
    print("PASS: INCOMPLETE EVIDENCE")

if __name__ == "__main__":
    try:
        test_A_all_pass()
        test_B_first_pass_later_failure()
        test_C_multiple_failures()
        test_D_empty_rag()
        test_E_incomplete_evidence()
        print("\nAll scenarios passed!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore original classes
        fi_service.FailureInvestigationAgent = original_fi_agent
        v_service.VerificationAgent = original_v_agent
        rag_ret.KnowledgeRetriever = original_rag
        # Reload graph to restore original agents? Not necessary for the test end.
        # Reload graph module to restore original imports (optional)
        importlib.reload(graph)