"""Q.167.F — espelho de `dbo.VARIAVEIS` (variáveis de configuração do ERP).

O motor de custos do ERP guarda factores de correcção numa tabela de
variáveis. A que nos interessa é ``VAR_ID = 2`` = "Factor de correcção das
MÃOS DE OBRA" (= '1.065'), aplicado aos componentes ``P_TP_ID = 90`` no
cálculo do custo (``Ordemfabrico_Compara_Custo_com_Standard`` etc.). Em vez
de gravar o literal 1.065 (proibido — dados honestos), espelhamos o valor
real do ERP e lemos daqui.

``var_value`` é guardado como texto (o ERP usa ``nvarchar``); o consumidor
converte para ``Decimal`` quando precisa (com fallback honesto = sem factor).
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class ErpVariable(TenantBase):
    """Uma linha de ``dbo.VARIAVEIS`` espelhada para Postgres local."""

    __tablename__ = "erp_variables"
    __table_args__ = (
        UniqueConstraint("tenant_id", "var_id", name="uq_erp_variables_tenant_var"),
        {"schema": "core"},
    )

    var_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    var_value: Mapped[Optional[str]] = mapped_column(String(255))
    var_description: Mapped[Optional[str]] = mapped_column(String(255))
