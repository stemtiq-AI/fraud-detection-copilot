"""
Fraud Detection Co-Pilot - CLI entry point.

Usage:
    python main.py --mock              # run with rule-based fallback, no API key needed
    python main.py                     # run with the real Claude API (needs ANTHROPIC_API_KEY)
    python main.py --no-interactive    # skip the human-in-the-loop input() prompt (for CI/demo)

Set your key first:
    export ANTHROPIC_API_KEY=sk-ant-...
"""

import argparse
import os
import sys

from src import orchestrator


def main():
    parser = argparse.ArgumentParser(description="Fraud Detection Co-Pilot")
    parser.add_argument("--mock", action="store_true",
                         help="Run with deterministic rule-based agents instead of calling Claude.")
    parser.add_argument("--no-interactive", action="store_true",
                         help="Skip the human-in-the-loop input() prompt; auto-accept agent recommendations.")
    args = parser.parse_args()

    client = None
    if not args.mock:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY is not set. Either:")
            print("  export ANTHROPIC_API_KEY=sk-ant-...")
            print("or run with --mock to try the pipeline without an API key.")
            sys.exit(1)
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

    orchestrator.run_pipeline(client, mock=args.mock, interactive=not args.no_interactive)


if __name__ == "__main__":
    main()
