"""
End-to-end soak test — exercises the live Phase 2 backend over many iterations
to catch reliability issues that single-run checks miss.

Unlike day7_check.py (which uses an in-process TestClient against a fresh DB),
this script hits a RUNNING uvicorn server at http://localhost:8000 — so it
exercises the real network path, real Pinata uploads, real on-chain calls,
and the real SQLite store.

Coverage per cycle:
  - Mix of approved / amount-fail / vendor-fail audits via POST /api/audit
  - Mix of chat prompts: happy-path, rejected, off-topic
  - Periodic batch submits
  - Verify sampled action_ids: right key / wrong key / no key
  - Verify pending leaf (before its batch is submitted)
  - Tamper demo on a verified record
  - Verify a bogus action_id (404 path)
  - Final dashboard sanity check

Run from project root with the backend already running:
    uvicorn api.main:app --reload --port 8000   # in one terminal
    python scripts/soak_test.py                 # in another

Configure via env vars:
    SOAK_BASE          = base URL (default http://localhost:8000)
    SOAK_CYCLES        = number of mixed-action cycles (default 5)
    SOAK_BATCH_EVERY   = submit a batch every N cycles (default 3)
    PAYLOAD_ENCRYPTION_KEY = the real auditor key (read from .env)

Exit code 0 only when every check passes.
"""

