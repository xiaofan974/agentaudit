
from dataclasses import dataclass


@dataclass
class QuoteCheck:
    claim: str
    chunk_id: str
    quote: str
    valid: bool
    reason: str


def verify_quote(claim, chunk_id, quote, evidence):
    matches = evidence.get("matches", [])

    source = next(
        (m for m in matches if m.get("id") == chunk_id),
        None,
    )

    if source is None:
        return QuoteCheck(
            claim, chunk_id, quote, False,
            "Referenced source chunk not found",
        )

    # Restrict supporting evidence to ExampleCo documents.
    document_id = source.get("document_id")

    if (
        not isinstance(document_id, str)
        or not document_id.startswith("exampleco-")
    ):
        return QuoteCheck(
            claim, chunk_id, quote, False,
            "Source document is not an ExampleCo document",
        )

    if not isinstance(quote, str) or not quote.strip():
        return QuoteCheck(
            claim, chunk_id, quote, False,
            "Missing supporting quote",
        )

    source_text = source.get("text", "")

    if quote not in source_text:
        return QuoteCheck(
            claim, chunk_id, quote, False,
            "Quote does not appear verbatim in source",
        )

    return QuoteCheck(
        claim, chunk_id, quote, True,
        "Exact quote verified; entailment not yet checked",
    )
