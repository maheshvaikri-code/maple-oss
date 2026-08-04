"""Benchmarks for the proposed MAPLE improvements (revalidate with owner).

Standalone + dependency-free (stdlib ``time`` only). Run:

    python benchmarks/bench_improvements.py

Reports real, measured numbers for the three code changes:
  #1 exponential_backoff(max_delay=...) -- worst-case total retry sleep, bounded vs unbounded
  #3 HealthMonitor.snapshot()          -- on-demand health-read throughput
  #2 register_mcp_tools governance     -- registration throughput with/without policy+namespace
"""

from __future__ import annotations

import pathlib
import sys
import time

# Run against the SOURCE tree (this repo), not any installed maple wheel.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from maple.autonomy.mcp_tools import register_mcp_tools
from maple.autonomy.tools import Tool, ToolRegistry
from maple.core.result import Result
from maple.error.recovery import exponential_backoff
from maple.monitoring.health_monitor import HealthMonitor
from maple.resources.lease import LeaseManager
from maple.resources.manager import ResourceManager
from maple.resources.specification import ResourceRange, ResourceRequest


def _t(fn, iters):
    """Return (ops_per_sec, seconds_total) for `iters` calls of `fn`."""
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    dt = time.perf_counter() - t0
    return (iters / dt if dt else float("inf")), dt


def bench_backoff_cap():
    """#1: the whole point of max_delay -- the total sleep a worst-case retry would incur."""
    attempts = 12
    uncapped = exponential_backoff(initial=0.1, factor=2.0, jitter=0.0)
    capped = exponential_backoff(initial=0.1, factor=2.0, jitter=0.0, max_delay=2.0)
    total_uncapped = sum(uncapped(n) for n in range(attempts))
    total_capped = sum(capped(n) for n in range(attempts))
    print(f"#1 backoff (12 attempts) total sleep: "
          f"uncapped={total_uncapped:8.1f}s   capped(2.0s)={total_capped:6.1f}s   "
          f"reduction={total_uncapped / total_capped:6.1f}x")


def bench_health_snapshot():
    """#3: on-demand snapshot throughput (a status endpoint would call this)."""
    m = HealthMonitor("bench")
    for _ in range(100):
        m.record_message(0.01)
    ops, _ = _t(m.snapshot, 20000)
    print(f"#3 HealthMonitor.snapshot(): {ops:12,.0f} ops/sec  (immediate, no sampling wait)")


def bench_mcp_registration():
    """#2: registration throughput -- governance (policy + namespace) overhead vs plain."""
    tools = [
        Tool(name=f"t{i}", description="d", parameters={}, handler=lambda **k: Result.ok("x"),
             tags=["mcp"])
        for i in range(500)
    ]

    def plain():
        register_mcp_tools(ToolRegistry(), tools)

    def governed():
        register_mcp_tools(ToolRegistry(), tools, server_id="srv", namespace=True,
                           policy=lambda t, s: True, max_tools=1000)

    ops_plain, _ = _t(plain, 20)
    ops_gov, _ = _t(governed, 20)
    overhead = (ops_plain / ops_gov - 1) * 100 if ops_gov else 0
    print(f"#2 register_mcp_tools (500 tools/call): "
          f"plain={ops_plain * 500:10,.0f} tools/s   governed={ops_gov * 500:10,.0f} tools/s   "
          f"governance overhead={overhead:5.1f}%")


def bench_resource_model():
    """#6: custom-dimension allocate+release and exclusive-lease acquire+release throughput."""
    # A mixed request: a renewable pool (gpu, refunded) + a consumable budget (money, spent).
    rm = ResourceManager()
    rm.register_resource("gpu", 10 ** 9)      # renewable
    rm.register_resource("money", 10 ** 12)   # consumable (depletes; sized so 20k calls fit)
    req = ResourceRequest(custom={
        "gpu": ResourceRange(min=1, preferred=1),
        "money": ResourceRange(min=1, preferred=1),
    })

    def alloc_release():
        a = rm.allocate(req).unwrap()
        rm.release(a)

    ops, _ = _t(alloc_release, 20000)
    print(f"#6 custom allocate+release (gpu+money): {ops:12,.0f} ops/sec")

    # Exclusive lease: acquire then release a device lease (ttl far larger than the run).
    lm = LeaseManager()

    def lease_cycle():
        lease = lm.acquire("device0", "agentA", ttl_seconds=3600).unwrap()
        lm.release(lease)

    ops2, _ = _t(lease_cycle, 20000)
    print(f"#6 exclusive lease acquire+release:     {ops2:12,.0f} ops/sec")


def main():
    print("=" * 78)
    print("MAPLE proposed-improvement benchmarks (stdlib timing; revalidate with owner)")
    print("=" * 78)
    bench_backoff_cap()
    bench_health_snapshot()
    bench_mcp_registration()
    bench_resource_model()
    print("=" * 78)


if __name__ == "__main__":
    main()
