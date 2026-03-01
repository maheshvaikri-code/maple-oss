"""Tests for maple.core.serialization - Serializer."""

import pytest
import json
from maple.core.serialization import Serializer, SerializationFormat
from maple.core.message import Message
from maple.core.types import Priority


@pytest.fixture
def serializer():
    return Serializer()


class TestSerializationFormat:
    """Test format enum."""

    def test_formats(self):
        assert SerializationFormat.JSON.value == "json"
        assert SerializationFormat.PICKLE.value == "pickle"
        assert SerializationFormat.MSGPACK.value == "msgpack"
        assert SerializationFormat.PROTOBUF.value == "protobuf"


class TestJSONSerialization:
    """Test JSON serialization/deserialization."""

    def test_serialize_dict(self, serializer):
        data = {"key": "value", "number": 42}
        result = serializer.serialize(data, SerializationFormat.JSON)
        assert result.is_ok()
        assert isinstance(result.unwrap(), bytes)

    def test_deserialize_dict(self, serializer):
        data = {"key": "value", "number": 42}
        serialized = serializer.serialize(data, SerializationFormat.JSON).unwrap()
        result = serializer.deserialize(serialized, SerializationFormat.JSON)
        assert result.is_ok()
        restored = result.unwrap()
        assert restored['key'] == "value"
        assert restored['number'] == 42

    def test_roundtrip_list(self, serializer):
        data = [1, "two", 3.0, None, True]
        serialized = serializer.serialize(data, SerializationFormat.JSON).unwrap()
        restored = serializer.deserialize(serialized, SerializationFormat.JSON).unwrap()
        assert restored == data

    def test_roundtrip_nested(self, serializer):
        data = {"a": {"b": {"c": [1, 2, 3]}}}
        serialized = serializer.serialize(data, SerializationFormat.JSON).unwrap()
        restored = serializer.deserialize(serialized, SerializationFormat.JSON).unwrap()
        assert restored == data

    def test_tuple_preservation(self, serializer):
        data = {"items": (1, 2, 3)}
        serialized = serializer.serialize(data, SerializationFormat.JSON).unwrap()
        restored = serializer.deserialize(serialized, SerializationFormat.JSON).unwrap()
        assert restored['items'] == (1, 2, 3)

    def test_set_preservation(self, serializer):
        data = {"items": {1, 2, 3}}
        serialized = serializer.serialize(data, SerializationFormat.JSON).unwrap()
        restored = serializer.deserialize(serialized, SerializationFormat.JSON).unwrap()
        assert restored['items'] == {1, 2, 3}

    def test_bytes_preservation(self, serializer):
        data = {"raw": b"hello bytes"}
        serialized = serializer.serialize(data, SerializationFormat.JSON).unwrap()
        restored = serializer.deserialize(serialized, SerializationFormat.JSON).unwrap()
        assert restored['raw'] == b"hello bytes"

    def test_invalid_json_deserialize(self, serializer):
        result = serializer.deserialize(b"not json", SerializationFormat.JSON)
        assert result.is_err()

    def test_unicode_support(self, serializer):
        data = {"text": "Hello \u4e16\u754c"}
        serialized = serializer.serialize(data, SerializationFormat.JSON).unwrap()
        restored = serializer.deserialize(serialized, SerializationFormat.JSON).unwrap()
        assert restored['text'] == "Hello \u4e16\u754c"


class TestPickleSerialization:
    """Test Pickle serialization/deserialization."""

    def test_roundtrip_dict(self, serializer):
        data = {"key": "value", "number": 42}
        serialized = serializer.serialize(data, SerializationFormat.PICKLE).unwrap()
        restored = serializer.deserialize(serialized, SerializationFormat.PICKLE).unwrap()
        assert restored == data

    def test_roundtrip_complex_objects(self, serializer):
        data = {"set": {1, 2, 3}, "tuple": (4, 5), "bytes": b"raw"}
        serialized = serializer.serialize(data, SerializationFormat.PICKLE).unwrap()
        restored = serializer.deserialize(serialized, SerializationFormat.PICKLE).unwrap()
        assert restored == data

    def test_invalid_pickle(self, serializer):
        result = serializer.deserialize(b"not pickle data", SerializationFormat.PICKLE)
        assert result.is_err()


class TestMsgPackSerialization:
    """Test MsgPack serialization (may not be available)."""

    def test_msgpack_unavailable(self, serializer):
        if not serializer.msgpack_available:
            result = serializer.serialize({"a": 1}, SerializationFormat.MSGPACK)
            assert result.is_err()
            assert "MSGPACK_UNAVAILABLE" in result.unwrap_err()['errorType']


class TestProtobufSerialization:
    """Test Protobuf serialization (not implemented)."""

    def test_protobuf_not_implemented(self, serializer):
        result = serializer.serialize({"a": 1}, SerializationFormat.PROTOBUF)
        assert result.is_err()
        assert "PROTOBUF_NOT_IMPLEMENTED" in result.unwrap_err()['errorType']

    def test_protobuf_deserialize_not_implemented(self, serializer):
        result = serializer.deserialize(b"data", SerializationFormat.PROTOBUF)
        assert result.is_err()


class TestDefaultFormat:
    """Test default format behavior."""

    def test_default_is_json(self):
        s = Serializer()
        assert s.default_format == SerializationFormat.JSON

    def test_custom_default(self):
        s = Serializer(default_format=SerializationFormat.PICKLE)
        assert s.default_format == SerializationFormat.PICKLE

    def test_serialize_uses_default(self):
        s = Serializer(default_format=SerializationFormat.JSON)
        result = s.serialize({"a": 1})
        assert result.is_ok()
        # JSON produces UTF-8 bytes
        assert b'"a"' in result.unwrap()


class TestMessageSerialization:
    """Test message serialization/deserialization."""

    def test_serialize_message(self, serializer):
        msg = Message(
            message_type="TEST",
            receiver="agent_2",
            payload={"data": "test"}
        )
        result = serializer.serialize_message(msg)
        assert result.is_ok()
        assert isinstance(result.unwrap(), bytes)

    def test_deserialize_message(self, serializer):
        msg = Message(
            message_type="TEST",
            receiver="agent_2",
            priority=Priority.HIGH,
            payload={"data": "test"}
        )
        serialized = serializer.serialize_message(msg).unwrap()
        result = serializer.deserialize_message(serialized)
        assert result.is_ok()
        restored = result.unwrap()
        assert restored.message_type == "TEST"
        assert restored.receiver == "agent_2"
        assert restored.payload['data'] == "test"

    def test_deserialize_invalid_bytes(self, serializer):
        result = serializer.deserialize_message(b"garbage")
        assert result.is_err()


class TestGetFormatInfo:
    """Test format info method."""

    def test_format_info(self, serializer):
        info = serializer.get_format_info()
        assert info['default_format'] == 'json'
        assert info['available_formats']['json'] is True
        assert info['available_formats']['pickle'] is True
        assert 'recommendations' in info
        assert info['recommendations']['human_readable'] == 'json'
        assert info['recommendations']['cross_language'] == 'json'


class TestObjectSerialization:
    """Test object serialization via JSON."""

    def test_object_with_dict(self, serializer):
        class Dummy:
            def __init__(self):
                self.x = 10
                self.y = "hello"

        data = {"obj": Dummy()}
        result = serializer.serialize(data, SerializationFormat.JSON)
        assert result.is_ok()
        restored = serializer.deserialize(result.unwrap(), SerializationFormat.JSON).unwrap()
        assert restored['obj']['x'] == 10
        assert restored['obj']['y'] == "hello"
