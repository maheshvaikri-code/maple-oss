"""Tests for maple.security.audit - AuditLogger."""

import pytest
import time
import os
import tempfile
from maple.security.audit import (
    AuditLogger, AuditEvent, AuditEventType, AuditSeverity,
    get_audit_logger, configure_audit_logger
)


@pytest.fixture
def logger():
    return AuditLogger(max_events_memory=100)


class TestAuditEventType:
    """Test AuditEventType enum."""

    def test_all_types(self):
        assert AuditEventType.AUTHENTICATION_SUCCESS.value == "AUTHENTICATION_SUCCESS"
        assert AuditEventType.AUTHENTICATION_FAILURE.value == "AUTHENTICATION_FAILURE"
        assert AuditEventType.AUTHORIZATION_GRANTED.value == "AUTHORIZATION_GRANTED"
        assert AuditEventType.AUTHORIZATION_DENIED.value == "AUTHORIZATION_DENIED"
        assert AuditEventType.LINK_ESTABLISHED.value == "LINK_ESTABLISHED"
        assert AuditEventType.SECURITY_VIOLATION.value == "SECURITY_VIOLATION"
        assert AuditEventType.TOKEN_ISSUED.value == "TOKEN_ISSUED"
        assert AuditEventType.TOKEN_REVOKED.value == "TOKEN_REVOKED"


class TestAuditEvent:
    """Test AuditEvent dataclass."""

    def test_to_dict(self):
        event = AuditEvent(
            event_id="evt_1",
            timestamp=1000000.0,
            event_type=AuditEventType.AUTHENTICATION_SUCCESS,
            severity=AuditSeverity.LOW,
            agent_id="agent_1",
            principal="user_1",
            resource="login",
            action="authenticate",
            result="SUCCESS",
            details={"method": "token"}
        )
        d = event.to_dict()
        assert d['event_id'] == "evt_1"
        assert d['event_type'] == "AUTHENTICATION_SUCCESS"
        assert d['severity'] == "LOW"
        assert d['agent_id'] == "agent_1"
        assert d['result'] == "SUCCESS"
        assert 'iso_timestamp' in d

    def test_optional_fields(self):
        event = AuditEvent(
            event_id="evt_2",
            timestamp=1000000.0,
            event_type=AuditEventType.LINK_FAILED,
            severity=AuditSeverity.HIGH,
            agent_id=None,
            principal=None,
            resource=None,
            action=None,
            result="FAILURE",
            details={},
            source_ip="192.168.1.1",
            session_id="sess_1"
        )
        d = event.to_dict()
        assert d['agent_id'] is None
        assert d['source_ip'] == "192.168.1.1"
        assert d['session_id'] == "sess_1"


class TestLogEvent:
    """Test core log_event method."""

    def test_log_event_returns_event_id(self, logger):
        event_id = logger.log_event(
            event_type=AuditEventType.AUTHENTICATION_SUCCESS,
            severity=AuditSeverity.LOW,
            result="SUCCESS",
            agent_id="agent_1"
        )
        assert event_id is not None
        assert isinstance(event_id, str)
        assert len(event_id) > 0

    def test_log_event_stored_in_memory(self, logger):
        logger.log_event(
            event_type=AuditEventType.AUTHENTICATION_SUCCESS,
            severity=AuditSeverity.LOW,
            result="SUCCESS"
        )
        assert len(logger.events) == 1

    def test_log_event_updates_counts(self, logger):
        logger.log_event(
            event_type=AuditEventType.AUTHENTICATION_SUCCESS,
            severity=AuditSeverity.LOW,
            result="SUCCESS"
        )
        assert logger.event_counts["AUTHENTICATION_SUCCESS"] == 1

    def test_log_event_memory_limit(self):
        small_logger = AuditLogger(max_events_memory=5)
        for i in range(10):
            small_logger.log_event(
                event_type=AuditEventType.AUTHENTICATION_SUCCESS,
                severity=AuditSeverity.LOW,
                result="SUCCESS"
            )
        assert len(small_logger.events) == 5

    def test_log_event_with_all_fields(self, logger):
        event_id = logger.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            severity=AuditSeverity.CRITICAL,
            result="VIOLATION",
            agent_id="agent_1",
            principal="user_1",
            resource="admin_panel",
            action="access",
            details={"ip": "10.0.0.1"},
            source_ip="10.0.0.1",
            session_id="sess_123"
        )
        events = logger.get_events()
        assert len(events) == 1
        assert events[0].event_id == event_id
        assert events[0].source_ip == "10.0.0.1"


