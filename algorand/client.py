"""
Algorand client factory for AgentAudit.

Provides connected algod and indexer clients for Algorand Testnet.
All connection config is loaded from .env.
"""

import os

from algosdk.v2client import algod, indexer
from dotenv import load_dotenv

load_dotenv()

ALGOD_URL = os.getenv("ALGORAND_NODE_URL", "https://testnet-api.algonode.cloud")
INDEXER_URL = os.getenv("ALGORAND_INDEXER_URL", "https://testnet-idx.algonode.cloud")


def get_algod_client() -> algod.AlgodClient:
    """
    Return a connected algod client for Algorand Testnet.

    Uses AlgoNode free public endpoint — no API key required.
    """
    return algod.AlgodClient("", ALGOD_URL)


def get_indexer_client() -> indexer.IndexerClient:
    """
    Return a connected indexer client for Algorand Testnet.

    Used for querying transaction history and application state.
    """
    return indexer.IndexerClient("", INDEXER_URL)
