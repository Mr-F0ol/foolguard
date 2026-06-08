"""Testes do fluxo principal da API (Mês 1).

Usamos um banco SQLite em memória para os testes, então eles rodam rápido
e sem depender do Postgres. Isso cobre o caminho feliz: registrar, logar,
criar aplicação e garantir que o controle de acesso funciona.

Rodar com:
    pytest
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # Registro
    r = await client.post(
        "/api/auth/register",
        json={"email": "user@test.com", "password": "supersecret123"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "user@test.com"
    # A resposta NÃO deve conter a senha nem o hash.
    assert "password" not in r.json()
    assert "hashed_password" not in r.json()

    # Login
    r = await client.post(
        "/api/auth/login",
        json={"email": "user@test.com", "password": "supersecret123"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client: AsyncClient):
    # Sem token, deve recusar.
    r = await client.get("/api/applications")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_and_list_application(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "owner@test.com", "password": "supersecret123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "owner@test.com", "password": "supersecret123"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Cria aplicação
    r = await client.post(
        "/api/applications",
        json={"name": "Minha App", "repo_url": "https://github.com/user/app"},
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["status"] == "registered"

    # Lista aplicações
    r = await client.get("/api/applications", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
