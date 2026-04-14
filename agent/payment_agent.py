"""
Payment approval agent for AgentAudit.

Two modes:

1. run_payment_agent(amount, vendor_id) — original flow (used by /api/audit).
   Agent decides approve/reject based on amount. Vendor check is on-chain.

2. run_chat_agent(prompt) — new chat flow (used by /api/chat).
   Agent receives a natural language task, autonomously picks a vendor and
   price from the vendor registry, then returns the full selection.

Fallback: decide_payment() — deterministic, no external deps. Always kept.
"""

import logging
import os

from dotenv import load_dotenv

from agent.vendors import VENDOR_REGISTRY, get_vendors_summary, get_vendor_by_id

load_dotenv()

logger = logging.getLogger(__name__)

POLICY_LIMIT = int(os.getenv("POLICY_LIMIT", "5000"))


# ---------------------------------------------------------------------------
# Fallback — deterministic, no LangChain required
# ---------------------------------------------------------------------------


def decide_payment(amount: int, vendor_id: str) -> tuple[str, str]:
    """
    Decide payment approval based on amount policy limit.

    Drop-in replacement for run_payment_agent(). Same return signature.
    Vendor check is enforced on-chain, not here.

    Args:
        amount: Payment amount to evaluate.
        vendor_id: Vendor identifier (for logging only).

    Returns:
        (decision, reason) where decision is "approved" or "rejected".
    """
    if amount < POLICY_LIMIT:
        decision = "approved"
        reason = f"Amount {amount} is within policy limit {POLICY_LIMIT}"
    else:
        decision = "rejected"
        reason = f"Amount {amount} exceeds policy limit {POLICY_LIMIT}"

    logger.info("Fallback decision: %s — %s (vendor: %s)", decision, reason, vendor_id)
    return decision, reason


def decide_vendor_and_payment(prompt: str) -> tuple[str, int, str, str]:
    """
    Fallback for run_chat_agent. Picks VENDOR_001 at ₹4500 regardless of prompt.

    Returns:
        (vendor_id, amount, decision, reason)
    """
    vendor = VENDOR_REGISTRY[0]
    amount = vendor["price"]
    reason = f"Selected {vendor['name']} at Rs{amount} (default fallback selection)"
    logger.info("Chat fallback: selected %s at %d", vendor["id"], amount)
    return vendor["id"], amount, "approved", reason


# ---------------------------------------------------------------------------
# Original flow — LangChain agent for /api/audit
# ---------------------------------------------------------------------------


async def run_payment_agent(amount: int, vendor_id: str) -> tuple[str, str]:
    """
    LangChain agent that decides payment approval using check_payment_policy tool.

    Falls back to decide_payment() on any failure.

    Args:
        amount: Payment amount to evaluate.
        vendor_id: Vendor identifier (for logging; vendor check is on-chain).

    Returns:
        (decision, reason) where decision is "approved" or "rejected".
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

        if response.tool_calls:
            tool_result = check_payment_policy.invoke(response.tool_calls[0]["args"])
            logger.info("LangChain tool result for vendor %s: %s", vendor_id, tool_result)
            if "approved" in tool_result.lower():
                return "approved", tool_result
            return "rejected", tool_result

        output = response.content or ""
        logger.info("LangChain text output for vendor %s: %s", vendor_id, output.strip())
        if "approved" in output.lower():
            return "approved", output.strip()
        return "rejected", output.strip()

    except Exception as e:
        logger.warning("LangChain agent failed, falling back to decide_payment: %s", e)
        return decide_payment(amount, vendor_id)


# ---------------------------------------------------------------------------
# Chat flow — autonomous vendor selection for /api/chat
# ---------------------------------------------------------------------------


async def run_chat_agent(prompt: str) -> tuple[str, int, str, str]:
    """
    LangChain agent that autonomously selects a vendor and price given a task prompt.

    Tools available:
      - get_available_vendors: lists all vendors with prices
      - finalize_vendor: commits to a vendor_id and amount

    Returns:
        (vendor_id, amount, decision, reason)
        decision is always "approved" at agent level — on-chain policy decides final outcome.

    Falls back to decide_vendor_and_payment() on any failure.

    Args:
        prompt: Natural language task from the user, e.g.
                "Find a vendor for office electronics and pay him."
    """
    try:
        from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
        from langchain_core.tools import tool
        from langchain_groq import ChatGroq

        selected: dict = {}  # mutable store for the finalize_vendor tool to write into

        @tool
        def get_available_vendors() -> str:
            """Get the list of available vendors with their prices and categories."""
            return get_vendors_summary()

        @tool
        def finalize_vendor(vendor_id: str, amount: int) -> str:
            """
            Finalize the vendor selection and payment amount.
            Call this once you have decided which vendor to use.

            Args:
                vendor_id: The vendor ID to select (e.g. VENDOR_001).
                amount: The agreed payment amount in Rs.
            """
            vendor = get_vendor_by_id(vendor_id)
            if not vendor:
                return f"Error: vendor {vendor_id} not found in registry."
            selected["vendor_id"] = vendor_id
            selected["amount"] = amount
            selected["vendor_name"] = vendor["name"]
            return f"Finalized: {vendor['name']} ({vendor_id}) at Rs{amount}."

        tools = [get_available_vendors, finalize_vendor]
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        llm_with_tools = llm.bind_tools(tools)

        system_prompt = (
            f"You are an autonomous procurement agent. Your job:\n"
            f"1. Call get_available_vendors to see what is available.\n"
            f"2. Pick the best vendor for the task. Consider price and fit.\n"
            f"3. Call finalize_vendor with your chosen vendor_id and price.\n"
            f"Budget limit is Rs{POLICY_LIMIT}. Prefer cost-effective options.\n"
            f"You MUST call finalize_vendor before finishing.\n\n"
            f"IMPORTANT: If the user's message is NOT related to procurement, vendor selection, "
            f"or payment — do NOT call any tools. Just reply with a short, polite message "
            f"saying you can only help with procurement and vendor-related tasks."
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]

        # Agentic loop — keep calling until finalize_vendor is invoked
        tool_map = {t.name: t for t in tools}

        for _ in range(6):  # max 6 iterations to prevent infinite loop
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)

            if not response.tool_calls:
                break  # agent finished without calling tools

            for tc in response.tool_calls:
                tool_result = tool_map[tc["name"]].invoke(tc["args"])
                messages.append(ToolMessage(content=str(tool_result), tool_call_id=tc["id"]))
                logger.info("Chat agent tool %s(%s) → %s", tc["name"], tc["args"], tool_result)

            if "vendor_id" in selected:
                break  # finalize_vendor was called, we have what we need

        if not selected:
            # Agent responded with text only — off-topic or unclear request
            last_text = next(
                (m.content for m in reversed(messages) if hasattr(m, "content") and m.content),
                "I can only help with procurement and vendor-related tasks."
            )
            logger.info("Chat agent returned off-topic response: %s", last_text)
            return None, 0, None, last_text

        vendor_id = selected["vendor_id"]
        amount = selected["amount"]
        vendor_name = selected.get("vendor_name", vendor_id)
        reason = f"Agent selected {vendor_name} ({vendor_id}) at Rs{amount} for: {prompt}"
        logger.info("Chat agent finalized: vendor=%s amount=%d", vendor_id, amount)
        return vendor_id, amount, "approved", reason

    except Exception as e:
        logger.warning("Chat agent failed, using fallback: %s", e)
        return decide_vendor_and_payment(prompt)
