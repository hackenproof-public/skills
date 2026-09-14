#!/usr/bin/env python3
"""
audit_scope.py — HackenProof audit scope calculator (Rust + Solidity).

READ-ONLY by design. This script never builds, compiles, tests, installs, or
executes anything from the target repository. It only reads files, counts
lines, classifies them, ranks files by security-critical indicators, estimates
audit effort, and screens the repository for prompt-injection text and
code-execution hazards (build scripts, tool configs, agent-instruction files).

Standard library only. Python 3.8+.

Usage:
    python3 audit_scope.py <repo-path-or-git-url> [options]

    --ref REF            branch, tag, or full commit SHA to clone (URL input only)
    --include GLOB       only count files matching GLOB (repeatable; repo-relative)
    --exclude GLOB       additionally exclude files matching GLOB (repeatable)
    --complexity TIER    override auto tier: low | medium | high (applies to all languages)
    --team N             auditors working in parallel for the calendar estimate (default 2)
    --rates FILE.json    override effort-model constants (see references/effort-model.md)
    --json PATH          write full machine-readable results to PATH
    --md PATH            write the Markdown scope report to PATH
    --top N              number of critical files to list (default 15)
    --keep               keep the temporary clone (URL input only)
    --quiet              do not print the Markdown report to stdout
"""

import argparse
import datetime as _dt
import fnmatch
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from collections import defaultdict

VERSION = "0.1.0"
TOOL = "hackenproof-audit-scope"

# --------------------------------------------------------------------------- #
# Effort model defaults — mirror references/effort-model.md. Override via --rates.
# Values are non-comment, non-blank source lines reviewed per auditor per day.
# --------------------------------------------------------------------------- #
DEFAULT_RATES = {
    "loc_per_auditor_day": {
        "solidity": {"low": 250, "medium": 150, "high": 90},
        "rust_onchain": {"low": 350, "medium": 220, "high": 130},
        "rust_offchain": {"low": 500, "medium": 300, "high": 180},
    },
    "range_low_factor": 0.8,
    "range_high_factor": 1.3,
    "reporting_share": 0.15,          # report writing, as share of core review days
    "fix_verification_share": 0.15,   # retest of fixes, as share of core review days
    "min_reporting_days": 1,
    "min_fix_verification_days": 1,
    "min_core_review_days": 3,
    "no_tests_multiplier": 1.15,      # no test suite for that language
    "low_docs_multiplier": 1.10,      # comment ratio below low_docs_threshold
    "low_docs_threshold": 0.05,
    "working_days_per_week": 5,
}

# --------------------------------------------------------------------------- #
# Path classification
# --------------------------------------------------------------------------- #
LANG_BY_EXT = {".sol": "solidity", ".rs": "rust"}

# Other source-like extensions, reported as "unsupported" so managers know they exist.
UNSUPPORTED_CODE_EXT = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".go", ".move", ".vy", ".cairo",
    ".fe", ".yul", ".huff", ".sw", ".c", ".cpp", ".h", ".hpp", ".java", ".kt", ".swift",
    ".rb", ".php", ".cs", ".scala", ".ml", ".hs", ".ex", ".exs", ".dart", ".zig", ".wat",
    ".circom", ".nr", ".lean", ".tact", ".fc", ".func", ".tolk",
}

# Directories that are never counted and (mostly) not scanned.
ALWAYS_SKIP_DIRS = {".git", "node_modules", "target", ".cargo", "artifacts", "cache", "cache_forge",
                    "cache_hardhat", "out", "dist", "build", "coverage", "typechain", "typechain-types",
                    "broadcast", ".venv", "venv", "__pycache__", ".idea", ".next", ".turbo", ".yarn"}

DEPENDENCY_DIR_NAMES = {"node_modules", "vendor", "vendors", "third_party", "third-party", "thirdparty",
                        "external", "externals", "deps", "dependencies", "forge-std", "ds-test",
                        "openzeppelin-contracts", "openzeppelin-contracts-upgradeable", "solmate",
                        "solady", "@openzeppelin", "@chainlink", "@uniswap", "@aave", "@layerzerolabs",
                        "prb-math", "@prb"}
GENERATED_DIR_NAMES = {"generated", "gen", "bindings", "codegen", "typechain", "typechain-types", "artifacts", "protos", "proto_gen"}
TEST_DIR_NAMES = {"test", "tests", "testing", "__tests__", "spec", "specs", "benches", "bench",
                  "fuzz", "fuzzing", "echidna", "certora", "invariant", "invariants", "halmos",
                  "medusa", "e2e", "integration", "integration-tests", "integration_tests",
                  "test-utils", "test_utils", "testutils", "fixtures"}
SCRIPT_DIR_NAMES = {"script", "scripts", "deploy", "deployment", "deployments", "migrations", "tasks", "ops"}
MOCK_DIR_NAMES = {"mock", "mocks", "stubs", "fakes", "harness", "harnesses"}
EXAMPLE_DIR_NAMES = {"example", "examples", "demo", "demos", "samples", "sample", "tutorial", "tutorials"}
INTERFACE_DIR_NAMES = {"interface", "interfaces"}

CATEGORY_ORDER = ["source", "interface", "test", "mock", "script", "example", "generated",
                  "dependency", "client_excluded"]

# --------------------------------------------------------------------------- #
# Security-critical indicators (regexes applied to comment/string-stripped code)
# name: (regex, weight, cap, description)
# --------------------------------------------------------------------------- #
SOL_INDICATORS = {
    "external_entrypoints": (r"\bfunction\s+\w+\s*\([^)]*\)[^{;]*\b(external|public)\b", 0.5, 30, "external/public functions"),
    "payable": (r"\bpayable\b", 3, 5, "payable functions / addresses"),
    "eth_transfer": (r"\.call\s*\{\s*value|\.transfer\s*\(|\.send\s*\(|\bsendValue\s*\(", 3, 5, "native value transfers"),
    "token_transfer": (r"\bsafeTransfer(From)?\s*\(|\btransferFrom\s*\(|\b_?mint\s*\(|\b_?burn\s*\(|\bsafeMint\s*\(", 2, 5, "token mint/burn/transfer"),
    "low_level_call": (r"\.call\s*\(|\.staticcall\s*\(", 3, 5, "low-level calls"),
    "delegatecall": (r"\bdelegatecall\b", 4, 5, "delegatecall"),
    "assembly": (r"\bassembly\b", 4, 5, "inline assembly"),
    "selfdestruct": (r"\bselfdestruct\b|\bsuicide\b", 5, 3, "selfdestruct"),
    "contract_creation": (r"\bcreate2\s*\(|\bnew\s+[A-Z]\w*\s*[({]|\bClones\.|\bCREATE3\b|\bcreate\s*\(", 2, 5, "contract creation / factories"),
    "upgradeable": (r"\bInitializable\b|\binitializer\b|\breinitializer\b|\bUUPSUpgradeable\b|\b_authorizeUpgrade\b|\bupgradeTo(AndCall)?\b|\bERC1967\b|\bTransparentUpgradeableProxy\b|\bBeaconProxy\b", 3, 5, "upgradeability"),
    "diamond": (r"\bIDiamondCut\b|\bLibDiamond\b|\bfacet\b|\bdiamondCut\b", 4, 5, "diamond / facets"),
    "access_control": (r"\bonlyOwner\b|\bonlyRole\b|\bAccessControl\b|\bOwnable\b|\brequire\s*\(\s*msg\.sender|\bmsg\.sender\s*==|\bonly\w+\b", 1, 10, "privileged roles"),
    "oracle": (r"\blatestRoundData\b|\bAggregatorV3Interface\b|\bIPyth\b|\bgetPriceUnsafe\b|\boracle\b|\bpriceFeed\b|\bTWAP\b|\bobserve\s*\(|\bgetPrice\w*\s*\(|\bIPriceOracle\b", 3, 5, "price oracles"),
    "signatures": (r"\becrecover\b|\bECDSA\b|\bSignatureChecker\b|\bEIP712\b|\bpermit\s*\(|\bisValidSignature\b|\bMerkleProof\b", 3, 5, "signature / proof verification"),
    "unchecked_math": (r"\bunchecked\s*\{", 2, 5, "unchecked blocks"),
    "fixed_point_math": (r"\bmulDiv\w*\s*\(|\bFixedPoint\w*\b|\bWadRay\w*\b|\bPRBMath\w*\b|\bUD60x18\b|\bSD59x18\b|\bsqrt\s*\(|\b1e18\b|\b1e27\b|\b10\s*\*\*\s*18\b|\bSafeCast\b|\bfullMulDiv\b", 2, 8, "fixed-point / precision math"),
    "flash_callbacks": (r"\bflashLoan\b|\bonFlashLoan\b|\breceiveFlashLoan\b|\buniswapV3\w*Callback\b|\bpancakeV3\w*Callback\b|\bonERC721Received\b|\bonERC1155Received\b|\bonERC1155BatchReceived\b|\btokensReceived\b|\bexecuteOperation\b", 3, 5, "flash-loan / hook callbacks"),
    "reentrancy_guard": (r"\bnonReentrant\b|\bReentrancyGuard\w*\b", 1, 5, "reentrancy guards (external interaction present)"),
    "receive_fallback": (r"\breceive\s*\(\s*\)\s*external|\bfallback\s*\(", 2, 3, "receive / fallback"),
    "cross_chain": (r"\bLayerZero\b|\blzReceive\b|\b_lzReceive\b|\b_nonblockingLzReceive\b|\bOApp\w*\b|\bCCIP\w*\b|\bccipReceive\b|\bWormhole\b|\bIWormhole\b|\baxelar\w*\b|\bIAxelar\w*\b|\bbridge\w*\b|\bIBridge\w*\b|\brelayer\b|\bcrossChain\w*\b|\bxReceive\b|\bIMailbox\b|\bhandle\s*\(\s*uint32\s+\w*origin", 4, 5, "cross-chain messaging / bridges"),
    "defi_core": (r"\bliquidat\w*\b|\bcollateral\w*\b|\bborrow\w*\b|\brepay\w*\b|\bhealthFactor\b|\bLTV\b|\bltv\b|\bswap\w*\s*\(|\baddLiquidity\w*\b|\bremoveLiquidity\w*\b|\bgetAmount(s)?(Out|In)\b|\bsqrtPrice\w*\b|\btick\w*\b|\bgetReserves\b|\bexchangeRate\w*\b|\bpricePerShare\b|\bconvertTo(Shares|Assets)\b|\btotalAssets\b|\bpreview(Deposit|Mint|Withdraw|Redeem)\b|\bstake\w*\s*\(|\bunstake\w*\s*\(|\bharvest\w*\b|\brebalance\w*\b|\bauction\w*\b|\bsettle\w*\b|\bmargin\w*\b|\bfunding\w*\b|\bperp\w*\b|\boption\w*\b|\bvesting\w*\b", 2, 15, "DeFi value-flow logic"),
    "governance": (r"\bpropose\s*\(|\bcastVote\w*\b|\bGovernor\w*\b|\bTimelock\w*\b|\bqueue\s*\(|\bexecute\s*\(|\bveto\w*\b|\bquorum\w*\b", 2, 5, "governance / timelock"),
    "randomness_time": (r"\bblock\.timestamp\b|\bblockhash\s*\(|\bblock\.prevrandao\b|\bblock\.difficulty\b|\bVRF\w*\b|\brandom\w*\b", 1, 5, "time / randomness dependence"),
    "tx_origin": (r"\btx\.origin\b", 2, 3, "tx.origin usage"),
    "hardcoded_address": (r"\b0x[0-9a-fA-F]{40}\b", 1, 5, "hardcoded addresses"),
    "storage_layout": (r"\bsstore\s*\(|\bsload\s*\(|\bStorageSlot\b|\b\.slot\b|\bkeccak256\s*\(\s*\"[\w.]+\.storage\b|\bstruct\s+\w*Storage\b", 2, 5, "manual storage slots"),
}

