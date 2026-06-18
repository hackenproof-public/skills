# Triage Mistakes — Shared Base

Accumulated mistakes from real triage sessions. Read before every session. Apply silently.

---

## EVIDENCE MISTAKES

### Accepting self-grading PoC harness as execution proof
A reporter submits a Puppeteer/automation script that drives both windows, writes its own output JSON (`"verdict":"confirmed"`, `checks:true`), and presents that output as evidence. The harness graded itself — no independent observable artifact exists.
**Fix:** For any XSS or JS-execution claim, require an independently observable artifact on the real origin: a video or screenshot of `alert(document.domain)` rendering via the real delivery path. "Bug exists in code" + "harness confirms" = Need More Info.

### Dismissing a verified on-chain PoC because the amount was small
Argued a mainnet-confirmed transaction (tiny amount, self-directed) "doesn't establish real impact." A small or self-directed amount is the responsible way to test — it does not reduce validity. If the mechanism is demonstrated on-chain, the amount is irrelevant.
**Fix:** Never use "small amount" or "self-transfer" to downgrade a confirmed on-chain PoC. Judge the mechanism, not the demonstrated value.

### Accepting cache poisoning without second-user confirmation
Accepted a cache poisoning report based on reporter's own response reflecting the injected parameter + a CloudFront `age` header. Neither proves the poisoned response was served to another user.
**Fix:** Cache poisoning requires a second request from a clean browser session or different IP confirming the poisoned response was globally cached.

### Accepting HTTP 200 as proof of state change
A PATCH request with empty body returned `200 {"data":null,"success":true}`. Treated as confirmed IDOR. Null data = no change occurred, the server processed it as a no-op.
**Fix:** 200 + null/empty response body = no-op. Always verify state before/after and check what was actually written.

### Accepting balance difference as fund theft
Reporter showed ETH balance difference after concurrent requests on testnet. Balance differences on testnet can be gas fees, not stolen funds.
**Fix:** Balance difference ≠ unauthorized transfer. Require destination account receipt, txhash showing funds arrived, and before/after on both sender and receiver.

### Forming severity opinion before verifying live
Read the description, formed a severity opinion, then checked the live endpoint — or never checked at all.
**Fix:** Verify live first. curl the endpoint, look up on-chain, check the repo. No opinion before verification is done.

### Never reading PoC attachments
Attachments were available but never fetched. Would have seen fabricated output in the first five lines.
**Fix:** Fetch all attachments before any analysis. Step one, always.

### Conflating evidence between reports
Attributed victim-side verification from one report to a different report with zero attachments.
**Fix:** Each report's evidence is strictly isolated. Never carry confirmation from one report to another.

### Not checking credential/key validity before proposing severity
Proposed High for an exposed TLS private key without verifying if the certificate was still active. It had expired — no exploitable impact.
**Fix:** For any credential or key exposure, verify it is still active and check expiry before proposing severity.

### Accepting AI-generated batch reports at face value
A reporter submitted four reports on the same day with identical structure: detailed file:line citations, local test harnesses, no live production crash demonstrated. Accepted without running the PoC.
**Fix:** Same reporter + same day + identical structure = AI-assisted scanning flag. Download and run the PoC before forming any opinion. Do not reject the whole batch blindly — verify each claim individually.

---

## DECISION MISTAKES

### Backing down on assessments without new facts
Changed a severity assessment the moment someone asked "why?" or "are you sure?" — no new factual information, just a question.
**Fix:** Explain reasoning clearly and hold the position. Changing opinion requires new facts or a factual counter, not just a question.

### Dup search with too-specific queries
Searched for multi-word mutation names — zero results. The existing report used completely different wording.
**Fix:** Search with 1-2 broad words. Then read results to find root-cause matches. Never copy-paste mutation names or function names into the search.

### Dup label ≠ correct anchor
Reports were labeled dup-X. Their actual root cause matched a different anchor with a different state. Applied wrong closure.
**Fix:** Always read the anchor report content, not just its state. Label + state ≠ same root cause. Verify content matches before closing.

### N/A when OOS is correct
Closed as N/A because a claimed code element didn't exist. The correct close was OOS (CLI is out of scope) — N/A is for findings that are not real vulnerabilities, OOS is for valid findings outside the program's scope.
**Fix:** N/A = not a vulnerability (fabricated, wrong). OOS = valid finding but outside program scope. These are different.

### Not checking scope before severity analysis
Spent analysis time on a finding before verifying the affected asset was in scope. It wasn't.
**Fix:** Scope check is step one before any analysis. If OOS → done.

### Pattern-matching vulnerability names to severity
Called "privilege escalation" → High without asking who the attacker is, what access they already have, and what they actually gain. The attacker was already an authenticated admin — OOS.
**Fix:** For any "privilege escalation" finding: who is the attacker, what is their starting access, what do they actually gain? Admin-to-admin boundary = OOS at most.

### Self-spoofing mistaken for cross-user impact
Reporter claimed "separate authenticated session was updated" — both sessions were the reporter's own.
**Fix:** When cross-user impact is claimed, verify who controlled the victim session. Same person = self-spoofing = N/A.

### Accepting reporter's self-assessed severity
Multiple reports self-labeled Critical. Analysis time was biased toward treating them as potentially Critical without independent assessment.
**Fix:** Reporter severity is irrelevant. Assess independently from the code and the program's definition of Critical.

