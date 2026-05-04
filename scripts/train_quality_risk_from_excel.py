"""Sprint Q.13.H — Bootstrap QualityRiskModel directly from `Folha_IA_extra.xlsx`.

Why this script exists
----------------------
The full pipeline is::

    Excel  →  factory_curated.* (DB)  →  semantic_queries cache
           →  QualityRiskRetrainJob (Sundays 02:00 UTC)
           →  ModelRegistry.save  →  human promote (admin gate)
           →  load_active_quality_risk_predictor  →  CPO fitness

In a fresh deploy where the curated layer hasn't been populated yet,
the predictor stays ``None`` and the GA's ``w_quality_risk`` term is a
no-op. This script bypasses the curated layer + scheduler + governance
gate by:

  1. Reading the Excel sheets directly (openpyxl read-only).
  2. Assembling training rows in the SAME shape that
     :func:`src.ml.models_domain.quality_risk.build_training_dataset`
     produces — same feature columns, same `is_error` label.
  3. Calling :meth:`QualityRiskModel.train` to fit the classifier.
  4. (Optional) Saving the joblib artifact + registering it active in
     :class:`ModelRegistry` so the next CPO call picks it up.

The script does NOT replace the production retrain job. It's a one-shot
bootstrap: useful for the very first deploy + for local dev where the
DB ingest hasn't run.

Usage
-----

::

    # Train + print metrics, no artifact persistence:
    python scripts/train_quality_risk_from_excel.py --excel Folha_IA_extra.xlsx

    # Train + save joblib to disk:
    python scripts/train_quality_risk_from_excel.py \\
      --excel Folha_IA_extra.xlsx \\
      --save-to models/quality_risk_v1.joblib

    # Train + register active in ModelRegistry (needs DATABASE_URL):
    python scripts/train_quality_risk_from_excel.py \\
      --excel Folha_IA_extra.xlsx \\
      --register --tenant 11111111-1111-1111-1111-111111111111

The training takes ~30-60s on the NELO data (529k phase rows joined
with 89k errors). The fitted classifier is ~few hundred KB on disk.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger("train_quality_risk_from_excel")


# ─────────────────────────────────────────────────────────────────────
# Excel readers — one per sheet, returning typed dicts.
# ─────────────────────────────────────────────────────────────────────


def _norm(value: Any) -> Any:
    """Treat the literal string ``'NULL'`` (Excel export of NULL) as None."""
    if isinstance(value, str) and value.strip().upper() == "NULL":
        return None
    return value


def _open_sheet(workbook, name: str):
    ws = workbook[name]
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    idx = {col: i for i, col in enumerate(header)}
    return rows, idx


def read_orders(workbook) -> Dict[str, str]:
    """Map ``of_id -> produto_id`` (the product = NELO 'modelo')."""
    rows, idx = _open_sheet(workbook, "OrdensFabrico")
    of_id_i, prod_i = idx["Of_Id"], idx["Of_ProdutoId"]
    out: Dict[str, str] = {}
    for row in rows:
        of_id = _norm(row[of_id_i])
        prod = _norm(row[prod_i])
        if of_id is None:
            continue
        out[str(of_id)] = "" if prod is None else str(prod)
    return out


def read_molds(workbook) -> Dict[str, int]:
    """Map ``mold_id -> pocket_count``."""
    rows, idx = _open_sheet(workbook, "Moldes")
    mold_i, pockets_i = idx["MoldeId"], idx["MoldeNumeroPocosId"]
    out: Dict[str, int] = {}
    for row in rows:
        mold = _norm(row[mold_i])
        pockets = _norm(row[pockets_i])
        if mold is None:
            continue
        try:
            out[str(mold)] = int(pockets) if pockets is not None else 1
        except (ValueError, TypeError):
            out[str(mold)] = 1
    return out


def read_team_sizes(workbook) -> Dict[str, int]:
    """Aggregate worker count per ``fase_of_id`` from the assignment sheet.

    Some phases have multiple worker rows (pair work, sub-crews); the
    team_size feature in the model is the count.
    """
    rows, idx = _open_sheet(workbook, "FuncionariosFaseOrdemFabrico")
    fase_of_i = idx["FuncionarioFaseOf_FaseOfId"]
    counts: Dict[str, int] = {}
    for row in rows:
        fase_of = _norm(row[fase_of_i])
        if fase_of is None:
            continue
        key = str(fase_of)
        counts[key] = counts.get(key, 0) + 1
    return counts


def read_errors(workbook) -> set:
    """Set of ``(of_id, fase_id)`` pairs that have at least one error.

    Uses ``Erro_FaseAvaliacao`` (the phase where the error was DETECTED)
    rather than ``Erro_FaseOfCulpada`` because the former is what
    :func:`build_training_dataset` joins on (the model predicts "is this
    phase where errors typically surface", which is the gating signal
    for the CPO).
    """
    rows, idx = _open_sheet(workbook, "OrdemFabricoErros")
    of_i, fase_aval_i = idx["Erro_OfId"], idx["Erro_FaseAvaliacao"]
    pairs: set = set()
    for row in rows:
        of_id = _norm(row[of_i])
        fase = _norm(row[fase_aval_i])
        if of_id is None or fase is None:
            continue
        pairs.add((str(of_id), str(fase)))
    return pairs


# ─────────────────────────────────────────────────────────────────────
# Build training rows by streaming FasesOrdemFabrico (the heavy sheet).
# ─────────────────────────────────────────────────────────────────────


def build_rows(
    workbook,
    *,
    order_to_modelo: Dict[str, str],
    mold_pockets: Dict[str, int],
    team_sizes: Dict[str, int],
    error_keys: set,
) -> List[Dict[str, Any]]:
    """One training row per `FasesOrdemFabrico` row.

    Mirrors `build_training_dataset` in
    :mod:`src.ml.models_domain.quality_risk` field-for-field.
    """
    rows_iter, idx = _open_sheet(workbook, "FasesOrdemFabrico")
    fid = idx["FaseOf_Id"]
    of_i = idx["FaseOf_OfId"]
    fim_i = idx["FaseOf_Fim"]
    fase_i = idx["FaseOf_FaseId"]
    mold_i = idx["MoldeOfId"]

    # First pass — count phase totals + phase errors so we can compute
    # `phase_error_rate` per fase_id (matches build_training_dataset).
    phase_totals: Dict[str, int] = {}
    phase_errors: Dict[str, int] = {}
    cached: List[Tuple[Any, Any, Any, Any, Any]] = []
    for row in rows_iter:
        fase_of_id = _norm(row[fid])
        of_id = _norm(row[of_i])
        fim = _norm(row[fim_i])
        fase_id = _norm(row[fase_i])
        mold_id = _norm(row[mold_i])
        if fase_of_id is None or of_id is None or fase_id is None:
            continue
        key = (str(of_id), str(fase_id))
        cached.append((str(fase_of_id), key, fim, str(mold_id) if mold_id else "", str(fase_id)))
        phase_totals[str(fase_id)] = phase_totals.get(str(fase_id), 0) + 1
        if key in error_keys:
            phase_errors[str(fase_id)] = phase_errors.get(str(fase_id), 0) + 1

    rows: List[Dict[str, Any]] = []
    for fase_of_id, key, fim, mold_id, fase_id in cached:
        of_id = key[0]
        modelo_id = order_to_modelo.get(of_id, "")
        total = phase_totals.get(fase_id, 0)
        errs = phase_errors.get(fase_id, 0)
        phase_error_rate = (errs / total) if total else 0.0
        rows.append({
            "modelo_id": modelo_id,
            "fase_id": fase_id,
            "team_size": int(team_sizes.get(fase_of_id, 1) or 1),
            "mold_pocket_count": mold_pockets.get(mold_id, 1),
            "phase_error_rate": round(phase_error_rate, 4),
            "queue_depth": total,
            "is_error": 1 if key in error_keys else 0,
            "timestamp": fim,
        })
    return rows


# ─────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────


def load_dataset(excel_path: Path) -> List[Dict[str, Any]]:
    """End-to-end: open the workbook, build the training set."""
    import openpyxl

    logger.info("Opening %s (read-only)…", excel_path)
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)

    t0 = time.time()
    logger.info("Reading orders…")
    order_to_modelo = read_orders(wb)
    logger.info("  %d orders", len(order_to_modelo))

    logger.info("Reading molds…")
    mold_pockets = read_molds(wb)
    logger.info("  %d molds", len(mold_pockets))

    logger.info("Reading team-size aggregates…")
    team_sizes = read_team_sizes(wb)
    logger.info("  %d (fase_of, team_size) pairs", len(team_sizes))

    logger.info("Reading errors…")
    error_keys = read_errors(wb)
    logger.info("  %d (of_id, fase_id) error keys", len(error_keys))

    logger.info("Streaming FasesOrdemFabrico → training rows…")
    rows = build_rows(
        wb,
        order_to_modelo=order_to_modelo,
        mold_pockets=mold_pockets,
        team_sizes=team_sizes,
        error_keys=error_keys,
    )
    elapsed = time.time() - t0
    logger.info(
        "Built %d training rows in %.1fs (%d positives, positive_rate=%.4f)",
        len(rows),
        elapsed,
        sum(r["is_error"] for r in rows),
        sum(r["is_error"] for r in rows) / max(1, len(rows)),
    )
    return rows


def train_model(rows: List[Dict[str, Any]]):
    """Fit `QualityRiskModel` on the prepared rows + return (model, metrics)."""
    from src.ml.models_domain.quality_risk import QualityRiskModel

    if not rows:
        raise SystemExit("No rows produced — check the Excel path / shape.")
    model = QualityRiskModel()
    metrics = model.train(rows)
    logger.info("Training metrics: %s", metrics)
    return model, metrics


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--excel",
        default="Folha_IA_extra.xlsx",
        help="Path to the NELO Excel export (default: %(default)s)",
    )
    parser.add_argument(
        "--save-to",
        default=None,
        help="Path to write the trained joblib artifact (skipped if omitted).",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register the artifact in ModelRegistry as active (needs DATABASE_URL).",
    )
    parser.add_argument(
        "--tenant",
        default=None,
        help="Tenant UUID for --register (required when --register is set).",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help=(
            "Subsample (stratified) to this many rows before training. "
            "Useful for smoke tests / CI runs where the full 529k rows "
            "are overkill. 0 = use everything (default)."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    excel_path = Path(args.excel).resolve()
    if not excel_path.exists():
        logger.error("Excel file not found: %s", excel_path)
        return 2

    rows = load_dataset(excel_path)
    if args.max_samples and 0 < args.max_samples < len(rows):
        # Stratified by `is_error` so the subsample keeps the positive
        # rate roughly the same — important when running with --max-samples
        # 5000 for a smoke test (1% positives needs the positives kept).
        positives = [r for r in rows if r["is_error"] == 1]
        negatives = [r for r in rows if r["is_error"] == 0]
        target_positive_rate = len(positives) / max(1, len(rows))
        target_pos = max(2, int(round(args.max_samples * target_positive_rate)))
        target_neg = args.max_samples - target_pos
        rows = positives[:target_pos] + negatives[:target_neg]
        logger.info(
            "Subsampled to %d rows (max_samples=%d, target_pos=%d, target_neg=%d)",
            len(rows), args.max_samples, target_pos, target_neg,
        )

    model, metrics = train_model(rows)

    print()
    print("--- QualityRiskModel trained ---------------------------------")
    print(f"  samples:        {metrics['samples']:>10}")
    print(f"  positive_rate:  {metrics['positive_rate']:>10.4f}")
    print(f"  train / val:    {metrics['samples_train']} / {metrics['samples_val']}")
    print(f"  AUC:            {metrics['auc']:>10.4f}")
    print(f"  AP:             {metrics['ap']:>10.4f}")
    print(f"  WMAPE (1-AUC):  {metrics['wmape']:>10.4f}")
    print()
    # Note on leakage (intentionally faithful to the production
    # trainer): `phase_error_rate` is computed across the whole dataset,
    # so each row's label is partially encoded in its own feature value.
    # That inflates AUC at training time but doesn't break production
    # use, where the predictor ranks new (unseen) assignments. Worth
    # flagging here so the AUC is read with the right grain of salt.
    if metrics["auc"] > 0.95 and metrics["positive_rate"] < 0.10:
        print(
            "  NOTE: AUC > 0.95 with sparse positives is partly an artefact "
            "of `phase_error_rate` being computed globally over the same "
            "dataset (also true of `build_training_dataset` in the curated "
            "pipeline). Production ranking still works; treat 0.99 as "
            "'training-time upper bound', not 'expected production AUC'."
        )
        print()

    if args.save_to:
        import joblib
        out_path = Path(args.save_to).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, out_path)
        logger.info("Saved joblib artifact to %s (%.1f KB)",
                    out_path, out_path.stat().st_size / 1024.0)

    if args.register:
        if not args.tenant:
            logger.error("--register requires --tenant <uuid>")
            return 2
        try:
            tenant_id = UUID(args.tenant)
        except ValueError:
            logger.error("--tenant must be a UUID")
            return 2
        # Lazy DB imports — keeps the train-only invocation light.
        import asyncio

        async def _register() -> None:
            from src.shared.database import get_session_context
            from src.ml.models.registry import ModelRegistry

            async with get_session_context() as session:
                registry = ModelRegistry(session, tenant_id)
                artifact = await registry.save(
                    model_name="quality_risk",
                    model=model,
                    metrics=dict(metrics),
                    trained_by="bootstrap_excel",
                    training_samples=int(metrics["samples"]),
                )
                # Direct activate — bootstrap path bypasses governance.
                # Operators can override later via the standard promote
                # flow; this gets the predictor live for the first CPO
                # call after deploy.
                from sqlalchemy import update
                from src.ml.models.registry import MLModelArtifact
                await session.execute(
                    update(MLModelArtifact)
                    .where(MLModelArtifact.tenant_id == tenant_id)
                    .where(MLModelArtifact.model_name == "quality_risk")
                    .values(active=False)
                )
                await session.execute(
                    update(MLModelArtifact)
                    .where(MLModelArtifact.id == artifact.id)
                    .values(active=True)
                )
                await session.commit()
                logger.info(
                    "Registered + activated quality_risk v%s (artifact_id=%s)",
                    artifact.version, artifact.id,
                )

        asyncio.run(_register())

    return 0


if __name__ == "__main__":
    sys.exit(main())
