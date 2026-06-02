"""Q.68.B — integration test do modo ``--mode freshness`` do
``scripts/check_etl_runs.py``.

O script lê ``core.etl_run`` para responder "os mirrors ERP ainda
correm?". O caminho feliz é fácil de verificar com fakes; o caminho que
realmente importa em produção (ler a tabela, formatar JSON, decidir
exit code com base em idade) só se demonstra contra uma DB Postgres
viva.

Por isso o teste é marcado ``@pytest.mark.integration`` e faz skip
quando a DB de dev não responde — coerente com a convenção em
``pytest.ini`` (marker registado, sem auto-skip).
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_etl_runs.py"
_DEV_TENANT = UUID("00000000-0000-0000-0000-000000000001")


_MIRRORS_UNDER_TEST = (
    "master",
    "molds",
    "skills",
    "quality",
    "time_mining",
    "stock",
)


async def _db_available() -> bool:
    """Probe rápido — devolve False se o Postgres não responde."""
    try:
        from src.shared.database import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_freshness_reports_six_mirrors_json() -> None:
    """Insere 6 linhas ``core.etl_run`` (uma por mirror, 12h atrás) e
    verifica que ``--mode freshness --stale-hours 48 --json``:

    * sai com exit code 0 (todos dentro de 48h);
    * emite JSON com os 6 mirrors no campo ``mirrors``;
    * cada mirror tem ``last_status == 'ok'`` e ``idade_horas`` ~12h.

    Cleanup é feito num ``finally`` — não deixa lixo entre execuções.
    """
    if not await _db_available():
        pytest.skip("Postgres dev não disponível — integration test skipped.")

    from src.core.models.etl_run import EtlRun
    from src.shared.database import async_session_factory

    now = datetime.now(timezone.utc)
    twelve_h_ago = now - timedelta(hours=12)
    finished = twelve_h_ago + timedelta(seconds=30)
    test_marker = f"q68b_test_{uuid4().hex[:8]}"
    inserted_ids: list[UUID] = []

    try:
        # ── ARRANGE: seed 6 audit rows, todas 12h atrás, status='ok' ──
        async with async_session_factory() as session:
            for mirror in _MIRRORS_UNDER_TEST:
                row = EtlRun(
                    tenant_id=_DEV_TENANT,
                    source=mirror,
                    status="ok",
                    started_at=twelve_h_ago,
                    finished_at=finished,
                    rows_read=10,
                    rows_inserted=5,
                    rows_updated=2,
                    rows_skipped=3,
                    error=test_marker,  # tag p/ cleanup determinístico
                )
                session.add(row)
            await session.flush()
            for obj in session.new:
                if isinstance(obj, EtlRun):
                    inserted_ids.append(obj.id)
            await session.commit()

        # ── ACT: corre o script via subprocess (sync; via to_thread) ──
        env_pythonpath = str(_REPO_ROOT)
        proc = await asyncio.to_thread(
            subprocess.run,
            [
                sys.executable,
                str(_SCRIPT),
                "--mode", "freshness",
                "--stale-hours", "48",
                "--json",
                # factory_raw vive na BD partilhada e pode estar legitimamente
                # stale (full-copy nocturno) — exclui-o para o teste de
                # core.etl_run ser determinístico (Q.157.0).
                "--no-factory-raw",
            ],
            cwd=str(_REPO_ROOT),
            env={"PYTHONPATH": env_pythonpath, **_clean_env()},
            capture_output=True,
            text=True,
            timeout=60,
        )

        # ── ASSERT: exit code + JSON estrutura ────────────────────────
        assert proc.returncode == 0, (
            f"script returncode={proc.returncode}\n"
            f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
        )

        report = json.loads(proc.stdout)
        assert report["stale_hours_threshold"] == 48.0
        assert report["stale_mirrors"] == [], (
            "Esperava zero stale com threshold=48h (rows 12h atrás), "
            f"obtive: {report['stale_mirrors']}"
        )

        sources_present = {m["source"] for m in report["mirrors"]}
        for expected in _MIRRORS_UNDER_TEST:
            assert expected in sources_present, (
                f"mirror {expected!r} ausente do report. "
                f"Presentes: {sorted(sources_present)}"
            )

        # Os 6 que inserimos devem aparecer com status='ok' e idade ~12h
        by_source = {m["source"]: m for m in report["mirrors"]}
        for mirror in _MIRRORS_UNDER_TEST:
            entry = by_source[mirror]
            assert entry["last_status"] == "ok", (
                f"{mirror}: last_status={entry['last_status']!r}, esperava 'ok'"
            )
            assert entry["idade_horas"] is not None
            # Numa BD a sincronizar (sync saudável), o mirror real pode ter
            # uma linha MAIS recente que o seed de 12h — o `DISTINCT ON (source)
            # ORDER BY started_at DESC` escolhe a mais recente. Por isso só
            # exigimos idade sã e não-stale (<48h), não exactamente ~12h.
            assert 0.0 <= entry["idade_horas"] <= 14.0, (
                f"{mirror}: idade_horas={entry['idade_horas']}, esperava <14h"
            )

    finally:
        # ── CLEANUP: apaga as linhas marcadas com test_marker ─────────
        async with async_session_factory() as session:
            await session.execute(
                text("DELETE FROM core.etl_run WHERE error = :marker"),
                {"marker": test_marker},
            )
            await session.commit()


def _clean_env() -> dict[str, str]:
    """Env mínimo para o subprocess herdar PATH/SystemRoot no Windows
    sem trazer variáveis estranhas. PYTHONPATH é passado em separado.
    """
    import os

    keep = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "USERPROFILE", "TEMP",
            "TMP", "WINDIR", "LOCALAPPDATA", "APPDATA", "COMSPEC",
            "DATABASE_URL")
    return {k: os.environ[k] for k in keep if k in os.environ}
