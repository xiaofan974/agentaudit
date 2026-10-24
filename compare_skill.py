
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

MODEL = os.getenv("AGENTAUDIT_EVAL_MODEL", "claude-haiku-4-5")
BUDGET = 0.10

answer = json.loads(
    (PROJECT_DIR / "fixtures/remote_work_subtle_error.json").read_text()
)
evidence = json.loads(
    (PROJECT_DIR / "fixtures/remote_work_evidence.json").read_text()
)


async def evaluate(use_skill):
    label = "WITH SKILL" if use_skill else "WITHOUT SKILL"
    print(f"\n=== {label} ===")

    instructions = (
        "You are evaluating the factual groundedness of a RAG answer. "
        "Compare the answer against the supplied source passages. "
        "Return a verdict (PASS, FAIL, or INSUFFICIENT_EVIDENCE), "
        "supporting reasoning, and any unsupported claims. "
        "Use only ExampleCo evidence, not Northwind evidence. "
        "Do not call external APIs."
    )

    if use_skill:
        instructions += (
            " First invoke the evidence-groundedness skill "
            "using the Skill tool, then apply its rules."
        )

    prompt = (
        f"{instructions}\n\n"
        f"RAG RESPONSE:\n{json.dumps(answer)}\n\n"
        f"SOURCE EVIDENCE:\n{json.dumps(evidence)}"
    )

    options = ClaudeAgentOptions(
        model=MODEL,
        cwd=str(PROJECT_DIR),
        setting_sources=["project"] if use_skill else [],
        allowed_tools=["Skill"] if use_skill else [],
        tools=["Skill"] if use_skill else [],
        max_turns=3 if use_skill else 1,
        max_budget_usd=BUDGET,
    )

    result = None

    
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    print(f"Tool called: {block.name}")
                elif isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            result = message


    if result:
        print(f"\nStatus: {result.subtype}")
        print(f"Cost: ${result.total_cost_usd or 0:.6f}")
    else:
        print("\nNo final result received.")


async def main():
    await evaluate(use_skill=False)
    await evaluate(use_skill=True)


if __name__ == "__main__":
    asyncio.run(main())
