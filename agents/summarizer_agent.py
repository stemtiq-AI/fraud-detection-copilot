"""
Agent 3: Summarizer

Implements the spec defined in agents/summarizer_agent.md. The system
prompt is loaded from that file's
"<!-- BEGIN/END SYSTEM PROMPT -->" section - it is the source of
truth, not the string below. Read summarizer_agent.md for full
purpose, guardrails (including the hard escalation-threshold rule),
and success metrics.
"""

import json
from pathlib import Path

from src import config
from src.agent_spec import load_system_prompt

SPEC_PATH = Path(__file__).resolve().parent / "summarizer_agent.md"
SYSTEM_PROMPT = load_system_prompt(SPEC_PATH)


def run_with_claude(client, case_file: dict) -> dict:
    """The spec'd agent. See summarizer_agent.md."""
    user_message = json.dumps(case_file, indent=2)

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
        cleaned = text.strip("`").replace("json\n", "", 1)
        return json.loads(cleaned)


def run_with_rules(case_file: dict) -> dict:
    """
    Testing fixture only - NOT the spec'd agent (see "Implementation
    notes" in summarizer_agent.md). Deterministic scoring formula so
    --mock mode can run without an API key. Still mechanically
    enforces the hard escalation-threshold rule from the spec.
    """
    risk_factors = case_file.get("risk_factors", [])
    mitigating = case_file.get("mitigating_factors", [])

    # Simple deterministic scoring: each risk factor adds points,
    # each mitigating factor subtracts a few.
    score = min(100, max(0, len(risk_factors) * 30 - len(mitigating) * 10 + 10))

    if score >= config.HUMAN_REVIEW_THRESHOLD:
        recommendation = "Escalate to Human"
    elif score <= 30:
        recommendation = "Approve"
    else:
        recommendation = "Decline"

    rationale = case_file.get("evidence_summary", "No evidence summary available.")
    if risk_factors:
        rationale += " Key risk factors: " + "; ".join(risk_factors) + "."

    return {
        "transaction_id": case_file.get("transaction_id"),
        "risk_score": score,
        "recommendation": recommendation,
        "rationale": rationale,
    }
