"""
ProdPlan ONE — Copilot data readers (Sprint Q.34.A)
====================================================

Leitores determinísticos, read-only e tenant-scoped que constroem
resumos a partir das tabelas relacionais **populadas** em Postgres
(`plan.production_orders`, `quality.rework_entry`).

Existem porque o `context_builder` lia a camada Factory Data Product
(`factory_curated.*` / `SemanticQueriesInMemory` in-memory), que arranca
vazia — o copiloto respondia "não tenho dados" mesmo com dados reais na
base. Os readers fecham essa lacuna sem tocar nos caminhos antigos.
"""
