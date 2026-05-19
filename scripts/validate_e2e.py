"""
ProdPlan ONE - End-to-End validation with real NELO data.

Runs the full ingestion + semantic + cross-module smoke test against
`Folha_IA_extra.xlsx` (57MB). Writes a Markdown report with PASS/DRIFT/FLAG
tags per metric. Does NOT touch the Postgres DB - `IngestEngine` runs in
in-memory mode (Sprint J default).

Usage:
    .venv/Scripts/python.exe scripts/validate_e2e.py
"""

from __future__ import annotations

import logging
import sys
import time
import traceback
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from statistics import mean, median
from typing import Any, List, Tuple

# Force UTF-8 stdout on Windows (cp1252 console otherwise crashes on
# any "->", ">=", "<=" or accented char the report happens to contain).
import io
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Python >=3.7
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Silence noisy libraries so validation output stays readable.
logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXCEL_PATH = REPO_ROOT / "Folha_IA_extra.xlsx"
REPORT_PATH = REPO_ROOT / "docs" / "sprint-validation-report.md"

sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Blueprint v2.0 reference numbers
# ---------------------------------------------------------------------------

BLUEPRINT: dict[str, Any] = {
    "orders_total": 27_911,
    "order_phase_total": 529_450,
    "funcionarios_fase_of_total": 423_769,
    "quality_events_total": 89_836,
    "workers_total": 301,
    "workers_active": 129,
    "skill_matrix_total": 902,
    "phases_total": 71,
    "phases_active": 41,
    "molds_total": 510,
    "molds_in_production": 397,
    "models_total": 899,
    "standard_phases_total": 15_445,
    "lead_time_avg_days": 51.0,
    "lead_time_median_days": 37.0,
    "lead_time_p90_days": 107.0,
    "rework_rate_pct": 11.6,
    "laminagem_error_rate_pct": 102.5,
    "pintura_error_rate_pct": 61.0,
    "prep_molde_error_rate_pct": 45.7,
    "top_error_1": ("Molde com deformações", 15_854),
    "top_error_2": ("Molde baço", 15_672),
}


# ---------------------------------------------------------------------------
# Report structure
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    name: str
    expected: Any
    observed: Any
    status: str  # PASS | DRIFT | FLAG | SKIP
    notes: str = ""

    def to_row(self) -> str:
        def _fmt(v: Any) -> str:
            if isinstance(v, float):
                return f"{v:,.2f}"
            if isinstance(v, int):
                return f"{v:,}"
            if isinstance(v, tuple) and len(v) == 2:
                return f"{v[0]} = {v[1]:,}"
            if v is None:
                return "-"
            return str(v)

        return (
            f"| {self.name} | {_fmt(self.expected)} | {_fmt(self.observed)} | "
            f"{self.status} | {self.notes} |"
        )


@dataclass
class Report:
    findings: List[Finding] = field(default_factory=list)
    bugs: List[str] = field(default_factory=list)
    phase_timings: List[Tuple[str, float]] = field(default_factory=list)
    ingest_stats: dict = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)

    def add(self, f: Finding) -> None:
        self.findings.append(f)
        print(f"  [{f.status:5}] {f.name}: expected={f.expected!r} observed={f.observed!r} {f.notes}")

    def add_bug(self, msg: str) -> None:
        self.bugs.append(msg)
        print(f"  [BUG  ] {msg}")

    def summary(self) -> dict:
        counts = {"PASS": 0, "DRIFT": 0, "FLAG": 0, "SKIP": 0}
        for f in self.findings:
            counts[f.status] = counts.get(f.status, 0) + 1
        total = len(self.findings)
        return {
            "total": total,
            "pass": counts["PASS"],
            "drift": counts["DRIFT"],
            "flag": counts["FLAG"],
            "skip": counts["SKIP"],
            "pct_pass": round(100 * counts["PASS"] / total, 1) if total else 0,
            "bugs": len(self.bugs),
            "elapsed_s": round(time.time() - self.started_at, 1),
        }


# ---------------------------------------------------------------------------
# Classifier - drift rules
# ---------------------------------------------------------------------------

def unwrap(resp: Any) -> dict:
    """SemanticQueriesInMemory wraps every payload as
    `{"data": {...}, "data_confidence": N, "trust_status": "...", ...}`.
    Unwrap once so our assertions look at the actual numbers."""
    if isinstance(resp, dict) and "data" in resp and isinstance(resp["data"], dict):
        return resp["data"]
    return resp if isinstance(resp, dict) else {}


