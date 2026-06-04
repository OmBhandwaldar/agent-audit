"""
Opt an account into testnet USDC (ASA 10458941) — needed for x402 payments.

Run for the x402 recipient (X402_RECIPIENT) so it can receive settlement, and for the
payer wallet so it can hold/transfer USDC.

Usage:
  X402_PAYER_MNEMONIC="<25 words>" python scripts/opt_in_usdc.py
  (falls back to DEPLOYER_MNEMONIC if X402_PAYER_MNEMONIC is unset)
"""

import os
import sys

from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

load_dotenv()

USDC_TESTNET_ASA = 10458941
ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")


def main() -> None:
    mn = os.getenv("X402_PAYER_MNEMONIC") or os.getenv("DEPLOYER_MNEMONIC")
    if not mn:
        raise SystemExit("Set X402_PAYER_MNEMONIC or DEPLOYER_MNEMONIC")

    sk = mnemonic.to_private_key(mn)
    addr = account.address_from_private_key(sk)
    client = algod.AlgodClient("", ALGOD_URL)

    info = client.account_info(addr)
    if any(a["asset-id"] == USDC_TESTNET_ASA for a in info.get("assets", [])):
        print(f"{addr} already opted into USDC ({USDC_TESTNET_ASA})")
        return

    txn = transaction.AssetTransferTxn(
        sender=addr, sp=client.suggested_params(), receiver=addr, amt=0, index=USDC_TESTNET_ASA
    )
    tx_id = client.send_transaction(txn.sign(sk))
    transaction.wait_for_confirmation(client, tx_id, 4)
    print(f"{addr} opted into USDC ({USDC_TESTNET_ASA})  TX {tx_id}")
    print("Now fund this address with testnet USDC: https://faucet.circle.com")


if __name__ == "__main__":
    main()
