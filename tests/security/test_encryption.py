"""Tests for maple.security.encryption - EncryptionManager."""

import pytest
from maple.security.encryption import EncryptionManager
from maple.agent.config import Config


@pytest.fixture
def enc():
    config = Config(agent_id="test", broker_url="memory://local")
    return EncryptionManager(config)


class TestEncryptionManager:
    """Test EncryptionManager with real crypto backend."""

    def test_has_real_crypto(self, enc):
        # cryptography library should be installed
        assert enc.has_real_crypto is True

    def test_encrypt_string(self, enc):
        result = enc.encrypt("hello world", "recipient")
        assert result.is_ok()
        encrypted = result.unwrap()
        assert isinstance(encrypted, str)
        assert encrypted != "hello world"

    def test_encrypt_dict(self, enc):
        result = enc.encrypt({"key": "value"}, "recipient")
        assert result.is_ok()

    def test_encrypt_bytes(self, enc):
        result = enc.encrypt(b"binary data", "recipient")
        assert result.is_ok()

    def test_encrypt_decrypt_roundtrip(self, enc):
        original = "secret message for roundtrip test"
        enc_result = enc.encrypt(original, "recipient")
        assert enc_result.is_ok()

        dec_result = enc.decrypt(enc_result.unwrap())
        assert dec_result.is_ok()
        assert dec_result.unwrap() == original

    def test_encrypt_decrypt_dict_roundtrip(self, enc):
        import json
        original = {"data": "confidential", "count": 42}
        enc_result = enc.encrypt(original, "recipient")
        assert enc_result.is_ok()

        dec_result = enc.decrypt(enc_result.unwrap())
        assert dec_result.is_ok()
        assert json.loads(dec_result.unwrap()) == original

    def test_decrypt_invalid_data(self, enc):
        result = enc.decrypt("not-valid-encrypted-data!!!")
        assert result.is_err()

    def test_generate_key_pair(self, enc):
        result = enc.generate_key_pair()
        assert result.is_ok()
        keys = result.unwrap()
        assert 'public_key' in keys
        assert 'private_key' in keys
        if enc.has_real_crypto:
            assert 'BEGIN PUBLIC KEY' in keys['public_key']
            assert 'BEGIN' in keys['private_key']

    def test_sign_message(self, enc):
        result = enc.sign_message("test message to sign")
        assert result.is_ok()
        signature = result.unwrap()
        assert isinstance(signature, str)
        assert len(signature) > 0

    def test_verify_signature(self, enc):
        message = "message to verify"
        sign_result = enc.sign_message(message)
        assert sign_result.is_ok()

        verify_result = enc.verify_signature(message, sign_result.unwrap())
        assert verify_result.is_ok()
        assert verify_result.unwrap() is True

    def test_verify_wrong_message(self, enc):
        sign_result = enc.sign_message("original message")
        assert sign_result.is_ok()

        verify_result = enc.verify_signature("tampered message", sign_result.unwrap())
        assert verify_result.is_ok()
        assert verify_result.unwrap() is False

    def test_multiple_key_pairs_are_unique(self, enc):
        r1 = enc.generate_key_pair()
        r2 = enc.generate_key_pair()
        assert r1.is_ok() and r2.is_ok()
        assert r1.unwrap()['public_key'] != r2.unwrap()['public_key']
