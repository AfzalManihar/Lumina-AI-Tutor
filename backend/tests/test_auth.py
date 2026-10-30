import pytest

from tests.conftest import register


async def test_register_login_me_logout(client):
    body = await register(client, "a@example.com")
    assert body["user"]["role"] == "student"
    assert "password" not in str(body).lower().replace("password_", "")
    me = await client.get("/api/v1/users/me")
    assert me.status_code == 200 and me.json()["email"] == "a@example.com"
    assert "password_hash" not in me.text
    out = await client.post("/api/v1/auth/logout")
    assert out.status_code == 204
    assert (await client.get("/api/v1/users/me")).status_code == 401  # session invalidated


async def test_duplicate_email_and_weak_password(client):
    await register(client, "dup@example.com")
    r = await client.post("/api/v1/auth/register", json={"email": "dup@example.com", "password": "Passw0rd123"})
    assert r.status_code == 409
    r = await client.post("/api/v1/auth/register", json={"email": "w@example.com", "password": "alllettersnodigit"})
    assert r.status_code == 422


async def test_login_wrong_password_safe_error(client):
    await register(client, "b@example.com")
    c2 = client
    r = await c2.post("/api/v1/auth/login", json={"email": "b@example.com", "password": "Wrong12345"})
    assert r.status_code == 401
    r2 = await c2.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "Wrong12345"})
    assert r.json()["error"]["message"] == r2.json()["error"]["message"]  # no user enumeration


async def test_brute_force_lockout(client):
    await register(client, "c@example.com")
    codes = []
    for _ in range(7):
        r = await client.post("/api/v1/auth/login", json={"email": "c@example.com", "password": "Wrong12345"})
        codes.append(r.status_code)
    assert codes[:5] == [401] * 5 and codes[5] == 429 and "retry-after" in r.headers
    # even the correct password is blocked while locked
    r = await client.post("/api/v1/auth/login", json={"email": "c@example.com", "password": "Passw0rd123"})
    assert r.status_code == 429


async def test_refresh_rotation_and_reuse_detection(client):
    await register(client, "d@example.com")
    old_cookie = client.cookies.get("lumina_refresh")
    assert old_cookie
    r = await client.post("/api/v1/auth/refresh")  # missing CSRF header
    assert r.status_code == 401
    r = await client.post("/api/v1/auth/refresh", headers={"X-Requested-With": "lumina"})
    assert r.status_code == 200
    new_cookie = client.cookies.get("lumina_refresh")
    assert new_cookie != old_cookie
    # replay the old (rotated-out) token -> rejected and all sessions revoked
    client.cookies.set("lumina_refresh", old_cookie, path="/api/v1/auth")
    r = await client.post("/api/v1/auth/refresh", headers={"X-Requested-With": "lumina"})
    assert r.status_code == 401
    client.cookies.set("lumina_refresh", new_cookie, path="/api/v1/auth")
    r = await client.post("/api/v1/auth/refresh", headers={"X-Requested-With": "lumina"})
    assert r.status_code == 401


async def test_unauthenticated_and_tampered_token(client):
    assert (await client.get("/api/v1/users/me")).status_code == 401
    r = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


async def test_profile_update_and_password_change(client):
    await register(client, "e@example.com")
    r = await client.patch("/api/v1/users/me", json={"name": "New", "settings": {"memory_enabled": False, "learning_topic": "Physics"}})
    assert r.status_code == 200 and r.json()["settings"]["memory_enabled"] is False
    r = await client.patch("/api/v1/users/me", json={"role": "admin"})  # extra fields forbidden
    assert r.status_code == 422
    r = await client.post("/api/v1/users/me/password", json={"old_password": "Passw0rd123", "new_password": "NewPassw0rd9"})
    assert r.status_code == 204
    assert (await client.get("/api/v1/users/me")).status_code == 401  # sessions revoked
    r = await client.post("/api/v1/auth/login", json={"email": "e@example.com", "password": "NewPassw0rd9"})
    assert r.status_code == 200


async def test_request_id_and_health(client):
    r = await client.get("/health")
    assert r.status_code == 200 and r.headers["x-request-id"]
    r = await client.get("/ready")
    assert r.status_code == 200
    r = await client.post("/api/v1/auth/login", json={"email": "bad"})
    assert r.status_code == 422 and r.json()["error"]["request_id"]
