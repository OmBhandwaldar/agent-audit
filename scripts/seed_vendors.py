"""
Seed the on-chain vendor whitelist after contract redeploy.

Calls add_vendor() for each approved vendor ID.
Run this once after every contract redeploy before testing the full flow.

Usage:
    python scripts/seed_vendors.py

Expected output:
    Seeding vendor whitelist on Algorand...
    ✅ VENDOR_001 added (TX: <tx_id>)
    ✅ VENDOR_002 added (TX: <tx_id>)
    Done. 2 vendors seeded.
    VENDOR_999 is intentionally NOT seeded — use it for rejection demos.
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.WARNING)

from algorand.contract_client import add_vendor

# Approved vendors for demo
# VENDOR_999 is intentionally excluded — use it to demo vendor policy rejection
APPROVED_VENDORS = ["VENDOR_001", "VENDOR_002"]


async def main() -> None:
    """Seed all approved vendors into the on-chain whitelist."""
    print("\nSeeding vendor whitelist on Algorand...")

    success_count = 0
    for vendor_id in APPROVED_VENDORS:
        try:
            tx_id = await add_vendor(vendor_id)
            print(f"  ✅ {vendor_id} added (TX: {tx_id})")
            success_count += 1
        except Exception as e:
            print(f"  ❌ {vendor_id} failed: {e}")

    print(f"\nDone. {success_count}/{len(APPROVED_VENDORS)} vendors seeded.")
    print("VENDOR_999 is intentionally NOT seeded — use it for rejection demos.\n")


if __name__ == "__main__":
    asyncio.run(main())
