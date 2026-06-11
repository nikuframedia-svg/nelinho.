"""Q.173.AS — CoeficienteX mirror (produto_fase → profit.phase_bonus_payout).

O caminho completo foi provado LIVE (21.461 linhas, idempotente em 2
corridas — 2026-06-12). Estes testes pinam os contratos puros: o helper
público de UUID de fase, o parse do valid_from, o registo do mirror e os
invariantes de honestidade (#5 e #8) que o ETL não pode violar.
"""

from __future__ import annotations

import inspect
from datetime import date

from src.adapters.nelo.etl.bonus_payout import (
    _VALID_FROM_FALLBACK,
    _parse_valid_from,
    mirror_bonus_payout,
    phase_uuid,
)


class TestPhaseUuid:
    def test_deterministico_e_estavel(self):
        """O contrato fase-ERP → UUID nunca pode mudar (a tabela já tem
        21k linhas keyed por ele)."""
        assert phase_uuid(36) == phase_uuid("36")
        assert str(phase_uuid(36)) == "90e85cea-89fb-5c70-a0de-b3ca5aecbf88"

    def test_fases_distintas_dao_uuids_distintos(self):
        assert phase_uuid(36) != phase_uuid(40)


class TestParseValidFrom:
    def test_data_iso_do_erp(self):
        assert _parse_valid_from("2024-03-15 10:22:00") == date(2024, 3, 15)

    def test_sem_data_usa_sentinela_de_janela_aberta(self):
        assert _parse_valid_from(None) == _VALID_FROM_FALLBACK
        assert _parse_valid_from("") == _VALID_FROM_FALLBACK

    def test_lixo_usa_sentinela(self):
        assert _parse_valid_from("não-é-data") == _VALID_FROM_FALLBACK


class TestRegistoEInvariantes:
    def test_mirror_registado_no_sync(self):
        """Asserção ESTÁTICA (inspect) — registo global + pytest-randomly
        não se misturam (lição Q.173.B)."""
        import src.adapters.nelo.etl.bonus_payout as mod
        import src.adapters.nelo.etl.sync as sync_mod

        src = inspect.getsource(mod)
        assert 'register_mirror("bonus_payout", mirror_bonus_payout)' in src
        assert '"bonus_payout"' in inspect.getsource(sync_mod._load_mirror_modules)

    def test_espelho_cru_sem_transformacao(self):
        """Invariante #8 — bonus_eur é cópia literal de PRODF_COEFICIENTE_X;
        nenhuma multiplicação/heurística no ETL (a semântica #64 pertence
        aos consumidores)."""
        src = inspect.getsource(mirror_bonus_payout)
        assert '"bonus_eur": r.coefx' in src
        for forbidden in ("coefx *", "* r.coefx", "coefx /"):
            assert forbidden not in src

    def test_cpo_nunca_importa_coeficiente_x(self):
        """Invariante #5 — CoeficienteX é DINHEIRO; zero imports deste
        módulo (ou de src.profit) dentro de src/plan/cpo."""
        from pathlib import Path

        cpo_dir = Path("src/plan/cpo")
        for py in cpo_dir.rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            assert "bonus_payout" not in text, f"{py} importa bonus_payout"
            assert "from src.profit" not in text, f"{py} importa src.profit"
