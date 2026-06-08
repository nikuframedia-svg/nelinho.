"""Q.167.E — apaga as linhas stale erp_of_fp de quality.rework_entry.

A fonte canónica de defeitos passou a ser ``OF_CHECKLIST`` (mirror
:mod:`src.adapters.nelo.etl.checklist`), que separa quem CAUSOU de quem
DETECTOU (RCA real). O antigo mirror ``OF_FP`` (:mod:`...etl.quality`) deixou
de escrever ``rework_entry`` — mas as ~100k linhas que ele já tinha escrito
(``context->>'source' = 'erp_of_fp'``) ficam stale: colapsam causer=detector
e não têm operador/chefe. Com o writer OF_FP removido (mirror_quality já não
escreve rework), apagá-las torna a tabela single-source POR CONSTRUÇÃO
(checklist + retrabalho humano via POST /rework, NUNCA stale OF_FP) — os
leitores deixam de poder dupla-contar sem precisarem de filtrar por source.

As linhas são ERP-reproduzíveis (derivadas de OF_FP), logo apagá-las é seguro
e o ``downgrade`` é um no-op documentado: não ressuscitamos a dupla contagem.

Revision ID: q167e_drop_offp_rework
Revises: q158a_employee_skill_chefe
Create Date: 2026-06-08
"""
from alembic import op

revision = "q167e_drop_offp_rework"
down_revision = "q158a_employee_skill_chefe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Limpeza one-time: só as linhas do antigo mirror OF_FP. As linhas do
    # checklist (source='erp_of_checklist') ficam intactas. Seq-scan único a
    # ~100k linhas — aceitável (sem índice funcional em context->>'source').
    op.execute(
        "DELETE FROM quality.rework_entry "
        "WHERE context->>'source' = 'erp_of_fp'"
    )


def downgrade() -> None:
    # No-op intencional: as linhas erp_of_fp são reproduzíveis a partir do ERP
    # mas re-criá-las traria de volta a dupla contagem que esta campanha eliminou.
    pass
