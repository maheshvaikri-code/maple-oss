"""Tests for maple.security.link - LinkManager and Link."""

import pytest
import time
from maple.security.link import LinkManager, Link, LinkState


@pytest.fixture
def manager():
    return LinkManager()


class TestLink:
    """Test Link dataclass behavior."""

    def test_link_creation(self):
        link = Link("agent_a", "agent_b")
        assert link.agent_a == "agent_a"
        assert link.agent_b == "agent_b"
        assert link.state == LinkState.INITIATING
        assert link.link_id.startswith("link_")
        assert link.shared_key is None

    def test_link_custom_id(self):
        link = Link("a", "b", link_id="custom_id")
        assert link.link_id == "custom_id"

    def test_link_establish(self):
        link = Link("a", "b")
        link.establish(3600)
        assert link.state == LinkState.ESTABLISHED
        assert link.established_at is not None
        assert link.expires_at > time.time()

    def test_link_not_expired(self):
        link = Link("a", "b")
        link.establish(3600)
        assert link.is_expired() is False

    def test_link_expired(self):
        link = Link("a", "b")
        link.establish(0)  # expires immediately
        time.sleep(0.01)
        assert link.is_expired() is True

    def test_link_terminate(self):
        link = Link("a", "b")
        link.shared_key = b"secret"
        link.terminate()
        assert link.state == LinkState.TERMINATED
        assert link.shared_key is None


class TestLinkManager:
    """Test LinkManager lifecycle operations."""

    def test_initiate_link(self, manager):
        link = manager.initiate_link("agent_a", "agent_b")
        assert link.agent_a == "agent_a"
        assert link.agent_b == "agent_b"
        assert link.state == LinkState.INITIATING
        assert link.link_id in manager.links

    def test_establish_link(self, manager):
        link = manager.initiate_link("agent_a", "agent_b")
        result = manager.establish_link(link.link_id)
        assert result.is_ok()

        established = result.unwrap()
        assert established.state == LinkState.ESTABLISHED
        assert established.established_at is not None

    def test_establish_link_has_crypto(self, manager):
        """When crypto is available, established links should have shared keys."""
        link = manager.initiate_link("agent_a", "agent_b")
        result = manager.establish_link(link.link_id)
        assert result.is_ok()

        established = result.unwrap()
        if manager.has_real_crypto:
            assert established.shared_key is not None
            assert len(established.shared_key) == 32  # 256-bit key
            assert established.encryption_params.get('has_shared_key') is True

    def test_establish_nonexistent_link(self, manager):
        result = manager.establish_link("nonexistent_link_id")
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'UNKNOWN_LINK'

    def test_validate_link(self, manager):
        link = manager.initiate_link("agent_a", "agent_b")
        manager.establish_link(link.link_id)

        result = manager.validate_link(link.link_id, "agent_a", "agent_b")
        assert result.is_ok()

    def test_validate_link_reverse_direction(self, manager):
        link = manager.initiate_link("agent_a", "agent_b")
        manager.establish_link(link.link_id)

        result = manager.validate_link(link.link_id, "agent_b", "agent_a")
        assert result.is_ok()

    def test_validate_nonexistent_link(self, manager):
        result = manager.validate_link("nonexistent", "a", "b")
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'INVALID_LINK'

    def test_validate_unestablished_link(self, manager):
        link = manager.initiate_link("agent_a", "agent_b")
        result = manager.validate_link(link.link_id, "agent_a", "agent_b")
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'LINK_NOT_ESTABLISHED'

    def test_validate_expired_link(self, manager):
        link = manager.initiate_link("agent_a", "agent_b")
        manager.establish_link(link.link_id, lifetime_seconds=0)
        time.sleep(0.01)

        result = manager.validate_link(link.link_id, "agent_a", "agent_b")
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'EXPIRED_LINK'

    def test_validate_unauthorized_agents(self, manager):
        link = manager.initiate_link("agent_a", "agent_b")
        manager.establish_link(link.link_id)

        result = manager.validate_link(link.link_id, "agent_c", "agent_d")
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'UNAUTHORIZED_LINK_USAGE'

    def test_terminate_link(self, manager):
        link = manager.initiate_link("agent_a", "agent_b")
        manager.establish_link(link.link_id)

        result = manager.terminate_link(link.link_id)
        assert result.is_ok()
        assert link.state == LinkState.TERMINATED

    def test_terminate_nonexistent_link(self, manager):
        result = manager.terminate_link("nonexistent")
        assert result.is_err()

    def test_get_links_for_agent(self, manager):
        link1 = manager.initiate_link("agent_a", "agent_b")
        link2 = manager.initiate_link("agent_a", "agent_c")
        manager.establish_link(link1.link_id)
        manager.establish_link(link2.link_id)

        result = manager.get_links_for_agent("agent_a")
        assert result.is_ok()
        links = result.unwrap()
        assert len(links) == 2

    def test_get_links_for_unknown_agent(self, manager):
        result = manager.get_links_for_agent("unknown")
        assert result.is_ok()
        assert len(result.unwrap()) == 0

    def test_get_links_excludes_terminated(self, manager):
        link = manager.initiate_link("agent_a", "agent_b")
        manager.establish_link(link.link_id)
        manager.terminate_link(link.link_id)

        result = manager.get_links_for_agent("agent_a")
        assert result.is_ok()
        assert len(result.unwrap()) == 0

    def test_multiple_links_between_same_agents(self, manager):
        link1 = manager.initiate_link("agent_a", "agent_b")
        link2 = manager.initiate_link("agent_a", "agent_b")
        manager.establish_link(link1.link_id)
        manager.establish_link(link2.link_id)

        assert link1.link_id != link2.link_id
        assert len(manager.links) == 2
