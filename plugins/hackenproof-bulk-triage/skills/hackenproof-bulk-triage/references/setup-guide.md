# Bulk Triage Setup Guide

## Prerequisites

Create `~/.claude/hackenproof-repos.yaml` before running the bulk triage skill. This file maps HackenProof program slugs to local repositories and/or blockchain explorers so the skill can validate reports against source code or deployed contracts.

## File Format

```yaml
programs:
  program-slug:
    repo: ~/path/to/local/clone       # optional — local git repo for source validation
    branch: main                       # optional — branch to track (defaults to current)
    explorer: https://explorer/address # optional — deployed contract URL
    enabled: true                      # optional — set false to skip (defaults to true)
```

## Validation Modes

Each program entry determines how reports are validated:

| Config                    | Mode       | Behavior                                              |
|---------------------------|------------|-------------------------------------------------------|
| `repo` set                | Source     | Git fetch + commit verification + source code review  |
| `explorer` set (no repo)  | Explorer   | Contract address matching against program scope       |
| Both `repo` and `explorer`| Hybrid     | Source validation + explorer as deployment anchor      |
| Neither                   | API-only   | Relies on report details and attachments only          |

## Example

```yaml
programs:
  # Source repo — validates commits and reads code
  near-intents-smart-contracts:
    repo: ~/hackenproof/bb/near/intents
    branch: main

  # Explorer only — deployed contract, no source
  some-defi-protocol:
    explorer: https://etherscan.io/address/0xABC123...

  # Both — source repo + deployed address
  multipli-smart-contracts:
    repo: ~/hackenproof/bb/multipli/Barebones-MultipliVault
    branch: v2
    explorer: https://snowtrace.io/address/0xCF0Eb4...

  # Temporarily disabled
  paused-program:
    repo: ~/hackenproof/bb/paused
    enabled: false
```

## Finding Program Slugs

Program slugs must match the HackenProof dashboard URL:

```
https://dashboard.hackenproof.com/manager/companies/{company}/{program-slug}/...
```

Or run the skill without the config file — it will list all assigned programs by slug so you know what to add.

## Notes

- Paths support `~` expansion.
- If `branch` is omitted, the skill uses the repo's current checked-out branch.
- Programs not listed in the file are still triaged using API-only mode.
- Multiple `explorer` values for the same program are not supported in YAML — use the primary contract address.
