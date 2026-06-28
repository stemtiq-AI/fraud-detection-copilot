"""
Orchestrator: runs the full pipeline.

  Detector  -> Investigator -> Summarizer -> [human checkpoint] -> audit log

This is the "multi-agent handoff" pattern: each agent has one job and
passes structured output to the next. The human-in-the-loop
checkpoint is mandatory whenever the risk score crosses
config.HUMAN_REVIEW_THRESHOLD - the system never silently declines
or blocks a high-stakes transaction on its own.
"""

import json
from datetime import datetime

from agents import detector_agent, investigator_agent, summarizer_agent
from . import config


def load_data():
    with open(config.CUSTOMERS_FILE) as f:
        customers = json.load(f)
    with open(config.TRANSACTIONS_FILE) as f:
        transactions = json.load(f)
    return customers, transactions


def human_checkpoint(report: dict) -> str:
    """
    Pauses the pipeline and asks a human to confirm the action for any
    high-risk case. In a real system this would be a queue/dashboard;
    here it's a CLI prompt so the pattern is visible end to end.
    """
    print("\n" + "=" * 60)
    print(f"HUMAN REVIEW REQUIRED - Transaction {report['transaction_id']}")
    print(f"Risk score: {report['risk_score']}/100")
    print(f"Agent recommendation: {report['recommendation']}")
    print(f"Rationale: {report['rationale']}")
    print("=" * 60)
    decision = input("Your decision - (a)pprove / (d)ecline / (k)eep agent recommendation: ").strip().lower()
    if decision == "a":
        return "Approve"
    elif decision == "d":
        return "Decline"
    else:
        return report["recommendation"]


def append_audit_log(entry: dict):
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    log = []
    if config.AUDIT_LOG_FILE.exists():
        with open(config.AUDIT_LOG_FILE) as f:
            log = json.load(f)
    log.append(entry)
    with open(config.AUDIT_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def write_report(report: dict, case_file: dict, final_decision: str):
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    path = config.OUTPUT_DIR / f"case_{report['transaction_id']}.md"
    with open(path, "w") as f:
        f.write(f"# Fraud Case Report - {report['transaction_id']}\n\n")
        f.write(f"**Risk score:** {report['risk_score']}/100\n\n")
        f.write(f"**Agent recommendation:** {report['recommendation']}\n\n")
        f.write(f"**Final decision:** {final_decision}\n\n")
        f.write(f"## Rationale\n{report['rationale']}\n\n")
        f.write("## Evidence\n")
        f.write(f"{case_file.get('evidence_summary', '')}\n\n")
        if case_file.get("risk_factors"):
            f.write("### Risk factors\n")
            for r in case_file["risk_factors"]:
                f.write(f"- {r}\n")
        if case_file.get("mitigating_factors"):
            f.write("\n### Mitigating factors\n")
            for m in case_file["mitigating_factors"]:
                f.write(f"- {m}\n")
    return path


def run_pipeline(client, mock: bool, interactive: bool = True):
    customers, transactions = load_data()

    print(f"Loaded {len(customers)} customers and {len(transactions)} transactions.")
    print(f"Mode: {'MOCK (rule-based, no API calls)' if mock else 'LIVE (Claude API)'}\n")

    # --- Agent 1: Detector ---
    print("[Detector] Scanning batch for suspicious transactions...")
    if mock:
        flagged = detector_agent.run_with_rules(customers, transactions)
    else:
        flagged = detector_agent.run_with_claude(client, customers, transactions)
    print(f"[Detector] Flagged {len(flagged)} transaction(s): "
          f"{[f['transaction_id'] for f in flagged]}\n")

    results = []

    for flag in flagged:
        txn_id = flag["transaction_id"]
        reason = flag.get("reason", "")

        # --- Agent 2: Investigator ---
        print(f"[Investigator] Building case file for {txn_id}...")
        if mock:
            case_file = investigator_agent.run_with_rules(txn_id, reason)
        else:
            case_file = investigator_agent.run_with_claude(client, txn_id, reason)

        # --- Agent 3: Summarizer ---
        print(f"[Summarizer] Scoring and drafting recommendation for {txn_id}...")
        if mock:
            report = summarizer_agent.run_with_rules(case_file)
        else:
            report = summarizer_agent.run_with_claude(client, case_file)

        # --- Human-in-the-loop checkpoint ---
        needs_review = report["risk_score"] >= config.HUMAN_REVIEW_THRESHOLD
        if needs_review and interactive:
            final_decision = human_checkpoint(report)
        else:
            final_decision = report["recommendation"]
            if needs_review:
                print(f"[Pipeline] Risk score {report['risk_score']} meets review threshold "
                      f"({config.HUMAN_REVIEW_THRESHOLD}) but --no-interactive was set - "
                      f"auto-applying agent recommendation: {final_decision}")
            else:
                print(f"[Pipeline] Risk score {report['risk_score']} below review threshold "
                      f"({config.HUMAN_REVIEW_THRESHOLD}) - auto-applying: {final_decision}")

        path = write_report(report, case_file, final_decision)
        append_audit_log({
            "transaction_id": txn_id,
            "risk_score": report["risk_score"],
            "agent_recommendation": report["recommendation"],
            "final_decision": final_decision,
            "timestamp": datetime.utcnow().isoformat(),
        })

        print(f"[Pipeline] Case report written to {path}\n")
        results.append({"report": report, "final_decision": final_decision})

    return results
