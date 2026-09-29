import pytest
from fastapi.testclient import TestClient

from demo_app.main import app


@pytest.mark.parametrize(
    ("name", "expected_greeting"),
    [("", "Hello, Stranger!"), ("Alice", "Hello, Alice!")],
)
def test_hello_form_greeting(name, expected_greeting):
    response = TestClient(app).post("/hello", data={"name": name})

    assert response.status_code == 200
    assert expected_greeting in response.text