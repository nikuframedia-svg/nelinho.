"""Q.134.M1 — cria as 2 tabelas create_all-only do loop de aprendizagem.

`plan.phase_duration_calibration` (Q.133.A1) e `plan.plan_execution_observed`
(Q.113/Q.134.A3a) viviam só em `Base.metadata` — nenhuma migração as criava.
Em dev "funcionavam" porque `init_db_create_all` as cria; numa BD FRESCA
`alembic upgrade head` rebentava no 065 (`ENABLE RLS` numa tabela inexistente).
O 065 passou a saltar tabelas inexistentes; esta migração cria-as e aplica-lhes
a RLS — fechando o `upgrade head` production-safe (mesmo padrão do 055a).

Idempotente nos dois sentidos:
  * BD fresca → `Table.create` cria as tabelas (com a coluna/índice novos do
    modelo); os ALTER/CREATE INDEX `IF NOT EXISTS` são no-op.
  * dev/prod (tabelas já existem via create_all) → `checkfirst=True` no-op no
    create; os ALTER/CREATE INDEX trazem-nas ao modelo Q.134 (coluna
    `systematic_deviation_pct` A3b + índice único parcial A3a) sem perder dados.

Revision ID: 066_q134_create_all_only
Revises: 065_qr_audit_rls
Create Date: 2026-05-31
"""
from alembic import op


revision = "066_q134_create_all_only"
down_revision = "065_qr_audit_rls"
branch_labels = None
depends_on = None


# (schema, table) — create_all-only confirmadas (teste fresh-DB: o 065 falhava
# em plan.phase_duration_calibration). encomendas_cancelled NÃO está aqui: é
# criada por q115_x5a; boat_boost/order_boost/work_order_override por q116c/d;
# kpi_snapshot por q117d. Só estas duas eram órfãs.
_TARGET_TABLES = [
    ("plan", "phase_duration_calibration"),
    ("plan", "plan_execution_observed"),
]


def upgrade() -> None:
    # model_registry garante que os models estão em Base.metadata.
    from src.shared import model_registry  # side-effect: regista models
    from src.shared.database import Base

    bind = op.get_bind()
    for schema, table_name in _TARGET_TABLES:
        table = Base.metadata.tables.get(f"{schema}.{table_name}")
        if table is None:  # defesa contra renames futuros — não falha
            op.execute(
                f"SELECT 'WARNING: {schema}.{table_name} ausente em metadata'"
            )
            continue
        # checkfirst=True → NOOP se já existe (create_all em dev/prod).
        table.create(bind, checkfirst=True)

    # Traz DBs já existentes (create_all antigo) ao modelo Q.134. No fresh-DB
    # o create() acima já os incluiu → estes IF NOT EXISTS são no-op.
    # A3b — coluna do desvio sistemático na calibração.
    op.execute(
        "ALTER TABLE plan.phase_duration_calibration "
        "ADD COLUMN IF NOT EXISTS systematic_deviation_pct double precision"
    )
    # A3a — índice único parcial p/ o UPSERT idempotente do capture_plan_execution.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_plan_exec_commit_of_phase "
        "ON plan.plan_execution_observed "
        "(tenant_id, schedule_commit_id, of_id, phase_id) "
        "WHERE schedule_commit_id IS NOT NULL"
    )

    # RLS tenant_isolation nas 2 tabelas (o 065 saltou-as numa BD fresca).
    for schema, table_name in _TARGET_TABLES:
        op.execute(
            f"ALTER TABLE {schema}.{table_name} ENABLE ROW LEVEL SECURITY"
        )
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation ON {schema}.{table_name}"
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {schema}.{table_name}
                USING (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
                WITH CHECK (
                    tenant_id = current_setting('app.tenant_id', true)::uuid
                )
            """
        )


def downgrade() -> None:
    # Não dropamos as tabelas (perda de dados em prod). Removemos só o que
    # esta migração acrescentou: policy + índice + coluna.
    for schema, table_name in _TARGET_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF to_regclass('{schema}.{table_name}') IS NOT NULL THEN
                    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation '
                          || 'ON {schema}.{table_name}';
                END IF;
            END $$
            """
        )
    op.execute("DROP INDEX IF EXISTS plan.uq_plan_exec_commit_of_phase")
    op.execute(
        "ALTER TABLE plan.phase_duration_calibration "
        "DROP COLUMN IF EXISTS systematic_deviation_pct"
    )
