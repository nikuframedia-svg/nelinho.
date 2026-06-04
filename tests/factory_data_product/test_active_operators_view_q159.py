"""Q.159 — a DDL da view `factory_raw.v_active_operators` codifica a regra EXATA
de "operador ativo": `E_ACTIVO = true` E trabalho (`offp_eq` ⋈ `of_fp`) numa
operação iniciada nos últimos 2 meses (60 dias), com a guarda `NULLIF(...,'')`
(as datas no mirror são TEXT — um '' rebentaria o ::timestamp).

Trava a estrutura sem precisar de BD (a contagem ~107 é verificada ao vivo pelo
próprio script). Protege contra regressões silenciosas na regra.
"""

from __future__ import annotations

from scripts.q159_setup_active_operators_view import _VIEW_DDL


def test_view_uses_entidade_active_flag():
    assert '"E_ACTIVO" = true' in _VIEW_DDL, "só colaboradores ativos"


def test_view_joins_work_records():
    assert "factory_raw.offp_eq" in _VIEW_DDL, "quem trabalhou (offp_eq)"
    assert "factory_raw.of_fp" in _VIEW_DDL, "operação (of_fp) p/ a data"


def test_view_window_is_two_months():
    assert "interval '60 days'" in _VIEW_DDL, "janela de 2 meses (60 dias)"
    assert "now() - interval '60 days'" in _VIEW_DDL


def test_view_guards_empty_text_dates():
    # As datas são TEXT no mirror — sem NULLIF um '' rebenta o ::timestamp.
    assert "NULLIF(o.\"OFFP_DATAINICIO\", '')::timestamp" in _VIEW_DDL


def test_view_is_idempotent():
    assert _VIEW_DDL.strip().startswith("CREATE OR REPLACE VIEW")
