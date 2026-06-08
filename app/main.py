"""Ponto de entrada da API Principal do FoolGuard.

Para rodar em desenvolvimento:
    uvicorn app.main:app --reload

A documentação interativa fica disponível automaticamente em:
    http://localhost:8000/docs

No Mês 1 criamos as tabelas direto no startup para simplificar. Numa fase
posterior, isso será substituído por migrações com Alembic (mais profissional
e seguro para produção).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import applications, auth, deployments, monitor, scans
from app.core.database import Base, engine

# Importante: importar os modelos para que o SQLAlchemy os registre antes
# de criar as tabelas.
from app.models import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cria as tabelas no banco ao iniciar (apenas para desenvolvimento).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="FoolGuard API",
    description="Plataforma de deploy seguro — build, scan, deploy e monitor automatizados.",
    version="0.4.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Endpoint simples para verificar se a API está no ar."""
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(applications.router)
app.include_router(scans.router)
app.include_router(deployments.router)
app.include_router(monitor.router)
