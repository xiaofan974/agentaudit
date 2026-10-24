import asyncio
import json
import unittest
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    UserMessage,
    ToolUseBlock,
    ToolResultBlock,
)

from guardrails import verify_quote
from final_gate import enforce_gate
from tool_capture import ToolCapture


ROOT = Path(__file__).resolve().parents[1]

EVIDENCE = json.loads(
    (ROOT / "fixtures" / "remote_work_evidence.json").read_text()
)

QUOTE = (
    "Remote staff must be available on Slack and email "
    "from 10:00 to 16:00 UK time."
)

CLAIM = {
    "claim": QUOTE,
    "chunk_id": "exampleco-remote-work:1",
    "quote": QUOTE,
}


class QuoteTests(unittest.TestCase):
    def test_valid_exampleco_quote(self):
        result = verify_quote(
            CLAIM["claim"],
            CLAIM["chunk_id"],
            CLAIM["quote"],
            EVIDENCE,
        )
        self.assertTrue(result.valid)

    def test_fabricated_quote_rejected(self):
        result = verify_quote(
            "ExampleCo provides a £100 stipend.",
            "exampleco-remote-work:1",
            "ExampleCo provides a £100 stipend.",
            EVIDENCE,
        )
        self.assertFalse(result.valid)

    def test_northwind_source_rejected(self):
        northwind = next(
            m for m in EVIDENCE["matches"]
            if m["id"].startswith("northwind-")
        )
        result = verify_quote(
            "Northwind policy",
            northwind["id"],
            northwind["text"][:40],
            EVIDENCE,
        )
        self.assertFalse(result.valid)
        self.assertIn("not an ExampleCo", result.reason)


class GateTests(unittest.IsolatedAsyncioTestCase):
    async def test_supported_claim(self):
        async def judge(claim, quote, source_text):
            return {"verdict": "SUPPORTED", "reason": "Supported"}

        result = await enforce_gate(
            [CLAIM], EVIDENCE, judge=judge
        )
        self.assertEqual(result["verdict"], "PASS")

    async def test_unsupported_claim(self):
        async def judge(claim, quote, source_text):
            return {
                "verdict": "NOT_SUPPORTED",
                "reason": "Unsupported detail",
            }

        result = await enforce_gate(
            [CLAIM], EVIDENCE, judge=judge
        )
        self.assertEqual(result["verdict"], "FAIL")

    async def test_judge_outage(self):
        async def judge(claim, quote, source_text):
            return {
                "verdict": "JUDGE_ERROR",
                "reason": "Simulated outage",
            }

        result = await enforce_gate(
            [CLAIM], EVIDENCE, judge=judge
        )
        self.assertEqual(
            result["verdict"], "INSUFFICIENT_EVIDENCE"
        )
        self.assertEqual(
            result["counts"]["evaluation_errors"], 1
        )

    async def test_invalid_quote_skips_judge(self):
        async def judge(claim, quote, source_text):
            self.fail("Judge should not run for invalid quotes")

        invalid = dict(CLAIM)
        invalid["quote"] = "This quote is fabricated."

        result = await enforce_gate(
            [invalid], EVIDENCE, judge=judge
        )
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(
            result["rejected_claims"][0]["stage"],
            "quote_check",
        )


class CaptureTests(unittest.TestCase):
    def test_missing_tool_result_rejected(self):
        capture = ToolCapture()
        capture.observe(
            AssistantMessage(
                content=[
                    ToolUseBlock(
                        id="tool-1",
                        name="mcp__rag__retrieve_evidence",
                        input={"question": "Remote work policy?"},
                    )
                ],
                model="test-model",
            )
        )
        with self.assertRaises(ValueError):
            capture.get_verified_inputs()

    def test_failed_tool_result_rejected(self):
        capture = ToolCapture()
        capture.observe(
            AssistantMessage(
                content=[
                    ToolUseBlock(
                        id="tool-1",
                        name="mcp__rag__run_rag_test",
                        input={"question": "Remote work policy?"},
                    )
                ],
                model="test-model",
            )
        )
        capture.observe(
            UserMessage(
                content=[
                    ToolResultBlock(
                        tool_use_id="tool-1",
                        content="RAG request failed",
                        is_error=True,
                    )
                ]
            )
        )
        with self.assertRaisesRegex(ValueError, "Tool returned an error"):
            capture.get_verified_inputs()


if __name__ == "__main__":
    unittest.main()
