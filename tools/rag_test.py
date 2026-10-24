

import json
import os
import time

import httpx
from claude_agent_sdk import tool


@tool(
    "run_rag_test",
    "Run one question against the configured RAG assistant. "
    "Use this tool to collect the actual answer, citations, "
    "retrieved chunk IDs, latency, token usage, and cost. "
    "This tool only reads results; it does not modify data.",
    {"question": str},
)
async def run_rag_test(args):
    question = args["question"]
    api_url = os.getenv("RAG_API_URL")

    if not api_url:
        return {
            "content": [{
                "type": "text",
                "text": "RAG_API_URL is not configured."
            }],
            "is_error": True,
        }

    start = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                api_url,
                json={"question": question},
            )
            response.raise_for_status()
            payload = response.json()

        answer = payload.get("answer", {})

        result = {
            "question": question,
            "answer": answer.get("answer"),
            "confidence": answer.get("confidence"),
            "sources_needed": answer.get("sources_needed"),
            "citations": answer.get("citations", []),
            "retrieved_chunk_ids": payload.get(
                "retrieved_chunk_ids", []
            ),
            "model": payload.get("model"),
            "tokens_used": payload.get("tokens_used"),
            "api_latency_ms": payload.get("latency_ms"),
            "request_duration_seconds": round(
                time.perf_counter() - start, 3
            ),
            "api_cost_usd": payload.get("cost_usd"),
            "http_status": response.status_code,
            "attempts": payload.get("attempts", []),
        }

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result),
            }]
        }

    except (httpx.HTTPError, ValueError) as exc:
        details = f"{type(exc).__name__}: {exc!s}"

        if isinstance(exc, httpx.TimeoutException):
            details += " (request exceeded the configured timeout)"

        if isinstance(exc, httpx.HTTPStatusError):
            details += (
                f" (HTTP {exc.response.status_code}; "
                f"response: {exc.response.text[:300]})"
            )

        return {
            "content": [{
                "type": "text",
                "text": f"RAG test failed: {details}",
            }],
            "is_error": True,
        }
