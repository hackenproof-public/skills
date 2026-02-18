# HackenProof Triage Marketplace Skill

Reusable triage skill for HackenProof report handling:

- verify commit/version is in scope
- verify submission scope
- check duplicates
- validate submission and decide state/severity/comment

Skill folder:

- `hackenproof-triage-marketplace/`

## Install for Codex

Install from GitHub using the built-in skill installer:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo hackenproof-public/skills \
  --path hackenproof-triage-marketplace \
  --ref main
```

For private repositories:

```bash
export GITHUB_TOKEN=<token>
```

After install, restart Codex.

Use in prompt:

```text
Use $hackenproof-triage-marketplace to triage report HACK-123.
```

## Install for Claude

If your Claude environment supports Codex-style skills, install to its skill directory:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo hackenproof-public/skills \
  --path hackenproof-triage-marketplace \
  --ref main \
  --dest <claude-skills-dir>
```

Then reload/restart Claude and invoke:

```text
Use $hackenproof-triage-marketplace to triage report HACK-123.
```

If your Claude setup uses a different plugin format, keep this repo as source-of-truth and add an import/conversion step in your Claude pipeline.

## Publish Checklist

1. Push `hackenproof-triage-marketplace/` to GitHub.
2. Create a tag (example: `v0.1.0`) for stable installs.
3. Install by tag with `--ref v0.1.0` for reproducible team behavior.
