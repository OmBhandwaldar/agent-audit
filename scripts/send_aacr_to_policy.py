"""
Transfer AACR tokens from deployer wallet to PolicyContract address.

Steps:
  1. Update ASA freeze address → deployer (currently held by old AuditContract)
  2. Unfreeze PolicyContract account for AACR (needed because default_frozen=True)
  3. Send AACR tokens to PolicyContract
  4. Restore ASA freeze address → PolicyContract

Run once after opt_in_asa_phase2.py succeeds.

Usage:
    python scripts/send_aacr_to_policy.py
"""

import os
import sys

from algosdk import account, logic, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")
POLICY_APP_ID = int(os.getenv("POLICY_APP_ID", "0"))
CONTRACT_APP_ID = int(os.getenv("CONTRACT_APP_ID", "0"))  # old AuditContract
COMPLIANCE_ASA_ID = int(os.getenv("COMPLIANCE_ASA_ID", "0"))

SEND_AMOUNT = 20


def main() -> None:
    """Unfreeze PolicyContract and send AACR tokens to it."""
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if POLICY_APP_ID == 0:
        raise RuntimeError("POLICY_APP_ID not set in .env")
    if COMPLIANCE_ASA_ID == 0:
        raise RuntimeError("COMPLIANCE_ASA_ID not set in .env")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    policy_address = logic.get_application_address(POLICY_APP_ID)
    old_contract_address = logic.get_application_address(CONTRACT_APP_ID) if CONTRACT_APP_ID else deployer_address

    client = algod.AlgodClient("", ALGOD_URL)

    print(f"Deployer:        {deployer_address}")
    print(f"PolicyContract:  {policy_address}")
    print(f"ASA ID:          {COMPLIANCE_ASA_ID}")

    # Step 1: Update ASA freeze address → deployer
    # (currently held by old AuditContract; deployer is still ASA manager)
    print("\nStep 1: Move ASA freeze authority → deployer...")
    params = client.suggested_params()
    txn1 = transaction.AssetConfigTxn(
        sender=deployer_address,
        sp=params,
        index=COMPLIANCE_ASA_ID,
        manager=deployer_address,
        reserve=deployer_address,
        freeze=deployer_address,       # ← take freeze back
        clawback=old_contract_address, # leave clawback on old contract for now
        strict_empty_address_check=False,
    )
    tx_id = client.send_transaction(txn1.sign(deployer_key))
    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"  ✅ Freeze authority → deployer (TX: {tx_id})")

    # Step 2: Unfreeze PolicyContract account for AACR
    print("\nStep 2: Unfreeze PolicyContract for AACR...")
    params = client.suggested_params()
    txn2 = transaction.AssetFreezeTxn(
        sender=deployer_address,
        sp=params,
        index=COMPLIANCE_ASA_ID,
        target=policy_address,
        new_freeze_state=False,  # unfreeze
    )
    tx_id = client.send_transaction(txn2.sign(deployer_key))
    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"  ✅ PolicyContract unfrozen (TX: {tx_id})")

    # Step 3: Send AACR tokens
    print(f"\nStep 3: Send {SEND_AMOUNT} AACR to PolicyContract...")
    params = client.suggested_params()
    txn3 = transaction.AssetTransferTxn(
        sender=deployer_address,
        sp=params,
        receiver=policy_address,
        amt=SEND_AMOUNT,
        index=COMPLIANCE_ASA_ID,
    )
    tx_id = client.send_transaction(txn3.sign(deployer_key))
    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"  ✅ Sent {SEND_AMOUNT} AACR to PolicyContract (TX: {tx_id})")

    # Step 4: Restore ASA freeze authority → PolicyContract
    print("\nStep 4: Restore ASA freeze authority → PolicyContract...")
    params = client.suggested_params()
    txn4 = transaction.AssetConfigTxn(
        sender=deployer_address,
        sp=params,
        index=COMPLIANCE_ASA_ID,
        manager=deployer_address,
        reserve=deployer_address,
        freeze=policy_address,         # ← PolicyContract is freeze authority
        clawback=old_contract_address,
        strict_empty_address_check=False,
    )
    tx_id = client.send_transaction(txn4.sign(deployer_key))
    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"  ✅ Freeze authority → PolicyContract (TX: {tx_id})")

    print(f"\n✅ Done! PolicyContract holds {SEND_AMOUNT} AACR and is ready.")
    print(f"\nNext: python scripts/seed_vendors_v2.py")


if __name__ == "__main__":
    main()
