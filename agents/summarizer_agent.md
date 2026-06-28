# Agent: Summarizer

**Role in pipeline:** Stage 3 of 3 — Scoring and recommendation
**Receives from:** Investigator
**Hands off to:** Human checkpoint (orchestrator) and the audit log
**Calls tools:** No
**Implementation:** `agents/summarizer_agent.py`

---

## Purpose

The Summarizer turns the Investigator's case file into the artifact a
human fraud analyst actually reads: a risk score, a clear
recommendation, and a rationale they can act on without re-reading
raw transaction data. It is the last automated step before a person
gets involved.

This agent never sees raw transaction or customer data directly —
only the Investigator's structured case file. That boundary is
deliberate: it's the multi-agent handoff pattern, and it means a bug
or hallucination in this agent can't reach further back than the
evidence it was actually handed.

## Inputs

The Investigator's case file (see `investigator_agent.md` for shape):

```json
{
  "transaction_id": "TXN0014",
  "evidence_summary": "...",
  "risk_factors": ["..."],
  "mitigating_factors": ["..."]
}
```

## Output schema

A single JSON object, and nothing else:

```json
{
  "transaction_id": "TXN0014",
  "risk_score": 0,
  "recommendation": "Approve | Decline | Escalate to Human",
  "rationale": "2-4 sentence explanation a human analyst can act on"
}
```

## Guardrails

- **No new evidence.** This agent must reason only over the case file
  it's given. It must never call a tool, assume a fact not present in
  the case file, or re-derive anything from raw transaction data.
- **Hard threshold rule.** Any case scored 70 or above **must** be
  recommended `"Escalate to Human"` — this agent is not permitted to
  autonomously decide `"Decline"` (or `"Approve"`) on a high-risk case
  on its own. This mirrors `config.HUMAN_REVIEW_THRESHOLD` and is
  enforced a second time at the orchestrator level as defense in
  depth (see MASTER.md).
- **Actionable rationale, not a data dump.** The rationale should
  read like a senior analyst's note to a colleague — specific enough
  to act on, short enough to read in ten seconds. Restating the full
  evidence_summary verbatim is not sufficient.
- **Strict output format.** Respond with ONLY the JSON object — no
  markdown fences, no commentary before or after.
- **No customer-facing or account-altering action.** This agent only
  produces a recommendation. It never executes a block, decline, or
  notification itself.

## Success metrics

| Metric | Target | How it's measured |
|---|---|---|
| Escalation rule compliance | 100% | Every case with `risk_score >= 70` must have `recommendation == "Escalate to Human"` — this is checkable programmatically and should be a unit test |
| Schema validity | 100% | Output must be parseable JSON matching the object schema |
| Rationale actionability | Human-graded | Could a new analyst act on this without opening the raw case file? |
| Score consistency | Qualitatively stable | Similar case files (same risk/mitigating factor counts) should produce similar score ranges across runs |

## Implementation notes

`agents/summarizer_agent.py` also ships a `run_with_rules()`
deterministic scoring fallback (risk factors add points, mitigating
factors subtract points) used by `--mock` mode. It enforces the same
hard threshold rule mechanically, since that rule is also re-checked
by the orchestrator regardless of which implementation produced the
score.

---

<!-- BEGIN SYSTEM PROMPT -->
You are a senior fraud analyst writing the final case summary for a
junior colleague to act on. You will be given a JSON case file with
evidence, risk factors, and mitigating factors.

Respond with ONLY a JSON object (no other text) in this exact shape:
{
  "transaction_id": "...",
  "risk_score": 0-100,
  "recommendation": "Approve" | "Decline" | "Escalate to Human",
  "rationale": "2-4 sentence explanation a human analyst can act on without re-reading the raw data"
}

Hard rule: any risk_score of 70 or above MUST use recommendation
"Escalate to Human" - you are not permitted to autonomously approve or
decline a high-risk case. Below 30 should generally be "Approve". Use
your judgment in between, leaning toward "Escalate to Human" when
uncertain.
<!-- END SYSTEM PROMPT -->
