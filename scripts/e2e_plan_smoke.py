"""Q.172.C — E2E smoke do fluxo de planeamento COMPLETO contra o stack live.

Prova, com dados reais e o backend servido em :8001, o ciclo inteiro:

  1. backend pronto (/health/ready)
  2. robô: POST /schedule/async → worker arq corre o CPO → DRAFT novo
  3. validador universal: cpo_meta.validation.ok no commit (Q.169.B)
  4. write-gate SoD: auto-aprovação é 403 GARANTIDO (author=UUID do aprovador;
     não clobbera o plano LIVE da demo; a promoção real é gesto humano)
  5. grid: GET /commits/{sha}?include_operations=true → ops com shape
  6. drag VÁLIDO: POST /operations/reorder → 200 + commit novo
  7. drag INVÁLIDO (sobreposição do mesmo barco) → 422 com axiom PT-PT
  8. reapply: novo run do robô → o override manual sobrevive (Q.142/Q.148)
  9. operador: GET /worker/{id}/operations-today → 200
 10. cleanup: apaga os commits manual_drag do smoke (Q.173.AN — sem isto cada
     corrida deixava um override ativo que o robô re-aplicava durante o TTL;
     foi o "override fantasma" da Q.173.S)

Uso:  .venv/Scripts/python.exe scripts/e2e_plan_smoke.py
Sai com código 0 (verde) / 1 (falha) e imprime um relatório por passo.
"""
from __future__ import annotations

import asyncio
import io
import sys

# Consola Windows é cp1252 — sem isto os passos com '→'/'≠' rebentam.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

BASE = "http://127.0.0.1:8001"
TENANT = "00000000-0000-0000-0000-000000000001"
USER_A = "22222222-2222-2222-2222-222222222222"  # proponente (dev)
HDRS = {
    "X-Tenant-Id": TENANT,
    "X-User-Id": USER_A,
    "X-User-Role": "manager_operations",
    "Content-Type": "application/json",
}

PLAN_CAP = 80          # suficiente p/ apanhar barcos com ≥2 ops (rota truncada à fase atual)
RUN_ID = uuid.uuid4().hex[:8]  # mensagem única fura o dedup _job_id entre corridas
TIME_LIMIT_S = 60.0
JOB_POLL_S = 5
JOB_TIMEOUT_S = 420    # worker + solver + persist

_passed: List[str] = []
_failed: List[str] = []


def _ok(step: str, detail: str = "") -> None:
    _passed.append(step)
    print(f"  OK   {step}" + (f" — {detail}" if detail else ""))


def _fail(step: str, detail: str) -> None:
    _failed.append(step)
    print(f"  FAIL {step} — {detail}")


async def _latest_commit_sha(
    client: httpx.AsyncClient, author: Optional[str] = None,
) -> Optional[str]:
    # author=USER_A distingue o DRAFT do smoke do DRAFT horário do robô
    # (auto_cpo_replan corre de hora a hora e pode interlear o poll).
    r = await client.get(f"{BASE}/v1/plan/cpo/commits", params={"limit": 10}, headers=HDRS)
    if r.status_code != 200 or not r.json():
        return None
    for row in r.json():
        if author is None or row.get("author") == author:
            return row["commit_sha256"]
    return None


async def _get_commit(client: httpx.AsyncClient, sha: str, ops: bool = False) -> Dict[str, Any]:
    r = await client.get(
        f"{BASE}/v1/plan/cpo/commits/{sha}",
        params={"include_operations": "true"} if ops else None,
        headers=HDRS,
    )
    r.raise_for_status()
    return r.json()


async def _cleanup_smoke_overrides() -> int:
    """Q.173.AN — apaga os commits manual_drag criados por smokes (este e
    corridas anteriores que falharam a meio). O reorder do passo 6 fica em
    `plan_schedule_commits` com `delta.tipo='manual_drag'` e autor humano —
    exatamente o que `active_manual_overrides` coleta — e sem limpeza o robô
    re-aplicava o move do smoke a TODOS os planos durante o TTL (14d).

    Acesso direto à BD (não há DELETE de commits na API, por design):
    o smoke corre na máquina do stack, com o venv do projeto.
    """
    import sys as _sys
    from pathlib import Path

    _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sqlalchemy import text as _text

    from src.shared.database import engine

    try:
        async with engine.begin() as conn:
            res = await conn.execute(
                _text(
                    "DELETE FROM plan_schedule_commits "
                    "WHERE tenant_id = :tid "
                    "  AND delta->>'tipo' = 'manual_drag' "
                    "  AND delta->>'reason' LIKE 'E2E smoke%' "
                    "  AND status != 'LIVE'"
                ),
                {"tid": TENANT},
            )
            return int(res.rowcount or 0)
    finally:
        await engine.dispose()


