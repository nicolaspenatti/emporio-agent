"""Agent safeguards that must hold no matter what the model decides.

These tests call the tool dispatcher directly, so they need no API key.
"""

from unittest.mock import MagicMock

import httpx
import pytest
from google.genai import errors

from emporio_agent.agent import MAX_FAILED_ORDER_LOOKUPS, Agent
from emporio_agent.data import load_store


@pytest.fixture
def agent():
    return Agent(api_key="test", model="test-model")


def test_order_lookups_are_blocked_after_too_many_failures(agent):
    real_email = load_store().customers[3].email
    for order_id in range(1, MAX_FAILED_ORDER_LOOKUPS + 1):
        assert agent._run_tool("get_order", {"order_id": order_id, "email": "intruso@x.com"})["found"] is False

    # Even the right e-mail is refused once the limit is reached.
    blocked = agent._run_tool("get_order", {"order_id": 1, "email": real_email})
    assert blocked["found"] is False
    assert blocked["blocked"] is True


def test_successful_lookups_do_not_count_as_failures(agent):
    real_email = load_store().customers[3].email
    for _ in range(MAX_FAILED_ORDER_LOOKUPS + 2):
        assert agent._run_tool("get_order", {"order_id": 1, "email": real_email})["found"] is True


def test_new_conversation_resets_the_limit(agent):
    for _ in range(MAX_FAILED_ORDER_LOOKUPS):
        agent._run_tool("get_order", {"order_id": 1, "email": "intruso@x.com"})
    agent.reset()
    assert "blocked" not in agent._run_tool("get_order", {"order_id": 1, "email": "intruso@x.com"})


def test_invalid_tool_arguments_return_error_instead_of_crashing(agent):
    assert "error" in agent._run_tool("get_order", {"order_id": 1})
    assert "error" in agent._run_tool("nao_existe", {})


# --- Fallback model ---------------------------------------------------------------

def agent_with_fake_api(failure: Exception) -> tuple[Agent, list[str]]:
    agent = Agent(api_key="test", model="main", fallback_model="backup")
    calls: list[str] = []

    def generate_content(model, contents, config):
        calls.append(model)
        if model == "main":
            raise failure
        return "response"

    agent.client = MagicMock()
    agent.client.models.generate_content.side_effect = generate_content
    return agent, calls


def test_slow_main_model_switches_to_fallback_without_retrying():
    agent, calls = agent_with_fake_api(httpx.ReadTimeout("slow"))
    assert agent._generate() == ("response", "backup")
    assert calls == ["main", "backup"]


def test_overloaded_main_model_is_retried_once_before_fallback(monkeypatch):
    monkeypatch.setattr("emporio_agent.agent.time.sleep", lambda _: None)
    overloaded = errors.ServerError(503, {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}})
    agent, calls = agent_with_fake_api(overloaded)
    assert agent._generate() == ("response", "backup")
    assert calls == ["main", "main", "backup"]


def test_unknown_main_model_switches_to_fallback_without_retrying():
    retired = errors.ClientError(404, {"error": {"code": 404, "message": "no longer available", "status": "NOT_FOUND"}})
    agent, calls = agent_with_fake_api(retired)
    assert agent._generate() == ("response", "backup")
    assert calls == ["main", "backup"]


def test_other_client_errors_are_not_hidden():
    bad_request = errors.ClientError(400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}})
    agent, calls = agent_with_fake_api(bad_request)
    with pytest.raises(errors.ClientError):
        agent._generate()
    assert calls == ["main"]