RUST_INDICATORS = {
    "pub_fns": (r"\bpub(\s*\([^)]*\))?\s+(async\s+)?(unsafe\s+)?fn\s+\w+", 0.5, 40, "public functions"),
    "instruction_handlers": (r"\bpub\s+fn\s+\w+\s*(<[^>]*>)?\s*\(\s*(mut\s+)?ctx\s*:\s*Context\s*<|\bpub\s+fn\s+(execute|instantiate|query|migrate|sudo|reply|ibc_\w+)\s*\(|#\[pallet::call_index|#\[pallet::weight|#\[ink\(message\)\]|#\[contractimpl\]|#\[endpoint\b|#\[payable\b|\bpub\s+fn\s+process_instruction\b", 2, 20, "on-chain entrypoints / instruction handlers"),
    "account_validation": (r"#\[account\s*\(|\bAccountInfo\b|\bUncheckedAccount\b|\bAccountLoader\b|\bis_signer\b|\bhas_one\s*=|\bconstraint\s*=|\bseeds\s*=|\bowner\s*==|\.key\(\)\s*==|\bassert_owned_by\b|\bassert_signer\b|\bsigner\b\s*,|\bSigner\s*<", 2, 10, "account / signer validation"),
    "cpi": (r"\binvoke_signed\s*\(|\binvoke\s*\(|\bCpiContext\b|\bprogram::invoke\b|\bWasmMsg::Execute\b|\bSubMsg::\w+|\bcross_contract\b|\bPromise::new\b|\bbuild_call\b|\bcall_builder\b|\bCallBuilder\b|\bself\.env\(\)\.invoke_contract\b", 4, 8, "cross-program / cross-contract calls"),
    "value_transfer": (r"\blamports\b|\bsystem_instruction::transfer\b|\bBankMsg::Send\b|\bBankMsg::Burn\b|\bCoin\s*\{|\bcoins\s*\(|\btransfer_lamports\b|\bPromise::new\(.*\)\.transfer\b|\benv::attached_deposit\b|\btransferred_value\b|\bT::Currency::transfer\b|\bBalances::transfer\b|\bsend_tokens\b|\bnative_token\b", 3, 8, "native value transfers"),
    "token_ops": (r"\bspl_token\b|\btoken::transfer\b|\btoken::mint_to\b|\btoken::burn\b|\banchor_spl\b|\bTransferChecked\b|\bcw20\b|\bCw20\w*\b|\bmint_to\b|\bburn_from\b|\bExecuteMsg::Transfer\b|\bft_transfer\w*\b|\bnft_transfer\w*\b|\bPSP22\b|\bPSP34\b|\bEsdtTokenPayment\b", 2, 8, "token operations"),
    "unsafe": (r"\bunsafe\b", 4, 8, "unsafe blocks"),
    "ffi_memory": (r"\btransmute\b|\bfrom_raw_parts(_mut)?\b|\bextern\s+\"C\"|#\[link\b|\basm!\s*\(|\bptr::\w+|\bmem::forget\b|\bManuallyDrop\b|\bMaybeUninit\b|\bset_len\b|\bget_unchecked\b", 4, 8, "raw memory / FFI"),
    "numeric_casts": (r"\bas\s+(u8|u16|u32|u64|u128|usize|i8|i16|i32|i64|i128|isize)\b", 2, 20, "numeric casts (truncation risk)"),
    "checked_math": (r"\bchecked_(add|sub|mul|div|pow|rem|shl|shr)\b|\bsaturating_\w+\b|\bwrapping_\w+\b|\boverflowing_\w+\b|\bmul_div\w*\b|\bPreciseNumber\b|\bDecimal::(from_ratio|percent|permille|bps|checked_\w+)|\bU256::from\b|\bmul_floor\b|\bmul_ceil\b|\bdiv_floor\b|\bdiv_ceil\b|\bisqrt\b|\bpow\s*\(", 1, 20, "explicit arithmetic handling (math-heavy)"),
    "panics": (r"\.unwrap\(\)|\.expect\s*\(|\bpanic!\s*\(|\bunreachable!\s*\(|\bassert!\s*\(|\bassert_eq!\s*\(", 1, 20, "panic paths (DoS surface)"),
    "deserialization": (r"\bborsh\b|\bBorsh\w+\b|\btry_from_slice\b|\bunpack\w*\s*\(|\bfrom_slice\b|\bdeserialize\w*\s*\(|\bfrom_json\b|\bfrom_binary\b|\bDecode\b|\bdecode\s*\(|\bSCALE\b|\bcodec::", 1, 10, "deserialisation of untrusted input"),
    "crypto": (r"\bed25519\w*\b|\bsecp256k1\w*\b|\bkeccak\w*\b|\bsha2\b|\bsha256\w*\b|\bsha3\b|\bblake2\w*\b|\bblake3\b|\bverify_signature\w*\b|\becrecover\w*\b|\bmerkle\w*\b|\bbls12\w*\b|\bgroth16\b|\bplonk\b|\bposeidon\w*\b|\bpairing\b|\bcurve25519\b|\bk256\b|\bp256\b|\bhmac\b|\bzeroize\b", 3, 8, "cryptography"),
    "oracle": (r"\bpyth\w*\b|\bPyth\w*\b|\bswitchboard\w*\b|\bSwitchboard\w*\b|\boracle\w*\b|\bOracle\w*\b|\bprice_feed\w*\b|\bPriceFeed\w*\b|\bchainlink\w*\b|\bget_price\w*\b|\btwap\b", 3, 8, "price oracles"),
    "cross_chain": (r"\bwormhole\w*\b|\bWormhole\w*\b|\bbridge\w*\b|\bBridge\w*\b|\bIbcMsg\b|\bIbcPacket\b|\bIbcChannel\w*\b|\bibc_\w+\b|\brelayer\w*\b|\bvaa\b|\bVAA\b|\bxcm\b|\bXcm\w*\b|\blayerzero\w*\b|\bhyperlane\w*\b|\bmailbox\b", 4, 8, "cross-chain / IBC / bridges"),
    "defi_core": (r"\bliquidat\w*\b|\bcollateral\w*\b|\bborrow\w*\b|\brepay\w*\b|\bhealth_factor\b|\bltv\b|\bswap\w*\b|\badd_liquidity\w*\b|\bremove_liquidity\w*\b|\bamount_out\b|\bamount_in\b|\bsqrt_price\w*\b|\btick\w*\b|\breserve\w*\b|\bexchange_rate\w*\b|\bstake\w*\b|\bunstake\w*\b|\bunbond\w*\b|\breward\w*\b|\bharvest\w*\b|\bvesting\w*\b|\bauction\w*\b|\bsettle\w*\b|\bmargin\w*\b|\bfunding\w*\b|\bperp\w*\b|\bfee_rate\b|\bslippage\b", 2, 15, "DeFi value-flow logic"),
    "admin_authority": (r"\badmin\w*\b|\bauthority\b|\bowner\b|\bgovernance\b|\bonly_admin\b|\bassert_admin\b|\bensure_root\b|\bensure_signed\b|\bassert_owner\b|\bcheck_owner\b|\bOwnership\b|\bsudo\b|\bset_authority\b|\bupgrade_authority\b", 1, 10, "privileged authority"),
    "upgrade_migration": (r"\bmigrate\w*\b|\bMigrate\w*\b|\bset_upgrade_authority\b|\bupgrade\w*\b|\bset_code_hash\b|\bstorage_version\b|\bon_runtime_upgrade\b|\bStorageVersion\b", 2, 5, "upgrade / migration paths"),
    "consensus_protocol": (r"\bconsensus\w*\b|\bfinali[sz]\w*\b|\bvalidator\w*\b|\bslash\w*\b|\bepoch\w*\b|\bfork_choice\b|\bmempool\b|\bgossip\w*\b|\bpeer\w*\b|\bblock_import\b|\bstate_root\b|\btrie\b|\bsequencer\w*\b|\bprover\w*\b|\bverifier\w*\b|\bcheckpoint\w*\b|\bchain_spec\b|\bruntime_upgrade\b", 2, 10, "consensus / protocol logic"),
    "concurrency": (r"\bMutex\s*<|\bRwLock\s*<|\bArc\s*<|\btokio::spawn\b|\bthread::spawn\b|\bmpsc::\w+|\batomic::\w+|\bAtomic\w+\b|\bSemaphore\b|\bDashMap\b|\bselect!\s*\{", 1, 10, "concurrency / shared state"),
    "network_process_fs": (r"\bstd::net\b|\bTcpStream\b|\bTcpListener\b|\bUdpSocket\b|\breqwest\b|\bhyper\b|\bureq\b|\bstd::process\b|\bCommand::new\b|\bstd::fs\b|\bfs::(read|write|remove|create|copy|rename)\w*\b|\bOpenOptions\b|\bstd::env::var\w*\b", 2, 10, "network / process / filesystem access"),
    "macro_definitions": (r"\bmacro_rules!\s*\w+|\bproc_macro\w*\b|#\[proc_macro\w*\]", 2, 5, "macro definitions"),
    "randomness_time": (r"\brand::\w+|\bthread_rng\b|\bOsRng\b|\bClock::get\b|\bunix_timestamp\b|\benv\.block\.time\b|\benv\.block\.height\b|\bblock_timestamp\b|\bSystemTime::now\b|\bInstant::now\b", 1, 5, "time / randomness dependence"),
}

# Rust framework detection (per file). Order matters only for display.
RUST_FRAMEWORKS = [
    ("anchor", r"\banchor_lang\b|#\[program\]|#\[derive\(Accounts\)\]|\banchor_spl\b", "onchain"),
    ("solana-native", r"\bsolana_program\b|\bentrypoint!\s*\(|\bprocess_instruction\b|\bsolana_sdk\b|\bpinocchio\b", "onchain"),
    ("cosmwasm", r"\bcosmwasm_std\b|#\[entry_point\]|\bcosmwasm_schema\b|\bcw_storage_plus\b|\bsylvia\b", "onchain"),
    ("substrate", r"\bframe_support\b|\bframe_system\b|#\[pallet|#\[frame_support::pallet\]|\bsp_runtime\b|\bsp_core\b|\bpolkadot_sdk\b", "onchain"),
    ("ink", r"#\[ink::contract\]|#\[ink\(|\bink_lang\b|\bink::\w+|\bink_env\b", "onchain"),
    ("near", r"\bnear_sdk\b|#\[near_bindgen\]|#\[near\(|\bnear_contract_standards\b", "onchain"),
    ("soroban", r"\bsoroban_sdk\b|#\[contractimpl\]|#\[contract\]|#\[contracttype\]", "onchain"),
    ("stylus", r"\bstylus_sdk\b|#\[entrypoint\]|\bsol_storage!\b", "onchain"),
    ("multiversx", r"\bmultiversx_sc\b|\belrond_wasm\b|#\[multiversx_sc::contract\]|#\[endpoint\b", "onchain"),
    ("casper", r"\bcasper_contract\b|\bcasper_types\b|\bodra\b", "onchain"),
    ("cosmos-sdk-rs", r"\bcosmrs\b|\bibc_proto\b|\btendermint\b|\bcometbft\b", "offchain"),
    ("reth-alloy", r"\breth\w*\b|\balloy\w*\b|\brevm\b|\bethers\b|\bfoundry_\w+\b", "offchain"),
    ("libp2p", r"\blibp2p\b|\bquinn\b|\bdiscv5\b", "offchain"),
    ("web-service", r"\baxum\b|\bactix_web\b|\bwarp\b|\brocket\b|\btonic\b|\bjsonrpsee\b|\btide\b|\bpoem\b|\bsalvo\b", "offchain"),
    ("storage-engine", r"\brocksdb\b|\bsled\b|\bredb\b|\bmdbx\b|\blmdb\b|\bsqlx\b|\bdiesel\b|\bsea_orm\b", "offchain"),
    ("zk-arith", r"\bark_\w+\b|\bhalo2\w*\b|\bbellman\b|\bplonky\w*\b|\brisc0\w*\b|\bsp1_\w+\b|\bnexus_\w+\b|\bwinterfell\b", "offchain"),
]
ONCHAIN_CARGO_DEPS = {"anchor-lang", "solana-program", "pinocchio", "cosmwasm-std", "frame-support", "ink",
                      "near-sdk", "soroban-sdk", "stylus-sdk", "multiversx-sc", "casper-contract", "odra",
                      "sylvia", "cw-storage-plus", "anchor-spl", "spl-token"}

SOL_FRAMEWORK_FILES = [
    ("foundry", ["foundry.toml"]),
    ("hardhat", ["hardhat.config.js", "hardhat.config.ts", "hardhat.config.cjs", "hardhat.config.mjs"]),
    ("truffle", ["truffle-config.js", "truffle.js"]),
    ("brownie", ["brownie-config.yaml", "brownie-config.yml"]),
    ("ape", ["ape-config.yaml"]),
    ("dapptools", [".dapprc"]),
]

# --------------------------------------------------------------------------- #
# Injection screening
# --------------------------------------------------------------------------- #
TEXT_SCAN_EXT = {".rs", ".sol", ".md", ".mdx", ".txt", ".rst", ".adoc", ".toml", ".json", ".yaml", ".yml",
                 ".js", ".ts", ".cjs", ".mjs", ".sh", ".bash", ".zsh", ".ps1", ".py", ".rb", ".env",
                 ".cfg", ".ini", ".conf", ".nix", ".mk", ".html", ".htm", ".xml", ".csv", ".lock", ""}
TEXT_SCAN_BASENAMES = {"Makefile", "makefile", "GNUmakefile", "justfile", "Justfile", "Dockerfile",
                       "Taskfile.yml", "Procfile", "Rakefile"}
MAX_SCAN_BYTES = 2 * 1024 * 1024

