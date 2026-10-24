
import json
import os

import httpx
from claude_agent_sdk import tool


@tool(
    "retrieve_evidence",
    "Retrieve source passages from the configured RAG application. "
    "Use this tool to verify whether a RAG answer's factual claims "
    "are supported by actual source text. "
    "Do not treat similarity scores as proof of factual support.",
    {"question": str},
)
async def retrieve_evidence(args):
    question = args["question"]

    api_url = os.getenv("RAG_API_URL")
    ingest_key = os.getenv("RAG_INGEST_KEY")

    if not api_url or not ingest_key:
        return {
            "content": [{
                "type": "text",
                "text": "RAG_API_URL or RAG_INGEST_KEY is missing.",
            }],
            "is_error": True,
        }

    # Derive the retrieval endpoint from our trusted API URL.
    retrieve_url = api_url.rsplit("/", 1)[0] + "/debug/retrieve"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                retrieve_url,
                params={"q": question},
                headers={"X-Ingest-Key": ingest_key},
            )
            response.raise_for_status()
            payload = response.json()

        matches = [
            {
                "id": match.get("id"),
                "document_id": match.get("document_id"),
                "source": match.get("source"),
                "score": match.get("score"),
                "text": match.get("text"),
            }
            for match in payload.get("matches", [])
        ]

        result = {
            "question": question,
            "match_count": payload.get("match_count"),
            "matches": matches,
        }

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result),
            }]
        }

    except (httpx.HTTPError, ValueError) as exc:
        return {
            "content": [{
                "type": "text",
                "text": f"Evidence retrieval failed: {type(exc).__name__}",
            }],
            "is_error": True,
        }
