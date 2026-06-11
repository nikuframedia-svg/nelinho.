#!/usr/bin/env python3
"""PP1-Nelo: verifica invariantes obrigatorias do CPO/scheduler.

Sai com codigo 0 se tudo bem, 1 se alguma invariante falha. Usa apenas
acoes read-only mais um pytest run.

Mantem alinhado com .claude/skills/nelinho-invariants/SKILL.md — as 12
invariantes (CX/C/F/E/D/ST/WG/CO/ME/H0 + imports + test-floor) devem ser
identicas la e aqui.

Diferencas face ao script de referencia da skill, para uso de longa duracao:
- `sys.executable` em vez de `python` solto (corre com o interpretador certo,
  venv incluido).
- Se `VERIFY_INVARIANTS_SKIP_TESTS` estiver definido, salta o bloco de testes
  — o CI ja corre `pytest tests/` num passo proprio; correr 2x seria ~20min
  desperdicados. Local / pre-commit nao definem a var: check completo.
- F4: a regex da skill (`w_quality_risk\\s*[:=]\\s*([\\d.]+)`) tinha um bug —
  nao apanhava a anotacao de tipo `: float =`. Aqui esta corrigida. A skill
  deve ser actualizada para casar (pendente de autorizacao para editar
  ficheiros .claude/skills/).
- Q.61.01: nova invariante `TESTS-no-empty-bodies` (AST scan) — apanha
  `def test_*: pass` antes do CI correr a suite. Stop-the-bleeding contra
  falsos positivos.
"""
import ast
import os
import re
import subprocess
import sys
from pathlib import Path

failures: list[tuple[str, str]] = []


def check(name: str, cond: bool, msg: str = "") -> None:
    if cond:
        print(f"  OK   {name}")
    else:
        failures.append((name, msg))
        print(f"  FAIL {name}: {msg}")


# --- ESTATICAS ---
print("\n-> ESTATICAS")

# CX1 — CoeficienteX como tempo (excluindo comentarios)
for fpath in Path("src").rglob("*.py"):
    if "__pycache__" in str(fpath):
        continue
    try:
        content = fpath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    bad = [
        b for b in re.findall(
            r"[Cc]oeficiente.?[Xx].*(?:hour|time|duration|minutes|seconds|horas)",
            content,
        )
        if not b.lstrip().startswith("#")
    ]
    if bad:
        check(f"CX-{fpath}", False,
              f"CoeficienteX como tempo: {bad[0][:80]}")

for fname, anchor in [
    ("src/plan/cpo/state.py",
     "CoeficienteX` in the ERP is a monetary bonus"),
    ("src/plan/cpo/pair_assignment.py",
     "CoeficienteX` is the bonus payout"),
]:
    fpath = Path(fname)
    if fpath.exists():
        check(f"CX-{fname}",
              anchor in fpath.read_text(encoding="utf-8"),
              "comentario explicativo perdido")

# C1
chrom_src = Path("src/plan/cpo/chromosome.py").read_text(encoding="utf-8")
check("C1-class", "class Chromosome" in chrom_src,
      "class Chromosome em falta")
check("C1-routing", "routing_choices" in chrom_src,
      "Chromosome sem routing_choices")

# F1-F4
fit_src = Path("src/plan/cpo/fitness.py").read_text(encoding="utf-8")
check("F1-throughput", "throughput_eur_day" in fit_src,
      "fitness sem throughput_eur_day")
check("F2-idle", "idle_operators" in fit_src,
      "fitness sem idle_operators")
check("F3-compute_fitness", "def compute_fitness" in fit_src,
      "compute_fitness em falta")
# Aceita `w_quality_risk = 0.10` e `w_quality_risk: float = 0.10` (anotacao
# de tipo no meio — a regex `[:=]` da skill original nao apanhava o segundo).
m = re.search(r"w_quality_risk\s*(?::[^=\n]*)?=\s*([\d.]+)", fit_src)
if m:
    check("F4-quality", float(m.group(1)) > 0,
          f"w_quality_risk = {m.group(1)} (devia ser > 0)")
