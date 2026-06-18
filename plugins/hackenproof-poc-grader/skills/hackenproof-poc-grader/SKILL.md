---
name: hackenproof-poc-grader
description: Grade the evidence quality of a HackenProof bug bounty report before forming a severity opinion. Returns one of five verdicts (Verified, Plausible, Weak, Invalid, Out of Scope Evidence) based on a rubric of evidence tiers and negative signals. Trigger on "grade poc", "evidence quality", "is this poc valid", "check evidence", or before any triage severity decision.
---

# HackenProof PoC Grader

Evaluate the quality of evidence in a HackenProof bug bounty report and return a quality verdict before triage.

## Workflow

### Step 1 — Load the rubric

Read `references/poc-grading-rubric.md` in full. All evidence tiers, verdicts, and red flags are defined there. Do not proceed without reading it.

### Step 2 — Load program-specific notes

Check for `~/.hackenproof/poc-notes/program-{slug}.md` where `{slug}` is the program slug from the report URL. If it exists, read it before grading.

### Step 3 — Collect all evidence

Attempt to fetch all attachments via `get_attachments` + `fetch_attachment`. Read all existing comments and note any transaction hashes or on-chain references in the description.

**If attachments cannot be fetched** (tool unavailable, network error, access denied):
Ask the operator to provide the content directly:
- **File or script**: paste the contents
- **Screenshot or image**: describe what is shown
- **Video**: describe what the video demonstrates step by step

Do not issue a verdict on evidence that could not be read. Wait for the operator's input before proceeding.

### Step 4 — Apply the rubric

Grade all collected evidence against the tiers and signals in `references/poc-grading-rubric.md`.

### Step 5 — Return verdict

Pick exactly one verdict from the rubric:

- **Verified** — Tier 1 evidence, ready for severity analysis
- **Plausible** — Tier 2 evidence, proceed with caution
- **Weak** — Tier 3 or Tier 4 evidence, set Need More Info
- **Invalid** — Negative signal hit, close as Not Applicable
- **Out of Scope Evidence** — Negative signal hit, close as Out of Scope

Output format:

```
PoC Quality: [Verdict]
Reason: [One sentence — what evidence is present and why this verdict applies]
Missing (Weak only): [Exactly what would upgrade this to Verified]
```

## Self-Expanding

When a notable PoC pattern is observed, append it to `~/.hackenproof/poc-notes/program-{slug}.md`. Create the file and `~/.hackenproof/poc-notes/` directory if they do not exist.

Format:
```
## [Pattern Name]
[What was observed]
**Grade impact:** [Verdict and why]
```
