# PLANO 22/04 — Auditoria Completa + Sprints A/B/C

**Objectivo:** levar o PP1 × NELO de estado alpha (~50%) a sistema demo-ready, baseado no documento `PP1_NELO_PLANO_COMPLETO_2.md` (V2) e em auditoria exaustiva do código real em `c:\Users\User\nelinho`.

**Data:** 22/04/2026
**Autor:** análise cruzada automática (grep + leitura de ficheiros) + V2 do plano
**Âmbito:** tudo em `src/` + `frontend/src/` + `alembic/versions/`. Ignorados: tests/, docs/.

---

## PARTE 1 — SUMÁRIO EXECUTIVO

### O que descobri

**1. Motor CPO:** 23 dos 29 bugs listados no V2 estão confirmados no código, 5 estão parcialmente corrigidos, 1 imprecisa, e apareceram **4 bugs novos** (NEW-1 a NEW-4) que o V2 não apanhou. Dos 10 aspectos-chave do domínio Nelo (par de Laminagem, backwards scheduling, cura/secagem, threshold moldes, buffer pós-Desmolde, multi-cavidade, retrabalho-causador, tempos standard vs reais, throughput €/dia, Trust Index gate) **apenas 2 estão implementados** correctamente (buffer pós-Desmolde + tempos reais parciais).

**2. Wiring inter-módulo:** 8 das 8 ligações críticas estão **quebradas ou mock**. O trust_index é literalmente hardcoded a 0.0. O módulo `explain/` não tem endpoints. O `improve/` está vazio. O `sandbox/` redirecciona para copilot. O único fluxo completo que funciona é o Copilot (Ollama + RAG + Guardrails chamam-se a sério).

**3. Modelos de dados:** Há lacunas estruturais que tornam features inteiras impossíveis até serem criadas. **O `Product` não tem `sale_price_eur`** — logo, o throughput €/dia (meta do CEO) não pode ser calculado. **Não existe `PhaseGapMatrix`** para os 16 gaps de cura/secagem. **Não existe `PreferenceRule`** model — Camada 1 de aprendizagem não tem onde gravar. O `ScheduleCommit` tem `alternatives` mas não `rejected_alternatives`.

**4. Frontend:** 147 ficheiros TSX, 41 páginas, mas 3 módulos importantes são stubs no frontend (explain, improve, twin), e não há geração de tipos via OpenAPI — contracto é strings hardcoded entre frontend e backend, o que já causou drift (Employee.aptitudes, snake_case/camelCase).

### Concretização global — revista

**~40% vs plano V2** (revisto para baixo dos 50% anteriores, porque o V2 acrescenta a auditoria §53-64 que descobre mais bugs, e os 3 explores detectaram mais drift do que estava visível).

### Caminho crítico

**11 bugs P0 + 4 buracos estruturais de modelo + ligação SQL Server.** Fechar isto dá demo credível. Tudo o resto é tier 2/3.

---

## PARTE 2 — ESTADO DO CÓDIGO

### 2.1 Motor CPO v4.0 — 29 bugs V2 + 4 novos

**Bugs CRÍTICOS (P0) — 11 itens**

