# Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy
# (Mahesh Vaikri)
#
# This file is part of MAPLE - Multi Agent Protocol Language Engine.
#
# MAPLE - Multi Agent Protocol Language Engine is free software: you can
# redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.
# MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details. You should have received a copy of
# the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
# Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""FileBroker across a real process boundary (ADR-167).

The conformance suite proves the contract in one process. This proves the
thing the transport exists for: that a message written by one OS process is
delivered in another, exactly once.

Every test here spawns real subprocesses. Nothing is simulated.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import pytest

from maple import Config
from maple.broker.file_broker import FileBroker, spool_path_from_url

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def spool():
    root = Path(tempfile.mkdtemp(prefix="maple-xproc-"))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_child(script_body, *args, timeout=60):
    """Run a snippet in a separate interpreter with MAPLE importable."""
    script = (
        textwrap.dedent(
            """
        import json, sys, time
        sys.path.insert(0, {root!r})
        from maple import Config
        from maple.broker.file_broker import FileBroker
        from maple.core.message import Message
        """
        ).format(root=str(REPO_ROOT))
        + textwrap.dedent(script_body)
    )
    return subprocess.run(
        [sys.executable, "-c", script, *[str(a) for a in args]],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def broker_for(root, agent_id="local", **perf):
    from maple.agent.config import PerformanceConfig

    return FileBroker(
        Config(
            agent_id=agent_id,
            broker_url=root.as_uri(),
            performance=PerformanceConfig(**perf) if perf else None,
        )
    )


CONSUMER = """
    root, agent, out, count = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    broker = FileBroker(Config(agent_id=agent, broker_url=root))
    got = []
    broker.subscribe(agent, lambda m: got.append(m.payload.get("i")))
    broker.connect()
    deadline = time.time() + 30
    while len(got) < count and time.time() < deadline:
        time.sleep(0.01)
    broker.disconnect()
    open(out, "w", encoding="utf-8").write(json.dumps(got))
"""


class TestAMessageCrossesTheProcessBoundary:
    def test_one_producer_one_consumer(self, spool):
        out = spool / "consumer.json"
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                textwrap.dedent(
                    "import json, sys, time\n"
                    f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
                    "from maple import Config\n"
                    "from maple.broker.file_broker import FileBroker\n"
                )
                + textwrap.dedent(CONSUMER),
                spool.as_uri(),
                "worker",
                str(out),
                "5",
            ]
        )
        try:
            producer = broker_for(spool, "producer")
            # wait for the consumer to announce presence
            deadline = time.time() + 30
            while not producer.is_routable("worker") and time.time() < deadline:
                time.sleep(0.02)
            assert producer.is_routable(
                "worker"
            ), "the other process never announced presence"

            from maple.core.message import Message

            for i in range(5):
                producer.send(
                    Message(message_type="WORK", receiver="worker", payload={"i": i})
                )
            child.wait(timeout=60)
        finally:
            if child.poll() is None:
                child.kill()

        assert out.exists(), "the consumer process wrote no result"
        assert sorted(json.loads(out.read_text("utf-8"))) == [0, 1, 2, 3, 4]

    def test_presence_is_visible_across_processes(self, spool):
        local = broker_for(spool, "local")
        assert local.is_routable("remote") is False

        result = run_child(
            """
            root, agent = sys.argv[1], sys.argv[2]
            broker = FileBroker(Config(agent_id=agent, broker_url=root))
            broker.subscribe(agent, lambda m: None)
            print("SUBSCRIBED")
            """,
            spool.as_uri(),
            "remote",
        )
        assert "SUBSCRIBED" in result.stdout, result.stderr
        assert (
            local.is_routable("remote") is True
        ), "a subscription made in another process was not visible"


class TestExactlyOneConsumerTakesEachMessage:
    """The property claim-by-rename could not provide on this platform, and
    the reason the spool lock is used instead (ADR-167)."""

    def test_competing_consumers_do_not_double_deliver(self, spool):
        producer = broker_for(spool, "producer")
        from maple.core.message import Message

        total = 60
        for i in range(total):
            producer.send(
                Message(message_type="WORK", receiver="shared", payload={"i": i})
            )

        outs = [spool / f"c{n}.json" for n in range(3)]
        children = []
        body = (
            "import json, sys, time\n"
            f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
            "from maple import Config\n"
            "from maple.broker.file_broker import FileBroker\n"
            + textwrap.dedent(
                """
                root, agent, out = sys.argv[1], sys.argv[2], sys.argv[3]
                broker = FileBroker(Config(agent_id=agent, broker_url=root))
                got = []
                broker.subscribe(agent, lambda m: got.append(m.payload.get("i")))
                broker.connect()
                time.sleep(4.0)
                broker.disconnect()
                open(out, "w", encoding="utf-8").write(json.dumps(got))
                """
            )
        )
        for out in outs:
            children.append(
                subprocess.Popen(
                    [sys.executable, "-c", body, spool.as_uri(), "shared", str(out)]
                )
            )
        try:
            for child in children:
                child.wait(timeout=90)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()

        delivered = []
        for out in outs:
            assert out.exists(), "a consumer process wrote no result"
            delivered += json.loads(out.read_text("utf-8"))

        assert sorted(delivered) == list(range(total)), (
            f"expected each of {total} messages exactly once, got "
            f"{len(delivered)} deliveries with "
            f"{len(delivered) - len(set(delivered))} duplicates"
        )


