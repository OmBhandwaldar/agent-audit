"""
agent/vendors.py

Vendor registry for the autonomous procurement agent.

Whitelisted on-chain: VENDOR_001, VENDOR_002
Not whitelisted:      VENDOR_003 (cheapest — failure demo)
Over budget:          VENDOR_004 (whitelisted but price > POLICY_LIMIT)
"""

from typing import TypedDict


class Vendor(TypedDict):
    id: str
    name: str
    price: int
    category: str


VENDOR_REGISTRY: list[Vendor] = [
    {"id": "VENDOR_001", "name": "TechSupplies Co",  "price": 4500, "category": "electronics"},
    {"id": "VENDOR_002", "name": "QuickParts Ltd",   "price": 4800, "category": "electronics"},
    {"id": "VENDOR_003", "name": "BudgetParts Inc",  "price": 3200, "category": "electronics"},
    {"id": "VENDOR_004", "name": "PremiumGear Corp", "price": 6200, "category": "electronics"},
]


def get_vendors_summary() -> str:
    """Return formatted vendor list for the agent to read."""
    lines = ["Available vendors:"]
    for v in VENDOR_REGISTRY:
        lines.append(f"  - {v['id']} | {v['name']} | price: Rs{v['price']} | category: {v['category']}")
    return "\n".join(lines)


def get_vendor_by_id(vendor_id: str) -> Vendor | None:
    """Look up a vendor by ID. Returns None if not found."""
    for v in VENDOR_REGISTRY:
        if v["id"] == vendor_id:
            return v
    return None
