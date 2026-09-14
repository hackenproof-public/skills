# Critical Code Heuristics

How the script ranks files in "Most critical files" and what each indicator means for a non-auditor. Indicators are regex counts on **comment- and string-stripped** source code, so words in documentation never influence the ranking.

Each indicator has a weight and a cap; a file's score is `Σ weight × min(count, cap)`. The score orders the review — it is not a vulnerability count and not a quality judgement. Use the "Why" column of the report to explain in plain words what a component does, e.g. "holds user deposits and pays out", "talks to another chain", "can be upgraded by an admin".

## Solidity indicators

| Indicator | Weight | Plain-English meaning |
|---|---|---|
| payable, eth_transfer, token_transfer | 3 / 3 / 2 | Moves money. Highest business impact if wrong. |
| low_level_call, delegatecall, assembly | 3 / 4 / 4 | Bypasses the compiler's safety rails; classic source of critical bugs. |
| selfdestruct | 5 | Can destroy a contract. |
| contract_creation | 2 | Factories / clones — bugs replicate across every deployment. |
| upgradeable, diamond, storage_layout | 3 / 4 / 2 | Admin can change code; storage collisions and initializer bugs live here. |
| access_control | 1 | Privileged functions exist; who can call what must be checked. |
| oracle | 3 | Depends on external prices — manipulation risk. |
| signatures | 3 | Verifies signatures / Merkle proofs — replay and malleability risk. |
| unchecked_math, fixed_point_math | 2 / 2 | Precision and overflow logic — rounding-direction bugs. |
| flash_callbacks, reentrancy_guard, receive_fallback | 3 / 1 / 2 | Re-entrancy surface; external code calls back in. |
| cross_chain | 4 | Bridges / messaging — cross-domain trust assumptions, highest-loss category historically. |
| defi_core | 2 | Lending, AMM, staking, vesting, auction logic — economic attack surface. |
| governance | 2 | Proposals, timelocks, votes — governance takeover risk. |
| randomness_time, tx_origin, hardcoded_address | 1 / 2 / 1 | Weak randomness, phishing-prone auth, hardcoded trust. |
| external_entrypoints | 0.5 | Size of the attack surface (public/external functions). |

## Rust indicators

| Indicator | Weight | Plain-English meaning |
|---|---|---|
| instruction_handlers, pub_fns | 2 / 0.5 | On-chain entrypoints (Anchor `ctx: Context<…>`, CosmWasm `execute/instantiate/query`, Substrate calls, ink!/Soroban/MultiversX messages) and public API size. |
| account_validation | 2 | Checks that the right accounts/signers were passed — the #1 Solana bug class. |
| cpi | 4 | Calls other programs/contracts — trust and reentrancy across programs. |
| value_transfer, token_ops | 3 / 2 | Moves lamports / coins / tokens. |
| unsafe, ffi_memory | 4 / 4 | Manual memory handling — memory-safety bugs possible. |
| numeric_casts, checked_math, panics | 2 / 1 / 1 | Truncation, overflow and panic (denial-of-service) surface. |
| deserialization | 1 | Parses untrusted bytes. |
| crypto | 3 | Custom signature / hash / ZK logic. |
| oracle | 3 | External price dependency. |
| cross_chain | 4 | Wormhole / IBC / bridges / XCM. |
| defi_core | 2 | Economic logic. |
| admin_authority, upgrade_migration | 1 / 2 | Privileged roles; migrations and upgrade authority. |
| consensus_protocol | 2 | Validators, finality, mempool, state roots — protocol-core code. |
| concurrency, network_process_fs | 1 / 2 | Off-chain services: shared state, network and filesystem access. |
| macro_definitions, randomness_time | 2 / 1 | Macro-generated code hides logic; time/randomness dependence. |

## Framework detection (Rust)

Per file, from imports and attributes: Anchor, Solana native / Pinocchio, CosmWasm (incl. Sylvia), Substrate / FRAME, ink!, NEAR, Soroban, Stylus, MultiversX, Casper/Odra → **on-chain**; reth/alloy/revm, libp2p, web frameworks (axum, actix, tonic, jsonrpsee…), storage engines, ZK libraries (arkworks, halo2, plonky, risc0, sp1…) → **off-chain**. A crate is on-chain if any file or its `Cargo.toml` says so; otherwise off-chain. This drives the effort bucket (see `effort-model.md`).

## Using the ranking in the summary

- Report the **top 5–10** files with a one-line plain description each. Group by component when files obviously belong together (e.g. `Vault.sol` + `VaultStrategy.sol`).
- State the **share of scope** they hold (the report prints it). "15 files hold 63 % of the code" tells the client where the review time goes.
- Never present indicator counts as findings. "Uses inline assembly in 11 places" is a scoping fact; "has 11 assembly vulnerabilities" is wrong.
- If the top of the list is dominated by utility libraries (math, strings, arrays) rather than business logic, say so — the audit lead may weigh business-logic files higher when planning.