PROMPT_PATTERNS = [
    # (kind, severity, regex)
    ("ai_directive_override", "high",
     r"\b(ignore|disregard|forget|bypass|discard)\b[^\n]{0,30}\b(previous|prior|above|earlier|preceding|initial|original|system|your|all)\b[^\n]{0,20}\b(instructions?|prompts?|rules?|guidelines?|directives?|messages?|constraints?|guardrails?|context)\b"
     r"|\boverride\s+(your|the system|previous|prior|all|any)\s+(instructions?|prompts?|rules?|guidelines?)\b"
     r"|\bnew\s+instructions?\s*:\s*\w|\bfrom now on,? (you|ignore|always|never|respond|answer)\b"),
    ("ai_roleplay", "high",
     r"\byou are (now |no longer )?(a |an )?(helpful |friendly |expert |senior |ai |large language |language |security )*(assistant|model|ai|llm|chatgpt|claude|gpt|copilot|gemini|agent|auditor bot)\b"),
    ("ai_addressed", "high",
     r"\b(dear|attention|note to|notice to|hey|hello|hi|message for|instructions? for)\s+(the\s+)?(ai|assistant|llm|claude|chatgpt|gpt|copilot|gemini|cursor|model|agent|automated (tool|scanner|auditor|reviewer)|language model)\b"),
    ("ai_conditional", "high",
     r"\b(if|when|whenever|in case) you are (an? |the )?(ai|llm|language model|assistant|bot|automated (tool|scanner|auditor|reviewer)|agent|claude|chatgpt|copilot)\b"),
    ("system_prompt_reference", "high",
     r"\b(system prompts?|system messages?|developer messages?|hidden instructions?|secret instructions?|initial prompts?|prompt injections?|jailbreak)\b"),
    ("chat_markup", "high",
     r"<\|im_start\|>|<\|im_end\|>|<\|endoftext\|>|\[INST\]|\[/INST\]|<<SYS>>|<\|system\|>|<\|user\|>|<\|assistant\|>|^\s*###\s*(system|instruction|assistant|human)\s*:?\s*$|^\s*(system|assistant|human)\s*:\s+(you|ignore|please|from now)|\bHuman:\s*$|\bAssistant:\s*$"),
    ("result_steering", "medium",
     r"\b(report|say|state|write|output|conclude|answer|respond|tell (the )?(user|reader|manager|client|team|sales))\b[^\n]{0,60}\b(no (vulnerabilit|issue|finding|bug|problem)|is (secure|safe|fully audited|bug[- ]free)|(\d[\d,]*)\s*(lines|loc|sloc|hours|days|weeks)|(low|minimal|trivial|zero) (complexity|effort|risk)|(a|the) (low|small|minimal) estimate)"),
    ("scope_steering", "medium",
     r"\b(do not|don't|never|skip|exclude|omit|avoid)\b[^\n]{0,40}\b(count|include|scan|analy[sz]e|review|audit|flag|report|mention|read|open|look at)\b[^\n]{0,40}\b(this|these|the following|that|any) (file|folder|directory|module|contract|crate|line|function|code|repo)s?\b"),
    ("tool_call_steering", "medium",
     r"\b(run|execute|invoke|launch)\b[^\n]{0,30}\b(command|script|bash|shell|terminal|curl|wget|npm|npx|yarn|pnpm|cargo|forge|anchor|python|pip|make|install)\b[^\n]{0,60}\b(before|first|and then|so that|in order to)\b[^\n]{0,40}\b(continu|proceed|analy[sz]|auditing|(the )?audit\b|counting|(the )?count\b|estimat|scop|review)"),
    ("exfil_steering", "medium",
     r"\b(send|post|upload|email|paste|exfiltrate|leak|transmit|forward)\b[^\n]{0,40}\b(api[_ -]?keys?|access tokens?|auth(entication)? tokens?|bearer tokens?|credentials?|passwords?|environment variables?|env vars?|\.env\b|ssh keys?|conversation( history)?|chat history|transcripts?|system prompt|previous messages|your (instructions|context|memory))"),
]

