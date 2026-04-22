# Completeness Checklist

Run through every item. Mark each as PASS, FAIL, or UNKNOWN.

## Root Cause

- [ ] The fix addresses the root cause, not just a symptom or a specific exploit path
- [ ] If the root cause is a missing check, the check is now present on ALL relevant code paths (not just the one in the report)
- [ ] If the root cause is a logic error, the corrected logic handles all input combinations

## Coverage

- [ ] Search the codebase for the same pattern — are there other instances of the same vulnerability that are NOT fixed?
- [ ] If the vulnerable function is called from multiple places, verify the fix works regardless of the caller
- [ ] If the vulnerability spans multiple functions or contracts, verify all are patched

## Edge Cases

- [ ] Zero/empty/null inputs — does the fix handle them?
- [ ] Maximum values — does the fix handle uint256 max, max array length, etc.?
- [ ] Boundary conditions — off-by-one, exactly-equal-to-threshold cases
- [ ] Ordering — does the fix work regardless of call ordering or transaction sequencing?

## Error Handling

- [ ] If the fix adds a new revert/require, is the error message descriptive?
- [ ] If the fix adds a new revert condition, could it be triggered by legitimate users in normal operation?
- [ ] If the fix modifies error handling, are errors still propagated correctly to callers?
