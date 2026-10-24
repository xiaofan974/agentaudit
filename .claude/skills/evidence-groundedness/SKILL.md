
---
name: evidence-groundedness
description: >
  Evaluate RAG answers for factual grounding, citation support,
  and appropriate abstention when source passages are available.
  Use when judging answer quality or producing an evidence-based
  evaluation report. Do not use for API connectivity checks,
  latency-only tests, or tasks without source evidence.
---

# Evidence-Groundedness Evaluation

## Rules

1. No evidence, no pass.
   Every factual claim must be supported by retrieved source text.
   Citation IDs alone are not proof.

2. Verify citations individually.
   A cited source must exist and contain evidence supporting the
   associated claim. A relevant document title is not enough.

3. Reward appropriate abstention.
   If the sources do not contain enough information, an honest
   refusal or uncertainty statement is preferable to invention.

4. Make failures actionable.
   Identify the unsupported claim, explain what evidence is missing,
   and recommend a concrete improvement.

5. Separate observations from judgments.
   Latency, cost, and retrieved chunk IDs are observations.
   Groundedness and correctness are evaluation judgments.
   The assistant's self-reported confidence is not proof.

## Required verdicts

- PASS: All material factual claims are supported by source text.
- FAIL: At least one material factual claim contradicts or goes
  beyond the available source evidence.
- INSUFFICIENT_EVIDENCE: The source passages needed to verify
  the answer were not provided or could not be retrieved.

Never assign PASS solely because citations are present.

## Example

Question: Can employees work remotely on Fridays?

Source: "Eligible employees may work remotely on Tuesdays and
Thursdays. Fridays are mandatory office days."

Answer A: "No. Friday is an office day."
Verdict: PASS
Reason: The answer is directly supported by the source.

Answer B: "Yes, with manager approval."
Verdict: FAIL
Reason: The source explicitly identifies Friday as an office day.

Answer C: "Employees may work remotely on Fridays."
Evidence: Only citation IDs were provided, without source text.
Verdict: INSUFFICIENT_EVIDENCE
Reason: Citation IDs alone cannot establish factual support.
