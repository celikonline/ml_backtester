"""Authentication tables and helpers for users, session tokens, and login workflows."""
import os
import secrets
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any;

import jwt
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table, Index, Boolean, Float, JSON, create_engine, MetaData, event, select

ROOT = os.environ.get("REGIME_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORAGE = os.environ.get("REGIMELAB_STORAGE", os.path.join(ROOT, "data", "platform"))

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

metadata = MetaData()

users = Table(
    "auth_users",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(256), unique=True, nullable=False, index=True),
    Column("password_hash", String(128), nullable=False),
    Column("password_salt", String(32), nullable=False),
    Column("name", String(120), nullable=False),
    Column("role", String(32), nullable=False, default="user"),
    Column("is_active", Integer, nullable=False, default=1),
    Column("created_at", String(40), nullable=False),
    Column("last_login_at", String(40), nullable=True),
    Column("features", JSON, nullable=False, default=dict),
    Column("workspace_id", String(36), nullable=True),
)
Index("ix_auth_users_workspace", users.c.workspace_id)

auth_tokens = Table(
    "auth_tokens",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(36), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False),
    Column("token_hash", String(128), nullable=False, unique=True),
    Column("issued_at", String(40), nullable=False),
    Column("expires_at", String(40), nullable=False),
    Column("revoked", Integer, nullable=False, default=0),
    Column("user_agent", String(256)),
)
Index("ix_auth_tokens_user", auth_tokens.c.user_id)
Index("ix_auth_tokens_expires", auth_tokens.c.expires_at)

password_partners = Table(
    "workspace_partners",
    metadata,
    Column("workspace_id", String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", String(36), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False),
    Column("role", String(32), nullable=False, default="member"),
    Column("created_at", String(40), nullable=False),
    PrimaryKeyConstraint("workspace_id", "user_id"),
)

DEFAULT_JWT_SECRET = os.environ.get("REGIMELAB_JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = int(os.environ.get("REGIMELAB_JWT_EXPIRY", "86400"))


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
    return jwt.encode(payload, DEFAULT_JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, DEFAULT_JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def create_heartbeat_hash(user_id: str, token_id: str) -> str:
    key = f"regimelab:hb:{token_id}:{user_id}"
    return hashlib.sha256(key.encode()).hexdigest()


def connect(url: str | None = None):
    url = url or os.environ.get("REGIMELAB_DATABASE_URL", f"sqlite:///{STORAGE}/registry.sqlite3")
    kwargs = {"connect_args": {"check_same_thread": False, "timeout": 30}} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _on_connect(dbapi, _):
            cur = dbapi.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
    return engine


def migrate(eng):
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    with eng.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")