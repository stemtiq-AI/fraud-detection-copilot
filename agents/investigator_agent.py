"""
Agent 2: Investigator

Implements the spec defined in agents/investigator_agent.md. The
system prompt is loaded from that file's
"<!-- BEGIN/END SYSTEM PROMPT -->" section - it is the source of
truth, not the string below. Read investigator_agent.md for full
purpose, available tools, guardrails, and success metrics.
"""

import json
from pathlib import Path

from src import config, tools
from src.agent_loop import run_agent_loop
from src.agent_spec import load_system_prompt

SPEC_PATH = Path(__file__).resolve().parent / "investigator_agent.md"
SYSTEM_PROMPT = load_system_prompt(SPEC_PATH)


def run_with_claude(client, transaction_id: str, flag_reason: str) -> dict:
    """The spec'd agent. See investigator_agent.md."""
    user_message = (
        f"Investigate transaction {transaction_id}.\n"
        f"Initial flag reason from triage: {flag_reason}"
    )

    final_text, _transcript = run_agent_loop(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_message=user_message,
        tool_schemas=tools.TOOL_SCHEMAS,
        tool_functions=tools.TOOL_FUNCTIONS,
    )

    if final_text is None:
        return {
            "transaction_id": transaction_id,
            "evidence_summary": "Investigation did not complete within the turn limit.",
            "risk_factors": [],
            "mitigating_factors": [],
        }

    try:
        return json.loads(final_text)
    except json.JSONDecodeError:
        cleaned = final_text.strip("`").replace("json\n", "", 1)
        return json.loads(cleaned)


def run_with_rules(transaction_id: str, flag_reason: str) -> dict:
    """
    Testing fixture only - NOT the spec'd agent (see "Implementation
    notes" in investigator_agent.md). Calls every tool in a fixed
    order with no reasoning, so --mock mode can run without an API
    key. Notice this has none of the .md file's guardrails enforced -
    a good in-class comparison point.
    """
    txn = tools.get_transaction(transaction_id)
    customer = tools.get_customer_profile(txn["customer_id"])
    history = tools.get_transaction_history(txn["customer_id"], exclude_transaction_id=transaction_id)
    merchant = tools.get_merchant_risk_info(txn["merchant"])

    risk_factors = [flag_reason]
    mitigating = []

    if merchant.get("high_risk_category"):
        risk_factors.append(f"Merchant '{txn['merchant']}' has an elevated chargeback rate "
                             f"({merchant.get('chargeback_rate', 0) * 100:.1f}%).")
    if not txn.get("card_present", True):
        risk_factors.append("Card was not physically present for this transaction.")
    if txn["amount"] <= customer.get("avg_transaction_amount", 0) * 1.5:
        mitigating.append("Amount is within a reasonable range of the customer's typical spend.")

    return {
        "transaction_id": transaction_id,
        "evidence_summary": (
            f"{customer.get('name', 'Customer')} normally spends ~{customer.get('avg_transaction_amount')} "
            f"per transaction in {customer.get('home_city')}. This transaction was {txn['amount']} at "
            f"{txn['merchant']} ({txn['category']}) in {txn['city']}. Customer has "
            f"{len(history.get('transactions', []))} other transactions on file."
        ),
        "risk_factors": risk_factors,
        "mitigating_factors": mitigating,
    }
