---
name: hackenproof-report-handoff
description: Generate structured report handoff summaries for client teams. Use after triaging a report to produce a standardized handoff with report URL, recommended severity, bounty range, and explanation. Trigger on "handoff", "transfer to client", "prepare handoff", "client summary".
---

# HackenProof Report Handoff

Generate a structured handoff summary after triaging a report. The handoff is what gets communicated to the client team — it must be clear, actionable, and include bounty context.

## When to Use

- After a report has been triaged (state is `Triaged` or any final state)
- When preparing a batch of triaged reports for client review
- When a client team requests a summary of findings

## Workflow

1. Run `get_program_info` to retrieve reward ranges, scopes, and program type.
2. Run `get_report_details` with `full=true` to get the complete report.
3. Extract the reward range for the report's severity from program rewards.
4. Generate the handoff summary using the template from `references/handoff-template.md`.
5. If multiple reports are provided, generate one handoff per report.

## Mandatory Tool Sequence

1. Call `get_program_info` — extract `rewards` object to map severity to bounty range.
2. Call `get_report_details` — extract title, severity, state, vulnerability description, target, and CVSS score.
3. If severity has not been set yet, recommend one using `references/severity-to-bounty.md` and program rewards.
4. Build the report URL from company, program, and report_id.
5. Produce the handoff in the exact format from `references/handoff-template.md`.

## Output Rules

- Always include the full dashboard URL.
- Always include both recommended severity AND bounty range (even if it's "$0" for informational).
- Keep the summary to 2-3 sentences max — focus on what the vulnerability is, what it impacts, and what the client should do.
- If the report is a duplicate, mention the duplication group but do NOT reference the original report ID (reporter cannot see it).
- If bounty range is not available in program info, state "Bounty range not configured for this severity" instead of guessing.

## Batch Mode

When given multiple report IDs:

1. Fetch program info once (shared across all reports).
2. Use `get_reports_details_batch` for efficiency.
3. Output handoffs sorted by severity (Critical first, then High, Medium, Low).
4. Add a summary line at the top: "X reports: Y Critical, Z High, ..."

## Quality Bar

- Every handoff must be grounded in actual report data — never fabricate impact or severity.
- Bounty range must come from `get_program_info` rewards, not from memory or assumptions.
- If the report lacks enough detail for a clear summary, note what's missing.
- Keep tone professional and neutral — this goes to the client.