# Hidden / obfuscated text
BIDI_CHARS = {"‪", "‫", "‬", "‭", "‮", "⁦", "⁧", "⁨", "⁩"}
ZERO_WIDTH_CHARS = {"​", "‌", "‍", "⁠", "᠎", "﻿", "­"}
BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")
HEX_BLOB_RE = re.compile(r"(?:\\x[0-9a-fA-F]{2}){12,}|(?:0x[0-9a-fA-F]{2}\s*,\s*){48,}")
OBFUSCATION_RE = re.compile(r"String::from_utf8\s*\(\s*vec!\s*\[|from_utf8_lossy\s*\(\s*&\s*\[|char::from_u32\s*\(|\bfromCharCode\s*\(|\batob\s*\(|\bBuffer\.from\s*\([^)]*['\"]base64['\"]|base64\s+(-d|--decode)|\beval\s*\(|new\s+Function\s*\(")
HTML_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.S)
HIDDEN_STYLE_RE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|color\s*:\s*(#fff(fff)?|white|transparent)|opacity\s*:\s*0(\.0+)?\b", re.I)

SHELL_PIPE_RE = re.compile(r"\b(curl|wget|fetch|Invoke-WebRequest|iwr)\b[^\n|]*\|\s*(sudo\s+)?(ba|z|da)?sh\b|base64\s+(-d|--decode)[^\n|]*\|\s*(ba|z)?sh\b|\bnode\s+-e\b[^\n]*\b(child_process|https?:|require\(['\"](net|http|https|dns)['\"]\)|eval|Buffer\.from\([^)]*base64)|\bpython\d?\s+-c\b[^\n]*\b(exec|urllib|requests|socket|subprocess|os\.system)\b")
NETWORK_RE = re.compile(r"\breqwest\b|\bureq\b|\bhyper\b|\bcurl\b|\bwget\b|\bstd::net\b|\bTcpStream\b|\bUdpSocket\b|\bhttps?://|\bgit2\b|\bgit_clone\b|\bdownload\w*\b", re.I)
PROCESS_RE = re.compile(r"\bstd::process\b|\bCommand::new\b|\bexec\w*\s*\(|\bspawn\w*\s*\(|\bchild_process\b|\bexecSync\b|\bspawnSync\b|\bsystem\s*\(|\bos\.system\b|\bsubprocess\b")
FS_SENSITIVE_RE = re.compile(r"\.ssh\b|id_rsa|id_ed25519|authorized_keys|\.aws\b|\.gnupg\b|\.bashrc|\.zshrc|\.profile\b|\.npmrc|\.cargo/credentials|\.config/gcloud|\.kube/config|/etc/passwd|\bHOME\b|\bUSERPROFILE\b|\bkeychain\b|\bwallet\b|\bmnemonic\b|\bseed phrase\b|\bkeypair\b|\bid\.json\b", re.I)
ENV_HOME_RE = re.compile(r"env::var\w*\s*\(\s*\"(HOME|USERPROFILE|PATH|SSH_AUTH_SOCK|AWS_\w+|GITHUB_TOKEN|NPM_TOKEN|CARGO_REGISTRY_TOKEN|ANTHROPIC_API_KEY|OPENAI_API_KEY)\"", re.I)

AGENT_CONFIG_FILES = {
    "CLAUDE.md": "medium", "CLAUDE.local.md": "medium", "AGENTS.md": "medium", "AGENT.md": "medium",
    "GEMINI.md": "medium", ".cursorrules": "medium", ".windsurfrules": "medium", ".clinerules": "medium",
    ".replit": "medium", "copilot-instructions.md": "medium", ".aider.conf.yml": "medium",
    ".mcp.json": "high", "mcp.json": "high", "settings.json": None, "settings.local.json": None,
}
AGENT_CONFIG_DIRS = {".claude", ".cursor", ".codex", ".gemini", ".aider", ".cline", ".windsurf", ".continue", ".roo", ".agents"}

HAZARD_CONFIG_BASENAMES = {
    "build.rs", "Cargo.toml", "config.toml", "config", "foundry.toml", "remappings.txt",
    "hardhat.config.js", "hardhat.config.ts", "hardhat.config.cjs", "hardhat.config.mjs",
    "truffle-config.js", "truffle.js", "package.json", ".npmrc", ".yarnrc", ".yarnrc.yml",
    ".pnpmfile.cjs", "tasks.json", "settings.json", "launch.json", "devcontainer.json", ".envrc",
    "Makefile", "makefile", "GNUmakefile", "justfile", "Justfile", "Taskfile.yml", "flake.nix",
    "shell.nix", "default.nix", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".gitattributes", ".gitmodules", "rust-toolchain", "rust-toolchain.toml", "Anchor.toml",
    ".tool-versions", ".nvmrc", "Scarb.toml",
}
BINARY_EXT = {".exe", ".dll", ".so", ".dylib", ".bin", ".jar", ".class", ".pyc", ".o", ".a", ".lib",
              ".zip", ".tar", ".gz", ".tgz", ".xz", ".bz2", ".7z", ".rar", ".dmg", ".pkg", ".msi",
              ".deb", ".rpm", ".apk", ".ipa", ".wasm", ".node"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def eprint(*a):
    print(*a, file=sys.stderr)


def code_with_strings(text, lang):
    """Comment-stripped text with string literals kept — for hazard scans where URLs/commands in strings matter."""
    return analyze_text(text, lang, keep_strings=True)[1]


def read_text(path):
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def sanitize_excerpt(s, limit=160):
    s = s.strip()
    if len(s) > limit:
        s = s[:limit] + "…"
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if ch in ("\t",):
            out.append(" ")
        elif cat.startswith("C") or ch in BIDI_CHARS or ch in ZERO_WIDTH_CHARS:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    return "".join(out).replace("`", "'")


def rel(path, root):
    return os.path.relpath(path, root).replace(os.sep, "/")


def is_hex_sha(s):
    return bool(re.fullmatch(r"[0-9a-fA-F]{7,64}", s or ""))


def looks_like_url(s):
    return bool(re.match(r"^(https?://|git@|ssh://|git://)", s)) or s.endswith(".git")


# --------------------------------------------------------------------------- #
# Comment / string aware line classification
# --------------------------------------------------------------------------- #
def analyze_text(text, lang, keep_strings=False):
    """
    Returns (per_line, code_only) where
      per_line = list of (has_code, has_comment) per physical line
      code_only = same text with comments blanked and string contents blanked
                  (quotes kept), preserving line structure.
    Handles: // and /* */ comments (nested for Rust), NatSpec, "..." and '...'
    strings, Rust raw strings r#"..."#, byte strings, char literals vs lifetimes,
    Solidity unicode"..." / hex"..." literals.
    """
    n = len(text)
    lines = text.count("\n") + 1
    has_code = [False] * lines
    has_comment = [False] * lines
    out = list(text)
    i = 0
    ln = 0
    rust = lang == "rust"

    def mark_code():
        has_code[ln] = True

    def mark_comment():
        has_comment[ln] = True

    while i < n:
        ch = text[i]
        if ch == "\n":
            ln += 1
            i += 1
            continue
        nxt = text[i + 1] if i + 1 < n else ""
        # Line comment
        if ch == "/" and nxt == "/":
            j = i
            while j < n and text[j] != "\n":
                out[j] = " "
                j += 1
            if any(not c.isspace() for c in text[i:j]):
                mark_comment()
            i = j
            continue
        # Block comment (nested in Rust)
        if ch == "/" and nxt == "*":
            depth = 1
            j = i + 2
            out[i] = out[i + 1] = " "
            mark_comment()
            while j < n and depth > 0:
                c = text[j]
                c2 = text[j + 1] if j + 1 < n else ""
                if c == "\n":
                    ln += 1
                    j += 1
                    continue
                if c == "*" and c2 == "/":
                    depth -= 1
                    out[j] = out[j + 1] = " "
                    j += 2
                    if depth == 0:
                        # the closing delimiter is comment content
                        has_comment[ln] = True
                    continue
                if rust and c == "/" and c2 == "*":
                    depth += 1
                    out[j] = out[j + 1] = " "
                    j += 2
                    continue
                if not c.isspace():
                    has_comment[ln] = True
                out[j] = " "
                j += 1
            i = j
            continue
        # Rust raw / byte / c strings
        if rust and (ch in "rbc") and _rust_string_prefix(text, i):
            j, quote_start = _rust_string_prefix(text, i)
            # j points at the opening quote; determine raw hashes
            k = i
            while k < quote_start:
                out[k] = text[k]
                k += 1
            mark_code()
            hashes = 0
            if "r" in text[i:quote_start]:
                p = quote_start
                while p < n and text[p] == "#":
                    hashes += 1
                    p += 1
                quote_pos = p
                end_delim = '"' + "#" * hashes
                e = text.find(end_delim, quote_pos + 1)
                if e < 0:
                    e = n
                for q in range(quote_start, min(e + len(end_delim), n)):
                    c = text[q]
                    if c == "\n":
                        ln += 1
                    elif q == quote_pos or (q >= e and q < e + len(end_delim)) or (quote_start <= q < quote_pos):
                        out[q] = c
                        mark_code()
                    else:
                        out[q] = c if keep_strings else " "
                        mark_code()
                i = min(e + len(end_delim), n)
                continue
            else:
                i = quote_start  # fall through to normal string handling
                ch = text[i]
        # Solidity unicode"..." / hex"..." prefixes
        if not rust and ch in "uh":
            m = re.match(r"(unicode|hex)(?=[\"'])", text[i:i + 8])
            if m and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
                for q in range(i, i + m.end()):
                    out[q] = text[q]
                mark_code()
                i += m.end()
                ch = text[i] if i < n else ""
        # Strings
        if ch == '"' or (ch == "'" and not rust):
            quote = ch
            out[i] = ch
            mark_code()
            j = i + 1
            while j < n:
                c = text[j]
                if c == "\\" and j + 1 < n:
                    out[j] = " "
                    if text[j + 1] == "\n":
                        ln += 1  # keep the newline in `out` so line structure survives
                    else:
                        out[j + 1] = " "
                    mark_code()
                    j += 2
                    continue
                if c == "\n":
                    # unterminated string on this line; be forgiving
                    ln += 1
                    j += 1
                    if not rust:
                        break
                    continue
                if c == quote:
                    out[j] = c
                    j += 1
                    break
                out[j] = c if keep_strings else " "
                mark_code()
                j += 1
            i = j
            continue
        # Rust char literal vs lifetime
        if rust and ch == "'":
            if nxt == "\\":
                esc = text[i + 2] if i + 2 < n else ""
                if esc == "u":
                    e = text.find("'", i + 3)
                elif esc == "x":
                    e = i + 5
                else:
                    e = i + 3
                if e < 0 or e >= n or text[e] != "'" or e - i > 14:
                    e = i  # malformed; treat the quote as a lone token
                for q in range(i, e + 1):
                    out[q] = text[q] if q in (i, e) else " "
                mark_code()
                i = e + 1
                continue
            if i + 2 < n and text[i + 2] == "'" and nxt != "\n":
                out[i + 1] = " "
                mark_code()
                i += 3
                continue
            # lifetime
            mark_code()
            i += 1
            continue
        if not ch.isspace():
            mark_code()
        i += 1

    per_line = list(zip(has_code, has_comment))
    return per_line, "".join(out)


def _rust_string_prefix(text, i):
    """If text[i:] starts a prefixed Rust string (r"", r#"", b"", br"", c"", cr""), return
    (i, index_of_first_quote_or_hash). Otherwise None."""
    m = re.match(r"(?:b|c)?r|b|c", text[i:i + 3])
    if not m:
        return None
    if i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_"):
        return None
    p = i + m.end()
    if p >= len(text):
        return None
    if "r" in m.group(0):
        q = p
        while q < len(text) and text[q] == "#":
            q += 1
        if q < len(text) and text[q] == '"':
            return (i, p)
        return None
    if text[p] == '"':
        return (i, p)
    return None


def rust_inline_test_lines(code_only):
    """Return a set of 0-based line indices belonging to #[cfg(test)] items."""
    test_lines = set()
    lines = code_only.split("\n")
    # positions of line starts
    starts = []
    pos = 0
    for l in lines:
        starts.append(pos)
        pos += len(l) + 1

    def line_of(idx):
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= idx:
                lo = mid
            else:
                hi = mid - 1
        return lo

    for m in re.finditer(r"#\[cfg\((?:test|all\(\s*test\b[^)]*\))\)\]", code_only):
        start = m.start()
        brace = code_only.find("{", m.end())
        semi = code_only.find(";", m.end())
        if brace < 0 or (0 <= semi < brace):
            # item without a body (e.g. `#[cfg(test)] mod tests;`) — just its line
            test_lines.add(line_of(start))
            continue
        depth = 0
        j = brace
        while j < len(code_only):
            c = code_only[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        for ln in range(line_of(start), line_of(j) + 1):
            test_lines.add(ln)
    return test_lines


# --------------------------------------------------------------------------- #
# Repository walk & classification
# --------------------------------------------------------------------------- #
def load_gitmodules(root):
    paths = set()
    p = os.path.join(root, ".gitmodules")
    txt = read_text(p) if os.path.isfile(p) else None
    if txt:
        for m in re.finditer(r"^\s*path\s*=\s*(.+)$", txt, re.M):
            paths.add(m.group(1).strip().strip("/"))
    return paths


def classify_path(relpath, root, submodules, includes, excludes):
    parts = relpath.split("/")
    dirs = parts[:-1]
    base = parts[-1]
    lower_dirs = [d.lower() for d in dirs]
    lower_base = base.lower()

    if includes and not any(_glob_match(relpath, g) for g in includes):
        return "client_excluded"
    if excludes and any(_glob_match(relpath, g) for g in excludes):
        return "client_excluded"

    # submodules and dependency dirs
    for k in range(1, len(parts)):
        prefix = "/".join(parts[:k])
        if prefix in submodules:
            return "dependency"
    if any(d in DEPENDENCY_DIR_NAMES for d in lower_dirs):
        return "dependency"
    # foundry-style lib/<pkg>/ with its own manifest → dependency
    if "lib" in lower_dirs:
        idx = lower_dirs.index("lib")
        if idx + 1 < len(dirs):
            pkg_dir = os.path.join(root, *dirs[:idx + 2])
            for marker in ("foundry.toml", "package.json", ".git", "Cargo.toml", "hardhat.config.js", "hardhat.config.ts"):
                if os.path.exists(os.path.join(pkg_dir, marker)):
                    return "dependency"
    if any(d in GENERATED_DIR_NAMES for d in lower_dirs) or re.search(r"\.pb\.rs$|_generated\.rs$|\.generated\.sol$|\.g\.rs$", lower_base):
        return "generated"
    if any(d in TEST_DIR_NAMES for d in lower_dirs) or re.search(r"\.t\.sol$|_tests?\.rs$|^test_\w+\.rs$|\.test\.sol$|(^|\W)tests?\.rs$|\bbenches?\b", lower_base):
        return "test"
    if any(d in MOCK_DIR_NAMES for d in lower_dirs) or re.match(r"^(mock|fake|stub|dummy|test)[A-Z_]", base) or re.search(r"mock\.(sol|rs)$", lower_base):
        return "mock"
    if any(d in SCRIPT_DIR_NAMES for d in lower_dirs) or lower_base.endswith(".s.sol"):
        return "script"
    if any(d in EXAMPLE_DIR_NAMES for d in lower_dirs):
        return "example"
    if any(d in INTERFACE_DIR_NAMES for d in lower_dirs):
        return "interface"
    return "source"


def _glob_match(relpath, pattern):
    pattern = pattern.strip().strip("/")
    if fnmatch.fnmatch(relpath, pattern):
        return True
    # directory prefix match: "contracts/core" matches "contracts/core/**"
    if relpath.startswith(pattern + "/"):
        return True
    if fnmatch.fnmatch(relpath, pattern + "/*") or fnmatch.fnmatch(relpath, pattern + "/**"):
        return True
    # match on any path suffix so "*.sol" style works across depth
    if "/" not in pattern and fnmatch.fnmatch(os.path.basename(relpath), pattern):
        return True
    return False


def solidity_decls(code_only):
    decls = []
    for m in re.finditer(r"^\s*(abstract\s+)?(contract|library|interface)\s+([A-Za-z_]\w*)", code_only, re.M):
        kind = m.group(2)
        if m.group(1):
            kind = "abstract contract"
        decls.append({"kind": kind, "name": m.group(3)})
    return decls


def count_indicators(code_only, table):
    hits = {}
    score = 0.0
    for name, (rx, weight, cap, _desc) in table.items():
        c = len(re.findall(rx, code_only, re.M))
        if c:
            hits[name] = c
            score += weight * min(c, cap)
    return hits, round(score, 1)


def detect_rust_frameworks(text):
    found = []
    for name, rx, kind in RUST_FRAMEWORKS:
        if re.search(rx, text):
            found.append((name, kind))
    return found


def nearest_cargo_toml(path, root):
    d = os.path.dirname(path)
    while True:
        cand = os.path.join(d, "Cargo.toml")
        if os.path.isfile(cand):
            return cand
        if os.path.abspath(d) == os.path.abspath(root) or len(d) <= len(root):
            return None
        d = os.path.dirname(d)


def analyze_file(path, root, lang, category):
    text = read_text(path)
    if text is None:
        return None
    per_line, code_only = analyze_text(text, lang)
    total = len(per_line)
    if text.endswith("\n"):
        total -= 1  # trailing newline does not create an extra line
        per_line = per_line[:total]
    inline_test = set()
    if lang == "rust":
        inline_test = {l for l in rust_inline_test_lines(code_only) if l < total}
    blank = comment = code = test_code = 0
    for idx, (hc, hcm) in enumerate(per_line):
        if hc:
            if idx in inline_test:
                test_code += 1
            else:
                code += 1
        elif hcm:
            comment += 1
        else:
            blank += 1

    # indicators on non-test code only
    if inline_test:
        code_lines = code_only.split("\n")
        code_only_main = "\n".join(l for i, l in enumerate(code_lines) if i not in inline_test)
    else:
        code_only_main = code_only

    info = {
        "path": rel(path, root),
        "lang": lang,
        "category": category,
        "lines": total,
        "blank": blank,
        "comment": comment,
        "code": code,
        "inline_test_code": test_code,
    }
    if lang == "solidity":
        decls = solidity_decls(code_only_main)
        info["decls"] = decls
        if category == "source" and decls and all(d["kind"] == "interface" for d in decls):
            info["category"] = "interface"
        if category == "source" and decls and all(d["kind"] == "abstract contract" for d in decls) is False and \
                any(d["name"].lower().startswith(("mock", "fake", "stub", "dummy")) for d in decls) and \
                all(d["name"].lower().startswith(("mock", "fake", "stub", "dummy", "i")) for d in decls):
            info["category"] = "mock"
        m = re.search(r"pragma\s+solidity\s+([^;]+);", code_only_main)
        info["pragma"] = m.group(1).strip() if m else None
        hits, score = count_indicators(code_only_main, SOL_INDICATORS)
        table = SOL_INDICATORS
    else:
        fw = detect_rust_frameworks(text)
        info["frameworks"] = sorted({n for n, _ in fw})
        info["rust_kind"] = "onchain" if any(k == "onchain" for _, k in fw) else ("offchain" if fw else None)
        hits, score = count_indicators(code_only_main, RUST_INDICATORS)
        table = RUST_INDICATORS
        if re.search(r"^\s*#!\[no_std\]", code_only_main, re.M):
            info["no_std"] = True
    info["indicators"] = hits
    info["critical_score"] = score
    # human-readable reasons: top indicators by weighted contribution
    contrib = []
    for name, c in hits.items():
        rx, w, cap, desc = table[name]
        contrib.append((w * min(c, cap), "%s (%d)" % (desc, c)))
    contrib.sort(reverse=True)
    info["reasons"] = [d for _, d in contrib[:5]]
    return info


def walk_repo(root, includes, excludes):
    submodules = load_gitmodules(root)
    files = []
    unsupported = defaultdict(lambda: {"files": 0, "lines": 0})
    hazard_files = []
    text_files = []
    binaries = []
    agent_files = []
    skipped_large = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in ALWAYS_SKIP_DIRS or d in AGENT_CONFIG_DIRS)
        # keep .claude etc. for hazard scanning, but never walk .git
        dirnames[:] = [d for d in dirnames if d != ".git"]
        relbase = rel(dirpath, root)
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            if os.path.islink(full):
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            rp = fn if relbase == "." else relbase + "/" + fn
            ext = os.path.splitext(fn)[1].lower()
            parts = rp.split("/")
            in_agent_dir = any(p in AGENT_CONFIG_DIRS for p in parts[:-1])
            if fn in AGENT_CONFIG_FILES or in_agent_dir or (fn == "copilot-instructions.md"):
                agent_files.append(rp)
            if fn in HAZARD_CONFIG_BASENAMES or ext in (".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd") or \
                    (".github/workflows" in relbase.replace("\\", "/") and ext in (".yml", ".yaml")) or \
                    (".vscode" in parts or ".devcontainer" in parts or ".cargo" in parts) or fn.startswith(".env"):
                hazard_files.append(rp)
            if ext in BINARY_EXT:
                binaries.append((rp, size))
            if ext in LANG_BY_EXT:
                if size > MAX_SCAN_BYTES:
                    skipped_large.append((rp, size))
                    continue
                cat = classify_path(rp, root, submodules, includes, excludes)
                files.append((full, rp, LANG_BY_EXT[ext], cat))
            elif ext in UNSUPPORTED_CODE_EXT:
                cat = classify_path(rp, root, submodules, includes, excludes)
                if cat in ("source", "interface"):
                    txt = read_text(full) if size <= MAX_SCAN_BYTES else None
                    if txt is not None:
                        unsupported[ext]["files"] += 1
                        unsupported[ext]["lines"] += sum(1 for l in txt.split("\n") if l.strip())
            if size <= MAX_SCAN_BYTES and (ext in TEXT_SCAN_EXT or fn in TEXT_SCAN_BASENAMES or fn in AGENT_CONFIG_FILES or in_agent_dir):
                text_files.append((full, rp))
    return {
        "files": files,
        "unsupported": dict(unsupported),
        "hazard_files": hazard_files,
        "text_files": text_files,
        "binaries": binaries,
        "agent_files": agent_files,
        "skipped_large": skipped_large,
        "submodules": sorted(submodules),
    }


# --------------------------------------------------------------------------- #
# Injection screening
# --------------------------------------------------------------------------- #
class Findings:
    def __init__(self):
        self.items = []
        self._seen = set()

    def add(self, severity, kind, path, line, message, excerpt=""):
        key = (kind, path, line)
        if key in self._seen:
            return
        self._seen.add(key)
        self.items.append({
            "severity": severity, "kind": kind, "file": path, "line": line,
            "message": message, "excerpt": sanitize_excerpt(excerpt) if excerpt else "",
        })

    def sorted(self):
        order = {"high": 0, "medium": 1, "info": 2}
        return sorted(self.items, key=lambda f: (order.get(f["severity"], 3), f["file"], f["line"] or 0))


def scan_prompt_injection(text, rp, findings, code_only=None, lang=None):
    lines = text.split("\n")
    is_doc = not lang
    co_lines = code_only.split("\n") if code_only is not None else None
    for idx, line in enumerate(lines, 1):
        low = line
        # for code files, only look inside comments/strings (the stripped-out parts)
        if co_lines is not None:
            co_line = co_lines[idx - 1] if idx - 1 < len(co_lines) else ""
            # comment/string text = chars that were blanked in code_only
            segment = "".join(c if (j >= len(co_line) or co_line[j] == " ") else " " for j, c in enumerate(line))
            low = segment
        if not low.strip():
            continue
        for kind, sev, rx in PROMPT_PATTERNS:
            if re.search(rx, low, re.I | re.M):
                findings.add(sev, "prompt_injection:" + kind, rp, idx,
                             "Text that reads as an instruction to an AI assistant / automated reviewer.", line)
                break
        # hidden characters
        bidi = [c for c in line if c in BIDI_CHARS]
        if bidi:
            findings.add("high", "hidden_text:bidi_override", rp, idx,
                         "Unicode bidirectional control character (Trojan Source technique) — rendered code can differ from compiled code.", line)
        zw = [c for c in line if c in ZERO_WIDTH_CHARS and not (idx == 1 and c == "﻿" and line.startswith("﻿"))]
        if zw:
            findings.add("medium", "hidden_text:zero_width", rp, idx,
                         "Zero-width / invisible Unicode characters present.", line)
        b64 = BASE64_BLOB_RE.search(low)
        if b64 and not rp.endswith((".lock", ".json", ".svg", ".snap", ".map", ".csv")) and not re.fullmatch(r"(0x)?[0-9a-fA-F]+", b64.group(0)):
            findings.add("medium", "encoded_blob:base64", rp, idx,
                         "Long base64-looking blob in comment/documentation text.", line)
        if HEX_BLOB_RE.search(line):
            findings.add("info", "encoded_blob:hex", rp, idx,
                         "Large embedded hex/byte blob — auditors should verify what it decodes to.", line)
    # html comments & hidden styling in docs
    if is_doc and rp.lower().endswith((".md", ".mdx", ".html", ".htm", ".rst", ".txt")):
        for m in HTML_COMMENT_RE.finditer(text):
            body = m.group(1)
            ln = text.count("\n", 0, m.start()) + 1
            for kind, sev, rx in PROMPT_PATTERNS:
                if re.search(rx, body, re.I | re.M):
                    findings.add("high", "prompt_injection:html_comment", rp, ln,
                                 "Hidden HTML comment containing AI-directed instructions.", body)
                    break
            else:
                if len(body.strip()) > 300:
                    findings.add("info", "hidden_text:long_html_comment", rp, ln,
                                 "Long hidden HTML comment in documentation — review its content.", body)
        for m in HIDDEN_STYLE_RE.finditer(text):
            ln = text.count("\n", 0, m.start()) + 1
            findings.add("medium", "hidden_text:css_hidden", rp, ln,
                         "Styling that hides text from human readers while keeping it machine-readable.", text.split("\n")[ln - 1])


def scan_non_ascii_identifiers(code_only, rp, findings):
    for idx, line in enumerate(code_only.split("\n"), 1):
        for ch in line:
            if ord(ch) > 127 and not ch.isspace():
                cat = unicodedata.category(ch)
                if cat.startswith("L") or cat.startswith("M") or cat.startswith("N"):
                    findings.add("high", "hidden_text:non_ascii_identifier", rp, idx,
                                 "Non-ASCII letter in code outside comments/strings — possible homoglyph identifier.", line)
                    break
                if cat.startswith("C"):
                    findings.add("high", "hidden_text:control_char_in_code", rp, idx,
                                 "Invisible/control character in code outside comments/strings.", line)
                    break


def scan_hazard_file(full, rp, findings, root):
    fn = os.path.basename(rp)
    parts = rp.split("/")
    text = read_text(full)
    if text is None:
        return
    low = text
    in_deps = any(p in DEPENDENCY_DIR_NAMES or p in ALWAYS_SKIP_DIRS for p in parts[:-1])

    def has(rx):
        return re.search(rx, low, re.M | re.I) is not None

    def first_line(rx):
        m = re.search(rx, low, re.M | re.I)
        if not m:
            return None, ""
        return low.count("\n", 0, m.start()) + 1, low.split("\n")[low.count("\n", 0, m.start())]

    # ---- Rust ----
    is_build_script = fn == "build.rs" and os.path.isfile(os.path.join(os.path.dirname(full), "Cargo.toml"))
    if is_build_script:
        low = code_with_strings(text, "rust")
        risky = NETWORK_RE.search(low) or PROCESS_RE.search(low) or FS_SENSITIVE_RE.search(low) or ENV_HOME_RE.search(low) \
            or has(r"\binclude!\s*\(") or OBFUSCATION_RE.search(low)
        if risky:
            ln, ex = first_line(NETWORK_RE.pattern + "|" + PROCESS_RE.pattern + "|" + FS_SENSITIVE_RE.pattern + r"|\binclude!\s*\(")
            ex = text.split("\n")[ln - 1] if ln else ex
            findings.add("high", "code_exec:build_script_suspicious", rp, ln,
                         "Cargo build script performs network / process / sensitive filesystem access. It runs automatically on `cargo build`, `cargo test`, `cargo check`, and on IDE indexing (rust-analyzer). Do not build.", ex)
        else:
            findings.add("medium" if not in_deps else "info", "code_exec:build_script", rp, None,
                         "Cargo build script present — arbitrary code runs at compile time (including IDE background checks). Do not build; auditors should read it first.")
    if fn == "Cargo.toml":
        if has(r"^\s*proc-macro\s*=\s*true"):
            crate_dir = os.path.dirname(full)
            risky_line = None
            for dp, dn, fns in os.walk(os.path.join(crate_dir, "src")):
                for f2 in fns:
                    if f2.endswith(".rs"):
                        raw2 = read_text(os.path.join(dp, f2)) or ""
                        t2 = code_with_strings(raw2, "rust")
                        m2 = NETWORK_RE.search(t2) or PROCESS_RE.search(t2) or FS_SENSITIVE_RE.search(t2) or ENV_HOME_RE.search(t2)
                        if m2:
                            risky_line = (rel(os.path.join(dp, f2), root), t2.count("\n", 0, m2.start()) + 1, t2.split("\n")[t2.count("\n", 0, m2.start())])
                            break
                if risky_line:
                    break
            if risky_line:
                findings.add("high", "code_exec:proc_macro_crate_suspicious", risky_line[0], risky_line[1],
                             "Procedural-macro crate performs network / process / sensitive filesystem access — this code runs inside the compiler and rust-analyzer on any build or IDE open.", risky_line[2])
            else:
                findings.add("info", "code_exec:proc_macro_crate", rp, first_line(r"proc-macro\s*=\s*true")[0],
                             "Procedural-macro crate — executes at compile time in the compiler / rust-analyzer process. Auditors read it before building.")
        if has(r"^\s*build\s*=\s*\""):
            ln, ex = first_line(r"^\s*build\s*=\s*\"")
            findings.add("medium", "code_exec:custom_build_script_path", rp, ln, "Custom build-script path declared.", ex)
        if has(r"^\s*\[patch"):
            ln, ex = first_line(r"^\s*\[patch")
            findings.add("medium", "supply_chain:cargo_patch", rp, ln, "Dependency source substitution via [patch] — crates may be replaced with local/remote forks.", ex)
        for m in re.finditer(r"^\s*([\w-]+)\s*=\s*\{[^}\n]*\bgit\s*=\s*\"([^\"]+)\"", low, re.M):
            findings.add("info", "supply_chain:git_dependency", rp, low.count("\n", 0, m.start()) + 1,
                         "Dependency pulled from a git URL rather than crates.io: %s" % m.group(1), m.group(0))
        for m in re.finditer(r"^\s*([\w-]+)\s*=\s*\{[^}\n]*\bpath\s*=\s*\"([^\"]*)\"", low, re.M):
            dep_path = os.path.normpath(os.path.join(os.path.dirname(full), m.group(2)))
            if os.path.isabs(m.group(2)) or m.group(2).startswith("~") or not (dep_path + os.sep).startswith(os.path.abspath(root) + os.sep):
                findings.add("medium", "supply_chain:path_dependency_outside_repo", rp, low.count("\n", 0, m.start()) + 1,
                             "Path dependency resolves outside the repository (%s) — the analysed tree does not contain that code." % m.group(1), m.group(0))
    if ".cargo" in parts and fn in ("config.toml", "config"):
        rx = r"^\s*(runner|rustc|rustc-wrapper|rustc-workspace-wrapper|rustdoc|replace-with|git-fetch-with-cli|linker)\s*=|^\s*\[(patch|source|alias|env)\b|-C\s*link-arg|--cfg\b"
        if has(rx):
            ln, ex = first_line(rx)
            findings.add("high", "code_exec:cargo_config", rp, ln,
                         ".cargo/config overrides the toolchain (runner / rustc wrapper / linker / source replacement / env). Any cargo command in this tree would run attacker-chosen binaries.", ex)
        else:
            findings.add("info", "code_exec:cargo_config_present", rp, None, ".cargo/config present — review before running any cargo command.")
    if fn in ("rust-toolchain", "rust-toolchain.toml"):
        if has(r"^\s*path\s*=|channel\s*=\s*\"[^\"]*(nightly|dev)"):
            ln, ex = first_line(r"^\s*path\s*=|channel\s*=")
            findings.add("info", "toolchain:pinned_custom", rp, ln, "Custom / nightly toolchain pinned.", ex)

    # ---- Solidity tooling ----
    if fn == "foundry.toml":
        if has(r"^\s*ffi\s*=\s*true"):
            ln, ex = first_line(r"^\s*ffi\s*=\s*true")
            findings.add("high", "code_exec:foundry_ffi", rp, ln,
                         "Foundry `ffi = true` lets tests/scripts execute arbitrary shell commands via vm.ffi(). Do not run forge test/script.", ex)
        if has(r"^\s*fs_permissions\s*=.*(read-write|write)"):
            ln, ex = first_line(r"^\s*fs_permissions")
            findings.add("medium", "code_exec:foundry_fs_write", rp, ln, "Foundry filesystem write permissions for cheatcodes.", ex)
        if has(r"^\s*(remappings|libs)\s*=.*(\.\./|^/|~/)"):
            ln, ex = first_line(r"^\s*(remappings|libs)\s*=")
            findings.add("medium", "supply_chain:remapping_outside_repo", rp, ln, "Remapping / libs path points outside the repository.", ex)
    if fn == "remappings.txt":
        if has(r"=\s*(\.\./|/|~/)"):
            ln, ex = first_line(r"=\s*(\.\./|/|~/)")
            findings.add("medium", "supply_chain:remapping_outside_repo", rp, ln, "Remapping points outside the repository.", ex)
    if fn.startswith(("hardhat.config", "truffle-config", "truffle.js")):
        if PROCESS_RE.search(low) or OBFUSCATION_RE.search(low) or has(r"require\(['\"](https?|node:http|http|https|net|dgram)['\"]\)|\bfetch\s*\(|\baxios\b|\bprocess\.env\.[A-Z_]*(KEY|SECRET|MNEMONIC|TOKEN)"):
            ln, ex = first_line(PROCESS_RE.pattern + "|" + OBFUSCATION_RE.pattern + r"|\bfetch\s*\(|\baxios\b|process\.env\.[A-Z_]*(KEY|SECRET|MNEMONIC|TOKEN)")
            sev = "high" if (PROCESS_RE.search(low) or OBFUSCATION_RE.search(low)) else "info"
            findings.add(sev, "code_exec:js_config_suspicious", rp, ln,
                         "Hardhat/Truffle config is executable JS that runs on every command; it spawns processes, evaluates code, or reads secrets from the environment." if sev == "high"
                         else "Config reads secrets / performs network calls — do not run with real credentials.", ex)
        else:
            findings.add("info", "code_exec:js_config", rp, None, "Executable JS/TS config — runs on any hardhat/truffle command. Do not run.")
    if fn == "package.json" and not in_deps:
        m = re.search(r"\"(preinstall|postinstall|install|prepare|prepublish|prepublishOnly|preprepare|postprepare)\"\s*:\s*\"([^\"]*)\"", low)
        if m:
            ln = low.count("\n", 0, m.start()) + 1
            sev = "high" if (SHELL_PIPE_RE.search(m.group(2)) or OBFUSCATION_RE.search(m.group(2)) or re.search(r"\bnode\s+-e|\bcurl\b|\bwget\b|https?://|\bbash\b|\bsh\s+-c", m.group(2))) else "medium"
            findings.add(sev, "code_exec:npm_lifecycle_script", rp, ln,
                         "npm lifecycle script runs automatically on `npm/yarn/pnpm install`. Do not install dependencies.", m.group(0))
        for m in re.finditer(r"\"[^\"]+\"\s*:\s*\"((git\+|github:|https?://|file:|link:)[^\"]*)\"", low):
            findings.add("info", "supply_chain:npm_nonregistry_dependency", rp, low.count("\n", 0, m.start()) + 1,
                         "npm dependency from git/URL/file rather than the registry.", m.group(0))
    if fn in (".npmrc", ".yarnrc", ".yarnrc.yml", ".pnpmfile.cjs"):
        if fn == ".pnpmfile.cjs" or has(r"^\s*registry\s*=|^\s*npmRegistryServer|^\s*plugins\s*:|^\s*@[\w-]+:registry|^\s*_auth|^\s*//.*:_authToken"):
            ln, ex = first_line(r"registry|plugins|_auth")
            findings.add("medium", "supply_chain:package_manager_config", rp, ln, "Package-manager config overrides registry / adds plugins / hooks (pnpmfile).", ex)

    # ---- Editor / dev-environment auto-execution ----
    if ".vscode" in parts:
        if fn == "tasks.json" and has(r"folderOpen"):
            ln, ex = first_line(r"folderOpen")
            findings.add("high", "code_exec:vscode_task_on_open", rp, ln, "VS Code task configured to run automatically when the folder is opened.", ex)
        if fn == "settings.json":
            rx = r"rust-analyzer\.(server\.path|check\.overrideCommand|cargo\.buildScripts\.overrideCommand|runnables\.command|procMacro\.server)|terminal\.integrated\.(shell|profiles|automationProfile|env)|python\.defaultInterpreterPath|git\.path|solidity\.(compileUsingLocalVersion|defaultCompiler|remappings)|\"[\w.]*\.(path|command|executable)\"\s*:"
            if has(rx):
                ln, ex = first_line(rx)
                findings.add("high", "code_exec:vscode_settings_override", rp, ln,
                             "Workspace settings override tool binaries / commands (rust-analyzer, terminal, git, compiler) — opening the folder in VS Code may execute repo-controlled programs.", ex)
            elif has(r"security\.workspace\.trust|files\.autoSave|editor\."):
                pass
            else:
                findings.add("info", "code_exec:vscode_settings", rp, None, "Workspace settings file present — review before trusting the workspace.")
        if fn == "launch.json":
            findings.add("info", "code_exec:vscode_launch", rp, None, "Debug launch configuration present — runs only on explicit debug start.")
    if ".devcontainer" in parts or fn == "devcontainer.json":
        rx = r"(postCreateCommand|onCreateCommand|postStartCommand|postAttachCommand|initializeCommand|updateContentCommand)"
        if has(rx):
            ln, ex = first_line(rx)
            findings.add("medium", "code_exec:devcontainer_lifecycle", rp, ln, "Dev-container lifecycle command runs automatically when the container is opened.", ex)
    if fn == ".envrc":
        findings.add("high", "code_exec:direnv", rp, None, ".envrc present — direnv executes it on `cd` into the directory if allowed. Do not `direnv allow`.")
    if fn.startswith(".env") and fn not in (".envrc",):
        if has(r"(PRIVATE_KEY|MNEMONIC|SEED|SECRET|API_KEY|TOKEN)\s*=\s*\S{8,}"):
            findings.add("info", "secrets:env_file_with_values", rp, None, ".env-style file contains populated secret-looking values — never source it; flag to the client.")

    # ---- Shell / task runners ----
    if fn in ("Makefile", "makefile", "GNUmakefile", "justfile", "Justfile", "Taskfile.yml") or fn.endswith((".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd")):
        if SHELL_PIPE_RE.search(low):
            m = SHELL_PIPE_RE.search(low)
            findings.add("high", "code_exec:remote_script_pipe", rp, low.count("\n", 0, m.start()) + 1,
                         "Downloads and pipes a remote script into a shell (or decodes-and-executes). Do not run.", low.split("\n")[low.count("\n", 0, m.start())])
        elif OBFUSCATION_RE.search(low):
            m = OBFUSCATION_RE.search(low)
            findings.add("medium", "code_exec:obfuscated_shell", rp, low.count("\n", 0, m.start()) + 1,
                         "Encoded / evaluated content in a script.", low.split("\n")[low.count("\n", 0, m.start())])
        elif FS_SENSITIVE_RE.search(low):
            m = FS_SENSITIVE_RE.search(low)
            findings.add("info", "code_exec:script_touches_sensitive_paths", rp, low.count("\n", 0, m.start()) + 1,
                         "Script references home-directory secrets / wallet / SSH paths.", low.split("\n")[low.count("\n", 0, m.start())])
    if fn in ("flake.nix", "shell.nix", "default.nix"):
        findings.add("info", "code_exec:nix_env", rp, None, "Nix environment definition — `nix develop` / `nix-shell` executes it. Do not enter the shell.")
    if fn.lower() in ("dockerfile", "docker-compose.yml", "docker-compose.yaml"):
        if SHELL_PIPE_RE.search(low):
            m = SHELL_PIPE_RE.search(low)
            findings.add("medium", "code_exec:remote_script_pipe", rp, low.count("\n", 0, m.start()) + 1,
                         "Container build pipes a remote script into a shell.", low.split("\n")[low.count("\n", 0, m.start())])

    # ---- CI ----
    if ".github/workflows" in rp:
        if has(r"^\s*(on\s*:.*)?pull_request_target\b|^\s*pull_request_target\s*:"):
            ln, ex = first_line(r"pull_request_target")
            findings.add("medium", "supply_chain:ci_pull_request_target", rp, ln,
                         "Workflow triggers on pull_request_target — fork PRs can run with repository secrets if it checks out PR code.", ex)
        if has(r"\$\{\{\s*github\.event\.(issue|comment|pull_request)\.(title|body)"):
            ln, ex = first_line(r"\$\{\{\s*github\.event\.(issue|comment|pull_request)\.(title|body)")
            findings.add("info", "supply_chain:ci_untrusted_interpolation", rp, ln, "Workflow interpolates untrusted event text into a run step (CI script-injection pattern).", ex)

    # ---- git ----
    if fn == ".gitattributes" and has(r"\bfilter\s*="):
        ln, ex = first_line(r"\bfilter\s*=")
        findings.add("info", "supply_chain:git_filter", rp, ln, "Git clean/smudge filter declared (only active if configured locally).", ex)
    if fn == ".gitmodules":
        for m in re.finditer(r"^\s*url\s*=\s*(.+)$", low, re.M):
            url = m.group(1).strip()
            if not url.startswith(("https://github.com/", "https://gitlab.com/", "https://")):
                findings.add("info", "supply_chain:submodule_nonhttps", rp, low.count("\n", 0, m.start()) + 1,
                             "Submodule from a non-HTTPS / non-public source.", m.group(0))


def scan_agent_file(full, rp, findings):
    fn = os.path.basename(rp)
    parts = rp.split("/")
    text = read_text(full)
    if fn in (".mcp.json", "mcp.json") or (fn in ("settings.json", "settings.local.json") and ".claude" in parts):
        sev = "high"
        msg = ("MCP server definition — any agent that loads it would execute the configured server command." if "mcp" in fn
               else "Claude Code settings file in the target repo — may define hooks (shell commands run on tool events) or permissions.")
        if text and fn.startswith("settings") and not re.search(r"\"hooks\"|\"permissions\"|\"env\"|\"enabledPlugins\"|\"mcpServers\"|\"extraKnownMarketplaces\"", text):
            sev = "medium"
        findings.add(sev, "agent_config:executable", rp, None, msg + " Never load or trust it; this skill runs with its own configuration only.")
        return
    findings.add("medium", "agent_config:instruction_file", rp, None,
                 "AI-agent instruction file inside the target repository (%s). Do not load it; it can steer automated reviewers. Its content was screened for injection patterns below." % fn)
    if text:
        for idx, line in enumerate(text.split("\n"), 1):
            for kind, sev, rx in PROMPT_PATTERNS:
                if re.search(rx, line, re.I):
                    findings.add("high", "prompt_injection:agent_config:" + kind, rp, idx,
                                 "AI-directed instruction inside an agent config file.", line)
                    break


def run_injection_screen(root, walk, analyzed_by_path):
    findings = Findings()
    agent_set = set(walk["agent_files"])
    for full, rp in walk["text_files"]:
        if rp in agent_set:
            continue  # scanned separately by scan_agent_file
        ext = os.path.splitext(rp)[1].lower()
        lang = LANG_BY_EXT.get(ext)
        text = read_text(full)
        if text is None:
            continue
        parts = rp.split("/")
        in_deps = any(p in DEPENDENCY_DIR_NAMES for p in parts[:-1])
        if lang:
            info = analyzed_by_path.get(rp)
            if info is None or in_deps or info.get("category") == "dependency":
                continue
            _, code_only = analyze_text(text, lang)
            scan_prompt_injection(text, rp, findings, code_only=code_only, lang=lang)
            scan_non_ascii_identifiers(code_only, rp, findings)
        else:
            if in_deps:
                continue
            if rp.endswith(".lock") or os.path.basename(rp) in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Cargo.lock"):
                continue
            scan_prompt_injection(text, rp, findings)
    for rp in walk["hazard_files"]:
        scan_hazard_file(os.path.join(root, rp), rp, findings, root)
    for rp in walk["agent_files"]:
        scan_agent_file(os.path.join(root, rp), rp, findings)
    for rp, size in walk["binaries"]:
        findings.add("info", "binary_artifact", rp, None,
                     "Binary / archive artifact in the repository (%d KB). Do not execute or extract; auditors should verify provenance." % (size // 1024))
    if walk["submodules"]:
        findings.add("info", "submodules_present", ".gitmodules", None,
                     "Repository declares %d git submodule(s) — they are not fetched by this tool; their code is excluded from the count: %s" % (len(walk["submodules"]), ", ".join(walk["submodules"][:10])))
    return findings.sorted()


# --------------------------------------------------------------------------- #
# Aggregation, complexity, effort
# --------------------------------------------------------------------------- #
def aggregate(files):
    by_lang_cat = defaultdict(lambda: defaultdict(lambda: {"files": 0, "lines": 0, "blank": 0, "comment": 0, "code": 0, "inline_test_code": 0}))
    for f in files:
        b = by_lang_cat[f["lang"]][f["category"]]
        b["files"] += 1
        for k in ("lines", "blank", "comment", "code", "inline_test_code"):
            b[k] += f[k]
    return {lang: dict(cats) for lang, cats in by_lang_cat.items()}


def crate_kinds(files, root):
    """Decide on-chain vs off-chain per Rust crate using file-level framework hits and Cargo.toml deps."""
    crate_files = defaultdict(list)
    for f in files:
        if f["lang"] != "rust":
            continue
        crate = nearest_cargo_toml(os.path.join(root, f["path"]), root)
        crate_rel = rel(crate, root) if crate else "(no Cargo.toml)"
        crate_files[crate_rel].append(f)
    kinds = {}
    for crate, fs in crate_files.items():
        kind = None
        if any(f.get("rust_kind") == "onchain" for f in fs):
            kind = "onchain"
        else:
            if crate != "(no Cargo.toml)":
                txt = read_text(os.path.join(root, crate)) or ""
                deps = set(re.findall(r"^\s*([\w-]+)\s*=", txt, re.M))
                if deps & ONCHAIN_CARGO_DEPS or re.search(r"crate-type\s*=\s*\[[^\]]*\"cdylib\"", txt):
                    kind = "onchain"
        if kind is None:
            kind = "offchain" if any(f.get("rust_kind") == "offchain" for f in fs) else "offchain"
        kinds[crate] = kind
        for f in fs:
            f["crate"] = crate
            f["rust_kind_resolved"] = kind
    return kinds


def suggest_complexity(files, lang):
    src = [f for f in files if f["lang"] == lang and f["category"] == "source"]
    code = sum(f["code"] for f in src) or 1
    total_score = sum(f["critical_score"] for f in src)
    density = total_score / (code / 1000.0)
    ind = defaultdict(int)
    for f in src:
        for k, v in f["indicators"].items():
            ind[k] += v
    drivers = []
    high_triggers = []
    kloc = code / 1000.0

    def per_k(k):
        return ind.get(k, 0) / kloc

    if lang == "solidity":
        if ind.get("cross_chain", 0) >= 5 and per_k("cross_chain") >= 1.0: high_triggers.append("cross-chain messaging (%d refs)" % ind["cross_chain"])
        if ind.get("diamond", 0) >= 3: high_triggers.append("diamond proxy pattern")
        if ind.get("assembly", 0) >= 5 and per_k("assembly") >= 5.0: high_triggers.append("heavy inline assembly (%d blocks)" % ind["assembly"])
        if per_k("fixed_point_math") >= 4.0 and per_k("defi_core") >= 6.0: high_triggers.append("precision-math-heavy DeFi logic")
        if ind.get("flash_callbacks", 0) >= 3 and per_k("flash_callbacks") >= 1.5: high_triggers.append("flash-loan / hook callbacks")
        if ind.get("delegatecall", 0) >= 3 and per_k("delegatecall") >= 1.0: high_triggers.append("multiple delegatecall sites")
        if per_k("oracle") >= 3.0 and per_k("defi_core") >= 6.0: high_triggers.append("oracle-dependent DeFi logic")
        med = [("oracle", "price oracles"), ("signatures", "signature verification"), ("upgradeable", "upgradeable contracts"),
               ("governance", "governance / timelock"), ("defi_core", "DeFi value flows"), ("low_level_call", "low-level calls"),
               ("unchecked_math", "unchecked arithmetic"), ("storage_layout", "manual storage slots")]
    else:
        if ind.get("cross_chain", 0) >= 10 and per_k("cross_chain") >= 5.0: high_triggers.append("cross-chain / IBC / bridge logic (%d refs)" % ind["cross_chain"])
        if ind.get("unsafe", 0) >= 5 and per_k("unsafe") >= 1.5: high_triggers.append("substantial unsafe code (%d blocks)" % ind["unsafe"])
        if ind.get("ffi_memory", 0) >= 5 and per_k("ffi_memory") >= 1.5: high_triggers.append("raw memory / FFI manipulation")
        if ind.get("crypto", 0) >= 10 and per_k("crypto") >= 3.0: high_triggers.append("cryptography-heavy code")
        if ind.get("consensus_protocol", 0) >= 30 and per_k("consensus_protocol") >= 6.0: high_triggers.append("consensus / protocol-core logic")
        if per_k("cpi") >= 5.0 and per_k("value_transfer") >= 2.0: high_triggers.append("CPI-heavy value transfers")
        if per_k("defi_core") >= 8.0 and per_k("checked_math") >= 6.0: high_triggers.append("math-heavy DeFi logic")
        if per_k("oracle") >= 3.0 and per_k("defi_core") >= 8.0: high_triggers.append("oracle-dependent DeFi logic")
        med = [("oracle", "price oracles"), ("cpi", "cross-program calls"), ("unsafe", "unsafe blocks"), ("token_ops", "token operations"),
               ("value_transfer", "native value transfers"), ("deserialization", "custom deserialisation"), ("concurrency", "concurrency"),
               ("upgrade_migration", "upgrade / migration paths"), ("numeric_casts", "numeric casts")]
    for k, label in med:
        if ind.get(k, 0) >= 3 and per_k(k) >= 0.5:
            drivers.append("%s (%d)" % (label, ind[k]))
    small = code < 300  # density is meaningless on tiny code bases
    if high_triggers:
        tier = "high"
    elif len(drivers) >= 2 or (density >= 40 and not small):
        tier = "medium"
    else:
        tier = "low"
    return {
        "tier": tier,
        "indicator_density_per_kloc": round(density, 1),
        "high_triggers": high_triggers,
        "drivers": drivers[:8],
        "indicator_totals": dict(sorted(ind.items(), key=lambda kv: -kv[1])),
    }


def estimate_effort(files, agg, complexity, rates, team, override_tier):
    r = rates
    parts = []
    notes = []
    core = 0.0
    for lang in ("solidity", "rust"):
        cats = agg.get(lang, {})
        src_code = cats.get("source", {}).get("code", 0)
        if src_code == 0:
            continue
        test_code = cats.get("test", {}).get("code", 0) + sum(f["inline_test_code"] for f in files if f["lang"] == lang)
        comment = sum(c["comment"] for k, c in cats.items() if k == "source")
        lines = sum(c["lines"] for k, c in cats.items() if k == "source") or 1
        tier = override_tier or complexity[lang]["tier"]
        if lang == "solidity":
            buckets = {"solidity": src_code}
        else:
            buckets = defaultdict(int)
            for f in files:
                if f["lang"] == "rust" and f["category"] == "source":
                    buckets["rust_" + (f.get("rust_kind_resolved") or "offchain")] += f["code"]
        for kind, code in buckets.items():
            if code == 0:
                continue
            rate = r["loc_per_auditor_day"][kind][tier]
            days = code / float(rate)
            mult = 1.0
            applied = []
            if test_code == 0:
                mult *= r["no_tests_multiplier"]
                applied.append("no test suite (x%.2f)" % r["no_tests_multiplier"])
            if comment / float(lines) < r["low_docs_threshold"]:
                mult *= r["low_docs_multiplier"]
                applied.append("sparse documentation (x%.2f)" % r["low_docs_multiplier"])
            days *= mult
            parts.append({"bucket": kind, "tier": tier, "code": code, "rate_loc_per_day": rate,
                          "auditor_days": round(days, 1), "adjustments": applied})
            core += days
    if core == 0:
        return {"parts": [], "note": "No in-scope Rust or Solidity source code found."}
    core_adj = max(core, r["min_core_review_days"])
    if core_adj > core:
        notes.append("Core review raised to the minimum engagement of %d auditor-days." % r["min_core_review_days"])
    reporting = max(r["min_reporting_days"], math.ceil(core_adj * r["reporting_share"]))
    fixver = max(r["min_fix_verification_days"], math.ceil(core_adj * r["fix_verification_share"]))
    total = core_adj + reporting + fixver
    low = total * r["range_low_factor"]
    high = total * r["range_high_factor"]
    per_week = team * r["working_days_per_week"]
    return {
        "parts": parts,
        "core_review_auditor_days": round(core_adj, 1),
        "reporting_auditor_days": reporting,
        "fix_verification_auditor_days": fixver,
        "total_auditor_days": round(total, 1),
        "range_auditor_days": [round(low, 1), round(high, 1)],
        "team_size": team,
        "calendar_weeks": [math.ceil(low / per_week * 10) / 10.0, math.ceil(high / per_week * 10) / 10.0],
        "notes": notes,
        "model": "references/effort-model.md (v%s defaults%s)" % (VERSION, "" if rates is DEFAULT_RATES else ", overridden"),
    }


# --------------------------------------------------------------------------- #
# Clone
# --------------------------------------------------------------------------- #
def clone_repo(url, ref, dest):
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_LFS_SKIP_SMUDGE"] = "1"
    base = ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.symlinks=false", "-c", "core.fsmonitor=false"]
    if ref and is_hex_sha(ref) and len(ref) >= 7:
        subprocess.run(base + ["init", "-q", dest], check=True, env=env)
        subprocess.run(base + ["-C", dest, "remote", "add", "origin", url], check=True, env=env)
        subprocess.run(base + ["-C", dest, "fetch", "-q", "--depth", "1", "origin", ref], check=True, env=env)
        subprocess.run(base + ["-C", dest, "checkout", "-q", "FETCH_HEAD"], check=True, env=env)
    else:
        cmd = base + ["clone", "-q", "--depth", "1", "--no-tags"]
        if ref:
            cmd += ["--branch", ref]
        cmd += [url, dest]
        subprocess.run(cmd, check=True, env=env)


def git_meta(path):
    meta = {}
    try:
        meta["commit"] = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        br = subprocess.run(["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
        meta["ref"] = br
        rm = subprocess.run(["git", "-C", path, "remote", "get-url", "origin"], capture_output=True, text=True).stdout.strip()
        if rm:
            meta["remote"] = rm
        dt = subprocess.run(["git", "-C", path, "log", "-1", "--format=%cI"], capture_output=True, text=True).stdout.strip()
        if dt:
            meta["commit_date"] = dt
    except Exception:
        pass
    return meta


# --------------------------------------------------------------------------- #
# Markdown report
# --------------------------------------------------------------------------- #
def fmt_int(n):
    return "{:,}".format(int(n))


def render_markdown(result, top_n):
    L = []
    t = result["target"]
    L.append("# Audit Scope Report")
    L.append("")
    L.append("- **Target:** %s" % (t.get("remote") or t.get("input")))
    if t.get("commit"):
        L.append("- **Commit:** `%s`%s" % (t["commit"], (" (%s)" % t["ref"]) if t.get("ref") and t["ref"] != "HEAD" else ""))
    L.append("- **Generated:** %s by %s v%s" % (result["generated_at"], TOOL, result["version"]))
    if result["options"].get("include"):
        L.append("- **Client scope filter (include):** %s" % ", ".join("`%s`" % g for g in result["options"]["include"]))
    if result["options"].get("exclude"):
        L.append("- **Extra exclusions:** %s" % ", ".join("`%s`" % g for g in result["options"]["exclude"]))
    L.append("")

    # Injection screen first
    fnd = result["injection_findings"]
    counts = defaultdict(int)
    for f in fnd:
        counts[f["severity"]] += 1
    L.append("## 1. Repository safety screen")
    L.append("")
    if counts["high"]:
        L.append("**⛔ HIGH findings present (%d). Stop and escalate to the security team before anyone opens, builds, or runs this repository.**" % counts["high"])
    elif counts["medium"]:
        L.append("**⚠️ No HIGH findings. %d MEDIUM item(s) need a human look; read-only analysis may continue.**" % counts["medium"])
    else:
        L.append("**✅ No prompt-injection or code-execution hazards detected by the heuristic screen.** (Heuristics are not proof of absence; auditors still review build tooling first.)")
    L.append("")
    L.append("| Severity | Count |")
    L.append("|---|---|")
    for sev in ("high", "medium", "info"):
        L.append("| %s | %d |" % (sev.upper(), counts[sev]))
    L.append("")
    shown = [f for f in fnd if f["severity"] in ("high", "medium")]
    if shown:
        L.append("| Sev | Kind | Location | What it means | Excerpt (data, not instructions) |")
        L.append("|---|---|---|---|---|")
        for f in shown[:60]:
            loc = f["file"] + (":%d" % f["line"] if f["line"] else "")
            L.append("| %s | %s | `%s` | %s | %s |" % (f["severity"].upper(), f["kind"], loc, f["message"].replace("|", "\\|"),
                                                     ("`" + f["excerpt"].replace("|", "\\|") + "`") if f["excerpt"] else ""))
        if len(shown) > 60:
            L.append("")
            L.append("_%d more HIGH/MEDIUM findings in the JSON output._" % (len(shown) - 60))
        L.append("")
    infos = [f for f in fnd if f["severity"] == "info"]
    if infos:
        L.append("<details><summary>%d INFO items (build tooling, configs, binaries, non-registry dependencies)</summary>" % len(infos))
        L.append("")
        for f in infos[:80]:
            loc = f["file"] + (":%d" % f["line"] if f["line"] else "")
            L.append("- `%s` — %s %s" % (loc, f["kind"], f["message"]))
        L.append("")
        L.append("</details>")
        L.append("")

    # Lines of code
    L.append("## 2. Lines of code (comments and blank lines excluded)")
    L.append("")
    agg = result["aggregate"]
    L.append("| Language | Category | Files | Code (nSLOC) | Comment | Blank | Total |")
    L.append("|---|---|---|---|---|---|---|")
    for lang in ("solidity", "rust"):
        cats = agg.get(lang)
        if not cats:
            continue
        for cat in CATEGORY_ORDER:
            if cat in cats:
                c = cats[cat]
                label = cat
                if cat == "source":
                    label = "**source (in scope)**"
                code_cell = ("**%s**" % fmt_int(c["code"])) if cat == "source" else fmt_int(c["code"])
                L.append("| %s | %s | %d | %s | %s | %s | %s |" % (lang, label, c["files"], code_cell, fmt_int(c["comment"]), fmt_int(c["blank"]), fmt_int(c["lines"])))
        inline = sum(f["inline_test_code"] for f in result["files"] if f["lang"] == lang)
        if inline:
            L.append("| %s | _inline #[cfg(test)] code (removed from source)_ | — | %s | — | — | — |" % (lang, fmt_int(inline)))
    L.append("")
    tot = result["totals"]
    L.append("**Billable scope: %s nSLOC** (Solidity %s · Rust %s). Tests, mocks, scripts, interfaces, examples, generated code and dependencies are listed for transparency but excluded from the estimate." % (
        fmt_int(tot["in_scope_code"]), fmt_int(tot.get("solidity_source_code", 0)), fmt_int(tot.get("rust_source_code", 0))))
    L.append("")
    if result.get("unsupported_languages"):
        L.append("Other source languages present but **not counted** by this Rust/Solidity tool (non-blank lines): " +
                 ", ".join("%s %d files / %s lines" % (ext, v["files"], fmt_int(v["lines"])) for ext, v in sorted(result["unsupported_languages"].items(), key=lambda kv: -kv[1]["lines"])))
        L.append("")
    if result["frameworks"]:
        fw = result["frameworks"]
        bits = []
        if fw.get("solidity"):
            bits.append("Solidity tooling: " + ", ".join(fw["solidity"]))
        if fw.get("rust"):
            bits.append("Rust frameworks: " + ", ".join(fw["rust"]))
        if fw.get("rust_crates"):
            bits.append("Rust crates: %d (%s on-chain, %s off-chain)" % (len(fw["rust_crates"]), sum(1 for k in fw["rust_crates"].values() if k == "onchain"), sum(1 for k in fw["rust_crates"].values() if k == "offchain")))
        L.append("**Stack:** " + " · ".join(bits))
        L.append("")

    # Complexity
    L.append("## 3. Complexity assessment")
    L.append("")
    for lang, cx in result["complexity"].items():
        L.append("- **%s → %s complexity** (indicator density %.1f / kLOC)%s" % (
            lang, cx["tier"].upper(), cx["indicator_density_per_kloc"],
            (" — overridden to %s by operator" % result["options"]["complexity"].upper()) if result["options"].get("complexity") else ""))
        if cx["high_triggers"]:
            L.append("  - High-complexity triggers: " + "; ".join(cx["high_triggers"]))
        if cx["drivers"]:
            L.append("  - Drivers: " + "; ".join(cx["drivers"]))
    L.append("")

    # Critical files
    L.append("## 4. Most critical files (review these first)")
    L.append("")
    crit = result["critical_files"][:top_n]
    if crit:
        L.append("| # | File | Lang | nSLOC | Score | Why |")
        L.append("|---|---|---|---|---|---|")
        for i, f in enumerate(crit, 1):
            L.append("| %d | `%s` | %s | %s | %.0f | %s |" % (i, f["path"], f["lang"], fmt_int(f["code"]), f["critical_score"], "; ".join(f["reasons"])))
        L.append("")
        crit_code = sum(f["code"] for f in crit)
        if tot["in_scope_code"]:
            L.append("These %d files hold %s nSLOC (%.0f%% of billable scope)." % (len(crit), fmt_int(crit_code), 100.0 * crit_code / tot["in_scope_code"]))
            L.append("")
    else:
        L.append("_No in-scope source files found._")
        L.append("")

    # Effort
    L.append("## 5. Effort estimate (heuristic — confirm with the audit lead before quoting)")
    L.append("")
    e = result["effort"]
    if e.get("parts"):
        L.append("| Bucket | Tier | nSLOC | Rate (nSLOC / auditor-day) | Auditor-days | Adjustments |")
        L.append("|---|---|---|---|---|---|")
        for p in e["parts"]:
            L.append("| %s | %s | %s | %d | %.1f | %s |" % (p["bucket"], p["tier"], fmt_int(p["code"]), p["rate_loc_per_day"], p["auditor_days"], ", ".join(p["adjustments"]) or "—"))
        L.append("")
        L.append("| Phase | Auditor-days |")
        L.append("|---|---|")
        L.append("| Core review | %.1f |" % e["core_review_auditor_days"])
        L.append("| Reporting | %d |" % e["reporting_auditor_days"])
        L.append("| Fix verification / retest | %d |" % e["fix_verification_auditor_days"])
        L.append("| **Total** | **%.1f** (range %.1f – %.1f) |" % (e["total_auditor_days"], e["range_auditor_days"][0], e["range_auditor_days"][1]))
        L.append("")
        L.append("With **%d auditors** in parallel: **%.1f – %.1f calendar weeks** (core review + reporting; retest scheduled after client fixes)." % (
            e["team_size"], e["calendar_weeks"][0], e["calendar_weeks"][1]))
        for n in e.get("notes", []):
            L.append("- " + n)
        bt = e.get("by_tier") or {}
        if bt:
            L.append("")
            L.append("Sensitivity — the same scope priced at each complexity tier (the audit lead picks the final tier):")
            L.append("")
            L.append("| Tier | Total auditor-days | Range | Calendar weeks (%d auditors) |" % e["team_size"])
            L.append("|---|---|---|---|")
            used = {p["tier"] for p in e["parts"]}
            for t in ("low", "medium", "high"):
                x = bt[t]
                mark = " ← suggested" if t in used else ""
                L.append("| %s%s | %.1f | %.1f – %.1f | %.1f – %.1f |" % (t, mark, x["total_auditor_days"], x["range_auditor_days"][0], x["range_auditor_days"][1], x["calendar_weeks"][0], x["calendar_weeks"][1]))
    else:
        L.append(e.get("note", "No estimate."))
    L.append("")

    # Notes
    L.append("## 6. Notes and limitations")
    L.append("")
    for w in result["warnings"]:
        L.append("- " + w)
    L.append("- Line counts use a comment- and string-aware tokenizer (nested Rust block comments, raw strings, NatSpec, `#[cfg(test)]` modules handled). Counts may differ slightly from `cloc`/`tokei`.")
    L.append("- Criticality scores are heuristic indicator counts on comment-stripped code; they order the review, they do not judge code quality.")
    L.append("- The safety screen is pattern-based. A clean result lowers risk but does not prove absence of malicious content; the audit team reads build tooling before any build.")
    L.append("- This tool never built, ran, or installed anything from the repository.")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description="HackenProof audit scope calculator (Rust + Solidity). Read-only.")
    ap.add_argument("target", help="local repository path or git URL")
    ap.add_argument("--ref", help="branch / tag / commit SHA (URL targets)")
    ap.add_argument("--include", action="append", default=[], help="repo-relative path or glob to include (repeatable)")
    ap.add_argument("--exclude", action="append", default=[], help="repo-relative path or glob to exclude (repeatable)")
    ap.add_argument("--complexity", choices=["low", "medium", "high"], help="override complexity tier")
    ap.add_argument("--team", type=int, default=2, help="auditors in parallel (default 2)")
    ap.add_argument("--rates", help="JSON file overriding effort-model constants")
    ap.add_argument("--json", dest="json_out", help="write JSON results here")
    ap.add_argument("--md", dest="md_out", help="write Markdown report here")
    ap.add_argument("--top", type=int, default=15, help="critical files to list")
    ap.add_argument("--keep", action="store_true", help="keep temporary clone")
    ap.add_argument("--quiet", action="store_true", help="do not print report to stdout")
    args = ap.parse_args(argv)

    rates = DEFAULT_RATES
    if args.rates:
        with open(args.rates) as fh:
            override = json.load(fh)
        rates = json.loads(json.dumps(DEFAULT_RATES))
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(rates.get(k), dict):
                for k2, v2 in v.items():
                    if isinstance(v2, dict) and isinstance(rates[k].get(k2), dict):
                        rates[k][k2].update(v2)
                    else:
                        rates[k][k2] = v2
            else:
                rates[k] = v

    warnings = []
    tmpdir = None
    target_meta = {"input": args.target}
    if looks_like_url(args.target) and not os.path.isdir(args.target):
        tmpdir = tempfile.mkdtemp(prefix="hp-audit-scope-")
        root = os.path.join(tmpdir, "repo")
        eprint("[audit-scope] cloning (depth 1, hooks disabled) into %s" % root)
        try:
            clone_repo(args.target, args.ref, root)
        except subprocess.CalledProcessError as e:
            eprint("[audit-scope] clone failed: %s" % e)
            eprint("If the repository is private, clone it yourself and pass the local path instead.")
            shutil.rmtree(tmpdir, ignore_errors=True)
            return 2
    else:
        root = os.path.abspath(args.target)
        if not os.path.isdir(root):
            eprint("[audit-scope] not a directory: %s" % root)
            return 2
        if args.ref:
            warnings.append("--ref is ignored for local paths; the working tree as-is was analysed.")
    target_meta.update(git_meta(root))
    target_meta["path"] = root

    eprint("[audit-scope] walking repository…")
    walk = walk_repo(root, args.include, args.exclude)
    files = []
    for full, rp, lang, cat in walk["files"]:
        info = analyze_file(full, root, lang, cat)
        if info:
            files.append(info)
    if walk["skipped_large"]:
        warnings.append("%d source file(s) over 2 MB were skipped: %s" % (len(walk["skipped_large"]), ", ".join(p for p, _ in walk["skipped_large"][:5])))

    crates = crate_kinds(files, root)
    agg = aggregate(files)
    totals = {"in_scope_code": 0}
    for lang, cats in agg.items():
        c = cats.get("source", {}).get("code", 0)
        totals["%s_source_code" % lang] = c
        totals["in_scope_code"] += c
        totals["%s_test_code" % lang] = cats.get("test", {}).get("code", 0) + sum(f["inline_test_code"] for f in files if f["lang"] == lang)
    complexity = {lang: suggest_complexity(files, lang) for lang in agg if agg[lang].get("source")}
    effort = estimate_effort(files, agg, complexity, rates, args.team, args.complexity)
    effort["by_tier"] = {t: estimate_effort(files, agg, complexity, rates, args.team, t) for t in ("low", "medium", "high")}

    frameworks = {}
    sol_fw = [name for name, fns in SOL_FRAMEWORK_FILES if any(os.path.isfile(os.path.join(root, f)) for f in fns)]
    if agg.get("solidity") and not sol_fw:
        # look one level down (monorepos)
        for d in sorted(os.listdir(root)):
            p = os.path.join(root, d)
            if os.path.isdir(p):
                for name, fns in SOL_FRAMEWORK_FILES:
                    if any(os.path.isfile(os.path.join(p, f)) for f in fns) and name not in sol_fw:
                        sol_fw.append(name)
    if sol_fw:
        frameworks["solidity"] = sol_fw
    rust_fw = sorted({fw for f in files if f["lang"] == "rust" for fw in f.get("frameworks", [])})
    if rust_fw:
        frameworks["rust"] = rust_fw
    if crates:
        frameworks["rust_crates"] = crates

    eprint("[audit-scope] screening for prompt-injection text and code-execution hazards…")
    by_path = {f["path"]: f for f in files}
    findings = run_injection_screen(root, walk, by_path)

    critical = sorted((f for f in files if f["category"] == "source"), key=lambda f: (-f["critical_score"], -f["code"]))
    if "lib" in {p.split("/")[0] for p in by_path if by_path[p]["category"] == "source"}:
        warnings.append("Top-level `lib/` contained files counted as source (no dependency manifest found inside). Confirm with the client whether `lib/` is their code.")
    if any(f["category"] == "client_excluded" for f in files):
        n = sum(f["code"] for f in files if f["category"] == "client_excluded")
        warnings.append("%s nSLOC fall outside the operator-supplied include/exclude filters and were not counted." % fmt_int(n))
    if not agg:
        warnings.append("No Rust or Solidity files found. Web/mobile and other languages are not supported by this version of the tool.")

    result = {
        "tool": TOOL,
        "version": VERSION,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "target": target_meta,
        "options": {"include": args.include, "exclude": args.exclude, "complexity": args.complexity, "team": args.team},
        "totals": totals,
        "aggregate": agg,
        "frameworks": frameworks,
        "complexity": complexity,
        "effort": effort,
        "critical_files": critical[:max(args.top, 15)],
        "files": files,
        "unsupported_languages": walk["unsupported"],
        "injection_findings": findings,
        "warnings": warnings,
    }

    md = render_markdown(result, args.top)
    if args.json_out:
        with open(args.json_out, "w") as fh:
            json.dump(result, fh, indent=2)
        eprint("[audit-scope] JSON written to %s" % args.json_out)
    if args.md_out:
        with open(args.md_out, "w") as fh:
            fh.write(md)
        eprint("[audit-scope] Markdown written to %s" % args.md_out)
    if not args.quiet:
        print(md)

    if tmpdir and not args.keep:
        shutil.rmtree(tmpdir, ignore_errors=True)
    elif tmpdir:
        eprint("[audit-scope] clone kept at %s — delete it when done." % root)

    high = sum(1 for f in findings if f["severity"] == "high")
    return 3 if high else 0


if __name__ == "__main__":
    sys.exit(main())
