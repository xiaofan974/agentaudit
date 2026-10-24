
import asyncio
import json
from pathlib import Path

from audit_output import (
    parse_audit_output,
    InvalidAuditOutput,
)
from final_gate import enforce_gate


PROJECT_DIR = Path(__file__).resolve().parent
FIXTURES = PROJECT_DIR / "fixtures"


async def run_guarded_audit(proposal_text, evidence):
    try:
        proposal = parse_audit_output(proposal_text)
    except InvalidAuditOutput as exc:
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "reason": str(exc),
            "accepted_claims": [],
            "rejected_claims": [],
        }

    if not isinstance(evidence, dict) or not evidence.get("matches"):
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "reason": "Source evidence is unavailable",
            "accepted_claims": [],
            "rejected_claims": [],
        }

    result = await enforce_gate(
        proposal["claims"],
        evidence,
    )

    return result


async def main():
    evidence = json.loads(
        (FIXTURES / "remote_work_evidence.json").read_text()
    )

    proposal = {
        "claims": [{
            "claim": (
                "Any request to move remote days to another week "
                "must receive written approval from the employee's "
                "line manager."
            ),
            "chunk_id": "exampleco-remote-work:0",
            "quote": (
                "Remote days cannot be moved to another week "
                "without written approval."
            ),
        }],
        "coverage_complete": True,
        "notes": "Day 3 regression case",
    }

    result = await run_guarded_audit(
        json.dumps(proposal),
        evidence,
    )

    print(json.dumps(result, indent=2))

    assert result["verdict"] == "FAIL", result
    assert len(result["rejected_claims"]) == 1, result
    assert result["rejected_claims"][0]["stage"] == "entailment", result
    assert (
        result["rejected_claims"][0]["judge_verdict"]
        == "NOT_SUPPORTED"
    ), result

    print("\nGuarded audit regression: PASS")


if __name__ == "__main__":
    asyncio.run(main())
