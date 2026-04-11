"""
Payment approval agent for AgentAudit.

Active path: decide_payment() — deterministic fallback, no external dependencies.
Production path: run_payment_agent() — LangChain agent with OpenAI (swap in when ready).

Note: the agent decides based on amount only. Vendor check happens on-chain in
the smart contract — the agent does not have access to the vendor whitelist.

To switch to LangChain: replace decide_payment() calls in audit_flow.py
with await run_payment_agent(amount, vendor_id). Interface is identical.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

POLICY_LIMIT = int(os.getenv("POLICY_LIMIT", "5000"))


# ---------------------------------------------------------------------------
# Active path — deterministic fallback (used for MVP demo)
# ---------------------------------------------------------------------------


def decide_payment(amount: int, vendor_id: str) -> tuple[str, str]:
    """
    Decide whether to approve or reject a payment based on amount policy limit.

    Drop-in replacement for run_payment_agent(). Same return signature.
    Note: vendor check is enforced on-chain, not here.
    Returns (decision, reason) where decision is "approved" or "rejected".

    Args:
        amount: Payment amount to evaluate.
        vendor_id: Vendor identifier (passed through for logging; not checked here).
    """
    if amount < POLICY_LIMIT:
        decision = "approved"
        reason = f"Amount {amount} is within policy limit {POLICY_LIMIT}"
    else:
        decision = "rejected"
        reason = f"Amount {amount} exceeds policy limit {POLICY_LIMIT}"

    logger.info("Payment decision: %s — %s (vendor: %s)", decision, reason, vendor_id)
    return decision, reason


# ---------------------------------------------------------------------------
# Production path — LangChain agent (swap in when ready, needs OPENAI_API_KEY)
# ---------------------------------------------------------------------------


async def run_payment_agent(amount: int, vendor_id: str) -> tuple[str, str]:
    """
    LangChain agent that decides payment approval using check_payment_policy tool.

    Requires OPENAI_API_KEY in .env. Same return signature as decide_payment().
    Note: vendor check is enforced on-chain, not by the agent.
    Returns (decision, reason) where decision is "approved" or "rejected".

    Uses LangChain 1.x API (create_tool_calling_agent + AgentExecutor).
    Falls back to decide_payment() on any failure.

    Args:
        amount: Payment amount to evaluate.
        vendor_id: Vendor identifier (passed through for logging; not checked here).
    """
    try:
        from langchain_core.tools import tool
        from langchain_groq import ChatGroq

        @tool
        def check_payment_policy(amount: int) -> str:
            """Check if a payment amount is within policy limits. Always use this tool."""
            if amount < POLICY_LIMIT:
                return f"approved: amount {amount} is within limit {POLICY_LIMIT}"
            return f"rejected: amount {amount} exceeds limit {POLICY_LIMIT}"

        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        llm_with_tools = llm.bind_tools([check_payment_policy])

        messages = [
            {"role": "system", "content": "You are a payment approval agent. Use the check_payment_policy tool to decide whether to approve or reject the payment. Always call the tool."},
            {"role": "user", "content": f"Should I approve a payment of amount {amount}?"},
        ]

        response = await llm_with_tools.ainvoke(messages)

        # If the model called the tool, invoke it and use the result
        if response.tool_calls:
            tool_result = check_payment_policy.invoke(response.tool_calls[0]["args"])
            logger.info("LangChain agent tool result for vendor %s: %s", vendor_id, tool_result)
            if "approved" in tool_result.lower():
                return "approved", tool_result
            return "rejected", tool_result

        # If no tool call, parse text response directly
        output = response.content or ""
        logger.info("LangChain agent text output for vendor %s: %s", vendor_id, output.strip())
        if "approved" in output.lower():
            return "approved", output.strip()
        return "rejected", output.strip()

    except Exception as e:
        logger.warning("LangChain agent failed, falling back to decide_payment: %s", e)
        return decide_payment(amount, vendor_id)
