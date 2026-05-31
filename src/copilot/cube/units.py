"""Mapa de unidades de medida `P_UNI_ID` → nome humano.

**Fonte autoritária**: tabela `UNIDADE` no ERP NELO (22 rows), descoberta na
SubB2.3 (continuação Q.78). Antes desta sub-sprint o mapa tinha 16 entradas
parcialmente inferidas; agora tem as **22 oficiais** com nomes humanos
directos do próprio ERP.

A tabela `UNIDADE` (MAR-KAYAKS.dbo.UNIDADE) com colunas `(UNI_ID, UNI_NOME)`
foi descoberta procurando `name LIKE '%UNI%'` em `sys.tables`. Não estava
em `factory_raw` (gap de espelhamento Q.75 — adicionar na próxima sub-sprint
de espelhamento).

**Validação das inferências Q.78** (5 que eram hipótese):
- ID=22: kWh / **KWh** ✓ (acerto perfeito)
- ID=16: rolos / **Rolo** ✓ (acerto perfeito)
- ID=17: caixa / **Caixa** ✓ (acerto perfeito)
- ID=18: tambor / **Bidão** ≈ (semântica idêntica: ambos = embalagem
  cilíndrica grande para químicos)
- ID=5: pack / **Conjunto** ≈ (semântica idêntica: ambos = pack pré-definido)

**Novas unidades descobertas** (não estavam no mapa anterior):
- ID=8: Gr (gramas)
- ID=9: Lata
- ID=15: Mts³ (metros cúbicos)
- ID=19: Saco
- ID=20: Bobine
- ID=21: Cone

Mantém-se a forma humanizada PT-PT (em vez das abreviaturas ERP) por
legibilidade na UI: "metros" em vez de "Mts", "kg" em vez de "Kg", etc.

Princípio inalterado: IDs fora do mapa devolvem "unidade desconhecida
(ID=N)" — nunca esconde.
"""
from __future__ import annotations

from typing import Optional

# 22 unidades — fonte: tabela `UNIDADE` do ERP NELO (SubB2.3).
# Comentário ao lado mostra `UNI_NOME` original quando difere da forma
# humanizada usada na UI.
KNOWN_UNITS: dict[int, str] = {
    1: "metros",        # Mts
    2: "m²",            # Mts²
    3: "placas",        # Placa
    4: "chapas",        # Chapa
    5: "conjunto",      # Conjunto
    6: "€",             # Euro
    7: "kg",            # Kg
    8: "gr",            # Gr
    9: "lata",          # Lata
    10: "litros",       # Ltr
    11: "pares",        # Par
    12: "unidades",     # Unid
    13: "tubos",        # Tubo
    14: "horas",        # Hora
    15: "m³",           # Mts³
    16: "rolos",        # Rolo
    17: "caixa",        # Caixa
    18: "bidão",        # Bidão (era "tambor" inferido — agora confirmado oficial)
    19: "sacos",        # Saco
    20: "bobines",      # Bobine
    21: "cones",        # Cone
    22: "kWh",          # KWh
}


def unit_label(unit_id: Optional[int]) -> str:
    """Devolve nome da unidade ou label "desconhecida" — nunca esconde.

    Args:
        unit_id: P_UNI_ID ou P_UNI_ID_MOVIMENTOS; None se a row vem sem unidade.

    Returns:
        Nome curto (22 oficiais NELO) se conhecida.
        "sem unidade definida" se unit_id é None.
        "unidade desconhecida (ID=N)" se int mas não mapeada (improvável agora
        que o mapa cobre 1-22 — só IDs >22 ou <1 cairiam aqui).
    """
    if unit_id is None:
        return "sem unidade definida"
    name = KNOWN_UNITS.get(int(unit_id))
    if name:
        return name
    return f"unidade desconhecida (ID={int(unit_id)})"


def is_known(unit_id: Optional[int]) -> bool:
    """True se `unit_id` está em `KNOWN_UNITS`."""
    if unit_id is None:
        return False
    return int(unit_id) in KNOWN_UNITS


__all__ = ["KNOWN_UNITS", "is_known", "unit_label"]
