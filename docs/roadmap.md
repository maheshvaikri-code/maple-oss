# MAPLE Roadmap

**As of 2.1.0 · 2026-09-02** · last updated 2026-09-02

One consolidated backlog. Until now the outstanding work lived in three
unconnected places: the capability matrix in
[`agent-framework-parity.md`](agent-framework-parity.md), the production
findings in the hardening analysis, and the "explicitly out of scope" sections
of individual ADRs. Nothing joined them, so the true size of the remaining work
was not visible anywhere.

## Where MAPLE stands

Of 21 capability rows in the parity matrix:

| Status | Count | Meaning |
| ---: | ---: | --- |
| **Native** | 5 | Implemented in the public runtime and covered by tests |
| **Native + Adapter** | 1 | Native surface plus protocol adapters (MCP and the external tool ecosystem) |
| **Preview** | 9 | Implemented but bounded or opt-in, with a narrower contract |
| **Partial** | 3 | A useful local subset exists; an important counterpart is absent |
| **Deferred** | 2 | Deliberately out of scope for now |
| **Unsupported** | 1 | The boundary fails closed or does not exist |

**Fifteen rows are not Native.** That is the honest scale of what remains, and
the labels are load-bearing: `Preview` is a promise about a *contract*, not a
marketing hedge. The fifteen are enumerated in Tier 4 below — nine whose limit
is that they are local, three whose limit is contract shape, and three that are
deliberate non-goals.

One theme explains most of it: **almost every Preview and Partial is local.**
The subset that exists is genuinely implemented and tested; what is missing is
the cross-process or hosted counterpart. That makes the ordering below simpler
than the count suggests, because a single piece of work — a conforming
distributed transport — unblocks several rows at once.

---

## Tier 1 — Blocks the deployment shape

These decide what MAPLE *is*, not what it has.

### 1.1 A transport that satisfies the broker contract

**Status:** designed, not built ([ADR-161](adr/161-broker-contract-and-the-path-to-multi-host.md))

The `Broker` protocol and its conformance suite exist. The bundled NATS
adapter does not pass: the suite names exactly five missing members —
`get_statistics`, `is_routable`, `set_separation_policy`,
`set_undeliverable_handler`, `unsubscribe` — and it enforces none of
`SecurityConfig`. It is 458 lines against 35 lines of test, excluded from
coverage, with no declared package extra.

MAPLE is no longer a single-process runtime: `FileBroker` crosses processes on
one host. It is not yet multi-*host*, so the "local" rows below still inherit a
ceiling — a lower one than before.

Sequence from ADR-161: `FileBroker` for multi-process on one host first, then
NATS to conformance with the extra declared, coverage restored, and integration
tests against a live server.

**Step one is done** ([ADR-167](adr/167-file-broker-multi-process-on-one-host.md)).
`FileBroker` passes the conformance suite unchanged and delivers across real
process boundaries — 3 consumer processes, 60 messages, each exactly once. The
contract is implementable twice, which is what makes it a contract.

Two findings from building it. Claim-by-`os.rename` — the obvious exclusion
primitive — was measured telling **both** racers they had won, 192 times in
200, so the spool uses MAPLE's existing `_InterProcessFileLock` instead (4
processes x 150 increments, zero lost updates). And a file-backed transport
cannot use ADR-166's condition variable across processes, so its latency is a
poll interval: on one host the in-memory broker remains the right choice.

**Still outstanding: NATS to conformance.** That is what makes MAPLE
multi-*host* rather than multi-process. The five missing members ADR-161 named
now exist and the `nats` extra is declared, so `describe_conformance` reports
structural conformance — but the remaining gap is **capability-shaped, not
method-shaped**: NATS publish is fire-and-forget, so backpressure, undeliverable
reporting and routability have to be built over a transport that does not
provide them. None of it was verifiable without a live server, so **CI now runs a NATS
service container**: `tests/integration/test_nats_live.py` exercises the
transport against a real server and is a required gate, with a guard that fails
the job if the tests *skip* rather than run — because "no server reached" would
otherwise look identical to "everything passed".

That suite measures both halves. What the transport does (delivery, statistics,
unsubscribe) and what it does not: **no backpressure, no undeliverable
reporting, no remote routability**, each asserted as currently false so the day
one changes is a deliberate edit. Those are the measurements the conformance
work has to be designed against, rather than assumptions about NATS.

