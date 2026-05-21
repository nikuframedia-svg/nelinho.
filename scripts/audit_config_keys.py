"""Q.67.3.C — Config keys audit.

Static analysis of every ``(category, key)`` pair seeded by
``src/core/services/default_configs.py`` against the source tree to
classify each key as USED / UNUSED / RUNTIME-ONLY.

Methodology
-----------
For each seed key we search:

* The full key literal ``"category.key"`` (e.g. ``"cpo.pop_size"``) — the
  shape used by ``tenant_config_map`` lookups (raw.get("cpo.pop_size"))
  and most JS/TS consumers.
* The bare key literal ``"key"`` (e.g. ``"cpo.pop_size"`` already
  contains dots, but for keys without dots like ``"language"`` this is
  the typical fingerprint). For keys without dots we also require the
  category to appear in the same file to reduce false positives.
* Common Python lookup patterns:
  ``get_config("category", "key")``,
  ``get("category", "key")``.

Each key is classified:

* **USED** — at least one direct call-site or string-literal hit in
  ``src/`` (excluding ``default_configs.py`` and the YAML source-of-truth
  ``config/yaml/system_defaults.yaml``) **or** in ``frontend/src/``.
* **RUNTIME-ONLY** — the key has zero static hits but the category has
  hits elsewhere. The category is dynamically iterated (e.g. via
  ``service.get_category(...)``), so the key is reachable at runtime even
  if no literal exists. Confidence is LOW; do **not** delete.
* **UNUSED** — zero static hits and the *category* itself has no
  dynamic iterators (or the key is the only one in the category).
  These are the deletion candidates.

Confidence (1 = low, 3 = high) is the count of distinct call-sites
matched. RUNTIME-ONLY rows are always confidence 1.

Output
------
Writes ``agent_docs/config_keys_audit.md`` with a markdown matrix plus
two summary sections (UNUSED candidates and RUNTIME-ONLY cautions).

Run
---
``python scripts/audit_config_keys.py``

This script does **not** mutate any source — it only reads + writes the
audit markdown.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
FRONTEND_DIR = ROOT / "frontend" / "src"
DEFAULT_CONFIGS_PY = SRC_DIR / "core" / "services" / "default_configs.py"
YAML_DEFAULTS = ROOT / "config" / "yaml" / "system_defaults.yaml"
OUT_PATH = ROOT / "agent_docs" / "config_keys_audit.md"

# Excluded from the search corpus: the seeds file itself + the YAML
# source-of-truth (both are definitions, not consumers).
EXCLUDED_FILES = {DEFAULT_CONFIGS_PY.resolve(), YAML_DEFAULTS.resolve()}

# File extensions worth scanning.
SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".yaml", ".yml"}


# ---------------------------------------------------------------------------
# Seed extraction (read-only — never edit default_configs.py)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeedEntry:
    category: str
    key: str
    default: str
    data_type: str

    @property
    def full_key(self) -> str:
        return f"{self.category}.{self.key}"


_TUPLE_RE = re.compile(
    r"""\(\s*
        ["'](?P<category>[a-z_][a-z0-9_]*)["']\s*,\s*
        ["'](?P<key>[A-Za-z0-9_.]+)["']\s*,\s*
        (?P<value>.+?)\s*,\s*
        ["'](?P<dtype>[a-z_]+)["']\s*,
    """,
    re.VERBOSE | re.DOTALL,
)


def load_seeds() -> list[SeedEntry]:
    """Parse DEFAULT_SEEDS without importing the module.

    Importing default_configs.py would drag in SQLAlchemy + governance,
    so we do a tolerant regex parse over the file text.
    """
    text = DEFAULT_CONFIGS_PY.read_text(encoding="utf-8")
    seeds: list[SeedEntry] = []
    seen: set[tuple[str, str]] = set()
    for match in _TUPLE_RE.finditer(text):
        cat = match["category"]
        key = match["key"]
        if (cat, key) in seen:
            continue
        seen.add((cat, key))
        default = match["value"].strip()
        # Shorten obviously long defaults for the markdown table.
        if len(default) > 40:
            default = default[:37] + "..."
        seeds.append(SeedEntry(category=cat, key=key, default=default, data_type=match["dtype"]))
    return seeds


# ---------------------------------------------------------------------------
# Source corpus
# ---------------------------------------------------------------------------


def iter_source_files() -> Iterable[Path]:
    for base in (SRC_DIR, FRONTEND_DIR):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in SOURCE_EXTS:
                continue
            if path.resolve() in EXCLUDED_FILES:
                continue
            # Skip generated / vendored / cache directories.
            parts = set(path.parts)
            if parts & {"__pycache__", "node_modules", "dist", "build", ".venv"}:
                continue
            yield path


def load_corpus() -> dict[Path, str]:
    corpus: dict[Path, str] = {}
    for path in iter_source_files():
        try:
            corpus[path] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return corpus


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


@dataclass
class KeyMatch:
    path: Path
    line_no: int
    snippet: str


def _find_literal(text: str, needle: str) -> list[int]:
    """Return 1-based line numbers where ``needle`` appears."""
    if needle not in text:
        return []
    lines: list[int] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            lines.append(idx)
    return lines


def search_key(seed: SeedEntry, corpus: dict[Path, str]) -> list[KeyMatch]:
    """Find every occurrence of this key's literals across the corpus."""
    # Two main fingerprints we accept:
    #  1. Full key as a string literal (with surrounding quotes) — most
    #     specific.
    #  2. Bare key (with surrounding quotes) — catches
    #     ``get_config("category", "key")`` and JSON-like maps.
    full_with_quotes_dq = f'"{seed.full_key}"'
    full_with_quotes_sq = f"'{seed.full_key}'"
    bare_dq = f'"{seed.key}"'
    bare_sq = f"'{seed.key}'"

    matches: list[KeyMatch] = []
    for path, text in corpus.items():
        # 1. Full key
        for line_no in _find_literal(text, full_with_quotes_dq):
            matches.append(KeyMatch(path, line_no, full_with_quotes_dq))
        for line_no in _find_literal(text, full_with_quotes_sq):
            matches.append(KeyMatch(path, line_no, full_with_quotes_sq))

        # 2. Bare key — only consider if (a) the key has at least one
        # dot (= specific enough) OR (b) the category also appears in
        # this file (= reduces false positives for short keys like
        # "theme" or "language").
        has_dot = "." in seed.key
        category_in_file = (
            f'"{seed.category}"' in text or f"'{seed.category}'" in text
        )
        if has_dot or category_in_file:
            for line_no in _find_literal(text, bare_dq):
                # Skip if we already counted this exact line via the
                # full-key form.
                if any(m.path == path and m.line_no == line_no for m in matches):
                    continue
                matches.append(KeyMatch(path, line_no, bare_dq))
            for line_no in _find_literal(text, bare_sq):
                if any(m.path == path and m.line_no == line_no for m in matches):
                    continue
                matches.append(KeyMatch(path, line_no, bare_sq))

    return matches


def category_has_dynamic_iteration(category: str, corpus: dict[Path, str]) -> bool:
    """Detect dynamic readers of an entire category.

    Patterns we recognise as evidence that *every* key in the category
    is consumed at runtime:

    * ``get_category("category")`` / ``get_category('category')``
    * ``load_<category>_tenant_config``
    """
    needles = (
        f'get_category("{category}")',
        f"get_category('{category}')",
    )
    for text in corpus.values():
        for needle in needles:
            if needle in text:
                return True
    return False


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class Verdict:
    seed: SeedEntry
    matches: list[KeyMatch]
    status: str  # USED / UNUSED / RUNTIME-ONLY
    confidence: int  # 1..3


def classify(seeds: list[SeedEntry], corpus: dict[Path, str]) -> list[Verdict]:
    # Pre-compute which categories have a dynamic-iteration consumer.
    dynamic_categories: set[str] = set()
    for cat in {s.category for s in seeds}:
        if category_has_dynamic_iteration(cat, corpus):
            dynamic_categories.add(cat)

    verdicts: list[Verdict] = []
    for seed in seeds:
        matches = search_key(seed, corpus)
        distinct_sites = len({(m.path, m.line_no) for m in matches})
        if distinct_sites >= 1:
            status = "USED"
            confidence = min(3, distinct_sites)
        elif seed.category in dynamic_categories:
            status = "RUNTIME-ONLY"
            confidence = 1
        else:
            status = "UNUSED"
            confidence = 3
        verdicts.append(
            Verdict(
                seed=seed,
                matches=matches,
                status=status,
                confidence=confidence,
            )
        )
    return verdicts


def _format_call_sites(verdict: Verdict, max_sites: int = 3) -> str:
    if not verdict.matches:
        if verdict.status == "RUNTIME-ONLY":
            return "(only via get_category)"
        return "(none)"
    distinct: list[KeyMatch] = []
    seen: set[tuple[Path, int]] = set()
    for m in verdict.matches:
        key = (m.path, m.line_no)
        if key in seen:
            continue
        seen.add(key)
        distinct.append(m)
        if len(distinct) >= max_sites:
            break
    parts: list[str] = []
    for m in distinct:
        rel = m.path.relative_to(ROOT).as_posix()
        parts.append(f"`{rel}:{m.line_no}`")
    extra = len({(m.path, m.line_no) for m in verdict.matches}) - len(distinct)
    if extra > 0:
        parts.append(f"(+{extra} more)")
    return ", ".join(parts)


def render_report(verdicts: list[Verdict]) -> str:
    total = len(verdicts)
    used = sum(1 for v in verdicts if v.status == "USED")
    unused = sum(1 for v in verdicts if v.status == "UNUSED")
    runtime_only = sum(1 for v in verdicts if v.status == "RUNTIME-ONLY")

    lines: list[str] = []
    lines.append("# Config keys audit — Q.67.3.C")
    lines.append("")
    lines.append(
        "Generated by `scripts/audit_config_keys.py`. Re-run any time "
        "`src/core/services/default_configs.py` changes."
    )
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        f"- **Source:** `src/core/services/default_configs.py` "
        f"({total} keys seeded)"
    )
    lines.append(
        "- **Static analysis:** grep call-sites in `src/` + "
        "`frontend/src/` for full-key literals (`\"category.key\"`) and "
        "bare-key literals (when the category also appears in the file)."
    )
    lines.append(
        "- **Dynamic awareness:** categories consumed via "
        "`get_category(\"<cat>\")` are flagged so individual keys that "
        "lack a static hit are marked **RUNTIME-ONLY**, not UNUSED."
    )
    lines.append("- **Classification:** USED / UNUSED / RUNTIME-ONLY.")
    lines.append(
        "- **Confidence (1–3):** distinct call-sites for USED rows; "
        "RUNTIME-ONLY is always 1 (LOW — keep, do **not** delete)."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total keys seeded: **{total}**")
    lines.append(f"- USED: **{used}**")
    lines.append(f"- UNUSED: **{unused}**")
    lines.append(f"- RUNTIME-ONLY: **{runtime_only}**")
    lines.append("")
    lines.append("## Matrix")
    lines.append("")
    lines.append("| Full key | Category | Default | Status | Call-sites | Confidence |")
    lines.append("|----------|----------|---------|--------|-----------|-----------|")

    # Stable ordering: status priority (UNUSED first, then RUNTIME-ONLY,
    # then USED), then category, then key, so reviewers see deletion
    # candidates at the top.
    status_order = {"UNUSED": 0, "RUNTIME-ONLY": 1, "USED": 2}
    for v in sorted(
        verdicts,
        key=lambda x: (status_order[x.status], x.seed.category, x.seed.key),
    ):
        seed = v.seed
        default = seed.default.replace("|", "\\|")
        if len(default) > 35:
            default = default[:32] + "..."
        call_sites = _format_call_sites(v).replace("|", "\\|")
        lines.append(
            f"| `{seed.full_key}` | `{seed.category}` | `{default}` | "
            f"**{v.status}** | {call_sites} | {v.confidence} |"
        )

    # UNUSED list
    unused_rows = [v for v in verdicts if v.status == "UNUSED"]
    lines.append("")
    lines.append("## UNUSED candidates for deletion (Q.68.X)")
    lines.append("")
    if not unused_rows:
        lines.append("_None — every seeded key has at least one consumer._")
    else:
        lines.append(
            "These keys have zero static hits in `src/` or `frontend/src/` "
            "and their category has no dynamic-iteration consumer. Safe to "
            "consider for removal in a follow-up sprint after a human "
            "sanity check."
        )
        lines.append("")
        for v in sorted(unused_rows, key=lambda x: (x.seed.category, x.seed.key)):
            lines.append(f"- `{v.seed.full_key}` (default `{v.seed.default}`)")

    # RUNTIME-ONLY list
    runtime_rows = [v for v in verdicts if v.status == "RUNTIME-ONLY"]
    lines.append("")
    lines.append("## RUNTIME-ONLY (NÃO apagar)")
    lines.append("")
    if not runtime_rows:
        lines.append("_None._")
    else:
        lines.append(
            "Categories below are iterated dynamically via "
            "`service.get_category(...)`. Even with zero literal hits, "
            "each key is read at runtime as part of the whole category. "
            "**Do not delete** without inspecting the consumer."
        )
        lines.append("")
        runtime_by_cat: dict[str, list[Verdict]] = {}
        for v in runtime_rows:
            runtime_by_cat.setdefault(v.seed.category, []).append(v)
        for cat in sorted(runtime_by_cat):
            keys = ", ".join(
                f"`{x.seed.key}`"
                for x in sorted(runtime_by_cat[cat], key=lambda x: x.seed.key)
            )
            lines.append(f"- `{cat}.*` (consumed via `get_category(\"{cat}\")`): {keys}")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    if not DEFAULT_CONFIGS_PY.exists():
        print(f"ERROR: cannot find {DEFAULT_CONFIGS_PY}", file=sys.stderr)
        return 1

    print(f"[audit] loading seeds from {DEFAULT_CONFIGS_PY.relative_to(ROOT)}")
    seeds = load_seeds()
    print(f"[audit] {len(seeds)} seed keys parsed")

    print("[audit] loading source corpus (src/ + frontend/src/)")
    corpus = load_corpus()
    print(f"[audit] {len(corpus)} files in corpus")

    print("[audit] classifying keys")
    verdicts = classify(seeds, corpus)

    used = sum(1 for v in verdicts if v.status == "USED")
    unused = sum(1 for v in verdicts if v.status == "UNUSED")
    runtime_only = sum(1 for v in verdicts if v.status == "RUNTIME-ONLY")
    print(
        f"[audit] verdict: USED={used}  UNUSED={unused}  RUNTIME-ONLY={runtime_only}"
    )

    report = render_report(verdicts)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(report, encoding="utf-8")
    print(f"[audit] wrote {OUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
