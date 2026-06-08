"""Configuração da conexão com o banco de dados (assíncrona).

Usamos SQLAlchemy 2.0 com suporte async, que é o padrão moderno e combina
com a natureza assíncrona do FastAPI. A sessão é injetada nas rotas via
dependência do FastAPI (ver get_db abaixo).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# O engine gerencia o pool de conexões com o Postgres.
engine = create_async_engine(settings.database_url, echo=False, future=True)

# Fábrica de sessões: cada requisição recebe a sua própria sessão.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Classe base para todos os modelos do banco."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependência do FastAPI que fornece uma sessão de banco por requisição.

    O padrão `async with` garante que a sessão seja sempre fechada
    corretamente, mesmo se ocorrer um erro.
    """
    async with AsyncSessionLocal() as session:
        yield session
