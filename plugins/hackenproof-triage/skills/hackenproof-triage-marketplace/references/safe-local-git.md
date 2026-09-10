# Safe Local Git Reads

Gate 1 accepts a commit hash, tag, or release version taken from the report. That identifier is
submitter-authored data (see `untrusted-input-handling.md`), and two separate mechanisms can turn
it into something other than a name. Both were reproduced on Git 2.53.

- **Git option parsing.** An argument starting with `-` is read as an option even when no shell is
  involved. A single `--output=<file>` argument makes `git show` or `git log` write over the named
  file, inside or outside the repository, and truncate it even when the command then fails with
  `fatal: bad object`.
- **Shell expansion, before Git runs.** `v$(printf${IFS}W0)` is a valid ref name and passes
  `check-ref-format`. Placed in double quotes in a Bash command line, the shell rewrites it to
  `vW0`, and Git resolves whatever that names: in the test, a different commit, with exit 0 and
  empty stderr. `--end-of-options` does not help, because the substitution happened before Git
  was executed.

## Contents

- Core rule
- 1. Execution mode
- 2. Accept
- 3. Resolve
- 4. Read
- 5. Decide
- Regression cases

## Core rule

Never splice an unvalidated report identifier into shell source or a Git read command. Validate
it, resolve it to one full commit object ID, and use only that object ID for later reads. Repository path,
Git executable, environment, options, and any output path come from operator configuration, never
from report text. This procedure grants no permissions: existing host and sandbox rules still
apply. Require Git 2.45 or newer before local validation; on an older or unrecognised version,
stop and record the limitation.

Set `GIT_NO_LAZY_FETCH=1` in the trusted environment **before the first Git invocation** and
preserve it for every call: version and repository probes, ref checks, object enumeration,
commit peeling, parent inspection, and all `show`/`diff` reads. Git 2.45 introduced this variable;
older versions can ignore it silently. A peel such as `<oid>^{commit}` can fetch a missing object
before rejecting its type, so setting the variable only at the final read is too late.

## 1. Execution mode

Pass the value literally, as one argument, through a process API that takes an argument vector
and no shell. The lists in this file are argument vectors, not shell templates. This applies to
every command that touches the value, including the `check-ref-format` call in step 2.

Where a shell is the only available execution path, use one that supports literal single-quoted
arguments: validate the character set first, then place the accepted value in **single quotes**.
The accepted character set below contains nothing a shell expands and no `'` that could close the quoting, so validation is what makes the shell form safe.
Never interpolate unvalidated report text into shell source, and never expect `--end-of-options`
to undo an expansion that has already happened.

## 2. Accept

Accept exactly one nonempty identifier, in one of these shapes:

- an ASCII hexadecimal object name of 7-64 characters;
- a fully qualified ref: `refs/heads/`, `refs/tags/`, or `refs/remotes/` followed by one or more
  components;
- a tag or branch name without the `refs/` prefix, such as a release label. Validate it with
  `[git, "-C", repo, "check-ref-format", "--allow-onelevel", name]`, then use only the fully
  qualified spelling you construct (`refs/tags/<name>` and `refs/heads/<name>`), never the bare
  name; step 3 rejects a name that exists in both namespaces.

Outside the hexadecimal form, accept only the characters `A-Z`, `a-z`, `0-9`, `.`, `_`, `/`, `+`
and `-`. That set covers real tags and branches (`v1.2.3`, `1.0.0-rc1`, `release/2.1`) and
excludes shell metacharacters; the checks below also reject Git revision syntax.

Reject, before any Git call: a leading hyphen — `check-ref-format` itself reads `--output=x` as an
option — any character outside the set, `..` anywhere, a leading or trailing `/`, a component that
starts with `.` or ends in `.lock`, and a bare `HEAD`, `FETCH_HEAD`, `ORIG_HEAD`,
`MERGE_HEAD` or another name matching `[A-Z][A-Z0-9_]*` without a `refs/` prefix. Git's porcelain
refuses to create a branch or tag named `HEAD`, but `update-ref` accepts `refs/tags/HEAD`, so this check is explicit rather than
implied. Do not repair, re-spell, or guess an identifier, and never substitute a default.

