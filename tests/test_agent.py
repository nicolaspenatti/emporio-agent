"""Agent safeguards that must hold no matter what the model decides.

These tests call the tool dispatcher directly, so they need no API key.
"""

import pytest

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