**This is the 3.0.0 anchor.** It converts more Preview/Partial rows to Native
than any feature would.

### 1.2 Metrics export

**Status:** done ([ADR-162](adr/162-metrics-export-without-a-dependency.md))

`maple.monitoring.metrics` renders any `get_statistics()`-style callable in the
Prometheus text exposition format, with no runtime dependency added. Types are
declared rather than inferred, non-numeric statistics are skipped rather than
coerced, and a source that raises is counted in `maple_metrics_source_errors`
instead of vanishing silently.

MAPLE renders; the host serves. No port is bound — that stays on the deployment
side of the operational boundary.

**What remains:** correlation across hops and hosted trace search, which are
part of Tier 4's tracing row rather than this one, and depend on 1.1.

---

## Tier 2 — Correctness under adverse conditions

**All four items are now done.** Each was measured before being designed, and
in three cases the measurement corrected the entry: the shutdown defect was
about accepted-but-unstarted work rather than executing work, the thread-count
claim was 5.5× overstated, and one of the four "unbounded waits" was already
correct.

| Item | Detail |
| --- | --- |
| ~~**Drain on shutdown**~~ | **Done** ([ADR-163](adr/163-two-clocks-and-a-drain-phase.md)). Measured: 38 of 40 messages discarded silently, `stop()` returning in 0.11s. It now drains queued work up to a deadline and reports what it could not. |
| ~~**Monotonic clocks**~~ | **Done** ([ADR-163](adr/163-two-clocks-and-a-drain-phase.md)). Durations moved to `time.perf_counter()`; records and JWT claims stay on the wall clock. A guard test fails CI on a new wall-clock duration. |
| ~~**Config validation**~~ | **Done** ([ADR-164](adr/164-configuration-is-validated-at-construction.md)). Nine invalid configurations were accepted; `agent_id=""` gave `Ok` sends that delivered nothing, and `max_queue_size=-5` failed every send with `QUEUE_FULL`. It also closed a hole in ADR-157: `NATS://` and `nats:/` silently fell back to the in-process broker. |
| ~~**Unbounded waits**~~ | **Done** ([ADR-165](adr/165-waits-end-when-the-thing-they-wait-for-does.md)), and the count was wrong. Three of the four were real: `Agent.receive()` and `Stream.receive()` never woke at all (`stop()` returned in 0.13s and left the thread wedged permanently), and an unbounded join on an LLM stream collector hung the caller for as long as a provider stalled. The fourth — `TaskQueue` — is **correct**: `stop()` calls `notify_all()` and a parked caller wakes in 0.00s. It matched a text search for a wait with no timeout argument, not a defect. |

---

## Tier 3 — Scale within one process — **done**

Both entries were measured, and **both descriptions were wrong**: one ceiling
did not exist, and the other was real but for a different reason than stated.

- ~~**~11 threads per agent.**~~ **This claim was wrong**, and measuring it
  was the cheapest thing on this page. Each `Agent` did construct a
  `ThreadPoolExecutor(max_workers=10)` — but nothing was ever submitted to it,
  and `ThreadPoolExecutor` spawns workers lazily, so it cost **zero** threads.
  Measured at 1, 5 and 10 agents: **2.0 threads per agent**, flat. A hundred
  agents is roughly two hundred threads, not eleven hundred. The dead pool is
  removed in [ADR-163](adr/163-two-clocks-and-a-drain-phase.md); the ceiling it
  was supposed to justify does not exist.
- ~~**10 ms delivery poll.**~~ **Done**
  ([ADR-166](adr/166-deliver-on-a-signal-not-a-poll.md)) — and this entry named
  the wrong cost. Idling was nearly free: one broker's CPU was below the
  measurement floor, and ten scopes together cost 1% of a core. What the poll
  actually cost was **latency on every hop** — measured p50 4.8 ms, p95
  10.0 ms, max 16.6 ms. Delivery now waits on a condition signalled by the
  enqueue: **p50 0.33 ms, p95 0.62 ms, max 0.85 ms**, and idle CPU drops below
  the floor as a side effect rather than as the point.

---

## Tier 4 — Capability parity

Ordered by whether the gap is a *contract* limit or a *hosting* limit, because
those need very different work.

### Local subset exists; the distributed counterpart does not

Each of these largely resolves once Tier 1.1 lands.