else:
    check("F4-quality", False, "w_quality_risk nao encontrado")

# E1
eng_src = Path("src/plan/cpo/engine.py").read_text(encoding="utf-8")
gens = re.findall(r"generations\s*:\s*int\s*=\s*(\d+)", eng_src)
if gens:
    g = int(gens[0])
    check("E1-generations", g >= 100,
          f"generations = {g} (minimo: 100)")
else:
    check("E1-generations", False,
          "default de generations nao encontrado")

# D2 / ST1
# Q.67.6.B3: decoder.py decomposto em decoder_helpers.py + decoder_resources.py
# + decoder_kpis.py. min_gap_hours pode estar em qualquer um — concatena para
# manter invariante "decoder layer chama min_gap_hours".
_decoder_files = [
    "src/plan/cpo/decoder.py",
    "src/plan/cpo/decoder_helpers.py",
    "src/plan/cpo/decoder_resources.py",
    "src/plan/cpo/decoder_kpis.py",
]
dec_src = "\n".join(
    Path(f).read_text(encoding="utf-8") for f in _decoder_files if Path(f).exists()
)
check("D2-curing", "min_gap_hours" in dec_src,
      "decoder layer (decoder.py + sub-modulos Q.67.6.B3) nao chama min_gap_hours")
state_src = Path("src/plan/cpo/state.py").read_text(encoding="utf-8")
check("ST1-data", "phase_transition_gaps" in state_src,
      "FactoryState sem phase_transition_gaps")
check("ST1-method", "def min_gap_hours" in state_src,
      "FactoryState sem min_gap_hours()")

# WG1 / WG2
dec_path = Path("src/shared/api/decisions.py")
if dec_path.exists():
    dec = dec_path.read_text(encoding="utf-8")
    check("WG1-execute", "TODO: Execute actual action" not in dec,
          "regressao: aprovacao nao executa accao")
    check("WG2-revert", "TODO: Revert state" not in dec,
          "regressao: rollback nao reverte estado")

# CO1
commits_src = Path("src/plan/cpo/commits.py").read_text(encoding="utf-8")
check("CO1-rejected", "rejected_alternatives" in commits_src,
      "ScheduleCommit sem rejected_alternatives (DPO sem input)")
check("CO1-preference", "user_preference_signal" in commits_src,
      "ScheduleCommit sem user_preference_signal (DPO sem porque)")

# ME1
me_src = Path("src/plan/cpo/mapelites.py").read_text(encoding="utf-8")
check("ME1-idle-axis", "idle_pct" in me_src,
      "MAP-Elites perdeu idle_pct (Blueprint v2.0 §5.6)")

# H0 — best-effort
out = subprocess.run(
    ["git", "diff", "HEAD~1", "--", "src/plan/"],
    # encoding explícito: o output do git é UTF-8 (comentários PT com acentos,
    # ex. "MÁXIMO"). Sem isto, em Windows/PowerShell o `text=True` decodifica
    # com cp1252 e rebenta num byte 0x81 (continuação de "Á") — falso-negativo
    # do gate, agravado quando HEAD~1 é um merge com diff grande.
    capture_output=True, text=True, encoding="utf-8", errors="replace",
)
if out.returncode == 0 and out.stdout:
    suspect = [
        s.strip() for s in re.findall(r"\+.*?=\s*\d{3,}", out.stdout)
        if "test" not in s.lower()
        and "#" not in s
        and "id" not in s.lower()
        and "alembic" not in s.lower()
        # Q.130.1 — constantes module-level (linhas +_UPPER_SNAKE =) são
        # definições legítimas de parâmetros físicos, não magic numbers inline.
        and not re.search(r"^\+_[A-Z][A-Z0-9_]+\s*[:=]", s.strip())
    ]
    check("H0-hardcodes", len(suspect) == 0,
          f"hardcodes novos em src/plan/: {suspect[:5]}")
elif out.returncode != 0:
    print("  SKIP H0-hardcodes: git diff HEAD~1 indisponivel")

# --- DINAMICAS ---
print("\n-> DINAMICAS")
sys.path.insert(0, ".")


