import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()
# Used to burn the same CPU time when the email is unknown (prevents user enumeration by timing)
DUMMY_HASH = _hasher.hash("dummy-password-for-timing-equalisation")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: uuid.UUID, role: str) -> tuple[str, int]:
    """Returns (jwt, expires_in_seconds)."""
    s = get_settings()
    now = datetime.now(UTC)
    ttl = timedelta(minutes=s.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), int(ttl.total_seconds())


def decode_access_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(
        token,
        s.jwt_secret,
        algorithms=[s.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Refresh tokens are stored hashed; a DB leak must not leak usable tokens."""
    return hashlib.sha256(token.encode()).hexdigest()