import asyncio
import os
import random
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("SOAK_BASE", "http://localhost:8000")
CYCLES = int(os.getenv("SOAK_CYCLES", "5"))
BATCH_EVERY = int(os.getenv("SOAK_BATCH_EVERY", "3"))
# Algorand testnet block time is ~3.5s; spacing audit calls avoids
# TransactionPool.Remember rejections from the deployer wallet being hit
# faster than the node can confirm previous txs.
INTER_CALL_DELAY = float(os.getenv("SOAK_DELAY_SEC", "2.5"))
REAL_KEY = os.getenv("PAYLOAD_ENCRYPTION_KEY", "")
WRONG_KEY = "a" * 64   # valid hex, wrong key
BOGUS_HEX = "zz" * 32  # invalid hex
TIMEOUT = 90.0

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[ ... ]\033[0m"


class Tally:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures: list[str] = []

    def check(self, label: str, cond: bool, detail: str = "") -> bool:
        tag = PASS if cond else FAIL
        line = f"  {tag}  {label}" + (f"  — {detail}" if detail else "")
        print(line)
        if cond:
            self.passed += 1
        else:
            self.failed += 1
            self.failures.append(label)
        return cond


def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


# ── Scenarios ──────────────────────────────────────────────────────────────

AUDIT_SCENARIOS = [
    # (amount, vendor_id, label, expect_decision)
    (4500, "VENDOR_001", "audit-approved-001",   "approved"),
    (4800, "VENDOR_002", "audit-approved-002",   "approved"),
    (3000, "VENDOR_001", "audit-low-amount",     "approved"),
    (7000, "VENDOR_001", "audit-amount-fail",    "rejected"),
    (9999, "VENDOR_002", "audit-amount-fail-2",  "rejected"),
    (4500, "VENDOR_999", "audit-vendor-fail",    "rejected"),
    (8000, "VENDOR_999", "audit-both-fail",      "rejected"),
]

CHAT_PROMPTS = [
    ("Find me a premium vendor for office electronics",     "approved"),
    ("Get a reliable approved vendor for parts",            "approved"),
    ("Pay QuickParts for office supplies",                  "approved"),
    ("find the cheapest vendor available",                  "rejected"),  # picks VENDOR_003
]

OFF_TOPIC_PROMPTS = [
    "what is the weather today",
    "tell me a joke",
    "who won the world cup",
]


TRANSIENT_PHRASES = ("TransactionPool", "txpool", "timeout", "503", "502")


async def _post_with_retry(client: httpx.AsyncClient, url: str, json_body: dict,
                            max_attempts: int = 3) -> httpx.Response:
    """POST with backoff retry on transient Algorand pool errors."""
    last = None
    for attempt in range(max_attempts):
        r = await client.post(url, json=json_body)
        if r.status_code == 200:
            return r
        body = r.text
        transient = any(phrase in body for phrase in TRANSIENT_PHRASES)
        if not transient:
            return r
        print(f"  {INFO}  transient {r.status_code} on attempt {attempt + 1}/{max_attempts} — backing off")
        await asyncio.sleep(4.0 * (attempt + 1))   # 4s, 8s, 12s
        last = r
    return last


async def run_audit(client: httpx.AsyncClient, amount: int, vendor_id: str, tally: Tally, label: str) -> str | None:
    """POST /api/audit. Returns action_id on success, None on failure."""
    try:
        r = await _post_with_retry(client, "/api/audit", {"amount": amount, "vendor_id": vendor_id})
        if r.status_code != 200:
            tally.check(f"{label} returns 200", False, f"got {r.status_code}: {r.text[:400]}")
            return None
        data = r.json()
        ok = all(k in data for k in ("action_id", "decision", "ipfs_cid", "algorand_tx_id", "policy_result"))
        tally.check(f"{label} response has all fields", ok)
        tally.check(f"{label} encrypted=True", data.get("encrypted") is True)
        return data.get("action_id")
    except Exception as e:
        tally.check(f"{label} did not raise", False, str(e)[:120])
        return None


async def run_chat(client: httpx.AsyncClient, prompt: str, tally: Tally, label: str) -> str | None:
    """POST /api/chat. Returns action_id on success (or None for off-topic)."""
    try:
        r = await _post_with_retry(client, "/api/chat",
                                    {"message": prompt, "agent_type_id": "payment_approval"})
        if r.status_code != 200:
            tally.check(f"{label} returns 200", False, f"got {r.status_code}: {r.text[:400]}")
            return None
        data = r.json()
        tally.check(f"{label} has reply", isinstance(data.get("reply"), str))
        audit = data.get("audit_result")
        if audit:
            return audit.get("action_id")
        return None
    except Exception as e:
        tally.check(f"{label} did not raise", False, str(e)[:120])
        return None


async def submit_batch(client: httpx.AsyncClient, tally: Tally) -> dict | None:
    """POST /api/batch/submit. Returns response data, or None if no pending."""
    try:
        r = await _post_with_retry(client, "/api/batch/submit", {})
        if r.status_code == 400:
            print(f"  {INFO}  batch submit skipped (no pending leaves)")
            return None
        if r.status_code != 200:
            tally.check("batch submit returns 200", False, f"got {r.status_code}: {r.text[:400]}")
            return None
        data = r.json()
        ok = all(k in data for k in ("batch_id", "merkle_root", "leaf_count", "anchor_tx_id"))
        tally.check(f"batch submit anchored {data.get('leaf_count')} leaves", ok,
                    f"batch_id={data.get('batch_id')}")
        return data
    except Exception as e:
        tally.check("batch submit did not raise", False, str(e)[:120])
        return None


async def verify_with_key(client: httpx.AsyncClient, action_id: str, key: str | None,
                           tally: Tally, label: str, expect_decrypt: bool) -> dict | None:
    """GET /api/verify with optional X-Auditor-Key header."""
    headers = {"X-Auditor-Key": key} if key else None
    try:
        r = await client.get(f"/api/verify?action_id={action_id}", headers=headers)
        if r.status_code != 200:
            tally.check(f"{label} returns 200", False, f"got {r.status_code}: {r.text[:400]}")
            return None
        data = r.json()
        dec = data.get("decryption", {})
        if expect_decrypt:
            tally.check(f"{label} decrypted=True",   dec.get("decrypted") is True)
            tally.check(f"{label} key_valid=True",   dec.get("key_valid")  is True)
            tally.check(f"{label} record present",   isinstance(dec.get("record"), dict))
        else:
            tally.check(f"{label} decrypted=False",  dec.get("decrypted") is False)
            # Envelope may be absent if Pinata gateway flakes out — accept
            # that as long as the backend reports the failure cleanly.
            envelope_ok = isinstance(dec.get("envelope"), dict)
            error_ok    = bool(dec.get("error"))
            tally.check(f"{label} envelope present OR error reported",
                        envelope_ok or error_ok,
                        "envelope missing and no error message" if not (envelope_ok or error_ok) else
                        "" if envelope_ok else f"ipfs error: {dec.get('error')}")
        return data
    except Exception as e:
        tally.check(f"{label} did not raise", False, str(e)[:120])
        return None


async def verify_pending(client: httpx.AsyncClient, action_id: str, tally: Tally) -> None:
    """A leaf not yet in any batch should return anchor_status=pending."""
    try:
        r = await client.get(f"/api/verify?action_id={action_id}")
        if r.status_code != 200:
            tally.check("pending verify returns 200", False, f"got {r.status_code}")
            return
        data = r.json()
        tally.check("pending verify anchor_status=pending",
                    data.get("anchor_status") == "pending")
        tally.check("pending verify merkle_proof_valid=None",
                    data["verification"]["merkle_proof_valid"] is None)
    except Exception as e:
        tally.check("pending verify did not raise", False, str(e)[:120])


async def verify_404(client: httpx.AsyncClient, tally: Tally) -> None:
    bogus = f"bogus_{random.randint(10_000_000, 99_999_999)}"
    try:
        r = await client.get(f"/api/verify?action_id={bogus}")
        tally.check("bogus action_id returns 404", r.status_code == 404,
                    f"got {r.status_code}")
    except Exception as e:
        tally.check("bogus action_id did not raise", False, str(e)[:120])


async def tamper(client: httpx.AsyncClient, action_id: str, tally: Tally) -> None:
    try:
        r = await client.get(f"/api/tamper-demo?action_id={action_id}")
        if r.status_code != 200:
            tally.check("tamper-demo returns 200", False, f"got {r.status_code}: {r.text[:400]}")
            return
        d = r.json()
        tally.check("tamper proof_original_valid=True",  d.get("proof_original_valid")  is True)
        tally.check("tamper proof_tampered_valid=False", d.get("proof_tampered_valid") is False)
        tally.check("tamper detected",                   d.get("tamper_detected")     is True)
    except Exception as e:
        tally.check("tamper did not raise", False, str(e)[:120])


async def dashboard(client: httpx.AsyncClient, tally: Tally) -> dict:
    try:
        r = await client.get("/api/dashboard")
        tally.check("dashboard returns 200", r.status_code == 200,
                    f"got {r.status_code}")
        data = r.json() if r.status_code == 200 else {}
        tally.check("dashboard has batcher state",
                    "pending_leaves_count" in data and "last_anchor_batch_id" in data)
        return data
    except Exception as e:
        tally.check("dashboard did not raise", False, str(e)[:120])
        return {}


# ── Main soak loop ─────────────────────────────────────────────────────────

async def main():
    if not REAL_KEY:
        print(f"{FAIL}  PAYLOAD_ENCRYPTION_KEY not set in .env — cannot run right-key checks")
        sys.exit(2)

    tally = Tally()
    anchored_action_ids: list[str] = []   # ids we know are in an anchored batch
    pending_action_ids:  list[str] = []   # ids still pending (cleared after submit)

    print(f"Soak test against {BASE}")
    print(f"  cycles={CYCLES}  batch_every={BATCH_EVERY}  inter_call_delay={INTER_CALL_DELAY}s")

    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as client:

        section("0. Initial dashboard snapshot")
        initial = await dashboard(client, tally)
        print(f"  {INFO}  start state: pending={initial.get('pending_leaves_count')}, "
              f"last_anchor={initial.get('last_anchor_batch_id')}")

        section("1. Soak loop")
        for i in range(1, CYCLES + 1):
            print(f"\n--- Cycle {i}/{CYCLES} ---")

            # Two audits per cycle, one chat, one off-topic
            a1 = random.choice(AUDIT_SCENARIOS)
            a2 = random.choice(AUDIT_SCENARIOS)
            cprompt, _ = random.choice(CHAT_PROMPTS)
            offtopic   = random.choice(OFF_TOPIC_PROMPTS)

            aid1 = await run_audit(client, a1[0], a1[1], tally, f"cycle{i} {a1[2]}")
            await asyncio.sleep(INTER_CALL_DELAY)
            aid2 = await run_audit(client, a2[0], a2[1], tally, f"cycle{i} {a2[2]}")
            await asyncio.sleep(INTER_CALL_DELAY)
            aid3 = await run_chat(client, cprompt, tally, f"cycle{i} chat")
            await asyncio.sleep(INTER_CALL_DELAY)
            await run_chat(client, offtopic, tally, f"cycle{i} off-topic (no leaf)")

            for aid in (aid1, aid2, aid3):
                if aid:
                    pending_action_ids.append(aid)

            # Verify a pending leaf before batch submit
            if pending_action_ids:
                sample = random.choice(pending_action_ids)
                print(f"  {INFO}  verifying pending leaf {sample}")
                await verify_pending(client, sample, tally)

            # Periodic batch submit
            if i % BATCH_EVERY == 0:
                print(f"  {INFO}  submitting batch...")
                result = await submit_batch(client, tally)
                if result:
                    # All currently-pending action_ids should now be anchored
                    anchored_action_ids.extend(pending_action_ids)
                    pending_action_ids.clear()

        # Final batch submit to clear any remaining pending
        if pending_action_ids:
            section("2. Final batch submit (flush remaining pending leaves)")
            result = await submit_batch(client, tally)
            if result:
                anchored_action_ids.extend(pending_action_ids)
                pending_action_ids.clear()

        # ── Verification matrix ────────────────────────────────────────────
        if anchored_action_ids:
            sample_ids = random.sample(anchored_action_ids,
                                       min(3, len(anchored_action_ids)))

            section("3. Verify with REAL key (expect decrypted)")
            for aid in sample_ids:
                await verify_with_key(client, aid, REAL_KEY, tally,
                                      f"verify({aid[-8:]}) right-key",
                                      expect_decrypt=True)

            section("4. Verify with WRONG key (expect ciphertext + error)")
            target = sample_ids[0]
            data = await verify_with_key(client, target, WRONG_KEY, tally,
                                          f"verify({target[-8:]}) wrong-key",
                                          expect_decrypt=False)
            if data:
                dec = data.get("decryption", {})
                tally.check("wrong-key key_provided=True", dec.get("key_provided") is True)
                tally.check("wrong-key key_valid=False",   dec.get("key_valid") is False)
                tally.check("wrong-key error message set", bool(dec.get("error")))

            section("5. Verify with NO key (expect ciphertext envelope)")
            target = sample_ids[-1]
            data = await verify_with_key(client, target, None, tally,
                                          f"verify({target[-8:]}) no-key",
                                          expect_decrypt=False)
            if data:
                dec = data.get("decryption", {})
                tally.check("no-key key_provided=False", dec.get("key_provided") is False)
                # Same tolerance as in verify_with_key — Pinata can flake.
                env = dec.get("envelope")
                if isinstance(env, dict):
                    tally.check("no-key envelope has nonce", "nonce" in env)
                else:
                    tally.check("no-key reports ipfs error cleanly",
                                bool(dec.get("error")),
                                f"error: {dec.get('error')}")

            section("6. Verify with malformed hex key (expect 400-ish handling)")
            target = sample_ids[0]
            data = await verify_with_key(client, target, BOGUS_HEX, tally,
                                          f"verify({target[-8:]}) bad-hex",
                                          expect_decrypt=False)
            if data:
                dec = data.get("decryption", {})
                tally.check("bad-hex key_valid=False", dec.get("key_valid") is False)

            section("7. Tamper demo on a verified record")
            await tamper(client, sample_ids[0], tally)

        section("8. 404 path — bogus action_id")
        await verify_404(client, tally)

        section("9. Final dashboard state")
        final = await dashboard(client, tally)
        tally.check("final pending_leaves_count == 0",
                    final.get("pending_leaves_count") == 0,
                    f"got {final.get('pending_leaves_count')}")
        tally.check("final last_anchor_batch_id present",
                    isinstance(final.get("last_anchor_batch_id"), str))

    # ── Summary ────────────────────────────────────────────────────────────
    print()
    print("=" * 72)
    print(f"SOAK COMPLETE — {tally.passed} passed, {tally.failed} failed")
    print("=" * 72)
    if tally.failed:
        print("\nFailed checks:")
        for f in tally.failures:
            print(f"  - {f}")
        sys.exit(1)
    print("\nAll checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
