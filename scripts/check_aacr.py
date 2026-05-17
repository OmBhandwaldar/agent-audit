"""Quick diagnostic: AACR balances for deployer + PolicyContract."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algosdk import account, mnemonic
from algosdk.logic import get_application_address
from dotenv import load_dotenv

from algorand.client import get_algod_client

load_dotenv()

algod = get_algod_client()
app_id = int(os.environ["POLICY_APP_ID"])
asa_id = int(os.environ["COMPLIANCE_ASA_ID"])

contract_addr = get_application_address(app_id)
deployer_addr = account.address_from_private_key(
    mnemonic.to_private_key(os.environ["DEPLOYER_MNEMONIC"])
)


def aacr_balance(addr: str) -> str:
    info = algod.account_info(addr)
    for a in info.get("assets", []):
        if a["asset-id"] == asa_id:
            return str(a["amount"])
    return "NOT OPTED IN"


print(f"PolicyContract address: {contract_addr}")
print(f"  ALGO balance: {algod.account_info(contract_addr)['amount'] / 1e6}")
print(f"  AACR balance: {aacr_balance(contract_addr)}")
print()
print(f"Deployer address: {deployer_addr}")
print(f"  ALGO balance: {algod.account_info(deployer_addr)['amount'] / 1e6}")
print(f"  AACR balance: {aacr_balance(deployer_addr)}")
