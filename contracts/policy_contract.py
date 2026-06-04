"""
AgentAudit multi-tenant Policy Contract.

One shared contract enforces per-org, per-agent policies stored as data (boxes),
not code. A policy is a predicate {field, operator, value}; an agent's policy set
is N predicates, all AND-ed. Mode 1 (public) predicates are enforced on-chain here.
Mode 2 (private) predicates are enforced off-chain by the backend and their result
is attested in the call, bound to a commitment stored on-chain in the rule box.

check_and_mint is creator-only: the AgentAudit backend is the trusted submitter that
resolves the org from the API key and reports the agent's decision. The on-chain
guarantees are the immutable policy thresholds and the AACR compliance receipt.

Box layout (keys are sha256 of ARC4-encoded parts so they match the off-chain client):
  tenant_rules (b"r:")  sha256(org_id + agent_id + itob(index)) -> PolicyRule
  rule_counts  (b"rc:") sha256(org_id + agent_id)               -> arc4.UInt64
  sets         (b"s:")  sha256(org_id + agent_id + field + value) -> arc4.Bool
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
    arc4,
    ensure_budget,
    itxn,
    op,
    urange,
)

# Operator codes (Mode 1 predicates)
OP_LT = 1
OP_LE = 2
OP_GT = 3
OP_GE = 4
OP_EQ = 5
OP_NE = 6
OP_IN = 7
OP_NOT_IN = 8

# Enforcement modes
MODE_ONCHAIN = 1
MODE_ATTESTED = 2


class PolicyRule(arc4.Struct):
    """One predicate in an agent's policy set."""

    mode: arc4.UInt64        # MODE_ONCHAIN or MODE_ATTESTED
    operator: arc4.UInt64    # OP_* (Mode 1 only)
    value_num: arc4.UInt64   # numeric threshold (Mode 1 numeric operators)
    field: arc4.String       # decision field name (also namespaces set membership)
    commitment: arc4.String  # Mode 2: sha256(policy_doc) hex; empty for Mode 1


