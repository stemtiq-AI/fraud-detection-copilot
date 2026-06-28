# MASTER: Fraud Detection Co-Pilot

**Target company:** JPMorgan Chase
**Category:** Agentic AI in Finance
**Implementation entry point:** `main.py` → `src/orchestrator.py`

This is the master spec for the whole system. It defines *why* the
system exists, *how* the agents fit together, and the *data
contracts* between them. Each agent's own behavior — its prompt,
guardrails, and success criteria — is defined in its own file under
`agents/`. This document is the map; the agent `.md` files are the
territory.

---

## 1. Purpose and context

Retail banks process enormous transaction volumes and cannot have a
human review every one. JPMorgan's real fraud operations rely on a
layered system: automated triage narrows millions of transactions
down to a manageable number of cases, an investigation layer gathers
context on each case, and a human analyst makes the final call on
anything with real financial or relationship stakes.

This project rebuilds that shape at toy scale, as a **three-agent
pipeline** with a **mandatory human checkpoint** for high-risk cases.
The goal is not to replace the analyst — it's to make them faster and
better-informed, and to never let the system silently take a
high-stakes action on its own.

## 2. System architecture

```
                ┌────────────┐      ┌────────────────┐      ┌──────────────┐
   all txns --> │  Detector  │ ---> │  Investigator   │ ---> │  Summarizer  │
                │  (triage)  │      │ (tool-use loop) │      │  (scoring)   │
                └────────────┘      └────────────────┘      └──────────────┘
                                                                     │
                                                                     v
                                                     risk_score >= 70 ?
                                                      /              \
                                                   yes                no
                                                    │                  │
                                                    v                  v
                                          HUMAN CHECKPOINT      auto-apply
                                          (orchestrator.py)     recommendation
                                                    │                  │
                                                    └────────┬─────────┘
                                                              v
                                                  outputs/audit_log.json
                                                  outputs/case_<TXN_ID>.md
```

