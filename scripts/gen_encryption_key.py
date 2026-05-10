"""
Generate a random AES-256 encryption key for IPFS payload encryption.

Run once, then add the output to .env as PAYLOAD_ENCRYPTION_KEY.

Usage:
    python scripts/gen_encryption_key.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto.payload import generate_key

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def main() -> None:
    """Generate key and write it to .env."""
    key_hex = generate_key()

    with open(ENV_PATH) as f:
        content = f.read()

    key_name = "PAYLOAD_ENCRYPTION_KEY"
    replacement = f"{key_name}={key_hex}"

    if re.search(rf"^{key_name}=.+", content, re.MULTILINE):
        print(f"{key_name} already set in .env — not overwriting.")
        print("Delete the existing line first if you want to rotate the key.")
        return

    updated = content.rstrip("\n") + f"\n{replacement}\n"
    with open(ENV_PATH, "w") as f:
        f.write(updated)

    print(f"Key generated and saved to .env:")
    print(f"  {key_name}={key_hex[:8]}...{key_hex[-8:]}")
    print()
    print("Keep this key safe — it is required to decrypt any IPFS payload.")


if __name__ == "__main__":
    main()
