"""Constantes semânticas para MOVIMENTO_TIPO (TPMOV) do ERP NELO.

Fonte: tabela ERP ``MOVIMENTO_TIPO`` conforme documentado em
``routes/_GLOSSARIO_BURACOS.md`` linhas 14-31 (Q.78 / SubB2.3).

Os tipos marcados com "documentado no glossário; confirmação oficial NELO
pendente" foram deduzidos por análise dos dados reais de ``factory_raw.movimento``
e estão em linha com as convenções do ERP MAR-KAYAKS, mas ainda não foram
validados presencialmente com a equipa NELO.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# TPMOV confirmados no glossário (fonte: MOVIMENTO_TIPO, Q.78/SubB2.3)
# ---------------------------------------------------------------------------

#: Entrada de produto acabado (1× por OF terminada).
TPMOV_ENTRADA: int = 1

#: Saída para stockagem — NÃO é consumo de OF.
#: Documentado no glossário; confirmação oficial NELO pendente.
TPMOV_SAIDA: int = 2

#: Reserva de material para OF — representa necessidade planeada.
#: ``MOV_SATISFEITO=False`` → reserva ainda não consumida.
#: ``MOV_SATISFEITO=True``  → reserva satisfeita (material consumido via TPMOV=11).
#: CONFIRMADO como filtro canónico de planeamento (Q.78/SubB2.3).
TPMOV_RESERVA: int = 4

#: Pedidos a fornecedor — base dos registos de encomenda.
TPMOV_PEDIDO_FORNECEDOR: int = 9

#: Saída como componente (consumo efectivo de OF) — NÃO conta para stock.
#: CONFIRMADO como filtro canónico de consumo de produção (Q.78/SubB2.3).
TPMOV_CONSUMO_OF: int = 11

#: Pedidos internos — stockagem interna.
#: Documentado no glossário; confirmação oficial NELO pendente.
TPMOV_PEDIDO_INTERNO: int = 12

# ---------------------------------------------------------------------------
# Conjuntos utilitários
# ---------------------------------------------------------------------------

#: Tipos que representam reservas de material para uma OF.
TPMOV_RESERVA_TIPOS: frozenset[int] = frozenset({TPMOV_RESERVA})

#: Tipos que representam consumo efectivo de material numa OF.
TPMOV_CONSUMO_TIPOS: frozenset[int] = frozenset({TPMOV_CONSUMO_OF})
