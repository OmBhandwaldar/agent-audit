"""
x402 payment gate for AgentAudit (Flavor 1: a provisioned tenant pays per call in USDC).

Protects POST /v1/audit/x402 behind a $0.01 USDC payment on Algorand testnet. The org is
still declared in the request body (the org's key + policies apply); the payment authorizes
the call instead of an API key. Disabled unless X402_ENABLED=true.

Env:
  X402_ENABLED          "true" to turn the gate on (default off)
  X402_RECIPIENT        Algorand address that receives the USDC (must be opted into USDC)
  X402_FACILITATOR_URL  facilitator that verifies/settles (default https://www.x402.org/facilitator)
  X402_PRICE_MICRO      price in micro-USDC (default "10000" = $0.01 USDC)
"""

import logging
import os

logger = logging.getLogger(__name__)

# Algorand TestNet CAIP-2 network id + testnet USDC ASA.
ALGORAND_TESTNET_CAIP2 = "algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="
USDC_TESTNET_ASA = 10458941

X402_ENABLED = os.getenv("X402_ENABLED", "false").lower() == "true"
X402_RECIPIENT = os.getenv("X402_RECIPIENT", "")
X402_FACILITATOR_URL = os.getenv("X402_FACILITATOR_URL", "https://www.x402.org/facilitator")
X402_PRICE_MICRO = os.getenv("X402_PRICE_MICRO", "10000")  # micro-USDC; 10000 = $0.01
X402_ROUTE = "POST /v1/audit/x402"


def install_x402(app) -> bool:
    """
    Install x402 payment middleware protecting the x402 audit route.

    Returns True if the gate was installed (X402_ENABLED), False otherwise.
    """
    if not X402_ENABLED:
        logger.info("x402 gate disabled (set X402_ENABLED=true to enable)")
        return False
    if not X402_RECIPIENT:
        raise RuntimeError("X402_ENABLED=true but X402_RECIPIENT (pay-to address) is not set")

    from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
    from x402.http.middleware.fastapi import PaymentMiddlewareASGI
    from x402.http.types import RouteConfig
    from x402.mechanisms.avm.exact import ExactAvmServerScheme
    from x402.schemas import AssetAmount
    from x402.server import x402ResourceServer

    facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=X402_FACILITATOR_URL))
    server = x402ResourceServer(facilitator)
    server.register(ALGORAND_TESTNET_CAIP2, ExactAvmServerScheme())
    server.initialize()  # fetch facilitator /supported; required before building requirements

    price = AssetAmount(
        amount=X402_PRICE_MICRO,
        asset=str(USDC_TESTNET_ASA),
        extra={"name": "USDC", "decimals": 6},
    )
    routes = {
        X402_ROUTE: RouteConfig(
            accepts=PaymentOption(
                scheme="exact",
                network=ALGORAND_TESTNET_CAIP2,
                pay_to=X402_RECIPIENT,
                price=price,
            ),
        ),
    }
    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
    logger.info("x402 gate ENABLED: %s -> pay_to=%s price=%s uUSDC", X402_ROUTE, X402_RECIPIENT, X402_PRICE_MICRO)
    return True
