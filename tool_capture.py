import json

from claude_agent_sdk import (
    AssistantMessage,
    UserMessage,
    ToolUseBlock,
    ToolResultBlock,
)


TOOLS = {
    "mcp__rag__run_rag_test": "rag_answer",
    "mcp__rag__retrieve_evidence": "evidence",
}


class ToolCapture:
    def __init__(self):
        self.pending = {}
        self.results = {}
        self.errors = []

    def observe(self, message):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    if block.name in TOOLS:
                        if block.name in self.pending.values():
                            self.errors.append(
                                f"Duplicate call: {block.name}"
                            )
                        self.pending[block.id] = block.name

        elif isinstance(message, UserMessage):
            for block in message.content:
                if not isinstance(block, ToolResultBlock):
                    continue

                tool_name = self.pending.pop(
                    block.tool_use_id, None
                )

                if tool_name is None:
                    continue

                result_name = TOOLS[tool_name]

                if result_name in self.results:
                    self.errors.append(
                        f"Duplicate result: {tool_name}"
                    )
                    continue

                if block.is_error:
                    self.errors.append(
                        f"Tool returned an error: {tool_name}"
                    )
                    continue

                try:
                    content = block.content

                    if isinstance(content, str):
                        raw = content
                    elif isinstance(content, list):
                        text_blocks = [
                            item["text"]
                            for item in content
                            if isinstance(item, dict)
                            and item.get("type") == "text"
                        ]
                        if len(text_blocks) != 1:
                            raise ValueError(
                                "Expected exactly one text block"
                            )
                        raw = text_blocks[0]
                    else:
                        raise ValueError(
                            "Unsupported tool result format"
                        )

                    payload = json.loads(raw)

                    if not isinstance(payload, dict):
                        raise ValueError(
                            "Tool result must be a JSON object"
                        )

                    self.results[result_name] = payload

                except (ValueError, TypeError, KeyError) as exc:
                    self.errors.append(
                        f"Invalid result from {tool_name}: {exc}"
                    )

    def get_verified_inputs(self):
        if self.errors:
            raise ValueError("; ".join(self.errors))

        if self.pending:
            raise ValueError(
                "Missing tool results: "
                + ", ".join(self.pending.values())
            )

        if set(self.results) != {"rag_answer", "evidence"}:
            raise ValueError(
                "Both RAG answer and evidence are required"
            )

        rag_answer = self.results["rag_answer"]
        evidence = self.results["evidence"]

        if not isinstance(rag_answer.get("answer"), str):
            raise ValueError("Missing RAG answer text")

        if not rag_answer["answer"].strip():
            raise ValueError("Empty RAG answer")

        if not isinstance(evidence.get("matches"), list):
            raise ValueError("Missing evidence matches")

        if not evidence["matches"]:
            raise ValueError("No evidence passages returned")

        return rag_answer, evidence
