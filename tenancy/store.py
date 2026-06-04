"""
SQLite tenant store for AgentAudit multi-tenancy.

Holds the off-chain provisioning state: organisations (with hashed API key and the
per-org encryption key), their agents, and per-agent policy-rule metadata mirroring
what was registered on-chain. The on-chain PolicyContract is the enforcement source
of truth; this store is what the backend reads to authenticate and to reconstruct the
check_and_mint call.

Environment:
    TENANTS_DB_PATH — path to the SQLite file (default: ./data/tenants.db)

Note: the per-org encryption key is stored here in the clear for this round. Production
would hold it in a KMS/HSM; the store would keep only a key reference.
"""

import os
import sqlite3
import time

DEFAULT_DB_PATH = os.getenv("TENANTS_DB_PATH", "./data/tenants.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
    org_id        TEXT PRIMARY KEY,
    api_key_hash  TEXT NOT NULL UNIQUE,
    enc_key_hex   TEXT NOT NULL,
    key_version   INTEGER NOT NULL DEFAULT 1,
    billing_mode  TEXT NOT NULL DEFAULT 'api_key',
    created_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    org_id     TEXT NOT NULL,
    agent_id   TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (org_id, agent_id)
);

CREATE TABLE IF NOT EXISTS agent_rules (
    org_id     TEXT NOT NULL,
    agent_id   TEXT NOT NULL,
    idx        INTEGER NOT NULL,
    mode       INTEGER NOT NULL,
    operator   INTEGER NOT NULL,
    value_num  INTEGER NOT NULL,
    field      TEXT NOT NULL,
    commitment TEXT NOT NULL DEFAULT '',
    doc_cipher TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (org_id, agent_id, idx)
);

CREATE INDEX IF NOT EXISTS idx_orgs_api_key ON orgs(api_key_hash);
"""


class TenantStore:
    """SQLite-backed store for orgs, agents, and policy-rule metadata."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._db_path = db_path
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            # Migration: add doc_cipher to agent_rules for DBs created before Mode 2.
            cols = [r[1] for r in conn.execute("PRAGMA table_info(agent_rules)").fetchall()]
            if "doc_cipher" not in cols:
                conn.execute("ALTER TABLE agent_rules ADD COLUMN doc_cipher TEXT NOT NULL DEFAULT ''")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- orgs ---------------------------------------------------------------

    def create_org(
        self,
        org_id: str,
        api_key_hash: str,
        enc_key_hex: str,
        key_version: int = 1,
        billing_mode: str = "api_key",
    ) -> None:
        """Insert a new organisation. Raises sqlite3.IntegrityError if it exists."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO orgs (org_id, api_key_hash, enc_key_hex, key_version, billing_mode, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (org_id, api_key_hash, enc_key_hex, key_version, billing_mode, int(time.time())),
            )

    def get_org(self, org_id: str) -> dict | None:
        """Return the org row by id, or None."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orgs WHERE org_id = ?", (org_id,)).fetchone()
        return dict(row) if row else None

    def get_org_by_api_key_hash(self, api_key_hash: str) -> dict | None:
        """Resolve an org from a hashed API key (used by the ingest auth path)."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orgs WHERE api_key_hash = ?", (api_key_hash,)).fetchone()
        return dict(row) if row else None

    def list_orgs(self) -> list[dict]:
        """Return all orgs (without exposing the api_key_hash)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT org_id, key_version, billing_mode, created_at FROM orgs ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    # -- agents -------------------------------------------------------------

    def add_agent(self, org_id: str, agent_id: str) -> None:
        """Register an agent under an org (idempotent)."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO agents (org_id, agent_id, created_at) VALUES (?, ?, ?)",
                (org_id, agent_id, int(time.time())),
            )

    def list_agents(self, org_id: str) -> list[str]:
        """Return agent ids for an org."""
        with self._connect() as conn:
            rows = conn.execute("SELECT agent_id FROM agents WHERE org_id = ? ORDER BY created_at", (org_id,)).fetchall()
        return [r["agent_id"] for r in rows]

    # -- rules --------------------------------------------------------------

    def add_rule(
        self,
        org_id: str,
        agent_id: str,
        idx: int,
        mode: int,
        operator: int,
        value_num: int,
        field: str,
        commitment: str = "",
        doc_cipher: str = "",
    ) -> None:
        """
        Record a policy rule's metadata mirroring the on-chain registration.

        For Mode-2 (private) rules, doc_cipher holds the encrypted policy doc envelope
        (JSON) whose sha256 equals the on-chain commitment; operator/value_num are 0
        on-chain and live only inside the encrypted doc.
        """
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO agent_rules "
                "(org_id, agent_id, idx, mode, operator, value_num, field, commitment, doc_cipher) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (org_id, agent_id, idx, mode, operator, value_num, field, commitment, doc_cipher),
            )

    def get_rules(self, org_id: str, agent_id: str) -> list[dict]:
        """Return an agent's rules ordered by index (matching on-chain order)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT idx, mode, operator, value_num, field, commitment, doc_cipher "
                "FROM agent_rules WHERE org_id = ? AND agent_id = ? ORDER BY idx",
                (org_id, agent_id),
            ).fetchall()
        return [dict(r) for r in rows]
