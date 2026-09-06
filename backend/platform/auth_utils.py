"""Authentication utilities: password hashing and JWT handling."""
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Any

import jwt

JWT_SECRET = secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 24 * 60 * 60


def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    iterations = 210000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations, dklen=64)
    return salt, dk.hex()


def verify_password(password: str, salt: str, expected: str) -> bool:
    iterations = 210000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations, dklen=64)
    return hmac.compare_digest(dk.hex(), expected)


def create_jwt(user_id: str, email: str, name: str, role: str = "user", extra: dict | None = None) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "role": role,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(datetime.now(timezone.utc).timestamp()) + JWT_EXPIRY_SECONDS,
        "jti": secrets.token_urlsafe(16),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
