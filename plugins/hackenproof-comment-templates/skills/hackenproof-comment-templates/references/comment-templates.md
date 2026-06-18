# Comment Templates

Standard templates for HackenProof triage comments. Each template has three parts:
- **Header** — acknowledgment and context
- **Main clause** — the decision and its explanation
- **Footer** — closing and reputation note (where applicable)

Replace all `*PLACEHOLDER*` values. Replace `// EXPLANATION` blocks with specific technical reasoning.

---

## Out of Scope

```
Hello,

Thank you for submitting your report! We appreciate your efforts in identifying this issue.

Your submission has been jointly analyzed by our triage specialists and the *TEAMNAME* security team.

Unfortunately, *ISSUE* falls outside the scope of our bug bounty program.

// BRIEF EXPLANATION — what specific scope rule applies and why this finding doesn't meet the bar.
// Reference the actual evidence present and what is missing. Be specific, not generic.

As a result, we will be closing this report as 'Out of Scope' and ending our investigation of this case. Please note that this closure will not impact your reputation score.

Wishing you the best of luck with your future findings!

Best regards,
HackenProof Triage Team
```

---

## Informative / Accepted Risk

```
Hello,

Thank you for submitting your report! We appreciate your efforts in identifying this issue.

The *TEAMNAME* team has reviewed this issue and has decided to accept the associated risk, meaning it will not be fixed as a security vulnerability.

// EXPLANATION FROM THE TEAM — why the risk is accepted, or why the finding is low-impact.
// Include what was confirmed as real vs what impact is missing.

However, it may be addressed as part of future updates or maintenance. As a result, we will be closing this report as 'Informative' and concluding our investigation. You will receive additional reputation points for your contribution.

If you disagree with this decision, please discuss this in the comment section below.

We truly appreciate your commitment to the security of this project. Wishing you a great day and the best of luck with your future findings!

Best regards,
HackenProof Triage Team
```

---

## Not Applicable

```
Hello,

Thank you for submitting your report and for your interest in helping to improve the security of our company.

Following a comprehensive joint review by our triage specialists and the *TEAMNAME* security team, we are unable to validate the reported issue at this time.

// BRIEF EXPLANATION — what specifically could not be reproduced or validated.
// State what evidence is present and what is missing. Do not be vague.

As a result, we have decided to close the report as Not Applicable. This decision is primarily due to the lack of sufficient evidence to confirm the existence of a vulnerability and the limited information provided in the report.

We encourage you to provide more detailed information or evidence if you believe further clarification can help us understand the issue. If you have additional context or proof of concept that was not included in the original submission, please feel free to provide it in the comment section below.

If new evidence arises, we are happy to revisit the issue.

We truly appreciate your efforts in contributing to the security of our platform. Wishing you a great day and the best of luck with your future findings!

Best regards,
HackenProof Triage Team
```

---

## Need More Info

```
Hello,

Thank you for submitting your report! We appreciate your efforts.

Your submission has been reviewed by our triage specialists and the *TEAMNAME* security team. We were unable to fully validate the issue with the information currently provided.

To continue our investigation, please provide:
// LIST EXACTLY WHAT IS MISSING — be specific:
// - What reproduction steps are incomplete
// - What evidence is needed (video, txhash, live domain PoC, etc.)
// - What environment or configuration is required

We will keep this report open for 14 days pending the additional information. If no update is received, we may close the report.

Best regards,
HackenProof Triage Team
```

---

## Duplicate

```
Hello,

Thank you for submitting your report.

After review, this issue shares the same root cause and impact as an existing confirmed finding in our system.

// ONE SENTENCE — describe the root cause that matches, without referencing the other report's ID.

As a result, we will be closing this report as 'Duplicate'.

We appreciate your continued efforts in improving the security of this platform. Wishing you the best of luck with your future findings!

Best regards,
HackenProof Triage Team
```

---

## Dual Defence — Informative (sub-Critical finding)

For DualDefence/audit programs where only Critical + working PoC qualifies for a bounty.
State = **Informative** (not OOS) for genuine but sub-critical findings.

```
Hello!

Thank you for your time and effort in submitting this report. We truly appreciate the work you put into *WHAT THEY INVESTIGATED*.

// 1-3 SENTENCES: acknowledge what was confirmed in the code, then the precise technical reason
// it does not meet the Critical threshold — e.g. trigger is not attacker-controlled,
// impact is off-chain/liveness/MEV, PoC exercises out-of-scope contracts,
// or the finding requires developer error as proximate cause.
// For the DualDefense Audit we focus exclusively on critical vulnerabilities that lead
// to direct loss or permanent lock of user funds.

We will be closing this report as 'Informative'.

Once again, we sincerely appreciate your efforts and look forward to your future findings. Have a great day, and best of luck with your bug hunt!

Best regards,
HackenProof Triage Team
```

**DD-specific rules:**
- Use Informative (not OOS) for genuine sub-critical findings. Reserve OOS for out-of-scope class/target.
- Never mention the actual severity label (High/Medium) — reference the Critical threshold only.
- No reputation score line on Informative.
- Acknowledge what was genuinely confirmed before explaining why it doesn't qualify.
