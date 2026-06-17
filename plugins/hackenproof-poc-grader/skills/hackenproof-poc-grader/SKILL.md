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

```
PoC Quality: [Verdict from rubric]
Reason: [One sentence — what evidence is present and why this verdict applies]
Missing (NMI only): [Exactly what would upgrade this to Verified]
```

## Self-Expanding

When a notable PoC pattern is observed, append it to `~/.hackenproof/poc-notes/program-{slug}.md`. Create the file and `~/.hackenproof/poc-notes/` directory if they do not exist.

Format:
```
## [Pattern Name]
[What was observed]
**Grade impact:** [Verdict and why]
```
