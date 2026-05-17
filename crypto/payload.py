"""
AES-GCM-256 encryption for AgentAudit IPFS payloads.

Encrypts decision records before uploading to IPFS so the plaintext
audit data is never stored on a public network unprotected.

The IPFS pin holds an encrypted envelope. The SHA256 of the CID still
goes to PolicyContract unchanged — the verification chain is unaffected.

Key management:
    Generate once: python scripts/gen_encryption_key.py
    Store result as PAYLOAD_ENCRYPTION_KEY in .env (64-char hex string).

Encrypted envelope format (JSON uploaded to IPFS):
    {
        "v":          1,
        "enc":        "aes-gcm-256",
        "nonce":      "<24-char hex  — 12 bytes>",
        "ciphertext": "<hex string  — plaintext + 16-byte GCM tag>"
    }
"""

import json
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

load_dotenv()

_ENV_KEY = "PAYLOAD_ENCRYPTION_KEY"
_NONCE_BYTES = 12   # 96-bit nonce — GCM standard
_KEY_BYTES = 32     # 256-bit key


def _load_key() -> bytes:
    """
    Load the AES-256 key from PAYLOAD_ENCRYPTION_KEY env var.

    Raises:
        RuntimeError: If the env var is missing or the wrong length.
    """
    hex_key = os.getenv(_ENV_KEY)
    if not hex_key:
        raise RuntimeError(
            f"{_ENV_KEY} not set in .env. "
            "Run: python scripts/gen_encryption_key.py"
        )
    key = bytes.fromhex(hex_key)
    if len(key) != _KEY_BYTES:
        raise RuntimeError(
            f"{_ENV_KEY} must be {_KEY_BYTES * 2} hex chars ({_KEY_BYTES} bytes). "
            f"Got {len(key)} bytes."
        )
    return key


def encrypt_payload(data: dict) -> dict:
    """
    Encrypt a decision record dict using AES-GCM-256.

    A fresh random nonce is generated for every call.

    Args:
        data: The plaintext decision record to encrypt.

    Returns:
        Encrypted envelope dict suitable for JSON serialization and IPFS upload.

    Raises:
        RuntimeError: If PAYLOAD_ENCRYPTION_KEY is missing or invalid.
    """
    key = _load_key()
    nonce = secrets.token_bytes(_NONCE_BYTES)
    plaintext = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    return {
        "v": 1,
        "enc": "aes-gcm-256",
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
    }


def decrypt_payload(envelope: dict, key: bytes | None = None) -> dict:
    """
    Decrypt an encrypted envelope back into the original decision record.

    Args:
        envelope: The encrypted envelope dict (as returned by encrypt_payload
                  or fetched from IPFS).
        key:      Optional 32-byte AES-256 key. If omitted, falls back to the
                  PAYLOAD_ENCRYPTION_KEY env var. Pass an explicit key when the
                  verifier supplies it at request time (e.g. via HTTP header).

    Returns:
        The original plaintext decision record dict.

    Raises:
        RuntimeError: If the key is missing/invalid, the version is unsupported,
                      or the ciphertext is tampered (GCM auth tag fails).
    """
    if envelope.get("v") != 1 or envelope.get("enc") != "aes-gcm-256":
        raise RuntimeError(
            f"Unsupported envelope version/algorithm: "
            f"v={envelope.get('v')} enc={envelope.get('enc')}"
        )

    if key is None:
        key = _load_key()
    elif len(key) != _KEY_BYTES:
        raise RuntimeError(
            f"Supplied key must be {_KEY_BYTES} bytes. Got {len(key)} bytes."
        )

    nonce = bytes.fromhex(envelope["nonce"])
    ciphertext = bytes.fromhex(envelope["ciphertext"])

    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as e:
        raise RuntimeError(f"Decryption failed — data may be tampered: {e}")

    return json.loads(plaintext.decode())


def parse_hex_key(hex_key: str) -> bytes:
    """
    Parse a hex-encoded AES-256 key string into bytes.

    Args:
        hex_key: 64-character hex string.

    Returns:
        32-byte key.

    Raises:
        ValueError: If the input is not valid hex or not 32 bytes long.
    """
    try:
        key = bytes.fromhex(hex_key.strip())
    except ValueError as e:
        raise ValueError(f"Auditor key is not valid hex")
    if len(key) != _KEY_BYTES:
        raise ValueError(
            f"Auditor key must be {_KEY_BYTES * 2} hex chars ({_KEY_BYTES} bytes). "
            f"Got {len(key)} bytes."
        )
    return key


def generate_key() -> str:
    """
    Generate a random 256-bit AES key as a hex string.

    Returns:
        64-character hex string suitable for PAYLOAD_ENCRYPTION_KEY in .env.
    """
    return secrets.token_bytes(_KEY_BYTES).hex()
