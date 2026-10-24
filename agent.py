
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
)

from tools.rag_test import run_rag_test
from tools.retrieve_evidence import retrieve_evidence
from audit_output import parse_audit_output, InvalidAuditOutput
from final_gate import enforce_gate
from tool_capture import ToolCapture

# Load environment variables FIRST
load_dotenv()

# Configuration
MODEL = os.getenv("AGENTAUDIT_MODEL", "claude-opus-5-5")
MAX_BUDGET_USD = float(
    os.getenv("AGENTAUDIT_MAX_BUDGET_USD", "0.15")
)

if MAX_BUDGET_USD <= 0:
    raise ValueError("AGENTAUDIT_MAX_BUDGET_USD must be positive")

LOG_DIR = Path("logs")

# Register the custom RAG testing tool
rag_server = create_sdk_mcp_server(
    name="rag",
    version="1.0.0",
    tools=[run_rag_test, retrieve_evidence],
)



async def main():
    print("🔍 AgentAudit | Evidence-grounded RAG evaluation\n")

    start = time.perf_counter()
    models = set()
    result = None
    assistant_text = []
    final_assistant_text = None
    capture = ToolCapture()

    try:
        async for message in query(
            prompt=(
                "You are AgentAudit, an AI evaluation agent. "
                "Your task is to evaluate the groundedness of a RAG assistant's answer. "

                "Test question: What is the company's remote work policy? "
                "The company being evaluated is ExampleCo. "

                "Follow this workflow in order: "
                "1. Load the evidence-groundedness skill using the Skill tool. "
                "2. Call run_rag_test exactly once with the test question. "
                "3. Call retrieve_evidence exactly once with the same question. "
                "4. Compare the RAG answer's factual claims against the retrieved "
                "source passages, following the skill's evaluation rules. "
                "5. Return a structured evidence proposal for external verification. "

                "Use only ExampleCo source passages to verify ExampleCo claims. "
                "Do not use Northwind policies as supporting evidence. "

                "Your final response must be a single valid JSON object, "
                "without Markdown code fences, with this structure: "
                '{"claims": [{"claim": "exact factual claim from the RAG answer", '
                '"chunk_id": "source chunk ID", '
                '"quote": "exact verbatim source passage"}], '
                '"coverage_complete": true, '
                '"notes": "brief observations"} '
                "Include every factual claim in the RAG answer, including "
                "claims you suspect are unsupported. "
                "For unsupported claims, use an empty quote and chunk_id "
                "rather than inventing evidence. "
                "Do not combine multiple independent claims into one. "
                "Do not issue a final PASS or FAIL; external checks decide. "

                "Never treat citation IDs, retrieval scores, or self-reported "
                "confidence as proof of groundedness. "
                "If a tool fails or evidence is unavailable, return an "
                "empty quote and chunk_id for affected claims. Never invent support. "
                "Do not call additional tools or repeat tests."
            ),
            
            options=ClaudeAgentOptions(
                model=MODEL,
                cwd=str(Path(__file__).resolve().parent),
                setting_sources=["project"],
                mcp_servers={"rag": rag_server},
                allowed_tools=[
                    "mcp__rag__run_rag_test",
                    "mcp__rag__retrieve_evidence",
                    "Skill",
                ],
                max_turns=6,
                max_budget_usd=MAX_BUDGET_USD,
            ),

        ):
   
            capture.observe(message)
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"\n🔧 Tool called: {block.name}")

                    elif isinstance(block, TextBlock):
                        assistant_text.append(block.text)
                        final_assistant_text = block.text
                        print('[UNVERIFIED AGENT OUTPUT]', block.text)

            elif isinstance(message, ResultMessage):
                result = message

    except Exception as exc:
        print(f"\nAgent execution failed: {exc}")
        raise

    finally:
        elapsed = time.perf_counter() - start

    if result is None:
        print("No final result received.")
        return


    print("\n" + "=" * 42)
    print("AGENTAUDIT — GUARDED VERDICT")
    print("=" * 42)

    guarded_result = {
        "verdict": "INSUFFICIENT_EVIDENCE",
        "reason": "No valid audit proposal",
    }

    if result.is_error:
        guarded_result["reason"] = "Agent execution failed"
    elif not (result.result or final_assistant_text):
        guarded_result["reason"] = "Agent returned no final text"
    else:
        try:
            proposal = parse_audit_output(result.result or final_assistant_text)
            rag_answer, evidence = capture.get_verified_inputs()

            print(
                "Live RAG answer captured:",
                bool(rag_answer["answer"].strip()),
            )
            print(
                "Live evidence passages captured:",
                len(evidence["matches"]),
            )

            guarded_result = await enforce_gate(
                proposal["claims"], evidence
            )

            # Claim extraction coverage has not been
            # independently verified yet.
            if guarded_result["verdict"] == "PASS":
                guarded_result["verdict"] = "INSUFFICIENT_EVIDENCE"
                guarded_result["reason"] = (
                    "Submitted claims passed, but complete "
                    "coverage of the RAG answer has not been "
                    "independently established."
                )

        except (InvalidAuditOutput, OSError, ValueError) as exc:
            guarded_result = {
                "verdict": "INSUFFICIENT_EVIDENCE",
                "reason": str(exc),
            }

    print(json.dumps(guarded_result, indent=2))

    usage = result.usage or {}


    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": result.session_id,
        "status": result.subtype,
        "is_error": result.is_error,
        "models": sorted(models),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_creation_tokens": usage.get(
            "cache_creation_input_tokens", 0
        ),
        "cache_read_tokens": usage.get(
            "cache_read_input_tokens", 0
        ),
        "execution_seconds": round(elapsed, 3),
        "sdk_duration_ms": result.duration_ms,
        "cost_usd": result.total_cost_usd,
        "audit_verdict": guarded_result["verdict"],
        "audit_counts": guarded_result.get("counts"),
        "budget_usd": MAX_BUDGET_USD,
        "budget_utilization_pct": (
            round(result.total_cost_usd / MAX_BUDGET_USD * 100, 1)
            if result.total_cost_usd is not None
            else None
        ),
    }

    # Display budget metrics
    print(f"Budget limit:    ${MAX_BUDGET_USD:.2f}")

    if metrics["budget_utilization_pct"] is not None:
        print(
            f"Budget used:     "
            f"{metrics['budget_utilization_pct']:.1f}%"
        )


    print("\n" + "=" * 42)
    print("📊 AGENTAUDIT — EXECUTION METRICS")
    print("=" * 42)
    print(f"Status:          {metrics['status']}")
    print(f"Model(s):        {', '.join(models) or 'Unknown'}")
    print(f"Input tokens:    {metrics['input_tokens']:,}")
    print(f"Output tokens:   {metrics['output_tokens']:,}")
    print(f"Cache creation:  {metrics['cache_creation_tokens']:,}")
    print(f"Cache read:      {metrics['cache_read_tokens']:,}")
    print(f"Execution time:  {elapsed:.2f}s")

    if result.total_cost_usd is not None:
        print(f"Total cost:      ${result.total_cost_usd:.6f}")
    else:
        print("Total cost:      Not available")

    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / "executions.jsonl"

    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(metrics) + "\n")

    print(f"\nMetrics saved to {log_file}")


if __name__ == "__main__":
    asyncio.run(main())
