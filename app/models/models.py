"""Modelos do banco de dados — FoolGuard.

Entidades:
  Mês 1: User, Application
  Mês 2: BuildLog
  Mês 3: ScanResult
  Mês 4: Deployment
  Mês 5: MonitorAlert
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Armazenamos apenas o HASH da senha, nunca a senha em si.
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    applications: Mapped[list["Application"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


# Valores válidos de status (documentados aqui para facilitar referência):
# "registered" → "queued" → "building" → "build_success" | "build_failed"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    # URL do repositório Git que será construído/auditado nas próximas fases.
    repo_url: Mapped[str] = mapped_column(String(500))
    # Status simples por enquanto; vira um enum mais rico nas fases futuras.
    status: Mapped[str] = mapped_column(String(50), default="registered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owner: Mapped["User"] = relationship(back_populates="applications")

    build_logs: Mapped[list["BuildLog"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    scan_results: Mapped[list["ScanResult"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    deployments: Mapped[list["Deployment"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    monitor_alerts: Mapped[list["MonitorAlert"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class BuildLog(Base):
    """Registro de uma execução de build para uma aplicação.

    Cada vez que um build é disparado, um BuildLog é criado ao fim com a
    saída completa do processo e se teve sucesso ou não.
    """

    __tablename__ = "build_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    output: Mapped[str] = mapped_column(Text, default="")
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    application: Mapped["Application"] = relationship(back_populates="build_logs")


# ── Mês 3: Security Scanner ──────────────────────────────────────────────────
# Fluxo de status pós-build: "build_success" → "scanning" → "scan_passed" | "scan_failed"

class ScanResult(Base):
    """Resultado de uma ferramenta de segurança (Trivy, Semgrep ou Gitleaks)."""

    __tablename__ = "scan_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    # "trivy" | "semgrep" | "gitleaks"
    tool: Mapped[str] = mapped_column(String(50))
    # Saída JSON bruta da ferramenta (para auditoria e re-análise futura)
    raw_output: Mapped[str] = mapped_column(Text, default="{}")
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    # True = nenhuma finding crítica encontrada
    passed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    application: Mapped["Application"] = relationship(back_populates="scan_results")


# ── Mês 4: Deploy Service ─────────────────────────────────────────────────────
# Fluxo de status: "queued" → "deploying" → "deployed" | "deploy_failed"

class Deployment(Base):
    """Representa uma tentativa de deploy de uma aplicação na nuvem."""

    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    image_tag: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="queued")
    # URL pública gerada pelo Terraform/AWS após deploy bem-sucedido
    endpoint_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Log completo do processo de deploy (terraform output, erros, etc.)
    deploy_log: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    application: Mapped["Application"] = relationship(back_populates="deployments")


# ── Mês 5: Monitor Service ────────────────────────────────────────────────────

class MonitorAlert(Base):
    """Alerta gerado pelo Monitor Service para uma aplicação deployada."""

    __tablename__ = "monitor_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    # "info" | "warning" | "critical"
    level: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    application: Mapped["Application"] = relationship(back_populates="monitor_alerts")
