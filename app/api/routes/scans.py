"""Rotas de resultados de segurança (Mês 3).

Retorna os resultados dos scanners (Semgrep, Gitleaks, Trivy) para cada
aplicação. A leitura desses dados é o que alimenta a seção "Segurança"
do painel web.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import Application, ScanResult, User
from app.schemas.schemas import ScanResultRead, ScanSummary

router = APIRouter(prefix="/api/applications", tags=["scans"])


@router.get("/{app_id}/scans", response_model=ScanSummary)
async def get_scan_results(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScanSummary:
    """Retorna o sumário de segurança mais recente da aplicação."""
    app_result = await db.execute(
        select(Application).where(
            Application.id == app_id,
            Application.owner_id == current_user.id,
        )
    )
    if app_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada")

    scans_result = await db.execute(
        select(ScanResult)
        .where(ScanResult.application_id == app_id)
        .order_by(ScanResult.created_at.desc())
    )
    scans = list(scans_result.scalars().all())

    return ScanSummary(
        application_id=app_id,
        all_passed=all(s.passed for s in scans) if scans else True,
        results=scans,
    )
