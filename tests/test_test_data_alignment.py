from app.requirement_to_testcase.generator import RequirementToTestCaseGenerator
from app.requirement_to_testcase.schema import TestCase as CaseModel
from app.test_automation_agent.service import TestAutomationAgent
from app.workflow import graph
from app.workflow.state import WorkflowState
from unittest.mock import Mock


def _test_case(test_type="functional"):
    return CaseModel(
        test_id="tc_sample",
        scenario_id="scenario_sample",
        title="Sample test",
        description="Sample description",
        steps=["Enter the name and submit"],
        expected_result="The expected result is shown",
        test_type=test_type,
        priority="medium",
    )


def test_empty_input_scenario_overrides_supplied_name():
    test_case = _test_case("negative")

    RequirementToTestCaseGenerator._align_scenario_test_data(
        object.__new__(RequirementToTestCaseGenerator),
        test_case,
        {"title": "Empty name input", "description": "Submit with a blank name"},
        {"name": "Alice"},
        {"name_selector": "#name"},
    )

    assert [(item.key, item.value) for item in test_case.test_data] == [("name", "")]


def test_boundary_test_data_matches_declared_character_limit():
    test_case = _test_case("boundary")

    RequirementToTestCaseGenerator._align_scenario_test_data(
        object.__new__(RequirementToTestCaseGenerator),
        test_case,
        {"title": "Maximum length name", "description": "Enter 255 characters"},
        {"name": "Alice"},
        {"name_selector": "#name"},
    )

    assert len(test_case.test_data[0].value) == 255


def test_special_character_data_uses_scenario_example():
    test_case = _test_case("boundary")

    RequirementToTestCaseGenerator._align_scenario_test_data(
        object.__new__(RequirementToTestCaseGenerator),
        test_case,
        {
            "title": "Unicode and special characters",
            "description": 'Use the name e.g., "Zoë O\'Neill 🚀"',
        },
        {},
        {"name_selector": "#name"},
    )

    assert test_case.test_data[0].value == "Zoë O'Neill 🚀"


def test_unsupported_feature_is_rejected_from_sut_catalog():
    state = WorkflowState(
        requirement="Verify that the profile works correctly.",
        sut_context={
            "available_routes": ["/login", "/dashboard", "/logout", "/hello"],
            "unsupported_features": ["profile"],
        },
    )

    result = graph.validate_requirement(state)

    assert result["missing_context"]["status"] == "unsupported"
    assert result["errors"] == [
        "Requested feature 'profile' is not implemented by this SUT."
    ]


def test_scenario_prompt_uses_authoritative_sut_catalog(monkeypatch):
    class ScenarioClient:
        prompt = ""

        def generate_structured(self, prompt, schema):
            self.prompt = prompt
            return schema(scenarios=[])

    client = ScenarioClient()
    monkeypatch.setattr(graph, "_get_llm_client", lambda: client)
    state = WorkflowState(
        requirement="Test the application",
        sut_context={
            "available_routes": ["/login", "/dashboard", "/logout", "/hello"],
            "available_features": ["login", "dashboard", "hello greeting"],
        },
    )

    result = graph.generate_test_scenarios(state)

    assert result["test_scenarios"] == []
    assert "/dashboard" in client.prompt
    assert "Only generate scenarios for features and routes explicitly described" in client.prompt


def test_automation_uses_route_specific_selectors_and_rejects_unknown_routes():
    agent = TestAutomationAgent(
        llm_client=Mock(),
        base_url="http://127.0.0.1:8001",
        sut_context={
            "routes": {
                "/login": {
                    "username_selector": "#username",
                    "password_selector": "#password",
                    "submit_selector": "#login_button",
                }
            }
        },
    )
    login_case = CaseModel(
        test_id="tc_login",
        scenario_id="login",
        route="/login",
        title="Login route selectors",
        description="Use the actual login controls",
        steps=["Click login"],
        expected_result="The login control is available",
        test_type="functional",
        priority="high",
    )

    assert agent._build_target_url(login_case) == "http://127.0.0.1:8001/login"
    agent._validate_code(
        'def test_login(driver):\n    assert driver.find_element(By.CSS_SELECTOR, "#username").is_displayed()',
        login_case,
    )

    unsupported_case = login_case.model_copy(update={"route": "/profile"})
    try:
        agent._build_target_url(unsupported_case)
    except ValueError as error:
        assert "not in the SUT route catalog" in str(error)
    else:
        raise AssertionError("an unknown route should be rejected")