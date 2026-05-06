"""Q.17.A — one-off generator that writes config/yaml/system_defaults.yaml
from the legacy default_configs.DEFAULT_SEEDS list.

Run once to bootstrap the YAML file. After that, edit the YAML directly;
this script is kept for re-generation if ever needed (e.g. backporting
runtime patches into the canonical YAML).

Usage:
    python scripts/generate_system_defaults_yaml.py
"""

from __future__ import annotations

import sys
from collections import OrderedDict
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.core.services.default_configs import DEFAULT_SEEDS  # noqa: E402

OUTPUT = REPO_ROOT / "config" / "yaml" / "system_defaults.yaml"


# Force PyYAML to emit dicts in insertion order so categories appear in the
# same order as DEFAULT_SEEDS (matching default_configs.py grouping).
def _represent_ordereddict(dumper: yaml.SafeDumper, data: OrderedDict):
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())


yaml.SafeDumper.add_representer(OrderedDict, _represent_ordereddict)

# Description blurbs per category (extracted from DEFAULT_SEEDS comments).
CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "governance": "Write-gate, auto-approval flags, timeline anti-fatigue.",
    "trust": "Trust Index v2 weights and gating thresholds.",
    "planning": "CPO v4 scheduler — population, fitness weights, queue/buffer, MAP-Elites grid, surrogate.",
    "supply": "Stock/material reorder thresholds and approval gates.",
    "quality": "Quality risk thresholds + rework buffers per phase.",
    "mold": "Mould health weights and maintenance threshold.",
    "cost": "Throughput targets and default margin assumptions.",
    "copilot": "Conversational copilot rate limits and diagnostic capabilities.",
    "llm": "LLM backend selection and parameters.",
    "factory_map": "Factory-map snapshot caching + projection horizons.",
    "workforce": "Worker tier boundaries, shift defaults, skill recency window.",
    "routing": "Routing template + phase-uses-mold list + buffer factor.",
    "alertas": "Alert thresholds, severities, and recipient lists.",
    "learning_rules": "Confidence thresholds for the rule detector + auto-revert window.",
    "learning": "Heavy learning pipeline flags (DPO fine-tune, PCMCI+ discovery).",
    "system": "UI language/theme/format, audit retention, sliding rate limits.",
    "rbac": "Default role + approval-required role + per-surface allowed roles.",
    "transporte": "Truck capacity, modal load, regroup-by-client, completion fill ratio.",
    "notifications": "Channel master switches + quiet hours + batch coalescing.",
    "reports": "Daily/weekly digest cadence and export format.",
    "tablet": "Operator-tablet refresh rate, font scale, kiosk mode, offline buffer.",
    "sandbox": "Scenario simulation budgets + retention.",
    "twin": "Digital-twin scenario horizon and comparison cap.",
    "ml": "Retrain cadence, holdout fraction, promotion threshold.",
    "kpi_targets": "OTD/FPY/rework targets shown on the CEO dashboard.",
    "dqa": "Drift alert + freshness threshold + auto-repair toggle.",
    "realtime": "SSE heartbeat + Kafka toggle + outbox flush batching.",
    "session": "Session timeout + step-up + remember-me lifetime.",
    "dispatch": "Despacho policy — advance/delay tolerance + client priority.",
    "explain": "Catalog cache + causal trace depth + fallback toggle.",
    "improve": "Suggestion cooldown, auto-dismiss horizon, min confidence.",
}


def main() -> int:
    # Group DEFAULT_SEEDS by category, preserving original order.
    by_category: OrderedDict[str, list[dict]] = OrderedDict()
    for category, key, value, data_type, description in DEFAULT_SEEDS:
        if category not in by_category:
            by_category[category] = []
        entry: dict = OrderedDict()
        entry["key"] = key
        entry["value"] = value
        entry["data_type"] = data_type
        entry["description"] = description
        by_category[category].append(entry)

    categories: OrderedDict[str, dict] = OrderedDict()
    for category, settings in by_category.items():
        cat_block: OrderedDict = OrderedDict()
        cat_block["description"] = CATEGORY_DESCRIPTIONS.get(category, "")
        cat_block["settings"] = settings
        categories[category] = cat_block

    document: OrderedDict = OrderedDict()
    document["version"] = 1
    document["schema_name"] = "system_defaults.v1"
    document["categories"] = categories

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    header = (
        "# ProdPlan ONE — system_defaults.yaml\n"
        "# Sprint Q.17.A foundation. Generated from src/core/services/default_configs.py.\n"
        "# Edit this file directly going forward; default_configs.iter_seeds() reads it.\n"
        "#\n"
        f"# Total settings: {sum(len(v) for v in by_category.values())}\n"
        f"# Categories: {len(by_category)}\n"
        "#\n"
    )
    body = yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        indent=2,
        width=100,
    )

    OUTPUT.write_text(header + body, encoding="utf-8")
    total = sum(len(v) for v in by_category.values())
    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)}: {len(by_category)} categories, {total} settings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
