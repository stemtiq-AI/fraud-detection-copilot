"""
Loads an agent's system prompt directly out of its markdown spec file.

Convention: every agent .md file under agents/ contains a section
wrapped in these exact markers:

    <!-- BEGIN SYSTEM PROMPT -->
    ...the actual prompt text sent to Claude...
    <!-- END SYSTEM PROMPT -->

This is the mechanism that makes "the .py file follows its .md file"
literally true rather than just a documentation convention: the
system prompt is NOT duplicated as a string inside the .py file. The
.md file is parsed and its system-prompt section is what actually
gets sent to the model. Edit the markdown, the agent's behavior
changes - no hunting through code for a prompt string, and no risk of
the doc and the implementation drifting apart.
"""

from pathlib import Path

BEGIN_MARKER = "<!-- BEGIN SYSTEM PROMPT -->"
END_MARKER = "<!-- END SYSTEM PROMPT -->"


def load_system_prompt(md_path) -> str:
    path = Path(md_path)
    text = path.read_text()

    try:
        start = text.index(BEGIN_MARKER) + len(BEGIN_MARKER)
        end = text.index(END_MARKER, start)
    except ValueError:
        raise ValueError(
            f"{path.name} is missing the required "
            f"'{BEGIN_MARKER}' / '{END_MARKER}' markers. "
            "Every agent spec must wrap its system prompt in these markers "
            "so the code can load it."
        )

    prompt = text[start:end].strip()
    if not prompt:
        raise ValueError(f"{path.name} has an empty system prompt section.")
    return prompt
