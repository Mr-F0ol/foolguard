"""Testes do Security Scanner (Mês 3)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import ScanResult
from tests.conftest import TestSession


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
        json={"name": "Scan Test App", "repo_url": "https://github.com/user/repo"},
    )
    return r.json()["id"]


@pytest.mark.asyncio
async def test_scan_summary_empty(auth_client, app_id):
    r = await auth_client.get(f"/api/applications/{app_id}/scans")
    assert r.status_code == 200
    body = r.json()
    assert body["application_id"] == app_id
    assert body["all_passed"] is True
    assert body["results"] == []


@pytest.mark.asyncio
async def test_scan_summary_with_results(auth_client, app_id):
    # Insere scan results diretamente no banco
    async with TestSession() as db:
        db.add(ScanResult(application_id=app_id, tool="semgrep", findings_count=3, passed=False))
        db.add(ScanResult(application_id=app_id, tool="gitleaks", findings_count=0, passed=True))
        db.add(ScanResult(application_id=app_id, tool="trivy", findings_count=1, passed=False))
        await db.commit()

    r = await auth_client.get(f"/api/applications/{app_id}/scans")
    assert r.status_code == 200
    body = r.json()
    assert body["all_passed"] is False
    assert len(body["results"]) == 3
    tools = {s["tool"] for s in body["results"]}
    assert tools == {"semgrep", "gitleaks", "trivy"}


@pytest.mark.asyncio
async def test_scan_requires_ownership(auth_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        await other.post("/api/auth/register", json={"email": "other@test.com", "password": "supersecret123"})
        login = await other.post("/api/auth/login", json={"email": "other@test.com", "password": "supersecret123"})
        other.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        r = await other.post("/api/applications", json={"name": "Other", "repo_url": "https://github.com/x/y"})
        other_app_id = r.json()["id"]

    r = await auth_client.get(f"/api/applications/{other_app_id}/scans")
    assert r.status_code == 404
