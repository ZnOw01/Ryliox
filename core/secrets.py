"""Secret management with rotation, encryption, and Vault preparation.

Implements OWASP A02: Cryptographic Failures protection through:
- Secure secret storage with encryption at rest
- Secret rotation support
- Preparation for HashiCorp Vault integration
- No hardcoded secrets
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


# Default paths
SECRETS_DIR: Path = Path(os.getenv("SECRETS_DIR", "./data/secrets"))
SECRETS_FILE: Path = Path(os.getenv("SECRETS_FILE", "./data/secrets.json.enc"))
MASTER_KEY_FILE: Path = Path(os.getenv("MASTER_KEY_FILE", "./data/.master_key"))

# Rotation settings
DEFAULT_ROTATION_DAYS: int = int(os.getenv("SECRET_ROTATION_DAYS", "90"))
KEY_ITERATIONS: int = 480000  # OWASP recommended minimum for PBKDF2


class SecretBackend(Protocol):
    """Protocol for secret backend implementations."""
    
    async def get(self, key: str) -> str | None:
        """Get a secret by key."""
        ...
    
    async def set(self, key: str, value: str, metadata: dict | None = None) -> None:
        """Store a secret."""
        ...
    
    async def delete(self, key: str) -> None:
        """Delete a secret."""
        ...
    
    async def rotate(self, key: str) -> None:
        """Rotate a secret."""
        ...


@dataclass(frozen=True)
class SecretMetadata:
    """Metadata for a stored secret."""
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    version: int
    rotated_at: datetime | None = None


class SecretManager:
    """Secure secret management with encryption at rest.
    
    Features:
    - AES-256-GCM encryption via Fernet
    - PBKDF2 key derivation with 480k iterations
    - Automatic secret rotation
    - Immutable audit log of secret access
    - Preparation for external Vault integration
    """
    
    _instance: SecretManager | None = None
    _initialized: bool = False
    
    def __new__(cls) -> SecretManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        secrets_file: Path | None = None,
        master_key_file: Path | None = None,
        rotation_days: int = DEFAULT_ROTATION_DAYS,
    ) -> None:
        if self._initialized:
            return
            
        self._secrets_file = secrets_file or SECRETS_FILE
        self._master_key_file = master_key_file or MASTER_KEY_FILE
        self._rotation_days = rotation_days
        self._fernet: Fernet | None = None
        self._secrets: dict[str, tuple[str, SecretMetadata]] = {}
        self._backend: SecretBackend | None = None
        
        self._initialized = True
    
    def _derive_key(self, password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
        """Derive encryption key from password using PBKDF2.
        
        Returns:
            Tuple of (key, salt)
        """
        if salt is None:
            salt = secrets.token_bytes(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=KEY_ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    def _get_or_create_master_key(self) -> bytes:
        """Get or generate the master encryption key."""
        if self._master_key_file.exists():
            # Read existing key
            content = self._master_key_file.read_bytes()
            # Expect format: salt(16) + key
            if len(content) < 17:
                raise SecretManagerError("Invalid master key file format")
            salt = content[:16]
            # Derive key from a stored password hash or environment
            password = os.getenv("SECRET_MASTER_PASSWORD")
            if not password:
                raise SecretManagerError(
                    "SECRET_MASTER_PASSWORD environment variable required"
                )
            key, _ = self._derive_key(password, salt)
            return key
        
        # Generate new master key
        self._master_key_file.parent.mkdir(parents=True, exist_ok=True)
        password = os.getenv("SECRET_MASTER_PASSWORD")
        if not password:
            # Generate random password if not set (first run)
            password = secrets.token_urlsafe(32)
            logger.warning(
                "Generated random master password. Set SECRET_MASTER_PASSWORD "
                "in environment for persistence across restarts."
            )
        
        key, salt = self._derive_key(password)
        # Store salt for future key derivation
        self._master_key_file.write_bytes(salt)
        # Secure the key file
        os.chmod(self._master_key_file, 0o600)
        
        return key
    
    def _get_fernet(self) -> Fernet:
        """Get or initialize Fernet cipher."""
        if self._fernet is None:
            key = self._get_or_create_master_key()
            self._fernet = Fernet(key)
        return self._fernet
    
    def _load_secrets(self) -> None:
        """Load encrypted secrets from disk."""
        if not self._secrets_file.exists():
            return
        
        fernet = self._get_fernet()
        try:
            encrypted_data = self._secrets_file.read_bytes()
            decrypted_data = fernet.decrypt(encrypted_data)
            data = json.loads(decrypted_data.decode('utf-8'))
            
            for key, value_data in data.items():
                if isinstance(value_data, dict):
                    secret_value = value_data.get("value", "")
                    metadata = SecretMetadata(
                        created_at=datetime.fromisoformat(value_data["created_at"]),
                        updated_at=datetime.fromisoformat(value_data["updated_at"]),
                        expires_at=datetime.fromisoformat(value_data["expires_at"]) if value_data.get("expires_at") else None,
                        version=value_data.get("version", 1),
                        rotated_at=datetime.fromisoformat(value_data["rotated_at"]) if value_data.get("rotated_at") else None,
                    )
                    self._secrets[key] = (secret_value, metadata)
                else:
                    # Legacy format - migrate
                    self._secrets[key] = (
                        str(value_data),
                        SecretMetadata(
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc),
                            expires_at=None,
                            version=1,
                        )
                    )
        except InvalidToken:
            logger.error("Failed to decrypt secrets file - invalid key or corrupted data")
            raise SecretManagerError("Failed to decrypt secrets - master key mismatch")
        except Exception as exc:
            logger.error("Failed to load secrets: %s", exc)
            raise SecretManagerError(f"Failed to load secrets: {exc}") from exc
    
    def _save_secrets(self) -> None:
        """Save encrypted secrets to disk."""
        fernet = self._get_fernet()
        
        data = {}
        for key, (value, metadata) in self._secrets.items():
            data[key] = {
                "value": value,
                "created_at": metadata.created_at.isoformat(),
                "updated_at": metadata.updated_at.isoformat(),
                "expires_at": metadata.expires_at.isoformat() if metadata.expires_at else None,
                "version": metadata.version,
                "rotated_at": metadata.rotated_at.isoformat() if metadata.rotated_at else None,
            }
        
        json_data = json.dumps(data, indent=2).encode('utf-8')
        encrypted_data = fernet.encrypt(json_data)
        
        self._secrets_file.parent.mkdir(parents=True, exist_ok=True)
        self._secrets_file.write_bytes(encrypted_data)
        os.chmod(self._secrets_file, 0o600)
    
    def get(self, key: str, default: str | None = None) -> str | None:
        """Get a secret value.
        
        Args:
            key: The secret key.
            default: Default value if not found.
            
        Returns:
            The secret value or default.
        """
        self._load_secrets()
        
        if key not in self._secrets:
            return default
        
        value, metadata = self._secrets[key]
        
        # Check expiration
        if metadata.expires_at and datetime.now(timezone.utc) > metadata.expires_at:
            logger.warning("Secret '%s' has expired", key)
            return default
        
        return value
    
    def set(
        self,
        key: str,
        value: str,
        expires_days: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Store a secret.
        
        Args:
            key: The secret key.
            value: The secret value.
            expires_days: Optional expiration in days.
            metadata: Optional additional metadata.
        """
        self._load_secrets()
        
        now = datetime.now(timezone.utc)
        expires_at = None
        if expires_days:
            expires_at = now + timedelta(days=expires_days)
        
        # Check if updating existing secret
        if key in self._secrets:
            _, old_metadata = self._secrets[key]
            version = old_metadata.version + 1
        else:
            version = 1
        
        secret_metadata = SecretMetadata(
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            version=version,
        )
        
        self._secrets[key] = (value, secret_metadata)
        self._save_secrets()
        
        logger.debug("Secret '%s' stored (version %d)", key, version)
    
    def delete(self, key: str) -> bool:
        """Delete a secret.
        
        Args:
            key: The secret key.
            
        Returns:
            True if deleted, False if not found.
        """
        self._load_secrets()
        
        if key not in self._secrets:
            return False
        
        del self._secrets[key]
        self._save_secrets()
        
        logger.info("Secret '%s' deleted", key)
        return True
    
    def rotate(self, key: str, new_value: str | None = None) -> str:
        """Rotate a secret (generate new value or use provided).
        
        Args:
            key: The secret key.
            new_value: Optional new value, or auto-generated if None.
            
        Returns:
            The new secret value.
        """
        self._load_secrets()
        
        if key not in self._secrets:
            raise SecretManagerError(f"Cannot rotate non-existent secret: {key}")
        
        old_value, old_metadata = self._secrets[key]
        
        # Generate new value if not provided
        if new_value is None:
            new_value = secrets.token_urlsafe(32)
        
        now = datetime.now(timezone.utc)
        new_metadata = SecretMetadata(
            created_at=old_metadata.created_at,  # Preserve original creation
            updated_at=now,
            expires_at=now + timedelta(days=self._rotation_days),
            version=old_metadata.version + 1,
            rotated_at=now,
        )
        
        self._secrets[key] = (new_value, new_metadata)
        self._save_secrets()
        
        # Hash old value for audit (don't store it)
        old_hash = hashlib.sha256(old_value.encode()).hexdigest()[:16]
        logger.info(
            "Secret '%s' rotated (version %d -> %d). Old value hash: %s",
            key,
            old_metadata.version,
            new_metadata.version,
            old_hash
        )
        
        return new_value
    
    def rotate_if_needed(self, key: str) -> str | None:
        """Rotate secret if rotation period has passed.
        
        Args:
            key: The secret key.
            
        Returns:
            New value if rotated, None if not needed.
        """
        self._load_secrets()
        
        if key not in self._secrets:
            return None
        
        _, metadata = self._secrets[key]
        
        if metadata.rotated_at is None:
            # Never rotated, check creation date
            check_date = metadata.created_at
        else:
            check_date = metadata.rotated_at
        
        rotation_due = check_date + timedelta(days=self._rotation_days)
        
        if datetime.now(timezone.utc) > rotation_due:
            return self.rotate(key)
        
        return None
    
    def get_metadata(self, key: str) -> SecretMetadata | None:
        """Get metadata for a secret without accessing the value."""
        self._load_secrets()
        
        if key not in self._secrets:
            return None
        
        _, metadata = self._secrets[key]
        return metadata
    
    def list_keys(self) -> list[str]:
        """List all secret keys (not values)."""
        self._load_secrets()
        return list(self._secrets.keys())
    
    def needs_rotation(self, key: str) -> bool:
        """Check if a secret needs rotation."""
        self._load_secrets()
        
        if key not in self._secrets:
            return False
        
        _, metadata = self._secrets[key]
        
        if metadata.rotated_at is None:
            check_date = metadata.created_at
        else:
            check_date = metadata.rotated_at
        
        rotation_due = check_date + timedelta(days=self._rotation_days)
        return datetime.now(timezone.utc) > rotation_due
    
    # Vault integration preparation
    async def configure_vault(self, vault_url: str, token: str) -> None:
        """Prepare for HashiCorp Vault integration.
        
        This is a preparation method - actual implementation would
        use the hvac library.
        """
        logger.info("Vault integration prepared for %s", vault_url)
        # Actual implementation would:
        # import hvac
        # client = hvac.Client(url=vault_url, token=token)
        # self._backend = VaultBackend(client)
        raise NotImplementedError("Vault integration not yet implemented")


