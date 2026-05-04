---
name: hackenproof-all-reports-export
description: 'Export ALL reports of a HackenProof program into a structured file. User chooses report detail level (Full, No Comments, or Public) and output format (Markdown, JSON, or CSV). Trigger on "export all reports to markdown", "generate md file for all program reports", "create export of all reports", "give me all reports as a file", "make a full report export", "export program reports", "final report for my program", "provide final report for program", "generate final report for program".'
---

# HackenProof Program Report Generator

Generate a structured summary report for all reports in a HackenProof program. The output is a self-contained file (Markdown, JSON, or CSV) ready to share or archive.

## Prerequisites

This skill makes one API call per report. For programs with many reports, Claude Code will prompt for confirmation on each call unless HackenProof tools are auto-approved.

**To avoid clicking "Allow" dozens of times**, tell the user to add this to `~/.claude/settings.json` once:

```json
{
  "permissions": {
    "allow": [
      "mcp__hackenproof__*"
    ]
  }
}
```

If the user has not done this yet, warn them before starting Step 4:

> "This program has {N} reports — I'll need to make {N} API calls. To avoid confirming each one, add `mcp__hackenproof__*` to your allowed tools in `~/.claude/settings.json`. Want me to proceed anyway?"

Only proceed after the user confirms.

## When to Use

- When a user asks for a summary, final, or export report of a program's reports
- When a user wants to save or share the state of all reports in a program
- When a user triggers with phrases like: "export all reports", "generate md file for all program reports", "final report for my program", "make a full report export", "export program reports"

## Workflow

### Step 1: Resolve Program

If the user provided a program slug or URL — use it directly.

If not:
1. Call `list_companies` to get all companies.
2. For each company, call `list_programs` to enumerate programs.
3. Show the user a numbered list:

```
Available programs:

  1. near-intents  (company: near-protocol)
  2. bluefin-dex   (company: bluefin)
  ...

Which program should I generate the report for?
```

Wait for selection before proceeding.

### Step 2: Ask for Report Type and Format

Present the options to the user:

```
Which report type do you want?

  1. Full — all available data (title, description, severity, state, PoC, attachments, comments, team info)
  2. No Comments — same as Full but without comments thread
  3. Public — no comments and no team/assignee information (safe to share externally)

Type 1, 2, or 3 (default: 1):
```

Then ask for output format:

```
Which output format do you want?

  1. Markdown (.md) — formatted report
  2. JSON (.json) — structured data
  3. CSV (.csv) — spreadsheet-ready

Type 1, 2, or 3 (default: 1):
```

Wait for both selections. Defaults: report type **1 (Full)**, format **1 (Markdown)**.

Map selections:
- Report type: `1` → `mode: full`, `2` → `mode: no-comments`, `3` → `mode: public`
- Format: `1` → `format: md`, `2` → `format: json`, `3` → `format: csv`

### Step 3: Fetch All Reports

1. Call `get_program_info` for the selected program — extract `title` (program display name), `company`, and program slug.
2. Call `list_reports` with `page=1`. If 10 results are returned, fetch subsequent pages until exhausted.
3. Collect the full list of report IDs and basic metadata (id, title, severity, state).

### Step 4: Fetch Report Details

**Always use `get_report_details` with `full=true` for every report individually.**

Do NOT use `get_reports_details_batch` — it returns incomplete `labels` data (known limitation: returns empty array even when labels exist). Only `get_report_details` with `full=true` returns accurate labels and all fields including comments in a single call.

Fetch reports in parallel where possible to reduce total time.

> **CRITICAL — do not return to the user between Step 4 and Step 5.** All fetched data lives only in the active context window and is lost on compaction. Immediately proceed to Step 5 (write the file) in the same response turn, without asking the user anything or waiting for confirmation.

For each report, collect:

**Always fetched (all modes):**
- Report ID and URL (`https://dashboard.hackenproof.com/manager/companies/{company}/{program}/reports/{id}`)
- Title
- Severity
- State
- Target / asset
- CVSS score (if present)
- Labels (accurate only from `get_report_details`)
- Description
- Steps to reproduce
- Attachments list (filenames only, not content)
- Submitted date (`created_at`)
- Published date (`published_at`)
- Last updated date
- SLA status

