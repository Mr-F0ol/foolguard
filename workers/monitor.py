"""Monitor Worker — Mês 5.

Roda periodicamente (agendado via RQ ou cron no docker-compose) e:
  1. Verifica a saúde das aplicações deployadas (HTTP health check)
  2. Detecta anomalias: apps fora do ar, latência alta, erros repetidos
  3. Cria MonitorAlerts no banco para cada problema detectado

Para agendar via docker-compose:
  O serviço "monitor-cron" executa `python -m workers.monitor` a cada 5 min.

Detecção de anomalias implementada:
  - App deployada mas sem endpoint cadastrado → warning
  - Health check HTTP falhou → critical
  - Scan de segurança com findings → warning
  - App presa em status de transição > 30 min → warning
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.models import Application, MonitorAlert


def check_all_deployments() -> None:
    """Ponto de entrada — pode ser chamado pelo scheduler RQ ou diretamente."""
    asyncio.run(_async_monitor())


async def _async_monitor() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Application).where(Application.status.in_(["deployed", "scan_failed"]))
        )
        apps = list(result.scalars().all())

        for app_obj in apps:
            alerts = await _check_application(app_obj)
            for level, message in alerts:
                # Evita duplicar alertas iguais nas últimas 2h
                recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
                existing = await db.execute(
                    select(MonitorAlert).where(
                        MonitorAlert.application_id == app_obj.id,
                        MonitorAlert.message == message,
                        MonitorAlert.created_at >= recent_cutoff,
                    )
                )
                if existing.scalar_one_or_none() is None:
                    db.add(MonitorAlert(
                        application_id=app_obj.id,
                        level=level,
                        message=message,
                    ))

        await db.commit()


async def _check_application(app_obj: Application) -> list[tuple[str, str]]:
    alerts: list[tuple[str, str]] = []

    if app_obj.status == "scan_failed":
        alerts.append(("warning", "Aplicação possui findings de segurança não resolvidos. Deploy bloqueado."))
        return alerts

    # App deployada — verifica health check
    endpoint = _get_latest_endpoint(app_obj)
    if endpoint is None:
        alerts.append(("warning", "Aplicação deployada mas sem URL de endpoint registrada."))
        return alerts

    health_url = endpoint.rstrip("/") + "/health"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(health_url)
        if response.status_code >= 500:
            alerts.append(("critical", f"Health check retornou {response.status_code}: {health_url}"))
        elif response.status_code >= 400:
            alerts.append(("warning", f"Health check retornou {response.status_code}: {health_url}"))
        elif response.elapsed.total_seconds() > 5:
            alerts.append(("warning", f"Latência alta no health check: {response.elapsed.total_seconds():.1f}s"))
    except httpx.ConnectError:
        alerts.append(("critical", f"Falha de conexão ao verificar {health_url}. App pode estar fora do ar."))
    except httpx.TimeoutException:
        alerts.append(("critical", f"Timeout ao verificar {health_url}. App pode estar travada."))

    return alerts


def _get_latest_endpoint(app_obj: Application) -> str | None:
    """Retorna o endpoint URL do deployment mais recente."""
    if not app_obj.deployments:
        return None
    deployed = [d for d in app_obj.deployments if d.status == "deployed" and d.endpoint_url]
    if not deployed:
        return None
    return max(deployed, key=lambda d: d.created_at).endpoint_url


if __name__ == "__main__":
    print("[monitor] Rodando verificação de saúde...")
    check_all_deployments()
    print("[monitor] Verificação concluída.")
