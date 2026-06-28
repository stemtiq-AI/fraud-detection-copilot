"""
The core agentic loop: send a message to Claude, and if it asks to
use a tool, run that tool, feed the result back, and repeat until
Claude returns a final text answer (or we hit a turn limit).

This single function is what makes the Investigator agent "agentic"
rather than a single hard-coded prompt: Claude decides *which* tools
to call, *in what order*, and *when it has enough evidence to stop*.
"""

import json

from . import config


def run_agent_loop(client, system_prompt: str, user_message: str,
                    tool_schemas: list, tool_functions: dict,
                    max_turns: int = config.MAX_AGENT_TURNS):
    """
    Returns (final_text, transcript) where transcript is the full
    list of messages exchanged, useful for debugging or for showing
    students exactly how the agent reasoned step by step.
    """
    messages = [{"role": "user", "content": user_message}]

    for turn in range(max_turns):
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=config.MAX_TOKENS,
            system=system_prompt,
            messages=messages,
            tools=tool_schemas,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    func = tool_functions.get(block.name)
                    if func is None:
                        result = {"error": f"Unknown tool: {block.name}"}
                    else:
                        result = func(**block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })
            messages.append({"role": "user", "content": tool_results})
            continue

        # Model is done calling tools and has produced its final answer.
        final_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        return final_text, messages

    return None, messages  # Hit max_turns without a final answer
