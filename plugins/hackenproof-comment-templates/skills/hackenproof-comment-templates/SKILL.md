---
name: hackenproof-comment-templates
description: Standard HackenProof triage closure comment templates for Out of Scope, Informative, Not Applicable, Need More Info, Duplicate, and Dual Defence Informative states. Use whenever writing a closure or decision comment on a HackenProof report. Trigger on "closure comment", "triage comment", "write comment", "close as", or any state transition that requires a comment.
---

# HackenProof Comment Templates

Generate structured, professional triage comments using the standard HackenProof template format.

## When to Use

Use when writing a closure or decision comment on any HackenProof report. Load `references/comment-templates.md` to select the correct template for the state being applied.

## How to Use

1. Identify the state: Out of Scope, Informative, Not Applicable, Need More Info, or Duplicate
2. Load the matching template from `references/comment-templates.md`
3. Fill in all `*PLACEHOLDER*` values and `// EXPLANATION` blocks with specific technical reasoning
4. Post the comment via whichever method your setup supports

## Comment Rules

- Every comment must explain the specific rule violated, what evidence was missing, and what would be needed to resubmit
- Never reference other report IDs in the comment body — reporters cannot see them. Internal labels like `dup-{id}` are fine because they are not part of the comment.
- Never mention the specific severity label in Dual Defence closure comments — reference the threshold only
- Never disclose private information (attack prerequisites, internal severity caps, client-side decisions) in public comments
- Verify every factual claim before writing it
- Comment quality does not drop during batch work

## Reputation Line Rules

Only include the reputation line matching the state:
- **OOS**: "Please note that this closure will not impact your reputation score." ✓
- **Informative**: Do NOT include any reputation line — Informative gives +2 rep
- **N/A**: NEVER include the reputation line — N/A is -5 rep
- **Duplicate**: Do NOT include reputation line
- **NMI**: No reputation mention
