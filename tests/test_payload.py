"""Unit tests for AES-GCM-256 payload encryption (crypto/payload.py)."""

import pytest

from crypto.payload import decrypt_payload, encrypt_payload, generate_key, parse_hex_key


def _key() -> bytes:
    return parse_hex_key(generate_key())


def test_roundtrip_explicit_key():
    key = _key()
    data = {"decision": "approved", "amount": 4500, "trace": [{"step": 1}]}
    env = encrypt_payload(data, key=key)
    assert env["enc"] == "aes-gcm-256" and env["v"] == 1
    assert decrypt_payload(env, key=key) == data


def test_wrong_key_fails():
    env = encrypt_payload({"x": 1}, key=_key())
    with pytest.raises(Exception):
        decrypt_payload(env, key=_key())  # different key


def test_tampered_ciphertext_fails():
    key = _key()
    env = encrypt_payload({"x": 1}, key=key)
    ct = bytearray(bytes.fromhex(env["ciphertext"]))
    ct[0] ^= 0xFF
    env["ciphertext"] = ct.hex()
    with pytest.raises(Exception):
        decrypt_payload(env, key=key)


def test_nonce_is_unique_per_call():
    key = _key()
    a = encrypt_payload({"x": 1}, key=key)
    b = encrypt_payload({"x": 1}, key=key)
    assert a["nonce"] != b["nonce"]


def test_parse_hex_key_validation():
    assert len(parse_hex_key("00" * 32)) == 32
    with pytest.raises(ValueError):
        parse_hex_key("nothex")
    with pytest.raises(ValueError):
        parse_hex_key("00" * 16)  # 16 bytes, not 32


def test_unsupported_envelope_rejected():
    with pytest.raises(RuntimeError):
        decrypt_payload({"v": 2, "enc": "aes-gcm-256", "nonce": "00", "ciphertext": "00"}, key=_key())
