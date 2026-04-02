"""
AgentAudit compliance contract.

Stores tamper-proof audit records in box storage, enforces payment policy,
and issues a compliance receipt ASA for approved agent actions.

Policies enforced:
  1. Amount check — payment amount must be below policy limit
  2. Vendor check — vendor must be on the on-chain approved whitelist

Deployed on Algorand Testnet — AgentAudit, AlgoBharat Hack Series 3.0.
"""

from algopy import (
    ARC4Contract,
    Asset,
    BoxMap,
    Bytes,
    Global,
    GlobalState,
    String,
    Txn,
    UInt64,
    itxn,
    op,
)
from algopy import arc4


class AuditRecord(arc4.Struct):
    """On-chain audit record stored per action in box storage."""

    ipfs_hash: arc4.String
    agent_id: arc4.String
    timestamp: arc4.UInt64
    policy_id: arc4.String
    decision: arc4.String
    policy_result: arc4.String  # "amount:pass|vendor:pass" (or "fail" per check)
    amount: arc4.UInt64
    asa_id: arc4.UInt64
    vendor_id: arc4.String


class AuditContract(ARC4Contract):
    """
    AgentAudit smart contract — verifiable audit infrastructure for AI agents.

    Methods:
      initialize       — called once at creation to set ASA ID and policy limit
      opt_in_asa       — called once post-deploy to opt contract into the ASA
      add_vendor       — add a vendor ID to the on-chain approved whitelist
      remove_vendor    — remove a vendor ID from the approved whitelist
      submit_audit     — store audit record, check policies, transfer ASA if approved
      get_audit_record — retrieve stored record by action ID (read only)
    """

    def __init__(self) -> None:
        """Declare global state and box map storage."""
        self.compliance_asa_id = GlobalState(UInt64(0), description="Compliance receipt ASA ID")
        self.policy_limit = GlobalState(UInt64(0), description="Max payment amount that passes policy")
        self.records = BoxMap(Bytes, AuditRecord, key_prefix=b"r:")
        self.vendors = BoxMap(Bytes, arc4.Bool, key_prefix=b"v:")

    @arc4.abimethod(create="require")
    def initialize(
        self,
        compliance_asa_id: UInt64,
        policy_limit: UInt64,
    ) -> None:
        """
        Configure contract at creation time. Called exactly once on deploy.

        Args:
            compliance_asa_id: ASA ID for the compliance receipt token (AACR).
            policy_limit: Payments below this amount pass policy (exclusive upper bound).
        """
        self.compliance_asa_id.value = compliance_asa_id
        self.policy_limit.value = policy_limit

    @arc4.abimethod
    def opt_in_asa(self) -> None:
        """
        Opt the contract account into the compliance receipt ASA.

        Must be called once after deploy, before sending ASA supply to the contract.
        Only the contract creator can call this method.
        """
        assert Txn.sender == Global.creator_address, "Only creator can call opt_in_asa"
        itxn.AssetTransfer(
            xfer_asset=Asset(self.compliance_asa_id.value),
            asset_receiver=Global.current_application_address,
            asset_amount=0,
        ).submit()

    @arc4.abimethod
    def add_vendor(self, vendor_id: arc4.String) -> None:
        """
        Add a vendor to the on-chain approved whitelist.

        Only the contract creator can call this method.
        Vendor key is sha256(vendor_id.bytes) — fixed 32-byte box key.

        Args:
            vendor_id: Vendor identifier string to approve (e.g. "VENDOR_001").
        """
        assert Txn.sender == Global.creator_address, "Only creator can add vendors"
        vendor_key = op.sha256(vendor_id.bytes)
        self.vendors[vendor_key] = arc4.Bool(True)

    @arc4.abimethod
    def remove_vendor(self, vendor_id: arc4.String) -> None:
        """
        Remove a vendor from the on-chain approved whitelist.

        Only the contract creator can call this method.

        Args:
            vendor_id: Vendor identifier string to remove.
        """
        assert Txn.sender == Global.creator_address, "Only creator can remove vendors"
        vendor_key = op.sha256(vendor_id.bytes)
        assert vendor_key in self.vendors, "Vendor not found"
        del self.vendors[vendor_key]

    @arc4.abimethod
    def submit_audit(
        self,
        action_id: arc4.String,
        ipfs_hash: arc4.String,
        agent_id: arc4.String,
        policy_id: arc4.String,
        decision: arc4.String,
        amount: UInt64,
        timestamp: UInt64,
        vendor_id: arc4.String,
    ) -> arc4.String:
        """
        Store audit record, evaluate policies, and issue ASA receipt if both pass.

        Policy 1 — Amount check: amount < policy_limit
        Policy 2 — Vendor check: vendor_id is in the approved whitelist

        Box key is sha256(action_id.bytes) — always 32 bytes.
        Transfers 1 AACR to caller if both policies pass.
        Returns policy result string: "amount:pass|vendor:pass" (or "fail" per check).

        Args:
            action_id: Unique identifier for this audit event.
            ipfs_hash: SHA256 hex of the IPFS CID for the off-chain decision JSON.
            agent_id: Identifier of the AI agent that made the decision.
            policy_id: Policy rule applied (e.g. "limit_5000").
            decision: Agent decision — "approved" or "rejected".
            amount: Payment amount evaluated by the agent.
            timestamp: Unix timestamp of the agent decision.
            vendor_id: Vendor identifier to check against the whitelist.
        """
        box_key = op.sha256(action_id.bytes)

        # Policy 1: amount check
        amount_passes = amount < self.policy_limit.value
        if amount_passes:
            amount_result = arc4.String("pass")
        else:
            amount_result = arc4.String("fail")

        # Policy 2: vendor check
        vendor_key = op.sha256(vendor_id.bytes)
        vendor_passes = vendor_key in self.vendors
        if vendor_passes:
            vendor_result = arc4.String("pass")
        else:
            vendor_result = arc4.String("fail")

        # Combined result string
        policy_result = arc4.String(
            String("amount:") + amount_result.native
            + String("|vendor:") + vendor_result.native
        )

        both_pass = amount_passes and vendor_passes

        if both_pass:
            receipt_asa_id = arc4.UInt64(self.compliance_asa_id.value)
        else:
            receipt_asa_id = arc4.UInt64(0)

        record = AuditRecord(
            ipfs_hash=ipfs_hash,
            agent_id=agent_id,
            timestamp=arc4.UInt64(timestamp),
            policy_id=policy_id,
            decision=decision,
            policy_result=policy_result,
            amount=arc4.UInt64(amount),
            asa_id=receipt_asa_id,
            vendor_id=vendor_id,
        )
        self.records[box_key] = record.copy()

        if both_pass:
            itxn.AssetTransfer(
                xfer_asset=Asset(self.compliance_asa_id.value),
                asset_sender=Global.current_application_address,
                asset_receiver=Txn.sender,
                asset_amount=1,
            ).submit()

        return policy_result

    @arc4.abimethod(readonly=True)
    def get_audit_record(self, action_id: arc4.String) -> arc4.String:
        """
        Retrieve a stored audit record by action ID.

        Returns pipe-delimited string:
          "ipfs_hash=...|agent_id=...|policy_id=...|decision=...|policy_result=...|vendor_id=..."
        Asserts if no record exists for the given action ID.

        Args:
            action_id: The action ID used when submit_audit was called.
        """
        box_key = op.sha256(action_id.bytes)
        assert box_key in self.records, "Audit record not found"
        record = self.records[box_key].copy()

        result = (
            String("ipfs_hash=") + record.ipfs_hash.native
            + String("|agent_id=") + record.agent_id.native
            + String("|policy_id=") + record.policy_id.native
            + String("|decision=") + record.decision.native
            + String("|policy_result=") + record.policy_result.native
            + String("|vendor_id=") + record.vendor_id.native
        )
        return arc4.String(result)
