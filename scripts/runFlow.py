"""
Day 5 checkpoint script — verifies the full audit pipeline works end to end.

Usage:
  python scripts/runFlow.py 3000    # should approve
  python scripts/runFlow.py 7000    # should reject

Expected output for an approved flow:
  Decision:       approved
  IPFS CID:       Qm...
  Algorand TX:    <tx_id>
  Policy Result:  pass
  ASA Minted:     True
"""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.WARNING)  # suppress info logs for clean output

sys.path.insert(0, ".")

from sdk.audit_flow import run_audit_flow


async def main() -> None:
    """Run audit flow and print all result fields."""
    amount = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    print(f"\nRunning audit flow for amount: {amount}\n")

    result = await run_audit_flow(amount)

    print(f"Decision:       {result['decision']}")
    print(f"IPFS CID:       {result['ipfs_cid']}")
    print(f"Algorand TX:    {result['algorand_tx_id']}")
    print(f"Policy Result:  {result['policy_result']}")
    print(f"ASA Minted:     {result['asa_minted']}")
    print(f"\nIPFS link:  https://gateway.pinata.cloud/ipfs/{result['ipfs_cid']}")
    print(f"TX link:    https://testnet.explorer.perawallet.app/tx/{result['algorand_tx_id']}")


asyncio.run(main())
