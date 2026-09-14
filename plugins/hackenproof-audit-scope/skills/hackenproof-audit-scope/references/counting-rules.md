# Counting Rules

How `scripts/audit_scope.py` decides what a "line of code" is and which files are billable.

## Line classification

Each physical line of a `.rs` or `.sol` file is exactly one of:

| Class | Rule |
|---|---|
| **code** | Contains at least one non-whitespace character that is not inside a comment. A line with code *and* a trailing comment is code. |
| **comment** | Contains only comment text (and whitespace). |
| **blank** | Whitespace only. |

"nSLOC" (normalised source lines of code) in the report = the **code** count.

The tokenizer is comment- and string-aware, so these common traps are handled:

- `//` or `/*` inside a string literal is **not** a comment (`"https://…"` stays code — `cloc` gets this wrong).
- Rust block comments nest: `/* a /* b */ c */` is one comment.
- Rust doc comments (`///`, `//!`, `/** */`) and Solidity NatSpec are comments.
- Rust raw strings `r"…"`, `r#"…"#`, byte strings `b"…"`, C strings `c"…"`; Solidity `hex"…"` and `unicode"…"` literals.
- Rust char literals (`'a'`, `'\n'`, `'\''`, `'\u{1F600}'`) versus lifetimes (`'static`).
- Backslash line continuations inside strings keep their line structure.
- A trailing newline at end of file does not create an extra blank line.

### Rust inline tests

Code inside `#[cfg(test)]` (or `#[cfg(all(test, …))]`) items is counted separately as **inline test code** and removed from the file's code count. In CosmWasm and Anchor repos this is routinely 30–60 % of a source file, so ignoring it would inflate the quote badly. The report shows the removed total in its own row.

## File categories

Every Rust/Solidity file gets one category; only **source** is billable. Precedence when several rules match: client filter → dependency → generated → test → mock → script → example → interface → source.

| Category | Rules (case-insensitive path segments and file names) |
|---|---|
| `client_excluded` | Outside the operator's `--include` list, or matching `--exclude`. Listed with its nSLOC so the client sees what was left out. |
| `dependency` | Git submodule paths from `.gitmodules`; directories `node_modules`, `vendor`, `third_party`, `external`, `deps`, `forge-std`, `ds-test`, `openzeppelin-contracts*`, `solmate`, `solady`, `@openzeppelin`, `@chainlink`, `@uniswap`, `@aave`, `@layerzerolabs`, `prb-math`; `lib/<pkg>/` when `<pkg>` contains its own `foundry.toml`, `package.json`, `Cargo.toml`, `.git`, or hardhat config (Foundry-style vendoring). A top-level `lib/` **without** such markers is counted as source and a warning is raised. |
| `generated` | Directories `generated`, `gen`, `bindings`, `codegen`, `typechain*`, `artifacts`, `protos`, `proto_gen`; files `*.pb.rs`, `*_generated.rs`, `*.generated.sol`, `*.g.rs`. |
| `test` | Directories `test`, `tests`, `testing`, `__tests__`, `spec`, `benches`, `fuzz`, `echidna`, `certora`, `invariant`, `halmos`, `medusa`, `e2e`, `integration*`, `test-utils`, `fixtures`; files `*.t.sol`, `*.test.sol`, `*_test.rs`, `*_tests.rs`, `test_*.rs`, `tests.rs`. |
| `mock` | Directories `mock`, `mocks`, `stubs`, `fakes`, `harness(es)`; files starting with `Mock`, `Fake`, `Stub`, `Dummy`, `Test` followed by an uppercase letter or `_`; `*mock.sol` / `*mock.rs`; Solidity files whose every contract is named `Mock*`/`Fake*`/`Stub*`/`Dummy*`. |
| `script` | Directories `script`, `scripts`, `deploy`, `deployment(s)`, `migrations`, `tasks`, `ops`; files `*.s.sol`. (`cli/`, `bin/`, `tools/` are **not** scripts — Rust binaries there are often real deliverables; check with the client.) |
| `example` | Directories `example(s)`, `demo(s)`, `sample(s)`, `tutorial(s)`. |
| `interface` | Directories `interface(s)`, or Solidity files whose only top-level declarations are `interface`. Interfaces carry no logic and are excluded from billable scope, but listed. |
| `source` | Everything else. |

Skipped entirely (never counted, never scanned for prompt text): `.git`, `node_modules`, `target`, `.cargo` registry caches, `artifacts`, `cache*`, `out`, `dist`, `build`, `coverage`, `typechain*`, `broadcast`, virtualenvs, `.idea`, `.next`, `.turbo`, `.yarn`. Symlinks are never followed. Source files over 2 MB are skipped and listed in warnings.

## Other languages

Files with other source extensions (`.ts`, `.js`, `.py`, `.go`, `.move`, `.vy`, `.cairo`, `.sw`, `.c`, `.circom`, `.nr`, …) in source-like locations are tallied as **non-blank lines only** and reported under "Other source languages present but not counted" so the operator knows the quote does not cover them. This version of the tool prices Rust and Solidity only.

## Verification

Per-file counts were compared with `cloc` 2.06 on public repositories:

| Repository | Files compared | Result |
|---|---|---|
| OpenZeppelin/openzeppelin-contracts | 420 | identical |
| CosmWasm/cw-plus | 87 | identical |
| coral-xyz/anchor | 336 | 5 files differ — all cases where `cloc` truncates a string at `//` inside a URL (`"http://…"`), so `cloc` is the one undercounting code |

To re-verify after changing the tokenizer, run `cloc --by-file --json` on a repo and compare `code` against `code + inline_test_code` per file from the script's JSON.