## 3. Resolve

Use the environment from the core rule for every command in this section. Obtain the storage
format with `[git, "-C", repo, "rev-parse", "--show-object-format=storage"]`: require `sha1`
(40 hexadecimal characters) or `sha256` (64). Reject malformed output and unsupported formats
as a local verification failure. Every object ID below must have that exact width.

**For a hexadecimal name**, enumerate matching objects directly, without looking up refs:

```
[git, "-C", repo, "rev-parse", "--disambiguate=" + identifier.lower()]
```

The option value is constructed only after step 2 has accepted the hexadecimal form. Require
exit 0, no diagnostic on stderr, and exactly one output line containing a full hexadecimal
object ID that starts with the submitted prefix. Two or more matches mean an ambiguous
abbreviation, which is a defect in the identifier. Zero matches establish only local absence:
shallow, single-branch, partial, and simply outdated clones all lack objects that exist upstream,
and no local command separates that from an invented identifier. Unless independent evidence
establishes that the identifier is invalid, report local verification as unavailable. Never pick
the first match or filter the matches by object type to make an abbreviation appear unique. A branch or tag carrying the same
name does not participate in this lookup. Checking the prefix alone is insufficient: two objects
can share it, and a same-named branch can hide that ambiguity from ordinary `rev-parse`.

**For a ref**, validate its full spelling with `check-ref-format`, then check exact existence:

```
[git, "-C", repo, "show-ref", "--verify", "--quiet", "--end-of-options", fullref]
```

Exit 1 with no diagnostic means the exact ref is absent from this clone, which is local absence
and not evidence that the ref is wrong; any other failure or diagnostic also means local
verification is unavailable. For a name without `refs/`, check both `refs/tags/<name>` and
`refs/heads/<name>`. Require exactly one existing ref; if both exist, request the fully qualified
name instead of silently choosing a namespace. Never retry an absent full ref in another namespace.

Read the verified ref's object ID with
`[git, "-C", repo, "show-ref", "--verify", "--hash", "--end-of-options", fullref]`.
Require success, no diagnostic, and exactly one full object ID. If the ref disappears or becomes
unreadable between the two calls, stop local verification. Retain this object ID, not the ref
spelling, for the next step.

**For either input form**, peel only that full object ID to a commit:

```
[git, "-C", repo, "rev-parse", "--verify", "--end-of-options", oid + "^{commit}"]
```

Require success, no diagnostic, and exactly one full commit object ID in the storage format.
An annotated tag may peel to a different object ID. Blobs, trees, and tags pointing at them are
not commits. Unreadable or missing objects are a local verification failure; do not fetch them
as a fallback. Keep only the resulting commit object ID for later reads. The absence of a
warning does not replace any of these checks.

## 4. Read

```
[git, "--no-pager", "-C", repo, "show", "--no-ext-diff", "--no-textconv", "--end-of-options", oid, "--"]
[git, "--no-pager", "-C", repo, "diff", "--no-ext-diff", "--no-textconv", "--end-of-options", base_oid, fix_oid, "--"]
```

Resolve each endpoint of a comparison separately. Keep the trailing `--` after the revisions:
`git show -- <identifier>` treats the identifier as a pathspec and exits 0 with empty output
whether or not that commit exists, so the spelling verifies nothing (see `gitcli`).
`--no-ext-diff` and `--no-textconv` keep repository configuration from running an external program
during the read; they assume a trusted Git executable and repository, and are not a sandbox for a
hostile one.

Keep `GIT_NO_LAZY_FETCH=1` from the core rule for these reads as well. In a partial clone,
missing objects must cause a local verification failure instead of a fetch.

