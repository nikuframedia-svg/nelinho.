"""Q.158 — Property tests para a truncagem de rota com base no histórico real.

Três invariantes Spelke para o RoutingResolver._truncate_route_to_current:

* **P1 — Fase concluída nunca entra no plano:**
  Qualquer fase cuja `fase_id` esteja em `completed_fase_ids`
  (= `OFFP_DATAFIM IS NOT NULL`) NÃO deve aparecer nas operações geradas.

* **P2 — Fase atual fora da rota NÃO re-planeia a rota inteira:**
  Se `current_fase_id` não está na rota, a função deve devolver apenas as
  fases por fazer (= não concluídas), nunca a rota completa com fases
  já terminadas incluídas.

* **P3 — Ordem das operações de um barco segue SEMPRE a sequência da rota
  (campo `sequence`), nunca colunas temporais (`OFFP_SEQUENCIA`/
  `OFFP_DATAINICIO`):**
  Para qualquer rota com `sequence` definido, as operações resultantes
  devem ter `sequence` estritamente não-decrescente.
"""

from __future__ import annotations

from typing import List, Optional, Set

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from src.plan.services.routing_resolver import RoutingRow, _truncate_route_to_current


# ---------------------------------------------------------------------------
# Estratégias de geração
# ---------------------------------------------------------------------------

@st.composite
def _routing_row(draw, seq: int) -> RoutingRow:
    fase_id = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=2, max_size=10,
    ))
    return RoutingRow(
        fase_id=fase_id,
        fase_nome=f"Fase {fase_id}",
        sequence=seq,
        duration_hours=draw(st.floats(min_value=0.1, max_value=20.0, allow_nan=False)),
        source="history_db",
        mold_required=False,
    )


@st.composite
def _route_with_completed(draw, min_size: int = 2, max_size: int = 8):
    """Gera uma rota (lista de RoutingRow ordenada por sequence) + conjunto
    de fase_ids já concluídas (subconjunto da rota).

    Retorna (rows, completed_fase_ids, current_fase_id_or_none).
    """
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    # Gera sequências únicas crescentes
    rows: List[RoutingRow] = []
    seen_fase_ids: list[str] = []
    for i in range(n):
        row = draw(_routing_row(seq=i + 1))
        # Garante fase_ids únicos na rota
        attempt = 0
        while row.fase_id in seen_fase_ids and attempt < 10:
            row = draw(_routing_row(seq=i + 1))
            attempt += 1
        seen_fase_ids.append(row.fase_id)
        rows.append(row)

    # Subconjunto das primeiras k fases como "concluídas" (k in 0..n-1)
    n_done = draw(st.integers(min_value=0, max_value=max(0, n - 1)))
    completed_fase_ids: Set[str] = {rows[i].fase_id for i in range(n_done)}

    # `current_fase_id`: pode ser uma fase da rota (incluindo concluídas),
    # pode ser desconhecida (fora da rota), ou None.
    choice = draw(st.integers(min_value=0, max_value=2))
    if choice == 0 and n > 0:
        # Fase da rota (pode ser concluída ou não)
        current_fase_id = draw(st.sampled_from(seen_fase_ids))
    elif choice == 1:
        # Fora da rota
        current_fase_id = "FASE_INVALIDA_XYZ"
    else:
        current_fase_id = None

    return rows, completed_fase_ids, current_fase_id


# ---------------------------------------------------------------------------
# P1 — Fase concluída nunca entra no plano
# ---------------------------------------------------------------------------

