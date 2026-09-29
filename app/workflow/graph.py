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
import json
import os
import re
import traceback
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END

from app.requirement_to_testcase.generator import RequirementToTestCaseGenerator
from app.requirement_to_testcase.schema import TestCase
from app.test_automation_agent.service import TestAutomationAgent
from app.selenium_engine.execution_service import ExecutionService
from app.failure_investigation_agent.service import FailureInvestigationAgent
from app.verification_agent.service import VerificationAgent
from app.bug_report_agent.service import BugReportAgent
from app.regression_test_agent.service import RegressionTestAgent
from app.llm.client import LLMClient, GroqClient, OpenAIClient, GeminiClient

from pathlib import Path
from app.rag.retriever import KnowledgeRetriever

from .state import WorkflowState
from pydantic import BaseModel, Field
from typing import List, Literal
from app.requirement_understanding.schema import RequirementUnderstanding


class Scenario(BaseModel):
    scenario_id: str = Field(..., description="Unique identifier for the scenario")
    scenario_type: Literal["functional", "negative", "boundary", "security"] = Field(..., description="Type of test scenario")
    title: str = Field(..., description="Short title summarizing the scenario")
    description: str = Field(..., description="Detailed description of what the scenario covers")
    route: Optional[str] = Field(
        default=None, description="Implemented SUT route this scenario exercises"
    )

class ScenarioList(BaseModel):
    scenarios: List[Scenario] = Field(..., description="List of generated test scenarios")


def _get_llm_client() -> LLMClient:
    """Get LLM client instance based on environment configuration."""
    llm_provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if llm_provider == "groq":
        return GroqClient()
    elif llm_provider == "gemini":
        return GeminiClient()
    elif llm_provider == "openai":
        return OpenAIClient()
    else:
        # Default to OpenAI for backward compatibility
        return OpenAIClient()


def _find_correlated_record(records, test_id, index):
    if not records:
        return None
    if test_id:
        match = next(
            (record for record in records if record.get("test_id") == test_id),
            None,
        )
        if match is not None:
            return match
    return records[index] if index < len(records) else None


def summarize_execution_results(execution_results):
    total = len(execution_results)
    passed = sum(1 for result in execution_results if result.get("status") == "pass")
    failed = sum(1 for result in execution_results if result.get("status") == "fail")
    errors = sum(1 for result in execution_results if result.get("status") == "error")
    skipped = sum(1 for result in execution_results if result.get("status") == "skipped")
    if failed:
        status = "fail"
    elif errors:
        status = "error"
    elif total and passed + skipped == total:
        status = "pass"
    else:
        status = "not_executed"

    summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
    }
    aggregate_result = {
        "status": status,
        **summary,
        "failed_test_ids": [
            result.get("test_id")
            for result in execution_results
            if result.get("status") == "fail"
        ],
        "error_test_ids": [
            result.get("test_id")
            for result in execution_results
            if result.get("status") == "error"
        ],
        "duration": sum(result.get("duration", 0) for result in execution_results),
    }
    return summary, aggregate_result


def validate_requirement(state: WorkflowState) -> Dict[str, Any]:
    """Node 0: Validate that the requirement is not empty.

    Returns error if requirement is empty, otherwise proceeds.
    """
    if not state.requirement or not state.requirement.strip():
        error_msg = "Requirement cannot be empty."
        return {"errors": (state.errors or []) + [error_msg]}
    # If valid, return empty dict (no changes to state)
    return {}


def route_after_validation(state: WorkflowState) -> str:
    """Route validated requirements through requirement understanding."""
    if state.errors:
        return "end"
    return "understand_requirement"