If the resolved commit is a merge — `show --no-patch --format=%P` prints more than one parent —
the default combined diff can omit changes that an explicit base-to-merge comparison shows.
Compare explicit endpoints instead.

## 5. Decide

Resolution establishes existence and object type only. Compare the resolved commit with program
scope from `get_program_info`; a successful Git read is not scope evidence.

Failures come in two kinds, and they do not lead to the same action:

- **The identifier is the problem** — it fails the shape checks, an abbreviation matches two or
  more objects, a short name exists as both a tag and a branch, or a resolved object is not a
  commit. These are properties of the identifier, visible without assuming the clone is complete.
  Set `Need more info` and request an exact commit.
- **Local verification is unavailable** — Git missing or older than 2.45, the configured path is
  not a repository, an object is unreadable (`error: inflate: data stream error`,
  `unable to unpack … header`), or the object or ref is absent from this clone. Absence is not
  evidence of invalidity. Record that local version verification did not run and treat the report
  as if no local repository were configured. Do not ask the reporter for a commit on those grounds
  unless independent evidence — program metadata, or an operator statement that this clone is
  complete and current — establishes that the identifier is wrong.

In both cases, do not run another command with that input, and never retry by dropping a
safeguard.

## Regression cases

Synthetic cases for this procedure. They need a scratch repository only and never contact a
program. A case passes when the identifier is rejected or resolved exactly as stated, and the guarded
commands leave fixture files unchanged and fetch no objects.

| # | Reported identifier or condition | Correct outcome |
|---|---|---|
| 1 | `--output=notes.txt` | Rejected at step 2 for the leading hyphen; never passed to Git; `Need more info`. |
| 2 | `v$(printf${IFS}W0)` | Rejected at step 2 for the character set. If a shell were used with double quotes, it would resolve a different commit with exit 0. |
| 3 | `HEAD~1` | Rejected at step 2 as revision syntax, even though Git would resolve it. |
| 4 | `abc1234..def5678` | Rejected at step 2 as a range; a comparison takes two separately resolved endpoints. |
| 5 | `HEAD`, with `refs/tags/HEAD` present in the repository | Rejected at step 2 as a pseudo-ref, even though the ref resolves. |
| 6 | An 8-character hex name that a branch also carries, with `core.warnAmbiguousRefs=false` | Object lookup ignores the branch: a unique matching object resolves; multiple matching objects are rejected, independently of warnings. |
| 7 | `refs/tags/missing`, with a branch of that exact name | The branch never stands in for the tag. The tag is absent from this clone, so report local verification as unavailable. |
| 8 | A 40-character hex name absent from the repository | Local absence only: report verification unavailable, and run no further command with that input. |
| 9 | `v1.2.3`, present as a tag | Resolve the exact `refs/tags/v1.2.3` ref, then peel its object ID; scope is checked separately. |
| 10 | A commit whose loose object has been corrupted | Environment failure, not a report failure: record that verification did not run; do not ask the reporter for another commit. |
| 11 | A partial clone missing the objects a read needs | With `GIT_NO_LAZY_FETCH=1` the read fails and writes nothing; treat it as an environment failure. |
| 12 | Two objects share a 7-character prefix, and a branch with that name selects one | Rejected: `--disambiguate` returns both objects, including with ambiguity warnings disabled. |
| 13 | Git 2.44 or older | Local validation unavailable before handling the identifier; do not rely on an ignored environment variable. |
| 14 | A missing blob is supplied as an object ID in a partial clone | No fetch; enumeration reports no local match and any guarded peel fails without fetching. The outcome is unavailable verification, not a rejected identifier. |
| 15 | A tag and a branch share the supplied short name | Request the fully qualified ref; do not choose a namespace automatically. |
| 16 | A shallow, single-branch, or outdated clone that lacks a commit which exists upstream | Same as any other local absence: verification unavailable. In the local test `--disambiguate` returned nothing and `cat-file -e` failed for a valid upstream commit, with no promisor remote configured, so "is there a promisor?" is not the test either. |
