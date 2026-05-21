"""
Q.67.3.A — CPO greedy vs GA benchmark
======================================

Mede se o GA do ``CPOv4Engine`` traz ganho real sobre o pipeline greedy
puro. O greedy é o estado em que o engine converge no fim da geração 0
(baseline antes da exploração GA). Para o medir sem mexer no engine
(`src/plan/cpo/*` é read-only neste sprint) corremos duas configurações:

  - ``greedy_only``: ``population_size=1``, ``generations=0``,
    ``time_limit_sec=0``. O loop GA nunca itera; o resultado coincide
    com a baseline emitida em ``engine.py:204-237``.
  - ``ga_full``: configuração default (``population_size=100``,
    ``generations=200``, ``time_limit_sec=30``). É exactamente o caminho
    que produção usa.

Em ambos os casos lemos as 5 métricas usadas pela operação:

  - ``makespan_hours``
  - ``otd_delivery`` (1.0 - frac late, 1.0 = sem atrasos)
  - ``throughput_eur_day``
  - ``num_late_orders``
  - ``solve_time_sec`` (latência)

Fontes de cenário (por ordem de preferência):

  1. ``--ingestion-id <uuid>``: carrega ``FactoryState`` a partir do
     active ingestion + corre o ``RoutingResolver`` sobre orders reais.
  2. ``--from-erp``: tenta puxar ``FactoryState.load`` para o dev tenant
     padrão. Se o curated layer estiver vazio (caso normal em dev) cai
     para 3.
  3. ``--dry-run`` (default em CI): gera 10 cenários sintéticos com
     20-50 ops cada e horizon de 14 dias. Útil para validar o script
     sem DB.

A nota no relatório explica que números prod-realistas têm de vir do
caminho 1 ou 2, corridos por quem tenha o backend ligado.

Uso:
  .venv\\Scripts\\python.exe scripts/cpo_benchmark.py --dry-run
  .venv\\Scripts\\python.exe scripts/cpo_benchmark.py --from-erp
  .venv\\Scripts\\python.exe scripts/cpo_benchmark.py --ingestion-id <uuid>

Saída:
  - stdout: tabela markdown lado-a-lado por cenário + resumo
  - opcional ``--out <path>``: grava a tabela no fim do relatório
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

# Garante que ``src.*`` é resolúvel quando o script corre fora do venv.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.plan.cpo.engine import CPOConfig, CPOv4Engine
from src.plan.cpo.state import FactoryState
from src.plan.engines.scheduling_adapter import (
    SchedulingMachine,
    SchedulingOperation,
)

logger = logging.getLogger("cpo_benchmark")

DEV_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


# --------------------------------------------------------------------------- #
# Métricas extraídas do dict-result do engine                                  #
# --------------------------------------------------------------------------- #

METRICS = (
    "makespan_hours",
    "otd_delivery",
    "throughput_eur_day",
    "num_late_orders",
    "solve_time_sec",
)


@dataclass
class RunResult:
    label: str
    metrics: dict[str, float]
    raw: dict[str, Any]


# --------------------------------------------------------------------------- #
# Cenário sintético para --dry-run                                             #
# --------------------------------------------------------------------------- #


def _synthetic_scenario(
    scenario_idx: int,
    rng: random.Random,
) -> tuple[list[SchedulingOperation], list[SchedulingMachine], datetime, datetime]:
    """Gera ops/machines determinísticos baseados em ``scenario_idx``.

    Não inventa números de produção: as durações vivem entre 30 e 240
    min, as datas de entrega são uniformes no horizon, e nenhuma das
    métricas é tratada como representativa da NELO real. O propósito é
    SÓ exercitar o ``CPOv4Engine`` ponta-a-ponta.
    """
    n_orders = 5 + scenario_idx % 4  # 5..8 orders
    ops_per_order = 4
    horizon_start = datetime(2026, 5, 21, 8, 0, 0)
    horizon_end = horizon_start + timedelta(days=14)

    machines = [
        SchedulingMachine(machine_id=f"M{m}", name=f"Machine {m}")
        for m in range(4)
    ]

    ops: list[SchedulingOperation] = []
    for o in range(n_orders):
        due = horizon_start + timedelta(
            hours=rng.uniform(48, 14 * 24 - 8),
        )
        for s in range(ops_per_order):
            ops.append(
                SchedulingOperation(
                    operation_id=f"s{scenario_idx}_o{o}_op{s}",
                    order_id=f"s{scenario_idx}_O{o}",
                    product_id=f"P{o % 3}",
                    sequence=s + 1,
                    operation_code=f"PHASE{s}",
                    duration_minutes=rng.uniform(30, 240),
                    machine_id=f"M{rng.randrange(4)}",
                    due_date=due,
                    priority=1.0,
                ),
            )
    return ops, machines, horizon_start, horizon_end


def _synthetic_state() -> FactoryState:
    return FactoryState(tenant_id=DEV_TENANT_ID)


# --------------------------------------------------------------------------- #
# Real scenario loader (best-effort)                                           #
# --------------------------------------------------------------------------- #


async def _load_real_scenarios(
    ingestion_id: Optional[UUID],
    n_scenarios: int,
) -> list[tuple[
    FactoryState,
    list[SchedulingOperation],
    list[SchedulingMachine],
    datetime,
    datetime,
]]:
    """Carrega cenários do active ingestion.

    Levanta ``RuntimeError`` (em vez de devolver dados vazios) se o
    backend não puder fornecer ops — assim o caller decide se cai para
    cenários sintéticos OU se sinaliza falha.
    """
    try:
        from src.shared.db import get_async_session_factory
        from src.plan.services.routing_resolver import RoutingResolver
    except Exception as e:  # pragma: no cover — defensivo
        raise RuntimeError(f"backend imports unavailable: {e}") from e

    session_factory = get_async_session_factory()
    horizon_start = datetime.utcnow()
    horizon_end = horizon_start + timedelta(days=14)

    scenarios: list[tuple[
        FactoryState,
        list[SchedulingOperation],
        list[SchedulingMachine],
        datetime,
        datetime,
    ]] = []

    async with session_factory() as session:
        state = await FactoryState.load(session, DEV_TENANT_ID)
        if not state.loaded_ok:
            raise RuntimeError(
                f"FactoryState load failed: {state.load_error}",
            )
        if not state.open_orders:
            raise RuntimeError(
                "FactoryState has zero open orders — populate curated layer "
                "via /v1/factory-data/ingest before benchmarking.",
            )

        resolver = RoutingResolver(state)
        # Pega ingestion_id se passado, senão usa o active
        _ = ingestion_id  # FactoryState.load já filtrou pelo active

        # Cada cenário = subset distinto de open_orders. Para amostras
        # estáveis dividimos as orders em N grupos e corremos cada grupo.
        orders = list(state.open_orders)
        if not orders:
            raise RuntimeError("no orders to schedule")

        chunk_size = max(1, len(orders) // max(1, n_scenarios))
        for idx in range(n_scenarios):
            chunk = orders[idx * chunk_size : (idx + 1) * chunk_size]
            if not chunk:
                break
            ops = resolver.resolve_many(chunk, horizon_start=horizon_start)
            if not ops:
                continue
            # Constrói SchedulingMachines a partir dos machine_ids das ops
            machine_ids = sorted({op.machine_id for op in ops if op.machine_id})
            machines = [
                SchedulingMachine(machine_id=mid, name=mid)
                for mid in machine_ids
            ]
            scenarios.append((state, ops, machines, horizon_start, horizon_end))

    if not scenarios:
        raise RuntimeError("no scenarios produced from real data")
    return scenarios


# --------------------------------------------------------------------------- #
# Engine runners                                                               #
# --------------------------------------------------------------------------- #


def _greedy_only_config() -> CPOConfig:
    """Engine configurada para emitir apenas a baseline greedy.

    ``generations=0`` faz o ``for gen in range(...)`` saltar — o engine
    devolve directamente a baseline em ``best_final``. As flags do
    pipeline ficam ON para que a baseline use o ``GreedyPipeline``
    explícito (8 fases) em vez do decoder embedded.
    """
    return CPOConfig(
        population_size=1,
        generations=0,
        time_limit_sec=0.0,
        seed=42,
    )


def _ga_full_config() -> CPOConfig:
    """Configuração default em produção — não tocar."""
    return CPOConfig(seed=42)  # tudo o resto é o default da dataclass


def _run_engine(
    state: FactoryState,
    ops: list[SchedulingOperation],
    machines: list[SchedulingMachine],
    horizon_start: datetime,
    horizon_end: datetime,
    config: CPOConfig,
) -> RunResult:
    engine = CPOv4Engine(state=state, config=config)
    t0 = time.time()
    result = engine.schedule(ops, machines, horizon_start, horizon_end)
    elapsed = time.time() - t0

    # ``solve_time_sec`` que o engine retorna já cobre o seu próprio
    # tempo. Mantemos o nosso wall-clock como fallback.
    metrics = {
        m: float(result.get(m, 0.0) or 0.0) for m in METRICS
    }
    metrics["solve_time_sec"] = float(result.get("solve_time_sec") or elapsed)
    label = "greedy_only" if config.generations == 0 else "ga_full"
    return RunResult(label=label, metrics=metrics, raw=result)


# --------------------------------------------------------------------------- #
# Reporting                                                                    #
# --------------------------------------------------------------------------- #


def _fmt(v: float, m: str) -> str:
    if m == "num_late_orders":
        return f"{int(v)}"
    if m == "otd_delivery":
        return f"{v:.3f}"
    return f"{v:.2f}"


def _delta_pct(greedy: float, ga: float, lower_is_better: bool) -> str:
    """Devolve string ``+x.x%`` (ganho) ou ``-x.x%`` (regressão).

    Para métricas em que mais é melhor (otd, throughput) ``lower_is_better=False``.
    """
    if abs(greedy) < 1e-9:
        # Sem baseline para comparar — só mostra o valor absoluto se for
        # zero também, senão N/A para evitar percentagens absurdas
        # (e.g. solve_time 0s → 30s não é "infinita regressão", é a
        # diferença de design entre os dois modos).
        if abs(ga) < 1e-9:
            return "+0.0%"
        return "n/a"
    if lower_is_better:
        pct = (greedy - ga) / abs(greedy) * 100.0
    else:
        pct = (ga - greedy) / abs(greedy) * 100.0
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


METRIC_DIRECTION = {
    "makespan_hours": True,         # lower is better
    "otd_delivery": False,          # higher is better
    "throughput_eur_day": False,    # higher is better
    "num_late_orders": True,        # lower is better
    "solve_time_sec": True,         # lower is better
}


def render_markdown(
    rows: list[tuple[str, RunResult, RunResult]],
    note: str = "",
) -> str:
    """Tabela por cenário + tabela de média + delta médio."""
    lines: list[str] = []
    if note:
        lines.append(note)
        lines.append("")

    lines.append("## Resultados por cenário")
    lines.append("")
    lines.append(
        "| Cenário | Métrica | Greedy puro | GA default | delta (GA vs greedy) |",
    )
    lines.append("|---|---|---|---|---|")
    for scen_id, greedy, ga in rows:
        for m in METRICS:
            lines.append(
                f"| {scen_id} | {m} | {_fmt(greedy.metrics[m], m)} | "
                f"{_fmt(ga.metrics[m], m)} | "
                f"{_delta_pct(greedy.metrics[m], ga.metrics[m], METRIC_DIRECTION[m])} |",
            )

    # Resumo: média + delta médio
    lines.append("")
    lines.append("## Resumo (média sobre cenários)")
    lines.append("")
    lines.append("| Métrica | Greedy puro (avg) | GA default (avg) | delta médio |")
    lines.append("|---|---|---|---|")
    for m in METRICS:
        g_vals = [g.metrics[m] for _, g, _ in rows]
        a_vals = [a.metrics[m] for _, _, a in rows]
        if not g_vals:
            continue
        g_avg = statistics.fmean(g_vals)
        a_avg = statistics.fmean(a_vals)
        lines.append(
            f"| {m} | {_fmt(g_avg, m)} | {_fmt(a_avg, m)} | "
            f"{_delta_pct(g_avg, a_avg, METRIC_DIRECTION[m])} |",
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Entrypoint                                                                   #
# --------------------------------------------------------------------------- #


def _run_one_scenario(
    state: FactoryState,
    ops: list[SchedulingOperation],
    machines: list[SchedulingMachine],
    horizon_start: datetime,
    horizon_end: datetime,
) -> tuple[RunResult, RunResult]:
    greedy = _run_engine(
        state, ops, machines, horizon_start, horizon_end,
        _greedy_only_config(),
    )
    ga = _run_engine(
        state, ops, machines, horizon_start, horizon_end,
        _ga_full_config(),
    )
    return greedy, ga


def _ensure_utf8_stdout() -> None:
    """Windows console default cp1252 não consegue gravar ç/á/ê. Forçamos
    UTF-8 explicitamente; em Linux/macOS é no-op."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfig = getattr(stream, "reconfigure", None)
        if reconfig is not None:
            try:
                reconfig(encoding="utf-8")
            except Exception:  # pragma: no cover — defensivo
                pass


