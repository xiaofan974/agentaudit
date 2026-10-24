
import asyncio
import json
from pathlib import Path

from guardrails import verify_quote
from judge import judge_claim


async def enforce_gate(claims, evidence, judge=judge_claim):
    accepted = []
    rejected = []
    evaluation_errors = []

    for item in claims:
        claim = item.get("claim", "")
        chunk_id = item.get("chunk_id", "")
        quote = item.get("quote", "")

        check = verify_quote(
            claim, chunk_id, quote, evidence
        )

        if not check.valid:
            rejected.append({
                "claim": claim,
                "reason": check.reason,
                "stage": "quote_check",
            })
            continue

        source_text = next(
            match["text"]
            for match in evidence["matches"]
            if match.get("id") == chunk_id
        )
        try:
            judgment = await judge(claim, quote, source_text)
        except Exception as exc:
            judgment = {
                "verdict": "JUDGE_ERROR",
                "reason": f"Judge execution failed: {type(exc).__name__}",
            }

        if judgment.get("verdict") == "SUPPORTED":
            accepted.append({
                "claim": claim,
                "chunk_id": chunk_id,
                "quote": quote,
            })
        elif judgment.get("verdict") in {
            "NOT_SUPPORTED", "CONTRADICTED"
        }:
            rejected.append({
                "claim": claim,
                "reason": judgment.get(
                    "reason", "Judge did not establish support"
                ),
                "stage": "entailment",
                "judge_verdict": judgment.get("verdict"),
            })
        else:
            evaluation_errors.append({
                "claim": claim,
                "reason": judgment.get(
                    "reason", "Judge did not complete"
                ),
                "stage": "entailment",
                "judge_verdict": judgment.get("verdict"),
            })

    if rejected:
        verdict = "FAIL"
    elif evaluation_errors or not accepted:
        verdict = "INSUFFICIENT_EVIDENCE"
    else:
        verdict = "PASS"

    return {
        "verdict": verdict,
        "accepted_claims": accepted,
        "rejected_claims": rejected,
        "evaluation_errors": evaluation_errors,
        "counts": {
            "accepted": len(accepted),
            "rejected": len(rejected),
            "evaluation_errors": len(evaluation_errors),
        },
    }


if __name__ == "__main__":
    print("Final gate module loaded successfully")
