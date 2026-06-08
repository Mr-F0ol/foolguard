"""Configurações centrais da aplicação.

Carrega valores do arquivo .env de forma validada usando pydantic-settings.
Isso garante que segredos (como a SECRET_KEY) nunca fiquem hard-coded no
código — uma boa prática de segurança fundamental.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Banco de dados
    database_url: str

    # Segurança / JWT
    secret_key: str
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    # Fila (Redis)
    redis_url: str = "redis://localhost:6379/0"

    # App
    environment: str = "development"


# Instância única usada em toda a aplicação.
settings = Settings()
