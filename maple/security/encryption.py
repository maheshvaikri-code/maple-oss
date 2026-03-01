"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or
modify it under the terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details. You should have
received a copy of the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""


# maple/security/encryption.py

from typing import Dict, Any, Union
import base64
import json
import logging
from ..core.result import Result

from .cryptography_impl import CryptographyManager, CRYPTO_AVAILABLE

logger = logging.getLogger(__name__)


class EncryptionManager:
    """
    Handles encryption and decryption for MAPLE agents.

    When the `cryptography` library is installed, delegates to
    CryptographyManager for real AES-256-GCM + RSA hybrid encryption,
    RSA/ECDSA signing, and proper key generation.

    Falls back to base64 encoding (NOT secure) when the library is absent.
    """

    def __init__(self, config):
        self.config = config
        self.encryption_key = getattr(config, 'encryption_key', None)
        self._crypto: CryptographyManager = None
        self._key_pair = None  # cached key pair

        if CRYPTO_AVAILABLE:
            try:
                self._crypto = CryptographyManager()
                # Generate a default key pair for this manager
                kp_result = self._crypto.generate_key_pair("RSA4096")
                if kp_result.is_ok():
                    self._key_pair = kp_result.unwrap()
                    logger.info("EncryptionManager initialized with real cryptography (AES-256-GCM + RSA4096)")
                else:
                    logger.warning(f"Key pair generation failed: {kp_result.unwrap_err()}")
            except Exception as e:
                logger.warning(f"CryptographyManager init failed, falling back to base64: {e}")
                self._crypto = None

        if not self._crypto:
            import warnings
            warnings.warn(
                "No cryptography library available. EncryptionManager will use base64 encoding "
                "which is NOT secure. Install with: pip install cryptography",
                UserWarning,
                stacklevel=2,
            )

    @property
    def has_real_crypto(self) -> bool:
        """Whether real cryptographic operations are available."""
        return self._crypto is not None and self._key_pair is not None

    def encrypt(self, data: Union[str, bytes, Dict[str, Any]], recipient: str) -> Result[str, Dict[str, Any]]:
        """
        Encrypt data for a specific recipient.

        When real crypto is available, uses AES-256-GCM with RSA key wrapping.
        Falls back to base64 encoding otherwise.
        """
        try:
            # Normalize data to string
            if isinstance(data, dict):
                data_str = json.dumps(data)
            elif isinstance(data, bytes):
                data_str = data.decode('utf-8')
            else:
                data_str = str(data)

            if self.has_real_crypto:
                return self._crypto.encrypt_data(data_str, self._key_pair.public_key)

            # Fallback: base64 encoding (NOT secure)
            encrypted = base64.b64encode(data_str.encode('utf-8')).decode('utf-8')
            return Result.ok(encrypted)

        except Exception as e:
            return Result.err({
                'errorType': 'ENCRYPTION_FAILED',
                'message': f'Failed to encrypt data: {str(e)}',
                'details': {'recipient': recipient}
            })

    def decrypt(self, encrypted_data: str) -> Result[str, Dict[str, Any]]:
        """
        Decrypt encrypted data.

        When real crypto is available, uses AES-256-GCM with RSA key unwrapping.
        Falls back to base64 decoding otherwise.
        """
        try:
            if self.has_real_crypto:
                result = self._crypto.decrypt_data(encrypted_data, self._key_pair.private_key)
                if result.is_ok():
                    return Result.ok(result.unwrap().decode('utf-8'))
                return Result.err(result.unwrap_err())

            # Fallback: base64 decoding
            decrypted = base64.b64decode(encrypted_data.encode('utf-8')).decode('utf-8')
            return Result.ok(decrypted)

        except Exception as e:
            return Result.err({
                'errorType': 'DECRYPTION_FAILED',
                'message': f'Failed to decrypt data: {str(e)}'
            })

    def generate_key_pair(self) -> Result[Dict[str, str], Dict[str, Any]]:
        """
        Generate a public/private key pair.

        When real crypto is available, generates RSA-4096 keys.
        Falls back to placeholder strings otherwise.
        """
        try:
            if self._crypto:
                kp_result = self._crypto.generate_key_pair("RSA4096")
                if kp_result.is_ok():
                    kp = kp_result.unwrap()
                    return Result.ok({
                        'public_key': kp.public_key_pem(),
                        'private_key': kp.private_key_pem()
                    })
                return Result.err(kp_result.unwrap_err())

            # Fallback: placeholder keys
            return Result.ok({
                'public_key': f'demo_public_key_{id(self) % 10000}',
                'private_key': f'demo_private_key_{id(self) % 10000}'
            })

        except Exception as e:
            return Result.err({
                'errorType': 'KEY_GENERATION_FAILED',
                'message': f'Failed to generate key pair: {str(e)}'
            })

    def sign_message(self, message: str, private_key: str = None) -> Result[str, Dict[str, Any]]:
        """
        Sign a message.

        When real crypto is available, uses RSA-PSS with SHA-256.
        Falls back to base64 encoding otherwise.
        """
        try:
            if self.has_real_crypto:
                return self._crypto.sign_data(message, self._key_pair.private_key)

            # Fallback: base64 encoding (NOT a real signature)
            signature = base64.b64encode(f'{message}:{private_key}'.encode()).decode()
            return Result.ok(signature)

        except Exception as e:
            return Result.err({
                'errorType': 'SIGNING_FAILED',
                'message': f'Failed to sign message: {str(e)}'
            })

    def verify_signature(self, message: str, signature: str, public_key: str = None) -> Result[bool, Dict[str, Any]]:
        """
        Verify a message signature.

        When real crypto is available, uses RSA-PSS with SHA-256 verification.
        Falls back to base64 check otherwise.
        """
        try:
            if self.has_real_crypto:
                return self._crypto.verify_signature(message, signature, self._key_pair.public_key)

            # Fallback: base64 check
            decoded = base64.b64decode(signature.encode()).decode()
            return Result.ok(message in decoded)

        except Exception as e:
            return Result.err({
                'errorType': 'VERIFICATION_FAILED',
                'message': f'Failed to verify signature: {str(e)}'
            })
