# AgentAudit

**An evidence-grounded evaluation agent for RAG-generated answers.**

AgentAudit tests a retrieval-augmented generation (RAG) assistant, captures its answer and retrieved evidence, and checks whether the answer's factual claims are supported by the source documents.

It combines an agentic investigation workflow with deterministic evidence checks and an independent LLM judge. Unsupported claims are flagged rather than silently accepted.

> **Status:** Five-day challenge MVP. Demonstrated on synthetic company-policy data; not production-ready.

## The problem

RAG systems can produce answers that sound credible, cite relevant documents, and still introduce unsupported details.

A citation alone does not establish that a source supports a claim.

AgentAudit explores a more defensible evaluation workflow: verify the evidence itself, assess whether it supports the claim, and explicitly report uncertainty when verification is incomplete.

## How it works

```text
              Test question
                    |
                    v
             Claude Agent SDK
                    |
          Evidence-groundedness
                skill
                    |
          +---------+---------+
          |                   |
          v                   v
      run_rag_test      retrieve_evidence
          |                   |
          v                   v
      RAG answer        Source passages
          |                   |
          +---------+---------+
                    |
                    v
          Structured claim proposal
                    |
                    v
          Independent verification
          +-----------------------+
          | Exact quote check     |
          | ExampleCo boundary    |
          | Haiku entailment judge|
          +-----------------------+
                    |
                    v
             Guarded verdict
          PASS / FAIL /
          INSUFFICIENT_EVIDENCE
```

### Verification layers

1. **Tool-result capture:** Correlates actual MCP tool calls with their responses, rejecting missing, malformed, duplicate, or failed results.
2. **Source validation:** Checks that a referenced chunk exists and belongs to the expected ExampleCo document set.
3. **Exact quotation:** Verifies that supporting quotations occur verbatim in retrieved source text.
4. **Independent entailment judge:** Uses a separate Haiku model to assess whether the claim follows from its quotation and surrounding source passage.
5. **Conservative verdict:** Rejects unsupported claims and withholds a full PASS when independent claim coverage has not been established.

The Claude agent proposes claims and evidence. The external verification gate determines the verdict.

## Example failure caught

A synthetic remote-work policy states:

> Remote days cannot be moved to another week without written approval.

A test answer added that this approval must come from the employee's line manager.

The source establishes that **written approval is required**, but does not identify the approver for this particular action.

AgentAudit's independent judge identified the added attribution as `NOT_SUPPORTED`.

This illustrates the difference between finding a relevant source and establishing that the source entails a specific claim.

## Implementation

- **Language:** Python
- **Agent framework:** Claude Agent SDK
- **Agent model:** Configurable through `AGENTAUDIT_MODEL`
- **Tools:** Local SDK MCP server exposing RAG testing and evidence retrieval
- **Evaluation model:** Configurable through `AGENTAUDIT_EVAL_MODEL` (tested with Claude Haiku)
- **Dependency management:** `uv`
- **Testing:** Python `unittest`

### Key files

| File | Responsibility |
|---|---|
| `agent.py` | Agent orchestration, tool observation, verdict and execution metrics |
| `tools/rag_test.py` | Query the RAG application |
| `tools/retrieve_evidence.py` | Retrieve supporting passages |
| `tool_capture.py` | Validate and correlate live tool responses |
| `guardrails.py` | Exact quotation and document-boundary checks |
| `judge.py` | Independent claim entailment evaluation |
| `final_gate.py` | Combine checks into a guarded verdict |
| `audit_output.py` | Validate the agent's structured proposal |
| `compare_skill.py` | Day 3 controlled skill comparison |
| `run_guarded_audit.py` | Targeted hallucination regression |
| `tests/test_guardrails.py` | Offline deterministic regression suite |
| `.claude/skills/evidence-groundedness/SKILL.md` | Agent evaluation instructions |

## Quick start

### Prerequisites

