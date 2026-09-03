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
"""Configuration is refused at construction, not three layers later (ADR-164).

Measured before this existed: nine invalid configurations all accepted.
``agent_id=""`` produced an agent whose every ``send()`` returned ``Ok`` and
delivered nothing; ``max_queue_size=-5`` made every send fail ``QUEUE_FULL``
with no full queue to find.
"""

import pytest

from maple import Config
from maple.agent.config import PerformanceConfig
from maple.error.types import ConfigurationError

MEMORY = "memory://test"


class TestAgentId:
    @pytest.mark.parametrize("value", ["", "   ", "\t", "\n"])
    def test_blank_is_refused(self, value):
        """An agent with no id is unroutable: every send to it returns Ok and
        delivers nothing."""
        with pytest.raises(ConfigurationError) as excinfo:
            Config(agent_id=value, broker_url=MEMORY)
        assert excinfo.value.field == "agent_id"

    @pytest.mark.parametrize("value", [None, 12345, 1.5, [], {}, object()])
    def test_non_strings_are_refused(self, value):
        with pytest.raises(ConfigurationError) as excinfo:
            Config(agent_id=value, broker_url=MEMORY)
        assert excinfo.value.field == "agent_id"
        assert type(value).__name__ in str(excinfo.value)

    def test_a_normal_id_is_accepted(self):
        assert Config(agent_id="worker-1", broker_url=MEMORY).agent_id == "worker-1"

    def test_surrounding_whitespace_is_not_silently_stripped(self):
        """Validation refuses blanks; it does not quietly rewrite values."""
        assert Config(agent_id=" worker ", broker_url=MEMORY).agent_id == " worker "


class TestBrokerUrl:
    def test_empty_is_refused(self):
        with pytest.raises(ConfigurationError) as excinfo:
            Config(agent_id="a", broker_url="")
        assert excinfo.value.field == "broker_url"

    @pytest.mark.parametrize("value", [None, 42, [], {}])
    def test_non_strings_are_refused(self, value):
        with pytest.raises(ConfigurationError) as excinfo:
            Config(agent_id="a", broker_url=value)
        assert excinfo.value.field == "broker_url"

    @pytest.mark.parametrize(
        "url", ["memory://scope", "nats://host:4222", "s2://stream"]
    )
    def test_supported_schemes_are_accepted(self, url):
        assert Config(agent_id="a", broker_url=url).broker_url == url

    @pytest.mark.parametrize(
        "url", ["MEMORY://s", "NATS://host", "Nats://host", "S2://x"]
    )
    def test_case_does_not_change_whether_a_scheme_is_known(self, url):
        """URI schemes are case-insensitive (RFC 3986). NATS:// used to miss
        the transport dispatch and fall back to in-process."""
        assert Config(agent_id="a", broker_url=url).broker_url == url

    @pytest.mark.parametrize("url", ["nats:/host:4222", "s2:/x", "memory:/scope"])
    def test_a_known_transport_must_be_spelled_as_a_url(self, url):
        """One missing slash was enough to fall back to the in-process broker
        while the deployment looked healthy."""
        with pytest.raises(ConfigurationError) as excinfo:
            Config(agent_id="a", broker_url=url)
        assert excinfo.value.field == "broker_url"
        assert "://" in str(excinfo.value), "the error should show the right form"

    @pytest.mark.parametrize(
        "url", ["natss://h", "redis://h", "kafka://h", "amqp://h", "http://h"]
    )
    def test_unsupported_schemes_are_refused(self, url):
        with pytest.raises(ConfigurationError) as excinfo:
            Config(agent_id="a", broker_url=url)
        assert excinfo.value.field == "broker_url"
        assert excinfo.value.error["details"]["supportedSchemes"]

    @pytest.mark.parametrize(
        "url", ["localhost:8080", "localhost", "my-broker-host", "127.0.0.1:9000"]
    )
    def test_scheme_less_values_still_work(self, url):
        """8 places including examples/helloworld.py use 'localhost:8080'.
        Nobody types that believing they configured a cluster, so refusing it
        would break the flagship example to prevent a mistake nobody makes."""
        assert Config(agent_id="a", broker_url=url).broker_url == url

    def test_the_error_names_what_would_have_happened(self):
        with pytest.raises(ConfigurationError) as excinfo:
            Config(agent_id="a", broker_url="redis://h")
        message = str(excinfo.value)
        assert "in-process" in message and "stay local" in message


