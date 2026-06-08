"""Rotas do Monitor Service (Mês 5).

Expõe alertas gerados pelo worker de monitoramento e permite que o usuário
reconheça (acknowledge) os alertas para limpar o painel.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import Application, MonitorAlert, User
from app.schemas.schemas import AcknowledgeRequest, MonitorAlertRead

router = APIRouter(prefix="/api/applications", tags=["monitor"])


@router.get("/{app_id}/alerts", response_model=list[MonitorAlertRead])
async def list_alerts(
    app_id: int,
    only_active: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MonitorAlert]:
    """Lista alertas de monitoramento de uma aplicação.

    Por padrão retorna apenas alertas não reconhecidos (only_active=true).
    Passe only_active=false para ver o histórico completo.
    """
    app_result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.owner_id == current_user.id,
        )
    )
    if app_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada")

    query = select(MonitorAlert).where(MonitorAlert.application_id == app_id)
    if only_active:
        query = query.where(MonitorAlert.acknowledged == False)  # noqa: E712
    query = query.order_by(MonitorAlert.created_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


@router.patch("/{app_id}/alerts/{alert_id}", response_model=MonitorAlertRead)
async def acknowledge_alert(
    app_id: int,
    alert_id: int,
    payload: AcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MonitorAlert:
    """Reconhece (ou desreconhece) um alerta."""
    app_result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.owner_id == current_user.id,
        )
    )
    if app_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada")

    alert_result = await db.execute(
        select(MonitorAlert).where(
            MonitorAlert.id == alert_id,
            MonitorAlert.application_id == app_id,
        )
    )
    alert = alert_result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta não encontrado")

    alert.acknowledged = payload.acknowledged
    await db.commit()
    await db.refresh(alert)
    return alert


@router.get("/alerts/summary", response_model=dict[str, int], tags=["monitor"])
async def alerts_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Contagem de alertas ativos por nível para todas as apps do usuário.

    Útil para o widget de resumo no topo do dashboard.
    """
    result = await db.execute(
        select(Application.id).where(Application.owner_id == current_user.id)
    )
    app_ids = [row[0] for row in result.all()]

    if not app_ids:
        return {"info": 0, "warning": 0, "critical": 0}

    alerts_result = await db.execute(
        select(MonitorAlert).where(
            MonitorAlert.application_id.in_(app_ids),
            MonitorAlert.acknowledged == False,  # noqa: E712
        )
    )
    alerts = list(alerts_result.scalars().all())

    return {
        "info": sum(1 for a in alerts if a.level == "info"),
        "warning": sum(1 for a in alerts if a.level == "warning"),
        "critical": sum(1 for a in alerts if a.level == "critical"),
    }
