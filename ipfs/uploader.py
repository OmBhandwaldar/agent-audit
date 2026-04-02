"""
IPFS uploader for AgentAudit decision records.

Uploads JSON data to IPFS via Pinata and returns the CID.
Retries once on failure with a 2-second delay before raising.
"""

import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PINATA_URL = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
PINATA_JWT = os.getenv("PINATA_JWT")
REQUEST_TIMEOUT = 10.0
MAX_RETRIES = 2
RETRY_DELAY = 2.0


async def upload_to_ipfs(data: dict, name: str = "") -> str:
    """
    Upload a JSON-serialisable dict to IPFS via Pinata.

    Retries once on any failure before raising.
    Returns the IPFS CID string (e.g. "QmXyz...").

    The optional name is stored as Pinata metadata so the verify endpoint
    can later look up the CID by action_id using the Pinata list API.

    Args:
        data: The decision record to upload.
        name: Optional Pinata metadata name (set to action_id for lookups).

    Raises:
        RuntimeError: If both attempts fail.
    """
    if not PINATA_JWT:
        raise RuntimeError("PINATA_JWT not set in .env")

    headers = {
        "Authorization": f"Bearer {PINATA_JWT}",
        "Content-Type": "application/json",
    }
    payload: dict = {"pinataContent": data}
    if name:
        payload["pinataMetadata"] = {"name": name}

    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(PINATA_URL, json=payload, headers=headers)
                response.raise_for_status()
                cid = response.json()["IpfsHash"]
                logger.info("IPFS upload successful: %s (name: %s)", cid, name or "—")
                return cid
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                logger.warning("IPFS upload attempt %d failed, retrying: %s", attempt + 1, e)
                await asyncio.sleep(RETRY_DELAY)

    raise RuntimeError(f"IPFS upload failed after {MAX_RETRIES} attempts: {last_error}")

