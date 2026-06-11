"""Q.173.AJ — gates anti-regressao para o runner setup_marts_all.py.

Testes estaticos (sem BD): verificam que:
1. O runner existe e e importavel.
2. O runner descobre pelo menos N scripts.
3. Todos os sql_table dos cube YMLs sao conhecidos pelo runner
   (i.e. existe um setup_marts_*.py para cada view marts.*).
4. As medidas removidas NAO existem no MEASURE_REGISTRY.
5. A dimensao erp_of_id existe no MEASURE_REGISTRY (nao work_order_id).

Nenhum acesso a BD.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).parent.parent.parent
SCRIPTS_DIR = REPO / "scripts"
CUBE_MODEL_DIR = REPO / "cube" / "model"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _load_runner():
    p = SCRIPTS_DIR / "setup_marts_all.py"
    spec = importlib.util.spec_from_file_location("setup_marts_all", p)
    assert spec and spec.loader, "setup_marts_all.py nao encontrado"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def _all_sql_tables() -> set[str]:
    """Extrai todos os sql_table dos cube YMLs."""
    tables: set[str] = set()
    for yml in CUBE_MODEL_DIR.glob("*.yml"):
        doc = yaml.safe_load(yml.read_text(encoding="utf-8"))
        for cube in (doc or {}).get("cubes", []):
            t = cube.get("sql_table", "")
            if t:
                tables.add(t.strip())
    return tables


def _marts_view_name(sql_table: str) -> str | None:
    """Extrai o nome da view de 'marts.v_xxx' ou None se nao for marts."""
    if sql_table.startswith("marts."):
        return sql_table.split(".", 1)[1]
    return None


def _script_for_view(view_name: str) -> Path | None:
    """Procura setup_marts_<sufixo>.py que gere a view dada."""
    # convencao: setup_marts_<nome_sem_v__e_sem_sufixo>.py
    # e.g. marts.v_facturacao_mes -> setup_marts_facturacao_mes.py
    candidate = SCRIPTS_DIR / f"setup_marts_{view_name.removeprefix('v_')}.py"
    if candidate.exists():
        return candidate
    # fallback: procura por view_name no conteudo dos scripts
    for p in SCRIPTS_DIR.glob("setup_marts_*.py"):
        if view_name in p.read_text(encoding="utf-8"):
            return p
    return None


# ---------------------------------------------------------------------------
# testes
# ---------------------------------------------------------------------------

class TestRunnerExists:
    def test_runner_file_exists(self):
        assert (SCRIPTS_DIR / "setup_marts_all.py").exists()

    def test_runner_importavel(self):
        mod = _load_runner()
        assert hasattr(mod, "main"), "setup_marts_all.main nao encontrado"
        assert hasattr(mod, "_discover_scripts"), "setup_marts_all._discover_scripts nao encontrado"

    def test_runner_descobre_pelo_menos_40_scripts(self):
        mod = _load_runner()
        scripts = mod._discover_scripts()
        assert len(scripts) >= 40, f"runner so descobre {len(scripts)} scripts (esperado >= 40)"

    def test_runner_nao_inclui_a_si_proprio(self):
        mod = _load_runner()
        scripts = mod._discover_scripts()
        names = [s.name for s in scripts]
        assert "setup_marts_all.py" not in names


class TestCubeYmlCoverage:
    def test_todos_sql_table_marts_tem_script(self):
        """Cada marts.v_* referenciado num cube YAML tem um setup_marts_*.py."""
        sql_tables = _all_sql_tables()
        missing: list[str] = []
        for t in sorted(sql_tables):
            view = _marts_view_name(t)
            if view is None:
                continue  # factory_raw.* ou outros — ok
            if _script_for_view(view) is None:
                missing.append(t)
        assert not missing, (
            "Cubes referenciam views marts sem script de setup:\n"
            + "\n".join(f"  {t}" for t in missing)
        )

    def test_factory_raw_moldes_nao_precisa_script(self):
        """factory_raw.moldes e uma tabela real, nao uma view marts."""
        tables = _all_sql_tables()
        assert "factory_raw.moldes" in tables  # confirmacao que o cube existe


class TestMeasureRegistry:
    def _load_registry(self):
        sys.path.insert(0, str(REPO))
        from src.copilot.cube.measure_contract import MEASURE_REGISTRY
        return MEASURE_REGISTRY

    def test_medidas_removidas_ausentes(self):
        reg = self._load_registry()
        removed = [
            "ambiental_cura_compliance.taxa",
            "ambiental_cura_compliance.total",
            "ambiental_cura_compliance.compliant",
            "ambiental_cura_horas.ciclos",
            "ambiental_cura_horas.total",
            "ambiental_estufa_temp.temp_max",
            "ambiental_estufa_temp.temp_avg",
            "ambiental_estufa_humidade.avg",
            "ambiental_iot_alarmes.total",
            "comercial_facturacao_agente.total",
            "logistica_docs.emitidos_total",
            "logistica_docs.pendentes_total",
            "operadores_horas.horas_total",
            "operadores_horas.n_apontamentos",
            "operadores_horas.n_ofs_distintas",
            "plataforma_copilot_latency.requests",
            "plataforma_copilot_latency.abstain",
            "plataforma_copilot_latency.errors",
            "plataforma_copilot_latency.latency_avg",
            "plataforma_copilot_latency.latency_p50",
            "plataforma_copilot_latency.latency_p95",
            "plataforma_copilot_latency.latency_p99",
            "plataforma_copilot_rag.hit_rate",
            "plataforma_copilot_rag.chunks_avg",
            "plataforma_copilot_rag.citations_avg",
            "plataforma_copilot_rag.requests",
            "plataforma_copilot_feedback.taxa_positivo",
            "plataforma_copilot_feedback.total",
            "plataforma_copilot_feedback.rating_avg",
        ]
        present = [k for k in removed if k in reg]
        assert not present, (
            "Medidas deviam ter sido removidas mas ainda existem:\n"
            + "\n".join(f"  {k}" for k in present)
        )

    def test_erp_of_id_presente_em_consumo_by_of(self):
        reg = self._load_registry()
        assert "consumo_by_of.custo_eur" in reg
        dims = reg["consumo_by_of.custo_eur"].dimensions_supported
        assert "erp_of_id" in dims, "erp_of_id deve estar em dimensions_supported"
        assert "work_order_id" not in dims, "work_order_id (legacy) nao deve estar"

    def test_canonical_dimensions_sem_work_order_id(self):
        sys.path.insert(0, str(REPO))
        from src.copilot.cube.measure_contract import CANONICAL_DIMENSIONS
        assert "work_order_id" not in CANONICAL_DIMENSIONS, (
            "work_order_id (legacy UUID) nao deve estar em CANONICAL_DIMENSIONS"
        )
