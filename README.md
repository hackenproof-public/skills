# HackenProof Skills Marketplace

Agent skills for triaging security reports on Ethereum and EVM smart contracts, packaged as a
Claude Code plugin marketplace. They cover report quality scoring, PoC evidence grading, fix
verification and full triage workflows. The skills come from the [HackenProof](https://hackenproof.com)
triage team.

## Do I need a HackenProof account?

Not for every skill. Some skills work on any report or codebase you give them. Others call the
HackenProof API through the HackenProof MCP server and only work for people with access to a
HackenProof program.

### Standalone (no account, no MCP server)

| Plugin | What it does | Input |
|--------|--------------|-------|
| `hackenproof-fix-verifier` | Checks whether a patch fixes the reported vulnerability without adding new ones. Includes Solidity-specific checks for reentrancy, access control, arithmetic, storage layout and upgrades. | A report or plain description, plus a local git diff |
| `hackenproof-report-quality-scorer` | Scores a vulnerability report 0–8 on target, reproduction, impact evidence and severity claim, and lists what is missing. | Report text pasted into the chat |
| `hackenproof-poc-grader` | Grades the PoC evidence in a report (Verified, Plausible, Weak, Invalid, Out of Scope Evidence). It fetches attachments through MCP when connected, and otherwise asks you to paste or describe the evidence. | A report with its PoC |

These skills use the HackenProof severity rubrics, but nothing in them depends on HackenProof
infrastructure. You can use them on reports from any bug bounty platform, audit contest or
internal review.

### Requires HackenProof access

| Plugin | What it does |
|--------|--------------|
| `hackenproof-triage` | Full single-report triage: scope, duplicates, state, severity, labels and comment |
| `hackenproof-bulk-triage` | Triage recommendations for all open reports across your assigned programs |
| `hackenproof-all-reports-export` | Exports all reports of a program to Markdown, JSON or CSV |
| `hackenproof-handoff` | Handoff summaries for client teams, with bounty ranges |
| `hackenproof-comment-templates` | HackenProof closure comment templates |
| `hackenproof-triage-mistakes` | A shared, self-expanding log of triage mistakes |

## Example

[`examples/solidity-reentrancy`](examples/solidity-reentrancy) shows a reentrancy report on a Solidity
vault going through the report quality scorer and the fix verifier. The fix verifier catches an
incomplete patch that is still exploitable through cross-function reentrancy. The example
includes Foundry tests that reproduce both the original exploit and the bypass.

### Standalone install

To add only the standalone skills, put this in `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "hackenproof-skills": {
      "source": {
        "source": "github",
        "repo": "hackenproof-public/skills"
      }
    }
  },
  "enabledPlugins": {
    "hackenproof-fix-verifier@hackenproof-skills": true,
    "hackenproof-report-quality-scorer@hackenproof-skills": true,
    "hackenproof-poc-grader@hackenproof-skills": true
  }
}
```

Each skill is a plain `SKILL.md` with reference files under
`plugins/<plugin>/skills/<skill>/`, so other agents that read the Agent Skills format can load
them directly.

## Install in Claude Code

### Option 1: Server-Managed Settings (org-wide)

Add to your organization's managed settings at **claude.ai → Admin Settings → Claude Code → Managed settings**:

```json
{
  "extraKnownMarketplaces": {
    "hackenproof-skills": {
      "source": {
        "source": "github",
        "repo": "hackenproof-public/skills"
      }
    }
  },
  "enabledPlugins": {
    "hackenproof-triage@hackenproof-skills": true
  }
}
```

All authenticated org members will receive the plugin automatically.

### Option 2: Project-level

Add to your project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "hackenproof-skills": {
      "source": {
        "source": "github",
        "repo": "hackenproof-public/skills"
      }
    }
  },
  "enabledPlugins": {
    "hackenproof-triage@hackenproof-skills": true
  }
}
```

### Option 3: Manual

1. Run `/plugin` in Claude Code
2. Go to **Marketplaces** tab
3. Add marketplace: `hackenproof-public/skills`
4. Install `hackenproof-triage`

## Repository Structure

```
.claude-plugin/
  marketplace.json          # Marketplace index
plugins/
  hackenproof-triage/
    .claude-plugin/
      plugin.json           # Plugin manifest
    skills/
      hackenproof-triage-marketplace/
        SKILL.md            # Skill definition
        agents/
          openai.yaml
        references/
          hackenproof-global-policy.md
          severity-mapping.md
          triage-comment-templates.md
```
