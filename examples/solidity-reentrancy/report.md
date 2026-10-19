# Reentrancy in Vault.withdrawAll() lets any depositor drain the vault

**Claimed severity:** Critical

## Target

`Vault.withdrawAll()` in `src/Vault.sol`.

## Description

`withdrawAll()` sends ETH to `msg.sender` with a low-level `call` before it sets
`balances[msg.sender] = 0`. A contract that receives the ETH can call
`withdrawAll()` again from its `receive()` hook. Its balance has not been
cleared yet, so each re-entry pays out the same balance again until the vault
runs out of ETH.

## Steps to reproduce

1. Start from a vault that holds other users' deposits (10 ETH in the PoC).
2. Deploy `SameFunctionAttacker` with 1 ETH. Its `receive()` calls
   `vault.withdrawAll()` again while the vault still holds at least 1 ETH.
3. Call `attacker.attack()`. It deposits 1 ETH, then calls `withdrawAll()`.
4. Run the PoC: `forge test --match-test test_reportPoC_drainsVault -vv`

The full PoC is in `test/Exploit.t.sol` (`SameFunctionAttacker`,
`test_reportPoC_drainsVault`).

## Impact

An attacker who deposits 1 ETH can withdraw the full balance of the contract.
In the PoC, the vault goes from 11 ETH to 0 and the attacker contract ends with
11 ETH. The 10 ETH it gains belonged to other depositors.

```
[PASS] test_reportPoC_drainsVault() (gas: 669474)
```

## Recommendation

Set the balance to zero before the external call
(checks-effects-interactions), and add a reentrancy guard.
