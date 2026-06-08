"""Testes do Deploy Service (Mês 4)."""

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models.models import Deployment

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


async def _create_app_with_status(client, status: str) -> int:
    r = await client.post(
        "/api/applications",
        json={"name": "Deploy App", "repo_url": "https://github.com/user/repo"},
    )
    app_id = r.json()["id"]
    # Força status diretamente no banco
    async with TestSession() as db:
        from sqlalchemy import select
        from app.models.models import Application
        result = await db.execute(select(Application).where(Application.id == app_id))
        obj = result.scalar_one()
        obj.status = status
        await db.commit()
    return app_id


@pytest.mark.asyncio
async def test_trigger_deploy_scan_passed(auth_client):
    app_id = await _create_app_with_status(auth_client, "scan_passed")

    with patch("app.api.routes.deployments._deploy_queue") as mock_q:
        mock_q.enqueue = MagicMock()
        r = await auth_client.post(f"/api/applications/{app_id}/deployments")
        assert r.status_code == 202
        body = r.json()
        assert body["status"] == "queued"
        assert body["application_id"] == app_id
        mock_q.enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_deploy_blocked_when_building(auth_client):
    app_id = await _create_app_with_status(auth_client, "building")
    r = await auth_client.post(f"/api/applications/{app_id}/deployments")
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_trigger_deploy_blocked_when_scan_failed(auth_client):
    app_id = await _create_app_with_status(auth_client, "scan_failed")
    r = await auth_client.post(f"/api/applications/{app_id}/deployments")
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_list_deployments_empty(auth_client):
    app_id = await _create_app_with_status(auth_client, "scan_passed")
    r = await auth_client.get(f"/api/applications/{app_id}/deployments")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_deployments_returns_history(auth_client):
    app_id = await _create_app_with_status(auth_client, "scan_passed")

    async with TestSession() as db:
        db.add(Deployment(application_id=app_id, image_tag="img:v1", status="deployed", endpoint_url="http://app.example.com"))
        db.add(Deployment(application_id=app_id, image_tag="img:v2", status="deploy_failed"))
        await db.commit()

    r = await auth_client.get(f"/api/applications/{app_id}/deployments")
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_deploy_requires_ownership(auth_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        await other.post("/api/auth/register", json={"email": "other@test.com", "password": "supersecret123"})
        login = await other.post("/api/auth/login", json={"email": "other@test.com", "password": "supersecret123"})
        other.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        r = await other.post("/api/applications", json={"name": "Other", "repo_url": "https://github.com/x/y"})
        other_app_id = r.json()["id"]

    r = await auth_client.post(f"/api/applications/{other_app_id}/deployments")
    assert r.status_code == 404
