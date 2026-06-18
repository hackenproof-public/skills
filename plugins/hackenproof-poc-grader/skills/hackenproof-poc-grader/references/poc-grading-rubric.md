# PoC Grading Rubric

## Verdicts

Each grading session returns exactly one of these:

- **Verified** — Tier 1 evidence. Proceed to severity analysis.
- **Plausible** — Tier 2 evidence. Lean toward lower severity until confirmed.
- **Weak** — Tier 3 or Tier 4 evidence. Set Need More Info; state exactly what is missing.
- **Invalid** — Negative signal in the Invalid Evidence list. Close as Not Applicable.
- **Out of Scope Evidence** — Negative signal in the Out of Scope Evidence list. Close as Out of Scope.

Negative signals override tier — if a negative signal matches, the verdict is Invalid or OOS Evidence regardless of tier.

## Evidence Tiers

### Tier 1 — Verified (strongest)
- On-chain mainnet transaction with txhash showing the attack
- Browser PoC on a real external domain demonstrating live data exfiltration or auth bypass
- Screen recording of full attack chain on a real production endpoint
- Video of exploit on a physical device (mobile)
- Second-user session confirmation showing cross-account impact

### Tier 2 — Plausible
- Testnet deployment with txhash + transaction explorer link
- Browser PoC on staging/test environment with real credentials
- Burp Suite capture showing server response to crafted request on live endpoint
- curl output showing live server behavior (not for XSS/CORS credential claims — those require browser)

### Tier 3 — Weak (→ Need More Info)
- Screenshots only, no video or reproduction guide
- curl showing headers or config without demonstrating actual impact
- Code review identifying a pattern without live execution
- Reproduction steps that require significant attacker prerequisites not addressed

### Tier 4 — Weak / Insufficient lab conditions (→ Need More Info)
- Localhost PoC where attacker domain is 127.0.0.1 or same machine
- Local environment only, not tested against the live application
- Missing key steps in reproduction guide
- No attachment despite claiming a demonstrated exploit
- PoC requires controlled lab conditions not replicable by a real attacker

---

## Negative Signals (override tier — apply regardless)

### → Invalid Evidence (Not Applicable)
- **Self-grading harness**: script's own JSON/console output says `"verdict":"confirmed"` or `checks:true` — the harness wrote and read its own result
- **Hardcoded success strings**: `console.log("VULNERABILITY CONFIRMED")` or `print("EXPLOIT SUCCESS")` hardcoded in test output
- **Hardhat/Foundry fork test**: `forge test --fork-url` or Hardhat local chain — no on-chain state change, no txhash; equivalent to a mocked unit test
- **Fabricated txhash**: transaction digest not found on any network (verify via fullnode RPC or explorer)
- **Code patterns cited don't exist**: reporter references file/line that doesn't exist in the actual codebase
- **Vitest/Jest mocked environment**: reporter wrote a unit test against their own mock — not the real library

### → Out of Scope Evidence
- **Localhost attacker**: both attacker and victim on `127.0.0.1` — browsers block real cross-origin requests to localhost (Private Network Access spec)
- **ADB commands**: requires USB or physical device access — OOS per mobile program rules
- **DevTools DOM manipulation**: reporter enabled a disabled button via browser DevTools — local DOM mod, not an external attack path
- **Self-spoofing**: reporter controlled both "victim" and "attacker" sessions — no cross-user impact
- **Physical device access required**: attack requires proximity or physical contact beyond standard remote exploitation
- **Static APK analysis only**: hardcoded values found via decompilation with no live credential verification or demonstrated impact

---

## Vulnerability-Class Specific Notes

### CORS / Credential Theft
- curl showing reflected origin ≠ browser exploit. Requires: browser-based PoC on real external domain + session cookie sent cross-origin shown in DevTools Network tab + authenticated response data returned
- `Access-Control-Allow-Origin: *` + `Access-Control-Allow-Credentials: true` = invalid combination by spec — browsers reject it. This "finding" is Invalid.

### XSS
- Self-grading Puppeteer harness that drives both windows = Invalid
- Requires independently observable artifact: screenshot/video of `alert(document.domain)` or `alert(document.cookie)` rendering via real delivery path

### Cache Poisoning
- Reporter's own `age` header showing cache hit = Weak. Requires second request from clean session/different IP proving poisoned response served to another user.

### Smart Contract
- Foundry fork test = Invalid (local simulation, no txhash)
- Valid: testnet deployment + txhash + video showing exploit

### On-Chain PoC
- Small or self-directed transaction amount does NOT reduce validity. A 1-unit self-transfer demonstrating the mechanism is as valid as a full drain. The minimal amount is responsible researcher conduct.

### AI-Generated Batch Reports
- Same reporter, same day, identical structure, multiple reports = AI-assisted scanning flag
- Pattern: detailed file:line citations, local test harnesses, no live production crash
- Do not reject the entire batch blindly — verify each impactful claim live. One valid finding in ten AI reports is still valid.

---

## Reputation Impact Reference
- OOS: 0 rep — mention in comment that it does not affect reputation
- Informative: +2 rep — do NOT say it won't affect reputation
- N/A: -5 rep — NEVER say it does not affect reputation
- Duplicate: +2 rep
- Spam: -20 rep
