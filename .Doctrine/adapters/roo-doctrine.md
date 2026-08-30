# Roo Code Rules — Doctrine

This repository is governed by an engineering doctrine.

BEFORE any work: read `.Doctrine.md` at the repo root and follow it —
task classes, gates, role protocol, and its §6 routing table decide which
`.Doctrine/` files to load (never bulk-read the folder). `AGENTS.md`
carries the compressed boot.

Hard rules that always bind: never fabricate output or claim untested
success; never commit secrets; never delete/skip/weaken a failing test;
behavior changes ship with tests; TODO is not done; stay in scope; ask
the human before irreversible/external actions (publish, delete data,
force-push, paid services, scope/API/license changes). The inner build
loop runs under `.Doctrine/skills/loop-engineering.md` caps: iteration
budgets, thrash detector, stop-and-escalate over endless retry.