class TestConvenienceMethods:
    """Test convenience logging methods."""

    def test_log_authentication_success(self, logger):
        event_id = logger.log_authentication_success("user_1", "agent_1", "token", "sess_1")
        assert event_id is not None
        events = logger.get_events(event_type=AuditEventType.AUTHENTICATION_SUCCESS)
        assert len(events) == 1
        assert events[0].result == "SUCCESS"

    def test_log_authentication_failure(self, logger):
        event_id = logger.log_authentication_failure("user_1", "agent_1", "bad_password", "10.0.0.1")
        assert event_id is not None
        events = logger.get_events(event_type=AuditEventType.AUTHENTICATION_FAILURE)
        assert len(events) == 1
        assert events[0].severity == AuditSeverity.MEDIUM

    def test_log_authorization_granted(self, logger):
        event_id = logger.log_authorization_granted("user_1", "data:test", "read", "agent_1")
        assert event_id is not None
        events = logger.get_events(event_type=AuditEventType.AUTHORIZATION_GRANTED)
        assert len(events) == 1

    def test_log_authorization_denied(self, logger):
        event_id = logger.log_authorization_denied("user_1", "admin:config", "write", "no_permission", "agent_1")
        assert event_id is not None
        events = logger.get_events(event_type=AuditEventType.AUTHORIZATION_DENIED)
        assert len(events) == 1
        assert events[0].severity == AuditSeverity.HIGH

    def test_log_link_established(self, logger):
        event_id = logger.log_link_established(
            "agent_a", "agent_b", "link_1",
            {"cipher_suite": "AES256-GCM", "key_length": 256}
        )
        assert event_id is not None
        events = logger.get_events(event_type=AuditEventType.LINK_ESTABLISHED)
        assert len(events) == 1

    def test_log_link_failed(self, logger):
        event_id = logger.log_link_failed("agent_a", "agent_b", "timeout")
        assert event_id is not None
        events = logger.get_events(event_type=AuditEventType.LINK_FAILED)
        assert len(events) == 1

    def test_log_security_violation(self, logger):
        event_id = logger.log_security_violation(
            "agent_1", "brute_force", {"attempts": 100}
        )
        assert event_id is not None
        events = logger.get_events(severity=AuditSeverity.CRITICAL)
        assert len(events) == 1

    def test_log_token_issued(self, logger):
        event_id = logger.log_token_issued("user_1", "jwt", 3600, ["read", "write"])
        assert event_id is not None
        events = logger.get_events(event_type=AuditEventType.TOKEN_ISSUED)
        assert len(events) == 1

    def test_log_token_revoked(self, logger):
        event_id = logger.log_token_revoked("user_1", "tok_123", "user_request")
        assert event_id is not None
        events = logger.get_events(event_type=AuditEventType.TOKEN_REVOKED)
        assert len(events) == 1


class TestGetEvents:
    """Test event retrieval with filters."""

    def test_get_all_events(self, logger):
        logger.log_authentication_success("u1", "a1", "token", "s1")
        logger.log_authentication_failure("u2", "a2", "bad_pass")
        events = logger.get_events()
        assert len(events) == 2

    def test_filter_by_type(self, logger):
        logger.log_authentication_success("u1", "a1", "token", "s1")
        logger.log_authentication_failure("u2", "a2", "bad_pass")
        events = logger.get_events(event_type=AuditEventType.AUTHENTICATION_SUCCESS)
        assert len(events) == 1

    def test_filter_by_severity(self, logger):
        logger.log_authentication_success("u1", "a1", "token", "s1")  # LOW
        logger.log_security_violation("a1", "brute_force", {})  # CRITICAL
        events = logger.get_events(severity=AuditSeverity.CRITICAL)
        assert len(events) == 1

    def test_filter_by_principal(self, logger):
        logger.log_authentication_success("user_a", "a1", "token", "s1")
        logger.log_authentication_success("user_b", "a2", "token", "s2")
        events = logger.get_events(principal="user_a")
        assert len(events) == 1

    def test_filter_by_since(self, logger):
        logger.log_authentication_success("u1", "a1", "token", "s1")
        time.sleep(0.05)
        since = time.time()
        time.sleep(0.05)
        logger.log_authentication_success("u2", "a2", "token", "s2")
        events = logger.get_events(since=since)
        assert len(events) == 1

    def test_limit(self, logger):
        for i in range(10):
            logger.log_authentication_success(f"u{i}", f"a{i}", "token", f"s{i}")
        events = logger.get_events(limit=3)
        assert len(events) == 3

    def test_events_sorted_newest_first(self, logger):
        logger.log_authentication_success("first", "a1", "token", "s1")
        time.sleep(0.01)
        logger.log_authentication_success("second", "a2", "token", "s2")
        events = logger.get_events()
        assert events[0].principal == "second"
        assert events[1].principal == "first"


class TestStatistics:
    """Test audit statistics."""

    def test_empty_stats(self, logger):
        stats = logger.get_statistics()
        assert stats['total_events'] == 0

    def test_stats_with_events(self, logger):
        logger.log_authentication_success("u1", "a1", "token", "s1")
        logger.log_authentication_failure("u2", "a2", "bad_pass")
        logger.log_security_violation("a3", "brute_force", {})

        stats = logger.get_statistics()
        assert stats['total_events'] == 3
        assert "AUTHENTICATION_SUCCESS" in stats['event_type_counts']
        assert stats['event_type_counts']['AUTHENTICATION_SUCCESS'] == 1
        assert "LOW" in stats['severity_counts']
        assert "SUCCESS" in stats['result_counts']
        assert stats['recent_events_count'] == 3

    def test_stats_timestamps(self, logger):
        logger.log_authentication_success("u1", "a1", "token", "s1")
        time.sleep(0.01)
        logger.log_authentication_success("u2", "a2", "token", "s2")

        stats = logger.get_statistics()
        assert stats['oldest_event_timestamp'] <= stats['newest_event_timestamp']


class TestFileLogging:
    """Test file-based audit logging."""

    def test_write_to_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            log_path = f.name

        try:
            file_logger = AuditLogger(log_file=log_path)
            file_logger.log_authentication_success("u1", "a1", "token", "s1")

            with open(log_path, 'r') as f:
                content = f.read()
            assert "AUTHENTICATION_SUCCESS" in content
        finally:
            os.unlink(log_path)

    def test_flush_is_noop(self, logger):
        logger.flush_to_file()  # Should not raise


class TestGlobalLogger:
    """Test global audit logger functions."""

    def test_configure_and_get(self):
        configure_audit_logger(log_file=None, enable_console=False, max_events_memory=50)
        audit = get_audit_logger()
        assert isinstance(audit, AuditLogger)
        assert audit.max_events_memory == 50
