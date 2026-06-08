"""Deploy Worker — Mês 4.

Fluxo de deploy:
  1. Push da imagem Docker para o ECR (AWS Elastic Container Registry)
  2. Executa `terraform apply` para criar/atualizar o serviço ECS Fargate
  3. Captura a URL pública do output do Terraform
  4. Atualiza o status do Deployment e da Application no banco

Pré-requisitos (configurados via variáveis de ambiente no .env):
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, ECR_REGISTRY

Para desenvolvimento local sem AWS, defina DEPLOY_DRY_RUN=true — o worker
simula o deploy e gera uma URL fictícia.
"""

import asyncio
import json
import os
import subprocess

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Application, Deployment


def run_deploy(app_id: int, deployment_id: int) -> None:
    """Ponto de entrada da tarefa RQ."""
    asyncio.run(_async_deploy(app_id, deployment_id))


async def _async_deploy(app_id: int, deployment_id: int) -> None:
    async with AsyncSessionLocal() as db:
        dep_result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = dep_result.scalar_one_or_none()
        app_result = await db.execute(select(Application).where(Application.id == app_id))
        app_obj = app_result.scalar_one_or_none()

        if deployment is None or app_obj is None:
            return

        deployment.status = "deploying"
        app_obj.status = "deploying"
        await db.commit()

        log = ""
        endpoint_url: str | None = None
        success = False

        dry_run = os.getenv("DEPLOY_DRY_RUN", "false").lower() == "true"

        try:
            if dry_run:
                log, endpoint_url = _dry_run_deploy(app_id)
                success = True
            else:
                log, endpoint_url = _aws_deploy(app_id, deployment.image_tag)
                success = True
        except Exception as exc:
            log += f"\n[ERRO] {exc}"

        deployment.status = "deployed" if success else "deploy_failed"
        deployment.deploy_log = log
        deployment.endpoint_url = endpoint_url
        app_obj.status = "deployed" if success else "deploy_failed"
        await db.commit()


def _dry_run_deploy(app_id: int) -> tuple[str, str]:
    """Simula um deploy para desenvolvimento local sem AWS."""
    log = (
        "[DRY RUN] Simulando push da imagem para ECR...\n"
        "[DRY RUN] Simulando terraform apply...\n"
        "[DRY RUN] Deploy concluído com sucesso.\n"
    )
    endpoint_url = f"http://app-{app_id}.foolguard.local"
    return log, endpoint_url


def _aws_deploy(app_id: int, image_tag: str) -> tuple[str, str]:
    """Executa o deploy real na AWS via ECR + Terraform."""
    log = ""
    registry = os.environ["ECR_REGISTRY"]
    region = getattr(settings, "aws_region", os.getenv("AWS_REGION", "us-east-1"))
    ecr_image = f"{registry}/foolguard-app-{app_id}:latest"

    # 1. Autenticar no ECR
    login_cmd = subprocess.run(
        ["aws", "ecr", "get-login-password", "--region", region],
        capture_output=True, text=True, check=True, timeout=30,
    )
    subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        input=login_cmd.stdout, capture_output=True, text=True, check=True, timeout=30,
    )
    log += "[OK] Login ECR\n"

    # 2. Tag e push da imagem
    subprocess.run(["docker", "tag", image_tag, ecr_image], check=True, timeout=30)
    push = subprocess.run(
        ["docker", "push", ecr_image], capture_output=True, text=True, check=True, timeout=300,
    )
    log += push.stdout + push.stderr + "\n[OK] Push ECR\n"

    # 3. Terraform apply
    infra_dir = os.path.join(os.path.dirname(__file__), "..", "infra")
    tf_vars = f"app_id={app_id},image_uri={ecr_image},region={region}"

    subprocess.run(
        ["terraform", "init", "-input=false"],
        cwd=infra_dir, check=True, timeout=120,
    )
    apply = subprocess.run(
        ["terraform", "apply", "-auto-approve", f"-var={tf_vars}"],
        cwd=infra_dir, capture_output=True, text=True, check=True, timeout=600,
    )
    log += apply.stdout + apply.stderr + "\n[OK] Terraform apply\n"

    # 4. Captura o endpoint do output
    output = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=infra_dir, capture_output=True, text=True, check=True, timeout=30,
    )
    tf_output = json.loads(output.stdout)
    endpoint_url = tf_output.get("app_url", {}).get("value")

    return log, endpoint_url