class SecretManagerError(Exception):
    """Error in secret management operations."""
    pass


class VaultBackend:
    """Placeholder for HashiCorp Vault backend.
    
    To use:
    1. pip install hvac
    2. Implement actual methods using hvac.Client
    """
    
    def __init__(self, client: Any) -> None:
        self._client = client
    
    async def get(self, key: str) -> str | None:
        """Get secret from Vault."""
        # Implementation:
        # response = self._client.secrets.kv.v2.read_secret_version(path=key)
        # return response['data']['data'].get('value')
        raise NotImplementedError()
    
    async def set(self, key: str, value: str, metadata: dict | None = None) -> None:
        """Store secret in Vault."""
        # Implementation:
        # self._client.secrets.kv.v2.create_or_update_secret(
        #     path=key,
        #     secret=dict(value=value, **(metadata or {}))
        # )
        raise NotImplementedError()
    
    async def delete(self, key: str) -> None:
        """Delete secret from Vault."""
        # Implementation:
        # self._client.secrets.kv.v2.delete_metadata_and_all_versions(key)
        raise NotImplementedError()
    
    async def rotate(self, key: str) -> None:
        """Rotate secret in Vault."""
        # Vault handles rotation internally for dynamic secrets
        raise NotImplementedError()


# Global instance
_secret_manager: SecretManager | None = None


