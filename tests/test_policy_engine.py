"""
Unit tests for the multi-tenant policy engine (tenancy/provisioning.py).

These exercise the off-chain logic only (no Algorand calls): rules are inserted into a
temp TenantStore directly, mirroring what register_* would persist on-chain.
"""

import json
import os
import tempfile

from algorand.contract_client_v2 import (
    MODE_ATTESTED,
    MODE_ONCHAIN,
    OP_IN,
    OP_LE,
    OP_LT,
    OP_NOT_IN,
)
from crypto.payload import encrypt_payload, generate_key, parse_hex_key
from tenancy.provisioning import (
    _eval_doc,
    _eval_numeric,
    build_check_args,
    policy_commitment,
    reverify_mode2,
)
from tenancy.store import TenantStore

KEY_HEX = generate_key()
KEY = parse_hex_key(KEY_HEX)


def _store(org: str = "acme") -> TenantStore:
    d = tempfile.mkdtemp()
    s = TenantStore(db_path=os.path.join(d, "tenants.db"))
    s.create_org(org, "apikeyhash", KEY_HEX)
    s.add_agent(org, "ag")
    return s


def _doc_cipher(doc: dict) -> str:
    return json.dumps(encrypt_payload(doc, key=KEY))


# -- pure evaluators --------------------------------------------------------


def test_eval_numeric():
    assert _eval_numeric(OP_LT, 3, 5) is True
    assert _eval_numeric(OP_LT, 5, 5) is False
    assert _eval_numeric(OP_LE, 5, 5) is True


def test_eval_doc_set():
    in_doc = {"field": "v", "operator": OP_IN, "members": ["A", "B"]}
    assert _eval_doc(in_doc, "A") is True
    assert _eval_doc(in_doc, "C") is False
    not_doc = {"field": "v", "operator": OP_NOT_IN, "members": ["A"]}
    assert _eval_doc(not_doc, "C") is True
    assert _eval_doc(not_doc, "A") is False


# -- build_check_args -------------------------------------------------------


def test_build_check_args_alignment_and_mode2():
    s = _store()
    s.add_rule("acme", "ag", 0, MODE_ONCHAIN, OP_LT, 5000, "amount", "", "")
    s.add_rule("acme", "ag", 1, MODE_ONCHAIN, OP_IN, 0, "vendor", "", "")
    risk_doc = {"field": "risk", "operator": OP_LE, "value_num": 3}
    s.add_rule("acme", "ag", 2, MODE_ATTESTED, 0, 0, "risk", policy_commitment(risk_doc), _doc_cipher(risk_doc))

    a = build_check_args(s, "acme", "ag", {"amount": 4500, "vendor": "V1", "risk": 2})
    assert a["fields"] == ["amount", "vendor", "risk"]
    assert a["values_num"][0] == 4500
    assert a["values_str"][1] == "V1"
    assert a["attested"][2] is True  # private risk 2 <= 3

    a_fail = build_check_args(s, "acme", "ag", {"amount": 4500, "vendor": "V1", "risk": 5})
    assert a_fail["attested"][2] is False  # 5 <= 3 is False


# -- reverify_mode2 ---------------------------------------------------------


def test_reverify_threshold_and_set():
    s = _store("bank")
    risk_doc = {"field": "risk", "operator": OP_LE, "value_num": 3}
    set_doc = {"field": "bankid", "operator": OP_IN, "members": ["X", "Y"]}
    s.add_rule("bank", "ag", 0, MODE_ATTESTED, 0, 0, "risk", policy_commitment(risk_doc), _doc_cipher(risk_doc))
    s.add_rule("bank", "ag", 1, MODE_ATTESTED, 0, 0, "bankid", policy_commitment(set_doc), _doc_cipher(set_doc))

    ok = reverify_mode2(s, "bank", "ag", {"risk": 2, "bankid": "X"}, KEY)
    assert all(r["commitment_matches"] for r in ok)
    assert ok[0]["recheck_pass"] is True and ok[1]["recheck_pass"] is True

    bad = reverify_mode2(s, "bank", "ag", {"risk": 9, "bankid": "Z"}, KEY)
    assert bad[0]["recheck_pass"] is False and bad[1]["recheck_pass"] is False


def test_reverify_wrong_key_cannot_decrypt():
    s = _store("c")
    doc = {"field": "risk", "operator": OP_LE, "value_num": 3}
    s.add_rule("c", "ag", 0, MODE_ATTESTED, 0, 0, "risk", policy_commitment(doc), _doc_cipher(doc))
    res = reverify_mode2(s, "c", "ag", {"risk": 2}, parse_hex_key("11" * 32))
    assert res[0]["commitment_matches"] is False
    assert res[0]["recheck_pass"] is None


# -- multi-tenant isolation -------------------------------------------------


def test_org_isolation_rule_sets():
    s = _store("o1")
    s.create_org("o2", "h2", KEY_HEX)
    s.add_agent("o2", "ag")
    s.add_rule("o1", "ag", 0, MODE_ONCHAIN, OP_LT, 100, "amount", "", "")
    s.add_rule("o1", "ag", 1, MODE_ONCHAIN, OP_IN, 0, "vendor", "", "")
    s.add_rule("o2", "ag", 0, MODE_ONCHAIN, OP_LT, 999, "loan_amount", "", "")

    a1 = build_check_args(s, "o1", "ag", {"amount": 50, "vendor": "V"})
    a2 = build_check_args(s, "o2", "ag", {"loan_amount": 50})
    assert a1["fields"] == ["amount", "vendor"]      # o1's two rules only
    assert a2["fields"] == ["loan_amount"]           # o2's one rule only
