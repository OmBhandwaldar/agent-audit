"""
Payment approval agent for AgentAudit.

Active path: decide_payment() — deterministic fallback, no external dependencies.
Production path: run_payment_agent() — LangChain agent with OpenAI (swap in when ready).

To switch to LangChain: replace decide_payment() calls in audit_flow.py
with await run_payment_agent(amount). Interface is identical.
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


def decide_payment(amount: int) -> tuple[str, str]:
    """
    Decide whether to approve or reject a payment based on policy limit.

    Drop-in replacement for run_payment_agent(). Same return signature.
    Returns (decision, reason) where decision is "approved" or "rejected".

    Args:
        amount: Payment amount to evaluate.
    """
    if amount < POLICY_LIMIT:
        decision = "approved"
        reason = f"Amount {amount} is within policy limit {POLICY_LIMIT}"
    else:
        decision = "rejected"
        reason = f"Amount {amount} exceeds policy limit {POLICY_LIMIT}"

    logger.info("Payment decision: %s — %s", decision, reason)
    return decision, reason


# ---------------------------------------------------------------------------
# Production path — LangChain agent (swap in when ready, needs OPENAI_API_KEY)
# ---------------------------------------------------------------------------


async def run_payment_agent(amount: int) -> tuple[str, str]:
    """
    LangChain agent that decides payment approval using check_payment_policy tool.

    Requires OPENAI_API_KEY in .env. Same return signature as decide_payment().
    Returns (decision, reason) where decision is "approved" or "rejected".

    Args:
        amount: Payment amount to evaluate.
    """
    from langchain.agents import AgentType, initialize_agent
    from langchain.tools import tool
    from langchain_openai import ChatOpenAI

    @tool
    def check_payment_policy(amount: int) -> str:
        """Check if a payment amount is within policy limits. Always use this tool."""
        if amount < POLICY_LIMIT:
            return f"approved: amount {amount} is within limit {POLICY_LIMIT}"
        return f"rejected: amount {amount} exceeds limit {POLICY_LIMIT}"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    agent = initialize_agent(
        tools=[check_payment_policy],
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=False,
    )

    prompt = (
        f"You are a payment approval agent. "
        f"Use the check_payment_policy tool to decide whether to approve "
        f"or reject a payment of amount {amount}. Always use the tool."
    )

    try:
        output = await agent.arun(prompt)
        output_lower = output.lower()
        if "approved" in output_lower:
            return "approved", output.strip()
        return "rejected", output.strip()
    except Exception as e:
        logger.warning("LangChain agent failed, falling back to decide_payment: %s", e)
        return decide_payment(amount)
