"""Schemas Pydantic: definem o formato dos dados que entram e saem da API.

Separar os schemas dos modelos do banco é uma prática importante de segurança:
- Controlamos exatamente quais campos o cliente pode enviar (evita que alguém
  injete campos indevidos, ex.: tentar definir o próprio `id` ou status).
- Controlamos o que sai (ex.: NUNCA retornamos o hash da senha).

Repare que não existe nenhum schema de saída que inclua a senha — isso é
proposital.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- User ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


# ---------- Auth ----------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ---------- Application ----------
class ApplicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    repo_url: str = Field(min_length=1, max_length=500)


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    repo_url: str
    status: str
    created_at: datetime


# ---------- BuildLog ----------
class BuildLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    output: str
    success: bool
    created_at: datetime


class BuildTriggered(BaseModel):
    message: str
    application_id: int
    status: str


# ---------- ScanResult (Mês 3) ----------
class ScanResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    tool: str
    raw_output: str
    findings_count: int
    passed: bool
    created_at: datetime


class ScanSummary(BaseModel):
    application_id: int
    all_passed: bool
    results: list[ScanResultRead]


# ---------- Deployment (Mês 4) ----------
class DeploymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    image_tag: str
    status: str
    endpoint_url: str | None
    deploy_log: str
    created_at: datetime


class DeployTriggered(BaseModel):
    message: str
    deployment_id: int
    application_id: int
    status: str


# ---------- MonitorAlert (Mês 5) ----------
class MonitorAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    level: str
    message: str
    acknowledged: bool
    created_at: datetime


class AcknowledgeRequest(BaseModel):
    acknowledged: bool = True
