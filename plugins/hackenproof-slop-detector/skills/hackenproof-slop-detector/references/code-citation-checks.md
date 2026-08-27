# Code Citation Checks

Every check below was run against live reports before being written down. No clone: repositories
in scope reach several gigabytes, and `contents?ref=` returns single files.

Fetch the tree once per commit and reuse it:

```bash
gh api "repos/{owner}/{repo}/git/trees/{commit}?recursive=1" --jq '.tree[].path' > /tmp/tree.txt
```

---

## C0 — Establish the commit

A version string is not a commit, and a tag ref is not a commit either.

```bash
# a version the report gives, e.g. v2.18.0
REF=$(gh api repos/{owner}/{repo}/git/ref/tags/v2.18.0 --jq '.object.sha')
TYPE=$(gh api repos/{owner}/{repo}/git/ref/tags/v2.18.0 --jq '.object.type')
# annotated tag → one more hop to reach the commit
[ "$TYPE" = "tag" ] && COMMIT=$(gh api repos/{owner}/{repo}/git/tags/$REF --jq '.object.sha') || COMMIT=$REF
```

**Skipping the second hop produces a false accusation.** On a live report the tag ref returned
`e32a16bf…` while the commit was `b9ba8025…`; dereferenced, it matched the reporter's citation
exactly. A naive comparison would have reported a fabricated version against a correct report.

Confirm the relationship rather than assuming it:

```bash
gh api "repos/{owner}/{repo}/compare/$CLAIMED...$COMMIT" --jq '"\(.status) ahead=\(.ahead_by) behind=\(.behind_by)"'
# identical | ahead | behind | diverged
```

A commit that exists but is `diverged` from the in-scope release is a real finding: the code was
read somewhere the programme does not cover.

## C1 — Path exists

```bash
gh api "repos/{owner}/{repo}/contents/{path}?ref={commit}" --jq '.path'
```

On 404, resolve before reporting:

```bash
grep -i "/$(basename {path})$" /tmp/tree.txt
```

- Path resolves as written → continue to C2.
- Basename found elsewhere → **`path-drift`**. Record both paths and continue checking the claim at
  the resolved path. A live report cited `configs/vite/transform-manifest.ts`, which 404s, while
  `packages/extension/configs/vite/transform-manifest.ts` exists and contains what was claimed.
- Basename found nowhere in the tree → **`contradicted`**. State that the tree was searched by
  basename at this commit and returned nothing.

## C2 — Line or range holds the quoted code

```bash
gh api -H "Accept: application/vnd.github.raw" \
  "repos/{owner}/{repo}/contents/{path}?ref={commit}" | sed -n '{start},{end}p'
```

Compare against the report's quote, ignoring indentation and trailing commas.

- Quote sits at the cited lines → **`verified`**. Confirmed on a live report: lines 61-66 matched
  the quoted block exactly.
- Quote sits within ±30 lines of the citation → **`verified-with-drift`**, naming the true line.
  Also confirmed live: a 62-74 citation whose quote began at 67, with 62-66 holding a neighbouring
  function the reporter never quoted.
- Quote is in the file but far outside the range → **`verified-with-drift`**, flagged as a large
  offset, since a wildly wrong line number suggests the citation was not taken from this commit.
- Quote is not in the file at all → **`contradicted`**.
- Line number exceeds the file length → **`contradicted`**, stating the file's real length.

A cited line that exists but holds different code is the sharpest signal in this file. A binary
"does line 62 exist" check passes it and learns nothing.

## C3 — Symbols exist

```bash
gh api -H "Accept: application/vnd.github.raw" \
  "repos/{owner}/{repo}/contents/{path}?ref={commit}" | grep -nE "(function|const|async|class)\s+{name}"
```

Check the property the report depends on, not merely the name. Where a report claims four methods
take no domain argument, verify the signatures — on a live report all four were confirmed at lines
14, 19, 34 and 39, which is a stronger result than "the names appear".

Symbol absent from the cited file but present elsewhere in the tree → `path-drift`, not
`contradicted`.

## C4 — Repository issues and pull requests

```bash
gh api repos/{owner}/{repo}/issues/{n} --jq '{number,title,state}'
```

Check that the report's characterisation matches the title and state. A live citation of issue #274
as "users asking to disable auto network-switching" matched
"Turn off automatic wallet / network switching", closed — accurate.

Note that the issues endpoint also resolves pull requests, so a PR number cited as an issue is not
a finding.

## C5 — Dependency and version claims

For "the project ships a vulnerable X", read what it actually ships:

```bash
gh api -H "Accept: application/vnd.github.raw" \
  "repos/{owner}/{repo}/contents/{manifest}?ref={commit}"
```

Take the version from `dependencies` / `devDependencies`, or from the lockfile where the claim
concerns the resolved version rather than the declared range. Then hand it to `advisory-checks.md`
for range comparison.

Verified live: a manifest at the cited commit declared `lodash ^4.18.1`, while both open advisories
for that package cover `<= 4.17.23` — the claim would be `contradicted` by the project's own
manifest.

State which file the version came from. A declared range and a locked version are different facts,
and a report may be right about one and wrong about the other.

## Reporting

Per citation: what was cited · verdict · resolved path or line where it differs · the command.
Always state the commit every verdict was measured against.
