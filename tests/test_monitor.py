"""Testes do Monitor Service (Mês 5)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models.models import MonitorAlert

test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/api/auth/register", json={"email": "dev@test.com", "password": "supersecret123"})
        login = await c.post("/api/auth/login", json={"email": "dev@test.com", "password": "supersecret123"})
        c.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield c


@pytest_asyncio.fixture
async def app_id(auth_client):
    r = await auth_client.post(
        "/api/applications",
        json={"name": "Monitor App", "repo_url": "https://github.com/user/repo"},
    )
    return r.json()["id"]


@pytest.mark.asyncio
async def test_list_alerts_empty(auth_client, app_id):
    r = await auth_client.get(f"/api/applications/{app_id}/alerts")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_alerts_filters_acknowledged(auth_client, app_id):
    async with TestSession() as db:
        db.add(MonitorAlert(application_id=app_id, level="warning", message="App lenta", acknowledged=False))
        db.add(MonitorAlert(application_id=app_id, level="info", message="Tudo ok", acknowledged=True))
        await db.commit()

    # only_active=true (padrão) — deve retornar apenas o não reconhecido
    r = await auth_client.get(f"/api/applications/{app_id}/alerts")
    assert len(r.json()) == 1
    assert r.json()[0]["message"] == "App lenta"

    # only_active=false — deve retornar os 2
    r = await auth_client.get(f"/api/applications/{app_id}/alerts?only_active=false")
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_acknowledge_alert(auth_client, app_id):
    async with TestSession() as db:
        alert = MonitorAlert(application_id=app_id, level="critical", message="App fora do ar")
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        alert_id = alert.id

    r = await auth_client.patch(
        f"/api/applications/{app_id}/alerts/{alert_id}",
        json={"acknowledged": True},
    )
    assert r.status_code == 200
    assert r.json()["acknowledged"] is True

    # Agora não aparece mais na lista ativa
    r = await auth_client.get(f"/api/applications/{app_id}/alerts")
    assert r.json() == []


@pytest.mark.asyncio
async def test_alerts_summary(auth_client, app_id):
    async with TestSession() as db:
        db.add(MonitorAlert(application_id=app_id, level="critical", message="Erro 1"))
        db.add(MonitorAlert(application_id=app_id, level="critical", message="Erro 2"))
        db.add(MonitorAlert(application_id=app_id, level="warning", message="Aviso"))
        db.add(MonitorAlert(application_id=app_id, level="info", message="Info", acknowledged=True))
        await db.commit()

    r = await auth_client.get("/api/applications/alerts/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["critical"] == 2
    assert body["warning"] == 1
    assert body["info"] == 0  # estava acknowledged


@pytest.mark.asyncio
async def test_alerts_require_ownership(auth_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        await other.post("/api/auth/register", json={"email": "other@test.com", "password": "supersecret123"})
        login = await other.post("/api/auth/login", json={"email": "other@test.com", "password": "supersecret123"})
        other.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        r = await other.post("/api/applications", json={"name": "Other", "repo_url": "https://github.com/x/y"})
        other_app_id = r.json()["id"]

    r = await auth_client.get(f"/api/applications/{other_app_id}/alerts")
    assert r.status_code == 404
