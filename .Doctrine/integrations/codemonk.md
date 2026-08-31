---
integration: codemonk
upstream: https://github.com/aroora-ai-labs/codemonk
license: MIT
pinned_version: 0.10.0
discipline: metrics-engineering
verified: 2026-07-12
---

# CodeMonk — Integration

The doctrine's metrology subsystem: zero-dependency change metrics, token
metering, and a graded scorecard for AI-agent coding. ~4,400 LOC, 85
tests, a golden-vector metric spec (CODEMONK-METRICS-v1, 25 hand-computed
vectors) — the same determinism discipline as the rest of this ecosystem.
Not vendored: pinned upstream, thin shim (`skills/metrics.md`).

## What it measures

**CESR** (merged AND survived — no revert/excess churn/incident, staged
decomposition) · **Agent Engagement Level** · **HITL coverage/intensity**
· **HITL Reduction Rate gated on CESR holding** (flags review erosion) ·
**ROI** (net hours after rework/review/incidents) · **Token Churn Ratio**
(spend on retried/superseded/failed attempts) · **cost per landed change**
(joined to outcomes via `item_id`).

## Install & health check

```bash
pip install codemonk            # or pipx; pin ==0.10.0
python -m codemonk demo         # full scorecard on synthetic data
python -m codemonk analyze --repo .   # real metrics from git history
```

Verified on this repo (2026-07-12): 31 agent changes detected via the
Co-Authored-By trailers, CESR 100% (zero reverts — accurate), HITL 0%
from git alone — see the wiring note below for why that number needs
enrichment before it means anything.

## Doctrine wiring

- **item_id discipline:** use the state-plane `task_refs` / brief slug as
  CodeMonk's `item_id` everywhere (commits, token logs, work items) so
  cost joins to landed outcomes.
- **HITL truth:** git carries no review data, so HITL reads 0. The
  doctrine's review reality lives in `docs/reviews/` and `docs/qa/` —
  `python tools/doctrine_metrics.py enrich` extracts the commits those
  artifacts reference (verified against the repo) and emits the overlay;
  consume with `analyze --enrich docs/metrics/enrichment.json`.
  Verified on this repo: HITL 0% → 27.3%. Fidelity label: "reviewed"
  means covered by the verifier fan-out (adversarial agent review,
  human-arbitrated) — quote it as such.
- **Token capture (closes the TCR / cost-per-landed-change gap):**
  capture is a SESSION-LAUNCH choice — OTel env must exist before the
  agent process starts, so no hook can enable it retroactively. Two
  supported wirings (a SessionStart hint fires when a metrics-adopted
  repo runs uncaptured):

  Option A — wrapped launch (endpoint spawned, env pre-wired; verified
  upstream on a real Claude Code run):

  ```bash
  codemonk wrap --otel -- claude
  ```

  Option B — standing collector + explicit env before launching:

  ```bash
  codemonk collect               # OTLP/JSON on 127.0.0.1:4318
  export CLAUDE_CODE_ENABLE_TELEMETRY=1
  export OTEL_METRICS_EXPORTER=otlp OTEL_LOGS_EXPORTER=otlp
  export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
  export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
  claude
  ```

  Both land events in `codemonk_tokens.jsonl` (gitignored — telemetry
  is machine-local). Report: `codemonk tokens --log
  codemonk_tokens.jsonl`; `codemonk.status` attrs make TCR precise;
  `item_id` = the state-plane `task_refs` joins spend to landed
  outcomes.
- **G7 is the consumer:** `codemonk scorecard` output is filed with the
  retrospective (`docs/metrics/`); trends via snapshot + `trend`.
  CESR drops feed the retro's 5-whys.
- **Provenance:** this repo's commit style (Claude co-author trailers)
  is what the agent/human attribution reads — keep the trailer rule.
- **Honesty law applies to numbers:** estimated cost stays labeled
  estimated (CodeMonk's own footer does this — keep it when quoting).

## Boundaries

Metrics never gate an individual merge (that is the council's job — see
`standards/merge-and-promotion.md`); they trend the process for G7.
Baseline fidelity notes: HITL/TCR track their inputs; git-only runs are
heuristics; live GitLab path unverified upstream at 0.10.0.