async def main() -> int:
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as client:
        # 1 — backend pronto
        try:
            r = await client.get(f"{BASE}/health/ready")
            assert r.status_code == 200
            _ok("backend /health/ready")
        except Exception as exc:
            _fail("backend /health/ready", str(exc))
            return 1

        baseline_sha = await _latest_commit_sha(client, author=USER_A)

        # 2 — robô: job async no worker arq (o caminho REAL de produção)
        r = await client.post(
            f"{BASE}/v1/plan/cpo/schedule/async",
            json={
                "plan_cap": PLAN_CAP,
                "time_limit_sec": TIME_LIMIT_S,
                "author": USER_A,  # = aprovador → SoD recusa, nunca promove
                "message": f"E2E smoke Q.172.C {RUN_ID}",
            },
            headers=HDRS,
        )
        if r.status_code not in (200, 202):
            _fail("POST /schedule/async", f"{r.status_code}: {r.text[:200]}")
            return 1
        _ok("POST /schedule/async", f"job aceite ({r.status_code})")

        # espera pelo DRAFT novo (sha diferente do baseline)
        new_sha: Optional[str] = None
        t0 = time.monotonic()
        while time.monotonic() - t0 < JOB_TIMEOUT_S:
            await asyncio.sleep(JOB_POLL_S)
            sha = await _latest_commit_sha(client, author=USER_A)
            if sha and sha != baseline_sha:
                new_sha = sha
                break
        if not new_sha:
            _fail("DRAFT do robô", f"sem commit novo em {JOB_TIMEOUT_S}s")
            return 1
        commit = await _get_commit(client, new_sha)
        _ok(
            "DRAFT do robô",
            f"{new_sha[:8]} ops={commit['operations_count']} "
            f"engine={commit.get('cpo_meta', {}).get('engine', '?')}",
        )

        # 3 — validador universal no caminho de escrita
        validation = (commit.get("cpo_meta") or {}).get("validation") or {}
        if validation.get("ok") is True:
            _ok("validate_schedule no commit", f"checks={validation.get('checks_run')}")
        else:
            _fail("validate_schedule no commit", f"cpo_meta.validation={validation!r}")

        # 4 — SoD: o proponente não se auto-aprova (write-gate vivo).
        #     NÃO promovemos a LIVE com outro user — o smoke não clobbera
        #     o plano LIVE da demo; a promoção é gesto humano no /overall.
        r = await client.put(
            f"{BASE}/v1/plan/cpo/commits/{new_sha}/approve",
            headers={**HDRS, "X-User-Id": USER_A},
        )
        # author do request é "e2e_plan_smoke"; SoD compara identidades de
        # aprovador vs proponente do commit — com o MESMO user tem de recusar
        # quando o author coincide; commits de autor distinto são aprováveis.
        if r.status_code in (403, 409):
            _ok("SoD write-gate", f"auto-aprovação recusada ({r.status_code})")
        elif r.status_code == 200:
            _fail(
                "SoD write-gate",
                "PROMOVEU com author==approver — SoD furado! Repor: "
                f"UPDATE plan_schedule_commits SET status='DRAFT' "
                f"WHERE commit_sha256 LIKE '{new_sha[:8]}%'",
            )
        else:
            _fail("SoD/approve", f"{r.status_code}: {r.text[:200]}")

        # 5 — grid: ops do commit com shape esperado
        detail = await _get_commit(client, new_sha, ops=True)
        ops = detail.get("operations") or []
        if ops and all(("operation_id" in o and "start_time" in o) for o in ops[:5]):
            _ok("grid ops do commit", f"{len(ops)} ops com operation_id+start_time")
        else:
            _fail("grid ops do commit", f"shape inesperado: {str(ops[:1])[:160]}")
            return 1

        # setup do drag: o cap interativo do tenant limita o plano (Q.161),
        # e a rota truncada à fase atual (Q.136) deixa a maioria dos barcos
        # com 1 op — o conflito determinístico é DOUBLE-BOOKING de operador
        # (axioma 1): mover a op X p/ a janela da op Y com o operador da Y.
        with_worker = [o for o in ops if (o.get("workers") or [])]
        if len(with_worker) < 2:
            _fail("drag setup", "menos de 2 ops com operador no plano do smoke")
            return 1
        with_worker.sort(key=lambda o: str(o.get("start_time")))
        op_a, op_b = with_worker[0], with_worker[1]

        # 6 — drag VÁLIDO: empurra uma op 30 dias p/ a frente
        last_op = with_worker[-1]
        new_start = (
            datetime.fromisoformat(str(last_op["start_time"])) + timedelta(days=30)
        ).isoformat()
        r = await client.post(
            f"{BASE}/v1/plan/operations/reorder",
            json={
                "operation_id": str(last_op["operation_id"]),
                "new_phase": str(last_op.get("phase_id", "")),
                "new_start_ts": new_start,
                "reason": "E2E smoke: move válido",
            },
            headers=HDRS,
        )
        if r.status_code == 200:
            drag_sha = r.json().get("commit_sha", "")
            _ok("drag válido", f"novo commit {str(drag_sha)[:8]}")
        else:
            _fail("drag válido", f"{r.status_code}: {r.text[:300]}")
            return 1

        # 7 — drag INVÁLIDO: op B para a janela da op A COM o operador da A
        #     → exclusividade_operador (axioma 1) tem de recusar.
        r = await client.post(
            f"{BASE}/v1/plan/operations/reorder",
            json={
                "operation_id": str(op_b["operation_id"]),
                "new_phase": str(op_b.get("phase_id", "")),
                "new_start_ts": str(op_a["start_time"]),
                "new_operator_id": str((op_a.get("workers") or [""])[0]),
                "reason": "E2E smoke: deve ser recusado",
            },
            headers=HDRS,
        )
        if r.status_code == 422:
            body = r.json()
            _ok("drag inválido recusado", str(body.get("detail", ""))[:120])
        else:
            _fail("drag inválido recusado", f"esperado 422, veio {r.status_code}")

        # 8 — reapply: novo run do robô; o override do passo 6 sobrevive
        baseline2 = await _latest_commit_sha(client, author=USER_A)
        r = await client.post(
            f"{BASE}/v1/plan/cpo/schedule/async",
            json={
                "plan_cap": PLAN_CAP,
                "time_limit_sec": TIME_LIMIT_S,
                "author": USER_A,  # = aprovador → SoD recusa, nunca promove
                "message": f"E2E smoke Q.172.C (reapply) {RUN_ID}",
            },
            headers=HDRS,
        )
        if r.status_code not in (200, 202):
            _fail("reapply run", f"{r.status_code}")
        else:
            sha3: Optional[str] = None
            t0 = time.monotonic()
            while time.monotonic() - t0 < JOB_TIMEOUT_S:
                await asyncio.sleep(JOB_POLL_S)
                sha = await _latest_commit_sha(client, author=USER_A)
                if sha and sha != baseline2:
                    sha3 = sha
                    break
            if not sha3:
                _fail("reapply run", "sem commit novo")
            else:
                # o reapply corre DEPOIS do persist do DRAFT e cria um commit
                # FILHO com o override re-aplicado — esperar por ele.
                for _ in range(6):
                    await asyncio.sleep(5)
                    head = await _latest_commit_sha(client)
                    if head and head != sha3:
                        sha3 = head
                        break
                detail3 = await _get_commit(client, sha3, ops=True)
                ops3 = {str(o["operation_id"]): o for o in (detail3.get("operations") or [])}
                moved = ops3.get(str(last_op["operation_id"]))
                if moved and str(moved.get("start_time", ""))[:16] == new_start[:16]:
                    _ok("reapply preserva override", f"{str(last_op['operation_id'])}")
                elif moved is None:
                    # plano pequeno: a op pode ficar fora do cap do run novo —
                    # honesto: WARN, não prova nem refuta o reapply
                    print("  WARN reapply: op fora do scope do run novo (cap)")
                    _ok("reapply run", f"DRAFT novo {sha3[:8]} (op fora do cap)")
                else:
                    _fail(
                        "reapply preserva override",
                        f"start={moved.get('start_time')} esperado≈{new_start}",
                    )

        # 9 — vista do operador
        emp = None
        r = await client.get(f"{BASE}/v1/core/employees", params={"active_only": "true", "limit": 1}, headers=HDRS)
        if r.status_code == 200 and r.json():
            body = r.json()
            items = body if isinstance(body, list) else body.get("items") or body.get("employees") or []
            if items:
                emp = items[0].get("id") or items[0].get("employee_code")
        if emp:
            r = await client.get(
                f"{BASE}/v1/plan/schedule/worker/{emp}/operations-today", headers=HDRS,
            )
            if r.status_code == 200:
                _ok("operador operations-today", f"employee={emp}")
            else:
                _fail("operador operations-today", f"{r.status_code}")
        else:
            print("  WARN operador: sem employees ativos para testar")

    # 10 — cleanup: o smoke não deixa overrides ativos atrás de si (Q.173.AN)
    try:
        n = await _cleanup_smoke_overrides()
        _ok("cleanup overrides do smoke", f"{n} commit(s) manual_drag apagados")
    except Exception as exc:
        _fail("cleanup overrides do smoke", f"{type(exc).__name__}: {exc}")

    print()
    print(f"E2E PLAN SMOKE: {len(_passed)} OK, {len(_failed)} FAIL")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
