# Fraud Detection Co-Pilot

A reference implementation for the **Fraud Detection Co-Pilot** project
(target company: **JPMorgan Chase**).

**Start with [`MASTER.md`](./MASTER.md)** — it has the full purpose,
architecture diagram, agent roster, data schemas, and orchestration
logic. This README is just setup and run commands.

Each agent has its own spec + implementation, paired by name under
`agents/`:

```
agents/detector_agent.md      <- purpose, guardrails, success metrics, system prompt
agents/detector_agent.py      <- loads its system prompt directly from the .md above
agents/investigator_agent.md
agents/investigator_agent.py
agents/summarizer_agent.md
agents/summarizer_agent.py
```

**Read the `.md` before the `.py`.** The markdown file is the source
of truth for what the agent is supposed to do; the Python file is
just the implementation, and it literally parses its system prompt
out of the markdown rather than duplicating it (see
`src/agent_spec.py`).

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # get one at console.anthropic.com
```

## Running it

**Try it first with zero setup** (rule-based agents, no API key, no cost):
```bash
python main.py --mock
```

**Run it for real**, with Claude actually reasoning and calling tools:
```bash
python main.py
```

Add `--no-interactive` to skip the `input()` prompt at the human
checkpoint (useful for demos/CI) — it auto-accepts the agent's
recommendation and still logs that the case crossed the review
threshold.

Each run produces:
- `outputs/case_<TXN_ID>.md` — a readable report per flagged transaction
- `outputs/audit_log.json` — a running log of every decision made

## A note on `run_with_rules()` vs `run_with_claude()`

Every agent ships two implementations. `run_with_rules()` is a plain
Python fallback so the pipeline runs for free, instantly, with no API
key — it's a testing fixture, **not** the spec'd agent (see each
agent's "Implementation notes" section). `run_with_claude()` is the
real agentic version that actually follows its `.md` spec. **Run both
on the same data and compare** — it's the fastest way to see what
reasoning the LLM adds over hardcoded rules, and where it costs you
(latency, $, predictability).

## Extension ideas

See "Production data model" in `MASTER.md` for how this would harden
into a real system (proper DB schema, persisted tool-call transcripts
for audit). Other good "go further" directions:

- **Memory across cases** — let the Detector learn a customer's
  evolving "normal" instead of a static average each run.
- **Feedback loop** — log human overrides of agent recommendations
  and use them to evaluate/tune `HUMAN_REVIEW_THRESHOLD`.
- **Web review queue** — replace the CLI `human_checkpoint()` with a
  simple Flask/Streamlit UI.
- **Evaluation harness** — run the pipeline against a labeled dataset
  and report precision/recall, the way a real fraud team would
  evaluate a model change before shipping it.
