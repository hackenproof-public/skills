# Report Markdown Template

Use this template when generating the final report file. Replace all `{placeholders}` with real values.

---

## Cover Page

```markdown
# Summary Report

- **Company:** {Company Display Name}
- **Program:** {Program Display Name}
- **Program Slug:** `{program-slug}`
- **Total Reports:** {count}
- **Generated:** {YYYY-MM-DD} UTC
- **Report Type:** {Full | No Comments | Public}

---

*With love by HackenProof team* ♥

---
```

---

## Table of Contents

```markdown
## Table of Contents

| # | ID | Title | Severity | State | Author | Created on |
|---|----|-------|----------|-------|--------|------------|
| 1 | [{REPORT-ID}](#{anchor}) | {Title} | {Severity} | {State} | {author} | {DD.MM.YYYY} |
| 2 | [{REPORT-ID}](#{anchor}) | {Title} | {Severity} | {State} | {author} | {DD.MM.YYYY} |
...
```

- Sort order: newest report first (by submission date descending). For same-date reports, sort by numeric ID descending.
- `Created on` format: `DD.MM.YYYY` — date only, no time (taken from `created_at` field).
- `Author` format: reporter username from the report.
- Anchor format: lowercase ID with hyphens (e.g. `#prog-123`, `#af6dd940-34`).

---

## Per-Report Section

Repeat this block for every report, in the same order as the Table of Contents (newest to oldest).

```markdown
---

<a name="{report-id}"></a>
## Report Title: {Title}

Report details:
- **Report ID:** {report-id}
- **URL:** https://dashboard.hackenproof.com/manager/companies/{company}/{program}/reports/{id}
- **Severity:** {Critical | High | Medium | Low | None}
- **State:** {New | In review | Need more info | Triaged | Duplicate | Informational | Not applicable | Out of scope | Spam | Resolved | Deleted}
- **Target / Asset:** {target or N/A}
- **CVSS Score:** {score or N/A}
- **Submitted:** {YYYY-MM-DD}
- **Last Updated:** {YYYY-MM-DD}
- **Labels:** {label1, label2 or None}
- **Report Author:** {author/reporter username}

### Description

{description text or N/A}

### Steps to Reproduce

{steps text or N/A}

### Impact

{impact text or N/A}

### Attachments

{list of filenames, one per line, or "None"}

<!-- Include only in mode: full -->
### Comments

#### Comment by {username} ({role}) on {YYYY-MM-DD}

{comment body}

*(hidden from reporter)* ← add this line only if is_hidden: true

---
```

If there are no comments in `mode: full`, write `*No comments.*` under the Comments heading.

---

## Notes on Special Cases

- **XSS/injection payloads in titles or content:** sanitize for safe Markdown display; add a note explaining the sanitization.
- **Demo/test content:** mark as `*[Demo/test report — ...]*`.
- **Truncated API content:** note `*[CONTENT PARTIALLY TRUNCATED — fetch report directly for complete data.]*`.
- **Public mode:** omit the `### Team Info` section and the `- **Report Author:**` field entirely.