**Only in `mode: full`:**
- Comments (already included in `get_report_details` with `full=true` — no separate `get_comments` call needed)

> **Known API limitations (as of 2026-05-02):** The following fields are visible in the HackenProof dashboard but not currently returned by the API:
> - **Comment attachments** — each comment has an `attachments` field but it always returns `[]` even when files are attached. In the report, note `*(attachments not available via API)*` if the comment is known to have files.
> - **Assignee** — the user assigned to triage the report is not returned.
> - **Participants / Team members** — managers participating in the report thread are not returned as a separate field.
> - **Bounty / reward per report** — actual payout is not returned (only program-level reward ranges via `get_program_info`).
> - **Program status** — Draft / Published / Private visibility is not returned.

### Step 5: Generate Report

Use the template from `references/report-template.md` for Markdown output.

Build the document in this order:
1. Cover page
2. Table of contents (auto-generated from report IDs and titles) — includes columns: #, ID, Title, Severity, State, Author, Created on (DD.MM.YYYY — date only, no time)
3. One section per report, sorted by report ID from newest to oldest (descending by submission date; for same-date reports, sort by numeric ID descending)

Write the final output to a single file in the current directory (use the Write tool):

**If `format: md`:**
`{program-slug}-report-{YYYY-MM-DD}.md`

**If `format: json`:**
`{program-slug}-report-{YYYY-MM-DD}.json`

Structure:
```json
{
  "program": "{program-slug}",
  "company": "{company}",
  "generated": "{YYYY-MM-DD}",
  "mode": "{full|no-comments|public}",
  "total": N,
  "reports": [
    {
      "id": "...",
      "url": "...",
      "title": "...",
      "severity": "...",
      "state": "...",
      "author": "...",
      "target": "...",
      "cvss": "...",
      "submitted": "YYYY-MM-DD",
      "published": "YYYY-MM-DD",
      "last_updated": "YYYY-MM-DD",
      "sla": "...",
      "labels": [],
      "description": "...",
      "steps_to_reproduce": "...",
      "impact": "...",
      "attachments": [],
      "comments": []
    }
  ]
}
```
- In `mode: public` omit `comments` array and `author` field.
- In `mode: no-comments` omit `comments` array.

**If `format: csv`:**
`{program-slug}-report-{YYYY-MM-DD}.csv`

Columns (header row first):
```
"ID","Title","Severity","State","Author","Target","CVSS","Submitted","Last Updated","Labels","URL"
```
- Wrap all values in double quotes.
- For multi-value fields (labels), join with ` | `.
- Dates in `YYYY-MM-DD` format.
- Null/missing values → `N/A`.

After writing the file, confirm to the user:
```
Report saved to: {filename}
Reports included: {count}
Mode: {Full | No Comments | Public}
Format: {Markdown | JSON | CSV}
```

## Output Rules

- Always include the cover page — never skip it (Markdown only).
- Table of contents must list every report with an anchor link (Markdown only).
- Sort reports by submission date descending (newest first). For reports submitted on the same date, sort by numeric ID descending (e.g. DSC-52 before DSC-50).
- In `mode: public`, strip all fields listed under "Only in full / no-comments" above — no assignee, no triager, no internal labels.
- In `mode: no-comments`, include assignee and labels but omit the comments section entirely.
- Never fabricate data — if a field is empty or not returned by the API, write `N/A`.
- Do not include raw JSON from API responses — format everything as clean Markdown.
- Attachments: list filenames only (not content). Do not call `fetch_attachment`.
- If the program has more than 50 reports, warn the user that generation may take a moment before starting Step 4.

## Error Handling

- If `list_reports` returns 0 results, stop and tell the user: "No reports found for program `{slug}`. Nothing to generate."
- If `get_program_info` fails, still proceed using the program slug as the display name.
- If `get_report_details` fails for a specific report, note the failure in the report section and continue with remaining reports.
