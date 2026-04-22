# Verdict Template

Use this format for every fix verification. Do not skip any section.

```md
# Fix Verification Report

## Verdict: {PASS | FAIL | NEEDS REVIEW}

## Vulnerability

- **Root cause**: {one-line description of what was fundamentally wrong}
- **Attack vector**: {how it could be exploited}
- **Affected component**: {file:function or contract.function}

## Fix Analysis

- **What the fix does**: {one-line description of the change}
- **Root cause addressed**: {Yes/No — explain}
- **All instances covered**: {Yes/No — list any unfixed instances}

## Completeness

| Check | Status | Notes |
|-------|--------|-------|
| Root cause fixed | {PASS/FAIL} | {detail} |
| All code paths covered | {PASS/FAIL} | {detail} |
| Edge cases handled | {PASS/FAIL} | {detail} |
| Error handling correct | {PASS/FAIL} | {detail} |

## Regressions

| Check | Status | Notes |
|-------|--------|-------|
| No interface changes | {PASS/FAIL/N/A} | {detail} |
| No behavioral regressions | {PASS/FAIL/N/A} | {detail} |
| No new trust assumptions | {PASS/FAIL/N/A} | {detail} |
| Integration impact | {PASS/FAIL/N/A} | {detail} |

## Similar Patterns Found

{List any other locations in the codebase with the same vulnerability pattern, even if not in the original report. If none found, write "No additional instances found."}

## Recommendation

{What should the developer do next? Merge as-is, apply additional changes, or investigate further. Be specific.}
```

## Verdict Criteria

- **PASS**: Root cause addressed, all instances covered, no regressions found, no similar patterns elsewhere
- **FAIL**: Root cause not addressed, fix is incomplete, or fix introduces a regression. Always explain what's wrong.
- **NEEDS REVIEW**: Fix looks correct but there are aspects you cannot fully verify (e.g., complex economic logic, external system behavior, production state dependencies). Always explain what needs manual review and why.
