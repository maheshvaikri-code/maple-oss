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
from ..core.result import Result

class EncryptionManager:
    """
    Handles encryption and decryption for MAPLE agents.
    """
    
    def __init__(self, config):
        self.config = config
        # In production, initialize proper encryption keys and algorithms
        self.encryption_key = getattr(config, 'encryption_key', 'demo_key_12345678')
    
    def encrypt(self, data: Union[str, bytes, Dict[str, Any]], recipient: str) -> Result[str, Dict[str, Any]]:
        """
        Encrypt data for a specific recipient.
        
        Args:
            data: The data to encrypt
            recipient: The intended recipient
            
        Returns:
            Result containing encrypted data or error
        """
        try:
            # Simplified encryption for demo purposes
            # In production, use proper cryptographic libraries like cryptography
            
            # Convert data to string if needed
            if isinstance(data, dict):
                data_str = json.dumps(data)
            elif isinstance(data, bytes):
                data_str = data.decode('utf-8')
            else:
                data_str = str(data)
            
            # Simple base64 encoding for demo (NOT secure!)
            # In production, use AES, ChaCha20, or other proper encryption
            encrypted_bytes = base64.b64encode(data_str.encode('utf-8'))
            encrypted_str = encrypted_bytes.decode('utf-8')
            
            return Result.ok(encrypted_str)
            
        except Exception as e:
            return Result.err({
                'errorType': 'ENCRYPTION_FAILED',
                'message': f'Failed to encrypt data: {str(e)}',
                'details': {'recipient': recipient}
            })
    
    def decrypt(self, encrypted_data: str) -> Result[str, Dict[str, Any]]:
        """
        Decrypt encrypted data.
        
        Args:
            encrypted_data: The encrypted data to decrypt
            
        Returns:
            Result containing decrypted data or error
        """
        try:
            # Simplified decryption for demo purposes
            # In production, use proper cryptographic libraries
            
            # Simple base64 decoding for demo (NOT secure!)
            decrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted_str = decrypted_bytes.decode('utf-8')
            
            return Result.ok(decrypted_str)
            
        except Exception as e:
            return Result.err({
                'errorType': 'DECRYPTION_FAILED',
                'message': f'Failed to decrypt data: {str(e)}'
            })
    
    def generate_key_pair(self) -> Result[Dict[str, str], Dict[str, Any]]:
        """
        Generate a public/private key pair for asymmetric encryption.
        
        Returns:
            Result containing key pair or error
        """
        try:
            # In production, use proper key generation
            # For demo, return placeholder keys
            return Result.ok({
                'public_key': f'demo_public_key_{hash(self.encryption_key) % 10000}',
                'private_key': f'demo_private_key_{hash(self.encryption_key) % 10000}'
            })
            
        except Exception as e:
            return Result.err({
                'errorType': 'KEY_GENERATION_FAILED',
                'message': f'Failed to generate key pair: {str(e)}'
            })
    
    def sign_message(self, message: str, private_key: str) -> Result[str, Dict[str, Any]]:
        """
        Sign a message using a private key.
        
        Args:
            message: The message to sign
            private_key: The private key for signing
            
        Returns:
            Result containing signature or error
        """
        try:
            # Simplified signing for demo purposes
            # In production, use proper digital signatures
            signature = base64.b64encode(f'{message}:{private_key}'.encode()).decode()
            return Result.ok(signature)
            
        except Exception as e:
            return Result.err({
                'errorType': 'SIGNING_FAILED',
                'message': f'Failed to sign message: {str(e)}'
            })
    
    def verify_signature(self, message: str, signature: str, public_key: str) -> Result[bool, Dict[str, Any]]:
        """
        Verify a message signature using a public key.
        
        Args:
            message: The original message
            signature: The signature to verify
            public_key: The public key for verification
            
        Returns:
            Result indicating verification success or failure
        """
        try:
            # Simplified verification for demo purposes
            # In production, use proper signature verification
            decoded = base64.b64decode(signature.encode()).decode()
            return Result.ok(message in decoded)
            
        except Exception as e:
            return Result.err({
                'errorType': 'VERIFICATION_FAILED',
                'message': f'Failed to verify signature: {str(e)}'
            })