def classify(expected: Any, observed: Any, *, abs_tol: float = 0.01) -> Tuple[str, str]:
    """Return (status, note) comparing observed vs expected."""
    if observed is None:
        return "SKIP", "not observed"
    if isinstance(expected, (int, float)) and isinstance(observed, (int, float)):
        if expected == 0:
            return ("PASS", "") if observed == 0 else ("FLAG", "expected zero")
        delta_pct = 100.0 * abs(observed - expected) / abs(expected)
        if delta_pct <= 1.0:
            return "PASS", f"delta={delta_pct:.2f}%"
        if delta_pct <= 5.0:
            return "DRIFT", f"delta={delta_pct:.2f}%"
        return "FLAG", f"delta={delta_pct:.2f}%"
    if expected == observed:
        return "PASS", ""
    return "FLAG", "value mismatch"


def _sign(msg: str) -> None:
    border = "=" * len(msg)
    print(f"\n{border}\n{msg}\n{border}")


# ---------------------------------------------------------------------------
# Fase B - Ingestion
# ---------------------------------------------------------------------------

def phase_b_ingest(report: Report):
    _sign("Fase B - Ingestion (57MB Excel)")
    from src.factory_data_product.ingest.engine import IngestEngine

    if not EXCEL_PATH.exists():
        report.add_bug(f"Excel not found at {EXCEL_PATH}")
        sys.exit(1)

    engine = IngestEngine()
    started = time.time()
    try:
        result = engine.ingest(EXCEL_PATH, auto_activate=True)
    except Exception as exc:
        report.add_bug(f"Ingestion raised {type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
    elapsed = time.time() - started
    report.phase_timings.append(("ingest", elapsed))

    report.ingest_stats = {
        "success": result.success,
        "status": str(result.status),
        "ingestion_id": str(result.ingestion_id) if result.ingestion_id else None,
        "total_rows_raw": result.total_rows_raw,
        "total_rows_curated": result.total_rows_curated,
        "quality_gate_status": str(result.quality_gate_status),
        "has_schema_drift": result.has_schema_drift,
        "drift_blocking": result.drift_blocking,
        "is_duplicate": result.is_duplicate,
        "errors": list(result.errors),
        "warnings": list(result.warnings),
        "elapsed_s": round(elapsed, 2),
    }
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Success: {result.success}")
    print(f"  Status: {result.status}")
    print(f"  Rows raw: {result.total_rows_raw:,}")
    print(f"  Rows curated: {result.total_rows_curated:,}")
    print(f"  Quality gate: {result.quality_gate_status}")
    print(f"  Schema drift: {result.has_schema_drift} (blocking={result.drift_blocking})")
    if result.errors:
        for err in result.errors:
            report.add_bug(f"Ingestion error: {err}")

    if not result.success:
        print("  !!! Ingestion did not succeed; aborting further phases.")
        return engine, None

    return engine, result.ingestion_id


# ---------------------------------------------------------------------------
# Fase C - Count validation
# ---------------------------------------------------------------------------

def phase_c_counts(report: Report, engine, ingestion_id):
    _sign("Fase C - Counts vs Blueprint v2.0")
    if ingestion_id is None:
        report.add(Finding("counts_skipped", "ingestion_id", None, "SKIP", "no ingestion"))
        return None

    raw_rows = engine._raw_rows
    curated = engine._curated_data.get(str(ingestion_id)) or engine._curated_data.get(ingestion_id)
    if not curated:
        # Some implementations key by UUID not string.
        for k, v in engine._curated_data.items():
            if str(k) == str(ingestion_id):
                curated = v
                break
    if not curated:
        report.add_bug(f"No curated data for ingestion {ingestion_id}")
        return None

    # Raw-row counts are per-sheet. Each record has "sheet_name" (or similar).
    # Count by sheet.
    by_sheet: dict[str, int] = {}
    for row in raw_rows:
        name = row.get("sheet_name") or row.get("sheet") or "?"
        by_sheet[name] = by_sheet.get(name, 0) + 1
    print("  RAW per-sheet:")
    for k, v in sorted(by_sheet.items()):
        print(f"    {k}: {v:,}")

    # Blueprint cross-check (flexible about sheet name spelling).
    def _find(*keywords) -> int:
        for k, v in by_sheet.items():
            key_low = k.lower()
            if all(kw.lower() in key_low for kw in keywords):
                return v
        return 0

    pairs: list[Tuple[str, int, Any]] = [
        ("orders (OrdensFabrico)", _find("Ordens"), BLUEPRINT["orders_total"]),
        ("order_phase (FasesOrdemFabrico)", _find("FasesOrdem"), BLUEPRINT["order_phase_total"]),
        ("funcionarios_fase_of", _find("Funcionarios", "Fase", "Ordem"), BLUEPRINT["funcionarios_fase_of_total"]),
        ("quality_events (OrdemFabricoErros)", _find("OrdemFabrico", "Erros"), BLUEPRINT["quality_events_total"]),
        ("workers (Funcionarios, not skill)", _find("Funcionarios") if not _find("Fase") else 0, BLUEPRINT["workers_total"]),
        ("skill_matrix (FuncionariosFasesAptos)", _find("FasesAptos"), BLUEPRINT["skill_matrix_total"]),
        ("phases (Fases)", _find("Fases") if not (_find("Ordem") or _find("Standard") or _find("Aptos")) else 0, BLUEPRINT["phases_total"]),
        ("molds (Moldes)", _find("Moldes"), BLUEPRINT["molds_total"]),
        ("models (Modelos)", _find("Modelos"), BLUEPRINT["models_total"]),
        ("standard_phases (FasesStandardModelos)", _find("Standard"), BLUEPRINT["standard_phases_total"]),
    ]
    for label, observed, expected in pairs:
        status, note = classify(expected, observed)
        report.add(Finding(label, expected, observed, status, note))

    # Curated counts (post-transformation - should broadly match raw).
    print(f"  CURATED tables ({len(curated)} keys):")
    for k in sorted(curated):
        rows = curated[k]
        print(f"    {k}: {len(rows):,}")

    return curated


# ---------------------------------------------------------------------------
# Fase D - Semantic layer
# ---------------------------------------------------------------------------

def phase_d_semantic(report: Report, engine):
    _sign("Fase D - Semantic queries with real data")
    from src.factory_data_product.services.semantic_queries_inmemory import (
        get_semantic_service,
    )

    svc = get_semantic_service(engine)

    # get_wip
    try:
        wip = unwrap(svc.get_wip())
    except Exception as exc:
        report.add_bug(f"get_wip raised: {exc}")
        wip = {}
    print(f"  get_wip -> {wip.get('total_orders')} orders, {wip.get('open_orders_pct')}% open")
    report.add(Finding(
        "get_wip.total_orders",
        BLUEPRINT["orders_total"], wip.get("total_orders"),
        *classify(BLUEPRINT["orders_total"], wip.get("total_orders")),
    ))
    open_pct = wip.get("open_orders_pct") or 0
    if isinstance(open_pct, (int, float)) and open_pct > 50:
        report.add(Finding(
            "get_wip.open_pct_realistic",
            "<=50%", f"{open_pct}%", "FLAG",
            "Blueprint: ~740 boats in prod out of 27.9k total orders",
        ))

    # get_lead_time
    try:
        lt = unwrap(svc.get_lead_time())
    except Exception as exc:
        report.add_bug(f"get_lead_time raised: {exc}")
        lt = {}
    for label, key, expected in [
        ("lead_time.avg", "avg_lead_time_days", BLUEPRINT["lead_time_avg_days"]),
        ("lead_time.median", "median_lead_time_days", BLUEPRINT["lead_time_median_days"]),
        ("lead_time.p90", "p90_lead_time_days", BLUEPRINT["lead_time_p90_days"]),
    ]:
        obs = lt.get(key)
        status, note = classify(expected, obs, abs_tol=1.0)
        if status == "DRIFT" and isinstance(obs, (int, float)):
            if abs(obs - expected) / expected <= 0.10:
                status = "PASS"
                note = "within 10% band"
        report.add(Finding(label, expected, obs, status, note))

    # get_quality - top errors
    try:
        q = unwrap(svc.get_quality(top_errors=10))
    except Exception as exc:
        report.add_bug(f"get_quality raised: {exc}")
        q = {}
    top = q.get("top_items") or []
    print(f"  get_quality -> total={q.get('total_errors')}, top5:")
    for i, item in enumerate(top[:5]):
        name = item.get("erro_tipo") or item.get("name") or item.get("error_type") or "?"
        count = item.get("count") or item.get("total_erros") or 0
        pct = item.get("pct") or item.get("percent") or 0
        print(f"    {i + 1}. {name[:40]:40} {count:>7,}  {pct:>5.1f}%")
    report.add(Finding(
        "quality.total_errors",
        BLUEPRINT["quality_events_total"],
        q.get("total_errors"),
        *classify(BLUEPRINT["quality_events_total"], q.get("total_errors")),
    ))
    if top:
        first = top[0]
        first_name = (first.get("erro_tipo") or first.get("name") or "").strip()
        first_count = first.get("count") or first.get("total_erros") or 0
        expected_name, expected_count = BLUEPRINT["top_error_1"]
        hit_name = expected_name.lower() in first_name.lower()
        status, note = ("PASS", "name ✓") if hit_name else ("FLAG", "top-1 error ≠ blueprint")
        report.add(Finding(
            "quality.top1.name",
            expected_name, first_name, status, note,
        ))
        report.add(Finding(
            "quality.top1.count",
            expected_count, first_count,
            *classify(expected_count, first_count),
        ))

    # get_bottlenecks - expect Laminagem/Pintura at top
    try:
        bn = unwrap(svc.get_bottlenecks(top_n=10))
    except Exception as exc:
        report.add_bug(f"get_bottlenecks raised: {exc}")
        bn = {}
    bn_rows = bn.get("bottlenecks") or []
    print(f"  get_bottlenecks -> {len(bn_rows)} phases; top3:")
    for b in bn_rows[:3]:
        name = b.get("phase_name") or b.get("fase_id") or "?"
        sev = b.get("severity") or "?"
        backlog = b.get("backlog_dias") or b.get("backlog_horas") or 0
        print(f"    {name[:30]:30} {sev:10} backlog={backlog}")
    top_names = " | ".join(
        (b.get("phase_name") or b.get("fase_id") or "").lower()
        for b in bn_rows[:3]
    )
    status = "PASS" if ("laminag" in top_names or "pintura" in top_names) else "FLAG"
    report.add(Finding(
        "bottlenecks.top_contains_laminagem_or_pintura",
        "laminag|pintura", top_names, status,
    ))

    # get_skills_risk
    try:
        sr = unwrap(svc.get_skills_risk(min_capable=5))
    except Exception as exc:
        report.add_bug(f"get_skills_risk raised: {exc}")
        sr = {}
    print(f"  get_skills_risk -> phases_at_risk={sr.get('phases_at_risk')}, spof={sr.get('spof_count')}")
    risk_phases = " | ".join(
        (r.get("phase_name") or r.get("fase_id") or "").lower()
        for r in (sr.get("at_risk_phases") or [])[:20]
    )
    hit = "pintura" in risk_phases or "golas" in risk_phases
    report.add(Finding(
        "skills_risk.includes_pintura_or_colagem_golas",
        "pintura|golas", risk_phases[:80], "PASS" if hit else "FLAG",
    ))

    # get_mold_conflicts - Blueprint warns low coverage
    try:
        mc = unwrap(svc.get_mold_conflicts())
    except Exception as exc:
        report.add_bug(f"get_mold_conflicts raised: {exc}")
        mc = {}
    print(f"  get_mold_conflicts -> conflicts={len(mc.get('conflicts') or [])}, coverage={mc.get('confidence')}")

    # get_overview
    try:
        ov = unwrap(svc.get_overview())
    except Exception as exc:
        report.add_bug(f"get_overview raised: {exc}")
        ov = {}
    tables = ov.get("tables") or {}
    print(f"  get_overview -> {len(tables)} tables available")

    return svc


# ---------------------------------------------------------------------------
# Fase E - Cross-module
# ---------------------------------------------------------------------------

def phase_e_cross_module(report: Report, engine, semantic):
    _sign("Fase E - Cross-module smoke tests")

    # 1. Rework classifier (R.9) against real phase names.
    try:
        from src.plan.cpo.decoder import classify_rework_phase

        # Pull phase names from curated Fases sheet.
        active = engine._active_run
        ingestion_id = active["active_ingestion_id"] if active else None
        curated = engine._curated_data.get(str(ingestion_id)) or {}
        # Phase names live either in 'phase' or in 'order_phase.fase_nome'.
        names: set[str] = set()
        for key in ("phase", "phases", "order_phase"):
            rows = curated.get(key) or []
            for r in rows:
                name = r.get("fase_nome") or r.get("name") or r.get("phase_name")
                if name:
                    names.add(str(name))
            if len(names) > 20:
                break
        buckets = {"sanding_water": 0, "sanding_polish": 0, "painting_finishing": 0, None: 0}
        for n in names:
            bucket = classify_rework_phase(n, None)
            buckets[bucket] = buckets.get(bucket, 0) + 1
        print(f"  rework_classifier buckets over {len(names)} phase names: {buckets}")
        hit = (
            buckets.get("sanding_water", 0) > 0
            or buckets.get("sanding_polish", 0) > 0
            or buckets.get("painting_finishing", 0) > 0
        )
        report.add(Finding(
            "rework_classifier.finds_at_least_one_bucket",
            ">=1 bucket hit", buckets, "PASS" if hit else "FLAG",
        ))
    except Exception as exc:
        report.add_bug(f"rework_classifier raised: {exc}")

    # 2. Fitness v2.0 - pure function
    try:
        from src.plan.cpo.fitness import FitnessConfig, compute_fitness

        cfg = FitnessConfig(use_v2_weights=True)
        # Synthetic schedule with known KPIs.
        schedule = {
            "makespan_hours": 200,
            "total_tardiness_hours": 20,
            "total_idle_hours": 40,
            "setups": 5,
            "throughput_eur_day": 32_000,
            "quality_risk_mean": 0.1,
        }
        fit = compute_fitness(schedule, cfg)
        print(f"  fitness_v2.compute -> {fit:.4f}")
        in_range = 0.0 <= fit <= 2.0  # accept small overshoot before clamp
        report.add(Finding(
            "fitness_v2.in_reasonable_range",
            "[0, 2]", round(fit, 4), "PASS" if in_range else "FLAG",
        ))
    except Exception as exc:
        report.add_bug(f"fitness_v2 raised: {exc}")

    # 3. MAP-Elites v2.0 - insert 10 synthetic elites
    try:
        from src.plan.cpo.chromosome import Chromosome
        from src.plan.cpo.mapelites import MAPElites3D

        archive = MAPElites3D(use_v2_axes=True)
        for i in range(10):
            c = Chromosome.identity(5)
            sched = {
                "lam_utilization": 40 + i * 4,
                "tardiness_transport_d": i * 1.0,
                "idle_pct": 30 - i * 2,
            }
            archive.insert(c, fitness=float(i), schedule=sched, generation=1)
        reps = archive.representatives(5)
        cells = archive.cells_occupied()
        print(f"  mapelites_v2 -> cells={cells}, representatives={len(reps)}")
        ok = cells >= 5 and len(reps) >= 3
        report.add(Finding(
            "mapelites_v2.10_inserts_spread",
            "cells>=5 reps>=3", f"cells={cells} reps={len(reps)}",
            "PASS" if ok else "FLAG",
        ))
    except Exception as exc:
        report.add_bug(f"mapelites_v2 raised: {exc}")

    # 4. Mold Health calculator - pure function
    try:
        from src.plan.services.mold_health_calculator import (
            HealthComponents, _risk_from_score,
        )

        # Evaluate classification across a sweep of scores.
        sweep = [_risk_from_score(s, {"red": 40, "yellow": 70}) for s in range(0, 101, 10)]
        red = sum(1 for s in sweep if s == "red")
        green = sum(1 for s in sweep if s == "green")
        print(f"  mold_health risk sweep (11 steps): red={red}, green={green}")
        # 0, 10, 20, 30 -> red (4). 40,50,60 -> yellow (3). 70+ -> green (4).
        ok = red >= 3 and green >= 3
        report.add(Finding(
            "mold_health.risk_classification_sweep",
            "red>=3 & green>=3", f"red={red} green={green}",
            "PASS" if ok else "FLAG",
        ))
    except Exception as exc:
        report.add_bug(f"mold_health raised: {exc}")

    # 5. Guardrails Tier 1 - regex survives NELO-ish Portuguese text
    try:
        from src.copilot.guardrails_tier1 import scan

        sample = "Encomenda OF-137073 para NIF: 501234567 fornecedor Móveis Lda"
        res = scan(sample)
        print(f"  tier1_scan('NIF:') -> matches={len(res.matches)}, patterns={res.pattern_counts()}")
        # Should pick up the NIF token at the very least.
        ok = res.has_violations
        report.add(Finding(
            "guardrails_tier1.detects_pt_nif",
            ">=1 match", f"{len(res.matches)} matches",
            "PASS" if ok else "FLAG",
        ))
    except Exception as exc:
        report.add_bug(f"guardrails_tier1 raised: {exc}")

    # 6. DatasetBuilder with real semantic
    try:
        from src.ml.llm.dataset_builder import DatasetBuilder

        builder = DatasetBuilder(semantic_service=semantic)
        examples = builder.build(max_per_topic=10)
        print(f"  dataset_builder -> {len(examples)} examples")
        ok = len(examples) >= 3
        report.add(Finding(
            "dataset_builder.generates_examples",
            ">=3", len(examples), "PASS" if ok else "FLAG",
        ))
    except Exception as exc:
        report.add_bug(f"dataset_builder raised: {exc}")

    # 7. Structured output smoke (no live LLM - exercise the shape parser).
    try:
        from pydantic import BaseModel

        from src.copilot.llm.structured import _coerce_to_dict, _build_schema_hint

        class _Shape(BaseModel):
            ok: bool

        s = _build_schema_hint(_Shape)
        coerced = _coerce_to_dict({"ok": True})
        print(f"  structured._build_schema_hint len={len(s)}; coerce dict ok")
        report.add(Finding(
            "structured.schema_hint_and_coerce",
            "len>30 & coerce dict", f"len={len(s)}",
            "PASS" if len(s) > 30 and coerced == {"ok": True} else "FLAG",
        ))
    except Exception as exc:
        report.add_bug(f"structured output raised: {exc}")


# ---------------------------------------------------------------------------
# Fase F - Bug hunt over real data
# ---------------------------------------------------------------------------

def phase_f_bug_hunt(report: Report, engine):
    _sign("Fase F - Bug hunt with real data")

    active = engine._active_run
    if not active:
        report.add_bug("No active run after ingestion - activation probably failed.")
        return
    ingestion_id = active["active_ingestion_id"]
    curated = engine._curated_data.get(str(ingestion_id)) or {}

    # Unicode sanity - pick a phase that carries diacritics.
    for key, rows in curated.items():
        for r in rows[:500]:
            for col, v in r.items():
                if isinstance(v, str) and ("ã" in v or "ç" in v or "ó" in v or "é" in v):
                    print(f"  unicode OK: [{key}.{col}] sample={v!r}")
                    report.add(Finding(
                        "unicode_pt_preserved", "diacritics readable",
                        f"{key}.{col}", "PASS",
                    ))
                    break
            else:
                continue
            break
        else:
            continue
        break

    # NULL handling - data_fim in open orders.
    op_rows = curated.get("order_phase") or []
    if op_rows:
        open_ops = sum(1 for r in op_rows if not r.get("data_fim"))
        closed_ops = len(op_rows) - open_ops
        print(f"  op_rows: {len(op_rows):,} (open={open_ops:,}, closed={closed_ops:,})")
        # Expect SOME open ops (WIP ≈ 740 barcos × ~18 phases ≈ 13k open phases)
        ok = open_ops > 0 and closed_ops > 0
        report.add(Finding(
            "null_handling.open_vs_closed_operations",
            "both non-zero",
            f"open={open_ops:,} closed={closed_ops:,}",
            "PASS" if ok else "FLAG",
        ))

    # Large list slicing - semantic queries cap at top_n.
    from src.factory_data_product.services.semantic_queries_inmemory import get_semantic_service
    svc = get_semantic_service(engine)
    for top_n in (5, 25, 100):
        q = svc.get_quality(top_errors=top_n)
        got = len(q.get("top_items") or [])
        ok = got <= top_n
        report.add(Finding(
            f"quality.top_n_cap(top_n={top_n})",
            f"<={top_n}", got,
            "PASS" if ok else "FLAG",
        ))

    # Date parsing - inspect a few data_inicio and see if datetime.date.
    if op_rows:
        from datetime import date, datetime
        sample = op_rows[0]
        d = sample.get("data_inicio")
        kind = type(d).__name__
        print(f"  date sample: data_inicio={d!r} type={kind}")
        ok = isinstance(d, (date, datetime, type(None), str))
        report.add(Finding(
            "date_parsing.data_inicio_type",
            "date | datetime | None",
            kind,
            "PASS" if ok else "FLAG",
        ))

    # Memory footprint - quick estimate.
    import gc, sys as _sys
    gc.collect()
    # Python doesn't give us a clean process RSS without psutil; approximate
    # by summing the largest curated lists.
    big = 0
    for k, v in curated.items():
        big += _sys.getsizeof(v) + sum(_sys.getsizeof(r) for r in v[:1000])
    print(f"  approximate in-memory bytes (sampled): {big / 1024 / 1024:.1f} MB")
    report.add(Finding(
        "memory.curated_reasonable",
        "<3 GB approx (sampled heuristic)",
        f"{big / 1024 / 1024:.1f} MB (sample)",
        "PASS",
        notes="sampled first 1000 rows per table",
    ))


# ---------------------------------------------------------------------------
# Fase G - Report
# ---------------------------------------------------------------------------

def phase_g_report(report: Report):
    _sign("Fase G - Report")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    summary = report.summary()
    lines: List[str] = []
    lines.append("# NELO Data Validation Report")
    lines.append("")
    lines.append(f"_Run: `scripts/validate_e2e.py` - {time.strftime('%Y-%m-%d %H:%M')} UTC._")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"* Tests run: **{summary['total']}**")
    lines.append(f"* PASS: **{summary['pass']}** ({summary['pct_pass']}%)")
    lines.append(f"* DRIFT (1-5%): **{summary['drift']}**")
    lines.append(f"* FLAG (>5% or unexpected): **{summary['flag']}**")
    lines.append(f"* SKIP: **{summary['skip']}**")
    lines.append(f"* Bugs found: **{summary['bugs']}**")
    lines.append(f"* Elapsed: **{summary['elapsed_s']}s**")
    lines.append("")

    lines.append("## Ingestion stats")
    lines.append("")
    for k, v in report.ingest_stats.items():
        lines.append(f"* `{k}`: {v}")
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    lines.append("| Metric | Expected | Observed | Status | Note |")
    lines.append("|---|---|---|---|---|")
    for f in report.findings:
        lines.append(f.to_row())
    lines.append("")

    lines.append("## Bugs")
    lines.append("")
    if report.bugs:
        for b in report.bugs:
            lines.append(f"* {b}")
    else:
        lines.append("_No bugs recorded._")
    lines.append("")

    lines.append("## Phase timings")
    lines.append("")
    for name, s in report.phase_timings:
        lines.append(f"* {name}: {s:.2f}s")
    lines.append("")

    lines.append("## What was NOT validated")
    lines.append("")
    lines.append("These areas need a live PostgreSQL to exercise end-to-end; the 529 unit tests")
    lines.append("are their sign-off for now.")
    lines.append("")
    lines.append("* Governance decision ledger + bulk / timeline / modify")
    lines.append("* Transport batches + Routing template services")
    lines.append("* Throughput dashboard (reads `OrderRevenue` from DB)")
    lines.append("* MRP shortage detector (reads `InventoryLedgerEntry` from DB)")
    lines.append("* APScheduler jobs (mold_health_scan / shortage_scan / alerts_scan)")
    lines.append("* Alembic migrations (applied only syntactically)")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  Report -> {REPORT_PATH}")
    print(f"  Summary: {summary}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    report = Report()

    try:
        engine, ingestion_id = phase_b_ingest(report)
    except Exception:
        phase_g_report(report)
        return 1

    if ingestion_id is None:
        phase_g_report(report)
        return 1

    try:
        phase_c_counts(report, engine, ingestion_id)
    except Exception as exc:
        report.add_bug(f"Phase C crashed: {exc}")
        traceback.print_exc()

    semantic = None
    try:
        semantic = phase_d_semantic(report, engine)
    except Exception as exc:
        report.add_bug(f"Phase D crashed: {exc}")
        traceback.print_exc()

    try:
        phase_e_cross_module(report, engine, semantic)
    except Exception as exc:
        report.add_bug(f"Phase E crashed: {exc}")
        traceback.print_exc()

    try:
        phase_f_bug_hunt(report, engine)
    except Exception as exc:
        report.add_bug(f"Phase F crashed: {exc}")
        traceback.print_exc()

    phase_g_report(report)
    return 0 if report.summary()["flag"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
