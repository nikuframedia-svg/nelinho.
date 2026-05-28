# Q.115.T — ETL FasesOf + WorkerAssignment

## Tabelas ERP de origem (Mar-Kayaks)

### FasesOf (~2.6M linhas)

- Historico LIMPO de fases por OF (`FaseOf_DataInicio` → `FaseOf_DataFim`)
- Antes do Q.115.T so era lido read-only via `services.list_entity_phases()`
- Campos chave: `OF_Id`, `FaseOf_Id`, `FaseOf_DataInicio`, `FaseOf_DataFim`, `WorkerId`, `MoldeId`

### WorkerAssignment (?)

- Historico de alocacoes operador-fase
- Suporta diferenciar `planned` vs `actual` (`assignment_type`)
- Campos chave: `WorkerId`, `OF_Id`, `FaseOf_Id`, `Atribuido_Em`, `Iniciado_Em`, `Terminado_Em`, `Tipo`

## Espelhos nelinho

- `plan.fases_of_history` (Q.115.A.08) — modelo `src/plan/models/fases_of_history.py`
- `hr.worker_phase_assignment` (Q.115.A.09) — modelo `src/hr/models/worker_phase_assignment.py`

## ETLs

- `src/adapters/nelo/etl/phase_history.py` — mirror `phase_history`
- `src/adapters/nelo/etl/worker_assignment.py` — mirror `worker_assignment`
- Services: `services.list_phase_history(since, limit)` + `services.list_worker_assignments(since, limit)`
- Schemas Pydantic: `FasesOfHistoryRow` + `WorkerAssignmentRow` em `schemas.py`

## Frequencia

- Full sync nocturno 02:00 UTC (incluido no `nelo_erp_sync` que corre todos os mirrors)
- Incremental 15 min via `nelo_erp_phase_history_incremental` (job separado)

## Activacao

Requer `SQLSERVER_ENABLED=true`. Sem isso, ETLs fazem skip silencioso (status='skipped', sem erro).

## Audit

`core.etl_run` regista cada execucao com `rows_read/ins/upd`. Watermark incremental lido de `MAX(finished_at)` das runs `status='ok'` via `last_sync_watermarks()`.

## Notes de implementacao

- `worker_id` ERP e `int` (id de entidade); convertido para UUID deterministico via `uuid5` para compatibilidade com `hr.worker_phase_assignment.worker_id UUID`.
- `duration_min` calculado em Python (nao SQL GENERATED) porque `fase_fim` e nullable.
- Datetimes naive do ERP assumidos UTC (NELO Vila do Conde, servidor ERP em UTC).
- Encoding UTF-8 forcado via `_safe_str` para prevenir problemas de charset CP1252.
