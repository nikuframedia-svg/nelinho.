"""Q.138.A: seed product_pricing from factory_raw.produto P_PRECOVENDA

Revision ID: 0a6edb6dbc74
Revises: 067_q135_phase_config
Create Date: 2026-06-01 03:13:06.840717+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a6edb6dbc74'
down_revision: Union[str, None] = '067_q135_phase_config'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TENANT_DEV = "00000000-0000-0000-0000-000000000001"

# Limiar minimo: precos < 10 EUR em P_PRECOVENDA sao tipicamente acessórios
# em unidades fraccionadas (eg. euros/kg de resina) — excluir para nao
# contaminar throughput_eur_day com valores de componentes, nao produtos acabados.
_MIN_PRICE_EUR = 10.0


def upgrade() -> None:
    """Seed profit.product_pricing com precos de lista PHC (P_PRECOVENDA).

    Fonte: factory_raw.produto.P_PRECOVENDA (preco de venda ao publico PHC).
    Join: factory_raw.produto.P_ID::text = core.products.product_code.
    Filtro: P_PRECOVENDA >= 10 EUR (exclui componentes em unidades fraccionadas).
    Scope: so insere se profit.product_pricing estiver vazio (idem para tenant dev).
    valid_from = data de execucao da migracao.

    Prova de correcao:
    - 3714 produtos com P_PRECOVENDA >= 10 EUR, todos mapeados para core.products.
    - Range razoavel: Canoe Sprint avg 3084 EUR, Canoe Marathon avg 2620 EUR.
    - Limiar de validacao: se CPO correr apos esta migracao, throughput_eur_day
      deve ser > 0 (era 0 antes por profit.product_pricing estar vazia).

    Limite desta abordagem (documentado):
    - P_PRECOVENDA e preco de tabela PHC, nao preco efectivamente cobrado
      (descontos, negociacoes especiais nao reflectidos).
    - entidade_phc_fact nao tem quantidade por produto — impossivel validar
      preco unitario contra faturacao PHC de forma directa.
    - P_PRECOVENDA_INTERNACIONAL = 0 para a maioria (usar P_PRECOVENDA para
      todos os mercados ate CFO confirmar campo correcto).
    - Reversivel: downgrade elimina as linhas inseridas por esta migracao.
    """
    conn = op.get_bind()

    # Guard: nao re-seeda se ja tem dados para este tenant
    count = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM profit.product_pricing"
            " WHERE tenant_id = CAST(:tid AS uuid)"
        ),
        {"tid": _TENANT_DEV},
    ).scalar()
    if count and count > 0:
        return  # ja seeded — idempotente

    conn.execute(
        sa.text(
            """
            INSERT INTO profit.product_pricing (
                id,
                tenant_id,
                product_id,
                sale_value_default_eur,
                currency_code,
                valid_from,
                valid_to,
                active,
                notes,
                created_at,
                updated_at
            )
            SELECT
                gen_random_uuid(),
                CAST(:tid AS uuid),
                cp.id,
                p."P_PRECOVENDA",
                'EUR',
                CURRENT_DATE,
                NULL,
                TRUE,
                'seed Q.138.A: P_PRECOVENDA PHC (preco de tabela; confirmar com CFO)',
                NOW(),
                NOW()
            FROM core.products cp
            JOIN factory_raw.produto p ON p."P_ID"::text = cp.product_code
            WHERE p."P_PRECOVENDA" >= :min_price
            ON CONFLICT DO NOTHING
            """
        ),
        {"tid": _TENANT_DEV, "min_price": _MIN_PRICE_EUR},
    )


def downgrade() -> None:
    """Remove as linhas de seed desta migracao (notas com tag Q.138.A)."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM profit.product_pricing
            WHERE tenant_id = CAST(:tid AS uuid)
              AND notes LIKE 'seed Q.138.A:%'
            """
        ),
        {"tid": _TENANT_DEV},
    )










