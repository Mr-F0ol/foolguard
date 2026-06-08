"""Security Scanner Worker — Mês 3.

Roda três ferramentas open-source de segurança em sequência:
  1. Semgrep  — SAST (análise estática do código-fonte)
  2. Gitleaks — secret scanning (senhas/chaves no código)
  3. Trivy    — scan da imagem Docker (vulnerabilidades em deps e OS)

Cada ferramenta gera um ScanResult no banco. Se qualquer ferramenta
encontrar findings críticos, o status da app vai para "scan_failed".

As ferramentas precisam estar instaladas no container do worker.
O Dockerfile instala todas via apt/pip durante o build.
"""

import asyncio
import json
import subprocess
import tempfile

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.models import Application, ScanResult


def run_security_scan(app_id: int, image_tag: str | None = None) -> None:
    """Ponto de entrada da tarefa RQ."""
    asyncio.run(_async_scan(app_id, image_tag))


async def _async_scan(app_id: int, image_tag: str | None) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Application).where(Application.id == app_id))
        app_obj = result.scalar_one_or_none()
        if app_obj is None:
            return

        app_obj.status = "scanning"
        await db.commit()

        all_passed = True

        with tempfile.TemporaryDirectory() as tmpdir:
            # Clone repo para os scanners de código-fonte
            clone = subprocess.run(
                ["git", "clone", "--depth", "1", app_obj.repo_url, tmpdir],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if clone.returncode == 0:
                semgrep_result = await _run_semgrep(db, app_id, tmpdir)
                gitleaks_result = await _run_gitleaks(db, app_id, tmpdir)
                if not semgrep_result or not gitleaks_result:
                    all_passed = False
            else:
                all_passed = False
                _save_error_result(db, app_id, "clone", clone.stderr)

            if image_tag:
                trivy_result = await _run_trivy(db, app_id, image_tag)
                if not trivy_result:
                    all_passed = False

        app_obj.status = "scan_passed" if all_passed else "scan_failed"
        await db.commit()


async def _run_semgrep(db, app_id: int, source_dir: str) -> bool:
    """Roda Semgrep no código-fonte e salva o resultado."""
    try:
        proc = subprocess.run(
            ["semgrep", "--config", "auto", source_dir, "--json", "--quiet"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        data = _safe_parse_json(proc.stdout)
        results = data.get("results", [])
        # Considera falha se houver findings de severidade ERROR ou WARNING
        critical = [r for r in results if r.get("extra", {}).get("severity") in ("ERROR", "WARNING")]
        passed = len(critical) == 0
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        data = {"error": str(exc)}
        results = []
        passed = False

    scan = ScanResult(
        application_id=app_id,
        tool="semgrep",
        raw_output=json.dumps(data),
        findings_count=len(results),
        passed=passed,
    )
    db.add(scan)
    await db.flush()
    return passed


async def _run_gitleaks(db, app_id: int, source_dir: str) -> bool:
    """Roda Gitleaks para detectar segredos vazados no repositório."""
    try:
        proc = subprocess.run(
            [
                "gitleaks",
                "detect",
                "--source", source_dir,
                "--report-format", "json",
                "--report-path", "/dev/stdout",
                "--no-git",
                "--exit-code", "0",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        data = _safe_parse_json(proc.stdout)
        findings = data if isinstance(data, list) else []
        passed = len(findings) == 0
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        data = {"error": str(exc)}
        findings = []
        passed = False

    scan = ScanResult(
        application_id=app_id,
        tool="gitleaks",
        raw_output=json.dumps(data),
        findings_count=len(findings),
        passed=passed,
    )
    db.add(scan)
    await db.flush()
    return passed


async def _run_trivy(db, app_id: int, image_tag: str) -> bool:
    """Roda Trivy para detectar vulnerabilidades na imagem Docker."""
    try:
        proc = subprocess.run(
            [
                "trivy", "image",
                "--format", "json",
                "--exit-code", "0",
                "--severity", "HIGH,CRITICAL",
                image_tag,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        data = _safe_parse_json(proc.stdout)
        # Conta findings de severidade HIGH e CRITICAL
        vuln_count = sum(
            len(r.get("Vulnerabilities") or [])
            for r in data.get("Results", [])
        )
        passed = vuln_count == 0
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        data = {"error": str(exc)}
        vuln_count = 0
        passed = False

    scan = ScanResult(
        application_id=app_id,
        tool="trivy",
        raw_output=json.dumps(data),
        findings_count=vuln_count,
        passed=passed,
    )
    db.add(scan)
    await db.flush()
    return passed


def _save_error_result(db, app_id: int, tool: str, error: str) -> None:
    scan = ScanResult(
        application_id=app_id,
        tool=tool,
        raw_output=json.dumps({"error": error}),
        findings_count=0,
        passed=False,
    )
    db.add(scan)


def _safe_parse_json(text: str) -> dict | list:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
