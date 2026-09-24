"""Run the LangGraph testing workflow end-to-end.

Usage:
    python -m app.workflow.run

Requires the SUT to be running at the TEST_APP_URL (default http://127.0.0.1:8001)
"""
import json
import os
import sys

from app.workflow.graph import build_workflow


def main():
    requirement = "The system shall allow users to log in with valid credentials."

    print("=" * 70)
    print("LangGraph Testing Workflow")
    print("=" * 70)
    print(f"Requirement : {requirement}")
    _sut_url = os.getenv("TEST_APP_URL", "http://127.0.0.1:8001")
    print(f"SUT         : {_sut_url}/login")
    print("-" * 70)

    workflow = build_workflow()

    # Invoke the compiled workflow
    final_state = workflow.invoke({"requirement": requirement})

    # --- Report results ---
    print("\n" + "=" * 70)
    print("WORKFLOW RESULT")
    print("=" * 70)

    # Test case
    if final_state.get("test_case"):
        tc = final_state["test_case"]
        print(f"\n[1] Test Case Generated:")
        print(f"    ID    : {tc.get('test_id')}")
        print(f"    Title : {tc.get('title')}")
        print(f"    Steps : {len(tc.get('steps', []))}")
    else:
        print("\n[1] Test Case: FAILED (see errors)")

    # Generated test
    if final_state.get("generated_test_path"):
        print(f"\n[2] Selenium Test Generated:")
        print(f"    File  : {final_state['generated_test_path']}")
    else:
        print("\n[2] Selenium Test: FAILED (see errors)")

    # Execution result
    result = final_state.get("execution_result")
    if result:
        status = result.get("status", "unknown")
        duration = result.get("duration", 0)
        print(f"\n[3] Execution Result:")
        print(f"    Status   : {status.upper()}")
        print(f"    Duration : {duration:.2f}s")
        if status == "fail" and result.get("exception"):
            exc = result["exception"]
            print(f"    Error    : {exc.get('type')}: {exc.get('message')}")
            if result.get("screenshot"):
                print(f"    Screenshot: {result['screenshot']}")
    else:
        print("\n[3] Execution: NOT REACHED (see errors)")

    # Failure investigation
    analysis = final_state.get("failure_analysis")
    if analysis:
        print(f"\n[4] Failure Investigation:")
        print(f"    Summary    : {analysis.get('failure_summary')}")
        print(f"    Root Cause : {analysis.get('probable_root_cause')}")
        print(f"    Severity   : {analysis.get('severity')}")
        print(f"    Owner      : {analysis.get('suggested_owner')}")
        print(f"    Confidence : {analysis.get('confidence')}")
        evidence = analysis.get("evidence", [])
        if evidence:
            print(f"    Evidence:")
            for ev in evidence:
                print(f"      - {ev}")
    elif result and result.get("status") != "pass":
        print("\n[4] Failure Investigation: SKIPPED (see errors)")
    else:
        print("\n[4] Failure Investigation: not needed (test passed)")

    # Verification result
    verification = final_state.get("verification_result")
    if verification:
        print(f"\n[5] Verification:")
        print(f"    Verdict  : {verification.get('verdict', 'unknown').upper()}")
        print(f"    Reasoning: {verification.get('reasoning')}")
        print(f"    Action   : {verification.get('recommended_action')}")
        gaps = verification.get("evidence_gaps", [])
        if gaps:
            print(f"    Gaps:")
            for gap in gaps:
                print(f"      - {gap}")
    elif result and result.get("status") != "pass":
        print("\n[5] Verification: SKIPPED (see errors)")
    else:
        print("\n[5] Verification: not needed (test passed)")

    # Errors
    errors = final_state.get("errors", [])
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")

    print("\n" + "=" * 70)

    # Exit code
    if result and result.get("status") == "pass":
        print("[PASS] Workflow completed - Selenium test passed against the SUT.")
        sys.exit(0)
    else:
        print("[FAIL] Workflow completed with failures.")
        sys.exit(1)


if __name__ == "__main__":
    main()
