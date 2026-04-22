# Handoff Template

Use this exact format for every report handoff. Do not skip any field.

## Single Report

```md
## Report Handoff

**Report**: {report_url}
**Title**: {report_title}
**Severity**: {severity}
**Recommended Bounty**: ${min} - ${max}
**Target**: {target}

### Summary

{2-3 sentence explanation: what the vulnerability is, what component is affected, and what the impact is}

### Recommendation

{What the client team should do: fix, investigate, deprioritize, or monitor. Be specific about the affected component.}
```

## Batch Header

When producing handoffs for multiple reports, add this header before the individual handoffs:

```md
# Handoff Summary for {program_name}

**Total reports**: {count}
**Breakdown**: {X Critical, Y High, Z Medium, W Low}
**Total estimated bounty range**: ${min_total} - ${max_total}

---
```

## Field Rules

- `report_url`: `https://dashboard.hackenproof.com/manager/companies/{company}/{program}/reports/{report_id}`
- `severity`: Use the severity already set on the report. If not set, recommend one and prefix with "Recommended: ".
- `bounty range`: From `get_program_info` rewards for the given severity. If rewards are not configured, write "Not configured".
- `target`: From report details. If null, write "Not specified".
- `summary`: Derived from vulnerability_description. Focus on root cause and business impact. No speculation.
- `recommendation`: Actionable next step for the client engineering team.
