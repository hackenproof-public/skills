# Advisory Checks

Two sources, different jobs. NVD answers "does this CVE exist and what product is it about". GitHub
Security Advisories answer "which versions of this package are affected", which NVD does not give in
a directly comparable form.

Record the date of every lookup. Advisories are amended, and a verdict without a date cannot be
re-checked later.

---

## A1 — Does the CVE exist

```bash
curl -s "https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2021-44228" \
 | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['totalResults'])"
```

- `totalResults` is 0 → **`contradicted`**. The identifier does not exist. Verified live against
  `CVE-2099-99999`.
- `totalResults` is 1 → continue to A2.

**Rate limits are not results.** Without an API key NVD allows roughly five requests per thirty
seconds and returns malformed output past that. A live run hit this on the first call and returned
valid data on retry. Never record a verdict from unparseable output — retry, then report
`unresolvable` if it persists.

A reserved-but-unpublished CVE returns a record with no description and no configurations. That is
`unresolvable`, not `contradicted` — the identifier was assigned, the details are embargoed.

## A2 — Is it about the right product

```bash
curl -s "https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={CVE}" | python3 -c "
import json,sys
v=json.load(sys.stdin)['vulnerabilities'][0]['cve']
print([x['value'] for x in v['descriptions'] if x['lang']=='en'][0][:200])
print(sorted({m['criteria'].split(':')[3]+':'+m['criteria'].split(':')[4]
              for c in v.get('configurations',[]) for n in c.get('nodes',[])
              for m in n.get('cpeMatch',[])}))
"
```

The CPE vendor:product list is the check. A real CVE cited for the wrong software is the most common
advisory-class slop, and it looks entirely convincing without this step. Verified live:
`CVE-2025-29927` exists and is `vercel:next.js`; cited against a wallet extension it would be
`contradicted`.

- Product matches the target or one of its dependencies → **`verified`**.
- Product is unrelated → **`contradicted`**, naming both the cited product and the real one.
- CVE has no CPE data → fall through to A3, which often does have package data.

## A3 — GitHub Security Advisories

More useful than NVD for anything with a package manifest, because it carries affected ranges.

By identifier:

```bash
gh api /advisories/GHSA-jfh8-c2jp-5v3q \
 --jq '{ghsa_id,cve_id,severity,summary,pkgs:[.vulnerabilities[].package.name]}'
```

By package, to test "is there any advisory for X at all":

```bash
gh api '/advisories?ecosystem=npm&affects=lodash&per_page=5' \
 --jq '.[]|{ghsa_id,cve_id,severity,range:[.vulnerabilities[]|select(.package.name=="lodash")|.vulnerable_version_range]}'
```

`ecosystem` takes `npm`, `pip`, `go`, `maven`, `rust`, `composer`, `nuget`, `rubygems`, `actions`,
`pub`, `swift`, `erlang`. Pick it from the manifest the version came from, not from the report.

## A4 — Version-range comparison

The step that turns an advisory into a verdict about *this* project. Take the shipped version from
`code-citation-checks.md` C5 and compare it to `vulnerable_version_range`.

```
shipped:    lodash ^4.18.1
advisories: CVE-2026-4800  high    >= 4.0.0, <= 4.17.23
            CVE-2026-2950  medium  <= 4.17.23
verdict:    contradicted — 4.18.1 is above both upper bounds
```

Verified live on a real manifest at a real commit.

Rules that keep this honest:

- Compare against what the project ships, never against the advisory's headline severity.
- A declared range (`^4.18.1`) and a locked version are different claims. Say which you used. Where
  the manifest gives a range whose lower bound falls inside the vulnerable range and no lockfile is
  present, the result is **`unresolvable`** — the installed version is genuinely unknown.
- Pre-release and build-metadata suffixes are not decided by numeric comparison. Where a version
  carries one, report `unresolvable` rather than guessing.
- An advisory withdrawn upstream (`withdrawn_at` set) supports nothing. Treat a citation of one as
  `unresolvable` and note the withdrawal.

## A5 — Recency

A published CVE younger than thirty days is out of scope for a bounty under the programme's own
rules, but that is a scope decision, not a slop finding. Record the publication date and leave the
disposition to triage. Do not fold it into a citation verdict.

## Reporting

Per identifier: cited id · exists · product or package · affected range · shipped version · verdict ·
lookup date · the command.
