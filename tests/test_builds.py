"""Testes do fluxo de builds (Mês 2).

O trigger de build (POST /builds) é testado com o Redis mockado,
então não é necessário ter Redis rodando para os testes passarem.

Rodar com:
    pytest
"""

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/api/auth/register", json={"email": "dev@test.com", "password": "supersecret123"})
        login = await c.post("/api/auth/login", json={"email": "dev@test.com", "password": "supersecret123"})
        token = login.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


@pytest.mark.asyncio
async def test_trigger_build_enqueues_job(auth_client: AsyncClient):
    # Cria aplicação
    r = await auth_client.post(
        "/api/applications",
        json={"name": "Test App", "repo_url": "https://github.com/user/repo"},
    )
    assert r.status_code == 201
    app_id = r.json()["id"]

    # Dispara build com Redis mockado
    with patch("app.api.routes.applications._build_queue") as mock_queue:
        mock_queue.enqueue = MagicMock()
        r = await auth_client.post(f"/api/applications/{app_id}/builds")
        assert r.status_code == 202
        assert r.json()["status"] == "queued"
        mock_queue.enqueue.assert_called_once()

    # Verifica que o status foi atualizado no banco
    r = await auth_client.get(f"/api/applications/{app_id}")
    assert r.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_trigger_build_conflict_when_already_queued(auth_client: AsyncClient):
    r = await auth_client.post(
        "/api/applications",
        json={"name": "Test App", "repo_url": "https://github.com/user/repo"},
    )
    app_id = r.json()["id"]

    with patch("app.api.routes.applications._build_queue"):
        await auth_client.post(f"/api/applications/{app_id}/builds")
        # Segunda chamada deve retornar 409
        r = await auth_client.post(f"/api/applications/{app_id}/builds")
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_list_build_logs_empty(auth_client: AsyncClient):
    r = await auth_client.post(
        "/api/applications",
        json={"name": "Test App", "repo_url": "https://github.com/user/repo"},
    )
    app_id = r.json()["id"]

    r = await auth_client.get(f"/api/applications/{app_id}/builds")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_build_endpoints_require_ownership(auth_client: AsyncClient):
    # Cria um segundo usuário
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as other:
        await other.post("/api/auth/register", json={"email": "other@test.com", "password": "supersecret123"})
        login = await other.post("/api/auth/login", json={"email": "other@test.com", "password": "supersecret123"})
        other.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

        # Cria app do outro usuário
        r = await other.post(
            "/api/applications",
            json={"name": "Other App", "repo_url": "https://github.com/other/repo"},
        )
        app_id = r.json()["id"]

    # Tenta disparar build como auth_client (dono errado) → 404
    r = await auth_client.post(f"/api/applications/{app_id}/builds")
    assert r.status_code == 404
