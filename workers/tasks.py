"""Tarefas assíncronas executadas pelo Build Worker.

Cada função aqui é enfileirada via RQ e roda num processo separado.
Isso isola o código de build da API principal — se o build travar ou
consumir muita CPU, a API continua respondendo normalmente.

Fluxo de um build:
  1. API recebe POST /api/applications/{id}/builds
  2. API atualiza status → "queued" e enfileira run_build(app_id)
  3. Worker pega a tarefa da fila Redis
  4. Worker clona o repo, roda docker build, atualiza status e salva o log
"""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

from redis import Redis
from rq import Queue
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Application, BuildLog


def run_build(app_id: int) -> None:
    """Ponto de entrada da tarefa RQ. Roda o build de forma assíncrona."""
    asyncio.run(_async_build(app_id))


async def _async_build(app_id: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Application).where(Application.id == app_id))
        app_obj = result.scalar_one_or_none()
        if app_obj is None:
            return

        app_obj.status = "building"
        await db.commit()

        log_output = ""
        success = False

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                log_output += _run_step(
                    ["git", "clone", "--depth", "1", app_obj.repo_url, tmpdir],
                    timeout=120,
                    step_label="git clone",
                    env={"GIT_TERMINAL_PROMPT": "0"},
                )

                dockerfile_path = Path(tmpdir) / "Dockerfile"
                if not dockerfile_path.exists():
                    generated = _generate_dockerfile(tmpdir)
                    dockerfile_path.write_text(generated)
                    log_output += f"\n[INFO] Dockerfile não encontrado — gerado automaticamente ({_detect_stack(tmpdir)})\n"

                image_tag = f"foolguard/app-{app_id}:latest"
                log_output += _run_step(
                    ["docker", "build", "-t", image_tag, tmpdir],
                    timeout=300,
                    step_label="docker build",
                )

            success = True

        except subprocess.CalledProcessError as exc:
            log_output += f"\n[ERRO] Processo terminou com código {exc.returncode}\n"
            log_output += exc.stdout or ""
            log_output += exc.stderr or ""
        except subprocess.TimeoutExpired as exc:
            log_output += f"\n[ERRO] Timeout após {exc.timeout}s\n"
        except Exception as exc:
            log_output += f"\n[ERRO] {exc}\n"

        build_log = BuildLog(
            application_id=app_id,
            output=log_output,
            success=success,
        )
        db.add(build_log)
        app_obj.status = "build_success" if success else "build_failed"
        await db.commit()

    # Após build bem-sucedido, dispara o scanner automaticamente
    if success:
        from workers.scanner import run_security_scan
        image_tag = f"foolguard/app-{app_id}:latest"
        conn = Redis.from_url(settings.redis_url)
        q = Queue("builds", connection=conn)
        q.enqueue(run_security_scan, app_id, image_tag)


def _detect_stack(directory: str) -> str:
    d = Path(directory)
    if (d / "package.json").exists():
        return "node"
    if (d / "requirements.txt").exists() or (d / "pyproject.toml").exists():
        return "python"
    if (d / "go.mod").exists():
        return "go"
    if (d / "pom.xml").exists() or (d / "build.gradle").exists():
        return "java"
    if (d / "Gemfile").exists():
        return "ruby"
    return "generic"


def _generate_dockerfile(directory: str) -> str:
    stack = _detect_stack(directory)
    d = Path(directory)

    if stack == "node":
        start = "npm start"
        if (d / "package.json").exists():
            import json
            try:
                pkg = json.loads((d / "package.json").read_text())
                scripts = pkg.get("scripts", {})
                if "start" not in scripts and "dev" in scripts:
                    start = "npm run dev"
            except Exception:
                pass
        return (
            "FROM node:20-alpine\n"
            "WORKDIR /app\n"
            "COPY package*.json ./\n"
            "RUN npm install --production\n"
            "COPY . .\n"
            f'CMD ["{start.split()[0]}", "{start.split()[1]}", "{start.split()[2]}"]\n'
            if len(start.split()) == 3 else
            "FROM node:20-alpine\n"
            "WORKDIR /app\n"
            "COPY package*.json ./\n"
            "RUN npm install --production\n"
            "COPY . .\n"
            f'CMD ["npm", "start"]\n'
        )
    if stack == "python":
        has_req = (d / "requirements.txt").exists()
        return (
            "FROM python:3.12-slim\n"
            "WORKDIR /app\n"
            + ("COPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\n" if has_req else "")
            + "COPY . .\n"
            'CMD ["python", "-m", "http.server", "8000"]\n'
        )
    if stack == "go":
        return (
            "FROM golang:1.22-alpine AS builder\n"
            "WORKDIR /app\n"
            "COPY go.* ./\n"
            "RUN go mod download\n"
            "COPY . .\n"
            "RUN go build -o app .\n"
            "FROM alpine:latest\n"
            "COPY --from=builder /app/app /app\n"
            'CMD ["/app"]\n'
        )
    # generic fallback
    return (
        "FROM ubuntu:22.04\n"
        "WORKDIR /app\n"
        "COPY . .\n"
        'CMD ["echo", "FoolGuard build OK"]\n'
    )


def _run_step(cmd: list[str], timeout: int, step_label: str, env: dict | None = None) -> str:
    """Executa um comando de shell, captura saída combinada e levanta exceção se falhar."""
    merged_env = {**os.environ, **(env or {})}
    header = f"\n{'='*60}\n[STEP] {step_label}\n{'='*60}\n"
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
        env=merged_env,
    )
    return header + result.stdout + result.stderr
