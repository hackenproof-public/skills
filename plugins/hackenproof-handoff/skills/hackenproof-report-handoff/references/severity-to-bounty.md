# Severity to Bounty Mapping

## How to determine bounty range

1. Call `get_program_info` for the program.
2. Look at the `rewards` field in the response.
3. Match the report severity to the corresponding reward tier.

The rewards object structure varies by program but typically contains min/max ranges per severity level.

## Bounty Notes

- Bounty ranges are program-specific — always pull from `get_program_info`, never assume.
- Some programs have fixed amounts per severity, others have ranges.
- Dual Defence programs only pay for Critical with PoC.
- Audit contest programs may have different payout structures (pool-based).
- If `rewards` is empty or missing for a severity, report "Bounty not configured for {severity}" in the handoff.