### Crediting appeal argument quality without new facts
Recommended reopening a closure based on the quality of the reporter's reframing — without checking whether prior reports covered the same finding or tracing actual reachability.
**Fix:** Before crediting any appeal: (a) search for prior reports of the same class — precedent is binding; (b) trace reachability end-to-end; (c) read the attached PoC and check whether it proves the headline claim or quietly weakens it. A well-written appeal is not new evidence.

### Not searching cross-program precedent for new vulnerability classes
Decided on a new vulnerability class without first searching how it was handled across other programs. Cross-program search found consistent OOS/N/A decisions already in place.
**Fix:** Before deciding on an unfamiliar vulnerability class, search for it across programs. The precedent is usually already there.

---

## COMMENT MISTAKES

### Writing brief generic comments
Posted 1-2 sentence comments just stating the decision with no explanation.
**Fix:** Every comment must explain which specific rule was violated, what evidence was missing, and what would be needed to resubmit.

### Wrong reputation line on N/A closures
Wrote "this does not affect your reputation score" on a N/A closure. N/A = -5 rep.
**Fix:** Only write "does not affect your reputation score" on OOS (0 rep). Never on N/A, Invalid, or Spam.

### Referencing other report IDs in public comments
Wrote "previously reported as REPORT-123" — reporters cannot see other reports.
**Fix:** Never reference report IDs in comments. Explain the issue in standalone terms.

### Generic dup comment mismatched to report content
Applied a bulk comment about a different issue to reports that described something else. Reporters called it out.
**Fix:** Every comment — even for dup reports — must reference the specific finding from that report. Never copy-paste generic reason lists.

### Posting factually wrong statements
Stated a code element "does not exist in the codebase" without verifying. Reporter proved it wrong with exact file:line references.
**Fix:** Verify every factual claim before writing it. "I checked X and found Y" — actually check X first.

### Comment quality degradation during batch work
Started strong with detailed comments, progressively shortened them as the batch grew.
**Fix:** Comment quality does not drop during batch work. Every comment must explain the specific code location, the decision reasoning, and what would change it.

---

## WORKFLOW MISTAKES

### Applying actions without explicit confirmation
Applied triage state changes immediately after forming decisions without presenting the plan and waiting for approval.
**Fix:** Present the full ordered list → wait for explicit confirmation → then apply. No exceptions for write actions.

### Batch-closing dup clusters without reading report content
Closed entire dup clusters with one generic comment. Several reports described different angles than the primary — they received wrong comments posted publicly.
**Fix:** Read every report's vulnerability description before closing. Confirm root cause matches the primary. Never bulk-close a dup cluster without per-report content check.

### Checking state before batch close
Tried to close reports that the client had already transitioned.
**Fix:** Call list_reports immediately before any batch close to catch state changes made by others.

### Setting state to Triaged automatically
Changed high-severity reports to Triaged state without being asked.
**Fix:** Never set state to Triaged. Only the program manager transitions reports to Triaged manually. Use: Informative, Out of scope, Not applicable, Duplicate, Spam.

### Re-rating an already-decided cluster
Came into a new session and re-analyzed a cluster that had already been triaged and aligned with the client. Contradicted a settled call.
**Fix:** Before forming any opinion on a report, check prior decisions (past sessions, client communication, decision logs). If already adjudicated, mirror it — don't re-litigate.

### Trusting dup labels without verifying content
Closed dup-labeled reports based on the label alone. Four labels were wrong — different mechanism than the claimed primary.
**Fix:** For every dup, fetch both the candidate and the claimed original and confirm root cause matches by content.

---

## PATTERN MISTAKES

### CORS wildcard + credentials = invalid combination
Accepted "CORS misconfiguration with credentials" where the server returned `Access-Control-Allow-Origin: *` AND `Access-Control-Allow-Credentials: true`. This combination is explicitly prohibited by the Fetch specification — browsers reject credentialed requests to wildcard origins.
**Fix:** When ACAO is `*`, credentials cannot be sent cross-origin. Don't accept CORS+credentials claims without a working browser PoC showing actual authenticated response data.

### Accepting curl as CORS browser exploit proof
curl showing `Access-Control-Allow-Credentials: true` with arbitrary origin reflected — accepted as exploitable. curl has no cookie jar.
**Fix:** For CORS credential attacks require: browser-based PoC on real external domain + session cookie sent cross-origin shown in DevTools Network tab + authenticated data in response.

### Foundry fork test accepted as valid SC PoC
Approved a finding because `forge test --fork-url` passed. No on-chain state change, no txhash.
**Fix:** Foundry fork test = local simulation = same class as mocked unit test. Require testnet/mainnet txhash.

### Localhost CORS PoC where attacker = victim machine
Reporter tested "cross-origin CORS" with both attacker and victim ports on 127.0.0.1. Modern browsers block real cross-origin requests to localhost.
**Fix:** If attacker and victim are on the same machine → OOS. Require attacker on external domain.

### DevTools button-enabling as security bypass
Reporter enabled a disabled button via browser DevTools, claimed the resulting crash was exploitable.
**Fix:** DevTools DOM manipulation is a local modification to the reporter's own browser — not an external attack path. DevTools-enabled UI bypass + crash = N/A. Require actual signing/transaction broadcast + txhash.

### Treating PoC bash script as UI vulnerability proof
Reporter provided a bash script calling RPC methods directly. Presented as proof the UI accepts malicious inputs.
**Fix:** For web UI vulnerability claims, the only valid PoC is a screen recording or screenshot of the actual browser UI sending the malicious transaction to the wallet for signing. Direct RPC calls prove nothing about the UI.