@settings(
    deadline=None,
    max_examples=300,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(_route_with_completed(min_size=2, max_size=8))
def test_p1_completed_phases_never_scheduled(args):
    """P1 — nenhuma operação com fase_id em completed_fase_ids deve
    aparecer no resultado de _truncate_route_to_current.

    Este invariante garante que fases com OFFP_DATAFIM preenchido
    (já concluídas) nunca voltam ao plano — independentemente do
    apontador OF_FP_ID.
    """
    rows, completed_fase_ids, current_fase_id = args
    result = _truncate_route_to_current(rows, current_fase_id, completed_fase_ids)

    for r in result:
        assert r.fase_id not in completed_fase_ids, (
            f"Fase {r.fase_id} está em completed_fase_ids mas entrou no plano. "
            f"current_fase_id={current_fase_id}, "
            f"completed={completed_fase_ids}"
        )


# ---------------------------------------------------------------------------
# P2 — Fase atual fora da rota NÃO re-planeia a rota inteira (com concluídas)
# ---------------------------------------------------------------------------

@settings(
    deadline=None,
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    n=st.integers(min_value=3, max_value=7),
    n_done=st.integers(min_value=1, max_value=2),
)
def test_p2_invalid_current_fase_no_full_replan(n, n_done):
    """P2 — quando current_fase_id não está na rota, a função NÃO deve
    devolver fases que estão em completed_fase_ids.

    O fallback antigo devolvia a rota COMPLETA (incluindo fases já feitas)
    quando o apontador era inválido. Este teste prova que o novo
    comportamento é correto: nunca re-planeia o passado.
    """
    rows = [
        RoutingRow(
            fase_id=f"F{i}",
            fase_nome=f"Fase {i}",
            sequence=i,
            duration_hours=1.0,
            source="history_db",
        )
        for i in range(1, n + 1)
    ]
    n_done = min(n_done, n - 1)
    completed = {f"F{i}" for i in range(1, n_done + 1)}

    # Fase atual fora da rota
    result = _truncate_route_to_current(rows, "FASE_INVALIDA", completed)

    for r in result:
        assert r.fase_id not in completed, (
            f"Fase {r.fase_id} está concluída mas foi re-planeada quando "
            f"current_fase_id era inválido. completed={completed}"
        )


# ---------------------------------------------------------------------------
# P3 — Ordem das operações segue SEMPRE a sequência da rota
# ---------------------------------------------------------------------------

@settings(
    deadline=None,
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(_route_with_completed(min_size=2, max_size=8))
def test_p3_result_order_follows_route_sequence(args):
    """P3 — as operações resultantes devem estar ordenadas pelo campo
    `sequence` da rota (PRODF_SEQUENCIA), nunca por colunas temporais
    como OFFP_SEQUENCIA ou OFFP_DATAINICIO.

    A função _truncate_route_to_current recebe a rota já ordenada por
    sequence e deve preservar essa ordem no resultado.
    """
    rows, completed_fase_ids, current_fase_id = args
    result = _truncate_route_to_current(rows, current_fase_id, completed_fase_ids)

    for i in range(1, len(result)):
        assert result[i - 1].sequence <= result[i].sequence, (
            f"Ordem violada: seq {result[i-1].sequence} ({result[i-1].fase_id}) "
            f"> seq {result[i].sequence} ({result[i].fase_id}). "
            f"A ordem das operações deve seguir PRODF_SEQUENCIA, nunca timestamps."
        )


# ---------------------------------------------------------------------------
# Testes de exemplo (não property) — casos concretos da BD real
# ---------------------------------------------------------------------------

class TestTruncateRouteUnit:
    """Casos concretos confirmados no barco 142079 da BD real."""

    def _route_142079(self) -> List[RoutingRow]:
        """Rota real simplificada do barco 142079:
        seq 1 Prep Molde, seq 2 Laminagem, seq 3 Pintura, seq 4 Cura, seq 5 Desmolde.
        """
        return [
            RoutingRow("FP1", "Prep Molde", 1, 2.0, "history_db"),
            RoutingRow("FP2", "Laminagem", 2, 8.0, "history_db"),
            RoutingRow("FP3", "Pintura", 3, 4.0, "history_db"),
            RoutingRow("FP4", "Cura", 4, 15.0, "history_db"),
            RoutingRow("FP5", "Desmolde", 5, 1.0, "history_db"),
        ]

    def test_fases_concluidas_nao_entram(self):
        """Fases com OFFP_DATAFIM preenchido (Prep Molde + Laminagem) não
        voltam ao plano, mesmo que OF_FP_ID aponte para FP2 (Laminagem)."""
        rows = self._route_142079()
        # Prep Molde + Laminagem concluídas
        completed = {"FP1", "FP2"}
        # OF_FP_ID aponta para FP2 (stale — já concluída)
        result = _truncate_route_to_current(rows, "FP2", completed)
        fase_ids = [r.fase_id for r in result]
        assert "FP1" not in fase_ids, "Prep Molde (concluída) não deve entrar no plano"
        assert "FP2" not in fase_ids, "Laminagem (concluída, apontador stale) não deve entrar no plano"
        assert "FP3" in fase_ids, "Pintura (por fazer) deve entrar no plano"

    def test_apontador_invalido_nao_replica_rota_inteira(self):
        """Quando OF_FP_ID não existe na rota, começar da 1ª fase por fazer,
        nunca re-planear fases já concluídas."""
        rows = self._route_142079()
        completed = {"FP1"}  # Prep Molde concluída
        # OF_FP_ID aponta para algo inválido
        result = _truncate_route_to_current(rows, "FP_INVALIDO_999", completed)
        fase_ids = [r.fase_id for r in result]
        assert "FP1" not in fase_ids, (
            "Apontador inválido NÃO deve causar re-plan da rota inteira; "
            "Prep Molde está concluída e não deve voltar ao plano"
        )
        assert "FP2" in fase_ids, "Laminagem (por fazer) deve estar no plano"

    def test_sem_concluidas_e_apontador_valido_comportamento_legado(self):
        """Sem completed_fase_ids, o comportamento legado mantém-se:
        truncar na fase atual (inclusiva)."""
        rows = self._route_142079()
        # Sem fases concluídas, apontador aponta para FP3
        result = _truncate_route_to_current(rows, "FP3", set())
        fase_ids = [r.fase_id for r in result]
        assert "FP1" not in fase_ids
        assert "FP2" not in fase_ids
        assert "FP3" in fase_ids
        assert "FP4" in fase_ids
        assert "FP5" in fase_ids

    def test_sem_concluidas_e_sem_current_devolve_rota_completa(self):
        """Sem current_fase_id e sem concluídas, devolve a rota completa."""
        rows = self._route_142079()
        result = _truncate_route_to_current(rows, None, set())
        assert len(result) == len(rows)

    def test_todas_concluidas_devolve_vazio(self):
        """Se todas as fases estiverem concluídas, o resultado deve ser
        vazio (nada a planear)."""
        rows = self._route_142079()
        completed = {"FP1", "FP2", "FP3", "FP4", "FP5"}
        result = _truncate_route_to_current(rows, "FP5", completed)
        assert result == [], "Todas concluídas → nada a planear"

    def test_ordem_preservada_apos_truncagem(self):
        """A ordem sequence deve ser preservada após a truncagem."""
        rows = self._route_142079()
        completed = {"FP1", "FP2"}
        result = _truncate_route_to_current(rows, "FP2", completed)
        seqs = [r.sequence for r in result]
        assert seqs == sorted(seqs), "Ordem sequence violada após truncagem"
