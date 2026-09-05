import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

import jwt
from sqlalchemy import select

from .auth import (
    create_jwt,
    decode_jwt,
    hash_password,
    verify_password,
)
from .db import connect, migrate, users as auth_users, auth_tokens, workspace_partners
from .schema import DomainError


CONFIG = {
    "JWT_SECRET": os.environ.get("REGIMELAB_JWT_SECRET", secrets.token_hex(32)),
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRY_SECONDS": int(os.environ.get("REGIMELAB_JWT_EXPIRY", "86400")),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuthService:
    def __init__(self):
        self._engine = connect()
        self._migrate()

    def _migrate(self):
        try:
            migrate(self._engine)
        except Exception:
            pass

    def _profile_id(self) -> str:
        return str(uuid.uuid4())

    def register(self, name: str, email: str, password: str, role: str = "user") -> dict[str, Any]:
        email = email.strip().lower()
        name = name.strip()
        existing = self._engine.scalar(select(auth_users.c.id).where(auth_users.c.email == email))
        if existing:
            raise DomainError("Bu e-posta zaten kayıtlı. Giriş yapmayı deneyin.", 409, "email_conflict")
        salt, pw_hash = hash_password(password)
        user_id = self._profile_id()
        now = _now()
        with self._engine.begin() as con:
            con.execute(auth_users.insert().values(
                id=user_id,
                email=email,
                password_hash=pw_hash,
                password_salt=salt,
                name=name,
                role=role,
                is_active=1,
                created_at=now,
                last_login_at=None,
                features={},
                workspace_id=None,
            ))
        token = create_jwt(user_id, email, name, role)
        return {"id": user_id, "email": email, "name": name, "role": role, "token": token, "created_at": now}

    def login(self, email: str, password: str, remember: bool = True) -> dict[str, Any]:
        email = email.strip().lower()
        row = self._engine.execute(select(auth_users).where(auth_users.c.email == email)).first()
        if not row:
            raise DomainError("E-posta veya şifre hatalı.", 401, "invalid_credentials")
        if not verify_password(password, row.password_salt, row.password_hash):
            raise DomainError("E-posta veya şifre hatalı.", 401, "invalid_credentials")
        if not row.is_active:
            raise DomainError("Hesap aktif değil.", 403, "inactive")
        token_id = secrets.token_hex(16)
        now = datetime.now(timezone.utc)
        expires = now.timestamp() + CONFIG["JWT_EXPIRY_SECONDS"]
        with self._engine.begin() as con:
            con.execute(auth_users.update().where(auth_users.c.id == row.id).values(last_login_at=_now()))
            con.execute(auth_tokens.insert().values(
                id=token_id,
                user_id=row.id,
                token_hash=hashlib.sha256(token_id.encode()).hexdigest(),
                issued_at=_now(),
                expires_at=datetime.fromtimestamp(expires, tz=timezone.utc).isoformat(),
                revoked=0,
            ))
        token = create_jwt(row.id, row.email, row.name, row.role)
        return {"id": row.id, "email": row.email, "name": row.name, "role": row.role, "token": token}

    def logout(self, token: str, user_id: str) -> None:
        payload = decode_jwt(token)
        if not payload:
            return
        token_id = secrets.token_hex(16)
        with self._engine.begin() as con:
            con.execute(auth_tokens.update().where(auth_tokens.c.user_id == user_id).values(revoked=1))

    @staticmethod
    def get_current_user(token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        payload = decode_jwt(token)
        if not payload:
            return None
        if "sub" not in payload:
            return None
        return payload

    def get_community(self, token: str) -> dict[str, Any]:
        payload = self.get_current_user(token)
        if not payload:
            raise DomainError("Lütfen önce giriş yapın.", 401, "unauthorized")
        user_id = payload.get("sub")
        ws_id = self._engine.scalar(select(auth_users.c.workspace_id).where(auth_users.c.id == user_id))
        ws = None
        if ws_id:
            from .db import workspaces
            row = self._engine.execute(select(workspaces).where(workspaces.c.id == ws_id)).first()
            if row:
                ws = {"id": row.id, "code": row.code, "name": row.name, "market": row.market}
        return {"user": {"id": user_id, **payload}, "workspace": ws}