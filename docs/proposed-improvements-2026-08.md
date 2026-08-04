# MAPLE — Proposed Improvements (2026-08)

> **STATUS: ACCEPTED — merged and released in v1.1.3.**
> Reviewed by the owner (all 6 items, code-level) and verified — full suite 1002 passed,
> 0 failed. Committed with a version bump to `1.1.3` and a `CHANGELOG.md` entry; the two
> intentional behavior changes (#3 `get_health_summary` no longer returns `no_data`; #5b
> library `logging.basicConfig` removed) were accepted knowingly. This document is retained
> as the rationale record. They came out of integrating MAPLE 1.1.2 into a downstream
> governed host (OpenHawk), where each rough edge was hit with real evidence.

Each item lists the **problem** (with where it was hit), the **change**, **backward
compatibility**, and the **tests/benchmarks** added.

---

## #1 — `exponential_backoff(max_delay=...)`: a per-attempt delay ceiling

- **Problem.** `maple.error.recovery.exponential_backoff(initial, factor, jitter)` had **no
  ceiling**: the delay grows as `initial * factor ** attempt`, so a large
  `RetryOptions.max_attempts` produces an enormous sleep that can stall a caller holding a
  resource across the backoff (a downstream fleet had to wrap it with `min(base(n), 2.0)`).
- **Change.** Added an optional `max_delay: Optional[float] = None`. When set, the returned
  delay — **including jitter** — never exceeds it (`delay = min(delay, max_delay)`).
- **Backward compatible.** Default `None` ⇒ prior unbounded behavior, byte-for-byte.
- **Tests.** `tests/error/test_backoff_max_delay.py` (6): uncapped grows unbounded; capped
  never exceeds; cap includes jitter; small attempts unaffected; default unchanged; retry
  attempt-count unchanged.
- **Benchmark.** 12 attempts: uncapped **≈409s** total sleep vs capped(2.0s) **≈17s** — a
  **~24×** reduction of worst-case stall.

## #2 — `register_mcp_tools(...)`: host governance hooks for untrusted MCP tools

- **Problem.** `maple.autonomy.register_mcp_tools(registry, tools)` registered an
  **external, untrusted** server's tools as-is: **no policy hook, no server-namespacing, no
  name sanitization, no cap.** A downstream host had to build all of that itself — and an
  expert review still found two privilege-escalation holes (cross-server name inheritance;
  control-byte names injecting rows into a human tool table) before getting it right. MAPLE
  can offer the safe building blocks so every consumer doesn't re-implement (and mis-implement) them.
- **Change (all opt-in, in `maple/autonomy/mcp_tools.py`):**
  - `policy(tool, server_id) -> bool` — a host authorization callback; a rejected tool (or a
    policy that **raises**) is **not** registered (fail-closed default-deny hook).
  - `namespace=True` (with `server_id`) — register under a sanitized `mcp.<server_id>.<name>`
    so a server can't shadow/overwrite another server's or a native tool.
  - `max_tools` — cap tools registered from one discovery.
  - New `sanitize_tool_name(name)` — reduce an untrusted name to `[A-Za-z0-9_.-]`, bounded.
- **Backward compatible.** With no hooks it registers all tools as before (safe only for a
  trusted server); this is documented in the docstring.
- **Tests.** `tests/autonomy/test_mcp_governance.py` (11): sanitize strips/bounds; policy
  reject skips; policy-raise fails closed; default registers all; namespacing prevents native
  shadowing; two servers' same-named tools stay distinct; namespace-without-server-id registers
  nothing; hostile name sanitized; `max_tools` caps.
- **Note.** `discover_mcp_tools` currently returns two *hardcoded* standard tools rather than
  the server's live tool list — a separate follow-up, out of scope here.

## #3 — `HealthMonitor.snapshot()`: an immediate, on-demand health read

- **Problem.** `get_health_summary()` returned `{"status": "no_data"}` until the background
  loop's **first `collection_interval`** sample, so a just-started monitor read `no_data`
  even though the counters were already live (a downstream reviewer flagged the confusing read).
- **Change (in `maple/monitoring/health_monitor.py`):**
  - New `snapshot()` — an **immediate** summary computed on demand from the accumulated
    counters (`_summarize(get_current_metrics())`), available the instant the monitor exists.
  - `get_health_summary()` now falls back to an on-demand read when no sample exists yet, so
    it **no longer returns `no_data`** while live data exists.
