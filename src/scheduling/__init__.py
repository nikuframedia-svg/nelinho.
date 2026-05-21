"""Q.66.A.4 — pacote `src.scheduling`.

Decomposição do ex-god-file `src/shared/scheduler.py` (1290L) em
módulos por domínio. Public surface continua acessível via shim em
`src/shared/scheduler.py` para backwards-compat (main.py, tests, docs).

Estrutura:
  * `core` — singleton `_scheduler` + arranque/registo/shutdown.
  * `jobs/ml`               — mold_health, quality_risk, drift.
  * `jobs/preference_learning` — detector, weights_retrain, dpo_finetune.
  * `jobs/causal`           — causal_discovery (PCMCI+).
  * `jobs/improve`          — adoption_signal, abl_feedback.
  * `jobs/audit`            — retention_purge global.
  * `jobs/supply`           — shortage_scan.
  * `jobs/alerts`           — alerts_scan.
  * `jobs/feedback`         — daily_feedback.
  * `jobs/order_reconciliation` — reconcile_order_statuses, job wrapper.
  * `jobs/nelo_erp`         — sync, incremental_sync, time_mining.
"""