def understand_requirement(state: WorkflowState) -> Dict[str, Any]:
    """Classify whether the requirement can be tested against the declared SUT."""
    context = state.sut_context or {}
    requirement = state.requirement.strip()
    requirement_lower = requirement.casefold()
    available_features = context.get("available_features", [])
    available_routes = context.get("available_routes", [])
    catalog_description = context.get("description", "")

    unsupported_feature = next(
        (
            feature
            for feature in context.get("unsupported_features", [])
            if isinstance(feature, str) and feature.casefold() in requirement_lower
        ),
        None,
    )
    broad_request = bool(
        re.fullmatch(
            r"(?:please\s+)?test\s+(?:the\s+)?(?:application|app)[.!]?",
            requirement,
            flags=re.IGNORECASE,
        )
    )

    if unsupported_feature:
        understanding = RequirementUnderstanding(
            feature=unsupported_feature,
            objective=requirement,
            expected_behavior="The requested feature is not implemented by this SUT.",
            status="unsupported",
            clarification_reason=(
                f"The SUT does not implement {unsupported_feature!r}. "
                f"Available features: {', '.join(available_features) or 'not specified'}."
            ),
        )
    elif broad_request:
        understanding = RequirementUnderstanding(
            feature="application",
            objective="Identify the specific application behavior to verify.",
            expected_behavior="Not specified.",
            ambiguities=["No feature, user action, or expected outcome was specified."],
            status="clarification_needed",
            clarification_reason=(
                "Please specify a feature, the user action, and the expected result. "
                f"The declared SUT routes are: {', '.join(available_routes) or 'not specified'}. "
                f"SUT description: {catalog_description or 'not provided'}."
            ),
        )
    else:
        prompt = f"""Determine whether this requirement is testable against the declared SUT.
Do not infer or invent routes, controls, credentials, or behavior.
Mark status testable only when a concrete behavior and expected result are identified
and are supported by this SUT context. Use clarification_needed for ambiguous or
underspecified requests and unsupported for features explicitly absent from the SUT.

Requirement:
{requirement}

Authoritative SUT context:
{json.dumps(context, indent=2, ensure_ascii=True)}

Return the required RequirementUnderstanding fields, including a useful clarification_reason
whenever status is not testable."""
        try:
            understanding = _get_llm_client().generate_structured(
                prompt, RequirementUnderstanding
            )
        except Exception as exc:
            return {
                "errors": (state.errors or []) + [f"understand_requirement: {exc}"]
            }

    result = {"requirement_understanding": understanding.model_dump()}
    if understanding.status != "testable":
        result["missing_context"] = {
            "status": understanding.status,
            "feature": understanding.feature,
            "reason": understanding.clarification_reason,
        }
    return result


def route_after_understanding(state: WorkflowState) -> str:
    understanding = state.requirement_understanding
    if state.errors or not understanding or understanding.get("status") != "testable":
        return "end"
    return "generate_test_scenarios"


def generate_test_case(state: WorkflowState) -> Dict[str, Any]:
    """Node 1: Convert requirement -> structured TestCase via LLM (backward compatibility).

    This node is kept for backward compatibility but is no longer used in the main flow.
    It generates a single test case from the requirement directly.
    """
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


