# Effort Model

Heuristic model used by `scripts/audit_scope.py` to turn billable nSLOC into auditor-days. The constants below are the script's defaults (`DEFAULT_RATES`). Override any of them without touching the script by passing `--rates my-rates.json` with the same keys; only the keys present are replaced.

**These are starting values for calibration, not HackenProof's official price list.** After a few real engagements, compare actual auditor-days with the script's output and adjust the rates here and in the script together. Every report carries the line "confirm with the audit lead before quoting" for this reason.

## Review rates (nSLOC per auditor per day)

| Bucket | Low | Medium | High | Typical content |
|---|---|---|---|---|
| `solidity` | 250 | 150 | 90 | Low: tokens, vesting, simple staking, NFT mint. Medium: standard DeFi (vaults, staking with rewards, governance, marketplaces), upgradeable systems. High: AMMs, lending/liquidation, derivatives, bridges, heavy assembly, novel cryptography, diamond proxies. |
| `rust_onchain` | 350 | 220 | 130 | Solana (Anchor/native/Pinocchio), CosmWasm, ink!, NEAR, Soroban, Stylus, MultiversX, Substrate pallets. Rust is more verbose per unit of logic than Solidity (account validation boilerplate), hence the higher rates. |
| `rust_offchain` | 500 | 300 | 180 | Node clients, consensus, p2p, indexers, relayers, wallets, RPC services, ZK provers. Low: CLIs and glue code. High: consensus/networking cores, custom crypto, unsafe-heavy code. |

The bucket for a Rust file is decided per crate: a crate is `rust_onchain` if any of its files import an on-chain framework or its `Cargo.toml` depends on one (`anchor-lang`, `solana-program`, `cosmwasm-std`, `frame-support`, `ink`, `near-sdk`, `soroban-sdk`, `stylus-sdk`, `multiversx-sc`, …) or builds a `cdylib`; otherwise `rust_offchain`.

## Tier selection

The script suggests one tier per language from indicator counts on comment-stripped source (see `critical-code-heuristics.md`):

- **high** — at least one *high trigger* fired (density-normalised so one library file cannot flip a large repo): heavy inline assembly, cross-chain messaging, diamond proxies, flash-loan/hook callbacks, multiple delegatecall sites, precision-math-heavy DeFi, oracle-dependent DeFi, substantial `unsafe`, raw memory/FFI, cryptography-heavy code, consensus core, CPI-heavy value transfers.
- **medium** — no high trigger, but two or more *drivers* (oracles, signatures, upgradeability, governance, DeFi value flows, low-level calls, unchecked math, manual storage; for Rust: CPI, unsafe, token ops, value transfers, custom deserialisation, concurrency, migrations, numeric casts) or a high overall indicator density on a non-trivial code base.
- **low** — otherwise.

`--complexity` overrides the suggestion for all languages. The report always includes a sensitivity table pricing the same scope at all three tiers so the audit lead can pick without re-running.

Calibration on public repositories with the defaults: OpenZeppelin Contracts → high (433 assembly blocks), solmate → high, Uniswap v2-core → high (AMM math), Raydium AMM → high, CosmWasm cw-plus → medium, Anchor framework → medium.

## Adjustments

| Adjustment | Factor | When |
|---|---|---|
| No test suite | ×1.15 | Zero test code for that language (no test dirs, no `*.t.sol`, no `#[cfg(test)]`). Auditors must build their own harness. |
| Sparse documentation | ×1.10 | Comment lines < 5 % of total lines in source files. |

Multipliers stack. They are applied per bucket before summing.

## Phases and floors

| Item | Rule |
|---|---|
| Core review | Sum of bucket days, minimum **3 auditor-days** (minimum engagement). |
| Reporting | 15 % of core review, minimum 1 day, rounded up. |
| Fix verification / retest | 15 % of core review, minimum 1 day, rounded up. |
| Total | Core + reporting + fix verification. |
| Range | ×0.8 to ×1.3 of total. Asymmetric because scope tends to grow, not shrink. |
| Calendar weeks | Range ÷ (team size × 5 working days). Default team size 2 (`--team`). Retest is scheduled after client fixes, so calendar weeks cover core review + reporting only in practice. |

## Overriding via `--rates`

```json
{
  "loc_per_auditor_day": {
    "solidity": {"medium": 170},
    "rust_onchain": {"low": 400, "medium": 250, "high": 150}
  },
  "min_core_review_days": 5,
  "reporting_share": 0.2,
  "range_high_factor": 1.25
}
```

Keys: `loc_per_auditor_day`, `range_low_factor`, `range_high_factor`, `reporting_share`, `fix_verification_share`, `min_reporting_days`, `min_fix_verification_days`, `min_core_review_days`, `no_tests_multiplier`, `low_docs_multiplier`, `low_docs_threshold`, `working_days_per_week`.

When you change defaults for the whole team, update **both** this file and `DEFAULT_RATES` in the script so they do not drift.

## What the model does not capture

- Repeated / templated code (many near-identical contracts review faster than their nSLOC suggests).
- Prior audits and public battle-testing of forked code.
- Formal verification, economic modelling, or fuzzing deliverables — quote separately.
- Client responsiveness during fix verification.
- Coordination overhead for teams larger than 3.

Note these in the summary as reasons the audit lead may move the estimate.
