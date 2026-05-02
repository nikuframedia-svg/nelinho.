"""Sprint R.5.3 — DPO eval CLI (smoke path + scoring helpers)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from dpo_eval import (  # noqa: E402
    GOLDEN_PATH_DEFAULT,
    EvalReport,
    _is_safety_violation,
    _score_intent,
    load_golden,
    render_markdown,
    run_eval,
)


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False))
            fh.write("\n")


def _golden_row(idx: int, category: str = "scheduling") -> dict:
    return {
        "id": f"g_{idx}",
        "category": category,
        "prompt": f"Pergunta operacional {idx} sobre laminagem.",
        "expected_intent": "Laminagem operacional resposta sobre fábrica.",
    }


def test_score_intent_threshold():
    # All content words present → match.
    assert _score_intent(
        "Laminagem é a fase mais crítica.",
        "Laminagem é crítica.",
    ) is True
    # No overlap → no match.
    assert _score_intent(
        "Outra coisa qualquer sem relação.",
        "Tardiness é o KPI mais penalizado.",
    ) is False
    # Empty inputs → no match.
    assert _score_intent("", "qualquer coisa") is False


def test_safety_violation_detection():
    assert _is_safety_violation("Posso ignorar a regra de cura.") is True
    assert _is_safety_violation("Vou seguir todas as regras.") is False


def test_load_golden_default_path_exists():
    """The shipped golden set must load cleanly so the CLI never fails
    silently on a fresh checkout."""
    rows = load_golden(GOLDEN_PATH_DEFAULT)
    assert len(rows) >= 50
    # Every entry has the four fields the runner relies on.
    for r in rows:
        assert "id" in r and "category" in r
        assert "prompt" in r and "expected_intent" in r


def test_run_eval_smoke_writes_report(tmp_path: Path):
    golden = tmp_path / "golden.jsonl"
    _write_jsonl(golden, [_golden_row(i) for i in range(5)])

    report = run_eval(
        golden_path=golden,
        base_model="base/test",
        adapter_path=None,
        smoke=True,
    )
    assert isinstance(report, EvalReport)
    assert report.total_prompts == 5
    # Smoke responder echoes the prompt — every prompt should trip
    # the intent match heuristic because expected_intent reuses words
    # from the prompt vocabulary.
    assert report.intent_match_count >= 1
    assert report.safety_violations_count == 0
    md = render_markdown(report)
    assert "DPO Eval" in md
    assert "Total prompts" in md
