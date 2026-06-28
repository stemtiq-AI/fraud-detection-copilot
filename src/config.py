"""
Central configuration for the Fraud Detection Co-Pilot.

Students: this is the one place to tweak the model name, thresholds,
and file paths. Everything else imports from here.
"""

from pathlib import Path

# --- Paths -------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs"

CUSTOMERS_FILE = DATA_DIR / "customers.json"
TRANSACTIONS_FILE = DATA_DIR / "transactions.json"
MERCHANT_RISK_FILE = DATA_DIR / "merchant_risk.json"
AUDIT_LOG_FILE = OUTPUT_DIR / "audit_log.json"

# --- Model ---------------------------------------------------------------
# claude-sonnet-4-6 is the current generally-available Sonnet model.
CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1500

# --- Business rules --------------------------------------------------
# Risk score (0-100) at or above this triggers a mandatory human
# checkpoint before any action is taken. This is the
# human-in-the-loop pattern: the agent recommends, a person decides.
HUMAN_REVIEW_THRESHOLD = 70

# Max tool-use turns the Investigator agent is allowed before it must
# stop and report. Prevents runaway agent loops.
MAX_AGENT_TURNS = 6