- **Backward compatibility / BEHAVIOR CHANGE.** `get_health_summary()` on a fresh monitor now
  returns a live summary (`healthy` with zero rates) instead of `no_data`. The one existing
  test that asserted `no_data` was updated (`tests/monitoring/test_health_monitor.py`). **This
  is the item most worth the owner's explicit sign-off**, since it changes an observable value.
- **Tests.** `tests/monitoring/test_health_snapshot.py` (4) + the updated `no_data` test.
- **Benchmark.** `snapshot()` ≈ **7k ops/sec** (cost dominated by `psutil.cpu_percent()`).

## #5 — Hygiene

- **#5a — `datetime.utcnow()` deprecation** (`maple/core/message.py`,
  `maple/security/cryptography_impl.py`). Replaced with
  `datetime.now(timezone.utc).replace(tzinfo=None)` — the **non-deprecated equivalent that
  keeps the same naive-UTC value**, so `Message` serialization (`.isoformat() + "Z"`) is
  unchanged. (Moving to timezone-*aware* datetimes is a larger, separate decision for the owner.)
- **#5b — library `logging.basicConfig`** removed from **7 modules** (`agent`, `broker`,
  `communication.streaming`, `error.circuit_breaker`, `error.recovery`, `resources.manager`,
  `resources.negotiation`). A library must not configure the **root** logger — it hijacked the
  host's logging and emitted INFO init noise. Each keeps its `logging.getLogger(__name__)`; the
  host now owns logging config. **Behavior note:** MAPLE's own `logger.info(...)` lines no
  longer print unless the host configures logging — intended, but worth the owner's awareness.
- **#5c — non-daemon threads: investigated, NO CHANGE NEEDED.** An audit of every
  `threading.Thread(...)` in `maple/` found they **already** set `daemon=True` (broker, agent,
  monitoring, discovery, state, task_management). The downstream "MAPLE spawns non-daemon
  threads" note was over-cautious for 1.1.2.
- **Tests.** `tests/test_hygiene.py` (3): no `utcnow` DeprecationWarning + naive-UTC preserved;
  timestamp serializes without a double timezone; a fresh import does not force the root logger to INFO.

## #6 — Resource model v2: lifecycle taxonomy, custom dimensions, exclusive leases

- **Problem.** `ResourceRequest` hard-codes five knobs (`compute`, `memory`, `bandwidth`,
  `tokens`, `time`) and `ResourceManager` models exactly one lifecycle — a **renewable pool**
  (`release()` refunded a hard-coded `['compute','memory','bandwidth','tokens']` list). That
  cannot express (a) other numeric dimensions an agent wants to negotiate (**GPU/VRAM, disk,
  `$` spend, API-call/QPS budget, energy**), (b) a **consumable** budget that is *spent* and
  must **not** be refunded on release (money, api_calls, energy), or (c) an **exclusive**
  resource held by **one agent at a time** (a lock, a physical device, a license seat, a
  singleton "leader" role). A downstream host (OpenHawk) hit exactly these: its scarcest
  resources are consumable ($ spend, provider quota) and exclusive (fleet-worker seats,
  tool-use grants) — neither of which the pool model represents.
- **Change (all backward-compatible; built-in fields byte-for-byte unchanged):**
  - **Lifecycle taxonomy** (`maple/resources/manager.py`): `ResourceLifecycle.{RENEWABLE,
    CONSUMABLE}` + `DEFAULT_LIFECYCLES` (compute/memory/bandwidth/tokens/gpu/disk = renewable;
    money/cost/api_calls/energy = consumable). `register_resource(type, amount, lifecycle=…)`
    takes an optional override; `lifecycle_of(type)` exposes it. `release()` now refunds a
    resource **iff** its lifecycle is `RENEWABLE` — so a consumable budget stays spent, and a
    new renewable dimension (gpu/disk) correctly returns to its pool. The historical four
    types are renewable, so their behaviour is identical.
  - **Custom dimensions** (`maple/resources/specification.py`): `ResourceRequest.custom:
    Optional[Dict[str, ResourceRange]]` lets an agent negotiate arbitrarily-named **numeric**
    resources without MAPLE hard-coding each. `_can_satisfy`/`_allocate_resources` handle them
    generically (a size-string like disk `'10GB'` is accepted and parsed to bytes); an
    *unregistered* custom name is a no-op, mirroring the built-in fields. Default `None`.
  - **Exclusive leases** (new `maple/resources/lease.py`): `LeaseManager`/`Lease` grant
    exclusive, **TTL-bounded** holds with a monotonically increasing **fencing token**.
    Expiry is the preemption mechanism (a crashed holder cannot deadlock the resource); a
    stale holder that resumes after its lease was re-granted fails `is_valid(lease)` and will
    not act. Thread-safe; the clock is injectable for deterministic tests. API: `acquire`,
    `renew`, `release`, `is_valid`, `holder_of`, `is_held`.