def generate_test_scenarios(state: WorkflowState) -> Dict[str, Any]:
    """Node 1.5: Dynamically generate test scenarios from the requirement and its understanding.

    Uses the requirement_understanding if available and its status is "testable".
    Otherwise, returns empty scenario list.
    """
    # If requirement understanding indicates non-testable, return empty scenarios
    if state.requirement_understanding is not None:
        try:
            # Convert dict to RequirementUnderstanding model for easy access
            understanding = RequirementUnderstanding(**state.requirement_understanding)
            if understanding.status != "testable":
                # Preserve the understanding in state (no change)
                return {"test_scenarios": [], "test_cases": []}
        except Exception:
            # If parsing fails, fall back to using raw requirement
            pass

    # Prepare prompt for LLM
    req = state.requirement.strip()

    # Build context from requirement understanding if available
    context_parts = [f"Requirement: {req}"]
    if state.requirement_understanding:
        try:
            understanding = RequirementUnderstanding(**state.requirement_understanding)
            if understanding.status == "testable":
                context_parts.append("\nRequirement Understanding:")
                context_parts.append(f"- Feature: {understanding.feature}")
                context_parts.append(f"- Objective: {understanding.objective}")
                context_parts.append(f"- Actors: {', '.join(understanding.actors) if understanding.actors else 'None specified'}")
                context_parts.append(f"- Inputs: {', '.join(understanding.inputs) if understanding.inputs else 'None specified'}")
                context_parts.append(f"- Preconditions: {', '.join(understanding.preconditions) if understanding.preconditions else 'None specified'}")
                context_parts.append(f"- Expected Behavior: {understanding.expected_behavior}")
                context_parts.append(f"- Constraints: {', '.join(understanding.constraints) if understanding.constraints else 'None specified'}")
                context_parts.append(f"- Ambiguities: {', '.join(understanding.ambiguities) if understanding.ambiguities else 'None specified'}")
            pass
        except Exception:
            # If parsing fails, ignore understanding
            pass
    if state.sut_context:
        context_parts.append("\nAuthoritative SUT context:")
        context_parts.append(json.dumps(state.sut_context, indent=2, ensure_ascii=True))
    context = '\n'.join(context_parts)

    prompt = f"""
You are an expert software test engineer. Generate a list of test scenarios that comprehensively cover the given requirement.
Consider different aspects such as functional, negative, boundary, and security scenarios as appropriate.
Only generate scenarios if the requirement is testable; otherwise return an empty list.
Each scenario must include:
    - scenario_id: a short unique identifier (e.g., "scen_1", "func_1")
    - scenario_type: one of "functional", "negative", "boundary", "security"
    - title: a short, clear title summarizing the scenario
    - description: a detailed description of what the scenario covers
    - route: an implemented route from the authoritative SUT context, or null if none is specified
Do not invent implementation details or SUT-specific selectors, URLs, or credentials.
Only generate scenarios for features and routes explicitly described in the authoritative SUT context. If the requirement is broad, cover only listed implemented features. Do not create scenarios for unavailable or unsupported features.
The number of scenarios should depend on the requirement; do not force a fixed number.
Return a JSON object with a "scenarios" array containing the scenario objects. When the SUT context lists route-specific selectors, choose the route relevant to each scenario and use only its selectors.
Do not return the schema description - return actual scenario data.
\n\n{context}
"""

    try:
        llm_client = _get_llm_client()
        # Use json_schema method for consistent structured output with Groq
        result: ScenarioList = llm_client.generate_structured(prompt, ScenarioList)
        scenarios = [scenario.model_dump() for scenario in result.scenarios]
    except Exception as exc:
        # If LLM fails, return empty scenarios and optionally log error
        # We'll add an error to state so the workflow can handle it
        return {"errors": (state.errors or []) + [f"generate_test_scenarios: {exc}"], "test_scenarios": [], "test_cases": []}

    # Return ONLY test_scenarios, NOT test_cases (test_cases will be generated separately)
    return {"test_scenarios": scenarios}


def generate_test_cases_from_scenarios(state: WorkflowState) -> Dict[str, Any]:
    """Node 2: Generate structured test cases from each scenario.

    For each scenario in test_scenarios, generate a corresponding test case.
    Store all test cases in test_cases and set test_case to the first one (backward compatibility).
    """
    if not state.test_scenarios:
        return {"test_cases": [], "test_case": None}

    try:
        llm_client = _get_llm_client()
        generator = RequirementToTestCaseGenerator(llm_client=llm_client)
    except Exception as exc:
        return {"errors": (state.errors or []) + [f"generate_test_cases_from_scenarios: failed to initialize: {exc}"], "test_cases": [], "test_case": None}

    test_cases = []
    errors = list(state.errors or [])

    for scenario in state.test_scenarios:
        scenario_id = scenario.get("scenario_id", "unknown") if isinstance(scenario, dict) else getattr(scenario, "scenario_id", "unknown")
        try:
            # Generate test case from scenario
            test_case = generator.generate_from_scenario(
                requirement=state.requirement,
                requirement_understanding=state.requirement_understanding or {},
                scenario=scenario,
                test_data=state.test_data,
                sut_context=state.sut_context
            )
            test_cases.append(test_case.model_dump())
        except Exception as exc:
            # Record error for this scenario but continue with remaining scenarios
            errors.append(f"generate_test_cases_from_scenarios: scenario {scenario_id} failed: {exc}")
            continue

    # Set test_case to the first test case for backward compatibility
    first_test_case = test_cases[0] if test_cases else None
    test_case_generated = len(test_cases) > 0

    result = {"test_cases": test_cases, "test_case": first_test_case}
    if errors != list(state.errors or []):
        result["errors"] = errors
    return result


