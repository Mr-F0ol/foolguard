"""Rotas de gestão de aplicações (CRUD básico).

Ponto de segurança central aqui: CONTROLE DE ACESSO. Toda rota exige um
usuário autenticado, e o usuário só pode ver/manipular as PRÓPRIAS
aplicações. Repare que cada consulta filtra por `owner_id == current_user.id`.

Falha de controle de acesso (deixar um usuário ver dados de outro) é a
vulnerabilidade nº 1 do OWASP Top 10. Acertar isso desde o início é
exatamente o tipo de detalhe que você vai destacar no threat model.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.models import Application, BuildLog, User
from app.schemas.schemas import ApplicationCreate, ApplicationRead, BuildLogRead, BuildTriggered

router = APIRouter(prefix="/api/applications", tags=["applications"])

# Conexão com Redis usada para enfileirar builds.
# A conexão é lazy — só falha se Redis estiver fora quando o endpoint for chamado.
_redis = Redis.from_url(settings.redis_url)
_build_queue = Queue("builds", connection=_redis)


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Application:
    app_obj = Application(
        name=payload.name,
        repo_url=payload.repo_url,
        owner_id=current_user.id,
    )
    db.add(app_obj)
    await db.commit()
    await db.refresh(app_obj)
    return app_obj


@router.get("", response_model=list[ApplicationRead])
async def list_applications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Application]:
    result = await db.execute(
        select(Application).where(Application.owner_id == current_user.id)
    )
    return list(result.scalars().all())


@router.get("/{app_id}", response_model=ApplicationRead)
async def get_application(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Application:
    result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.owner_id == current_user.id,
        )
    )
    app_obj = result.scalar_one_or_none()
    if app_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aplicação não encontrada",
        )
    return app_obj


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.owner_id == current_user.id,
        )
    )
    app_obj = result.scalar_one_or_none()
    if app_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aplicação não encontrada",
        )
    await db.delete(app_obj)
    await db.commit()


@router.post("/{app_id}/builds", response_model=BuildTriggered, status_code=status.HTTP_202_ACCEPTED)
async def trigger_build(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BuildTriggered:
    """Enfileira um build para a aplicação.

    Retorna 202 Accepted imediatamente — o build roda em background.
    Use GET /{app_id} para acompanhar o status.
    """
    result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.owner_id == current_user.id,
        )
    )
    app_obj = result.scalar_one_or_none()
    if app_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada")

    if app_obj.status in ("queued", "building"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Build já em andamento (status: {app_obj.status})",
        )

    app_obj.status = "queued"
    await db.commit()

    from workers.tasks import run_build
    _build_queue.enqueue(run_build, app_id)

    return BuildTriggered(
        message="Build enfileirado com sucesso",
        application_id=app_id,
        status="queued",
    )


@router.get("/{app_id}/builds", response_model=list[BuildLogRead])
async def list_build_logs(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BuildLog]:
    """Retorna o histórico de builds de uma aplicação."""
    result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.owner_id == current_user.id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada")

    logs_result = await db.execute(
        select(BuildLog)
        .where(BuildLog.application_id == app_id)
        .order_by(BuildLog.created_at.desc())
    )
    return list(logs_result.scalars().all())
