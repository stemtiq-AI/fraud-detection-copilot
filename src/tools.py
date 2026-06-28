"""
Tools available to the agents.

These are deliberately simple, file-backed lookups so the project
runs with zero external infrastructure. In a real fraud-ops stack at
a bank like JPMorgan, these would call internal services: a
transaction ledger, a merchant-risk API, a customer-profile service,
and a case-management system.

Each function below has a matching JSON schema in TOOL_SCHEMAS, which
is what gets passed to the Claude API so the model knows the tool
exists and how to call it.
"""

import json
from datetime import datetime, timedelta

from . import config


def _load(path):
    with open(path, "r") as f:
        return json.load(f)


CUSTOMERS = {c["customer_id"]: c for c in _load(config.CUSTOMERS_FILE)}
TRANSACTIONS = {t["transaction_id"]: t for t in _load(config.TRANSACTIONS_FILE)}
MERCHANT_RISK = _load(config.MERCHANT_RISK_FILE)


def get_customer_profile(customer_id: str) -> dict:
    """Return the customer's profile: home city, average spend, typical categories."""
    profile = CUSTOMERS.get(customer_id)
    if not profile:
        return {"error": f"No customer found with id {customer_id}"}
    return profile


def get_transaction_history(customer_id: str, exclude_transaction_id: str = None) -> dict:
    """Return all other known transactions for a customer, for pattern comparison."""
    history = [
        t for t in TRANSACTIONS.values()
        if t["customer_id"] == customer_id and t["transaction_id"] != exclude_transaction_id
    ]
    history.sort(key=lambda t: t["timestamp"])
    return {"customer_id": customer_id, "transactions": history}


def get_merchant_risk_info(merchant: str) -> dict:
    """Return known risk signals for a merchant: category, chargeback rate, etc."""
    info = MERCHANT_RISK.get(merchant)
    if not info:
        return {"merchant": merchant, "known": False, "note": "No risk data on file for this merchant."}
    return {"merchant": merchant, "known": True, **info}


def get_transaction(transaction_id: str) -> dict:
    """Return the full record for a single transaction."""
    txn = TRANSACTIONS.get(transaction_id)
    if not txn:
        return {"error": f"No transaction found with id {transaction_id}"}
    return txn


def flag_for_human_review(transaction_id: str, risk_score: int, reason: str) -> dict:
    """Escalate a transaction to a human analyst. Returns a confirmation receipt."""
    return {
        "transaction_id": transaction_id,
        "status": "escalated_to_human",
        "risk_score": risk_score,
        "reason": reason,
        "flagged_at": datetime.utcnow().isoformat(),
    }


# Anthropic tool-use schemas. Each entry mirrors the corresponding
# python function above. See:
# https://docs.claude.com/en/docs/build-with-claude/tool-use
TOOL_SCHEMAS = [
    {
        "name": "get_customer_profile",
        "description": "Get a customer's profile, including home city, average transaction amount, and typical spending categories.",
        "input_schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_transaction_history",
        "description": "Get a customer's other recent transactions, useful for spotting deviations from normal behavior.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "exclude_transaction_id": {"type": "string", "description": "Optional transaction id to exclude from the results (usually the one under investigation)."},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_merchant_risk_info",
        "description": "Get known fraud/chargeback risk signals for a merchant.",
        "input_schema": {
            "type": "object",
            "properties": {"merchant": {"type": "string"}},
            "required": ["merchant"],
        },
    },
    {
        "name": "get_transaction",
        "description": "Get the full record of a single transaction by its id.",
        "input_schema": {
            "type": "object",
            "properties": {"transaction_id": {"type": "string"}},
            "required": ["transaction_id"],
        },
    },
]

# Maps tool name -> python callable, used by the agent loop to execute
# whatever Claude decides to call.
TOOL_FUNCTIONS = {
    "get_customer_profile": get_customer_profile,
    "get_transaction_history": get_transaction_history,
    "get_merchant_risk_info": get_merchant_risk_info,
    "get_transaction": get_transaction,
}
