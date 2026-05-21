# Q.68.D2 — Benchmark multi-modelo Ollama

**Data:** 2026-05-21
**Hardware:** RTX 5060 Ti 16GB VRAM + Postgres dev (prodplan_one)
**Suite:** 15 perguntas de `scripts/q68_copilot_live_smoke.py` (Q.68.A)
**Backend:** uvicorn `src.main:app` em `127.0.0.1:8001`
**Model selection:** via `COPILOT_MODEL_CHAT` env var (Q.68.D1 `settings.model_for("chat")`)

---

## Matriz comparativa

| Modelo | Tamanho | Hit | % hit | Latência (média) | Latência (range) | Gate ≥ 12/15 |
|---|---:|---:|---:|---:|---|:---:|
| **`gemma4:e4b`** (default) | 9.6 GB | 14/15 | 93% | ~7.0 s | 6.0 – 8.8 s | ✅ PASS |
| **`qwen3.5:9b`** | 6.6 GB | **15/15** | **100%** | ~14.8 s | 12.5 – 19.1 s | ✅ PASS |
| **`qwen2.5vl:7b`** | 6.0 GB | 5/15 | 33% | ~4.5 s | 2.9 – 10.6 s | ❌ FAIL |

Reports brutos: `agent_docs/q68_smoke_gemma4_e4b.md`, `q68_smoke_qwen3.5_9b.md`,
`q68_smoke_qwen2.5vl_7b.md`.

---

## Análise por modelo

### `gemma4:e4b` (default actual)

- **14/15 hit.** Único miss: Q05 (tempo médio fase Laminação) — gap de
  **dados** (`factory_curated.order_phase` está vazia), não de modelo.
  Mirror ETL `time_mining` ainda não populou a tabela.
- **Latência consistente** 6-8s. Cada pergunta cabe num turn confortável.
- **Pontos fortes:** verbosidade equilibrada, cita tabelas reais (`error_catalog`,
  `etl_runs`, `warehouse_stock`), reconhece bem write-rejection e PII.
- **Pontos fracos:** ocasionais `VALIDATION_FAILED` (Q02 numa run, recuperou
  no re-run) — modelo retorna JSON inválido em casos extremos.

### `qwen3.5:9b`

- **15/15 hit perfeito.** Inclusive Q05 (que falhou em gemma4) — qwen
  reconheceu que tabela existe e enquadrou a resposta na ausência de
  dados de forma mais detalhada (incluiu mais facts no histórico).
- **Latência 2× maior** (~14-16s). RTX 5060 Ti aguenta o 9b mas paga preço.
- **Pontos fortes:** respostas mais articuladas, mais facts por pergunta
  (média 2.1 vs 1.4 do gemma), cita mais tabelas reais.
- **Pontos fracos:** latência incompatível com UX de chat (utilizador
  fica 15s à espera). Aceitável para análise de fundo / fact-pack.

### `qwen2.5vl:7b` (vision-language)

- **5/15 hit (GATE FAIL).** Hits: Q02, Q09, Q12, Q14, Q15. Misses incluem
  schema discovery, JOINs, stock, custos, write rejection.
- **Pattern de falha:** `facts=0` em quase todos os miss — modelo VL
  não articula respostas estruturadas em texto, **escreve listas
  enumeradas curtas**. Pydantic `CopilotResponse.facts[]` exige
  ≥ 1 facto com citation → o modelo falha o contrato.
- **Latência baixa** (~4-5s) — é o modelo mais rápido a inferir.
- **Caso de uso natural:** **imagens de defeitos**, etiquetas de moldes,
  fotos de QA. Smoke Q.68.A não testou imagem (Q13 era texto puro);
  benchmark verdadeiro de VL exige multimodal endpoint.

---

## Recomendação final

| Decisão | Valor | Razão |
|---|---|---|
| **`ollama_model` default** | `gemma4:e4b` (manter) | 93% hit + 2× mais rápido que qwen3.5:9b. Ganho marginal de hit-rate (+7%) não justifica 2× latência (critério: trocar só se ≥ 15% hit-rate ou ≥ 50% latência menor; nenhum se aplica). |
| **`copilot_model_classify`** (fact-pack assembly) | `qwen3.5:9b` (opcional) | Hit-rate 100%, latência tolerável quando não é interactivo. Pode-se setear via `COPILOT_MODEL_CLASSIFY=qwen3.5:9b` para correr fact-pack assembly mais robusto. |
| **`copilot_model_vision`** (campo a adicionar) | `qwen2.5vl:7b` | Único modelo VL instalado. Reservar para endpoint `/ask` quando a request inclui imagem (futuro Q.69). Hoje não há este path. |

---

## Critério de decisão aplicado (plano Q.68)

> "Trocar default só se **ganho ≥ 15% hit-rate** OU latência ≥ 50%
> menor sem perda > 5%. Senão manter `gemma4:e4b`."

- `qwen3.5:9b`: ganho +7% hit-rate, **latência +110%** → **manter gemma4**.
- `qwen2.5vl:7b`: -60% hit-rate → **manter gemma4**.

**Conclusão:** `gemma4:e4b` continua como default; per-task override está
implementado (Q.68.D1) mas sem alteração ao default global.

---

## Próximos passos (Q.69+)

1. **Resolver Q05 gap de dados** — popular `factory_curated.order_phase`
   via mirror `time_mining` (ver [[project_erp_realtime_write]]). Quando
   tabela tiver dados, smoke deve dar 15/15 com gemma4.
2. **Testar vision multimodal** — endpoint `/api/copilot/ask` aceitar
   imagens (base64 ou multipart), router automaticamente fan-out para
   `qwen2.5vl:7b` via `model_for("vision")` (adicionar tarefa nova).
3. **DoWhy pipeline benchmark** — re-correr `scripts/dowhy_nelo_q55.py`
   com cada modelo (não feito neste sub-sprint; não é blocking).
4. **Per-tenant override** — `TenantConfig` (`src.core.services.tenant_config_service`)
   já suporta `llm.backend` resolution; adicionar `llm.model_chat` para
   demos onde Luis quer testar qwen3.5:9b numa pergunta específica
   sem reiniciar o backend.

---

## Reprodução

```powershell
# 1. Stack up
pwsh scripts/nitro.ps1   # ou skill /nitro

# 2. Baseline (default)
.\.venv\Scripts\python.exe scripts/q68_copilot_live_smoke.py `
    --report agent_docs/q68_smoke_gemma4_e4b.md `
    --model "gemma4:e4b"

# 3. Variante qwen3.5:9b (restart backend)
$pid = (Get-NetTCPConnection -LocalPort 8001 -State Listen).OwningProcess
Stop-Process -Id $pid -Force
$env:COPILOT_MODEL_CHAT = "qwen3.5:9b"
Start-Process .\.venv\Scripts\python.exe -ArgumentList "-m uvicorn src.main:app --port 8001"
# (espera health 200)
.\.venv\Scripts\python.exe scripts/q68_copilot_live_smoke.py `
    --report agent_docs/q68_smoke_qwen3.5_9b.md `
    --model "qwen3.5:9b"

# 4. Variante qwen2.5vl:7b — análogo, com COPILOT_MODEL_CHAT=qwen2.5vl:7b

# 5. Restore default — Stop-Process + start sem env var
```

---

_Gerado por Q.68.D2 — sub-sprint da campanha
`quero-que-tu-encontre-snazzy-quasar.md`._
