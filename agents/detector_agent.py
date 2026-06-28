"""
Agent 1: Detector

Implements the spec defined in agents/detector_agent.md. The system
prompt below is NOT hardcoded here - it's loaded directly from the
"<!-- BEGIN/END SYSTEM PROMPT -->" section of that file, so the
markdown spec is the actual source of truth for this agent's
behavior. Read detector_agent.md for full purpose, guardrails, and
success metrics before changing anything here.
"""

import json
from pathlib import Path

from src import config
from src.agent_spec import load_system_prompt

SPEC_PATH = Path(__file__).resolve().parent / "detector_agent.md"
SYSTEM_PROMPT = load_system_prompt(SPEC_PATH)


def run_with_claude(client, customers: list, transactions: list) -> list:
    """The spec'd agent. See detector_agent.md."""
    user_message = json.dumps({
        "customers": customers,
        "transactions": transactions,
    }, indent=2)

    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=config.MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Model occasionally wraps JSON in markdown fences; strip and retry once.
        cleaned = text.strip("`").replace("json\n", "", 1)
        return json.loads(cleaned)


def run_with_rules(customers: list, transactions: list) -> list:
    """
    Testing fixture only - NOT the spec'd agent (see "Implementation
    notes" in detector_agent.md). Deterministic stand-in so --mock
    mode can run the pipeline without an API key.
    """
    customer_lookup = {c["customer_id"]: c for c in customers}
    by_customer = {}
    for t in transactions:
        by_customer.setdefault(t["customer_id"], []).append(t)

    flagged = []

    for cust_id, txns in by_customer.items():
        profile = customer_lookup.get(cust_id, {})
        avg_amount = profile.get("avg_transaction_amount", 1)
        txns_sorted = sorted(txns, key=lambda t: t["timestamp"])

        # Rule 1: amount spike (>10x customer's average)
        for t in txns_sorted:
            if t["amount"] > avg_amount * 10:
                flagged.append({
                    "transaction_id": t["transaction_id"],
                    "reason": f"Amount {t['amount']} is more than 10x customer's average ({avg_amount}).",
                })

        # Rule 2: impossible travel (different cities within 90 minutes)
        for i in range(len(txns_sorted) - 1):
            a, b = txns_sorted[i], txns_sorted[i + 1]
            if a["city"] != b["city"]:
                from datetime import datetime
                t1 = datetime.fromisoformat(a["timestamp"])
                t2 = datetime.fromisoformat(b["timestamp"])
                if abs((t2 - t1).total_seconds()) < 90 * 60:
                    flagged.append({
                        "transaction_id": b["transaction_id"],
                        "reason": f"Transaction in {b['city']} occurs only "
                                  f"{int(abs((t2 - t1).total_seconds()) / 60)} minutes after a "
                                  f"transaction in {a['city']} - implausible travel.",
                    })

        # Rule 3: card-testing pattern (3+ small transactions within 5 minutes)
        small_rapid = [t for t in txns_sorted if t["amount"] < 200]
        for i in range(len(small_rapid) - 2):
            from datetime import datetime
            window = small_rapid[i:i + 3]
            t_first = datetime.fromisoformat(window[0]["timestamp"])
            t_last = datetime.fromisoformat(window[-1]["timestamp"])
            if (t_last - t_first).total_seconds() < 5 * 60:
                for t in window:
                    flagged.append({
                        "transaction_id": t["transaction_id"],
                        "reason": "Part of a rapid sequence of small transactions - possible card testing.",
                    })
                break

    # De-duplicate by transaction_id, keep first reason
    seen = {}
    for f in flagged:
        seen.setdefault(f["transaction_id"], f)
    return list(seen.values())
