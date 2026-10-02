from tests.conftest import PASSWORD

API = "/api/v1"
REG = {"email": "Jane@Example.com", "password": PASSWORD, "first_name": "Jane"}


async def test_health(client):
    assert (await client.get("/health")).json() == {"status": "ok"}
    assert (await client.get("/ready")).json() == {"status": "ready"}


async def test_register_sets_cookie_and_normalises_email(client):
    r = await client.post(f"{API}/auth/register", json=REG)
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "jane@example.com"
    assert body["user"]["role"] == "customer"
    assert body["access_token"] and "refresh_token" not in body
    set_cookie = r.headers["set-cookie"].lower()
    assert "refresh_token=" in set_cookie and "httponly" in set_cookie


async def test_register_duplicate_email(client):
    await client.post(f"{API}/auth/register", json=REG)
    r = await client.post(f"{API}/auth/register", json=REG)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_already_registered"


async def test_register_weak_password_uses_uniform_error_format(client):
    r = await client.post(f"{API}/auth/register", json={**REG, "password": "12345678"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert err["details"][0]["field"] == "password"
    assert err["request_id"]


async def test_login_and_me(client):
    await client.post(f"{API}/auth/register", json=REG)
    r = await client.post(f"{API}/auth/login", json={"email": "jane@example.com", "password": PASSWORD})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["email"] == "jane@example.com"


async def test_login_wrong_password(client):
    await client.post(f"{API}/auth/register", json=REG)
    r = await client.post(f"{API}/auth/login", json={"email": "jane@example.com", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


async def test_me_requires_auth(client):
    r = await client.get(f"{API}/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"
    bad = await client.get(f"{API}/auth/me", headers={"Authorization": "Bearer garbage"})
    assert bad.json()["error"]["code"] == "invalid_token"


async def test_refresh_rotates_and_detects_reuse(client):
    await client.post(f"{API}/auth/register", json=REG)
    old = client.cookies.get("refresh_token")
    assert old

    r = await client.post(f"{API}/auth/refresh")  # cookie jar sends the current cookie
    assert r.status_code == 200 and r.json()["access_token"]
    new = client.cookies.get("refresh_token")
    assert new and new != old

    # Replaying the already-rotated token => theft signal => family revoked
    replay = await client.post(f"{API}/auth/refresh", headers={"Cookie": f"refresh_token={old}"})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "refresh_token_reused"

    # ...and the newer token from the same family is now dead too
    after = await client.post(f"{API}/auth/refresh", headers={"Cookie": f"refresh_token={new}"})
    assert after.status_code == 401


async def test_logout_revokes_refresh_token(client):
    await client.post(f"{API}/auth/register", json=REG)
    token = client.cookies.get("refresh_token")
    assert (await client.post(f"{API}/auth/logout")).status_code == 204
    r = await client.post(f"{API}/auth/refresh", headers={"Cookie": f"refresh_token={token}"})
    assert r.status_code == 401


async def test_refresh_without_cookie(client):
    r = await client.post(f"{API}/auth/refresh")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "refresh_token_missing"


async def test_update_profile(client):
    reg = (await client.post(f"{API}/auth/register", json=REG)).json()
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    r = await client.patch(f"{API}/auth/me", headers=h, json={"last_name": "Doe", "phone": "+919876543210"})
    assert r.status_code == 200
    assert r.json()["last_name"] == "Doe" and r.json()["phone"] == "+919876543210"
