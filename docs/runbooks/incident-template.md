# Incident review template

Fill in within 5 business days of any sev-1. Save as
`docs/incidents/YYYY-MM-DD-short-slug.md`.

---

**Incident ID**: `<YYYY-MM-DD-nn>`
**Severity**: `sev-1 | sev-2`
**Status**: `open | mitigated | resolved`
**Detected at** (UTC): `…`
**Resolved at** (UTC): `…`
**Duration**: `…`

## Summary (1 paragraph)

<One paragraph for the non-engineer: what broke, what the user saw,
how we fixed it.>

## Timeline (UTC, newest last)

- `HH:MM` — …
- `HH:MM` — …

## Root cause

<What actually caused the failure, not just the immediate trigger.
Five whys.>

## Impact

- Users affected: …
- Data affected: …
- SLO burn: …% of the month's error budget consumed.

## What went well

- …

## What went badly

- …

## Action items

- [ ] **`INFRA-…`** <Concrete fix, with owner + deadline>
- [ ] **`INFRA-…`** <…>

## References

- Alert: …
- Runbook: …
- Commits: …
- Logs: …
