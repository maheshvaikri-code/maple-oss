# 03 — Parallel Execution Protocol (subagents)

The company can put several employees to work **at the same time** using
Claude Code subagents (`.claude/agents/`). Parallelism is a tool for Class
M/L tasks with genuinely independent work — not a default. A wrong parallel
split costs more than serial execution.

## 1. When to fan out

Fan out only when ALL of these hold:

1. The G2 plan decomposes into **work packages** with no shared files.
2. Shared contracts (types, schemas, API signatures, traits/interfaces)
   are **frozen and committed first** — contract-first, then parallel.
3. Each package has its own acceptance criteria and can be verified alone.
4. Width ≤ **4** concurrent agents. Prefer 2–3 bigger packages over 5 slivers.

Good candidates: independent modules; docs while tests are written; the G4/G5
review fan-out (below); porting the same fix across isolated crates/packages.

Never parallel: gate decisions, DB migrations, dependency additions, version
bumps, release steps, anything on the escalation list, two packages that edit
the same file (re-partition or serialize instead).

## 2. Orchestrator discipline (main thread)

The main conversation is the **Orchestrator** — it wears the Product Owner /
Architect hats, dispatches, and reconciles. It does not write feature code
while workers are out.

Dispatch rules — every subagent prompt is **self-contained** (subagents do
not inherit chat history):

- The work-package brief: goal, acceptance criteria **verbatim**, constraints.
- **File scope**: exact paths the agent may create/modify. Out-of-scope
  edits are a review BLOCKER.
- Which role card + skills to Read first (paths under `.Doctrine/`).
- What to return: summary, files touched, test commands run + real output,
  open questions. No "done" without evidence (Non-Negotiable #1).

## 3. Reconcile (after workers return)

1. Orchestrator reviews each report; rejects any package lacking evidence.
2. Integrate in dependency order; run the **full** suite after each merge —
   per-package green does not imply integration green.
3. Conflicts or interface drift → back to the owning package, not patched
   in-place by the orchestrator.
4. Then the normal gates resume (G4 →).

## 4. The review fan-out (recommended even for solo-stream tasks)

At G4/G5, dispatch in parallel with fresh context:

- `code-reviewer` — diff vs. brief + standards → review report
- `security-reviewer` — audit sweep → sign-off or veto
- `qa-engineer` — executes the test plan → QA report

Each writes its artifact to `docs/`; the Orchestrator merges findings into a
single severity-ranked verdict. Fresh-context review is the point: reviewers
must **not** be told what the author believes the code does.

## 5. Roles that never run as subagents

Product Owner, Chief Architect, UX Designer, Release Manager, and FDE stay
in the main thread — their work is interactive (human escalations, decisions,
publishing, the P1/P6 sign-offs) and must not happen in a detached context.
(FDE's P4 build and P5 instrumentation harness may still fan out as workers.)
ALL startup-profile roles are main-thread for the same reason: everything
they produce points outward, and external sends belong to the human.

## 6. Provided agents

`.claude/agents/` ships with: eight parallel **workers** (backend, frontend,
database, interop, devops engineers, sre, data-engineer, ml-engineer) and
six fresh-context **verifiers** (code-reviewer, security-reviewer,
qa-engineer, project-reviewer, tech-writer, compliance-officer). Each is a
thin shell that Reads its `.Doctrine/roles/` card — the doctrine stays the
single source of truth.
