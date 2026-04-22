# Smart Contract Fix Checks

Additional checks for Solidity, Move, Rust (Solana/CosmWasm) and other smart contract fixes.

## Reentrancy

- [ ] If the fix adds a reentrancy guard, verify it covers ALL external calls in the function, not just the one exploited
- [ ] If the fix reorders state changes (checks-effects-interactions), verify the new order is correct for ALL state variables
- [ ] Cross-function reentrancy: are there other functions that read the same state and could be called during reentrancy?
- [ ] Cross-contract reentrancy: does the fix account for callbacks from other contracts in the protocol?

## Access Control

- [ ] If the fix adds an access check, verify it uses the correct role/permission (not a weaker one)
- [ ] Verify the access check cannot be bypassed via delegatecall, proxy, or initializer
- [ ] If the fix restricts a function to a specific caller, verify that caller can't be manipulated

## Arithmetic

- [ ] If the fix addresses an overflow/underflow, verify the fix covers all arithmetic in the function (not just the one line)
- [ ] If using SafeMath or checked arithmetic, verify no unchecked block bypasses it
- [ ] If the fix changes precision or decimal handling, verify rounding direction favors the protocol (not the attacker)

## State and Storage

- [ ] If the fix modifies storage layout, verify it's compatible with existing proxy deployments
- [ ] If the fix changes a mapping or array, verify no stale data can be read
- [ ] If the fix adds a new state variable, verify initialization — especially behind proxies

## External Calls

- [ ] If the fix changes how external calls are made, verify return values are checked
- [ ] If the fix adds a new external call, verify it can't be used to manipulate state
- [ ] If the fix adds a callback guard, verify it doesn't break legitimate integrations

## Token Handling

- [ ] If the fix involves token transfers, verify it handles fee-on-transfer tokens (if applicable)
- [ ] If the fix involves token approvals, verify no approval front-running is introduced
- [ ] If the fix involves ETH transfers, verify it handles contracts that reject ETH (no receive/fallback)

## Upgrade Safety

- [ ] If the contract is upgradeable, verify the fix doesn't break the storage layout
- [ ] If the fix changes an initializer, verify it can't be called again on an existing deployment
- [ ] If the fix changes a function selector, verify proxy routing still works
