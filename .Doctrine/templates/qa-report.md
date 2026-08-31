# QA + Security Report — <task> @ <commit>
<!-- G5 artifact. File as docs/qa/<task>.md -->

**QA Engineer** · **Security Reviewer** · **Date:**
**Build under test:** exact commit/tag (must equal what ships)

## Acceptance criteria verification
| # | Criterion | How executed | Evidence (real output) | Pass |
|---|-----------|--------------|------------------------|------|

## Adversarial & edge matrix
| Input/scenario | Expected | Observed | Pass |
|----------------|----------|----------|------|
(empty · huge · unicode · zero/negative · duplicate · concurrent ·
malformed · interrupted · limit−1/limit/limit+1)

## Regression
Suite: command + summary output pasted. Flakes: none / ticketed as …

## Bugs found
| # | Repro steps (minimal) | Severity | Fixed @ | Re-verified | Regression test |
|---|----------------------|----------|---------|-------------|-----------------|

## Security sweep (per skills/security.md)
Secrets scan: … · Injection review: … · Dep audit (output attached): … ·
Dangerous constructs: … · Bounds/fail-closed: …

**Security verdict:** SIGN-OFF / **VETO** (reasons) · human override: n/a or quoted
**QA verdict:** pass / fail → returned to G3 with findings
