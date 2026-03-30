"""
Post-deploy ASA setup script. Run once after deploying AuditContract.

Steps performed in order:
  1. Update ASA clawback + freeze addresses -> contract address
  2. Fund contract address with 0.2 ALGO (covers ASA opt-in MBR + fees)
  3. Call contract's opt_in_asa() — contract self-opts into the ASA
  4. Transfer full 1M AACR supply from deployer -> contract address

Prerequisite: CONTRACT_APP_ID and COMPLIANCE_ASA_ID must be set in .env.

Usage: python scripts/update_asa.py
"""

import os

from algosdk import abi, account, logic, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

load_dotenv()

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
DEPLOYER_MNEMONIC = os.getenv("DEPLOYER_MNEMONIC")
COMPLIANCE_ASA_ID = int(os.getenv("COMPLIANCE_ASA_ID", "0"))
CONTRACT_APP_ID = int(os.getenv("CONTRACT_APP_ID", "0"))

ASA_TOTAL_SUPPLY = 1_000_000
CONTRACT_FUND_AMOUNT = 200_000  # 0.2 ALGO: 0.1 for ASA opt-in MBR + 0.1 buffer


def get_algod_client() -> algod.AlgodClient:
    """Return a connected algod client for testnet."""
    return algod.AlgodClient("", ALGOD_URL)


def step1_update_asa_addresses(
    client: algod.AlgodClient,
    deployer_key: str,
    deployer_address: str,
    contract_address: str,
) -> None:
    """
    Update ASA clawback and freeze addresses to the contract address.
    Manager and reserve remain with the deployer.
    """
    params = client.suggested_params()

    txn = transaction.AssetConfigTxn(
        sender=deployer_address,
        sp=params,
        index=COMPLIANCE_ASA_ID,
        manager=deployer_address,
        reserve=deployer_address,
        freeze=contract_address,
        clawback=contract_address,
        strict_empty_address_check=False,
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"  TX: {tx_id}")
    print(f"  ASA clawback + freeze -> {contract_address}")


def step2_fund_contract(
    client: algod.AlgodClient,
    deployer_key: str,
    deployer_address: str,
    contract_address: str,
) -> None:
    """
    Send 0.2 ALGO to the contract address to cover the ASA opt-in MBR.
    The contract must hold ALGO before it can opt into any ASA.
    """
    params = client.suggested_params()

    txn = transaction.PaymentTxn(
        sender=deployer_address,
        sp=params,
        receiver=contract_address,
        amt=CONTRACT_FUND_AMOUNT,
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"  TX: {tx_id}")
    print(f"  Sent {CONTRACT_FUND_AMOUNT / 1_000_000} ALGO to contract address")


def step3_opt_contract_into_asa(
    client: algod.AlgodClient,
    deployer_key: str,
    deployer_address: str,
) -> None:
    """
    Call the contract's opt_in_asa() method.
    The contract submits a zero-amount self-transfer to opt into the ASA.
    foreign_assets must include the ASA ID so the AVM can reference it.
    """
    selector = abi.Method.from_signature("opt_in_asa()void").get_selector()
    params = client.suggested_params()
    # Outer tx must cover its own fee + the inner ASA transfer fee.
    params.flat_fee = True
    params.fee = 2000  # 2x min fee: 1 outer + 1 inner transaction

    txn = transaction.ApplicationCallTxn(
        sender=deployer_address,
        sp=params,
        index=CONTRACT_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[selector],
        foreign_assets=[COMPLIANCE_ASA_ID],
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"  TX: {tx_id}")
    print(f"  Contract opted into ASA {COMPLIANCE_ASA_ID}")


def step4_send_asa_supply(
    client: algod.AlgodClient,
    deployer_key: str,
    deployer_address: str,
    contract_address: str,
) -> None:
    """
    Transfer the full 1M AACR supply from deployer to the contract address.
    The contract must be opted in (step 3) before this can succeed.
    """
    params = client.suggested_params()

    txn = transaction.AssetTransferTxn(
        sender=deployer_address,
        sp=params,
        receiver=contract_address,
        amt=ASA_TOTAL_SUPPLY,
        index=COMPLIANCE_ASA_ID,
    )

    signed_txn = txn.sign(deployer_key)
    tx_id = client.send_transaction(signed_txn)
    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"  TX: {tx_id}")
    print(f"  Transferred {ASA_TOTAL_SUPPLY:,} AACR to contract")


def main() -> None:
    """Validate env, derive addresses, run all four setup steps."""
    if not DEPLOYER_MNEMONIC:
        raise RuntimeError("DEPLOYER_MNEMONIC not set in .env")
    if COMPLIANCE_ASA_ID == 0:
        raise RuntimeError("COMPLIANCE_ASA_ID not set in .env — run create_asa.py first")
    if CONTRACT_APP_ID == 0:
        raise RuntimeError("CONTRACT_APP_ID not set in .env — run deploy_contract.py first")

    deployer_key = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    deployer_address = account.address_from_private_key(deployer_key)
    contract_address = logic.get_application_address(CONTRACT_APP_ID)

    print(f"Deployer:          {deployer_address}")
    print(f"Contract App ID:   {CONTRACT_APP_ID}")
    print(f"Contract address:  {contract_address}")
    print(f"ASA ID:            {COMPLIANCE_ASA_ID}")
    print()

    client = get_algod_client()

    print("Step 1: Updating ASA clawback + freeze to contract address...")
    step1_update_asa_addresses(client, deployer_key, deployer_address, contract_address)
    print()

    print("Step 2: Funding contract address for ASA opt-in MBR...")
    step2_fund_contract(client, deployer_key, deployer_address, contract_address)
    print()

    print("Step 3: Opting contract into ASA...")
    step3_opt_contract_into_asa(client, deployer_key, deployer_address)
    print()

    print("Step 4: Transferring 1M AACR supply to contract...")
    step4_send_asa_supply(client, deployer_key, deployer_address, contract_address)
    print()

    print("ASA setup complete.")
    print(f"Contract holds 1M AACR and is ready to issue compliance receipts.")
    print(f"Explorer: https://testnet.explorer.perawallet.app/application/{CONTRACT_APP_ID}")


if __name__ == "__main__":
    main()
