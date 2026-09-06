"""Auth hardening: session-bound JWTs, revoke ownership, server-side RBAC."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from backend.platform.api import auth_router, router as v1_router, domain_error
from backend.platform.auth_utils import create_jwt
from backend.platform.db import metadata, auth_users, auth_tokens, workspace_partners
from backend.platform.schema import DomainError


def _spec(name):
    return {
        "name": name, "dataset_id": "demo", "models": ["ridge"],
        "features": {"groups": ["technical"], "names": []},
        "optimization": {"algorithm": "none", "population": 4, "generations": 2, "elitism": 1,
                         "min_features": 3, "max_features": 10, "max_drawdown": .9},
        "validation": {"method": "walk_forward", "train_ratio": .65, "folds": 2, "gap": 2, "locked_test": True},
        "backtest": {"capital": 10000, "cost_bps": .5, "slippage_bps": .2},
    }


class _Stub:
    def __init__(self, engine):
        self.engine = engine

    def start(self):
        pass

    def close(self):
        pass


def make_client(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "auth.db").as_posix())
    metadata.create_all(engine, tables=[auth_users, auth_tokens, workspace_partners])
    app = FastAPI()
    app.add_exception_handler(DomainError, domain_error)
    app.state.experiments = _Stub(engine)
    app.state.notebooks = _Stub(engine)
    app.include_router(auth_router())
    app.include_router(v1_router(lambda i: None, lambda: []))
    return TestClient(app), engine


def register(client, name, email, password="password123"):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def login(client, email, password="password123"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_first_user_bootstraps_admin_and_register_creates_session(tmp_path):
    with make_client(tmp_path)[0] as client:
        first = register(client, "Admin", "admin@x.io")
        assert first["role"] == "admin"
        assert first["session_id"]
        me = client.get("/api/auth/me", headers=auth(first["token"]))
        assert me.status_code == 200
        assert me.json()["role"] == "admin"
        assert me.json()["session_id"] == first["session_id"]
        second = register(client, "User", "user@x.io")
        assert second["role"] == "user"


def test_revoked_session_rejected_on_auth_and_api(tmp_path):
    with make_client(tmp_path)[0] as client:
        u = register(client, "Admin", "admin@x.io")
        r = client.post("/api/auth/token/revoke", headers=auth(u["token"]), json={"token_id": u["session_id"]})
        assert r.status_code == 200
        assert client.get("/api/auth/me", headers=auth(u["token"])).status_code == 401
        # Login no longer grants API access either.
        assert client.get("/api/v1/models", headers=auth(u["token"])).status_code == 401


def test_cross_user_revoke_blocked_but_admin_allowed(tmp_path):
    with make_client(tmp_path)[0] as client:
        admin = register(client, "Admin", "admin@x.io")
        user = register(client, "User", "user@x.io")
        # Horizontal escalation: user tries to kill the admin's session.
        r = client.post("/api/auth/token/revoke", headers=auth(user["token"]),
                        json={"token_id": admin["session_id"]})
        assert r.status_code == 404
        assert client.get("/api/auth/me", headers=auth(admin["token"])).status_code == 200
        # Admin revoking another user's session is legitimate.
        r = client.post("/api/auth/token/revoke", headers=auth(admin["token"]),
                        json={"token_id": user["session_id"]})
        assert r.status_code == 200
        assert client.get("/api/auth/me", headers=auth(user["token"])).status_code == 401


def test_password_change_kills_sessions_then_relogin(tmp_path):
    with make_client(tmp_path)[0] as client:
        u = register(client, "Admin", "admin@x.io")
        r = client.post("/api/auth/password", headers=auth(u["token"]),
                        json={"old_password": "password123", "new_password": "newpassword123"})
        assert r.status_code == 200
        assert client.get("/api/auth/me", headers=auth(u["token"])).status_code == 401
        fresh = login(client, "admin@x.io", "newpassword123")
        assert client.get("/api/auth/me", headers=auth(fresh["token"])).status_code == 200


def test_viewer_is_read_only(tmp_path):
    with make_client(tmp_path)[0] as client:
        admin = register(client, "Admin", "admin@x.io")
        user = register(client, "User", "user@x.io")
        r = client.patch(f"/api/auth/users/{user['id']}", headers=auth(admin["token"]), json={"role": "viewer"})
        assert r.status_code == 200, r.text
        v = login(client, "user@x.io")
        assert client.get("/api/v1/models", headers=auth(v["token"])).status_code == 200
        denied = client.post("/api/v1/experiments", headers=auth(v["token"]), json=_spec("viewer-try"))
        assert denied.status_code == 403
        assert denied.json()["detail"] == "Bu işlem için yetkiniz yok."
        assert client.get("/api/auth/users", headers=auth(v["token"])).status_code == 403


def test_admin_user_management_guards(tmp_path):
    with make_client(tmp_path)[0] as client:
        admin = register(client, "Admin", "admin@x.io")
        user = register(client, "User", "user@x.io")
        # Non-admin cannot manage users.
        assert client.get("/api/auth/users", headers=auth(user["token"])).status_code == 403
        # Admin cannot change its own account.
        assert client.patch(f"/api/auth/users/{admin['id']}", headers=auth(admin["token"]),
                            json={"role": "user"}).status_code == 403
        # Last active admin cannot be demoted.
        assert client.patch(f"/api/auth/users/{admin['id']}", headers=auth(admin["token"]),
                            json={"role": "user"}).status_code == 403
        second_admin = register(client, "Admin2", "admin2@x.io")
        assert second_admin["role"] == "user"
        # Promote via admin, then demote the first admin (no longer last).
        assert client.patch(f"/api/auth/users/{second_admin['id']}", headers=auth(admin["token"]),
                            json={"role": "admin"}).status_code == 200
        r = client.patch(f"/api/auth/users/{admin['id']}", headers=auth(second_admin["token"]),
                         json={"role": "user"})
        assert r.status_code == 200, r.text
        # Deactivation revokes all sessions.
        u = login(client, "user@x.io")
        assert client.patch(f"/api/auth/users/{user['id']}", headers=auth(second_admin["token"]),
                            json={"is_active": False}).status_code == 200
        assert client.get("/api/auth/me", headers=auth(u["token"])).status_code in (401, 403)


def test_logout_revokes_current_session_only(tmp_path):
    with make_client(tmp_path)[0] as client:
        register(client, "Admin", "admin@x.io")
        a = login(client, "admin@x.io")
        b = login(client, "admin@x.io")
        assert client.post("/api/auth/logout", headers=auth(a["token"])).status_code == 200
        assert client.get("/api/auth/me", headers=auth(a["token"])).status_code == 401
        assert client.get("/api/auth/me", headers=auth(b["token"])).status_code == 200


def test_revoke_all_ends_every_session(tmp_path):
    with make_client(tmp_path)[0] as client:
        register(client, "Admin", "admin@x.io")
        a = login(client, "admin@x.io")
        b = login(client, "admin@x.io")
        assert client.post("/api/auth/token/revoke-all", headers=auth(a["token"])).status_code == 200
        assert client.get("/api/auth/me", headers=auth(a["token"])).status_code == 401
        assert client.get("/api/auth/me", headers=auth(b["token"])).status_code == 401


def test_forged_jti_without_session_row_rejected(tmp_path):
    client, _ = make_client(tmp_path)
    with client:
        u = register(client, "Admin", "admin@x.io")
        forged = create_jwt(u["id"], "admin@x.io", "Admin", "admin", jti="no-such-session")
        assert client.get("/api/auth/me", headers=auth(forged)).status_code == 401


def test_sessions_list_flags_current(tmp_path):
    with make_client(tmp_path)[0] as client:
        register(client, "Admin", "admin@x.io")
        a = login(client, "admin@x.io")
        b = login(client, "admin@x.io")
        r = client.get("/api/auth/sessions", headers=auth(b["token"]))
        assert r.status_code == 200
        by_id = {s["id"]: s for s in r.json()["sessions"]}
        assert by_id[b["session_id"]]["current"] is True
        assert by_id[a["session_id"]]["current"] is False
