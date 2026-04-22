---
name: hackenproof-fix-verifier
description: Verify that a security fix actually addresses the reported vulnerability without introducing new issues. Works with any local codebase — no MCP or bug bounty platform required. Trigger on "verify fix", "check fix", "is this fix correct", "review patch", "did this fix the bug".
---

# Fix Verifier

Verify that a code change actually fixes a reported vulnerability — and doesn't introduce new ones.

## When to Use

- After applying a fix for a security finding
- Before merging a security-related PR
- When reviewing someone else's patch for a vulnerability
- When a researcher reports that a fix is incomplete
- Works on any codebase — no MCP connection or bug bounty platform required

## Inputs

The user provides two things:

1. **The vulnerability** — one of:
   - A pasted vulnerability description or report text
   - A HackenProof report URL or ID (if MCP is connected)
   - A CVE ID or advisory description
   - A plain-English explanation of the bug

2. **The fix** — one of:
   - The current working tree changes (`git diff`)
   - A specific commit or commit range (`git diff <commit1>..<commit2>`)
   - A branch comparison (`git diff main..fix-branch`)
   - A PR number (read diff from local git)
   - If not specified, use unstaged + staged changes in the current repo

## Workflow

### Phase 1: Understand the Vulnerability

1. Parse the vulnerability description to extract:
   - **Root cause** — what is fundamentally wrong (e.g., missing access check, unchecked return value, reentrancy)
   - **Attack vector** — how an attacker exploits it (e.g., call sequence, malicious input, frontrunning)
   - **Affected component** — which contract, function, endpoint, or module
   - **Impact** — what happens if exploited (e.g., fund loss, unauthorized access, DoS)
2. If the vulnerability references specific code (line numbers, function names), locate it in the codebase.
3. If MCP is connected and a report ID is given, fetch the full report with `get_report_details`.

### Phase 2: Analyze the Fix

4. Read the git diff to identify all changed files, functions, and lines.
5. For each change, classify it as:
   - **Direct fix** — directly addresses the root cause
   - **Supporting change** — necessary refactoring or test update to support the fix
   - **Unrelated change** — not connected to the vulnerability (flag for review)
6. Map the changes back to the root cause:
   - Does the fix address the root cause, or just a symptom?
   - Does the fix cover all code paths where the vulnerability exists?
   - Are there other locations with the same pattern that are NOT fixed?

### Phase 3: Check for Completeness

7. Run through the completeness checklist from `references/completeness-checklist.md`:
   - Root cause addressed (not just the specific exploit path)
   - All instances of the pattern fixed (not just the one mentioned in the report)
   - Edge cases covered (boundary values, empty inputs, max values)
   - Error paths handled (what if the fix itself fails or reverts)
8. If the vulnerability is in a smart contract, run the additional checks from `references/smart-contract-fix-checks.md`.

### Phase 4: Check for Regressions

9. Run through the regression checklist from `references/regression-checklist.md`:
   - Does the fix change any public interface or function signature?
   - Does the fix alter state transitions or storage layout?
   - Does the fix break any existing invariants?
   - Does the fix introduce new trust assumptions?
   - Could the fix cause a denial of service (e.g., new revert conditions)?
   - Does the fix introduce a new dependency or external call?
10. Search the codebase for callers of the modified functions — could any be affected?
11. If tests exist, check whether existing tests still pass conceptually (flag if test modifications look like they're weakening assertions rather than updating them).

### Phase 5: Verdict

12. Produce the verification report using the format from `references/verdict-template.md`.

## Output Rules

- Always produce a clear **PASS / FAIL / NEEDS REVIEW** verdict.
- Always explain the reasoning — never just say "looks good".
- If FAIL, explain exactly what's wrong and suggest what to change.
- If NEEDS REVIEW, explain what you're uncertain about and what the developer should manually verify.
- If you find the same vulnerability pattern elsewhere in the codebase, report those locations even if the original fix is correct.
- Keep the output actionable — developers should know exactly what to do next after reading the verdict.

## Quality Bar

- Ground every assessment in the actual diff and codebase — never speculate about code you haven't read.
- If you can't determine whether the fix is complete, say so and explain why, rather than guessing.
- Treat the fix as suspicious by default — the goal is to find problems, not to rubber-stamp.
- Consider both the happy path and adversarial conditions when evaluating the fix.
