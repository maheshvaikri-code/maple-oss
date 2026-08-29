# Slice 199 plan — execution integration isolation gate

**Brief:** [maple-agent-runtime-slice199.md](../briefs/maple-agent-runtime-slice199.md)  
**Design/ADR:** [ADR-143](../adr/143-execution-isolation-boundary.md)  
**Class:** L

## Gates

| # | Gate | Role | Artifact | Status |
|---|---|---|---|---|
| 1 | Threat model and unsupported-surface inventory | Chief Architect / Security | brief and ADR assets, boundaries, non-claims | complete |
| 2 | Isolation/action/artifact contract | Chief Architect / Security / Backend | explicit decisions 1–8 in the brief | blocked pending human input |
| 3 | Implementation design | Backend / ML / Interop | typed action and worker contracts only after Gate 2 | pending |
| 4 | Adversarial implementation tests | Security / QA | isolation, approval, quota, cleanup, artifact, and side-effect tests | pending |
| 5 | Fresh review and package evidence | Code Reviewer / Security / QA / Release | fresh verifier reports, clean package, no-network doctor | pending |

## Threat sketch

Assets: host filesystem and processes, credentials, network and browser
sessions, display/input devices, generated code, artifacts, human approvals,
tenant identity, audit records, and external side effects. Threats include
escape from isolation, prompt-generated exfiltration, path traversal, secret
injection, network pivoting, browser session theft, quota bypass, stale approval
reuse, incomplete cleanup, result poisoning, replay, and ambiguous ownership.

## Rollback

The safe rollback is to keep the capability unsupported and retain the current
trusted/non-executing surfaces. No implementation changes are authorized by
this slice. Any future partial implementation must be removable without
changing existing artifact or trusted-handler behavior.

## Exit condition

G0/G1 are complete. G2 is intentionally blocked until the human supplies the
required isolation and policy decisions or explicitly removes the capability
from MAPLE's intended release scope.
