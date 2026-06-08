"""Rotas de deploy (Mês 4).

Permite disparar um deploy de uma aplicação que passou no scan de segurança,
e consultar o histórico de deployments com o endpoint gerado.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.models import Application, Deployment, User
from app.schemas.schemas import DeploymentRead, DeployTriggered

router = APIRouter(prefix="/api/applications", tags=["deployments"])

_redis = Redis.from_url(settings.redis_url)
_deploy_queue = Queue("builds", connection=_redis)

# Status que permitem iniciar um deploy
_DEPLOYABLE_STATUSES = {"scan_passed", "build_success", "deploy_failed", "deployed"}


@router.post("/{app_id}/deployments", response_model=DeployTriggered, status_code=status.HTTP_202_ACCEPTED)
async def trigger_deploy(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeployTriggered:
    """Enfileira um deploy para uma aplicação que passou nos scans de segurança."""
    result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.owner_id == current_user.id,
        )
    )
    app_obj = result.scalar_one_or_none()
    if app_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada")

    if app_obj.status not in _DEPLOYABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Deploy não disponível neste status: {app_obj.status}. "
                   "A aplicação precisa ter passado no scan de segurança.",
        )

    image_tag = f"foolguard/app-{app_id}:latest"
    deployment = Deployment(
        application_id=app_id,
        image_tag=image_tag,
        status="queued",
    )
    db.add(deployment)
    app_obj.status = "queued"
    await db.commit()
    await db.refresh(deployment)

    from workers.deploy import run_deploy
    _deploy_queue.enqueue(run_deploy, app_id, deployment.id)

    return DeployTriggered(
        message="Deploy enfileirado com sucesso",
        deployment_id=deployment.id,
        application_id=app_id,
        status="queued",
    )


@router.get("/{app_id}/deployments", response_model=list[DeploymentRead])
async def list_deployments(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Deployment]:
    """Histórico de deployments de uma aplicação."""
    result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.owner_id == current_user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada")

    deps = await db.execute(
        select(Deployment)
        .where(Deployment.application_id == app_id)
        .order_by(Deployment.created_at.desc())
    )
    return list(deps.scalars().all())


@router.get("/{app_id}/deployments/{dep_id}", response_model=DeploymentRead)
async def get_deployment(
    app_id: int,
    dep_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Deployment:
    result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.owner_id == current_user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada")

    dep_result = await db.execute(
        select(Deployment).where(
            Deployment.id == dep_id,
            Deployment.application_id == app_id,
        )
    )
    deployment = dep_result.scalar_one_or_none()
    if deployment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment não encontrado")
    return deployment