- Python version specified in `.python-version`
- [`uv`](https://docs.astral.sh/uv/)
- Anthropic API credentials
- Access to a compatible RAG service exposing the required `/ask` and `/debug/retrieve` endpoints

### Install

```bash
git clone https://github.com/xiaofan974/agentaudit.git
cd agentaudit
uv sync
```

Create a local `.env` file:

```dotenv
ANTHROPIC_API_KEY=your_api_key
AGENTAUDIT_MODEL=claude-opus-5-5
AGENTAUDIT_EVAL_MODEL=claude-haiku-4-5
AGENTAUDIT_MAX_BUDGET_USD=0.15
RAG_API_URL=https://your-rag-service.example
RAG_INGEST_KEY=your_retrieval_key
```

The example values above are configuration placeholders, not credentials. The live demonstration requires access to the compatible RAG backend; the repository does not bundle that service.

### Run the agent

```bash
uv run python agent.py
```

The current challenge scenario evaluates the remote-work policy of **ExampleCo**, a fictional company.

The agent calls the RAG tools, proposes evidence-backed claims, and runs the external verification gate.

Execution summaries are saved locally to `logs/executions.jsonl`, which is excluded from Git.

**Note:** The configured agent budget applies to the agent SDK execution. Independent judge calls and any external RAG service costs may be additional.

## Tests and evidence

### Offline regression suite

Run:

```bash
uv run python -m unittest discover -s tests -v
```

The suite checks:

- Valid ExampleCo quotations
- Fabricated quotations
- Cross-tenant Northwind evidence
- Supported and unsupported claim verdicts
- Judge errors
- Invalid quotations that must not reach the judge
- Missing MCP tool responses
- Failed MCP tool responses

**Day 5 result:** 9/9 tests passed in each of three consecutive runs (27/27 test executions).

These tests use controlled judge responses. They validate deterministic code paths and verdict orchestration, **not the statistical accuracy or consistency of a live LLM judge**.

### Additional evaluation findings

During development:

- A subtle invented approval requirement was rejected as `NOT_SUPPORTED`.
- Three targeted context-aware judge calibration cases passed.
- Re-evaluating five previously rejected claims changed three to `SUPPORTED`; two remained `NOT_SUPPORTED`.
- Live MCP capture successfully collected a RAG answer and five retrieved passages.

These are small, targeted evaluations, not a representative benchmark.

### Observed execution cost

One full agent run recorded:

| Metric | Observed value |
|---|---:|
| Agent SDK cost | $0.137681 |
| Execution time | 93.26 seconds |
| Agent budget | $0.15 |
| Budget utilization | 91.8% |
| Captured evidence passages | 5 |

These measurements came from a run before the final context-aware judge and error-handling updates. The complete updated end-to-end flow has not yet been re-benchmarked.

The SDK cost excludes separately incurred evaluation calls and any RAG backend charges.

## What changed during the challenge

**Day 1 — Define the task:** Focus on groundedness evaluation rather than generic answer scoring.

**Day 2 — Connect tools:** Integrate RAG answer generation and source retrieval through MCP.

**Day 3 — Evaluate behavior:** Compare evaluation with and without a dedicated skill. Both configurations detected two of three seeded failures but missed a subtle invented approver.

**Day 4 — Add guardrails:** Introduce exact quote verification, source boundaries, an independent entailment judge, context-aware judging, live tool-result capture, and fail-closed error handling.

**Day 5 — Ship:** Add repeatable regression tests, execution-verdict logging, documentation, and a reproducible demonstration workflow.

## Known limitations

1. **Claim coverage is not independently verified.** The agent reports whether it extracted all factual claims, but the system does not yet establish this independently. Even when submitted claims pass, the top-level verdict is conservatively downgraded to `INSUFFICIENT_EVIDENCE`.
2. **LLM judgments can vary.** The Haiku judge may still be overly strict or miss unsupported implications. The current calibration sample is small.
3. **Company-specific validation.** Source restrictions currently target synthetic ExampleCo documents; this is not a general-purpose multi-tenant authorization system.
4. **Fixed demonstration task.** The main agent currently evaluates a predefined remote-work policy question rather than accepting arbitrary user tasks.
5. **External RAG dependency.** A compatible running RAG service is required for the live demonstration.
6. **Limited observability.** Execution summaries capture timing, cost, and verdict information, but do not yet provide a complete per-step audit trace.
7. **No production validation.** Security, scale, robustness, and real-world evaluation accuracy have not been established.

## Next steps

- Independently verify claim extraction coverage.
- Expand the evaluation dataset using real failure patterns.
- Measure live judge reliability across repeated runs.
- Introduce a richer step-level trace and evidence review interface.
- Generalize tenant boundaries and support additional RAG backends.

## Why this project matters

AgentAudit demonstrates a product principle: **AI-generated answers should be evaluated against what the evidence actually establishes, not merely whether they sound convincing or contain citations.**

The goal is not to make an LLM judge appear infallible. It is to make uncertainty, unsupported claims, and verification failures visible before users rely on an answer.