class TestSeveralProcessesMayServeTheSameAgent:
    """Competing consumers is the case this transport exists for, so two
    brokers serving one agent id must not write the same files.

    CI caught this and a local run did not: on Windows, ``os.replace`` onto a
    destination another process holds open fails with PermissionError, and
    three consumers refreshing one shared presence file collided until the
    child processes died (ADR-167).
    """

    def test_presence_files_are_per_instance(self, spool):
        first = broker_for(spool, "a")
        second = broker_for(spool, "b")

        assert first._presence_path("shared") != second._presence_path("shared"), (
            "two brokers serving the same agent share a presence path, so "
            "they will race os.replace on it"
        )

    def test_presence_written_by_one_is_seen_by_the_other(self, spool):
        first = broker_for(spool, "a")
        second = broker_for(spool, "b")

        assert second.is_routable("shared") is False
        first.subscribe("shared", lambda m: None)
        assert second.is_routable("shared") is True

    def test_one_leaving_does_not_unregister_the_other(self, spool):
        first = broker_for(spool, "a")
        second = broker_for(spool, "b")
        first.subscribe("shared", lambda m: None)
        second.subscribe("shared", lambda m: None)

        first.unsubscribe("shared")
        assert (
            second.is_routable("shared") is True
        ), "one consumer leaving removed presence for the others"

    def test_concurrent_presence_refresh_does_not_raise(self, spool):
        """The collision CI hit, driven hard in-process."""
        import threading

        brokers = [broker_for(spool, f"b{n}") for n in range(4)]
        errors = []

        def hammer(broker):
            try:
                for _ in range(60):
                    broker._touch_presence("shared")
            except Exception as exc:  # pragma: no cover - the failure path
                errors.append(exc)

        threads = [threading.Thread(target=hammer, args=(b,)) for b in brokers]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"presence refresh raised: {errors[:2]}"

    def test_a_topic_subscriber_served_twice_receives_once(self, spool):
        """Two processes serving one agent must not double the fan-out."""
        from maple.core.message import Message

        first = broker_for(spool, "a")
        second = broker_for(spool, "b")
        first.subscribe_topic("news", lambda t, m: None, agent_id="reader")
        second.subscribe_topic("news", lambda t, m: None, agent_id="reader")

        publisher = broker_for(spool, "pub")
        publisher.publish(
            "news", Message(message_type="NEWS", receiver="reader", payload={})
        )

        queued = list((spool / "inbox" / "reader").glob("*.json"))
        assert len(queued) == 1, f"fanned out {len(queued)} copies to one agent"


class TestSpoolUrlParsing:
    def test_a_posix_url(self):
        assert spool_path_from_url("file:///var/run/maple").name == "maple"

    def test_a_bare_path_is_accepted(self, tmp_path):
        assert spool_path_from_url(str(tmp_path)) == tmp_path

    def test_a_round_trip_through_as_uri(self, tmp_path):
        assert spool_path_from_url(tmp_path.as_uri()) == tmp_path

    @pytest.mark.parametrize("value", ["", "   "])
    def test_an_empty_url_is_refused(self, value):
        with pytest.raises(ValueError):
            spool_path_from_url(value)


class TestMessagesOutliveTheProcessThatSentThem:
    def test_a_message_waits_in_the_spool(self, spool):
        """Not a durability guarantee - just that the queue is on disk."""
        producer = broker_for(spool, "producer")
        from maple.core.message import Message

        producer.send(
            Message(message_type="LATER", receiver="notyet", payload={"i": 1})
        )
        del producer

        pending = list((spool / "inbox" / "notyet").glob("*.json"))
        assert len(pending) == 1

        record = json.loads(pending[0].read_text("utf-8"))
        assert record["receiver"] == "notyet"
        assert record["message"]["payload"]["i"] == 1

    def test_a_later_process_picks_it_up(self, spool):
        producer = broker_for(spool, "producer")
        from maple.core.message import Message

        producer.send(
            Message(message_type="LATER", receiver="worker", payload={"i": 42})
        )

        out = spool / "later.json"
        result = run_child(
            """
            root, agent, out = sys.argv[1], sys.argv[2], sys.argv[3]
            broker = FileBroker(Config(agent_id=agent, broker_url=root))
            got = []
            broker.subscribe(agent, lambda m: got.append(m.payload.get("i")))
            broker.connect()
            deadline = time.time() + 20
            while not got and time.time() < deadline:
                time.sleep(0.01)
            broker.disconnect()
            open(out, "w", encoding="utf-8").write(json.dumps(got))
            """,
            spool.as_uri(),
            "worker",
            str(out),
        )
        assert out.exists(), result.stderr
        assert json.loads(out.read_text("utf-8")) == [42]


class TestBackpressureIsSharedAcrossProcesses:
    def test_the_bound_counts_what_another_process_queued(self, spool):
        """The spool is the queue, so the limit is a property of the spool and
        not of one process's memory."""
        from maple.core.message import Message

        first = broker_for(spool, "p1", max_queue_size=3)
        for _ in range(3):
            first.send(Message(message_type="X", receiver="stalled", payload={}))

        # a *different* broker instance sees the same full queue
        second = broker_for(spool, "p2", max_queue_size=3)
        from maple.error.types import BrokerOverflowError

        with pytest.raises(BrokerOverflowError) as excinfo:
            second.send(Message(message_type="X", receiver="stalled", payload={}))
        assert excinfo.value.error["errorType"] == "QUEUE_FULL"
