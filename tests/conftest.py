import os

# Must be set before the app is imported (settings are cached at import time).
os.environ.update(
    DATABASE_URL="sqlite+aiosqlite://",
    ENVIRONMENT="test",
    RATE_LIMIT_ENABLED="false",
    COOKIE_SECURE="false",
    JWT_SECRET="test-secret-test-secret-test-secret-123456",
)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.db.models  # noqa: E402, F401
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.auth.models import Role, User  # noqa: E402

PASSWORD = "Passw0rd!x"


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _make_user(session_factory, email: str, role: Role) -> None:
    async with session_factory() as s:
        s.add(User(email=email, password_hash=hash_password(PASSWORD), role=role))
        await s.commit()


async def _login_headers(client, email: str) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def admin_headers(client, session_factory):
    await _make_user(session_factory, "admin@example.com", Role.admin)
    return await _login_headers(client, "admin@example.com")


@pytest.fixture
async def customer_headers(client, session_factory):
    await _make_user(session_factory, "cust@example.com", Role.customer)
    return await _login_headers(client, "cust@example.com")