def generate_selenium_tests(state: WorkflowState) -> Dict[str, Any]:
    """Node 3: Convert TestCases -> Selenium pytest files via LLM.

    Processes ALL test cases in test_cases and generates Selenium tests for each.
    Maintains backward compatibility by setting singular fields to the first test case.
    """
    if not state.test_cases:
        return {"errors": (state.errors or []) + ["generate_selenium_tests: no test_cases in state"]}

    try:
        llm_client = _get_llm_client()
        agent = TestAutomationAgent(
            llm_client=llm_client,
            base_url=state.base_url,
            sut_id=state.sut_id,
            sut_context=state.sut_context,
            test_data=state.test_data
        )

        generated_test_codes = []
        first_generated_path = None
        first_generated_code = None

        # Generate Selenium test for each test case
        for test_case_dict in state.test_cases:
            # Reconstruct TestCase from dict
            test_case = TestCase(**test_case_dict)

            # Generate the test
            file_path = agent.generate_test(test_case)
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

            # Store the generated code and path for this test case
            generated_test_codes.append({
                "test_id": test_case.test_id,
                "scenario_id": test_case.scenario_id,
                "generated_test_path": file_path,
                "generated_test_code": code
            })

            # Set backward compatibility fields to the first successfully generated test
            if first_generated_path is None:
                first_generated_path = file_path
                first_generated_code = code

        # Update state with plural fields
        update_dict = {
            "generated_test_codes": generated_test_codes,
            "errors": state.errors or []  # Preserve existing errors
        }

        # Set backward compatibility singular fields (point to first test case)
        if first_generated_path is not None:
            update_dict["generated_test_path"] = first_generated_path
            update_dict["generated_test_code"] = first_generated_code

        return update_dict

    except Exception as exc:
        return {"errors": (state.errors or []) + [f"generate_selenium_tests: {exc}"]}