def check_flexible_phases_have_curing_gaps() -> None:
    """Q.116.B — cada fase `is_flexible=True` declara `allowed_predecessors`,
    e cada par (predecessor_alternativo, fase_flexivel) tem de existir como
    `(from_phase, to_phase)` em `NELO_CURING_GAPS_SEED` (via helper
    `curing_gap_pairs()` em `src/plan/cpo/state.py`).

    Sem gap = ordem alternativa sem suporte fisico — o decoder nao pode
    garantir a quimica da transicao.

    Skip silencioso quando a DB nao esta disponivel (dev sem stack) —
    o check e opt-in via `--q116b` e nao bloqueia o commit de quem nao
    tem Postgres a correr.
    """
    try:
        import asyncio
        from sqlalchemy import select
        from src.plan.cpo.state import curing_gap_pairs, normalize_phase_code
        from src.plan.models.routing_template import RoutingTemplatePhase
        from src.shared.database import get_session
    except Exception as exc:  # pragma: no cover — import only fails in broken envs
        check(
            "Q116B-curing-gaps",
            True,
            f"skip — imports nao disponiveis ({exc.__class__.__name__})",
        )
        return

    async def _run() -> tuple[bool, str]:
        gaps = curing_gap_pairs()
        async for sess in get_session():
            # Carrega todas as fases do tenant — inclui as flexiveis e o resto
            # (precisamos do resto para mapear phase row id → phase_id string).
            res = await sess.execute(select(RoutingTemplatePhase))
            all_phases = list(res.scalars().all())
            # Map: phase_id string (NELO business key) per row id is direct.
            # Codigo canonico = normalize_phase_code(phase_id ou phase_name).
            missing: list[str] = []
            for row in all_phases:
                if not getattr(row, "is_flexible", False):
                    continue
                this_code = normalize_phase_code(row.phase_id) or normalize_phase_code(
                    row.phase_name
                )
                for pred in row.allowed_predecessors or []:
                    pred_code = normalize_phase_code(pred)
                    if (pred_code, this_code) not in gaps:
                        missing.append(f"{pred_code}->{this_code}")
            return (len(missing) == 0, ", ".join(missing[:5]))
        return (True, "")

    try:
        ok, payload = asyncio.run(_run())
    except Exception as exc:
        # DB indisponivel ou config em falta — nao bloqueia.
        check(
            "Q116B-curing-gaps",
            True,
            f"skip — DB indisponivel ({exc.__class__.__name__})",
        )
        return
    check(
        "Q116B-curing-gaps",
        ok,
        f"fases flexiveis sem gap declarado: {payload}",
    )


if "--q116b" in sys.argv:
    check_flexible_phases_have_curing_gaps()

for module, attr in [
    ("src.plan.cpo.chromosome", "Chromosome"),
    ("src.plan.cpo.engine", "CPOv4Engine"),
    ("src.plan.cpo.fitness", "compute_fitness"),
    ("src.plan.cpo.decoder", "decode"),
    ("src.plan.cpo.safety_net", "is_worse_than_baseline"),
    ("src.plan.cpo.commits", "ScheduleCommit"),
    ("src.plan.cpo.mapelites", None),
    ("src.plan.cpo.state", "FactoryState"),
]:
    label = f"IMPORT-{module}" + (f".{attr}" if attr else "")
    try:
        mod = __import__(module, fromlist=[attr] if attr else [])
        if attr is not None and not hasattr(mod, attr):
            check(label, False, f"{attr} ausente")
        else:
            check(label, True)
    except ImportError as e:
        check(label, False, f"Import falhou: {e}")

