# Example: triaging a Solidity reentrancy report

This example takes one vulnerability report through two skills that run
without a HackenProof account:

1. `hackenproof-report-quality-scorer` checks whether the report is complete
   enough to triage.
2. `hackenproof-fix-verifier` checks whether the developer's patch actually
   fixes the bug.

The contracts are intentionally vulnerable and exist only for this example.
Do not deploy them.

## Files

| File | What it is |
|------|------------|
| `src/Vault.sol` | ETH vault with a reentrancy bug in `withdrawAll()` |
| `report.md` | The vulnerability report as a researcher would submit it |
| `src/VaultPatched.sol` | The developer's first fix attempt |
| `fix.diff` | The same fix as a diff against `Vault.sol` |
| `test/Exploit.t.sol` | Foundry tests: the report's PoC, plus a bypass of the patch |

Run the tests with [Foundry](https://getfoundry.sh):

```bash
cd examples/solidity-reentrancy
forge test -vv
```

```
[PASS] test_patch_blocksReportPoC()
[PASS] test_patch_bypassedViaWithdraw()
[PASS] test_reportPoC_drainsVault()
```

## Step 1: score the report

Paste the contents of `report.md` into Claude Code and ask:

> score this report

The skill scores the text against its rubric (`references/scoring-rubric.md`):

```
Report Quality Score: 7/8 — Actionable

Target:            1/2 — contract and function named, but no deployed address or network
Reproduction:      2/2 — numbered steps from a stated starting state, with a runnable Foundry PoC
Impact & Evidence: 2/2 — attacker gains 10 ETH of other users' deposits; test output shows the balances
Severity Claim:    2/2 — claimed Critical; draining all deposits reads Critical

Missing:
- Deployed contract address and network (mainnet, L2, or testnet), or confirmation that the contract is not deployed yet
- The repository commit the report was tested against, to confirm it is in scope

Suggested next step: triage as-is, and ask for the deployment address in the first comment
```

The report can be triaged, but the triager still needs a deployment
address and commit to check scope.

## Step 2: verify the fix

The developer's patch (`fix.diff`) adds a `nonReentrant` guard to
`withdrawAll()`. Ask Claude Code:

> verify fix — vulnerability is report.md, fix is fix.diff

The skill reads the diff and the codebase, then works through its completeness,
regression and smart-contract checklists:

```md
# Fix Verification Report

## Verdict: FAIL

## Vulnerability

- **Root cause**: ETH is sent to `msg.sender` before the sender's balance is updated
- **Attack vector**: a contract re-enters the vault from its `receive()` hook while its balance is still unchanged
- **Affected component**: Vault.withdrawAll (the same pattern exists in Vault.withdraw)

## Fix Analysis

- **What the fix does**: adds a `nonReentrant` modifier to `withdrawAll()` only
- **Root cause addressed**: No. The external call still happens before the state update, and the guard covers one function.
- **All instances covered**: No. `withdraw()` has no guard and also sends ETH before updating the balance.

## Completeness

| Check | Status | Notes |
|-------|--------|-------|
| Root cause fixed | FAIL | Checks-effects-interactions is still violated in both functions |
| All code paths covered | FAIL | During the `withdrawAll()` callback, the attacker calls the unguarded `withdraw()`. Its balance is still nonzero, so the vault pays it twice. |
| Edge cases handled | PASS | Zero-balance withdrawals behave as before |
| Error handling correct | PASS | Failed transfers still revert |

## Regressions

| Check | Status | Notes |
|-------|--------|-------|
| No interface changes | PASS | External signatures are unchanged |
| No behavioral regressions | PASS | Honest withdrawals behave as before |
| No new trust assumptions | PASS | None |
| Integration impact | PASS | Contracts that call `withdrawAll()` from a callback now revert, which is intended |

## Similar Patterns Found

- `Vault.withdraw` (src/Vault.sol): it sends ETH before `balances[msg.sender] -= amount`. The checked
  subtraction blocks re-entry into `withdraw()` itself, but not cross-function re-entry from `withdrawAll()`.

## Recommendation

Do not merge. In both `withdraw()` and `withdrawAll()`, update `balances[msg.sender]` before the
external call, and put `nonReentrant` on both functions. Add the cross-function case
(`test_patch_bypassedViaWithdraw`) to the test suite as a regression test.
```

`test_patch_bypassedViaWithdraw` confirms the bypass: against
`VaultPatched`, the attacker deposits 1 ETH and withdraws 2 ETH.

The outputs above show what the skills produce for these files. Wording will
differ from run to run, but the scores and the verdict should match.
