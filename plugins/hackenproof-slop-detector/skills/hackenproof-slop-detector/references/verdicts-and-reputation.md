# Verdicts and Reputation

Five verdicts per citation. Only one of them can support a penalty.

| Verdict | Meaning |
|---|---|
| `verified` | The cited thing is there, as cited. |
| `verified-with-drift` | It is there; the path, line, or a value is written wrongly. |
| `citation-without-commit` | Checkable in principle, pinned to nothing — "defaultbranch", a bare version, no commit. |
| `unresolvable` | The check could not run: no commit established, provider down, rate limit, pruned ledger, unknown installed version. |
| `contradicted` | The source was reached and does not contain what was cited. |

`unresolvable` and `contradicted` are the pair that matters. The first means *we could not look*, the
second means *we looked and it is not there*. Collapsing them is the failure this skill exists to
prevent.

---

## Prose-PoC screen

The fourth check from the issue, and the only one needing no external source.

A PoC is prose when the submission describes what an attacker would observe rather than showing what
the reporter observed: no pasted response, no real identifier, no attachment, no log line, no
transaction — every specific-looking element a placeholder, a hypothetical, or a narrated result with
the result withheld.

This is the same test `hackenproof-report-quality-scorer` applies as its observed-value rule. Where
that skill is available, defer to it rather than reimplementing the judgement, and carry its result
through as one line here. Prose-PoC is **never** a fabrication finding on its own — a thin report is
thin, and thin is not dishonest.

## Reputation mapping

The programme's scale: Invalid −5 · Spam −20 · Out of scope 0 · Duplicate and Informational +2.
Penalties are for clearly bad or spammy submissions, not for weak ones.

**Nothing here decides a penalty. It supplies the evidence a human decides on.**

| Situation | What the evidence supports |
|---|---|
| Every citation `verified`, some `verified-with-drift` | No penalty. A good report with citation hygiene problems. |
| Any `unresolvable` | No penalty, whatever else is present. The check did not run. |
| One or two `contradicted` among many `verified` | No penalty. Transcription errors. Worth a Need-more-info asking them to correct the citations. |
| `contradicted` on the claim the finding rests on — the cited code is absent from the tree, or the transaction's stated effect is absent from a transaction the node does hold | Supports Invalid (−5). State the receipts. |
| Every substantive citation `contradicted`, plus `structurally-invalid` hashes or a non-existent CVE, plus a prose PoC | Supports Spam (−20). This is the only combination that does. |

Requirements before any penalty is proposed:

1. The resolution step ran — basename search, tag dereference, ±30-line quote search, provider fallbacks. Its result is in the output.
2. The receipts are printed. A penalty proposal without the commands that produced it is not evidence.
3. No `unresolvable` verdict is sitting in the same report on a load-bearing claim.

A penalty is close to irreversible from the researcher's side. Where the evidence is mixed, propose
no penalty and say what would settle it.

## Output shape

```
# Citation Check — {PROG-N}

Commit checked: {sha}  ({how it was established})
Looked up on:   {YYYY-MM-DD}
Target type:    {github_repository | web_url | android | ios}
{Code checks not applicable — target is {type}.}

| Cited | Verdict | Detail | Command |
|---|---|---|---|
| `path.ts:61-66` | verified | quote matches at 61-66 | `gh api …contents/…?ref=…` |
| `configs/vite/x.ts` | verified-with-drift | real path `packages/extension/configs/vite/x.ts` | `grep -i /x.ts$ tree.txt` |
| `CVE-2099-99999` | contradicted | NVD totalResults=0 | `curl …?cveId=…` |
| `3TNNto2…xY61` | pruned-inconclusive | slot predates window 441633334→442113302 (~2.2d) | `getTransaction` + `getFirstAvailableBlock` |

PoC form: {evidence | prose — no observed value}

## Reputation evidence

{one of the rows from the mapping, with the citations it rests on}
{"No penalty supported." where that is the answer}
```

Keep the `Commit checked` and `Looked up on` lines in every run. A citation check without them cannot
be reproduced, which makes it worth nothing at the moment someone disputes it.
