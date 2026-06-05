"""
Unit tests for the AgentAudit SDK client (agentaudit/client.py).

Covers billing-mode selection and guards only — no network. The actual audit() HTTP
calls (api-key and x402) are exercised by the live runs / integration tests.
"""

import pytest

from agentaudit import AuditClient

WORDS = "word " * 25  # placeholder mnemonic (mode selection doesn't parse it)


def test_api_key_mode():
    assert AuditClient(api_key="aa_test").billing == "api_key"


def test_x402_mode():
    assert AuditClient(org_id="medico", x402_mnemonic=WORDS).billing == "x402"


def test_no_credentials_raises():
    with pytest.raises(ValueError):
        AuditClient()


def test_x402_requires_org_id():
    with pytest.raises(ValueError):
        AuditClient(x402_mnemonic=WORDS)


def test_base_url_trailing_slash_stripped():
    assert AuditClient(api_key="k", base_url="http://host:8000/").base_url == "http://host:8000"


def test_capture_rejects_bad_return_shape():
    client = AuditClient(api_key="k")

    @client.capture(agent_id="a", action="approve")
    def bad():
        return "not a dict"

    with pytest.raises(ValueError):
        bad()  # raises before any network call
