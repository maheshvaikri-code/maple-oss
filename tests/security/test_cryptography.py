"""Tests for maple.security.cryptography_impl - CryptographyManager."""

import pytest
from maple.security.cryptography_impl import (
    CryptographyManager, CryptoSuite, KeyPair, CRYPTO_AVAILABLE
)


@pytest.fixture
def crypto():
    return CryptographyManager()


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography library not installed")
class TestKeyGeneration:
    """Test key pair generation for various algorithms."""

    def test_generate_rsa4096(self, crypto):
        result = crypto.generate_key_pair("RSA4096")
        assert result.is_ok()
        kp = result.unwrap()
        assert kp.key_type == "RSA4096"
        assert kp.private_key is not None
        assert kp.public_key is not None

    def test_generate_rsa2048(self, crypto):
        result = crypto.generate_key_pair("RSA2048")
        assert result.is_ok()
        assert result.unwrap().key_type == "RSA2048"

    def test_generate_ecdsa_p256(self, crypto):
        result = crypto.generate_key_pair("ECDSA_P256")
        assert result.is_ok()
        kp = result.unwrap()
        assert kp.key_type == "ECDSA_P256"

    def test_generate_ecdsa_p384(self, crypto):
        result = crypto.generate_key_pair("ECDSA_P384")
        assert result.is_ok()

    def test_unsupported_key_type(self, crypto):
        result = crypto.generate_key_pair("INVALID_TYPE")
        assert result.is_err()
        assert result.unwrap_err()['errorType'] == 'UNSUPPORTED_KEY_TYPE'

    def test_key_pair_pem_export(self, crypto):
        kp = crypto.generate_key_pair("RSA2048").unwrap()
        pub_pem = kp.public_key_pem()
        assert 'BEGIN PUBLIC KEY' in pub_pem

        priv_pem = kp.private_key_pem()
        assert 'BEGIN PRIVATE KEY' in priv_pem

    def test_key_pair_to_dict(self, crypto):
        kp = crypto.generate_key_pair("RSA2048").unwrap()
        d = kp.to_dict()
        assert d['key_type'] == 'RSA2048'
        assert 'created_at' in d
        assert 'public_key_pem' in d


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography library not installed")
class TestEncryptDecrypt:
    """Test AES-256-GCM hybrid encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self, crypto):
        kp = crypto.generate_key_pair("RSA4096").unwrap()

        enc_result = crypto.encrypt_data("hello world", kp.public_key)
        assert enc_result.is_ok()

        dec_result = crypto.decrypt_data(enc_result.unwrap(), kp.private_key)
        assert dec_result.is_ok()
        assert dec_result.unwrap() == b"hello world"

    def test_encrypt_bytes(self, crypto):
        kp = crypto.generate_key_pair("RSA4096").unwrap()
        enc_result = crypto.encrypt_data(b"binary data", kp.public_key)
        assert enc_result.is_ok()

        dec_result = crypto.decrypt_data(enc_result.unwrap(), kp.private_key)
        assert dec_result.is_ok()
        assert dec_result.unwrap() == b"binary data"

    def test_decrypt_with_wrong_key(self, crypto):
        kp1 = crypto.generate_key_pair("RSA4096").unwrap()
        kp2 = crypto.generate_key_pair("RSA4096").unwrap()

        enc_result = crypto.encrypt_data("secret", kp1.public_key)
        assert enc_result.is_ok()

        dec_result = crypto.decrypt_data(enc_result.unwrap(), kp2.private_key)
        assert dec_result.is_err()

    def test_decrypt_corrupted_data(self, crypto):
        result = crypto.decrypt_data("not-valid-encrypted-data", None)
        assert result.is_err()


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography library not installed")
class TestSignVerify:
    """Test digital signatures with RSA and ECDSA."""

    def test_rsa_sign_verify(self, crypto):
        kp = crypto.generate_key_pair("RSA4096").unwrap()

        sign_result = crypto.sign_data("test data", kp.private_key)
        assert sign_result.is_ok()

        verify_result = crypto.verify_signature("test data", sign_result.unwrap(), kp.public_key)
        assert verify_result.is_ok()
        assert verify_result.unwrap() is True

    def test_rsa_verify_wrong_data(self, crypto):
        kp = crypto.generate_key_pair("RSA4096").unwrap()

        sign_result = crypto.sign_data("original", kp.private_key)
        assert sign_result.is_ok()

        verify_result = crypto.verify_signature("tampered", sign_result.unwrap(), kp.public_key)
        assert verify_result.is_ok()
        assert verify_result.unwrap() is False

    def test_ecdsa_sign_verify(self, crypto):
        kp = crypto.generate_key_pair("ECDSA_P256").unwrap()

        sign_result = crypto.sign_data("ecdsa test", kp.private_key)
        assert sign_result.is_ok()

        verify_result = crypto.verify_signature("ecdsa test", sign_result.unwrap(), kp.public_key)
        assert verify_result.is_ok()
        assert verify_result.unwrap() is True

    def test_sign_bytes(self, crypto):
        kp = crypto.generate_key_pair("RSA2048").unwrap()
        sign_result = crypto.sign_data(b"bytes data", kp.private_key)
        assert sign_result.is_ok()


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography library not installed")
class TestCertificateGeneration:
    """Test X.509 certificate generation."""

    def test_self_signed_certificate(self, crypto):
        kp = crypto.generate_key_pair("RSA4096").unwrap()
        cert_result = crypto.generate_certificate(kp, "test-agent")
        assert cert_result.is_ok()
        cert_pem = cert_result.unwrap()
        assert 'BEGIN CERTIFICATE' in cert_pem

    def test_ca_signed_certificate(self, crypto):
        ca_kp = crypto.generate_key_pair("RSA4096").unwrap()
        agent_kp = crypto.generate_key_pair("RSA4096").unwrap()
        cert_result = crypto.generate_certificate(
            agent_kp, "agent-001", issuer_key_pair=ca_kp
        )
        assert cert_result.is_ok()

    def test_certificate_validity_days(self, crypto):
        kp = crypto.generate_key_pair("RSA2048").unwrap()
        cert_result = crypto.generate_certificate(kp, "test", validity_days=30)
        assert cert_result.is_ok()


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography library not installed")
class TestKeyDerivation:
    """Test ECDH key derivation."""

    def test_ecdh_shared_secret(self, crypto):
        kp_a = crypto.generate_key_pair("ECDSA_P256").unwrap()
        kp_b = crypto.generate_key_pair("ECDSA_P256").unwrap()

        secret_a = crypto.derive_shared_secret(kp_a.private_key, kp_b.public_key)
        assert secret_a.is_ok()

        secret_b = crypto.derive_shared_secret(kp_b.private_key, kp_a.public_key)
        assert secret_b.is_ok()

        # Both sides should derive the same secret
        assert secret_a.unwrap() == secret_b.unwrap()

    def test_ecdh_different_pairs_different_secrets(self, crypto):
        kp_a = crypto.generate_key_pair("ECDSA_P256").unwrap()
        kp_b = crypto.generate_key_pair("ECDSA_P256").unwrap()
        kp_c = crypto.generate_key_pair("ECDSA_P256").unwrap()

        secret_ab = crypto.derive_shared_secret(kp_a.private_key, kp_b.public_key).unwrap()
        secret_ac = crypto.derive_shared_secret(kp_a.private_key, kp_c.public_key).unwrap()

        assert secret_ab != secret_ac

    def test_rsa_key_no_exchange(self, crypto):
        kp = crypto.generate_key_pair("RSA2048").unwrap()
        result = crypto.derive_shared_secret(kp.private_key, kp.public_key)
        assert result.is_err()


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography library not installed")
class TestUtilities:
    """Test utility methods."""

    def test_secure_random(self, crypto):
        r1 = crypto.secure_random(32)
        r2 = crypto.secure_random(32)
        assert len(r1) == 32
        assert r1 != r2

    def test_hash_sha256(self, crypto):
        h1 = crypto.hash_data("test")
        h2 = crypto.hash_data("test")
        assert h1 == h2

        h3 = crypto.hash_data("different")
        assert h1 != h3

    def test_hash_sha512(self, crypto):
        h = crypto.hash_data("test", algorithm="SHA512")
        assert isinstance(h, str)
        assert len(h) > 0