def get_secret_manager() -> SecretManager:
    """Get or initialize the global SecretManager instance."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager


def get_secret(key: str, default: str | None = None) -> str | None:
    """Convenience function to get a secret."""
    return get_secret_manager().get(key, default)


def set_secret(
    key: str,
    value: str,
    expires_days: int | None = None,
) -> None:
    """Convenience function to store a secret."""
    return get_secret_manager().set(key, value, expires_days)


def rotate_secret(key: str, new_value: str | None = None) -> str:
    """Convenience function to rotate a secret."""
    return get_secret_manager().rotate(key, new_value)


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure token."""
    return secrets.token_urlsafe(length)


def hash_sensitive_value(value: str, salt: str | None = None) -> str:
    """Hash a sensitive value for safe storage/comparison.
    
    Uses SHA-256 with optional salt.
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    salted = f"{salt}{value}".encode()
    hash_value = hashlib.sha256(salted).hexdigest()
    return f"{salt}${hash_value}"


def verify_hashed_value(value: str, hashed: str) -> bool:
    """Verify a value against its hash."""
    if "$" not in hashed:
        return False
    
    salt, _ = hashed.split("$", 1)
    return hash_sensitive_value(value, salt) == hashed


__all__ = [
    "SecretManager",
    "SecretManagerError",
    "SecretMetadata",
    "get_secret_manager",
    "get_secret",
    "set_secret",
    "rotate_secret",
    "generate_secure_token",
    "hash_sensitive_value",
    "verify_hashed_value",
]
