---
description: Write a doctrine state-plane checkpoint (propose → validate → commit)
---

Write a state-plane checkpoint for this session. Follow the propose→dispose
protocol exactly (`.Doctrine/state-plane/STATE.md`):

1. Author a proposal JSON in a temp file (NOT in the repo) with:
   - `session_id`: `s-<date>-<letter>` (reuse this session's id if one
     exists in `.doctrine-state/checkpoint.json`).
   - `control`: your current `role`, `phase`, `gates_passed`,
     `ponytail_mode`, `active_intents` (≤8, filesystem-safe ids only).
   - `distillate`: what THIS session learned that is not expressed in
     code. Hard caps: ≤12 `learned` (claim ≤280 chars, evidence ≤160 —
     a file:line, a command, or a decision id, NEVER a dialogue quote;
     `confidence: verified` ONLY if you executed it this session),
     ≤8 `dead_ends`, ≤6 `open_threads`, ≤6 `next_actions`. No secrets —
     the validator rejects secret-like content and the files are
     committed forever.
2. Run: `python tools/doctrine_state.py checkpoint --proposal <tmpfile>`
   — the validator stamps seq/at_commit/created_at and chains the hash.
   If it rejects the proposal, fix the proposal; never bypass.
3. Run: `python tools/doctrine_state.py verify` and paste the output.
4. Commit exactly as the tool instructs
   (`git add .doctrine-state && git commit -m "state: checkpoint <seq>"`).

$ARGUMENTS