def main(argv: Optional[list[str]] = None) -> int:
    _ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = ap.add_mutually_exclusive_group()
    src.add_argument(
        "--dry-run", action="store_true",
        help="cenários sintéticos (não toca em DB). Default.",
    )
    src.add_argument(
        "--from-erp", action="store_true",
        help="puxa FactoryState do active ingestion. Cai para "
             "dry-run se o curated layer estiver vazio.",
    )
    src.add_argument(
        "--ingestion-id", type=str, default=None,
        help="UUID de ingestion específica (assume backend live).",
    )
    ap.add_argument(
        "--n-scenarios", type=int, default=10,
        help="número de cenários (default 10).",
    )
    ap.add_argument(
        "--out", type=str, default=None,
        help="grava o relatório nesta path (markdown).",
    )
    ap.add_argument(
        "--json-out", type=str, default=None,
        help="grava resultados crus em JSON (debug).",
    )
    ap.add_argument(
        "--seed", type=int, default=42,
        help="seed do RNG do gerador sintético (default 42).",
    )
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    use_real = args.from_erp or args.ingestion_id is not None
    rng = random.Random(args.seed)
    rows: list[tuple[str, RunResult, RunResult]] = []
    mode_note = ""

    scenarios: list[tuple[
        FactoryState,
        list[SchedulingOperation],
        list[SchedulingMachine],
        datetime,
        datetime,
    ]] = []

    if use_real:
        try:
            ingestion_uuid = (
                UUID(args.ingestion_id) if args.ingestion_id else None
            )
            scenarios = asyncio.run(
                _load_real_scenarios(ingestion_uuid, args.n_scenarios),
            )
            mode_note = (
                "Fonte: active ingestion do dev tenant. "
                f"{len(scenarios)} cenários reais carregados."
            )
        except Exception as e:
            print(
                f"[cpo_benchmark] real scenarios indisponíveis ({e}); "
                "a cair para cenários sintéticos.",
                file=sys.stderr,
            )
            scenarios = []
            mode_note = (
                f"Fonte: --from-erp falhou ({e}). Resultados abaixo são "
                "cenários SINTÉTICOS — usar apenas para sanity-check; "
                "o benchmark real fica pendente para correr em prod-like."
            )

    if not scenarios:
        # Fallback sintético — sempre 10 cenários (ou ``--n-scenarios``).
        state = _synthetic_state()
        for idx in range(args.n_scenarios):
            ops, machines, hs, he = _synthetic_scenario(idx, rng)
            scenarios.append((state, ops, machines, hs, he))
        if not mode_note:
            mode_note = (
                "Fonte: cenários SINTÉTICOS (--dry-run). Estes números "
                "não representam a NELO — são apenas para validar que o "
                "script corre verde. O benchmark real fica pendente "
                "para correr em prod-like (backend + curated layer ON)."
            )

    for idx, (state, ops, machines, hs, he) in enumerate(scenarios):
        scen_id = f"s{idx:02d}"
        print(
            f"[cpo_benchmark] scenario {scen_id}: ops={len(ops)} "
            f"machines={len(machines)}",
            file=sys.stderr,
        )
        try:
            greedy, ga = _run_one_scenario(state, ops, machines, hs, he)
        except Exception as e:
            print(
                f"[cpo_benchmark] {scen_id} falhou: {e}",
                file=sys.stderr,
            )
            continue
        rows.append((scen_id, greedy, ga))

    if not rows:
        print(
            "[cpo_benchmark] zero cenários produziram resultado — abortar.",
            file=sys.stderr,
        )
        return 1

    md = render_markdown(rows, note=mode_note)
    print(md)

    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"[cpo_benchmark] relatório gravado em {args.out}", file=sys.stderr)

    if args.json_out:
        payload = {
            "mode_note": mode_note,
            "rows": [
                {
                    "scenario": scen_id,
                    "greedy": greedy.metrics,
                    "ga": ga.metrics,
                }
                for scen_id, greedy, ga in rows
            ],
        }
        Path(args.json_out).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        print(
            f"[cpo_benchmark] JSON cru gravado em {args.json_out}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