Each arrow is a **multi-agent handoff**: the receiving agent only sees
the previous agent's *structured output*, never the raw upstream data
directly (the Summarizer, for instance, never sees raw transactions —
only the Investigator's case file). This keeps each agent's blast
radius contained and makes the whole pipeline auditable step by step.

## 3. Agent roster

| Agent | File (code) | File (spec) | Calls tools? | Produces |
|---|---|---|---|---|
| Detector | `agents/detector_agent.py` | `agents/detector_agent.md` | No | List of flagged transaction ids + reasons |
| Investigator | `agents/investigator_agent.py` | `agents/investigator_agent.md` | Yes (4 tools) | A structured case file |
| Summarizer | `agents/summarizer_agent.py` | `agents/summarizer_agent.md` | No | Risk score + recommendation + rationale |

**Convention:** every agent's `.py` file loads its system prompt
directly out of its `.md` file (see `src/agent_spec.py`) rather than
hardcoding the prompt as a string. The markdown spec is the source of
truth — read it before reading or editing the corresponding code.

## 4. Shared infrastructure (`src/`)

| File | Responsibility |
|---|---|
| `config.py` | Model name, `HUMAN_REVIEW_THRESHOLD`, `MAX_AGENT_TURNS`, file paths |
| `tools.py` | The tool functions agents can call, plus their Claude tool-schemas |
| `agent_loop.py` | The generic tool-use loop (send message → execute any requested tool calls → repeat until a final answer) that powers the Investigator |
| `agent_spec.py` | Parses the `<!-- BEGIN/END SYSTEM PROMPT -->` section out of an agent's `.md` file |
| `orchestrator.py` | Wires the three agents together, runs the human checkpoint, writes reports + audit log |

## 5. Data contracts (schemas)

These are the JSON shapes that pass between stages. They're enforced
informally today (each agent's `.md` spec states the schema and the
agent is prompted to follow it); see Section 7 for how a production
version would enforce them with real validation.

### Customer

```json
{
  "customer_id": "CUST1001",
  "name": "Aisha Khan",
  "home_city": "Mumbai",
  "avg_transaction_amount": 2200,
  "typical_categories": ["Groceries", "Dining", "Fuel", "Electronics"]
}
```

### Transaction

```json
{
  "transaction_id": "TXN0001",
  "customer_id": "CUST1001",
  "amount": 1850,
  "merchant": "BigBasket",
  "category": "Groceries",
  "city": "Mumbai",
  "timestamp": "2026-06-20T09:12:00",
  "card_present": true
}
```

### Merchant risk record

```json
{
  "merchant": "Global Electronics Hub",
  "category": "Electronics",
  "chargeback_rate": 0.21,
  "high_risk_category": true
}
```

### Detector output (flag)

```json
{ "transaction_id": "TXN0014", "reason": "short explanation" }
```

### Investigator output (case file)

```json
{
  "transaction_id": "TXN0014",
  "evidence_summary": "2-4 sentences",
  "risk_factors": ["..."],
  "mitigating_factors": ["..."]
}
```

### Summarizer output (report)

```json
{
  "transaction_id": "TXN0014",
  "risk_score": 100,
  "recommendation": "Escalate to Human",
  "rationale": "2-4 sentences"
}
```

### Audit log entry

```json
{
  "transaction_id": "TXN0014",
  "risk_score": 100,
  "agent_recommendation": "Escalate to Human",
  "final_decision": "Escalate to Human",
  "timestamp": "2026-06-21T14:23:01.041633"
}
```

## 6. Orchestration logic (`src/orchestrator.py`)

1. Load `data/customers.json` and `data/transactions.json`.
2. Run **Detector** once over the whole batch → list of flags.
3. For each flag:
   a. Run **Investigator** → case file.
   b. Run **Summarizer** → report (risk_score, recommendation, rationale).
   c. **Human checkpoint:** if `risk_score >= config.HUMAN_REVIEW_THRESHOLD`
      (default 70), pause and require a human decision
      (`approve` / `decline` / `keep agent recommendation`) before
      proceeding. This rule is enforced **twice** - once inside the
      Summarizer's own guardrails, once again here at the orchestrator
      level - as defense in depth. A prompt-level guardrail alone is
      not trusted as the only safeguard for a high-stakes decision.
   d. Write `outputs/case_<TXN_ID>.md` and append to
      `outputs/audit_log.json`.

`--no-interactive` skips the `input()` prompt (for CI/demos) and
auto-accepts the agent's recommendation, but the underlying threshold
check and audit log entry still happen, so the case is still flagged
as having required review.

## 7. Production data model (reference)

The project uses flat JSON files so it runs with zero infrastructure.
A production version at a bank would back this with real tables.
Sketch, if you were to extend this toward production:

```sql
CREATE TABLE customers (
    customer_id            VARCHAR(20) PRIMARY KEY,
    name                    VARCHAR(255),
    home_city               VARCHAR(100),
    avg_transaction_amount  DECIMAL(12,2),
    typical_categories      JSON
);

CREATE TABLE transactions (
    transaction_id   VARCHAR(20) PRIMARY KEY,
    customer_id       VARCHAR(20) REFERENCES customers(customer_id),
    amount            DECIMAL(12,2) NOT NULL,
    merchant          VARCHAR(255) NOT NULL,
    category          VARCHAR(100),
    city              VARCHAR(100),
    occurred_at       TIMESTAMP NOT NULL,
    card_present      BOOLEAN,
    INDEX idx_customer_time (customer_id, occurred_at)
);

CREATE TABLE merchant_risk (
    merchant            VARCHAR(255) PRIMARY KEY,
    category             VARCHAR(100),
    chargeback_rate      DECIMAL(5,4),
    high_risk_category   BOOLEAN
);

CREATE TABLE fraud_cases (
    case_id             BIGINT PRIMARY KEY AUTO_INCREMENT,
    transaction_id       VARCHAR(20) REFERENCES transactions(transaction_id),
    flag_reason           TEXT,
    evidence_summary       TEXT,
    risk_factors            JSON,
    mitigating_factors      JSON,
    risk_score                SMALLINT,
    recommendation             VARCHAR(30),
    final_decision              VARCHAR(30),
    investigator_transcript      JSON,   -- full tool-call trace, for audit
    created_at                    TIMESTAMP DEFAULT now(),
    reviewed_by                   VARCHAR(100) NULL,
    reviewed_at                    TIMESTAMP NULL
);

CREATE TABLE audit_log (
    log_id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    transaction_id     VARCHAR(20),
    actor                VARCHAR(50),   -- 'detector' | 'investigator' | 'summarizer' | 'human:<analyst_id>'
    action                VARCHAR(50),
    payload                JSON,
    created_at              TIMESTAMP DEFAULT now()
);
```

Notes for students extending this:
- `fraud_cases.investigator_transcript` is where you'd persist the
  full tool-call trace from `agent_loop.py`'s transcript return value
  — currently discarded after each run, but it's exactly what a real
  audit/compliance team would want preserved.
- `audit_log` here is normalized per-actor rather than the flat
  per-case JSON file the toy version uses, so you can reconstruct the
  full decision trail for any transaction, not just the final outcome.

## 8. How to run

See `README.md` for setup and run commands. Quick reference:

```bash
python main.py --mock     # rule-based fallback agents, no API key needed
python main.py            # real Claude-driven agents, needs ANTHROPIC_API_KEY
```

## 9. File map

```
fraud-detection-copilot/
├── MASTER.md                      <- you are here
├── README.md                      <- setup/run instructions
├── main.py
├── requirements.txt
├── agents/
│   ├── detector_agent.md          <- spec: purpose, guardrails, metrics, system prompt
│   ├── detector_agent.py          <- implementation, loads prompt from the .md above
│   ├── investigator_agent.md
│   ├── investigator_agent.py
│   ├── summarizer_agent.md
│   └── summarizer_agent.py
├── src/
│   ├── config.py
│   ├── tools.py
│   ├── agent_loop.py
│   ├── agent_spec.py              <- parses system prompts out of agent .md files
│   └── orchestrator.py
├── data/
│   ├── customers.json
│   ├── transactions.json
│   └── merchant_risk.json
└── outputs/                       <- generated case reports + audit log
```
