# Tests

40 tests, all green, ~0.6s. Run them:

```bash
pytest -q                          # all tests
pytest --cov=agentaudit --cov=api --cov=batcher --cov=crypto \
       --cov=sdk --cov=tenancy --cov-report=term-missing   # with coverage
python scripts/gen_test_report.py  # -> test-report.xlsx (results + coverage)
```

The suite is intentionally **flat** — six files, one per area. Coverage is concentrated
where correctness matters most (the Merkle proof engine and encryption are ~97% / 79%);
the lighter areas are network / chain / LLM boundaries, which are exercised by the
end-to-end soak test on testnet rather than by unit tests.

## Unit — deterministic core logic

| File | Covers |
|---|---|
| `test_merkle.py` | Merkle tree construction + inclusion proofs (the trust core). ~97% of `batcher/merkle.py`. |
| `test_payload.py` | AES-GCM-256 encrypt/decrypt, nonce handling, tamper detection. |
| `test_policy_engine.py` | Policy predicate evaluation — Mode-1 operators (`<,<=,>,>=,==,!=,in,not_in`) and Mode-2 attested rules. |
| `test_store.py` | SQLite batch store + tenant store (leaves, proofs, orgs, agents, rules). |

## Integration — wired components (network/chain mocked)

| File | Covers |
|---|---|
| `test_api_integration.py` | FastAPI surface: API-key auth, the audit pipeline, and the verify path, with the chain mocked. |
| `test_sdk_client.py` | `AuditClient` — billing-mode selection (API key vs x402) and request shaping. |

## Not unit-tested (covered by the testnet soak run)

The on-chain contracts (`contracts/`), the Algorand/IPFS clients, and the LLM agent are
I/O boundaries — validated by running the full pipeline against live testnet, not by
mocked unit tests.
