# Regression Checklist

Check each item to verify the fix doesn't break existing functionality.

## Interface Changes

- [ ] No public/external function signatures changed (unless intentional and documented)
- [ ] No event signatures changed (would break indexers/subgraphs)
- [ ] No error/revert message changes that downstream contracts depend on
- [ ] Return values haven't changed type or meaning

## Behavioral Changes

- [ ] Existing valid inputs still produce the same outputs
- [ ] State transitions that worked before still work (no new unexpected reverts)
- [ ] Gas consumption hasn't increased dramatically for normal operations
- [ ] No new blocking conditions that could prevent legitimate operations

## Trust Assumptions

- [ ] No new admin/privileged roles introduced
- [ ] No new external dependencies added (oracles, other contracts)
- [ ] No existing permission checks weakened or removed
- [ ] Timelocks and delays not reduced or bypassed

## Integration Impact

- [ ] Functions called by other contracts in the protocol still behave as expected
- [ ] Functions called by external integrations (DEX routers, aggregators) still work
- [ ] If a modifier was changed, all functions using it are still correct

## Test Integrity

- [ ] If test files were modified, changes update expectations (not weaken assertions)
- [ ] No test deletions without replacement
- [ ] If new revert conditions were added, corresponding tests exist
- [ ] If behavior changed, tests reflect the new expected behavior