class PolicyContract(ARC4Contract):
    """Multi-tenant policy enforcement + AACR compliance receipt minting."""

    def __init__(self) -> None:
        self.compliance_asa_id = GlobalState(UInt64(0), description="AACR compliance receipt ASA ID")
        self.tenant_rules = BoxMap(Bytes, PolicyRule, key_prefix=b"r:")
        self.rule_counts = BoxMap(Bytes, arc4.UInt64, key_prefix=b"rc:")
        self.sets = BoxMap(Bytes, arc4.Bool, key_prefix=b"s:")

    @arc4.abimethod(create="require")
    def initialize(self, compliance_asa_id: UInt64) -> None:
        """Set the AACR ASA ID at creation. The creator is the trusted backend/minter."""
        self.compliance_asa_id.value = compliance_asa_id

    @arc4.abimethod
    def opt_in_asa(self) -> None:
        """Opt the contract account into the AACR ASA (creator only)."""
        assert Txn.sender == Global.creator_address, "Only creator can opt in"
        itxn.AssetTransfer(
            xfer_asset=Asset(self.compliance_asa_id.value),
            asset_receiver=Global.current_application_address,
            asset_amount=0,
            fee=0,
        ).submit()

    @arc4.abimethod
    def register_rule(self, org_id: arc4.String, agent_id: arc4.String, rule: PolicyRule) -> UInt64:
        """Append a predicate to an org+agent policy set (creator only). Returns its index."""
        assert Txn.sender == Global.creator_address, "Only creator can register rules"
        count_key = op.sha256(org_id.bytes + agent_id.bytes)
        idx = self.rule_counts.get(count_key, default=arc4.UInt64(0)).native
        rule_key = op.sha256(org_id.bytes + agent_id.bytes + op.itob(idx))
        self.tenant_rules[rule_key] = rule.copy()
        self.rule_counts[count_key] = arc4.UInt64(idx + 1)
        return idx

    @arc4.abimethod
    def add_to_set(
        self, org_id: arc4.String, agent_id: arc4.String, field: arc4.String, value: arc4.String
    ) -> None:
        """Add a value to an org+agent+field membership set, for in/not_in predicates (creator only)."""
        assert Txn.sender == Global.creator_address, "Only creator can edit sets"
        set_key = op.sha256(org_id.bytes + agent_id.bytes + field.bytes + value.bytes)
        self.sets[set_key] = arc4.Bool(True)  # noqa: FBT003

    @arc4.abimethod
    def remove_from_set(
        self, org_id: arc4.String, agent_id: arc4.String, field: arc4.String, value: arc4.String
    ) -> None:
        """Remove a value from an org+agent+field membership set (creator only)."""
        assert Txn.sender == Global.creator_address, "Only creator can edit sets"
        set_key = op.sha256(org_id.bytes + agent_id.bytes + field.bytes + value.bytes)
        assert set_key in self.sets, "Value not in set"
        del self.sets[set_key]

    @arc4.abimethod
    def check_and_mint(
        self,
        org_id: arc4.String,
        agent_id: arc4.String,
        action_id: arc4.String,
        ipfs_hash: arc4.String,
        values_num: arc4.DynamicArray[arc4.UInt64],
        values_str: arc4.DynamicArray[arc4.String],
        attested: arc4.DynamicArray[arc4.Bool],
    ) -> arc4.String:
        """
        Evaluate an org+agent's policy set against a decision; mint 1 AACR if all pass.

        Creator-only: the backend is the trusted submitter (resolves org from the API key
        and reports the agent's decision). values_num/values_str/attested are aligned to the
        stored rules by index. Returns a per-rule result string like "pass:onchain|fail:attested".
        """
        assert Txn.sender == Global.creator_address, "Only creator (backend) can submit audits"

        count_key = op.sha256(org_id.bytes + agent_id.bytes)
        rule_count = self.rule_counts.get(count_key, default=arc4.UInt64(0)).native
        assert rule_count > UInt64(0), "No policies registered for this org/agent"
        assert values_num.length == rule_count, "values_num length mismatch"
        assert values_str.length == rule_count, "values_str length mismatch"
        assert attested.length == rule_count, "attested length mismatch"

        # The per-rule loop (box reads + sha256 + compares) can exceed the base
        # opcode budget; request headroom proportional to the rule count.
        ensure_budget(UInt64(400) + rule_count * UInt64(200))

        all_pass = True
        result = String("")

        for i in urange(rule_count):
            rule_key = op.sha256(org_id.bytes + agent_id.bytes + op.itob(i))
            assert rule_key in self.tenant_rules, "Missing rule box"
            rule = self.tenant_rules[rule_key].copy()
            mode = rule.mode.native

            passed = False
            if mode == UInt64(MODE_ONCHAIN):
                provenance = String("onchain")
                operator = rule.operator.native
                if operator == UInt64(OP_IN) or operator == UInt64(OP_NOT_IN):
                    set_key = op.sha256(
                        org_id.bytes + agent_id.bytes + rule.field.bytes + values_str[i].bytes
                    )
                    in_set = set_key in self.sets
                    if operator == UInt64(OP_IN):
                        passed = in_set
                    else:
                        passed = not in_set
                else:
                    lhs = values_num[i].native
                    rhs = rule.value_num.native
                    if operator == UInt64(OP_LT):
                        passed = lhs < rhs
                    elif operator == UInt64(OP_LE):
                        passed = lhs <= rhs
                    elif operator == UInt64(OP_GT):
                        passed = lhs > rhs
                    elif operator == UInt64(OP_GE):
                        passed = lhs >= rhs
                    elif operator == UInt64(OP_EQ):
                        passed = lhs == rhs
                    else:  # OP_NE
                        passed = lhs != rhs
            else:
                # Mode 2: trust the backend's attested result (method is creator-gated).
                provenance = String("attested")
                passed = attested[i].native

            if not passed:
                all_pass = False

            if passed:
                token = String("pass:")
            else:
                token = String("fail:")
            if i == UInt64(0):
                result = token + provenance
            else:
                result = result + String("|") + token + provenance

        if all_pass:
            itxn.AssetTransfer(
                xfer_asset=Asset(self.compliance_asa_id.value),
                asset_receiver=Txn.sender,
                asset_amount=1,
                fee=0,
            ).submit()

        return arc4.String(result)
