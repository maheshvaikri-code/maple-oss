"""Tests for maple.core.result - the Result[T, E] contract.

`result.py` is the type every fallible MAPLE API returns, and it had no
dedicated test module (68% coverage, exercised only incidentally through
callers). These cover the contract directly, including the typed failure
introduced in ADR-158.
"""

import pytest

from maple.core.result import Result, UnwrapError


class TestConstruction:
    def test_ok_is_ok_and_not_err(self):
        r = Result.ok(42)
        assert r.is_ok()
        assert not r.is_err()

    def test_err_is_err_and_not_ok(self):
        r = Result.err("boom")
        assert r.is_err()
        assert not r.is_ok()

    def test_ok_can_hold_none(self):
        """None is a legitimate success value, not an absence of one."""
        r = Result.ok(None)
        assert r.is_ok()
        assert r.unwrap() is None

    def test_ok_can_hold_falsy_values(self):
        for value in (0, "", [], {}, False):
            assert Result.ok(value).is_ok()
            assert Result.ok(value).unwrap() == value


class TestUnwrap:
    def test_unwrap_returns_the_success_value(self):
        assert Result.ok("v").unwrap() == "v"

    def test_unwrap_on_err_raises_unwrap_error(self):
        with pytest.raises(UnwrapError) as excinfo:
            Result.err({"errorType": "NOPE"}).unwrap()
        assert excinfo.value.value == {"errorType": "NOPE"}

    def test_unwrap_err_returns_the_error_value(self):
        assert Result.err("e").unwrap_err() == "e"

    def test_unwrap_err_on_ok_raises_unwrap_error(self):
        with pytest.raises(UnwrapError) as excinfo:
            Result.ok(7).unwrap_err()
        assert excinfo.value.value == 7

    def test_unwrap_error_is_still_an_exception(self):
        """Callers catching broad Exception must keep working (ADR-158)."""
        assert issubclass(UnwrapError, Exception)
        with pytest.raises(Exception):
            Result.err("e").unwrap()

    def test_unwrap_or_returns_default_on_err_and_value_on_ok(self):
        assert Result.err("e").unwrap_or("fallback") == "fallback"
        assert Result.ok("v").unwrap_or("fallback") == "v"


class TestCombinators:
    def test_map_applies_only_to_ok(self):
        assert Result.ok(2).map(lambda x: x * 3).unwrap() == 6
        assert Result.err("e").map(lambda x: x * 3).unwrap_err() == "e"

    def test_map_err_applies_only_to_err(self):
        assert Result.err("e").map_err(str.upper).unwrap_err() == "E"
        assert Result.ok(1).map_err(str.upper).unwrap() == 1

    def test_and_then_chains_and_short_circuits(self):
        assert Result.ok(2).and_then(lambda x: Result.ok(x + 1)).unwrap() == 3
        assert Result.err("e").and_then(lambda x: Result.ok(x + 1)).unwrap_err() == "e"

    def test_or_else_recovers_only_from_err(self):
        assert Result.err("e").or_else(lambda e: Result.ok("recovered")).unwrap() == (
            "recovered"
        )
        assert Result.ok("v").or_else(lambda e: Result.ok("recovered")).unwrap() == "v"

    def test_and_then_is_not_called_on_err(self):
        """Short-circuiting must not evaluate the continuation."""
        calls = []

        def f(x):
            calls.append(x)
            return Result.ok(x)

        Result.err("e").and_then(f)
        assert calls == []


class TestSerialization:
    def test_ok_roundtrips_through_dict(self):
        original = Result.ok({"n": 1})
        restored = Result.from_dict(original.to_dict())
        assert restored.is_ok()
        assert restored.unwrap() == {"n": 1}

    def test_err_roundtrips_through_dict(self):
        original = Result.err({"errorType": "X"})
        restored = Result.from_dict(original.to_dict())
        assert restored.is_err()
        assert restored.unwrap_err() == {"errorType": "X"}

    def test_to_dict_labels_the_variant(self):
        assert Result.ok(1).to_dict()["status"] == "ok"
        assert Result.err(1).to_dict()["status"] == "err"


class TestEqualityAndRepr:
    def test_same_variant_and_value_are_equal(self):
        assert Result.ok(1) == Result.ok(1)
        assert Result.err("e") == Result.err("e")

    def test_ok_and_err_holding_the_same_value_are_not_equal(self):
        assert Result.ok(1) != Result.err(1)

    def test_not_equal_to_a_non_result(self):
        assert Result.ok(1) != 1

    def test_repr_shows_the_variant(self):
        assert "ok" in repr(Result.ok(1))
        assert "err" in repr(Result.err(1))