class TestPerformanceBounds:
    @pytest.mark.parametrize(
        "name",
        [
            "connection_pool_size",
            "max_concurrent_requests",
            "max_queue_size",
            "max_message_bytes",
            "batch_size",
        ],
    )
    @pytest.mark.parametrize("value", [0, -1, -10000])
    def test_non_positive_is_refused(self, name, value):
        with pytest.raises(ConfigurationError) as excinfo:
            Config(
                agent_id="a",
                broker_url=MEMORY,
                performance=PerformanceConfig(**{name: value}),
            )
        assert excinfo.value.field == f"performance.{name}"

    @pytest.mark.parametrize("value", [1.5, "10", None.__class__, [1]])
    def test_non_integers_are_refused(self, value):
        with pytest.raises(ConfigurationError):
            Config(
                agent_id="a",
                broker_url=MEMORY,
                performance=PerformanceConfig(max_queue_size=value),
            )

    def test_booleans_are_not_integers_here(self):
        """True is an int in Python; it is not a queue size."""
        with pytest.raises(ConfigurationError):
            Config(
                agent_id="a",
                broker_url=MEMORY,
                performance=PerformanceConfig(max_queue_size=True),
            )

    def test_one_is_allowed(self):
        config = Config(
            agent_id="a",
            broker_url=MEMORY,
            performance=PerformanceConfig(max_queue_size=1),
        )
        assert config.performance.max_queue_size == 1

    def test_defaults_pass(self):
        assert Config(agent_id="a", broker_url=MEMORY, performance=PerformanceConfig())

    def test_no_performance_config_is_fine(self):
        assert Config(agent_id="a", broker_url=MEMORY).performance is None


class TestTheErrorItself:
    def test_it_is_a_value_error(self):
        """Callers already catch ValueError for a bad argument."""
        with pytest.raises(ValueError):
            Config(agent_id="", broker_url=MEMORY)

    def test_it_carries_a_typed_error_like_the_rest_of_maple(self):
        with pytest.raises(ConfigurationError) as excinfo:
            Config(agent_id="", broker_url=MEMORY)
        error = excinfo.value.error
        assert error["errorType"] == "INVALID_CONFIGURATION"
        assert error["details"]["field"] == "agent_id"
        assert error["message"]

    def test_validate_can_be_called_directly(self):
        config = Config(agent_id="a", broker_url=MEMORY)
        config.validate()  # must not raise

        config.agent_id = ""
        with pytest.raises(ConfigurationError):
            config.validate()


class TestTheSchemeListDoesNotDrift:
    """ADR-164: a new transport must be added to KNOWN_SCHEMES or its URLs are
    refused. This pins the list against what actually dispatches."""

    def test_every_dispatched_scheme_is_declared_known(self):
        import inspect

        from maple.agent.agent import Agent

        source = inspect.getsource(Agent._create_broker)
        dispatched = {
            part.split("://")[0].strip('"').strip("'").lower()
            for part in source.split()
            if "://" in part
        }
        dispatched = {name for name in dispatched if name.isalnum()}

        undeclared = dispatched - set(Config.KNOWN_SCHEMES)
        assert not undeclared, (
            f"_create_broker dispatches on {sorted(undeclared)}, which "
            "Config.KNOWN_SCHEMES does not list, so those URLs are refused "
            "before they ever reach the transport."
        )

    def test_memory_is_declared_even_though_it_is_the_fallback(self):
        assert "memory" in Config.KNOWN_SCHEMES

    def test_the_list_is_lowercase(self):
        """Comparison lowercases the input, so a capitalised entry here would
        never match."""
        assert all(s == s.lower() for s in Config.KNOWN_SCHEMES)


class TestRealAgentsStillBuild:
    def test_the_documented_helloworld_config_is_accepted(self):
        """examples/helloworld.py uses a scheme-less broker_url."""
        assert Config(agent_id="hello-agent", broker_url="localhost:8080")

    def test_a_full_config_is_accepted(self):
        from maple.agent.config import SecurityConfig

        assert Config(
            agent_id="worker",
            broker_url="memory://prod",
            capabilities=["compute"],
            security=SecurityConfig("jwt", {"token": "t"}),
            performance=PerformanceConfig(max_queue_size=500),
        )