| Capability | Today | What is missing |
| --- | --- | --- |
| **Workflow graph and parallelism** | Preview | Typed nodes, conditional routing, bounded fan-out/fan-in and deterministic joins all exist locally. Distributed scheduling and cross-process step ownership do not. |
| **Durable checkpoints and recovery** | Partial | Memory/file checkpoints with bounded history, CAS versions and fencing leases exist. Cross-process run restoration and a stated side-effect policy do not. No exactly-once claim. |
| **Conversation sessions and memory** | Partial | Bounded session stores plus working, episodic and semantic memory — all host-local. |
| **Human-in-the-loop approval** | Partial | Durable approvals and human-input records with per-record cross-process fencing. Remote notification delivery and hosted approval UX are absent. |
| **Retrieval, RAG and citations** | Preview | Deterministic chunking, source references, lexical and caller-supplied-vector retrieval, checkpointed ingestion — all local and bounded. No managed vector store; embeddings stay host-owned. |
| **Tracing and observability** | Preview | Bounded event streams, redaction, local spans, an exporter seam. No hosted trace search, no correlation propagated across hops. Overlaps Tier 1.2. |
| **Evaluations** | Preview | Deterministic output/schema cases, tool trajectories, retrieval and groundedness metrics, judge calibration. No provider-owned orchestration or hosted aggregation. |
| **Streaming** | Preview | Provider-native streams plus bounded lifecycle events. No hosted aggregation or remote deduplication. |
| **Handoffs and agent-as-tool** | Preview | Bounded approval-by-default ownership transfer with local records. Remote routing and authentication need separate review. |

### Contract-shaped, independent of transport

| Capability | Today | What is missing |
| --- | --- | --- |
| **Typed I/O and structured generation** | Preview | Typed tool models, `output_model`, bounded schema parsing and repair exist. The narrowness is deliberate — widening it is a contract decision, not a bug. |
| **Guardrails and policy enforcement** | Preview | Input/output guardrails with fail-closed approval and bounded event metadata. Richer policy composition is unbuilt. |
| **Multimodal image input** | Preview | Bounded ordered text/image parts with validated sources. Other modalities are absent. |

### Deliberately not built

These are decisions, not omissions, and each needs a reviewed contract before
any implementation.

| Capability | Status | Position |
| --- | --- | --- |
| **Code interpreter, browser, computer use, sandboxing** | Unsupported | [ADR-143](adr/143-execution-isolation-boundary.md) gates this pending an explicit isolation contract. `TrustedLocalExecutor` runs handlers the host explicitly trusted; extracted code blocks are data and are never executed. A subprocess is not an isolation boundary, and rebranding the executor as a sandbox would be a false security claim. |
| **Hosting, visual tooling, managed runtime** | Deferred | `RunServer` is loopback with a dependency-free client contract. No hosted multi-tenant service, dashboard, or control plane — and none implied. |
| **Language SDK breadth** | Deferred | Python only. |

---

## Recommended order

1. ~~**Metrics export** (Tier 1.2)~~ — **done.** Smallest change, largest
   operator benefit; 2.1.0's counters now have somewhere to go.
2. ~~**Tier 2 in full**~~ — **done**: drain on shutdown, monotonic clocks,
   config validation, and bounded waits. Every entry was measured before being
   designed, and three of the four descriptions were wrong in the process.
3. ~~**`FileBroker`** (Tier 1.1, step one)~~ — **done.** Multi-process on one
   host, and the first genuine proof the broker contract is implementable
   twice.
4. **NATS to conformance** (Tier 1.1, step two) — **next**, and the 3.0.0
   anchor. Converts
   the "local" limit on nine Tier 4 rows into a real distributed story.
5. **Everything else**, reordered once 3 and 4 reveal what they actually cost.

The parity ledger's own guidance applies to this list too: order by runtime
correctness, not by the number of framework checkmarks.

## Not on this list

Reducing the 275-entry `__all__`. Shrinking the public surface of a released
version is a breaking product decision, not a defect fix, and belongs to a
major version if it happens at all.

## Keeping this honest

Every status here traces to [`agent-framework-parity.md`](agent-framework-parity.md),
which carries the evidence per row, or to an ADR. When a status changes, change
it there first — this page is a view over that record, and a view that drifts
from its source is worse than no view. The same failure produced a website
advertising a test count two releases out of date.
