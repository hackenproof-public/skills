---
name: hackenproof-triage-mistakes
description: Accumulated HackenProof triage mistakes and corrections. Load at the start of every triage session and selectively before evidence evaluation, severity decisions, comment writing, or batch closes. Self-expands per-analyst into ~/.hackenproof/mistakes/. Trigger on "triage", "review report", "before triage", or any HackenProof report decision.
---

# HackenProof Triage Mistakes

Load accumulated triage mistakes before every session to prevent repeating known errors. Self-expands as new mistakes are discovered.

## When to Use

At session start, read the shared base in `references/triage-mistakes.md`.

During a session, when a personal `~/.hackenproof/mistakes/<category>.md` exists, load only the relevant category:

- About to evaluate evidence → `~/.hackenproof/mistakes/evidence.md`
- About to form a severity opinion → `~/.hackenproof/mistakes/decisions.md`
- About to write a comment → `~/.hackenproof/mistakes/comments.md`
- Running a batch close → `~/.hackenproof/mistakes/workflow.md`
- Triaging CORS, SC, or mobile reports → `~/.hackenproof/mistakes/patterns.md`

If a personal category file does not exist, the shared base alone is sufficient — do not block on the missing file.

## File Structure

Mistakes are split across category files to avoid loading everything at once. The shared base lives in `references/`. Personal additions live in `~/.hackenproof/mistakes/`.

```
references/
├── triage-mistakes.md    ← shared base, all categories combined

~/.hackenproof/mistakes/  ← personal, grows from real sessions
├── evidence.md           ← evidence verification mistakes
├── decisions.md          ← severity and decision mistakes
├── comments.md           ← comment writing mistakes
├── workflow.md           ← process and workflow mistakes
└── patterns.md           ← vulnerability-class specific mistakes
```

## How to Use

1. At session start: read `references/triage-mistakes.md` (full shared base)
2. When working a specific task: check `~/.hackenproof/mistakes/[category].md` if it exists
3. Apply rules during analysis

## Self-Expanding

When a new mistake is caught — in real time or at session end — append it to the matching category file in `~/.hackenproof/mistakes/`. If the file or directory does not exist, create it. Use this format:

```
## [Short Title]
[What happened — one paragraph, concrete terms]
**Fix:** [The exact rule for next time, written as a positive instruction]
```

Load only the relevant category file for the task at hand. Never load all category files at once unless starting a fresh session.

Periodically contribute universal patterns back to `references/triage-mistakes.md` via PR.
