"""
API integration tests for the multi-tenant backend.

Exercises the HTTP surface end-to-end (FastAPI TestClient) with the Algorand + IPFS
layer mocked, so it's deterministic and needs no testnet: API-key auth (401/200),
the ingest pipeline producing a stored record, dashboard aggregation, and the
verify (pending) path. Policy correctness itself is covered by test_policy_engine.
"""

import hashlib
import os
import tempfile
from collections import deque

import pytest
from fastapi.testclient import TestClient

import api.main as m
import sdk.audit_flow_v2 as flow
from algorand.contract_client_v2 import MODE_ONCHAIN, OP_IN, OP_LT, PolicyCheckResult
from batcher.store import BatchStore
from crypto.payload import generate_key
from tenancy.store import TenantStore

API_KEY = "aa_test_key_123"


@pytest.fixture
def client(monkeypatch):
    d = tempfile.mkdtemp()
    ts = TenantStore(db_path=os.path.join(d, "tenants.db"))
    bs = BatchStore(db_path=os.path.join(d, "batcher.db"))

    ts.create_org("testorg", hashlib.sha256(API_KEY.encode()).hexdigest(), generate_key())
    ts.add_agent("testorg", "agentx")
    ts.add_rule("testorg", "agentx", 0, MODE_ONCHAIN, OP_LT, 5000, "amount", "", "")
    ts.add_rule("testorg", "agentx", 1, MODE_ONCHAIN, OP_IN, 0, "vendor", "", "")

    monkeypatch.setattr(m, "tenant_store", ts)
    monkeypatch.setattr(m, "batch_store", bs)
    monkeypatch.setattr(m, "recent_audits", deque(maxlen=50))

    async def fake_upload(data, name=""):
        return "QmTESTCID"

    async def fake_check(*args, **kwargs):
        return PolicyCheckResult("TX_TEST", "pass:onchain|pass:onchain", True)

    monkeypatch.setattr(flow, "upload_to_ipfs", fake_upload)
    monkeypatch.setattr(flow, "submit_policy_check", fake_check)

    return TestClient(m.app)


def _body(amount=4500, vendor="VENDOR_001"):
    return {
        "agent_id": "agentx",
        "action": "approve_payment",
        "decision": "approved",
        "fields": {"amount": amount, "vendor": vendor},
    }


def test_ingest_requires_auth(client):
    r = client.post("/v1/audit", json=_body())
    assert r.status_code == 401


def test_ingest_rejects_bad_key(client):
    r = client.post("/v1/audit", headers={"Authorization": "Bearer not-a-real-key"}, json=_body())
    assert r.status_code == 401


def test_ingest_success_and_dashboard(client):
    r = client.post("/v1/audit", headers={"Authorization": f"Bearer {API_KEY}"}, json=_body())
    assert r.status_code == 200
    j = r.json()
    assert j["decision"] == "approved"
    assert j["asa_minted"] is True
    assert j["action_id"]
    assert j["org_id"] == "testorg"

    dash = client.get("/api/dashboard").json()
    assert dash["total_audits"] == 1
    assert dash["pending_leaves_count"] == 1


def test_verify_pending_path(client):
    r = client.post("/v1/audit", headers={"Authorization": f"Bearer {API_KEY}"}, json=_body())
    action_id = r.json()["action_id"]

    v = client.get(f"/api/verify?action_id={action_id}").json()
    assert v["anchor_status"] == "pending"
    assert v["record_summary"]["fields"]["amount"] == 4500


def test_verify_unknown_action_404(client):
    assert client.get("/api/verify?action_id=does_not_exist").status_code == 404


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