| ID | File:Line | Problema | Impacto |
|---|---|---|---|
| D1 | [decoder.py:534-584](../src/plan/cpo/decoder.py#L534) | `_last_on_machine_has_different_family` retorna sempre `False` → setups sempre 0 | GA nunca optimiza setups |
| D2 | [decoder.py](../src/plan/cpo/decoder.py) inteiro | Sem constraints de cura/secagem (16 transições §3.8) | Planos fisicamente impossíveis |
| F1 | [fitness.py:60,155-173](../src/plan/cpo/fitness.py#L60) | `w_v2_throughput_eur_day` existe mas schedule dict **não tem `throughput_eur_day`** real | Meta €30-35K/dia nunca optimizada |
| WG1 | decisions.py:368 | `# TODO: Execute actual action` | Aprovação não executa |
| CO1 | [commits.py:73-76](../src/plan/cpo/commits.py#L73) | Sem `rejected_alternatives` nem `user_preference_signal` | Moat nunca acumula dados |
| C1 | [chromosome.py:45-48](../src/plan/cpo/chromosome.py#L45) | `routing_choices` existe mas decoder ignora | Routing A/B nunca optimizado |
| CX1-5 | 3 ficheiros | `CoeficienteX` tratado como tempo, é dinheiro | Lógica workforce com justificação inválida |

**Bugs ALTO (P1) — 11 itens**

D3 (quality_weight não usado no decoder), D4 (backwards scheduling só flag, sem lógica), D5 (worker selection ignora skills), F2 (idle operadores não calculado), F4 (w_quality_risk=0.0 por default), E1 (generations=50, spec=200), ME1 (eixos MAP-Elites não são laminagem-específicos), ST1 (sem phase_transition_gaps no FactoryState), TI1 (Trust Index só 4/8 componentes: falta P, A, E, CC), WG2 (rollback não implementado), FR1 (op_flip_routing faz 2-opt, não flip A↔B).

**Bugs MÉDIO (P2) — 7 itens**

D6, D7, F3, FR2, E2, E3, SN1.

**Bugs BAIXO (P3) — 4 itens**

C2, C3, ME2, TI2.

**Bugs NOVOS descobertos (não estão no V2)**

| ID | File:Line | Problema | Severidade |
|---|---|---|---|
| NEW-1 | pair_assignment.py:36-42 | `PAIR_REQUIRED_PHASES` uppercase mas comparação case-insensitive pode falhar com "Laminagem" mixed do DB | CRÍTICO |
| NEW-2 | decoder.py:307-323 | `_pick_workers` não valida `state.can_perform(phase_id, worker_id)` — pode alocar worker sem skill | ALTO |
| NEW-3 | fitness.py:142-145 | `_norm()` clipa [0,1] antes da subtração → inversão silenciosa se throughput negativo | MÉDIO |
| NEW-4 | engine.py:196-200 | Surrogate context estático; `n_ops` muda com infeasible, divergência GA vs baseline | BAIXO |

### 2.2 Regras de domínio Nelo — implementação real

| Regra | Estado | Evidência |
|---|---|---|
| A — Laminagem requer par | 🟡 parcial | `pair_assignment.py` implementado mas **não é chamado pelo decoder** |
| B — Backwards scheduling | ❌ | Flag existe ([engine.py:73](../src/plan/cpo/engine.py#L73)) + gene `schedule_direction` mas sem lógica |
| C — 16 curing constraints | ❌ | Nenhuma menção no código |
| D — Threshold manutenção moldes | ❌ | Não aparece no código de scheduling (existe em config mas não aplicado) |
| E — Buffer pós-Desmolde | ✅ | [decoder.py:138-157](../src/plan/cpo/decoder.py#L138) (4h default) |
| F — Moldes multi-cavidade | 🟡 | `compute_mold_batches` existe mas D6 (sem urgência) |
| G — Retrabalho volta ao chefe | ❓ | Campos existem no modelo (`causer_employee_id`) mas routing não encontrado |
| H — Tempos reais vs standard | 🟡 | `state.py:137-147` usa históricos com fallback `standard × 2` |
| I — Throughput €/dia na fitness | ❌ | Peso existe (0.15), mas schedule não devolve o valor (cascata F1) |
| J — Trust Index gateia aprovação | ❌ | `trust_index` hardcoded a 0.0 em [cpo.py ~120](../src/plan/api/cpo.py) |

**Diagnóstico:** 2 em 10 das regras de domínio estão a funcionar end-to-end. As restantes têm scaffolding mas falta a última peça (ligar ao decoder, popular o valor, activar gate).

### 2.3 Wiring inter-módulo — 8 ligações

**Cenário A — Gestor aprova na Timeline:** 5 buracos no fluxo.
- Endpoint `GET /v1/plan/cpo/timeline` existe mas **frontend não o chama**
- UI Timeline não distingue "aprovar uma alternativa" vs "rejeitar as restantes"
- Endpoint `POST .../approve` não existe em [src/plan/api/cpo.py](../src/plan/api/cpo.py)
- Write-gate `decisions.py:368` tem `# TODO: Execute actual action`
- `rejected_alternatives` não tem coluna (CO1)

**Cenário B — Copilot pergunta/resposta:** funcional end-to-end. FactoryState real via SQL, Ollama chama-se realmente, Guardrails Tier1/Tier2 activos. Único ponto frágil: se Ollama offline retorna erro estruturado (boa prática).

**Cenário C — CPO gera plano:** 6 fases executam mas `trust_index = 0.0` hardcoded. Rejected_alternatives não guardado. Sem comparação com parent commit ("isto é melhor?"). Sem validação de constraints de fase.

**Ligações (8):**
- plan ← profit: 🟡 só priority_report.py:27 (não na fitness do CPO)
- plan ← dqa: ❌ trust_index=0.0 hardcoded
- plan ← hr: ❌ zero imports
- plan ← supply: ❌ zero imports
- explain ← plan: ❌ módulo explain/ sem endpoints reais
- sandbox ← plan: ❌ redirecciona para copilot
- workforce ← plan+hr: ❌ fallback mock `MEDIAN_HOURLY_RATE=5.54`
- improve ← ml+plan: ❌ módulo improve/ vazio

### 2.4 Modelos de dados — buracos estruturais

**CRÍTICOS:**

1. **`Product` sem `sale_price_eur`** — [product.py:38](../src/core/models/product.py) tem `standard_cost`, não preço de venda. Sem isto, throughput €/dia não pode ser calculado. **Blocker direto da meta CEO.**

2. **Sem `PhaseGapMatrix`** — os 16 gaps de cura/secagem não têm onde viver. Só existe `queue_time.median_h = 5.2h` global em [default_configs.py:105-107](../src/core/services/default_configs.py#L105). Precisa tabela nova ou config seed.

3. **Sem `PreferenceRule`** — Camada 1 da aprendizagem não tem onde gravar. Sem tabela = sem sistema de regras aprendidas.

4. **`ScheduleCommit.rejected_alternatives`** — campo inexistente. Migration 022 necessária.

**ALTO:**

5. `ReworkEntry.causer_employee_id` existe mas é NULLABLE sem warning — QA02 routing (pintura volta ao causador) falha silenciosamente quando NULL.

6. `MoldDefectLog.severity` é string (`"low"/"medium"/"high"`) mas dados ERP têm `OFCH_GRAVIDADE` numérico (1/2). Precisa mapeamento explícito na ingestão.

**Enums OK:** `ScheduleStatus`, `OrderStatus`, `ProductType`, `AutonomyLevel`, `DecisionStatus`, `ApprovalAction`, `RiskLevel` — todos definidos em ficheiros dedicados.

**Frontend:**
- Types hand-written, sem OpenAPI generation
- Drift em `Employee.aptitudes` (array no TS, many-to-many no backend)
- ScenarioComparison aceita snake_case E camelCase (workaround de inconsistência)
- `ScheduleCommit.alternatives` sem tipo TS dedicado

### 2.5 Migrations Alembic — 21 existentes + 4 novas a criar

```
001 copilot_tables            012 plan_schedule_commits
002 copilot_conversations     013 tenant_configuration
003 event_outbox              014 supply_master
004 dqa_tables                015 transport_batch
005 supply_tables             016 routing_templates
006 copilot_action_logs       017 product_pricing
007 decision_ledger           018 quality_rework
008 pgvector_embeddings       019 schedule_quality_score
009 twin_scenarios            020 mold_maintenance
010 copilot_alerts            20260120 core_tables
011 ml_model_artifacts
```

**A criar:**
- **022_schedule_commit_learning_fields** — adiciona `rejected_alternatives`, `user_preference_signal` em `plan_schedule_commits`
- **023_phase_transition_gaps** — cria tabela para 16 constraints de cura
- **024_preference_rules** — cria tabela para regras aprendidas (Camada 1)
- **025_product_sale_price** — adiciona `sale_price_eur` + `sale_price_currency` em `core.products`
- **025a_phase_bonus_payout** — tabela CoeficienteX movido para Custos

---

## PARTE 3 — PLANO DE CORRECÇÃO

### Princípios

1. **Corrigir antes de adicionar.** Os 29 bugs da auditoria V2 precedem features novas.
2. **Gravar antes de aprender.** `rejected_alternatives` desde o Sprint B = dataset de preferências começa a acumular.
3. **Confirmar antes de construir.** H2/H3/H4 ao CEO antes do Sprint A terminar.
4. **Ligar antes de optimizar.** SQL Server Nelo ligado antes de qualquer optimização de fitness real.
5. **Cada sprint tem demo interna.** Se algo não consegue ser demo'd, não está feito.

### Estratégia

- **3 sprints de 2 semanas = 6 semanas** até demo credível ao CEO
- **Tier 2 (8 semanas mais)** para LLM causal + aprendizagem profunda
- **Tier 3 (6+ meses)** para DoWhy-GCM, PCMCI+, DPO, RLM

---

## SPRINT A (Semanas 1-2) — Desbloqueio + Physics

**Objectivo:** O scheduler pára de gerar planos fisicamente impossíveis. As hipóteses abertas são confirmadas. Os valores errados (CoeficienteX, 50→61) são corrigidos.

### A.1 Fixes CoeficienteX (CX1-CX5) — Dia 1

**CX1 — Remover 3 comentários errados.** Esforço: 15 min.

- [src/plan/cpo/pair_assignment.py:6](../src/plan/cpo/pair_assignment.py#L6) — remover `"CoeficienteX > 0 encodes the second worker's time"`
- [src/plan/cpo/state.py:59](../src/plan/cpo/state.py#L59) — remover `"phase codes that require a 2-person crew (CoeficienteX > 0)"`
- [src/core/services/default_configs.py:113](../src/core/services/default_configs.py#L113) — remover `"WF11 — Laminagem SEMPRE 2 workers (CoeficienteX > 0)"`

Substituir por: `"Laminagem standard requer 2 workers (88.5% das operações históricas — FuncionariosFaseOrdemFabrico)"`.

**CX2 — Substituir critério.** Esforço: 1h.

Em `pair_assignment.py` e `state.py`, trocar:
```python
# ❌ Antigo
if phase.coeficiente_x > 0:
    return PAIR_REQUIRED

# ✅ Novo — baseado em dados históricos
def _compute_pair_required_phases(historical_ops: list) -> set[str]:
    """Para cada fase, calcula % ops com ≥2 workers.
    Retorna fases onde ≥80% historicamente foram pares."""
    by_phase = defaultdict(list)
    for op in historical_ops:
        by_phase[op.phase_code].append(len(op.workers) >= 2)
    return {
        phase for phase, pairs in by_phase.items()
        if sum(pairs) / len(pairs) >= 0.80
    }
```

Seed: `PAIR_REQUIRED_PHASES = {"LAMINAGEM"}`. Laminagem Infusão fica fora (só 40% pares).

**CX3 — Auditar ausência em contas de duração.** Esforço: 2h.

Grep `coeficiente_x|coefficientX` em `src/plan/cpo/` e `src/plan/engines/`. Verificar que em nenhum sítio é somado, multiplicado ou comparado com tempos (`timedelta`, `hours`, `minutes`). Se encontrar algum, remover e documentar no commit.

**CX4 — Mover para src/profit/.** Esforço: 2h.

Adicionar em `src/profit/models.py`:
```python
class PhaseBonusPayout(TenantBase):
    __tablename__ = "profit.phase_bonus_payout"
    product_id: Mapped[UUID]
    phase_id: Mapped[UUID]
    bonus_eur: Mapped[Decimal]  # o valor do CoeficienteX
    source: Mapped[str] = mapped_column(default="ERP_STANDARD")
```

Migration Alembic `025a_phase_bonus_payout`.

**CX5 — Alimentar módulo Custos.** Esforço: 4h.

`src/profit/service.py`:
- `calculate_worker_payroll(worker_id, period)` — soma de bonus por operação feita
- `calculate_order_labor_cost(of_id)` — prémios × quantidade de operações da OF
- Expor em `src/profit/api/cogs.py` como componente de CS01.

### A.2 Confirmar hipóteses com CEO (H-ASK) — Dia 2

**Mensagem única ao CEO.** Esforço: 10 minutos (do CEO), 1 dia de espera por resposta.

Conteúdo exato:

> Bom dia [CEO]. 3 perguntas rápidas para calibrar o software de produção:
>
> 1. **Manutenção dos moldes:** quantos usos aguenta um molde antes de começar a causar defeitos? Ou fazem manutenção por inspecção visual sem número fixo?
>
> 2. **Erros — campo `OFCH_GRAVIDADE`:** o que significam os valores **1** e **2**? É severidade (1=menor, 2=maior)? Tipo de defeito (estético vs estrutural)?
>
> 3. **Laminagem com 1 trabalhador:** 11.5% dos registos mostram Laminagem feita por 1 pessoa. São sempre erros de registo ou há casos legítimos (barcos pequenos, reparações, urgências)?
>
> Para referência — o CoeficienteX (prémio €) e a data de transporte (camião) já estão confirmados.

### A.3 Constraints de cura/secagem (D2 + ST1) — Dias 3-5

**Criar tabela `phase_transition_gap`.** Migration Alembic 023:

```python
# alembic/versions/023_phase_transition_gaps.py
op.create_table(
    "phase_transition_gap",
    sa.Column("id", PG_UUID, primary_key=True),
    sa.Column("tenant_id", PG_UUID, nullable=False, index=True),
    sa.Column("from_phase_code", sa.String(64), nullable=False),
    sa.Column("to_phase_code", sa.String(64), nullable=False),
    sa.Column("min_gap_hours", sa.Numeric(5, 2), nullable=False),
    sa.Column("reason", sa.String(128)),  # 'curing_resin', 'drying_paint', etc.
    sa.Column("n_observations", sa.Integer),  # quantos registos históricos
    sa.Column("active", sa.Boolean, default=True),
    sa.Column("created_at", sa.DateTime, default=sa.func.now()),
    sa.UniqueConstraint("tenant_id", "from_phase_code", "to_phase_code"),
    schema="plan",
)
```

**Seed com 16 transições.** Em `src/core/services/default_configs.py`, secção `phase_gaps`:

```python
PHASE_GAPS_SEED = [
    ("LAMINAGEM", "CURA", 15.0, "curing_resin", 17012),
    ("PINTURA_ACABAMENTO", "LIXAGEM_SECO", 12.5, "drying_paint", 20335),
    ("PINTURA_ACABAMENTO", "COLAGEM_PECAS", 12.5, "drying_paint", 1229),
    ("PINTURA_ACABAMENTO", "COLAGEM_GOLAS", 15.5, "drying_paint", 134),
    ("COLAGEM_PECAS", "PINTURA_ACABAMENTO", 19.5, "curing_glue", 6912),
    ("COLAGEM_PECAS", "ACABAMENTO_2", 23.5, "curing_glue", 2290),
    ("COLAGEM_PECAS", "ACABAMENTO_3", 21.5, "curing_glue", 385),
    ("COLAGEM_PECAS", "ACABAMENTO_PREPARACAO", 23.5, "curing_glue", 676),
    ("COLAGEM_BARCOS", "PINTURA_ACABAMENTO", 19.0, "curing_glue", 777),
    ("ACABAMENTO_ENVERNIZ", "LIXAGEM_AGUA", 18.0, "drying_varnish", 3016),
    ("COLAGEM_GOLAS", "ACABAMENTO_3", 24.5, "curing_glue", 175),
    ("COLAGEM_GOLAS", "ACABAMENTO_2", 24.0, "curing_glue", 183),
    ("LIXAGEM_SECO", "ACABAMENTO_ENVERNIZ", 21.5, "drying", 474),
    ("LIXAGEM_SECO", "ACABAMENTO_PINTURA", 21.5, "drying", 548),
    ("LIXAGEM_AGUA", "ACABAMENTO_2", 15.0, "drying", 999),
    ("LAMINAGEM_INFUSAO", "CURA", 24.0, "curing_infusion", 300),
]
```

**Aplicar no FactoryState.** [src/plan/cpo/state.py](../src/plan/cpo/state.py):
```python
@dataclass
class FactoryState:
    # ... campos existentes ...
    phase_transition_gaps: Dict[Tuple[str, str], float] = field(default_factory=dict)

    @classmethod
    async def load_from_db(cls, session, tenant_id):
        # ... load existing ...
        gaps = await session.execute(
            select(PhaseTransitionGap)
            .where(PhaseTransitionGap.tenant_id == tenant_id)
            .where(PhaseTransitionGap.active == True)
        )
        phase_transition_gaps = {
            (g.from_phase_code, g.to_phase_code): float(g.min_gap_hours)
            for g in gaps.scalars()
        }
        return cls(..., phase_transition_gaps=phase_transition_gaps)
```

**Aplicar no decoder.** [src/plan/cpo/decoder.py](../src/plan/cpo/decoder.py) — no cálculo de `earliest_start`:
```python
def _earliest_start_for_op(state, op, predecessors_ended_at):
    earliest = max(predecessors_ended_at.values(), default=op.due_date_start)
    # NOVO — respeitar cura/secagem obrigatória
    for pred_phase, pred_end in predecessors_by_phase.items():
        min_gap = state.phase_transition_gaps.get(
            (pred_phase, op.phase_code), 0.0
        )
        earliest = max(earliest, pred_end + timedelta(hours=min_gap))
    return earliest
```

**Aplicar no CP-SAT.** [src/plan/engines/cpsat_lrho.py](../src/plan/engines/cpsat_lrho.py) — adicionar constraint:
```python
for op in operations:
    for pred_op in precedence_map[op.id]:
        gap_h = phase_gaps.get((pred_op.phase_code, op.phase_code), 0)
        gap_min = int(gap_h * 60)
        model.Add(op.start >= pred_op.end + gap_min)
```

**Testes obrigatórios:**
- `tests/plan/test_curing_constraints.py` — verifica que schedule com Laminagem→Cura tem gap ≥15h
- Property-based: para qualquer schedule gerado, `∀ (pred, succ) ∈ gaps: succ.start - pred.end ≥ min_gap`

### A.4 Actualizar constantes — Dia 5

- [default_configs.py:121](../src/core/services/default_configs.py#L121): `50 → 61` routing templates
- [default_configs.py:166](../src/core/services/default_configs.py#L166): remover hardcode 500, deixar só `configurable=True`
- Campo `workers_active_2024` não deve ser hardcoded — calcular de `FuncionariosFaseOrdemFabrico` em load time

### A.5 Bugs P0 adicionais — Dias 6-10

**D1 — Setup counter real.** [decoder.py:534-584](../src/plan/cpo/decoder.py#L534). Implementar comparação de `setup_family` entre última op da máquina e op actual. Incrementar `setups` quando muda família. Adicionar campo `setup_family` a `Operation` model.

**F1 — Throughput €/dia no schedule.** Depende de adicionar `Product.sale_price_eur` (migration 025). No decoder, após scheduling, calcular:
```python
throughput_eur_day = (
    sum(op.product.sale_price_eur for op in schedule
        if op.is_final_phase
        and op.end_time.date() == target_date)
)
schedule_result["throughput_eur_day"] = throughput_eur_day
```

**WG1 — Execute actual action.** [decisions.py:368](../src/shared/api/decisions.py#L368). Implementar `ActionExecutor.execute(decision)`:
- Aplicar `proposed_state` ao `FactoryState`
- Persistir em DB
- Emitir evento Kafka `DECISION_EXECUTED`
- Gravar audit log append-only

**NEW-1 — Normalização case.** [pair_assignment.py:36-42](../src/plan/cpo/pair_assignment.py#L36). Garantir `.upper()` em ambos os lados da comparação.

**NEW-2 — Validar skill em _pick_workers.** [decoder.py:307](../src/plan/cpo/decoder.py#L307). Antes de usar worker, chamar `state.can_perform(phase_id, worker_id)`. Se falso, skip.

### Critério de saída Sprint A

- [ ] `pytest tests/plan/` passa
- [ ] `python -c "from src.plan.cpo import decoder; ..."` não emite warnings
- [ ] Nenhuma menção a `CoeficienteX` como tempo no código (grep vazio)
- [ ] Schedule gerado respeita todos os 16 curing constraints (teste property-based)
- [ ] Resposta do CEO a H2/H3/H4 documentada em `plano-22-04.md`
- [ ] 11 bugs P0 fechados, commits com referência ao ID (D1, CX1, etc.)

---

## SPRINT B (Semanas 3-4) — Alicerce do Moat

**Objectivo:** a partir deste sprint, cada aprovação na Timeline passa a gerar dados de aprendizagem. SQL Server ligado em modo read-only. Bugs P1 do motor resolvidos.

### B.1 Rejected alternatives + user preference (CO1) — Dias 1-2

**Migration 022** — `alembic/versions/022_schedule_commit_learning_fields.py`:
```python
op.add_column("plan_schedule_commits",
    sa.Column("rejected_alternatives", JSONB, nullable=False, server_default="[]"),
    schema="plan")
op.add_column("plan_schedule_commits",
    sa.Column("user_preference_signal", JSONB, nullable=False, server_default="{}"),
    schema="plan")
op.add_column("plan_schedule_commits",
    sa.Column("evidence_refs", JSONB, nullable=False, server_default="[]"),
    schema="plan")
op.add_column("plan_schedule_commits",
    sa.Column("scenarios_tested", sa.Integer, nullable=False, server_default="0"),
    schema="plan")
```

**Modelo** — [src/plan/cpo/commits.py:45](../src/plan/cpo/commits.py#L45):
```python
class ScheduleCommit(TenantBase):
    # ... campos existentes ...
    rejected_alternatives: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    user_preference_signal: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    evidence_refs: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    scenarios_tested: Mapped[int] = mapped_column(sa.Integer, default=0)
```

**Schema de cada `rejected_alternative`:**
```python
{
    "commit_sha_would_be": "abc123...",  # se esta tivesse sido escolhida
    "kpis": {
        "makespan_h": 120.5, "tardiness_h": 8.2,
        "throughput_eur_day": 28400, "setup_count": 12,
        "quality_risk": 0.34, "idle_ratio": 0.18
    },
    "delta_vs_chosen": {  # diferenças para a alternativa aceite
        "makespan_h": +2.3,
        "throughput_eur_day": -1200
    },
    "rejection_reason": "user_text" | "auto_worse_makespan" | null,
    "rejected_at": "2026-04-22T14:30:00Z",
    "mapelites_cell": [0.8, 0.1, 0.2]  # localização no grid 10×10×5
}
```

### B.2 Timeline UI grava rejeitados — Dias 3-5

**Backend endpoint.** Em [src/plan/api/cpo.py](../src/plan/api/cpo.py):
```python
@router.post("/plan/cpo/commit/{commit_id}/decide")
async def decide_on_commit(
    commit_id: UUID,
    decision: TimelineDecision,  # {chosen_alt_id, rejected_alt_ids[], reason?}
    user: User = Depends(get_user),
):
    commit = await commits_service.get(commit_id)
    chosen_alt = commit.alternatives[decision.chosen_alt_idx]
    rejected = [
        build_rejected_record(alt, chosen_alt, decision.reason)
        for i, alt in enumerate(commit.alternatives)
        if i != decision.chosen_alt_idx
    ]
    await commits_service.update(
        commit_id,
        rejected_alternatives=rejected,
        user_preference_signal={
            "chose_idx": decision.chosen_alt_idx,
            "user_id": str(user.id),
            "decided_at": datetime.utcnow().isoformat(),
            "weekday": datetime.utcnow().isoweekday(),
            "hour": datetime.utcnow().hour,
        }
    )
    # Dispara execução real (depende de WG1)
    await action_executor.execute_commit(commit)
```

**Frontend.** Reutilizar [DeltaWizard.tsx](../frontend/src/components/twin/DeltaWizard.tsx) para UI de trade-offs. Criar rota `/plan/timeline` nova ou integrar em `/plan/scheduling`. Mostrar:
- 5-10 alternativas lado-a-lado
- Tabela comparativa de KPIs (makespan, €/dia, tardiness, quality)
- Highlight da escolha
- Campo opcional de "motivo de rejeição" para as outras

### B.3 Ligar SQL Server ERP Nelo — Dias 6-8

**Adicionar driver.** Em `requirements.txt`:
```
pyodbc==5.0.1
aioodbc==0.5.0  # async wrapper
```

**Config.** Em `src/shared/config.py`:
```python
class Settings:
    # ... existing ...
    sqlserver_enabled: bool = False
    sqlserver_url: Optional[str] = None  # "mssql+aioodbc://user:pass@host/NELO_ERP?driver=ODBC+Driver+18+for+SQL+Server"
    sqlserver_pool_size: int = 5
```

**Adapter.** Criar `src/infrastructure/erp/sqlserver/nelo_erp.py`:
- Read-only queries para `OrdensFabrico`, `FasesOrdemFabrico`, `Funcionarios`, `Moldes`, `FasesStandardModelos`
- Modo shadow: compara resultado com Excel importado, regista divergências
- Nunca escreve (advisory mode do blueprint)

**Ingestão periódica.** Cron/Dagster job que puxa deltas a cada 15 min.

**Shadow mode 1 semana** antes de activar em produção.

### B.4 Bugs P1 do motor — Dias 8-10

**D3 — quality_weight usado.** Em `_pick_workers`:
```python
def _pick_workers(phase_id, available, quality_weight):
    def score(w):
        skill = state.skill_score(phase_id, w.id)
        quality = state.quality_history(phase_id, w.id)
        speed = 1.0 / (1.0 + (w.free_at - now).total_seconds() / 3600)
        return (skill * quality) * quality_weight + speed * (1 - quality_weight)
    return sorted(available, key=score, reverse=True)[:team_size]
```

**D4 — Backwards scheduling real.** Pré-computa `latest_start` por operação subtraindo durações das fases seguintes + gaps de cura. Usa `earliest = max(earliest, latest_start - buffer)`.

**D5 — Worker selection com skills** — já resolvido em D3.

**F2 — Idle operadores.**
```python
total_worker_minutes_available = n_workers * horizon_minutes
total_worker_minutes_used = sum(op.duration * op.team_size for op in schedule)
idle_ratio = 1.0 - total_worker_minutes_used / total_worker_minutes_available
schedule_result["idle_ratio"] = idle_ratio
```

**F4 — `w_quality_risk = 0.10` default.**

**E1 — `generations: int = 200` default.**

**ME1 — MAP-Elites eixos específicos Nelo.**
```python
def extract_behaviors(schedule):
    lam_util = sum(op.duration for op in schedule if op.phase == "LAMINAGEM") / \
               (lam_workers * horizon_h)
    max_tardiness_days = max(
        (op.end - op.transport_date).days for op in schedule
        if op.is_final_phase
    )
    idle_ratio = schedule["idle_ratio"]
    return (lam_util, max_tardiness_days, idle_ratio)
```

### Critério de saída Sprint B

- [ ] Migration 022 aplicada, coluna `rejected_alternatives` existe
- [ ] Timeline UI mostra 5+ alternativas com KPIs
- [ ] Approve na Timeline grava `rejected_alternatives` com ≥3 entradas
- [ ] `action_executor.execute_commit` aplica plano ao FactoryState (não é mais TODO)
- [ ] SQL Server em shadow mode, zero escritas, query completa ao dataset Nelo
- [ ] `pytest tests/plan/test_commits_learning.py` passa
- [ ] Primeira Timeline end-to-end funcional (demo interna)

---

## SPRINT C (Semanas 5-6) — Motor Correcto + Camada 1 + Ligações

**Objectivo:** CPO v4.0 completo com todos os bugs P1-P2 fechados. Camada 1 de aprendizagem activa (mesmo que com 0 commits, está pronta). 4 ligações inter-módulo fechadas. Trust Index completo (7/8).

### C.1 Model gaps — Dia 1

**Product.sale_price_eur** — Migration 025:
```python
op.add_column("products",
    sa.Column("sale_price_eur", sa.Numeric(18, 4), nullable=True),
    schema="core")
op.add_column("products",
    sa.Column("sale_price_currency", sa.String(3), server_default="EUR"),
    schema="core")
```

**PreferenceRule** — Migration 024:
```python
op.create_table(
    "preference_rules",
    sa.Column("id", PG_UUID, primary_key=True),
    sa.Column("tenant_id", PG_UUID, nullable=False),
    sa.Column("type", sa.String(64), nullable=False),  # temporal_block, tradeoff, operator_affinity
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("predicate", JSONB, nullable=False),  # serialized rule
    sa.Column("confidence", sa.Numeric(3, 2), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),  # detected, confirmed, rejected
    sa.Column("detected_from_commits", JSONB),  # list of commit_ids
    sa.Column("created_at", sa.DateTime, default=sa.func.now()),
    sa.Column("confirmed_at", sa.DateTime),
    sa.Column("confirmed_by", PG_UUID),
    schema="governance",
)
```

### C.2 Camada 1 — PreferenceRuleDetector — Dias 2-4

**Novo módulo** `src/governance/preference_learning/`:

```python
# detector.py (~200 linhas)
class PreferenceRuleDetector:
    async def scan(self, session, tenant_id, window_days: int = 30):
        commits = await self._fetch_commits_with_rejections(session, tenant_id, window_days)
        rules = []
        rules += self._detect_temporal_patterns(commits)
        rules += self._detect_tradeoff_preferences(commits)
        rules += self._detect_operator_affinities(commits)
        rules += self._detect_phase_threshold_rules(commits)
        return [r for r in rules if r.confidence >= 0.7]

    def _detect_temporal_patterns(self, commits):
        # "Gestor rejeita X à sexta" etc.
    def _detect_tradeoff_preferences(self, commits):
        # "Prefere menos setup mesmo com throughput -5%"
    def _detect_operator_affinities(self, commits):
        # "Operator X sempre para fase Y"
    def _detect_phase_threshold_rules(self, commits):
        # "Nunca < 18 pintores"
```

**Cron job** — diário às 03:00, corre `scan()` e grava regras `status=detected` em DB.

**Frontend** — página `/admin/learned-rules`:
- Lista de regras detectadas com confidence
- Botão "Confirmar" / "Rejeitar" / "Modificar"
- Gestor confirma → `status=confirmed` → usado no próximo schedule

### C.3 Ligações inter-módulo — Dias 5-7

**plan ← hr.** Em [src/plan/cpo/state.py](../src/plan/cpo/state.py):
```python
from src.hr.service import HRService

async def load_from_db(cls, session, tenant_id):
    # ... existing ...
    hr = HRService(session, tenant_id)
    workers_availability = await hr.get_workers_availability(date_range)
    # {worker_id: [(start, end, is_available), ...]}
```

**plan ← supply.** Em `_earliest_start_for_op`:
```python
from src.supply.service import StockService

stock = await stock_service.check_materials(op.product_id, op.start_date)
if not stock.available:
    earliest = max(earliest, stock.next_available_date)
```

**plan ← dqa (Trust Index real).** Em [src/plan/api/cpo.py](../src/plan/api/cpo.py) substituir `trust_index = 0.0` por:
```python
from src.dqa.service import TrustIndexService
trust = await trust_service.calculate(tenant_id, evidence_refs)
# Gate para auto-aprovação
if trust.value < 0.75:
    commit.requires_human_approval = True
```

**explain ← plan.** Em [src/explain/api.py](../src/explain/api.py) (criar se não existir):
```python
@router.get("/v1/explain/commit/{commit_id}")
async def explain_commit(commit_id: UUID):
    commit = await commits_service.get(commit_id)
    return {
        "kpis": commit.kpis,
        "alternatives": commit.alternatives,
        "rejected": commit.rejected_alternatives,
        "why_these_choices": generate_explanation(commit),
    }
```

### C.4 Trust Index completo (TI1, TI2) — Dia 8

Adicionar componentes em falta em [src/dqa/trust_v2.py](../src/dqa/trust_v2.py):

- **Provenance (P=0.15):** tier da fonte (sensor > historian > ERP > manual)
- **Anomaly (A=0.10):** `1 - P(anomaly)` usando IsolationForest sobre features do evidence_refs
- **Evidence (E=0.05):** 1 se há commit_id verificável, 0 senão

Redistribuir para somar 1.0: C=0.15, V=0.20, F=0.15, K=0.20, P=0.15, A=0.10, E=0.05 = 1.00 ✓

**Causal Coherence (CC=opcional, 8º):** deixar para Tier 2 (requer DAG).

**Gates activos.** Em [src/shared/api/decisions.py](../src/shared/api/decisions.py):
```python
if trust_index < 0.50:
    raise HTTPException(423, "Trust too low — suggestion-only mode")
if trust_index < 0.75 and action == "auto_approve":
    raise HTTPException(403, "Auto-approval disabled — trust < 0.75")
```

### C.5 Restantes bugs P2 — Dias 9-10

D6 (mold batch com urgência), D7 (soft horizon coerente), F3 (pesos normalizados), FR1 (renomear op_flip_routing), FR2 (running_avg exponencial), E2 (surrogate auto-on), E3 (FRRMAB reward imediato), SN1 (safety-net compara makespan).

### Critério de saída Sprint C

- [ ] Todos os 29 bugs da auditoria V2 fechados (confirmar com grep aos IDs nos commits)
- [ ] `Product.sale_price_eur` populado para ≥80% dos produtos
- [ ] `PreferenceRuleDetector` corre no cron, produz ≥1 regra de teste
- [ ] Trust Index retorna 7 componentes, gates activos
- [ ] Schedule gerado usa stock real + calendário HR real
- [ ] `trust_index` no ScheduleCommit já não é 0.0 — vem do DQA
- [ ] Demo interna: pergunta ao Copilot → plano gerado → Timeline → aprovação → regra detectada no dashboard

---

## PARTE 4 — MÉTRICAS DE SUCESSO GLOBAIS

**Ao fim dos 3 sprints (6 semanas):**

| Métrica | Baseline | Meta | Verificação |
|---|---|---|---|
| Bugs auditoria V2 fechados | 0/29 | 29/29 | grep dos IDs nos commits |
| Bugs novos (NEW-1-4) fechados | 0/4 | 4/4 | idem |
| Regras domínio Nelo implementadas | 2/10 | 10/10 | tabela §2.2 com todos ✅ |
| Ligações inter-módulo | 0/8 | 7/8 (sandbox opcional) | grep imports |
| Migrations criadas | 21 | 26 (022-025a) | `alembic history` |
| `pytest` passing | ~? | ≥80% | CI log |
| Commits com `rejected_alternatives` ≥3 | 0% | 100% | query SQL |
| SQL Server ligado | Não | Shadow mode | logs de queries |
| Regras aprendidas detectadas | 0 | ≥3 | tabela `preference_rules` |
| Demo end-to-end executável | Não | Sim | script demo 30min |

**Demo script final (Sprint C fim de semana 6):**

1. Gestor abre Factory Map → vê 740 barcos em produção (dados reais do SQL Server shadow)
2. Copilot: "Quantos K1 Vanquish atrasados?" → responde com número real
3. Clicar "Replanear" → CPO v4.0 corre 60s → devolve 5 alternativas no Timeline
4. Gestor vê trade-offs (makespan vs €/dia vs setup) → aprova uma → rejeita 4
5. ActionExecutor aplica ao state → commit SHA registado
6. Rejected_alternatives gravado em DB
7. Camada 1 detecta 1ª regra ("prefere menos setup se €/dia diferença <5%") e pede confirmação
8. Gestor confirma regra → próximo schedule aplica-a

---

## PARTE 5 — RISCOS E MITIGAÇÕES

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| CEO responde que `OFCH_GRAVIDADE` é o contrário do que pensávamos | Média | 35 ficheiros com lógica invertida | Sprint A inclui enviar pergunta no Dia 2. Se resposta vier no Dia 5, refactor fica Sprint B |
| SQL Server schema divergente do Excel | Alta | Adapter precisa refactor | Shadow mode durante 1 semana detecta divergências antes de depender |
| Dataset Excel 2020-21 enviesa calibrações | Alta | Tempos de referência errados | Usar só dados ≥2023 para calibrações do scheduler |
| GPU (RTX 5060 Ti 16GB) sem headroom para LLM + ML concorrente | Média | Copilot fica offline em picos | Monitorizar VRAM, quantização Q4, fallback heurístico quando OOM |
| Migration 022 falha em produção | Baixa | Down-time | Testar em staging primeiro; migration reversível |
| `PreferenceRuleDetector` gera falsos positivos | Alta | Regras más aprendidas | Todas as regras requerem confirmação explícita do gestor |
| Camada 1 precisa ≥30 commits para ser útil | Certa | Sistema parece "não aprender" nas 1ªs semanas | Pré-popular com 5-10 regras de domínio (ex: "Laminagem sempre par") para dar sinal de vida |
| `throughput_eur_day` requer `sale_price` populado | Alta | Fitness F1 continua 0 sem dados | Sprint C dia 1 inclui data entry task para popular preços (conversar com comercial da Nelo) |

---

## PARTE 6 — FORA DE ÂMBITO (Tier 2/3 — pós demo)

Depois da demo (a partir da semana 7):

**Tier 2 (8 semanas — Sprints D/E/F/G):**
- LLM Causal: `NELO_DAG` em código, `CausalChain` Pydantic, 4 causas Aristóteles no ExplainDrawer, Mill's 5 methods
- POETIQ loop iterativo (2-5 iterações)
- Camada 2 aprendizagem (`AdaptiveFitnessWeights`, precisa 50+ commits)
- Causal Coherence (8º Trust)
- Frontend: PWA offline (Workbox+Dexie), i18n (PT/DE-AT/EN), 3 Umwelts
- Property-based tests (Hypothesis)
- 29 outros módulos TSX a polir (Factory Map visual real, Alert Center isolado)

**Tier 3 (6+ meses — após 500+ commits em produção):**
- DoWhy-GCM — atribuição causal formal com 22 nós + confundidores
- PCMCI+ / tigramite — descoberta causal semanal
- Camada 3 — DPO fine-tune do Gemma (500+ pares de preferência)
- Camada 4 — ABLkit (abductive learning: kernel corrige LLM)
- RLM (Layer 1) — REPL Python tipado para factory state
- RAG HyDE + multilingual-e5-large
- Entropia causal na fitness
- Dataset causal 7-tipos (2500+ pares sintéticos)

---

## PARTE 7 — PERGUNTAS EM ABERTO AO CEO (enviar Sprint A Dia 2)

```
Bom dia. 3 perguntas para calibrar o software:

1. Manutenção dos moldes — quantos usos aguenta um molde antes
   de começar a causar defeitos? Ou fazem manutenção por
   inspecção visual sem número fixo?

2. No campo OFCH_GRAVIDADE dos erros, o que significam
   1 e 2? É severidade (1=menor, 2=maior)? Tipo de defeito
   (estético vs estrutural)?

3. Laminagem com 1 trabalhador — 11,5% dos registos mostram
   Laminagem feita por 1 pessoa. São sempre erros de registo
   ou há casos legítimos?

Para referência — CoeficienteX (prémio €) e data transporte
(camião) já confirmaste.
```

---

## ANEXO — CHECKLIST AGREGADO DOS 34 FIXES

### P0 — 15 itens (Sprint A + B)

- [ ] CX1 Remover 3 comentários errados
- [ ] CX2 Substituir critério pair por mediana team_size histórico
- [ ] CX3 Auditar ausência em contas de duração
- [ ] CX4 Mover para src/profit/ com migration 025a
- [ ] CX5 Alimentar CS01 com prémios reais
- [ ] D1 Setup counter real
- [ ] D2 16 curing constraints (migration 023)
- [ ] F1 Throughput €/dia real (depende de CX + product.sale_price)
- [ ] WG1 Execute actual action
- [ ] WG2 Rollback com parent commit
- [ ] CO1 rejected_alternatives + user_preference_signal (migration 022)
- [ ] C1 Routing A/B usado no decoder
- [ ] ST1 phase_transition_gaps no FactoryState
- [ ] NEW-1 Normalização case pair_assignment
- [ ] NEW-2 Validar skill em _pick_workers

### P1 — 10 itens (Sprint B + C)

- [ ] D3 quality_weight usado
- [ ] D4 Backwards scheduling real
- [ ] D5 Worker selection com skills
- [ ] F2 Idle operadores calculado
- [ ] F4 w_quality_risk default 0.10
- [ ] E1 Generations default 200
- [ ] ME1 MAP-Elites eixos Nelo-específicos
- [ ] TI1 Trust Index 7 componentes
- [ ] FR1 Renomear op_flip_routing
- [ ] NEW-3 _norm() validação de sinal

### P2 — 8 itens (Sprint C)

- [ ] D6 Mold batch com urgência
- [ ] D7 Soft horizon coerente
- [ ] F3 Pesos normalizados (ou documentar escala)
- [ ] FR2 Running_avg exponencial
- [ ] E2 Surrogate auto-on
- [ ] E3 FRRMAB reward imediato
- [ ] SN1 Safety-net compara makespan
- [ ] NEW-4 Surrogate context recalc

### P3 — 4 itens (Sprint C se sobrar tempo)

- [ ] C2 quality_weight range alinhado
- [ ] C3 setup_grouping_gap gene
- [ ] ME2 explain_representative()
- [ ] TI2 Consistency z-score real

### Migrations — 5 novas

- [ ] 022 schedule_commit_learning_fields
- [ ] 023 phase_transition_gaps
- [ ] 024 preference_rules
- [ ] 025 product_sale_price
- [ ] 025a phase_bonus_payout (CoeficienteX)

---

**Fim do plano 22/04.**

Este documento substitui as iterações anteriores e é a fonte única de verdade para os próximos 6 sprints. Actualizações devem manter a estrutura: auditoria → correcções priorizadas → sprint plan detalhado → métricas de sucesso.
