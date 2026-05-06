"""
ProdPlan ONE - Excel Column Catalogue (Onda 3.5)
=================================================

Single source of truth for the column names exposed by `Folha_IA_extra.xlsx`.
Verified directly against the workbook on 2026-05-02 (10 sheets, ~1.1M
rows). Before this catalogue, four different naming conventions floated
around the codebase (`Of_Id`, `OF_Id`, `OrdemFabricoId`, `Of_DataCriacao`)
which silently broke the transformer (CAT-1: every `curated.order.of_id`
came out as ""). New code MUST import from here instead of hard-coding
column names.

Each sheet exposes:

  * a per-sheet `Cols` namespace (dot-access, so misspelled refs raise
    AttributeError at import-time / on first use)
  * a `BUSINESS_KEYS[sheet]` list — the column(s) that uniquely identify
    a row (used by parser.py + quality gates)
  * a `CRITICAL_COLUMNS[sheet]` set — columns whose removal MUST block
    ingestion (used by drift_detector.py)
  * `CRITICAL_SHEETS` — sheets whose removal MUST block ingestion

Conventions noted on the source workbook:
  * `Of_*`  prefix on OrdensFabrico (NOT `OF_*` — that was the spec
    ghost from another factory)
  * `FaseOf_*` prefix on FasesOrdemFabrico
  * `Funcionario_*` (with capital F) on Funcionarios
  * `FuncionarioFase_*` on FuncionariosFasesAptos (master skill matrix)
  * `FuncionarioFaseOf_*` on FuncionariosFaseOrdemFabrico (allocations)
  * `Erro_*` + `OFCH_GRAVIDADE` (ALL-CAPS, oddly) on OrdemFabricoErros
  * `Molde*` (no underscore) on Moldes — different from `MoldeOf*` which
    appears on FasesOrdemFabrico
  * `Produto_*` on Modelos (sheet name is "Modelos" but rows are products)
  * `ProdutoFase_*` on FasesStandardModelos
  * `Fase_*` on Fases
"""

from __future__ import annotations

from typing import Dict, List, Set


# ---------------------------------------------------------------------------
# Per-sheet column namespaces
# ---------------------------------------------------------------------------

class _OrdensFabrico:
    OF_ID = "Of_Id"
    DATA_CRIACAO = "Of_DataCriacao"
    DATA_ACABAMENTO = "Of_DataAcabamento"
    PRODUTO_ID = "Of_ProdutoId"
    FASE_ID = "Of_FaseId"
    DATA_TRANSPORTE = "Of_DataTransporte"


class _FasesOrdemFabrico:
    FASE_OF_ID = "FaseOf_Id"
    OF_ID = "FaseOf_OfId"
    INICIO = "FaseOf_Inicio"
    FIM = "FaseOf_Fim"
    DATA_PREVISTA = "FaseOf_DataPrevista"
    COEFICIENTE = "FaseOf_Coeficiente"
    COEFICIENTE_X = "FaseOf_CoeficienteX"
    FASE_ID = "FaseOf_FaseId"
    PESO = "FaseOf_Peso"
    RETORNO = "FaseOf_Retorno"
    TURNO = "FaseOf_Turno"
    SEQUENCIA = "FaseOf_Sequencia"
    HORAS_PREVISTAS = "FaseOf_HorasPrevistas"
    # Mold subset (denormalised onto each phase row)
    MOLDE_OF_ID = "MoldeOfId"
    MOLDE_NOME = "MoldeNome"
    MOLDE_NUMERO_POCOS_ID = "MoldeNumeroPocosId"
    MOLDE_MODELO_ID = "MoldeModeloId"
    MOLDE_TAMANHO_ID = "MoldeTamanhoId"


class _FuncionariosFaseOrdemFabrico:
    FASE_OF_ID = "FuncionarioFaseOf_FaseOfId"
    FUNCIONARIO_ID = "FuncionarioFaseOf_FuncionarioId"
    CHEFE = "FuncionarioFaseOf_Chefe"


class _OrdemFabricoErros:
    DESCRICAO = "Erro_Descricao"
    OF_ID = "Erro_OfId"
    FASE_AVALIACAO = "Erro_FaseAvaliacao"
    GRAVIDADE = "OFCH_GRAVIDADE"  # ALL-CAPS in source, intentional
    FASE_OF_AVALIACAO = "Erro_FaseOfAvaliacao"
    FASE_OF_CULPADA = "Erro_FaseOfCulpada"


class _Funcionarios:
    FUNCIONARIO_ID = "Funcionario_Id"
    NOME = "Funcionario_Nome"
    ACTIVO = "Funcionario_Activo"
    VALOR_HORA = "FuncionarioValorHora"  # no underscore in source


class _FuncionariosFasesAptos:
    FUNCIONARIO_ID = "FuncionarioFase_FuncionarioId"
    FASE_ID = "FuncionarioFase_FaseId"
    INICIO = "FuncionarioFase_Inicio"


class _Fases:
    FASE_ID = "Fase_Id"
    NOME = "Fase_Nome"
    SEQUENCIA = "Fase_Sequencia"
    PRODUCAO = "Fase_Producao"
    AUTOMATICA = "Fase_Automatica"
    NUMERO_FUNCIONARIOS = "Fase_NumeroFuncionarios"
    CAPACIDADE_HORAS_DIA = "Fase_CapacidadeHorasDia"


class _Moldes:
    MOLDE_ID = "MoldeId"
    NOME = "MoldeNome"
    ESTADO = "MoldeEstado"
    MODELO = "MoldeModelo"
    NUMERO_POCOS_ID = "MoldeNumeroPocosId"
    MODELO_ID = "MoldeModeloId"
    TAMANHO_ID = "MoldeTamanhoId"