def execute_tests(state: WorkflowState) -> Dict[str, Any]:
    """Node 4: Execute ALL generated Selenium tests via ExecutionService.

    Executes each generated test and stores results in execution_results.
    Creates an aggregated execution_summary.
    Maintains backward compatibility by setting execution_result to the first test result.
    """
    if not state.generated_test_codes:
        return {"errors": (state.errors or []) + ["execute_tests: no generated_test_codes in state"]}

    sut_proc = None
    try:
        # Ensure the SUT is running before Selenium tries to connect
        sut_proc = _start_sut()

        execution_results = []
        first_execution_result = None

        # Execute each generated test
        for generated_test_info in state.generated_test_codes:
            file_path = generated_test_info["generated_test_path"]

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
                # Create error result for this test
                error_result = {
                    "status": "error",
                    "exception": {
                        "type": "ValueError",
                        "message": f"no test_ function found in generated file: {file_path}",
                        "traceback": ""
                    },
                    "duration": 0,
                    "screenshot": None,
                    "test_id": generated_test_info["test_id"],
                    "scenario_id": generated_test_info["scenario_id"]
                }
                execution_results.append(error_result)

                # Set backward compatibility to first error if not already set
                if first_execution_result is None:
                    first_execution_result = error_result
                continue

            try:
                with ExecutionService() as service:
                    result = service.execute_test(test_func)

                # Add test identification to the result
                result["test_id"] = generated_test_info["test_id"]
                result["scenario_id"] = generated_test_info["scenario_id"]
                execution_results.append(result)

                # Set backward compatibility to first result if not already set
                if first_execution_result is None:
                    first_execution_result = result

            except Exception as exc:
                # Create error result for this test
                error_result = {
                    "status": "error",
                    "exception": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "traceback": traceback.format_exc(),
                    },
                    "duration": 0,
                    "screenshot": None,
                    "test_id": generated_test_info["test_id"],
                    "scenario_id": generated_test_info["scenario_id"]
                }
                execution_results.append(error_result)

                # Set backward compatibility to first error if not already set
                if first_execution_result is None:
                    first_execution_result = error_result

        execution_summary, aggregate_execution_result = summarize_execution_results(
            execution_results
        )

        # Update state with plural fields
        update_dict = {
            "execution_results": execution_results,
            "execution_summary": execution_summary,
            "execution_result": aggregate_execution_result,
            "primary_execution_result": first_execution_result,
            "errors": state.errors or []  # Preserve existing errors
        }

        return update_dict

    except Exception as exc:
        return {
            "errors": (state.errors or []) + [f"execute_tests: {exc}"],
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
    """Node 5: Investigate test failure via FailureInvestigationAgent.

    Investigates the first failed/error test for backward compatibility.
    For multiple failures, investigates each and stores in failure_analyses.
    """
    # Check if we have execution results
    if not state.execution_results:
        # Fallback to singular execution_result for backward compatibility
        if state.execution_result is None:
            return {"errors": (state.errors or []) + ["investigate_failure: no execution results in state"]}

        # Check if the singular result indicates failure
        if state.execution_result.get("status") not in ["fail", "error"]:
            return {}  # No failure to investigate

        # Investigate the singular result (backward compatibility)
        try:
            llm_client = _get_llm_client()
            agent = FailureInvestigationAgent(llm_client=llm_client)

            # Extract from execution_result
            exec_result = state.execution_result
            exception = exec_result.get("exception") if exec_result else None
            # Prepare parameters for the investigate method
            analysis = agent.investigate(
                requirement=state.requirement,
                test_case=state.test_case,
                generated_test_code=state.generated_test_code,
                exception=exception,
                stdout=exec_result.get("stdout") if exec_result else None,
                stderr=exec_result.get("stderr") if exec_result else None,
                screenshot_path=exec_result.get("screenshot") if exec_result else None,
                execution_metadata=exec_result,
                retrieved_knowledge=state.retrieved_knowledge,
                test_id=exec_result.get("test_id") if exec_result else None,
                scenario_id=exec_result.get("scenario_id") if exec_result else None,
                base_url=state.base_url,
                sut_id=state.sut_id,
                sut_context=state.sut_context,
            )
            return {"failure_analysis": analysis.model_dump() if hasattr(analysis, 'model_dump') else analysis}
        except Exception as exc:
            return {"errors": (state.errors or []) + [f"investigate_failure: {exc}"]}

    # We have execution_results - check for failures/errors
    failed_tests = [r for r in state.execution_results if r.get("status") in ["fail", "error"]]
    if not failed_tests:
        return {}  # No failures to investigate

    try:
        llm_client = _get_llm_client()
        agent = FailureInvestigationAgent(llm_client=llm_client)

        failure_analyses = []
        first_failure_analysis = None

        # Investigate each failed/error test
        for execution_result in failed_tests:
            # Find the corresponding test case
            test_case_dict = None
            if state.test_cases:
                for tc in state.test_cases:
                    if tc.get("test_id") == execution_result.get("test_id"):
                        test_case_dict = tc
                        break

            # Find the corresponding generated test code
            generated_test_code = None
            if state.generated_test_codes:
                for gt in state.generated_test_codes:
                    if gt.get("test_id") == execution_result.get("test_id"):
                        generated_test_code = gt.get("generated_test_code")
                        break

            # Extract from execution_result
            exception = execution_result.get("exception") if execution_result else None
            # Prepare parameters for the investigate method
            analysis = agent.investigate(
                requirement=state.requirement,
                test_case=test_case_dict,
                generated_test_code=generated_test_code,
                exception=exception,
                stdout=execution_result.get("stdout") if execution_result else None,
                stderr=execution_result.get("stderr") if execution_result else None,
                screenshot_path=execution_result.get("screenshot") if execution_result else None,
                execution_metadata=execution_result,
                retrieved_knowledge=state.retrieved_knowledge,
                test_id=execution_result.get("test_id") if execution_result else None,
                scenario_id=execution_result.get("scenario_id") if execution_result else None,
                base_url=state.base_url,
                sut_id=state.sut_id,
                sut_context=state.sut_context,
            )
            analysis_dict = analysis.model_dump() if hasattr(analysis, 'model_dump') else analysis
            analysis_dict.update({
                "test_id": execution_result.get("test_id"),
                "scenario_id": execution_result.get("scenario_id"),
            })
            failure_analyses.append(analysis_dict)

            # Set backward compatibility to first failure analysis
            if first_failure_analysis is None:
                first_failure_analysis = analysis_dict

        # Update state with plural fields
        update_dict = {
            "failure_analyses": failure_analyses,
            "errors": state.errors or []  # Preserve existing errors
        }

        # Set backward compatibility singular field (point to first failure analysis)
        if first_failure_analysis is not None:
            update_dict["failure_analysis"] = first_failure_analysis

        return update_dict

    except Exception as exc:
        return {"errors": (state.errors or []) + [f"investigate_failure: {exc}"]}


def verify_failure(state: WorkflowState) -> Dict[str, Any]:
    """Node 6: Verify failure investigation via VerificationAgent.

    Verifies the first failure analysis for backward compatibility.
    For multiple failures, verifies each and stores in verification_results.
    """
    # Check if we have failure analyses
    if not state.failure_analyses:
        # Fallback to singular failure_analysis for backward compatibility
        if state.failure_analysis is None:
            return {"errors": (state.errors or []) + ["verify_failure: no failure analyses in state"]}

        # Verify the singular result (backward compatibility)
        try:
            llm_client = _get_llm_client()
            agent = VerificationAgent(llm_client=llm_client)

            verification = agent.verify(
                requirement=state.requirement,
                test_case=state.test_case,
                generated_test_code=state.generated_test_code,
                execution_result=state.execution_result,
                failure_analysis=state.failure_analysis,
                test_id=state.test_case.get("test_id") if state.test_case else None,
                scenario_id=state.test_case.get("scenario_id") if state.test_case else None,
                base_url=state.base_url,
                sut_id=state.sut_id,
                sut_context=state.sut_context,
            )
            return {"verification_result": verification.model_dump() if hasattr(verification, 'model_dump') else verification}
        except Exception as exc:
            return {"errors": (state.errors or []) + [f"verify_failure: {exc}"]}

    # We have failure_analyses - verify each one
    try:
        llm_client = _get_llm_client()
        agent = VerificationAgent(llm_client=llm_client)

        verification_results = []
        first_verification_result = None

        # Verify each failure analysis
        for i, failure_analysis in enumerate(state.failure_analyses):
            # Find corresponding test case, generated test code, and execution result
            test_id = failure_analysis.get("test_id")
            test_case_dict = _find_correlated_record(state.test_cases, test_id, i)
            generated_test_info = _find_correlated_record(
                state.generated_test_codes, test_id, i
            )
            execution_result = _find_correlated_record(
                state.execution_results, test_id, i
            )
            generated_test_code = (
                generated_test_info.get("generated_test_code")
                if generated_test_info else None
            )

            verification = agent.verify(
                requirement=state.requirement,
                test_case=test_case_dict,
                generated_test_code=generated_test_code,
                execution_result=execution_result,
                failure_analysis=failure_analysis,
                test_id=test_case_dict.get("test_id") if test_case_dict else None,
                scenario_id=test_case_dict.get("scenario_id") if test_case_dict else None,
                base_url=state.base_url,
                sut_id=state.sut_id,
                sut_context=state.sut_context,
            )
            verification_dict = verification.model_dump() if hasattr(verification, 'model_dump') else verification
            verification_dict.update({
                "test_id": test_id or (test_case_dict or {}).get("test_id"),
                "scenario_id": (test_case_dict or {}).get("scenario_id")
                or failure_analysis.get("scenario_id"),
            })
            verification_results.append(verification_dict)

            # Set backward compatibility to first verification result
            if first_verification_result is None:
                first_verification_result = verification_dict

        # Update state with plural fields
        update_dict = {
            "verification_results": verification_results,
            "errors": state.errors or []  # Preserve existing errors
        }

        # Set backward compatibility singular field (point to first verification result)
        if first_verification_result is not None:
            update_dict["verification_result"] = first_verification_result

        return update_dict

    except Exception as exc:
        return {"errors": (state.errors or []) + [f"verify_failure: {exc}"]}


def generate_bug_report(state: WorkflowState) -> Dict[str, Any]:
    """Node 8: Generate bug report via BugReportAgent.

    Generates bug report for the first failed/error test for backward compatibility.
    For multiple failures, generates bug report for each and stores in bug_reports.
    """
    # Check if we have verification results (needed for bug report)
    if not state.verification_results:
        # Fallback to singular verification_result for backward compatibility
        if state.verification_result is None:
            return {"errors": (state.errors or []) + ["generate_bug_report: no verification results in state"]}

        # Generate bug report for the singular verification (backward compatibility)
        try:
            llm_client = _get_llm_client()
            agent = BugReportAgent(llm_client=llm_client)

            bug_report = agent.generate(
                requirement=state.requirement,
                test_case=state.test_case,
                execution_result=state.execution_result,
                failure_analysis=state.failure_analysis,
                verification_result=state.verification_result,
                retrieved_knowledge=state.retrieved_knowledge
            )
            return {"bug_report": bug_report}
        except Exception as exc:
            return {"errors": (state.errors or []) + [f"generate_bug_report: {exc}"]}

    # We have verification_results - generate bug report for each one
    try:
        llm_client = _get_llm_client()
        agent = BugReportAgent(llm_client=llm_client)

        bug_reports = []
        first_bug_report = None

        # Generate bug report for each verification result
        for i, verification_result in enumerate(state.verification_results):
            # Find corresponding test case, failure analysis, and execution result
            test_id = verification_result.get("test_id")
            test_case_dict = _find_correlated_record(state.test_cases, test_id, i)
            failure_analysis_dict = _find_correlated_record(
                state.failure_analyses, test_id, i
            )
            execution_result_dict = _find_correlated_record(
                state.execution_results, test_id, i
            )

            bug_report = agent.generate(
                requirement=state.requirement,
                test_case=test_case_dict,
                execution_result=execution_result_dict,
                failure_analysis=failure_analysis_dict,
                verification_result=verification_result,
                retrieved_knowledge=state.retrieved_knowledge
            )
            bug_reports.append(bug_report)

            # Set backward compatibility to first bug report
            if first_bug_report is None:
                first_bug_report = bug_report

        # Update state with plural fields
        update_dict = {
            "bug_reports": bug_reports,
            "errors": state.errors or []  # Preserve existing errors
        }

        # Set backward compatibility singular field (point to first bug report)
        if first_bug_report is not None:
            update_dict["bug_report"] = first_bug_report

        return update_dict

    except Exception as exc:
        return {"errors": (state.errors or []) + [f"generate_bug_report: {exc}"]}


def generate_regression_test(state: WorkflowState) -> Dict[str, Any]:
    """Node 7: Generate regression test via RegressionTestAgent.

    Generates regression test for the first failed/error test for backward compatibility.
    For multiple failures, generates regression test for each and stores in regression_tests.
    """
    # Check if we have failure analyses
    if not state.failure_analyses:
        # Fallback to singular failure_analysis for backward compatibility
        if state.failure_analysis is None:
            return {"errors": (state.errors or []) + ["generate_regression_test: no failure analyses in state"]}

        # Generate regression test for the singular failure (backward compatibility)
        try:
            llm_client = _get_llm_client()
            agent = RegressionTestAgent(llm_client=llm_client)

            test_case = agent.generate(
                requirement=state.requirement,
                test_case=state.test_case,
                failure_analysis=state.failure_analysis,
                verification_result=state.verification_result
            )
            return {"regression_test": test_case.model_dump() if hasattr(test_case, 'model_dump') else test_case}
        except Exception as exc:
            return {"errors": (state.errors or []) + [f"generate_regression_test: {exc}"]}

    # We have failure_analyses - generate regression test for each one
    try:
        llm_client = _get_llm_client()
        agent = RegressionTestAgent(llm_client=llm_client)

        regression_tests = []
        first_regression_test = None

        # Generate regression test for each failure analysis
        for i, failure_analysis in enumerate(state.failure_analyses):
            # Find corresponding test case and verification result
            test_id = failure_analysis.get("test_id")
            test_case_dict = _find_correlated_record(state.test_cases, test_id, i)
            verification_result = _find_correlated_record(
                state.verification_results, test_id, i
            )
            if not verification_result or verification_result.get("verdict") != "confirmed":
                continue

            test_case = agent.generate(
                requirement=state.requirement,
                test_case=test_case_dict,
                failure_analysis=failure_analysis,
                verification_result=verification_result
            )
            test_case_dict = test_case.model_dump() if hasattr(test_case, 'model_dump') else test_case
            regression_tests.append(test_case_dict)

            # Set backward compatibility to first regression test
            if first_regression_test is None:
                first_regression_test = test_case_dict

        # Update state with plural fields
        update_dict = {
            "regression_tests": regression_tests,
            "errors": state.errors or []  # Preserve existing errors
        }

        # Set backward compatibility singular field (point to first regression test)
        if first_regression_test is not None:
            update_dict["regression_test"] = first_regression_test
        else:
            update_dict["regression_test"] = None

        return update_dict

    except Exception as exc:
        return {"errors": (state.errors or []) + [f"generate_regression_test: {exc}"]}


def execute_test(state: WorkflowState) -> Dict[str, Any]:
    """Node 8: Execute the generated Selenium test via ExecutionService (BACKWARD COMPATIBILITY).

    This node is kept for backward compatibility but is no longer used in the main flow.
    It executes a single test from the generated_test_path.
    """
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


def build_workflow():
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("validate_requirement", validate_requirement)
    workflow.add_node("understand_requirement", understand_requirement)
    workflow.add_node("generate_test_scenarios", generate_test_scenarios)
    workflow.add_node("generate_test_cases_from_scenarios", generate_test_cases_from_scenarios)
    workflow.add_node("generate_test_case", generate_test_case)  # Kept for backward compatibility
    workflow.add_node("generate_selenium_tests", generate_selenium_tests)  # Changed to plural
    workflow.add_node("execute_tests", execute_tests)  # Changed to plural
    workflow.add_node("execute_test", execute_test)  # Kept for backward compatibility
    workflow.add_node("investigate_failure", investigate_failure)
    workflow.add_node("verify_failure", verify_failure)
    workflow.add_node("generate_regression_test", generate_regression_test)
    workflow.add_node("generate_bug_report", generate_bug_report)

    # Set entry point
    workflow.set_entry_point("validate_requirement")

    # Add edges
    workflow.add_conditional_edges(
        "validate_requirement",
        route_after_validation,
        {
            "understand_requirement": "understand_requirement",
            "end": END
        }
    )

    workflow.add_conditional_edges(
        "understand_requirement",
        route_after_understanding,
        {
            "generate_test_scenarios": "generate_test_scenarios",
            "end": END,
        },
    )

    # Main flow: scenarios -> test cases -> selenium tests -> execution
    workflow.add_edge("generate_test_scenarios", "generate_test_cases_from_scenarios")
    workflow.add_edge("generate_test_cases_from_scenarios", "generate_selenium_tests")
    workflow.add_edge("generate_selenium_tests", "execute_tests")

    # Conditional edges after execution
    workflow.add_conditional_edges(
        "execute_tests",
        lambda state: "investigate_failure" if state.execution_summary and state.execution_summary.get("failed", 0) > 0 or state.execution_summary and state.execution_summary.get("errors", 0) > 0 else "end",
        {
            "investigate_failure": "investigate_failure",
            "end": END
        }
    )

    # Failure handling flow
    workflow.add_edge("investigate_failure", "verify_failure")
    workflow.add_edge("verify_failure", "generate_bug_report")
    workflow.add_edge("generate_bug_report", "generate_regression_test")
    workflow.add_edge("generate_regression_test", END)

    # Compile and return
    return workflow.compile()