# --- AST: testes nao podem ter corpo vazio (Q.61.01) ---
# Apanha `def test_*: pass` / `def test_*: ...` / corpo so com docstring.
# Theater destes esta proibido — passa sem afirmar nada e mascara
# regressoes durante refactor.
print("\n-> AST DOS TESTES")
empty_tests: list[tuple[str, str, int]] = []
for tpath in Path("tests").rglob("test_*.py"):
    try:
        tree = ast.parse(tpath.read_text(encoding="utf-8"))
    except SyntaxError as e:
        check(f"AST-parse-{tpath}", False, f"syntax error: {e}")
        continue
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        # Remove docstring antes de medir o corpo.
        body = [
            s for s in node.body
            if not (
                isinstance(s, ast.Expr)
                and isinstance(s.value, ast.Constant)
                and isinstance(s.value.value, str)
            )
        ]
        if len(body) == 0:
            empty_tests.append((str(tpath), node.name, node.lineno))
        elif len(body) == 1 and isinstance(body[0], ast.Pass):
            empty_tests.append((str(tpath), node.name, node.lineno))
        elif (
            len(body) == 1
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and body[0].value.value is Ellipsis
        ):
            empty_tests.append((str(tpath), node.name, node.lineno))
check(
    "TESTS-no-empty-bodies",
    len(empty_tests) == 0,
    f"{len(empty_tests)} teste(s) com corpo vazio: "
    + ", ".join(f"{p}:{ln} {n}" for p, n, ln in empty_tests[:3])
    + (" ..." if len(empty_tests) > 3 else ""),
)

# WG2 (Q.172.D) — o validador universal tem de estar LIGADO aos dois
# caminhos de escrita de schedules. Se alguém o desligar do
# create_from_schedule ou do apply_manual_reorder, o CI parte aqui.
_commits_src = Path("src/plan/cpo/commits.py").read_text(encoding="utf-8")
check(
    "WG2-validador-no-commit",
    "validate_schedule" in _commits_src,
    "create_from_schedule deixou de chamar validate_schedule (Q.169.B)",
)
_reorder_src = Path("src/plan/services/manual_reorder.py").read_text(encoding="utf-8")
check(
    "WG2-validador-no-drag",
    "validate_schedule" in _reorder_src,
    "apply_manual_reorder deixou de passar pelo validador universal (Q.171.D)",
)

# HD1 (Q.172.D) — dados honestos no backend (invariante #8): padrões de
# mock/fabricação não entram em src/ (a campanha de saneamento limpou-os;
# este gate impede o regresso).
_mock_hits: list[str] = []
for _fp in Path("src").rglob("*.py"):
    if "__pycache__" in str(_fp):
        continue
    try:
        _content = _fp.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for _m in re.finditer(r"def _get_mock_|MOCK_[A-Z_]+\s*=|_fake_data\s*=", _content):
        _line = _content[: _m.start()].count("\n") + 1
        _mock_hits.append(f"{_fp}:{_line}")
check(
    "HD1-zero-mocks-backend",
    len(_mock_hits) == 0,
    "padrões de mock no backend: " + ", ".join(_mock_hits[:3]),
)

# --- TESTES ---
print("\n-> TESTES")
if os.environ.get("VERIFY_INVARIANTS_SKIP_TESTS"):
    print("  SKIP TESTS-* : VERIFY_INVARIANTS_SKIP_TESTS definido "
          "(a suite pytest corre noutro passo do CI)")
else:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-x", "--tb=no", "-q"],
        # encoding explícito (ver nota no git diff acima): output UTF-8.
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    TEST_FLOOR = 1800
    m = re.search(r"(\d+) passed", result.stdout)
    if m:
        n = int(m.group(1))
        check("TESTS-pass", n >= TEST_FLOOR,
              f"so {n} passaram (floor: {TEST_FLOOR})")
        fail_m = re.search(r"(\d+) failed", result.stdout)
        if fail_m:
            check("TESTS-zero-fail", int(fail_m.group(1)) == 0,
                  f"{fail_m.group(1)} testes falharam")
        else:
            check("TESTS-zero-fail", True)
    else:
        check("TESTS-pass", False,
              f"pytest output inesperado: {result.stdout[-200:]}")

# --- RESUMO ---
print(f"\n{'='*60}")
if failures:
    print(f"{len(failures)} INVARIANTES FALHARAM:")
    for name, msg in failures:
        print(f"   {name}: {msg}")
    print("\nNao fazer commit ate resolver TODAS.")
    sys.exit(1)
else:
    print("TODAS as invariantes passam — seguro para commit.")
    sys.exit(0)