class _Modelos:
    PRODUTO_ID = "Produto_Id"
    NOME = "Produto_Nome"
    PESO_DESMOLDE = "Produto_PesoDesmolde"
    PESO_ACABAMENTO = "Produto_PesoAcabamento"
    QTD_GEL_DECK = "Produto_QtdGelDeck"
    QTD_GEL_CASCO = "Produto_QtdGelCasco"
    NUMERO_POCOS_ID = "Produto_NumeroPocosId"
    MODELO_ID = "Produto_ModeloId"
    TAMANHO_ID = "Produto_TamanhoId"


class _FasesStandardModelos:
    PRODUTO_ID = "ProdutoFase_ProdutoId"
    FASE_ID = "ProdutoFase_FaseId"
    SEQUENCIA = "ProdutoFase_Sequencia"
    COEFICIENTE = "ProdutoFase_Coeficiente"
    COEFICIENTE_X = "ProdutoFase_CoeficienteX"
    HORAS_PREVISTAS = "ProdutoFase_HorasPrevistas"


# Public re-exports — `from .excel_columns import OrdensFabrico` etc.
OrdensFabrico = _OrdensFabrico
FasesOrdemFabrico = _FasesOrdemFabrico
FuncionariosFaseOrdemFabrico = _FuncionariosFaseOrdemFabrico
OrdemFabricoErros = _OrdemFabricoErros
Funcionarios = _Funcionarios
FuncionariosFasesAptos = _FuncionariosFasesAptos
Fases = _Fases
Moldes = _Moldes
Modelos = _Modelos
FasesStandardModelos = _FasesStandardModelos


# ---------------------------------------------------------------------------
# Sheet catalogue (used by parser, drift detector, quality gates)
# ---------------------------------------------------------------------------

SHEETS: List[str] = [
    "OrdensFabrico",
    "FasesOrdemFabrico",
    "FuncionariosFaseOrdemFabrico",
    "OrdemFabricoErros",
    "Funcionarios",
    "FuncionariosFasesAptos",
    "Fases",
    "Moldes",
    "Modelos",
    "FasesStandardModelos",
]


# Business keys: the column(s) whose value uniquely identifies a row.
# Used by parser.py to compute `business_key_sha256` for dedup, and by
# quality gates to detect duplicates.
BUSINESS_KEYS: Dict[str, List[str]] = {
    "OrdensFabrico": [OrdensFabrico.OF_ID],
    "FasesOrdemFabrico": [FasesOrdemFabrico.FASE_OF_ID],
    "FuncionariosFaseOrdemFabrico": [
        FuncionariosFaseOrdemFabrico.FASE_OF_ID,
        FuncionariosFaseOrdemFabrico.FUNCIONARIO_ID,
    ],
    # OrdemFabricoErros has no surrogate key in the workbook; (OfId,
    # Descricao) is "good enough" for dedup at the row level.
    "OrdemFabricoErros": [
        OrdemFabricoErros.OF_ID,
        OrdemFabricoErros.DESCRICAO,
    ],
    "Funcionarios": [Funcionarios.FUNCIONARIO_ID],
    "FuncionariosFasesAptos": [
        FuncionariosFasesAptos.FUNCIONARIO_ID,
        FuncionariosFasesAptos.FASE_ID,
    ],
    "Fases": [Fases.FASE_ID],
    "Moldes": [Moldes.MOLDE_ID],
    "Modelos": [Modelos.PRODUTO_ID],
    "FasesStandardModelos": [
        FasesStandardModelos.PRODUTO_ID,
        FasesStandardModelos.FASE_ID,
    ],
}


# Critical columns: removal blocks ingestion (drift detector returns
# severity=BLOCKING). Anything outside this set is downgraded to WARNING.
CRITICAL_COLUMNS: Dict[str, Set[str]] = {
    "OrdensFabrico": {
        OrdensFabrico.OF_ID,
        OrdensFabrico.DATA_CRIACAO,
        OrdensFabrico.PRODUTO_ID,
    },
    "FasesOrdemFabrico": {
        FasesOrdemFabrico.FASE_OF_ID,
        FasesOrdemFabrico.OF_ID,
        FasesOrdemFabrico.FASE_ID,
    },
    "Funcionarios": {Funcionarios.FUNCIONARIO_ID, Funcionarios.NOME},
    "Fases": {Fases.FASE_ID, Fases.NOME},
    "Moldes": {Moldes.MOLDE_ID},
    "Modelos": {Modelos.PRODUTO_ID, Modelos.NOME},
    "FasesStandardModelos": {
        FasesStandardModelos.PRODUTO_ID,
        FasesStandardModelos.FASE_ID,
    },
    "OrdemFabricoErros": {
        OrdemFabricoErros.OF_ID,
        OrdemFabricoErros.DESCRICAO,
    },
    "FuncionariosFaseOrdemFabrico": {
        FuncionariosFaseOrdemFabrico.FASE_OF_ID,
        FuncionariosFaseOrdemFabrico.FUNCIONARIO_ID,
    },
    "FuncionariosFasesAptos": {
        FuncionariosFasesAptos.FUNCIONARIO_ID,
        FuncionariosFasesAptos.FASE_ID,
    },
}


# Sheets that MUST exist for ingestion to be valid.
CRITICAL_SHEETS: Set[str] = {
    "OrdensFabrico",
    "FasesOrdemFabrico",
    "Funcionarios",
    "Fases",
    "Moldes",
    "Modelos",
}
