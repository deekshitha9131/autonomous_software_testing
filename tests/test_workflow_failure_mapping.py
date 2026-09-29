from app.workflow import graph
from app.workflow.state import WorkflowState
from app.bug_report_agent.service import BugReportAgent


def _test_state():
    test_cases = [
        {"test_id": "tc_pass", "scenario_id": "scenario_pass", "title": "Passing"},
        {"test_id": "tc_fail", "scenario_id": "scenario_fail", "title": "Failing"},
    ]
    generated_test_codes = [
        {"test_id": "tc_pass", "generated_test_code": "pass_code"},
        {"test_id": "tc_fail", "generated_test_code": "fail_code"},
    ]
    execution_results = [
        {"test_id": "tc_pass", "scenario_id": "scenario_pass", "status": "pass"},
        {"test_id": "tc_fail", "scenario_id": "scenario_fail", "status": "fail"},
    ]
    return test_cases, generated_test_codes, execution_results


def test_verify_failure_matches_records_by_test_id(monkeypatch):
    test_cases, generated_test_codes, execution_results = _test_state()
    received = {}

    class FakeVerificationAgent:
        def __init__(self, llm_client):
            pass

        def verify(self, **kwargs):
            received.update(kwargs)
            return {"verdict": "confirmed"}

    monkeypatch.setattr(graph, "_get_llm_client", lambda: object())
    monkeypatch.setattr(graph, "VerificationAgent", FakeVerificationAgent)
    state = WorkflowState(
        requirement="The failing scenario must be identified",
        test_cases=test_cases,
        generated_test_codes=generated_test_codes,
        execution_results=execution_results,
        failure_analyses=[
            {"test_id": "tc_fail", "scenario_id": "scenario_fail"}
        ],
    )

    result = graph.verify_failure(state)

    assert received["test_case"]["test_id"] == "tc_fail"
    assert received["generated_test_code"] == "fail_code"
    assert received["execution_result"]["status"] == "fail"
    assert result["verification_results"][0]["test_id"] == "tc_fail"


def test_bug_report_and_regression_match_failure_by_test_id(monkeypatch):
    test_cases, _, execution_results = _test_state()
    failure_analyses = [
        {"test_id": "tc_fail", "scenario_id": "scenario_fail"}
    ]
    verification_results = [
        {"test_id": "tc_fail", "scenario_id": "scenario_fail", "verdict": "confirmed"}
    ]
    bug_report_input = {}
    regression_input = {}

    class FakeBugReportAgent:
        def __init__(self, llm_client):
            pass

        def generate(self, **kwargs):
            bug_report_input.update(kwargs)
            return {"summary": "failure report"}

    class FakeRegressionTestAgent:
        def __init__(self, llm_client):
            pass

        def generate(self, **kwargs):
            regression_input.update(kwargs)
            return {"test_id": "regression-tc_fail"}

    monkeypatch.setattr(graph, "_get_llm_client", lambda: object())
    monkeypatch.setattr(graph, "BugReportAgent", FakeBugReportAgent)
    monkeypatch.setattr(graph, "RegressionTestAgent", FakeRegressionTestAgent)
    state = WorkflowState(
        requirement="The failing scenario must be identified",
        test_cases=test_cases,
        execution_results=execution_results,
        failure_analyses=failure_analyses,
        verification_results=verification_results,
    )

    graph.generate_bug_report(state)
    graph.generate_regression_test(state)

    assert bug_report_input["test_case"]["test_id"] == "tc_fail"
    assert bug_report_input["execution_result"]["status"] == "fail"
    assert regression_input["test_case"]["test_id"] == "tc_fail"


def test_aggregate_execution_result_exposes_later_failure():
    results = [
        {"test_id": "tc_pass", "status": "pass", "duration": 0.4},
        {"test_id": "tc_fail", "status": "fail", "duration": 0.7},
    ]

    summary, aggregate = graph.summarize_execution_results(results)

    assert summary == {
        "total": 2,
        "passed": 1,
        "failed": 1,
        "errors": 0,
        "skipped": 0,
    }
    assert aggregate["status"] == "fail"
    assert aggregate["failed_test_ids"] == ["tc_fail"]
    assert abs(aggregate["duration"] - 1.1) < 1e-9


def test_bug_report_marks_unverified_root_cause_unverified():
    report = BugReportAgent(llm_client=None).generate(
        requirement="Test requirement",
        test_case={"test_id": "tc_fail"},
        execution_result={"status": "fail"},
        failure_analysis={"probable_root_cause": "unsupported theory"},
        verification_result={"verdict": "inconclusive"},
        retrieved_knowledge=None,
    )

    assert report["root_cause_status"] == "unverified"
    assert report["summary"] == "Observed test failure; root cause remains unverified."