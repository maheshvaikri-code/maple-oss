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


# maple/security/cryptography_impl.py
# Creator: Mahesh Vaikri

"""
Production Cryptographic Implementation for MAPLE Security
Provides enterprise-grade encryption, signing, and certificate management
"""

import os
import base64
import json
import time
from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import logging

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.x509 import CertificateBuilder, Name, NameAttribute, BasicConstraints
    from cryptography.x509.oid import ExtensionOID, NameOID
    from cryptography import x509
    import secrets
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from ..core.result import Result

logger = logging.getLogger(__name__)

class CryptoSuite(Enum):
    """Supported cryptographic suites."""
    AES256_GCM_RSA4096 = "AES256-GCM-RSA4096"
    AES256_GCM_ECDSA = "AES256-GCM-ECDSA"
    CHACHA20_POLY1305_RSA4096 = "CHACHA20-POLY1305-RSA4096"

@dataclass
class KeyPair:
    """Cryptographic key pair."""
    private_key: Any
    public_key: Any
    key_type: str
    created_at: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Export key pair information (without private key)."""
        return {
            'key_type': self.key_type,
            'created_at': self.created_at,
            'public_key_pem': self.public_key_pem()
        }
    
    def public_key_pem(self) -> str:
        """Export public key as PEM string."""
        if not CRYPTO_AVAILABLE:
            return "CRYPTO_NOT_AVAILABLE"
        
        pem = self.public_key.public_key_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode('utf-8')
    
    def private_key_pem(self, password: Optional[bytes] = None) -> str:
        """Export private key as PEM string (password protected)."""
        if not CRYPTO_AVAILABLE:
            return "CRYPTO_NOT_AVAILABLE"
        
        encryption = serialization.NoEncryption()
        if password:
            encryption = serialization.BestAvailableEncryption(password)
        
        pem = self.private_key.private_key_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption
        )
        return pem.decode('utf-8')

class CryptographyManager:
    """
    Production-grade cryptographic manager for MAPLE.
    
    Features:
    - RSA and ECDSA key generation
    - AES-256-GCM and ChaCha20-Poly1305 encryption
    - Digital signatures and verification
    - Certificate generation and management
    - Key derivation and exchange
    """
    
    def __init__(self, crypto_suite: CryptoSuite = CryptoSuite.AES256_GCM_RSA4096):
        if not CRYPTO_AVAILABLE:
            raise ImportError("Cryptography library not available. Install with: pip install cryptography")
        
        self.crypto_suite = crypto_suite
        self.master_key: Optional[bytes] = None
        self.certificates: Dict[str, Any] = {}
        
        logger.info(f"CryptographyManager initialized with suite: {crypto_suite.value}")
    
    def generate_key_pair(self, key_type: str = "RSA4096") -> Result[KeyPair, Dict[str, Any]]:
        """
        Generate a cryptographic key pair.
        
        Args:
            key_type: Type of key to generate ("RSA2048", "RSA4096", "ECDSA_P256", "ECDSA_P384")
            
        Returns:
            Result containing KeyPair or error
        """
        try:
            if key_type.startswith("RSA"):
                key_size = int(key_type[3:])  # Extract size from "RSA4096"
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=key_size
                )
                public_key = private_key.public_key()
                
            elif key_type.startswith("ECDSA"):
                if "P256" in key_type:
                    curve = ec.SECP256R1()
                elif "P384" in key_type:
                    curve = ec.SECP384R1()
                else:
                    curve = ec.SECP256R1()  # Default
                
                private_key = ec.generate_private_key(curve)
                public_key = private_key.public_key()
            
            else:
                return Result.err({
                    'errorType': 'UNSUPPORTED_KEY_TYPE',
                    'message': f'Unsupported key type: {key_type}'
                })
            
            key_pair = KeyPair(
                private_key=private_key,
                public_key=public_key,
                key_type=key_type,
                created_at=time.time()
            )
            
            logger.info(f"Generated {key_type} key pair")
            return Result.ok(key_pair)
            
        except Exception as e:
            error = {
                'errorType': 'KEY_GENERATION_ERROR',
                'message': f'Failed to generate key pair: {str(e)}',
                'details': {'keyType': key_type}
            }
            logger.error(f"Key generation error: {error}")
            return Result.err(error)
    
    def encrypt_data(self, data: Union[str, bytes], public_key: Any) -> Result[str, Dict[str, Any]]:
        """
        Encrypt data using public key cryptography.
        
        Args:
            data: Data to encrypt
            public_key: Recipient's public key
            
        Returns:
            Result containing base64-encoded encrypted data or error
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # Use hybrid encryption: RSA for key, AES for data
            if self.crypto_suite == CryptoSuite.AES256_GCM_RSA4096:
                # Generate AES key
                aes_key = secrets.token_bytes(32)  # 256 bits
                iv = secrets.token_bytes(12)  # 96 bits for GCM
                
                # Encrypt data with AES-GCM
                cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv))
                encryptor = cipher.encryptor()
                encrypted_data = encryptor.update(data) + encryptor.finalize()
                
                # Encrypt AES key with RSA
                encrypted_key = public_key.encrypt(
                    aes_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
                # Combine encrypted key, IV, tag, and data
                result = {
                    'encrypted_key': base64.b64encode(encrypted_key).decode('utf-8'),
                    'iv': base64.b64encode(iv).decode('utf-8'),
                    'tag': base64.b64encode(encryptor.tag).decode('utf-8'),
                    'data': base64.b64encode(encrypted_data).decode('utf-8'),
                    'suite': self.crypto_suite.value
                }
                
                return Result.ok(base64.b64encode(json.dumps(result).encode()).decode('utf-8'))
            
            else:
                return Result.err({
                    'errorType': 'UNSUPPORTED_CRYPTO_SUITE',
                    'message': f'Crypto suite not implemented: {self.crypto_suite.value}'
                })
                
        except Exception as e:
            error = {
                'errorType': 'ENCRYPTION_ERROR',
                'message': f'Failed to encrypt data: {str(e)}',
                'details': {'suite': self.crypto_suite.value}
            }
            logger.error(f"Encryption error: {error}")
            return Result.err(error)
    
    def decrypt_data(self, encrypted_data: str, private_key: Any) -> Result[bytes, Dict[str, Any]]:
        """
        Decrypt data using private key cryptography.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            private_key: Recipient's private key
            
        Returns:
            Result containing decrypted data or error
        """
        try:
            # Decode and parse encrypted package
            package_data = json.loads(base64.b64decode(encrypted_data).decode())
            
            suite = package_data.get('suite', self.crypto_suite.value)
            
            if suite == CryptoSuite.AES256_GCM_RSA4096.value:
                # Decrypt AES key with RSA
                encrypted_key = base64.b64decode(package_data['encrypted_key'])
                aes_key = private_key.decrypt(
                    encrypted_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
                # Decrypt data with AES-GCM
                iv = base64.b64decode(package_data['iv'])
                tag = base64.b64decode(package_data['tag'])
                data = base64.b64decode(package_data['data'])
                
                cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv, tag))
                decryptor = cipher.decryptor()
                decrypted_data = decryptor.update(data) + decryptor.finalize()
                
                return Result.ok(decrypted_data)
            
            else:
                return Result.err({
                    'errorType': 'UNSUPPORTED_CRYPTO_SUITE',
                    'message': f'Crypto suite not supported: {suite}'
                })
                
        except Exception as e:
            error = {
                'errorType': 'DECRYPTION_ERROR',
                'message': f'Failed to decrypt data: {str(e)}'
            }
            logger.error(f"Decryption error: {error}")
            return Result.err(error)
    
    def sign_data(self, data: Union[str, bytes], private_key: Any) -> Result[str, Dict[str, Any]]:
        """
        Create a digital signature for data.
        
        Args:
            data: Data to sign
            private_key: Signer's private key
            
        Returns:
            Result containing base64-encoded signature or error
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            if hasattr(private_key, 'sign'):  # RSA key
                signature = private_key.sign(
                    data,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            else:  # ECDSA key
                signature = private_key.sign(data, ec.ECDSA(hashes.SHA256()))
            
            return Result.ok(base64.b64encode(signature).decode('utf-8'))
            
        except Exception as e:
            error = {
                'errorType': 'SIGNING_ERROR',
                'message': f'Failed to sign data: {str(e)}'
            }
            logger.error(f"Signing error: {error}")
            return Result.err(error)
    
    def verify_signature(self, data: Union[str, bytes], signature: str, public_key: Any) -> Result[bool, Dict[str, Any]]:
        """
        Verify a digital signature.
        
        Args:
            data: Original data
            signature: Base64-encoded signature
            public_key: Signer's public key
            
        Returns:
            Result containing verification result or error
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            signature_bytes = base64.b64decode(signature)
            
            if hasattr(public_key, 'verify'):  # RSA key
                public_key.verify(
                    signature_bytes,
                    data,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            else:  # ECDSA key
                public_key.verify(signature_bytes, data, ec.ECDSA(hashes.SHA256()))
            
            return Result.ok(True)
            
        except Exception as e:
            # Verification failed
            return Result.ok(False)
    
    def generate_certificate(
        self,
        key_pair: KeyPair,
        subject_name: str,
        issuer_key_pair: Optional[KeyPair] = None,
        validity_days: int = 365
    ) -> Result[str, Dict[str, Any]]:
        """
        Generate an X.509 certificate.
        
        Args:
            key_pair: Key pair for the certificate
            subject_name: Subject name (e.g., "CN=agent1,O=MAPLE")
            issuer_key_pair: Issuer's key pair (self-signed if None)
            validity_days: Certificate validity period
            
        Returns:
            Result containing PEM-encoded certificate or error
        """
        try:
            # Parse subject name
            subject = Name([NameAttribute(NameOID.COMMON_NAME, subject_name)])
            
            # Create certificate
            builder = CertificateBuilder()
            builder = builder.subject_name(subject)
            
            if issuer_key_pair:
                # Signed by issuer
                issuer = Name([NameAttribute(NameOID.COMMON_NAME, "MAPLE-CA")])
                signing_key = issuer_key_pair.private_key
            else:
                # Self-signed
                issuer = subject
                signing_key = key_pair.private_key
            
            builder = builder.issuer_name(issuer)
            builder = builder.public_key(key_pair.public_key)
            builder = builder.serial_number(secrets.randbits(64))
            
            # Set validity period
            import datetime
            now = datetime.datetime.utcnow()
            builder = builder.not_valid_before(now)
            builder = builder.not_valid_after(now + datetime.timedelta(days=validity_days))
            
            # Add extensions
            builder = builder.add_extension(
                BasicConstraints(ca=False, path_length=None),
                critical=True
            )
            
            # Sign the certificate
            certificate = builder.sign(signing_key, hashes.SHA256())
            
            # Convert to PEM
            pem = certificate.public_bytes(serialization.Encoding.PEM)
            
            logger.info(f"Generated certificate for {subject_name}")
            return Result.ok(pem.decode('utf-8'))
            
        except Exception as e:
            error = {
                'errorType': 'CERTIFICATE_GENERATION_ERROR',
                'message': f'Failed to generate certificate: {str(e)}',
                'details': {'subject': subject_name}
            }
            logger.error(f"Certificate generation error: {error}")
            return Result.err(error)
    
    def derive_shared_secret(self, private_key: Any, peer_public_key: Any) -> Result[bytes, Dict[str, Any]]:
        """
        Derive a shared secret using ECDH key exchange.
        
        Args:
            private_key: Our private key
            peer_public_key: Peer's public key
            
        Returns:
            Result containing shared secret or error
        """
        try:
            if not hasattr(private_key, 'exchange'):
                return Result.err({
                    'errorType': 'KEY_EXCHANGE_NOT_SUPPORTED',
                    'message': 'Key type does not support key exchange'
                })
            
            # Perform ECDH
            shared_key = private_key.exchange(ec.ECDH(), peer_public_key)
            
            # Derive final key using HKDF
            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,  # 256 bits
                salt=None,
                info=b'MAPLE-Link-Key'
            ).derive(shared_key)
            
            return Result.ok(derived_key)
            
        except Exception as e:
            error = {
                'errorType': 'KEY_DERIVATION_ERROR',
                'message': f'Failed to derive shared secret: {str(e)}'
            }
            logger.error(f"Key derivation error: {error}")
            return Result.err(error)
    
    def secure_random(self, length: int) -> bytes:
        """Generate cryptographically secure random bytes."""
        return secrets.token_bytes(length)
    
    def hash_data(self, data: Union[str, bytes], algorithm: str = "SHA256") -> str:
        """Hash data using specified algorithm."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        if algorithm == "SHA256":
            digest = hashes.Hash(hashes.SHA256())
        elif algorithm == "SHA512":
            digest = hashes.Hash(hashes.SHA512())
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        
        digest.update(data)
        return base64.b64encode(digest.finalize()).decode('utf-8')

# Global instance for easy access
crypto_manager = CryptographyManager() if CRYPTO_AVAILABLE else None
