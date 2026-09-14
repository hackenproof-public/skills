# HackenProof Skills Marketplace

Claude Code plugin marketplace for HackenProof bug bounty triage.

## Plugins

### hackenproof-triage

Reusable triage skill for HackenProof report handling:

- Verify commit/version is in scope
- Verify submission scope
- Check duplicates
- Validate submission and decide state/severity/comment

### hackenproof-audit-scope

Pre-sales scoping for Rust and Solidity repositories (built for Sales Managers):

- Counts billable lines of code (comments/blank lines excluded; tests, mocks, scripts, interfaces, generated code and dependencies separated)
- Ranks the most security-critical files and suggests a complexity tier
- Estimates audit effort (auditor-days, range, calendar weeks, sensitivity across tiers)
- Screens the repo for prompt-injection text and code-execution hazards before anyone opens or builds it
- Read-only: never builds, installs or runs anything from the target repository

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