- **Backward compatibility.** New `custom` field defaults `None`; `register_resource`'s
  `lifecycle` arg is optional; the four historical pools stay renewable and refund exactly as
  before (regression-tested). New symbols are additive exports. **No behavior change to any
  existing call.**
- **Tests.** `tests/resources/test_resource_model.py` (36): lifecycle defaults/override/
  fallback; consumable-not-refunded vs renewable-refunded vs mixed release; `custom`
  to_dict/from_dict/roundtrip; custom allocate/shortfall/unregistered-ignored/preferred-cap/
  size-string; lease acquire/reject/renew-token, expiry preemption, fencing-token
  invalidation of a stale holder, release-by-stale no-op, renew-after-lost, invalid TTL, and
  a 20-thread concurrency race proving exactly one acquirer wins. Full `tests/resources/`
  suite: **92 passed.**
- **Benchmark.** `custom allocate+release (gpu+money)` ≈ **249k ops/sec**; `exclusive lease
  acquire+release` ≈ **717k ops/sec** (stdlib timing; no new dependency).
- **Design note for the owner.** The taxonomy stops at two lifecycles (renewable/consumable);
  the exclusive-lease semantic is delivered as a *separate* primitive (`LeaseManager`) rather
  than folded into `ResourceManager.allocate`, because leases need TTL/fencing/preemption that
  the min/preferred/max pool model doesn't. A future step could unify them under one façade —
  flagged as a deliberate boundary, not an omission.

---

## Evidence

- New/changed tests all pass. Full product suite (excluding the 5 slow `test_doctrine_*`
  tooling files): **1002 passed, 0 failed** (187s) — the prior 966 baseline + 36 new #6
  tests, no regressions. Owner should re-run in the MAPLE dev environment
  (`pip install -e ".[dev]"` for `pytest-asyncio` + `pytest-cov` + `psutil`).
- Benchmarks: `python benchmarks/bench_improvements.py` (stdlib timing; no new dependency).

## Files touched (uncommitted)

```text
maple/error/recovery.py                 (#1 max_delay; #5b basicConfig)
maple/autonomy/mcp_tools.py             (#2 governance hooks + sanitize)
maple/monitoring/health_monitor.py      (#3 snapshot + on-demand summary)
maple/core/message.py                   (#5a utcnow)
maple/security/cryptography_impl.py     (#5a utcnow)
maple/agent/agent.py                    (#5b basicConfig)
maple/broker/broker.py                  (#5b basicConfig)
maple/communication/streaming.py        (#5b basicConfig)
maple/error/circuit_breaker.py          (#5b basicConfig)
maple/resources/manager.py              (#5b basicConfig; #6 lifecycle + custom dims)
maple/resources/negotiation.py          (#5b basicConfig)
maple/resources/specification.py        (#6 ResourceRequest.custom)
maple/resources/lease.py                (#6 new: LeaseManager / Lease)
maple/resources/__init__.py             (#6 exports)
maple/__init__.py                       (#6 top-level exports)
tests/error/test_backoff_max_delay.py           (new)
tests/autonomy/test_mcp_governance.py           (new)
tests/monitoring/test_health_snapshot.py        (new)
tests/monitoring/test_health_monitor.py         (updated: no_data -> live)
tests/resources/test_resource_model.py          (#6 new)
tests/test_hygiene.py                           (new)
benchmarks/bench_improvements.py                (new; #1/#2/#3/#6)
docs/proposed-improvements-2026-08.md           (this file)
```

**No version change. No commit. Revalidate with the owner.**
