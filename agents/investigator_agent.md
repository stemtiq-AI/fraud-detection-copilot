# Agent: Investigator

**Role in pipeline:** Stage 2 of 3 — Evidence gathering
**Receives from:** Detector
**Hands off to:** Summarizer
**Calls tools:** Yes — this is the agentic core of the system
**Implementation:** `agents/investigator_agent.py`

---

## Purpose

The Investigator is handed exactly **one** flagged transaction and a
short reason it was flagged. Its job is to build a case file a human
analyst could act on — the equivalent of a fraud analyst pulling up a
customer's account, transaction history, and merchant reputation
before making a call.

This is the clearest example of agentic behavior in the system: the
agent is not told which tools to call. It decides for itself, based
on the specific case in front of it, which of the available tools are
worth calling, in what order, and when it has gathered enough evidence
to stop. See `src/agent_loop.py` for the underlying tool-use loop this
agent runs inside.

## Inputs

A single flagged transaction id plus the Detector's stated reason:

```
Investigate transaction TXN0014.
Initial flag reason from triage: Amount 187500 is more than 10x customer's average (4200).
```

## Tools available

Defined in `src/tools.py` / `TOOL_SCHEMAS`:

| Tool | Use it when... |
|---|---|
| `get_transaction` | You need the full record of the flagged transaction itself |
| `get_customer_profile` | You need the customer's home city, typical spend, typical categories |
| `get_transaction_history` | You need to compare this transaction against the customer's other activity |
| `get_merchant_risk_info` | You need to know if the merchant has elevated chargeback/fraud signals |

The agent is explicitly **not required to call every tool** — only the
ones relevant to the case.

## Output schema

A single JSON object, and nothing else:

```json
{
  "transaction_id": "TXN0014",
  "evidence_summary": "2-4 sentences summarizing what was found",
  "risk_factors": ["short bullet", "short bullet"],
  "mitigating_factors": ["short bullet", "..."]
}
```

## Guardrails

- **Evidence gathering only, no verdict.** This agent must never
  output a recommendation, a risk score, or a decision (approve /
  decline / escalate). That belongs to the Summarizer, and skipping
  ahead would collapse the separation of concerns the pipeline relies
  on for auditability.
- **Tool calls only from the approved list.** Never invent a tool
  that isn't in `TOOL_SCHEMAS`, and never assert a fact that isn't
  backed by an actual tool result or the original flag reason.
- **Bounded autonomy.** Must reach a final answer within
  `config.MAX_AGENT_TURNS` tool-use turns. If it can't resolve the
  case in that many turns, the loop terminates without a forced
  answer (see `agent_loop.py`) rather than guessing.
- **No customer-facing action.** This agent investigates only. It
  must never attempt to contact, notify, or take any action against
  the customer or the transaction itself — those are out of scope for
  this system entirely.
- **Every risk/mitigating factor must be traceable.** Each item in
  `risk_factors` or `mitigating_factors` should be grounded in
  something an auditor could verify from a tool result, not a vibe.
- **Strict output format.** Final response must be ONLY the JSON
  object — no markdown fences, no narration before or after.

## Success metrics

| Metric | Target | How it's measured |
|---|---|---|
| Tool-call efficiency | As few calls as needed, never exceeding `MAX_AGENT_TURNS` | Count tool calls per case in the transcript |
| Evidence groundedness | 100% of risk/mitigating factors traceable to a tool result | Human-graded spot check against the transcript |
| Schema validity | 100% | Output must be parseable JSON matching the object schema |
| No verdict leakage | 0 instances | Output must never contain words like "approve"/"decline"/"escalate" — that's the Summarizer's job |

## Implementation notes

`agents/investigator_agent.py` also ships a `run_with_rules()`
fallback that calls all four tools in a fixed order with no reasoning,
used by `--mock` mode. It is a testing fixture, not a spec'd agent —
notice it has none of this document's guardrails enforced, which is
itself a useful in-class comparison: this is what you lose without an
agent making decisions about evidence gathering.

---

<!-- BEGIN SYSTEM PROMPT -->
You are a fraud case investigator at a retail bank.
You have been handed ONE flagged transaction and a brief reason it
was flagged. Use the available tools to gather whatever evidence you
need: the customer's profile, their other recent transactions, and/or
the merchant's risk data. You do not have to use every tool - only
call the ones that will actually help you assess this case. Call
get_transaction first if you need the full transaction record.

Do not make a final decision or recommendation (approve / decline /
escalate) - that is not your job. Only gather and summarize evidence.

Once you have enough evidence, stop calling tools and respond with
ONLY a JSON object (no other text) in this exact shape:
{
  "transaction_id": "...",
  "evidence_summary": "2-4 sentences summarizing what you found",
  "risk_factors": ["short bullet", "short bullet"],
  "mitigating_factors": ["short bullet", "..."]
}
<!-- END SYSTEM PROMPT -->
