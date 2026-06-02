"""Q.95.2 — Contrato multiagente do Cube semantic layer.

**Planta partilhada** que qualquer agente (humano ou LLM) lê antes de construir
uma medida nova. Codifica numa fonte ÚNICA as regras de unidade, soma e
correspondência de intenção que de outra forma viveriam espalhadas em
[query.py], [interpret.py] e [narrate.py].

═══════════════════════════════════════════════════════════════
Estrutura: DUAS zonas separadas
═══════════════════════════════════════════════════════════════

**ZONA FIXA** (só o Luís escreve; agentes leem, nunca alteram):
    1. `CanonicalUnit` — enum das unidades canónicas reconhecidas no sistema.
    2. `CANONICAL_DIMENSIONS` — dimensões partilhadas entre medidas.
    3. `SUM_COMPATIBILITY` — matriz de soma (qual unidade pode somar com qual).
    4. `_DERIVED_MEASURE_PATTERNS` — regex de medidas derivadas inexistentes.

**ZONA DE REGISTO** (agentes declaram a sua medida aqui):
    `MEASURE_REGISTRY` — dict {nome → MeasureSpec}. Cada nova medida é
    REGISTADA aqui antes de poder ser invocada no Cube. Se uma medida precisa
    de uma unidade/dimensão fora da zona fixa, o agente PARA e reporta — não
    inventa.

═══════════════════════════════════════════════════════════════
API exposta (única forma de outros módulos usarem o contrato)
═══════════════════════════════════════════════════════════════
    - `is_physical_unit_measure(name) -> bool`
    - `is_monetary_measure(name) -> bool`
    - `is_fractional_measure(name) -> bool`            (Q.96)
    - `is_derived_measure_request(question) -> str | None`
    - `is_causal_question(question) -> str | None`     (Q.96)
    - `is_unsupported_concept_request(question) -> str | None`  (Q.97)
    - `is_period_mismatch(question, query, today) -> str | None` (Q.97)
    - `can_sum_measures(measures) -> tuple[bool, str | None]`
    - `assert_soma_safe(query) -> list[str]`           Q.95.1 anti-soma-cega
    - `assert_dims_supported(query) -> list[str]`      (Q.97) enforce dims

Subsume estruturalmente:
    - Q.95.1 c03 (soma cega sem filtro) — `assert_soma_safe`.
    - Q.95.1 c07 (substituição de medida) — `is_derived_measure_request`.
    - Q.96 causalidade — `is_causal_question`.
    - Q.96 fraction range — apresentação % via `is_fractional_measure`.
    - Q.97 FIX 1 (mês discordante) — `is_period_mismatch`.
    - Q.97 FIX 2 (dims declarativas → enforced) — `assert_dims_supported`.
    - Q.97 FIX 3 (refugo/scrap não-registado) — `is_unsupported_concept_request`.
"""
from __future__ import annotations

import datetime as _dt
import re
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from .query import CubeQuery


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ ZONA FIXA — só Luís escreve. Agentes leem.                               ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class CanonicalUnit(str, Enum):
    """Unidades canónicas do sistema. **Não inventar valores aqui sem Luís.**

    A unidade REAL de uma row (kg vs tambor vs m²) vive numa dimensão
    (`unidade_id`); estes são os AGRUPAMENTOS canónicos no nível superior.
    Soma só faz sentido entre rows com a MESMA `CanonicalUnit` E a mesma
    sub-unidade (kg+kg sim, kg+m² não, mesmo ambos sendo QUANTIDADE_FISICA).
    """

    QUANTIDADE_FISICA = "quantidade_fisica"   # kg, m², m, unidade, tambor, …
    DINHEIRO = "dinheiro"                     # €
    TEMPO = "tempo"                           # horas (sempre converter na origem)
    CONTAGEM = "contagem"                     # int adimensional (nº OFs, nº peças)
    FRACAO = "fracao"                         # 0-1 interno (apresentar como % só na narração)
    # Q.107 Onda 4 — temperatura em °C com agregação MAX/AVG (não-SUM).
    # SUM(temperatura) é semanticamente inválido; o cube agrega MAX ou AVG.
    # Medidas TEMPERATURA têm `aggregation` no MeasureSpec.
    TEMPERATURA = "celsius"


# Dimensões canónicas partilhadas. Agentes cruzam medidas pela MESMA dim,
# não por variantes próprias.
CANONICAL_DIMENSIONS: frozenset[str] = frozenset({
    "tempo",        # data, data_inicio, data_fim, …
    "material",     # nome canónico do material
    "unidade_id",   # sub-unidade dentro de QUANTIDADE_FISICA/DINHEIRO
    "fase",         # Q.96: FP_NOME canónico (Laminagem, Pintura, …)
    "estufa",       # Q.100: nome canónico da estufa de cura (Estufa 60, …)
    "cliente",      # Q.102: E_NOME canónico do cliente PHC (via 2-hop JOIN)
    "disciplina",   # Q.102: TP_NOME da disciplina comercial (Canoe Sprint, …)
    "destino",      # Q.104: DEST_NOME (Nacional/UE/Outros/Todos)
    "tipo_transporte",  # Q.104: TRTP_NOME (Camião/Barco/Avião/Normal/...)
    "culpa",        # Q.104: TRDTCL_NOME (Cliente/Nelo/Transportador) — CLASSIFICAÇÃO NELO
    "produto",      # Q.107: P_NOME canónico do modelo/produto (K1, K2, K4, ...)
    "pais",         # Q.107: E_PAIS canónico (Portugal, Espanha, Itália, ...)
    "gravidade",    # Q.107: OFCH_GRAVIDADE (1=leve, 2=intermédio, 3=grave)
    "local",        # Q.107: OFCH_LOCAL (Deck, Casco, Proa, ...) — zona física defeito
    "epoca",        # Q.108.B: EPHCF_EPOCA — ano DESPORTIVO (Out-Set, ≠ ano calendário)
    "agente",       # Q.108.C: AF_E_ID via entidade.E_NOME (59 agentes NELO).
                    # APLICA-SE A comercial_facturacao_agente.total APENAS
                    # (fonte AGENTE_FATURACAO independente de EPHCF; NUNCA
                    # cruzar com comercial_facturacao.total — dupla contagem).
    "molde_id",     # Q.108.E.2: ERP OF_OF_ID_MLD (parent OF que é o molde).
                    # Populado em quality.rework_entry.mold_id pelo backfill
                    # Q.108.E.1. Aplica-se a qualidade_rework_por_molde.*.
    "sensor_id",    # Q.108.W1: SENSOR_ID em factory_raw.iot_sensor — chave
                    # física do sensor (drill-down dentro de estufa).
    "action_type",  # Q.108.W1: ACTION_TYPE em shared.decision_runs (Q.17
                    # whitelist: INCREASE_SS, ADJUST_PRICE, RESCHEDULE_OF, …).
    "fase_sequencia",  # Q.108.W2: FP_SEQUENCIA (1..29 produtivas, 30+ terminais).
    "fase_origem",  # Q.108.W2: fase a sair em transitions.
    "fase_destino",  # Q.108.W2: fase a entrar (LEAD).
    "source",       # Q.108.W3: core.etl_run.source — nome da mirror.
    "entity_type",  # Q.108.W3: core.audit_log.entity_type.
    "action",       # Q.108.W3: core.audit_log.action (INSERT/UPDATE/DELETE).
    "route",        # Q.108.L.2: copilot_request_log.route — endpoint REST.
    "mold_code",    # Q.108.J.2: plan.mold.mold_code = ERP MLD_ID.
    "molde_nome",   # Q.108.J.2: plan.mold.name — nome humano do molde.
    "mold_type",    # Q.108.J.2: plan.mold.mold_type — tipo (tipo-1, tipo-2, …).
    "modelo",       # Q.108.F.3b: factory_raw.produto.P_NOME — K1/K2/K4/...
    "modelo_id",    # Q.108.F.3b: factory_raw.produto.P_ID.
    "work_order_id",  # Q.108.G: supply.inventory_ledger_entries.work_order_id.
    "sku_id",       # Q.108.G: P_ID stringificada — chave material no ledger.
    "operador_id",  # Q.108.M: AT_E_ID — FK para ENTIDADE (operador NELO).
    "fase_id",      # Q.108.M: FP_ID — FK para FASES_PRODUCAO.
    "colaborador",  # Q.106: ENTIDADE.E_NOME via E_ID — colaborador NELO
                    # (158 activos canónicos). Decisão Luís: dim normal,
                    # permite drill por pessoa + ranking individual.
    "departamento",  # Q.106: ENTIDADE_TIPO.ENT_NOME via E_ENT_ID — cargo
                     # canónico (Laminador, Pintor, Acabador, Lixador,
                     # Multitarefa, Escritório, Manutenção, …).
    # Futuro (registar com PR ao Luís antes de usar): "maquina", "turno", "of",
    # "transportadora",
    # "categoria_produto" (P_PCONT_ID) — adiada Q.108.B porque
    # v_consumo_material_dia filtra P_PCONT_ID=1 (MP estrita); precisa
    # view nova v_consumo_categoria_dia para ter uso real (Q.108.D).
})


# Matriz de soma — invariante D1/D3/D5/D6: duas medidas só somam se partilham
# a MESMA CanonicalUnit. Cross-unit é PROIBIDO (€ + horas, kg + contagem, …).
# Mesma unidade É PERMITIDA (D6: custo + custo soma; D5: custo único unit_id
# soma sem mistura).
SUM_COMPATIBILITY: dict[CanonicalUnit, frozenset[CanonicalUnit]] = {
    CanonicalUnit.QUANTIDADE_FISICA: frozenset({CanonicalUnit.QUANTIDADE_FISICA}),
    CanonicalUnit.DINHEIRO: frozenset({CanonicalUnit.DINHEIRO}),
    CanonicalUnit.TEMPO: frozenset({CanonicalUnit.TEMPO}),
    CanonicalUnit.CONTAGEM: frozenset({CanonicalUnit.CONTAGEM}),
    CanonicalUnit.FRACAO: frozenset({CanonicalUnit.FRACAO}),
    # Q.107 Onda 4: TEMPERATURA é cross-row NÃO-aditiva (SUM inválido).
    # A matriz aqui só diz com que outras units cross-measure pode ser
    # combinada (i.e., na mesma agregação) — TEMPERATURA isolada. A
    # agregação real (MAX/AVG) é controlada pelo campo `aggregation` da
    # MeasureSpec, não pela matriz.
    CanonicalUnit.TEMPERATURA: frozenset({CanonicalUnit.TEMPERATURA}),
}


# Q.95.1 — padrões PT-PT de medida DERIVADA inexistente (preço/kg, €/X, rácio,
# taxa, média de, "quanto sai cada kg", custo unitário). Defesa primária está
# no prompt [cube_interpret.md] regra 6 — este regex é a rede pós-pergunta
# para o caso do LLM ignorar a regra.
#
# Q.96 cuidado: "taxa de defeitos" é medida REGISTADA (qualidade.taxa_defeitos),
# NÃO derivada. O padrão `\btaxa\s+de\b` apanharia "taxa de defeitos" como
# falso positivo. Exclusão explícita: `taxa de defeitos` / `taxa de defeito` /
# `taxa de scrap` (futuro) — não bloqueiam.
_DERIVED_MEASURE_PATTERNS = re.compile(
    r"(?:"
    r"pre[çc]o\s+(?:por|unit[áa]rio|m[ée]dio|/)"
    r"|€\s*/"
    r"|euros?\s+por\s+(?:kg|litro|unidade|hora|m[²³23])"
    r"|/\s*(?:kg|litro|unidade|hora|m[²³23])"
    r"|\brácio\b|\bracio\b"
    r"|\btaxa\s+de\s+(?!defeitos?|scrap)"  # Q.96: excluir taxa de defeitos
    r"|\bm[ée]dia\s+de\b"
    r"|\b(?:quanto|qual)\s+(?:sai|custa)\s+cada\s+(?:kg|litro|unidade|hora|m[²³23]|tambor)"
    r"|\bcusto\s+unit[áa]rio\b"
    r"|\bvalor\s+unit[áa]rio\b"
    r")",
    re.IGNORECASE,
)


# Q.96 — padrões PT-PT de pergunta CAUSAL. O Cube responde "quanto/qual",
# não "porquê". Causalidade é domínio separado (NELO_DAG / diagnostic intent).
# Alinhado com `_DIAGNOSTIC_TRIGGERS` em [src/copilot/intent_router.py] — se
# o utilizador chega ao /ask-cube com pergunta causal, abstemos com referência
# clara à rota correcta.
_CAUSAL_QUESTION_PATTERNS = re.compile(
    r"(?:"
    r"\bporqu[eê]\b"
    r"|\bporque\s+(?:é\s+que|que|isso|isto|caiu|subiu|baixou|aconteceu|aumentou)"
    r"|\bpor\s+que\s+(?:raz[ãa]o|motivo|é\s+que)"
    r"|\b(?:o\s+que|qu[eê])\s+(?:causou|provocou|originou)"
    r"|\bcausa\s+(?:da|do|de|das|dos|raiz)"
    r"|\braiz\s+(?:do|da|de|deste|desta)"
    r"|\bgargalo\b|\bgargalos\b"
    r"|\bdiagn[óo]stico\b"
    r"|\binvestigar\b"
    r")",
    re.IGNORECASE,
)


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ ZONA DE REGISTO — agentes declaram a SUA medida AQUI.                    ║
# ╠══════════════════════════════════════════════════════════════════════════╣
# ║ Antes de adicionar uma entrada nova:                                     ║
# ║   1. A `unit` tem de ser uma `CanonicalUnit` válida (da zona fixa).      ║
# ║   2. Todas as `dimensions_supported` têm de estar em                     ║
# ║      `CANONICAL_DIMENSIONS`.                                             ║
# ║   3. Se a medida precisa de unidade/dimensão fora da zona fixa,          ║
# ║      PARA e reporta ao Luís para a acrescentar. NÃO inventes.            ║
# ║   4. Preenche `business_decision` com a decisão Fase 0 (Q.94.A) que      ║
# ║      define a semântica desta medida (fonte, fórmula, NULL semantics).   ║
# ╚══════════════════════════════════════════════════════════════════════════╝


class MeasureSpec(BaseModel):
    """Declaração de uma medida dentro do contrato."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str                                  # ex: "consumo_material.consumo"
    unit: CanonicalUnit
    dimensions_supported: frozenset[str]
    business_decision: str
    # Q.105.A — campos para retrieval BM25+embedding de medidas (remove o
    # teto do prompt, evita LLM perder disciplina com 11+ cubes).
    # `description`: frase curta PT-PT (≤120 chars) usada para indexar.
    # `synonyms`: termos PT-PT (verbos, sinónimos, contexto domínio) que o
    # utilizador pode usar; usados pelo BM25 sobre tokens normalizados.
    # Default vazio para retro-compatibilidade — `_validate_registry` emite
    # warning visível mas não bloqueia.
    description: str = ""
    synonyms: tuple[str, ...] = ()
    # Q.107 Onda 4 — agregação cross-row. Default SUM (aditivo). Para
    # TEMPERATURA usar MAX ou AVG (SUM(°C) é inválido). FRACAO é ratio
    # measure no Cube (SUM(num)/SUM(den)) — não usa este campo.
    aggregation: str = "SUM"  # "SUM" | "MAX" | "AVG"


MEASURE_REGISTRY: dict[str, MeasureSpec] = {
    "consumo_material.consumo": MeasureSpec(
        name="consumo_material.consumo",
        unit=CanonicalUnit.QUANTIDADE_FISICA,
        dimensions_supported=frozenset({"tempo", "material", "unidade_id"}),
        business_decision=(
            "Q.94.A: SUM(MOV_QUANTIDADE × COALESCE(P_UNI_MOV_FACTOR, 1)) na "
            "unidade-base do produto. Filtro MOV_TPMOV_ID=11 + P_PCONT_ID=1. "
            "NUNCA somar sobre unidade_id distintos (kg + tambor)."
        ),
        description="Quantidade de matéria-prima consumida (kg, tambor, m², …)",
        synonyms=(
            "consumo", "consumimos", "consumido", "gasto", "gastámos",
            "gasta", "usado", "usámos", "usaram", "matéria-prima",
            "material", "resina", "gelcoat", "acetona", "fibra", "cola",
            "kg", "quantidade", "saiu", "saiu para producao",
            "saiu para produção", "saída para produção", "dispensado",
        ),
    ),
    "consumo_material.custo": MeasureSpec(
        name="consumo_material.custo",
        unit=CanonicalUnit.DINHEIRO,
        dimensions_supported=frozenset({"tempo", "material", "unidade_id"}),
        business_decision=(
            "Q.94.A.0.2: SUM(MOV_QUANTIDADE × NULLIF(P_PRECOCUSTO, 0)) em €. "
            "P_PRECOCUSTO em €/unidade-base; validado vs Resina Lavesan EN 720 "
            "= 7,78 €/kg (Abril 2026 = 8 820 €). NULL para sem preço (NUNCA €0)."
        ),
        description="Custo em € da matéria-prima consumida (interno, P_PRECOCUSTO)",
        synonyms=(
            "custo", "custou", "custa", "custaram", "custos",
            "gastámos", "gasto", "preço", "valor", "euros", "€",
            "matéria-prima", "material", "resina", "gelcoat", "acetona",
            "consumimos", "comprámos",
        ),
    ),
    "consumo_material.n_movimentos": MeasureSpec(
        name="consumo_material.n_movimentos",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "material", "unidade_id"}),
        business_decision=(
            "COUNT(*) de linhas em MOVIMENTO. Adimensional — soma sempre OK."
        ),
        description="Número de movimentos (linhas de stock) de matéria-prima",
        synonyms=(
            "movimentos", "linhas", "lançamentos", "transações", "vezes",
            "frequência", "número de", "quantos", "matéria-prima",
        ),
    ),
    "qualidade.taxa_defeitos": MeasureSpec(
        name="qualidade.taxa_defeitos",
        unit=CanonicalUnit.FRACAO,
        dimensions_supported=frozenset({"tempo", "fase"}),
        business_decision=(
            "Q.96.A.0: taxa = SUM(defeitos)/NULLIF(SUM(total_checks),0) sobre "
            "marts.v_taxa_defeitos_dia. Ratio measure no Cube — NUNCA SUM(taxa). "
            "Numerador: OFCH_GRAVIDADE >= 1 (1=leve, 2=intermédio, 3=grave). "
            "Denominador: COUNT(*) checks (taxa por OFs distintas deu 120%, "
            "refutado). Gravidade=0 = template (NÃO conta como defeito). "
            "Anchor: Laminagem em Abril 2026 = 331/5341 = 6,20% no espelho "
            "factory_raw (vs ~5,3% Q.81 em MAR-KAYAKS — diferença é cobertura "
            "do espelho: 97k de 3M rows). OFCH_LOCAL (zona física) NÃO "
            "espelhada — dim 'zona' fora do escopo Q.96 (pendente Q.98)."
        ),
        description="Taxa (%) de defeitos detectados em checks de qualidade",
        synonyms=(
            "taxa", "percentagem", "defeitos", "qualidade", "checklist",
            "OFCH", "rejeitados", "problemas", "falhas", "defeituosos",
            "controlo", "inspeção",
        ),
    ),
    "qualidade.defeitos": MeasureSpec(
        name="qualidade.defeitos",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "fase"}),
        business_decision=(
            "Q.96: contagem absoluta de defeitos reais "
            "(OFCH_GRAVIDADE >= 1) — numerador isolado da taxa. CONTAGEM "
            "adimensional, soma sempre OK."
        ),
        description="Número absoluto de defeitos (GRAVIDADE>=1) por fase",
        synonyms=(
            "defeitos", "defeituosos", "problemas", "falhas", "rejeitados",
            "número de defeitos", "quantos defeitos", "OFCH", "checklist",
            "qualidade",
        ),
    ),
    "qualidade.total_checks": MeasureSpec(
        name="qualidade.total_checks",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "fase"}),
        business_decision=(
            "Q.96: contagem total de checks (templates + defeitos) — "
            "denominador da taxa. CONTAGEM adimensional."
        ),
        description="Número total de checks de qualidade (denominador da taxa)",
        synonyms=(
            "checks", "checklist", "verificações", "inspeções", "controlos",
            "templates", "qualidade", "total checks",
        ),
    ),
    # ── Q.99 Onda 1: 3 medidas Produção CONTAGEM em paralelo ──
    "producao_ofs_em_curso.total": MeasureSpec(
        name="producao_ofs_em_curso.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"fase"}),
        business_decision=(
            "Q.99 Onda 1 / Agente A: contagem de OFs em curso "
            "(FP_SEQUENCIA<30, critério canónico Q.79). Fonte: "
            "marts.v_ofs_em_curso_snapshot. Anchor factory_raw espelho: "
            "4 233 OFs activas em 32 fases (top: Laminagem peças 1 233, "
            "Corte peças 1 100). CONTAGEM adimensional. Snapshot do "
            "estado actual — dim 'tempo' NÃO suportada (pergunta 'este "
            "mês' → abstain via assert_dims_supported). Dim 'material' "
            "fora do escopo."
        ),
        description="Número de OFs em curso (não-terminais, snapshot actual)",
        synonyms=(
            "OFs", "ordens de fabrico", "em curso", "abertas", "activas",
            "produção", "a fabricar", "kayaks", "barcos em produção",
            "encomendas activas",
        ),
    ),
    "producao_pecas_laminadas.total": MeasureSpec(
        name="producao_pecas_laminadas.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "fase"}),
        business_decision=(
            "Q.99 Onda 1 / Agente B: contagem de fases de laminagem "
            "terminadas (OFFP_DATAFIM NOT NULL, FP_NOME ILIKE '%lamin%'). "
            "Plano B porque vPecasLaminadas não está espelhada em "
            "factory_raw. Fonte: marts.v_pecas_laminadas_mes (ano_mes × "
            "fase). Anchor Abril 2026 = 2 393 (Lam peças 1 122 + Lam 611 "
            "+ Infusão 383 + Não Laminado 191 + Double Dutch 86). "
            "CONTAGEM adimensional. NOTA: 'Não Laminado' (FP_ID=11) é "
            "apanhado pelo ILIKE mas é o oposto semanticamente — "
            "refinamento pendente analista."
        ),
        description="Contagem de fases de laminagem terminadas por mês",
        synonyms=(
            "peças laminadas", "laminagem", "laminadas", "infusão",
            "double dutch", "laminagem peças", "fases terminadas",
            "peças por mês",
        ),
    ),
    "producao_ofs_por_fase.total": MeasureSpec(
        name="producao_ofs_por_fase.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"fase"}),
        business_decision=(
            "Q.99 Onda 1 / Agente C: contagem de OFs em curso POR fase "
            "(drill-down de producao_ofs_em_curso.total — mesma fonte e "
            "critério Q.79). Fonte: marts.v_ofs_por_fase_snapshot. Anchor "
            "factory_raw: Laminagem peças 1 233, Corte peças 1 100, Não "
            "Laminado 392, Corte 294, Lam Infusão 222, etc. SUM global = "
            "4 233. CONTAGEM adimensional. NÃO somar com "
            "producao_ofs_em_curso.total (mesma contagem em 2 cubes = "
            "dupla contagem). Snapshot sem dim 'tempo'."
        ),
        description="OFs em curso distribuídas POR fase (drill-down)",
        synonyms=(
            "OFs por fase", "distribuição por fase", "drill por fase",
            "produção por fase", "kayaks em laminagem", "kayaks em corte",
            "kayaks em pintura", "ordens por fase",
        ),
    ),
    # ── Q.102: primeira medida do domínio Comercial ──
    "comercial_facturacao.total": MeasureSpec(
        name="comercial_facturacao.total",
        unit=CanonicalUnit.DINHEIRO,
        description="Facturação NELO total em € (vendas externas, PHC)",
        synonyms=(
            "facturação", "faturação", "facturámos", "faturámos",
            "facturamos", "faturamos", "vendas", "vendemos", "receita",
            "vendido", "facturado", "faturado", "vendidas", "vendido total",
            "€", "euros", "PHC", "facturação total", "vendas totais",
            # Q.107.B: nomes de disciplinas (pergunta tipo "Faturação Canoe Sprint")
            "Canoe Sprint", "Sprint", "Ocean", "Marathon", "Fitness",
            "Canoe Marathon", "Fitness Ep", "Fitness Pl", "disciplina",
            "modalidade", "categoria",
            # Q.107.B: nomes de clientes top
            "Olimpijczyk", "Gusser", "KanuSport", "Nauticus", "Adnan",
            "Aliev", "Anjana", "clientes",
            # Q.107.B: padrões temporais comuns
            "em Abril", "em Maio", "em Janeiro", "este mês",
            "ano passado", "neste ano", "em 2024", "em 2025", "em 2026",
            # Q.108 Onda A: padrões por país (dim pais)
            "Poland", "Polónia", "Germany", "Alemanha", "Italy", "Itália",
            "Spain", "Espanha", "France", "França", "Portugal",
            "USA", "Estados Unidos", "Turkey", "Turquia", "China", "Japan",
            "por país", "country", "exportação", "mercado externo",
            "facturação por país", "vendas por país",
            # Q.108 Onda B: padrões por época desportiva (dim epoca)
            "época", "epoca", "época desportiva", "temporada",
            "ano desportivo", "season", "temporada 2024", "temporada 2025",
            "época 2024", "época 2025", "por época",
        ),
        dimensions_supported=frozenset({"tempo", "cliente", "disciplina", "pais", "epoca"}),
        business_decision=(
            "Q.102 Fase 0: SUM(EPHCF_FACTURADO) sobre "
            "marts.v_facturacao_mes (agregado mensal por cliente × "
            "disciplina). Anchor MAR-KAYAKS: total €125 372 058 "
            "(2009-2026), Canoe Sprint TP_ID=6 = €73 018 963 (58.24%), "
            "Gusser KanuSport 2024 = €488 898, total 2024 = €9 538 482. "
            "HIPÓTESE FORTE: valor é BASE sem IVA — PHC ERP NELO não "
            "tem coluna IVA separada; armazena base para reporting "
            "fiscal. Pendente confirmação CFO. Notas crédito subtraem "
            "(3 797 rows negativos no espelho; min -€87 780); SUM é "
            "líquido. EPOCA=ano desportivo (Out-Set) documentado mas "
            "medida usa ANO calendário. 32.6% rows agregadas sem "
            "cliente (vendas balcão/loja) = 'Sem cliente registado'; "
            "14.3% sem disciplina = 'Não categorizado'. JOIN cliente "
            "correcto Q.102.A: EPHCF_EPHC_ID = ENTIDADE_PHC.EPHC_ID "
            "(PK local), NÃO EPHC_PHC_ID (Q.82 errou na ponte)."
        ),
    ),
    # ── Q.103 Agente A: drill-down comercial por cliente ──
    # ── Q.107 Onda 4: TEMPERATURA (refactor zona fixa) ──
    "ambiental_estufa_temp.temp_max": MeasureSpec(
        name="ambiental_estufa_temp.temp_max",
        unit=CanonicalUnit.TEMPERATURA,
        dimensions_supported=frozenset({"tempo", "estufa"}),
        business_decision=(
            "Q.107 Onda 4: temperatura MÁXIMA registada nas estufas "
            "de cura (sensors 12/14/17). Agregação MAX cross-row "
            "(NÃO SUM — somar °C é inválido). Anchor Estufa 60 Abril "
            "2026 = 79.4°C. Q.82 documenta cura química a 68-71°C "
            "(15h); pico observado 80.2°C historicamente."
        ),
        description="Pico de temperatura em estufa (°C, MAX cross-row, NÃO somar)",
        synonyms=(
            "temperatura máxima estufa", "temperatura maxima",
            "pico temperatura estufa", "pico temperatura", "pico cura",
            "temp máx estufa", "estufa quente", "máximo cura",
            "graus celsius máximo", "que temperatura atingiu",
            "qual a temperatura", "que temperatura", "quão quente",
            # Q.107.B: padrões "temperatura na/da cura" (cu08)
            "temperatura cura", "temperatura na cura", "temperatura da cura",
            "qual a temperatura atingida", "que temperatura cura",
            "Estufa 60 temperatura", "temperatura Estufa",
            "celsius", "graus", "°C",
        ),
        aggregation="MAX",
    ),
    "ambiental_estufa_temp.temp_avg": MeasureSpec(
        name="ambiental_estufa_temp.temp_avg",
        unit=CanonicalUnit.TEMPERATURA,
        dimensions_supported=frozenset({"tempo", "estufa"}),
        business_decision=(
            "Q.107 Onda 4: temperatura MÉDIA das estufas. Agregação "
            "AVG cross-row (NÃO SUM). Anchor Estufa 60 Abril 2026 = "
            "51.3°C avg (inclui standby + cura — entre ciclos a "
            "estufa baixa)."
        ),
        description="Temperatura média em estufa de cura (°C AVG)",
        synonyms=(
            "temperatura média", "temp média", "média estufa",
            "temperatura ambiente", "celsius médio",
        ),
        aggregation="AVG",
    ),
    # ── Q.107 Onda 3: moldes ──
    "moldes.total": MeasureSpec(
        name="moldes.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(),
        business_decision=(
            "Q.107 Onda 3: COUNT de moldes em factory_raw.moldes. "
            "Anchor espelho = 91 moldes. Q.82 documentou 1 506 em "
            "MAR-KAYAKS (764 em uso); o espelho actual tem subset. "
            "Snapshot — sem dim tempo."
        ),
        description="Contagem total de moldes",
        synonyms=(
            "moldes", "molde", "número de moldes", "parque de moldes",
            "MLD",
        ),
    ),
    "moldes.com_utilizacao": MeasureSpec(
        name="moldes.com_utilizacao",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(),
        business_decision=(
            "Q.107 Onda 3: moldes com pelo menos 1 utilização "
            "(MLD_UTILIZ > 0). Anchor espelho = 55 / 91 (60.4%). "
            "Proxy para 'molde em uso' do Q.82."
        ),
        description="Moldes com utilizações registadas (MLD_UTILIZ>0)",
        synonyms=(
            "moldes em uso", "moldes utilizados", "moldes activos",
            "moldes a trabalhar",
        ),
    ),
    # ── Q.107 Onda 3: ciclos de cura (registar measure existente no YAML) ──
    "ambiental_cura_horas.ciclos": MeasureSpec(
        name="ambiental_cura_horas.ciclos",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "estufa"}),
        business_decision=(
            "Q.107 Onda 3: contagem de ciclos de cura. Measure já "
            "existia no cube YAML ambiental_cura_horas desde Q.100 "
            "mas faltava no REGISTRY. Anchor Estufa 60 Abril 2026 = "
            "13 ciclos."
        ),
        description="Número de ciclos de cura em estufa",
        synonyms=(
            "ciclos de cura", "ciclos", "quantos ciclos", "n ciclos",
            "ciclos estufa",
        ),
    ),
    # ── Q.107 Onda 1: pecas_cortadas + pecas_pintadas (padrão Q.99) ──
    "producao_pecas_cortadas.total": MeasureSpec(
        name="producao_pecas_cortadas.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "fase"}),
        business_decision=(
            "Q.107 Onda 1: contagem de fases de CORTE terminadas "
            "(OFFP_DATAFIM not null, FP_NOME ILIKE '%corte%'). "
            "Padrão Q.99 paralelo a pecas_laminadas. Anchor Abril 2026 "
            "= 4 923 (4 fases: Corte, Corte peças, Corte & Costura, "
            "Preparação)."
        ),
        description="Fases de CORTE terminadas (peças cortadas, NÃO laminadas)",
        synonyms=(
            "peças cortadas", "cortadas", "corte", "cortes", "corte peças",
            "fases de corte", "preparação corte", "costura corte",
            "kayaks cortados", "barcos cortados",
        ),
    ),
    "producao_pecas_pintadas.total": MeasureSpec(
        name="producao_pecas_pintadas.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "fase"}),
        business_decision=(
            "Q.107 Onda 1: contagem de fases de PINTURA terminadas "
            "(OFFP_DATAFIM not null, FP_NOME ILIKE '%pintura%'). "
            "Padrão Q.99. Anchor Abril 2026 = 770 (4 fases: Pintura, "
            "Pintura Acabamento, Acabamento-Pintura, Pintura-Verniz)."
        ),
        description="Fases de PINTURA terminadas (peças pintadas, NÃO consumo de tinta)",
        synonyms=(
            "peças pintadas", "pintadas", "pintura", "pintar", "verniz",
            "acabamento pintura", "fases de pintura", "kayaks pintados",
            "barcos pintados",
        ),
    ),
    # ── Q.107 Onda 1: logistica_transportes (TRANSPORTE granularidade) ──
    "logistica_transportes.total": MeasureSpec(
        name="logistica_transportes.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "destino", "tipo_transporte", "pais"}),
        business_decision=(
            "Q.107 Onda 1: COUNT(*) em factory_raw.transporte (1 row = "
            "1 viagem). Granularidade TRANSPORTE (NÃO OF — para OFs ver "
            "logistica_ofs_expedidas). Anchor 2024 = 490 transportes. "
            "Q.82: ~500-700 transportes/ano históricos."
        ),
        description="Número de transportes (viagens) registados",
        synonyms=(
            "transportes", "viagens", "envios", "remessas", "expedições",
            "transportar",
        ),
    ),
    "logistica_transportes.entregues": MeasureSpec(
        name="logistica_transportes.entregues",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "destino", "tipo_transporte", "pais"}),
        business_decision=(
            "Q.107 Onda 1: transportes com TR_DATA_ENTREGA preenchida. "
            "Cobertura histórica 15 % (Q.82); anos recentes podem ter "
            "baixa cobertura. Anchor histórico = 1 745 / 11 380 (15.3%)."
        ),
        description="Transportes entregues (com TR_DATA_ENTREGA)",
        synonyms=(
            "entregues", "entregaram", "chegaram", "concluídos",
            "entrega completa", "entrega registada",
        ),
    ),
    # ── Q.107 Onda 1: medidas adicionais ao cube comercial_facturacao ──
    "comercial_facturacao.n_facturas": MeasureSpec(
        name="comercial_facturacao.n_facturas",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "cliente", "disciplina", "pais", "epoca"}),
        business_decision=(
            "Q.107 Onda 1: COUNT(*) de linhas em ENTIDADE_PHC_FACT. "
            "Anchor MAR-KAYAKS: 100 625 rows totais (2009-2026); 6 774 "
            "rows em 2024 (Q.82). Inclui rows com €0 e negativos (notas "
            "crédito) — para só positivas usar filter facturado_eur > 0. "
            "CONTAGEM adimensional. Measure já existia no cube YAML "
            "comercial_facturacao desde Q.102 — Q.107 só REGISTA "
            "formalmente no contrato."
        ),
        description="Número de linhas/facturas emitidas",
        synonyms=(
            "número de facturas", "n facturas", "quantas facturas",
            "linhas de facturação", "n vendas", "transações comerciais",
            "documentos emitidos",
        ),
    ),
    "comercial_facturacao.clientes_activos": MeasureSpec(
        name="comercial_facturacao.clientes_activos",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "disciplina", "pais", "epoca"}),
        business_decision=(
            "Q.107 Onda 1: COUNT(DISTINCT EPHCF_EPHC_ID) — clientes "
            "identificáveis com faturação no período. Anchor: 127 "
            "clientes activos em 2024 (vs 280 acumulado histórico). "
            "Excluir EPHCF_EPHC_ID NULL (vendas balcão/loja). Não "
            "aditivo entre meses (mesma identidade) — cuidado em "
            "comparações; somar count entre meses pode duplicar."
        ),
        description="Número de clientes identificáveis com facturação no período",
        synonyms=(
            "clientes activos", "quantos clientes", "número de clientes",
            "clientes únicos", "clientes a comprar", "compradores",
        ),
    ),
    # ── Q.107 Onda 1: qualidade — taxa de defeitos graves ──
    "qualidade.defeitos_graves": MeasureSpec(
        name="qualidade.defeitos_graves",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "fase"}),
        business_decision=(
            "Q.107 Onda 1: SUM(CASE OFCH_GRAVIDADE=3) — numerador de "
            "taxa_grave. Anchor: 561 graves global no espelho. CONTAGEM "
            "adimensional, soma sempre OK. Subset de qualidade.defeitos."
        ),
        description="Número absoluto de defeitos graves (GRAVIDADE=3)",
        synonyms=(
            "graves", "defeitos graves", "criticidade", "severidade alta",
            "gravidade 3", "problemas graves",
        ),
    ),
    "qualidade.taxa_grave": MeasureSpec(
        name="qualidade.taxa_grave",
        unit=CanonicalUnit.FRACAO,
        dimensions_supported=frozenset({"tempo", "fase"}),
        business_decision=(
            "Q.107 Onda 1: ratio defeitos_graves / defeitos_total onde "
            "defeitos_grave = OFCH_GRAVIDADE=3 e total = GRAVIDADE>=1. "
            "Anchor espelho factory_raw: 561 graves / 5 660 totais = "
            "9.9 % proporção crítica. Ratio measure no Cube — NUNCA "
            "SUM(taxa_grave). Complemento à qualidade.taxa_defeitos "
            "(que é defeitos/checks); este é grave/defeitos."
        ),
        description="Proporção de defeitos graves (gravidade=3) sobre defeitos reais",
        synonyms=(
            "defeitos graves", "proporção grave", "% graves",
            "severidade defeitos", "criticidade",
        ),
    ),
    "comercial_top_clientes.total": MeasureSpec(
        name="comercial_top_clientes.total",
        unit=CanonicalUnit.DINHEIRO,
        description="Facturação NELO drill-down por cliente (ranking)",
        synonyms=(
            "top clientes", "melhores clientes", "quem comprou", "ranking clientes",
            "facturação por cliente", "vendas por cliente", "facturámos a",
            "faturámos a", "compraram", "comprou", "ranking de clientes",
            "top 5", "top 10", "principais clientes", "maiores clientes",
            "top cliente identificavel", "cliente identificável",
            # Q.107.B: nomes literais dos top clientes 2024
            "Olimpijczyk", "Gusser", "KanuSport", "Nauticus", "GmbH",
            "Adnan", "Aliev", "Sel. Turca", "Selecção Turca",
            "Anjana", "International", "Nelo Rental", "Rental",
        ),
        dimensions_supported=frozenset({"tempo", "cliente", "disciplina"}),
        business_decision=(
            "Q.103 Agente A: drill-down por cliente sobre "
            "marts.v_facturacao_mes (mesma fonte que comercial_facturacao "
            "Q.102, perfil cliente-centric). SUM(facturado_eur) ORDER BY "
            "cliente DESC. Anchor herdado Q.102: top-1 2024 = Gusser "
            "KanuSport €488 898; soma SEM filtros = €125 372 058. Base "
            "IVA HERDADA Q.102: BASE sem IVA (PHC não tem coluna IVA "
            "separada), pendente CFO — se mudar, muda nas 3 comerciais "
            "(facturacao + top_clientes + facturacao_disciplina) em "
            "simultâneo. JOIN cliente herdado Q.102.A: EPHCF_EPHC_ID = "
            "ENTIDADE_PHC.EPHC_ID (PK local, NÃO EPHC_PHC_ID que Q.82 "
            "errou). DUPLA CONTAGEM: NÃO somar com "
            "comercial_facturacao.total nem comercial_facturacao_"
            "disciplina.total — são a mesma faturação decomposta de 3 "
            "formas (mesma SUM, mesma fonte). 32.6 % rows agregadas com "
            "'Sem cliente registado' (vendas balcão/loja)."
        ),
    ),
    # ── Q.103 Agente B: drill-down comercial por disciplina ──
    "comercial_facturacao_disciplina.total": MeasureSpec(
        name="comercial_facturacao_disciplina.total",
        unit=CanonicalUnit.DINHEIRO,
        description="Facturação NELO por disciplina (Canoe Sprint, Ocean, …)",
        synonyms=(
            "facturação por disciplina", "faturação por disciplina",
            "disciplina específica", "modalidade", "categoria", "TP_NOME",
            "vendas por modalidade", "vendas por disciplina",
            # Q.107.B: nomes literais que aparecem isolados em perguntas
            "Canoe Sprint", "Canoe Sprint Ep.", "Sprint", "Ocean",
            "Canoe Marathon", "Marathon", "Fitness Ep.", "Fitness Pl.",
            "Fitness", "Training",
            # Q.107.B: padrões de pergunta sobre disciplina isolada
            "qual a faturação de", "quanto vendemos em",
            "facturação Canoe", "facturação Ocean",
            "em Canoe Sprint", "em Ocean", "em Marathon",
        ),
        dimensions_supported=frozenset({"tempo", "disciplina"}),
        business_decision=(
            "Q.103 Agente B: drill-down por disciplina sobre "
            "marts.v_facturacao_mes (mesma fonte que comercial_facturacao "
            "Q.102, perfil disciplina-centric). SUM(facturado_eur) GROUP "
            "BY disciplina. Anchor herdado Q.102: Canoe Sprint Ep. = "
            "€73 018 963 (58.24 %), Ocean €6 283 503, Canoe Marathon "
            "€4 430 043, Fitness Ep. €4 141 622, Fitness Pl. €3 357 430. "
            "Soma de TODAS as disciplinas = €125 372 058 (anchor "
            "coerência). 'Não categorizado' = €14 851 681 (14.3 % rows "
            "agregadas sem TP_ID). Base IVA HERDADA Q.102 (BASE sem IVA, "
            "pendente CFO). DUPLA CONTAGEM: NÃO somar com "
            "comercial_facturacao.total nem comercial_top_clientes.total "
            "— mesma faturação 3 vistas. dims_supported SEM 'cliente' "
            "deliberadamente — perfil disciplina-only; para drill por "
            "cliente usa comercial_top_clientes."
        ),
    ),
    # ── Q.104 Medida 1: primeira medida do domínio Logística ──
    "logistica_ofs_expedidas.total": MeasureSpec(
        name="logistica_ofs_expedidas.total",
        unit=CanonicalUnit.CONTAGEM,
        description="OFs expedidas (transporte enviado, por destino e tipo)",
        synonyms=(
            "OFs expedidas", "enviadas", "transportadas", "expedidas",
            "entregues", "destino", "UE", "exportação", "transporte",
            "camião", "barco", "avião", "envio", "logística",
        ),
        dimensions_supported=frozenset({"tempo", "destino", "tipo_transporte"}),
        business_decision=(
            "Q.104 Fase 0: SUM(n_ofs) sobre marts.v_ofs_expedidas_mes "
            "(agregado mensal por destino × tipo_transporte). Critério "
            "canónico Q.82 §4: TROF_ENVIADO=TRUE + TR_DATA NOT NULL "
            "(NÃO usar OF_DATATRANSPORTE — morto desde 2009). "
            "Granularidade view: COUNT(DISTINCT TROF_OF_ID) por sub-grupo. "
            "Anchor 2024 (SUM agregada) = 5 830 OFs-expedições (= 4 063 UE "
            "+ 1 530 Outros + 237 Nacional). NOTA crítica: COUNT DISTINCT "
            "global = 5 573; o delta ~257 são OFs expedidas em destinos "
            "múltiplos no mesmo ano — a SUM agregada conta cada expedição "
            "por destino (semanticamente 'OFs para UE' + 'OFs para Outros' "
            "= 'OFs expedidas com destino'). Histórico anual estável "
            "5-7K. Transportadora NÃO em dims_supported — 98.5 % externos "
            "genéricos sem nome único; TR_OPERADOR_CODIGO só 3 % cobertura "
            "(buraco residual Q.82, não inventar)."
        ),
    ),
    # ── Q.104 Medida 2: atrasos com classificação NELO ──
    "logistica_atrasos_culpa.total": MeasureSpec(
        name="logistica_atrasos_culpa.total",
        unit=CanonicalUnit.CONTAGEM,
        description="Atrasos de transporte segundo classificação NELO",
        synonyms=(
            "atrasos", "atrasado", "alterações de data", "culpa",
            "responsabilidade", "transportador", "cliente atrasou",
            "logística falhou", "datas alteradas",
        ),
        dimensions_supported=frozenset({"tempo", "culpa"}),
        business_decision=(
            "Q.104 Medida 2: SUM(n_atrasos) sobre "
            "marts.v_atrasos_culpa_mes (agregado mensal por culpa). "
            "**SEMÂNTICA CRÍTICA**: a 'culpa' é CLASSIFICAÇÃO humana "
            "NELO registada em TRDT_TRDTCL_ID, NÃO veredito do sistema. "
            "O copiloto REPORTA a repartição registada, NÃO atribui "
            "responsabilidade. 'Atraso' = alteração de data registada "
            "em TRANSP_DATAS; atrasos NÃO registados nesta tabela não "
            "estão visíveis. Anchor Q.104.A (real pós-espelhamento): "
            "total = 3 030 atrasos (Q.82 dizia 3 027; +3 rows recentes); "
            "Culpa Cliente 2 114 (69.8 %), Culpa Nelo 790 (26.1 %), "
            "Culpa Transportador 126 (4.2 %). 100 % têm classificação "
            "— sem categoria 'sem classificação' (todos os atrasos "
            "registados foram classificados). Período por "
            "TRDT_DATA_CRIACAO (quando a alteração foi feita). NARRAÇÃO "
            "deve referir 'classificação registada' / 'segundo a "
            "classificação NELO' — NUNCA 'a NELO teve culpa de X' como "
            "facto objectivo."
        ),
    ),
    # ── Q.100 Medida 1: primeira medida do domínio Ambiental (IoT) ──
    "ambiental_cura_horas.total": MeasureSpec(
        name="ambiental_cura_horas.total",
        unit=CanonicalUnit.TEMPO,
        description="Horas de cura química em estufa (T>=65°C)",
        synonyms=(
            "cura", "horas de cura", "horas cura", "tempo de cura",
            "tempo cura", "estufa", "tempo em estufa", "secagem",
            "Estufa 60", "Estufa 30", "Estufa Peças", "ciclo de cura",
            "química", "curagem",
            # Q.107.B: padrões comparativos (cu03 Março vs Abril)
            "cura mensal", "cura por mês", "comparativo cura",
            "estufa por período", "estufa mensal",
            "Março vs Abril", "Abril vs Maio", "comparar cura",
            # Q.107.B: variantes de pergunta
            "quantas horas", "estufa quanto tempo", "duração cura",
        ),
        dimensions_supported=frozenset({"tempo", "estufa"}),
        business_decision=(
            "Q.100 Medida 1: horas em ciclos de cura química. Fonte: "
            "marts.v_ciclos_cura (1 row por ciclo). Ciclo = janela "
            "contínua T>=65°C com gap separador >60min e duração >=1h. "
            "SUM(duracao_h) onde duracao_h = MAX(ts)-MIN(ts) do ciclo "
            "(NÃO 'n_leituras × 5min' — esse subestima ~10%). Threshold "
            "65°C separa standby (~30°C) de cura activa (73-77°C avg, "
            "pico 80.2°C). IOT_SENSOR_ALARM.SA_MIN=45°C é o limite "
            "NELO documentado mas 65 é onde os ciclos reais aparecem "
            "na distribuição. Anchor Q.100.A: Estufa 60 (sensor 12) "
            "em Abril 2026 = 13 ciclos / 150.6 h (médio 11.58 h, pico "
            "79.4°C). Padrão noturno (~19h→07h overnight). Aditivo "
            "entre estufas e meses. Cobertura: 1 ano espelho Q.98."
        ),
    ),
    # ── Q.108 Onda A: utilização total de moldes (SUM(MLD_UTILIZ)) ──
    "moldes.utilizacao_total": MeasureSpec(
        name="moldes.utilizacao_total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(),
        business_decision=(
            "Q.108 Onda A: soma total de utilizações dos moldes "
            "(SUM(MLD_UTILIZ) em factory_raw.moldes). Anchor espelho = "
            "101 utilizações acumuladas em 91 moldes (55 deles com "
            "utilização > 0). Snapshot — sem dim tempo. NÃO confundir "
            "com `moldes.com_utilizacao` (que conta moldes binariamente)."
        ),
        description="Soma total de utilizações dos moldes (SUM MLD_UTILIZ)",
        synonyms=(
            "utilizações moldes", "total utilizações", "uso moldes",
            "utilização cumulativa moldes", "uso acumulado moldes",
            "soma utilizações", "MLD_UTILIZ total",
            "quantas utilizações", "vezes que moldes foram usados",
        ),
    ),
    # ── Q.108 Onda A: taxa de defeitos INTERMÉDIOS (gravidade=2) ──
    "qualidade.taxa_intermedia": MeasureSpec(
        name="qualidade.taxa_intermedia",
        unit=CanonicalUnit.FRACAO,
        dimensions_supported=frozenset({"tempo", "fase"}),
        business_decision=(
            "Q.108 Onda A: ratio defeitos_intermedios / defeitos_total "
            "onde intermedio = OFCH_GRAVIDADE=2 e total = GRAVIDADE>=1. "
            "Anchor espelho factory_raw: 1 368 intermédios / 5 660 "
            "totais = 24.2 %. Ratio measure no Cube — NUNCA "
            "SUM(taxa_intermedia). Análoga a taxa_grave mas para "
            "gravidade 2 (severidade média). Soma de taxa_grave + "
            "taxa_intermedia + taxa_leve = 1 (partição completa)."
        ),
        description="Proporção de defeitos intermédios (gravidade=2) sobre defeitos reais",
        synonyms=(
            "defeitos intermédios", "proporção intermédia", "% intermédios",
            "severidade média", "gravidade 2", "intermédios",
            "defeitos médios", "média severidade", "gravidade intermédia",
        ),
    ),
    # ── Q.108 Onda A: emissões CO2 em transportes (sub-unidade kg_co2) ──
    "logistica_transportes.co2_total": MeasureSpec(
        name="logistica_transportes.co2_total",
        unit=CanonicalUnit.QUANTIDADE_FISICA,
        dimensions_supported=frozenset({"tempo", "destino", "tipo_transporte", "pais"}),
        business_decision=(
            "Q.108 Onda A: SUM(TR_CO2) em factory_raw.transporte — "
            "emissões CO2 estimadas em kg por viagem. Sub-unidade "
            "FIXA `kg_co2` (não confundir com kg de material em "
            "consumo_material). Por ser sub-unidade única, NÃO inclui "
            "`unidade_id` em dimensions_supported — escapa ao guard "
            "anti-soma-cega Q.95.1 (que assume sub-unidades múltiplas). "
            "Anchor histórico = 38 546 kg em 11 382 transportes com "
            "TR_CO2 não-NULL. NUNCA somar com consumo_material.consumo "
            "ou qualquer outra QUANTIDADE_FISICA (sub-unidades diferentes)."
        ),
        description="Emissões de CO2 em kg dos transportes (sub-unidade kg_co2)",
        synonyms=(
            "CO2", "emissões CO2", "emissões", "carbono", "kg de CO2",
            "pegada carbono", "footprint carbono",
            "CO2 transportes", "CO2 logística", "emissões logística",
            "quanto CO2", "CO2 emitido", "emissões transportes",
            "kg CO2", "carbon footprint",
        ),
    ),
    # ── Q.108 Onda A: humidade média das estufas (FRACAO, AGG=AVG) ──
    "ambiental_estufa_humidade.avg": MeasureSpec(
        name="ambiental_estufa_humidade.avg",
        unit=CanonicalUnit.FRACAO,
        dimensions_supported=frozenset({"tempo", "estufa"}),
        aggregation="AVG",
        business_decision=(
            "Q.108 Onda A: humidade relativa média das estufas. View "
            "marts.v_estufa_humidade_mes divide SD_HUM por 100 (0-100% "
            "→ 0-1 FRACAO) e agrega AVG por mês × sensor. Filtra "
            "sensores 12 (Estufa 60), 14 (Estufa 30), 17 (Estufa Peças) "
            "— exclui sensor 15 'Temperatura Exterior' (não é estufa). "
            "Anchors globais histórico: Estufa 60 ~0.383 (38.3%); "
            "Estufa 30 ~0.305; Estufa Peças ~0.414. Agregação cross-row "
            "AVG (NÃO SUM — humidade média não soma). Apresentar em % "
            "na narração (×100)."
        ),
        description="Humidade relativa média das estufas (0-1, narração em %)",
        synonyms=(
            "humidade", "humidade estufa", "humidade média", "%RH",
            "humidade relativa", "hum média estufa",
            "humidade Estufa 60", "humidade Estufa 30", "humidade Estufa Peças",
            "qual a humidade", "humidade na estufa", "humidade ambiente estufa",
            "RH estufa", "SD_HUM",
        ),
    ),
    # ── Q.108.B2: documentação dos transportes (TRANSP_DOCS) ──
    "logistica_docs.emitidos_total": MeasureSpec(
        name="logistica_docs.emitidos_total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.B2: COUNT(*) sobre factory_raw.transp_docs com "
            "TRDOC_DATA preenchida (CMR, factura, packing list, etc). "
            "Cobertura 64% (29 969 / 46 917 datadas; 16 948 docs sem "
            "data não entram na medida). Anchor 2024 = 1 397 docs "
            "emitidos. CONTAGEM aditiva entre meses. NUNCA confundir "
            "com `logistica_transportes.total` (transportes "
            "granularidade — 1 transporte pode ter 0+ docs)."
        ),
        description="Documentos de transporte emitidos por mês (CMR, packing list)",
        synonyms=(
            "documentos transporte", "docs transporte", "CMR", "packing list",
            "factura transporte", "documentos emitidos", "docs emitidos",
            "documentação logística", "documentos logística",
            "quantos documentos", "n documentos", "papelada transporte",
            "carta de porte", "guia de transporte", "Bill of Lading", "B/L",
            "documentos expedição", "guias expedição", "guias de remessa",
            "CMR emitidos", "documentos enviados transporte",
        ),
    ),
    "logistica_docs.pendentes_total": MeasureSpec(
        name="logistica_docs.pendentes_total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.B2: COUNT(*) sobre factory_raw.transp_docs com "
            "TRDOC_TRATADO=FALSE (ou NULL) E TRDOC_DATA preenchida. "
            "Anchor histórico = 20 pendentes (vs 29 949 tratados, "
            "99.9% processados); 2024 = 3 pendentes. Indicador de "
            "backlog logístico residual. Aditivo entre meses."
        ),
        description="Documentos de transporte por processar (TRDOC_TRATADO=FALSE)",
        synonyms=(
            "docs pendentes", "documentos pendentes", "papelada pendente",
            "docs por tratar", "documentos não tratados", "docs em atraso",
            "backlog documentos", "documentação em falta",
            "papelada por fazer", "TRDOC_TRATADO false",
        ),
    ),
    # ── Q.108 Onda A: regras de alarme IoT configuradas ──
    "ambiental_iot_alarmes.total": MeasureSpec(
        name="ambiental_iot_alarmes.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(),
        business_decision=(
            "Q.108 Onda A: contagem de regras de alarme IoT configuradas "
            "(factory_raw.iot_sensor_alarm.SA_ID). Cada linha = UMA "
            "regra viva (limite min/max num sensor), NÃO um disparo. "
            "Anchor espelho = 14 regras em 14 sensores distintos. "
            "Q.82 documentou correctamente 14. Snapshot — sem dim "
            "tempo (regras são configuração, não eventos)."
        ),
        description="Regras de alarme IoT configuradas (limites min/max em sensores)",
        synonyms=(
            "alarmes IoT", "regras de alarme", "alarmes configurados",
            "limites sensores", "thresholds sensores", "alertas IoT",
            "quantas regras alarme", "regras vivas alarme",
            "configuração alarmes", "alarme min max sensor",
            "monitoring rules", "sensores com alarme",
        ),
    ),
    # ── Q.108.C: facturação atribuída a agentes (AGENTE_FATURACAO) ──
    "comercial_facturacao_agente.total": MeasureSpec(
        name="comercial_facturacao_agente.total",
        unit=CanonicalUnit.DINHEIRO,
        dimensions_supported=frozenset({"tempo", "agente"}),
        business_decision=(
            "Q.108.C: SUM(AF_VALOR) sobre marts.v_facturacao_agente_trim. "
            "Fonte AGENTE_FATURACAO (Q.108-A espelhada) — declaração "
            "TRIMESTRAL de agentes comerciais. Granularidade trimestral "
            "(NÃO mensal). Anchor acumulado = €65 816 613 em 59 agentes "
            "/ 2 234 declarações. Anchor 2024 = €3 102 232 (39 agentes "
            "em 123 declarações). Top 2024: Gusser KanuSport (Nauticus "
            "GmbH) €395 698; Anjana International €336 822; Flat Water "
            "€292 129. NUNCA somar com comercial_facturacao.total — "
            "fonte distinta (EPHCF vs AGENTE_FATURACAO); são ângulos "
            "diferentes da mesma facturação (cliente vs agente que "
            "comissionou); dupla contagem. Granularidade AGENTE_FATURACAO "
            "é trimestral, EPHCF é mensal — não comparáveis directamente."
        ),
        description="Facturação atribuída a agentes comerciais (€, AGENTE_FATURACAO, trimestral)",
        synonyms=(
            "agente", "agentes", "agente comercial", "agentes comerciais",
            "comissão agente", "comissões", "facturação agente",
            "vendas por agente", "AF_VALOR", "declaração agente",
            "declarações trimestrais agente", "top agente",
            "Gusser agente", "Anjana", "Olimpijczyk agente",
            "Flat Water agente", "Nelo Canada agente",
            "comissionado", "agenciado",
        ),
    ),
    # ── Q.108.E.2: rework por molde (mart sobre quality.rework_entry) ──
    "qualidade_rework_por_molde.total": MeasureSpec(
        name="qualidade_rework_por_molde.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "molde_id"}),
        business_decision=(
            "Q.108.E.2: COUNT(*) sobre marts.v_rework_por_molde_mes — "
            "incidentes de retrabalho agregados por (mês, molde_id). "
            "Q.108.E.1 destrancou esta medida ao popular "
            "quality.rework_entry.mold_id a partir de "
            "OperationRow.mold_work_order_id (OF_OF_ID_MLD parent). "
            "CONTAGEM adimensional — soma sempre OK. Útil para top-N "
            "moldes problemáticos e correlação com utilização."
        ),
        description="Incidentes de retrabalho por molde (mês × molde_id)",
        synonyms=(
            "rework por molde", "defeitos por molde", "molde problemático",
            "incidentes molde", "retrabalho molde", "MLD_ID",
            "moldes com defeitos", "top moldes defeito",
        ),
    ),
    "qualidade_rework_por_molde.graves": MeasureSpec(
        name="qualidade_rework_por_molde.graves",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "molde_id"}),
        business_decision=(
            "Q.108.E.2: sub-contagem WHERE severe_return=TRUE em "
            "marts.v_rework_por_molde_mes. Proxy de severidade — "
            "OFFP_RETORNO_GRAVE marca incidentes que pediram chefe. "
            "CONTAGEM adimensional. Combinado com .total dá taxa de "
            "severidade por molde (mas a razão calcula-se no caller)."
        ),
        description="Incidentes GRAVES de retrabalho por molde (mês × molde_id)",
        synonyms=(
            "retrabalho grave molde", "defeito grave molde",
            "severe rework por molde", "moldes mais graves",
        ),
    ),
    # ── Q.108.E.2: rework por disciplina (TP_NOME via context) ──
    "qualidade_rework_por_disciplina.total": MeasureSpec(
        name="qualidade_rework_por_disciplina.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "disciplina"}),
        business_decision=(
            "Q.108.E.2: COUNT(*) sobre marts.v_rework_por_disciplina_mes — "
            "incidentes de retrabalho agregados por (mês, disciplina). "
            "Disciplina = TP_NOME (Canoe Sprint, Canoe Marathon, Ocean, "
            "Fitness, …) populada em quality.rework_entry.context."
            "product_type_name desde Q.108.E.1. CONTAGEM adimensional. "
            "Mesma dim 'disciplina' que comercial_facturacao_disciplina "
            "— permite cross-cube na mesma chave."
        ),
        description="Incidentes de retrabalho por disciplina (mês × disciplina)",
        synonyms=(
            "rework por disciplina", "defeitos por disciplina",
            "qualidade por modalidade", "defeitos por categoria",
            "Sprint defeitos", "Ocean defeitos", "Marathon defeitos",
            "Fitness defeitos",
        ),
    ),
    "qualidade_rework_por_disciplina.graves": MeasureSpec(
        name="qualidade_rework_por_disciplina.graves",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "disciplina"}),
        business_decision=(
            "Q.108.E.2: sub-contagem severe_return=TRUE em "
            "marts.v_rework_por_disciplina_mes. Permite identificar que "
            "disciplinas concentram retrabalho severo. CONTAGEM."
        ),
        description="Incidentes GRAVES de retrabalho por disciplina (mês × disciplina)",
        synonyms=(
            "rework grave disciplina", "defeito grave disciplina",
            "Sprint defeito grave", "modalidade severidade",
        ),
    ),
    # ── Q.108.F.1: lead time de OFs por mês ──
    "producao_lead_time_of.ofs_fechadas": MeasureSpec(
        name="producao_lead_time_of.ofs_fechadas",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.F.1: SUM(n_ofs_fechadas) sobre marts.v_lead_time_of_mes. "
            "Contagem absoluta de OFs que fecharam (todas as fases têm "
            "OFFP_DATAFIM) no mês. CONTAGEM, soma sempre OK. Denominador "
            "natural para taxa de throughput de OFs."
        ),
        description="Número de OFs fechadas por mês (todas as fases terminadas)",
        synonyms=(
            "OFs fechadas", "OFs terminadas", "OFs concluídas",
            "ordens de fabrico fechadas", "throughput OFs", "barcos terminados",
            "OFs produzidas", "produzidas no mês", "produção mensal",
            "barcos produzidos no mês",
        ),
    ),
    "producao_lead_time_of.lead_time_avg": MeasureSpec(
        name="producao_lead_time_of.lead_time_avg",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.F.1: AVG(lead_time_dias) — dias entre MIN(OFFP_DATAINICIO) "
            "e MAX(OFFP_DATAFIM) por work_order_id, agregado pelo mês de "
            "fechamento. TEMPO em dias. Agregação CROSS-row é AVG (NÃO "
            "SUM — somar 30 dias × 12 meses não dá 360 dias). Cube faz "
            "AVG; para ponderar pelo n_ofs ver derived KPI."
        ),
        description="Lead time médio (dias) de OFs fechadas no mês",
        synonyms=(
            "lead time", "tempo de produção", "duração OF",
            "dias por OF", "tempo médio OF", "tempo até fechar",
            "ciclo OF", "duração média barco", "tempo entrega",
        ),
    ),
    "producao_lead_time_of.lead_time_p50": MeasureSpec(
        name="producao_lead_time_of.lead_time_p50",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.F.1: P50 (mediana) do lead time por mês. PERCENTILE_CONT "
            "(0.5) — mais robusto a outliers do que AVG. Agregação CROSS-row "
            "é AVG (médio dos P50 mensais), NÃO SUM."
        ),
        description="Lead time MEDIANO (P50) das OFs por mês (dias)",
        synonyms=(
            "lead time mediano", "P50 lead time", "mediana duração OF",
            "mediana tempo produção",
        ),
    ),
    "producao_lead_time_of.lead_time_p90": MeasureSpec(
        name="producao_lead_time_of.lead_time_p90",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.F.1: P90 do lead time por mês. PERCENTILE_CONT(0.9) — "
            "90 % das OFs fecharam em <= este número de dias. Útil para "
            "SLA / promessas de prazo. Cross-row aggregation AVG, NÃO SUM."
        ),
        description="Lead time P90 das OFs por mês (dias)",
        synonyms=(
            "P90 lead time", "lead time pior caso", "SLA OFs",
            "duração 90 percentil",
        ),
    ),
    # ── Q.108.W1: cura compliance % (destrava corr_temp_avg_vs_compliance_cura) ──
    "ambiental_cura_compliance.taxa": MeasureSpec(
        name="ambiental_cura_compliance.taxa",
        unit=CanonicalUnit.FRACAO,
        dimensions_supported=frozenset({"tempo", "estufa", "sensor_id"}),
        business_decision=(
            "Q.108.W1: ratio measure SUM(ciclos_compliant)/NULLIF(SUM(total_ciclos),0) "
            "sobre marts.v_cura_compliance_mes. Universo: ciclos que atingiram "
            "T>=45°C (alarme); compliant = T_max>=65°C AND duracao_h>=1h "
            "(critério Q.100). FRACAO 0-1; NUNCA SUM(taxa). Destrava "
            "`corr_temp_avg_vs_compliance_cura`."
        ),
        description="% ciclos de cura compliant (T>=65°C, duração>=1h)",
        synonyms=(
            "cura compliance", "compliance cura", "ciclos válidos", "cura ok",
            "cura conforme", "compliance químico", "secagem válida",
            "% cura compliant",
        ),
    ),
    "ambiental_cura_compliance.total": MeasureSpec(
        name="ambiental_cura_compliance.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "estufa", "sensor_id"}),
        business_decision=(
            "Q.108.W1: SUM(total_ciclos) — universo de ciclos que atingiram "
            "T>=45°C (denominador da compliance). CONTAGEM, aditiva."
        ),
        description="Total ciclos de cura tentados (T>=45°C) por mês/estufa",
        synonyms=(
            "total ciclos cura", "ciclos tentados", "tentativas cura",
        ),
    ),
    "ambiental_cura_compliance.compliant": MeasureSpec(
        name="ambiental_cura_compliance.compliant",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "estufa", "sensor_id"}),
        business_decision=(
            "Q.108.W1: SUM(ciclos_compliant) — numerador isolado da taxa. "
            "CONTAGEM, aditiva. Para drill-down de quantos ciclos passaram "
            "o critério canónico Q.100."
        ),
        description="Ciclos de cura compliant (T_max>=65°C E duração>=1h)",
        synonyms=(
            "ciclos compliant", "cura ok contagem", "secagem válida count",
        ),
    ),
    # ── Q.108.W1: aprovações Q.17 (governance decisions) ──
    "aprovacoes_q17.propostas": MeasureSpec(
        name="aprovacoes_q17.propostas",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "action_type"}),
        business_decision=(
            "Q.108.W1: SUM(total_propostas) — COUNT decisões Q.17 propostas "
            "no mês. Source: marts.v_aprovacoes_q17_mes / shared.decision_runs. "
            "CONTAGEM aditiva."
        ),
        description="Decisões Q.17 propostas por mês × action_type",
        synonyms=(
            "decisões propostas", "decision PRs", "Q.17 propostas",
            "aprovações solicitadas",
        ),
    ),
    "aprovacoes_q17.aprovadas": MeasureSpec(
        name="aprovacoes_q17.aprovadas",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "action_type"}),
        business_decision=(
            "Q.108.W1: COUNT decisões em status APPROVED ou EXECUTED. "
            "CONTAGEM aditiva."
        ),
        description="Decisões Q.17 aprovadas/executadas por mês",
        synonyms=(
            "decisões aprovadas", "Q.17 aprovadas", "approved decisions",
            "executed decisions",
        ),
    ),
    "aprovacoes_q17.pendentes": MeasureSpec(
        name="aprovacoes_q17.pendentes",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "action_type"}),
        business_decision=(
            "Q.108.W1: COUNT decisões ainda em status PROPOSED (à espera). "
            "Snapshot-like — depende de quando se corre a query. CONTAGEM."
        ),
        description="Decisões Q.17 pendentes de aprovação",
        synonyms=(
            "decisões pendentes", "pending approvals", "Q.17 à espera",
            "aprovações pendentes",
        ),
    ),
    "aprovacoes_q17.rejeitadas": MeasureSpec(
        name="aprovacoes_q17.rejeitadas",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "action_type"}),
        business_decision=(
            "Q.108.W1: COUNT em REJECTED ou ROLLED_BACK. CONTAGEM."
        ),
        description="Decisões Q.17 rejeitadas/revertidas",
        synonyms=(
            "decisões rejeitadas", "rejeitadas", "rolled back",
            "decisões revertidas",
        ),
    ),
    "aprovacoes_q17.approval_time_avg": MeasureSpec(
        name="aprovacoes_q17.approval_time_avg",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "action_type"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.W1: AVG horas entre proposed_at e (executed_at ou "
            "rolled_back_at). TEMPO; cross-row AVG (NÃO SUM)."
        ),
        description="Tempo médio de aprovação Q.17 (horas)",
        synonyms=(
            "tempo aprovação", "approval time", "horas aprovação",
            "latência decisória",
        ),
    ),
    "aprovacoes_q17.approval_time_p50": MeasureSpec(
        name="aprovacoes_q17.approval_time_p50",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "action_type"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.W1: PERCENTILE_CONT(0.5) mediano das horas de aprovação. "
            "TEMPO; cross-row AVG."
        ),
        description="Tempo mediano (P50) de aprovação Q.17 (horas)",
        synonyms=(
            "P50 aprovação", "mediana aprovação", "tempo mediano decisão",
        ),
    ),
    # ── Q.108.W1.2: backlog de OFs em atraso ──
    "planeamento_backlog.total": MeasureSpec(
        name="planeamento_backlog.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.W1.2: COUNT(*) de OFs em atraso hoje "
            "(OF_DATAENTREGA < now AND OF_DATAFIM IS NULL). "
            "Snapshot diário em marts.v_backlog_dia. CONTAGEM aditiva."
        ),
        description="OFs em atraso hoje (data prometida ultrapassada)",
        synonyms=(
            "backlog", "OFs atrasadas", "atrasos", "OFs em atraso",
            "encomendas atrasadas", "barcos atrasados",
        ),
    ),
    "planeamento_backlog.dias_atraso_avg": MeasureSpec(
        name="planeamento_backlog.dias_atraso_avg",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.W1.2: AVG dias entre OF_DATAENTREGA e now. "
            "TEMPO em dias; cross-row AVG."
        ),
        description="Dias médios de atraso entre OFs em backlog",
        synonyms=(
            "dias de atraso", "atraso médio", "lag médio",
        ),
    ),
    "planeamento_backlog.dias_atraso_p50": MeasureSpec(
        name="planeamento_backlog.dias_atraso_p50",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.W1.2: P50 (mediana) dos dias de atraso. Robusto a outliers."
        ),
        description="Mediana dos dias de atraso (P50)",
        synonyms=("mediana atraso", "P50 atraso"),
    ),
    "planeamento_backlog.dias_atraso_max": MeasureSpec(
        name="planeamento_backlog.dias_atraso_max",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="MAX",
        business_decision=(
            "Q.108.W1.2: MAX dias atraso — pior caso. TEMPO; cross-row MAX."
        ),
        description="Pior caso de atraso entre OFs em backlog (dias)",
        synonyms=("pior atraso", "máximo atraso"),
    ),
    # ── Q.108.W1.2: reagendamentos do CPO scheduler ──
    "planeamento_reagendamentos.total": MeasureSpec(
        name="planeamento_reagendamentos.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.W1.2: COUNT(*) plan_schedule_commits por mês. Cada commit "
            "é um plano produzido pelo CPO. CONTAGEM aditiva entre meses."
        ),
        description="Total commits do CPO por mês (planos produzidos)",
        synonyms=(
            "reagendamentos", "commits CPO", "planos produzidos",
            "scheduler runs", "re-plans",
        ),
    ),
    "planeamento_reagendamentos.live": MeasureSpec(
        name="planeamento_reagendamentos.live",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.W1.2: COUNT commits com status='LIVE' (aprovados). "
            "CONTAGEM aditiva."
        ),
        description="Commits do CPO promovidos a LIVE (aprovados)",
        synonyms=(
            "commits LIVE", "planos aprovados", "approved schedule commits",
        ),
    ),
    "planeamento_reagendamentos.draft": MeasureSpec(
        name="planeamento_reagendamentos.draft",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.W1.2: COUNT commits em DRAFT (CPO produziu mas não "
            "foi aprovado). Sinal de scheduler em modo experimental."
        ),
        description="Commits do CPO que ficaram em DRAFT",
        synonyms=("commits DRAFT", "planos não aprovados"),
    ),
    "planeamento_reagendamentos.replans": MeasureSpec(
        name="planeamento_reagendamentos.replans",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.W1.2: COUNT commits com parent_id NOT NULL — proxy de "
            "quantas vezes o plano foi alterado em relação a um pai. "
            "CONTAGEM."
        ),
        description="Re-plans (commits derivados de outro commit)",
        synonyms=("re-plans", "alterações de plano", "replanings"),
    ),
    # ── Q.108.W2: WIP por fase ──
    "producao_wip_fase.total": MeasureSpec(
        name="producao_wip_fase.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "fase", "fase_sequencia"}),
        business_decision=(
            "Q.108.W2: COUNT operações activas (OFFP_DATAFIM NULL E "
            "FP_SEQUENCIA<30) por fase. Snapshot diário em "
            "marts.v_wip_fase_dia. CONTAGEM aditiva entre fases."
        ),
        description="Work In Progress — operações activas por fase (snapshot)",
        synonyms=(
            "WIP", "work in progress", "operações activas", "em curso por fase",
            "peças em fase", "barcos por fase",
        ),
    ),
    # ── Q.108.W2: schedule adherence ──
    "producao_schedule_aderencia.taxa": MeasureSpec(
        name="producao_schedule_aderencia.taxa",
        unit=CanonicalUnit.FRACAO,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.W2: ratio SUM(on_time)/NULLIF(SUM(on_time+late),0) sobre "
            "marts.v_schedule_aderencia_mes. % OFs fechadas dentro de "
            "OF_DATAENTREGA. FRACAO 0-1; ignora OFs sem promessa."
        ),
        description="% OFs entregues no prazo prometido (schedule adherence)",
        synonyms=(
            "schedule adherence", "aderência ao prazo", "% no prazo",
            "OTD interno", "entregas no prazo", "cumprimento de prazo",
        ),
    ),
    "producao_schedule_aderencia.fechadas": MeasureSpec(
        name="producao_schedule_aderencia.fechadas",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision="Q.108.W2: COUNT total OFs fechadas no mês. CONTAGEM aditiva.",
        description="OFs fechadas por mês (todas, com ou sem promessa)",
        synonyms=("OFs fechadas mês", "ordens completadas"),
    ),
    "producao_schedule_aderencia.on_time": MeasureSpec(
        name="producao_schedule_aderencia.on_time",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.W2: COUNT OFs fechadas dentro de OF_DATAENTREGA. CONTAGEM."
        ),
        description="OFs entregues no prazo (numerador da adherence)",
        synonyms=("OFs no prazo", "on-time"),
    ),
    "producao_schedule_aderencia.late": MeasureSpec(
        name="producao_schedule_aderencia.late",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision="Q.108.W2: COUNT OFs late.",
        description="OFs fechadas após o prazo",
        synonyms=("OFs atrasadas fecho", "late delivery"),
    ),
    "producao_schedule_aderencia.dias_atraso_avg": MeasureSpec(
        name="producao_schedule_aderencia.dias_atraso_avg",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.W2: AVG dias entre actual_close e promised_date para as "
            "late. TEMPO; cross-row AVG."
        ),
        description="Dias médios de atraso (apenas OFs late)",
        synonyms=("atraso médio dias", "lag entrega"),
    ),
    # ── Q.108.W2: phase transition time ──
    "producao_phase_transition.total": MeasureSpec(
        name="producao_phase_transition.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "fase_origem", "fase_destino"}),
        business_decision=(
            "Q.108.W2: COUNT transições fase_origem→fase_destino limpas "
            "(end < next_start). CONTAGEM aditiva."
        ),
        description="Transições limpas entre fases consecutivas",
        synonyms=("transições", "passagens fase", "transitions"),
    ),
    "producao_phase_transition.transition_avg": MeasureSpec(
        name="producao_phase_transition.transition_avg",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "fase_origem", "fase_destino"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.W2: AVG horas idle entre fim de fase e início da seguinte. "
            "Mede queue entre estações. TEMPO; cross-row AVG."
        ),
        description="Tempo médio de transição entre fases (horas)",
        synonyms=(
            "idle time", "tempo entre fases", "queue", "espera entre fases",
            "tempo morto", "transition time",
        ),
    ),
    "producao_phase_transition.transition_p50": MeasureSpec(
        name="producao_phase_transition.transition_p50",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "fase_origem", "fase_destino"}),
        aggregation="AVG",
        business_decision="Q.108.W2: P50 horas transição. Cross-row AVG.",
        description="Mediana das horas de transição entre fases",
        synonyms=("mediana transição", "P50 idle"),
    ),
    "producao_phase_transition.transition_p90": MeasureSpec(
        name="producao_phase_transition.transition_p90",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "fase_origem", "fase_destino"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.W2: P90 horas transição — 90% das transições em <= este nº "
            "horas. SLA-like."
        ),
        description="P90 das horas de transição entre fases",
        synonyms=("pior transição", "P90 transição"),
    ),
    # ── Q.108.W2: lead time entrega ──
    "logistica_lead_time_entrega.entregas": MeasureSpec(
        name="logistica_lead_time_entrega.entregas",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.W2: COUNT entregas (TR_DATA preenchida + TROF_ENVIADO=TRUE) "
            "por mês. CONTAGEM aditiva."
        ),
        description="Número de entregas por mês",
        synonyms=("entregas", "expedições", "shipments"),
    ),
    "logistica_lead_time_entrega.lead_time_avg": MeasureSpec(
        name="logistica_lead_time_entrega.lead_time_avg",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.W2: AVG dias entre MAX(OFFP_DATAFIM) e TR_DATA. "
            "TEMPO em dias; cross-row AVG."
        ),
        description="Lead time entrega médio (dias)",
        synonyms=(
            "lead time entrega", "dias até entregar", "tempo entrega",
            "dias OF→cliente", "delivery lead time",
        ),
    ),
    "logistica_lead_time_entrega.lead_time_p50": MeasureSpec(
        name="logistica_lead_time_entrega.lead_time_p50",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision="Q.108.W2: P50 dias lead time entrega.",
        description="Mediana lead time entrega (dias)",
        synonyms=("mediana entrega",),
    ),
    "logistica_lead_time_entrega.lead_time_p90": MeasureSpec(
        name="logistica_lead_time_entrega.lead_time_p90",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision="Q.108.W2: P90 dias lead time entrega — SLA candidato.",
        description="P90 lead time entrega (dias)",
        synonyms=("SLA entrega", "P90 entrega"),
    ),
    # ── Q.108.W3: idade de moldes ──
    "moldes_idade.activos": MeasureSpec(
        name="moldes_idade.activos",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision="Q.108.W3: COUNT plan.mold WHERE active=TRUE (snapshot).",
        description="Moldes activos (active=TRUE)",
        synonyms=("moldes activos", "moldes em uso", "moldes na frota"),
    ),
    "moldes_idade.com_data": MeasureSpec(
        name="moldes_idade.com_data",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.W3: COUNT moldes com acquired_date preenchida — "
            "denominador para AVG idade. CONTAGEM."
        ),
        description="Moldes com acquired_date populada",
        synonyms=("moldes com data", "moldes datados"),
    ),
    "moldes_idade.idade_avg": MeasureSpec(
        name="moldes_idade.idade_avg",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.W3: AVG anos = AVG((now - acquired_date) / 365.25). "
            "TEMPO em anos; cross-row AVG."
        ),
        description="Idade média dos moldes em anos",
        synonyms=(
            "idade moldes", "idade média moldes", "moldes antigos",
            "vida média molde",
        ),
    ),
    "moldes_idade.idade_p50": MeasureSpec(
        name="moldes_idade.idade_p50",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision="Q.108.W3: P50 idade — mediana em anos.",
        description="Mediana de idade dos moldes (anos)",
        synonyms=("mediana idade moldes",),
    ),
    "moldes_idade.idade_max": MeasureSpec(
        name="moldes_idade.idade_max",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="MAX",
        business_decision="Q.108.W3: MAX idade — molde mais antigo.",
        description="Idade do molde mais antigo (anos)",
        synonyms=("molde mais antigo", "MAX idade molde"),
    ),
    # ── Q.108.W3: ETL freshness ──
    "plataforma_etl_freshness.freshness_avg": MeasureSpec(
        name="plataforma_etl_freshness.freshness_avg",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "source"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.W3: AVG horas desde a última run OK por source."
        ),
        description="Idade média (horas) da última sync por source",
        synonyms=(
            "ETL freshness", "idade última sync", "freshness médio",
            "freshness dos mirrors",
        ),
    ),
    "plataforma_etl_freshness.freshness_max": MeasureSpec(
        name="plataforma_etl_freshness.freshness_max",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "source"}),
        aggregation="MAX",
        business_decision="Q.108.W3: MAX horas — pior caso. Sinaliza ETL parado.",
        description="Idade máxima (horas) entre as sources",
        synonyms=("pior freshness", "ETL parado"),
    ),
    "plataforma_etl_freshness.failed_30d": MeasureSpec(
        name="plataforma_etl_freshness.failed_30d",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "source"}),
        business_decision="Q.108.W3: COUNT ETL runs FAILED nos últimos 30 dias.",
        description="ETL runs falhadas nos últimos 30 dias",
        synonyms=(
            "ETL errors", "sync errors", "runs falhadas", "ERP sync errors",
        ),
    ),
    "plataforma_etl_freshness.ok_30d": MeasureSpec(
        name="plataforma_etl_freshness.ok_30d",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "source"}),
        business_decision="Q.108.W3: COUNT ETL runs OK nos últimos 30 dias.",
        description="ETL runs OK nos últimos 30 dias",
        synonyms=("ETL OK", "runs ok"),
    ),
    # ── Q.108.W3: audit log activity ──
    "plataforma_audit_atividade.entries": MeasureSpec(
        name="plataforma_audit_atividade.entries",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "entity_type", "action"}),
        business_decision=(
            "Q.108.W3: COUNT audit_log entries por dia × entity × action."
        ),
        description="Entries de audit_log",
        synonyms=("audit entries", "audit log", "registos auditoria"),
    ),
    "plataforma_audit_atividade.actors": MeasureSpec(
        name="plataforma_audit_atividade.actors",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "entity_type", "action"}),
        aggregation="MAX",
        business_decision=(
            "Q.108.W3: COUNT DISTINCT actor_id (DAU). NÃO aditivo entre dias — "
            "aggregation=MAX para snapshot diário."
        ),
        description="Active users (DAU / contagem distinct actors)",
        synonyms=(
            "active users", "DAU", "MAU", "utilizadores activos", "DAU/MAU",
        ),
    ),
    # ── Q.108.H: ARPU pre-computed ──
    "comercial_arpu.eur_por_cliente": MeasureSpec(
        name="comercial_arpu.eur_por_cliente",
        unit=CanonicalUnit.DINHEIRO,
        dimensions_supported=frozenset({"tempo", "disciplina", "pais"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.H: ARPU pré-computado em marts.v_arpu_mes "
            "(facturado_total / clientes_activos) por mês×disciplina×país. "
            "AVG cross-row — NÃO SUM (é ratio). NÃO existe como sum-up "
            "global directo porque clientes_activos é COUNT DISTINCT."
        ),
        description="ARPU (€/cliente activo) por mês × disciplina × país",
        synonyms=(
            "ARPU", "average revenue per user", "euros por cliente",
            "receita por cliente", "facturação por cliente",
        ),
    ),
    "comercial_arpu.facturado_total": MeasureSpec(
        name="comercial_arpu.facturado_total",
        unit=CanonicalUnit.DINHEIRO,
        dimensions_supported=frozenset({"tempo", "disciplina", "pais"}),
        business_decision=(
            "Q.108.H: numerador do ARPU (DINHEIRO aditivo)."
        ),
        description="Facturação total agregada (numerador do ARPU)",
        synonyms=("facturação por país", "facturação ARPU"),
    ),
    "comercial_arpu.clientes_activos": MeasureSpec(
        name="comercial_arpu.clientes_activos",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "disciplina", "pais"}),
        business_decision=(
            "Q.108.H: clientes activos pré-computados por linha (mês × "
            "disciplina × país). CONTAGEM. NÃO somar entre meses — é "
            "DISTINCT ao nível de linha."
        ),
        description="Clientes activos por mês × disciplina × país",
        synonyms=("clientes activos disciplina", "DISTINCT clientes"),
    ),
    # ── Q.108.H: MoM growth ──
    "comercial_facturacao_mom.mom_pct": MeasureSpec(
        name="comercial_facturacao_mom.mom_pct",
        unit=CanonicalUnit.FRACAO,
        dimensions_supported=frozenset({"tempo", "disciplina"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.H: MoM growth pré-computado com LAG() em "
            "marts.v_facturacao_mom. FRACAO (-1=−100%, +1=+100%). "
            "AVG cross-row (NÃO SUM)."
        ),
        description="Variação MoM da facturação (-1.0..+inf, mostrar como %)",
        synonyms=(
            "MoM growth", "crescimento mensal", "variação mensal",
            "growth mês a mês", "MoM percent",
        ),
    ),
    "comercial_facturacao_mom.facturado_eur": MeasureSpec(
        name="comercial_facturacao_mom.facturado_eur",
        unit=CanonicalUnit.DINHEIRO,
        dimensions_supported=frozenset({"tempo", "disciplina"}),
        business_decision=(
            "Q.108.H: facturado_eur por (mês, disciplina) — mesma fonte que "
            "comercial_facturacao_disciplina mas exposto sob este cube para "
            "narração junto do mom_pct."
        ),
        description="Facturação mensal por disciplina (referência do MoM)",
        synonyms=("facturação mensal", "vendas mês"),
    ),
    "comercial_facturacao_mom.prev_eur": MeasureSpec(
        name="comercial_facturacao_mom.prev_eur",
        unit=CanonicalUnit.DINHEIRO,
        dimensions_supported=frozenset({"tempo", "disciplina"}),
        business_decision=(
            "Q.108.H: facturado_eur do mês anterior (LAG). DINHEIRO, mas "
            "NÃO somar com facturado_eur do mesmo período (duplicação)."
        ),
        description="Facturação do mês anterior (referência do MoM)",
        synonyms=("mês anterior facturação",),
    ),
    # ── Q.108.H: HHI clientes ──
    "comercial_hhi.indice": MeasureSpec(
        name="comercial_hhi.indice",
        unit=CanonicalUnit.FRACAO,
        dimensions_supported=frozenset({"tempo", "disciplina"}),
        aggregation="AVG",
        business_decision=(
            "Q.108.H: HHI = SUM(quota²) por (mês × disciplina). Range [0,1]. "
            "AVG cross-row (NÃO SUM — é índice próprio do período). "
            "Thresholds canónicos: <0.15 baixa, 0.15-0.25 média, >0.25 alta."
        ),
        description="HHI de concentração de clientes (0-1)",
        synonyms=(
            "HHI", "Herfindahl", "concentração clientes",
            "índice concentração", "dependência clientes",
        ),
    ),
    "comercial_hhi.n_clientes": MeasureSpec(
        name="comercial_hhi.n_clientes",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "disciplina"}),
        business_decision=(
            "Q.108.H: COUNT clientes activos no período (mês × disciplina). "
            "CONTAGEM — somar entre meses NÃO faz sentido (sobreposições)."
        ),
        description="Número de clientes a comprar no período",
        synonyms=("clientes no período", "n clientes mês"),
    ),
    "comercial_hhi.quota_max": MeasureSpec(
        name="comercial_hhi.quota_max",
        unit=CanonicalUnit.FRACAO,
        dimensions_supported=frozenset({"tempo", "disciplina"}),
        aggregation="MAX",
        business_decision=(
            "Q.108.H: quota do maior cliente (0-1). Cross-row MAX."
        ),
        description="Quota do maior cliente do período (% da receita)",
        synonyms=("maior cliente quota", "concentração single cliente"),
    ),
    "comercial_hhi.receita_total": MeasureSpec(
        name="comercial_hhi.receita_total",
        unit=CanonicalUnit.DINHEIRO,
        dimensions_supported=frozenset({"tempo", "disciplina"}),
        business_decision="Q.108.H: SUM facturado positivo (denominador HHI).",
        description="Receita total do período (denominador HHI)",
        synonyms=("receita HHI",),
    ),
    # ── Q.108.J.2: top moldes mais usados ──
    "moldes_top_uso.utilizacoes": MeasureSpec(
        name="moldes_top_uso.utilizacoes",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(
            {"tempo", "mold_code", "molde_nome", "mold_type"}
        ),
        business_decision=(
            "Q.108.J.2: SUM(usage_counter) de plan.mold. Counter ERP "
            "MLD_UTILIZ populado pela ETL desde Q.108.J.2. CONTAGEM "
            "aditiva entre moldes; ORDER BY DESC permite top-N."
        ),
        description="Utilizações por molde (contador ERP MLD_UTILIZ)",
        synonyms=(
            "top moldes", "moldes mais usados", "MLD_UTILIZ",
            "utilizações molde", "ranking moldes",
        ),
    ),
    "moldes_top_uso.max_single": MeasureSpec(
        name="moldes_top_uso.max_single",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(
            {"tempo", "mold_code", "molde_nome", "mold_type"}
        ),
        aggregation="MAX",
        business_decision=(
            "Q.108.J.2: MAX(usage_counter) — molde mais usado isoladamente. "
            "Cross-row MAX."
        ),
        description="Molde com maior contador isolado (top-1)",
        synonyms=("molde mais usado", "top-1 molde"),
    ),
    "moldes_top_uso.moldes_count": MeasureSpec(
        name="moldes_top_uso.moldes_count",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(
            {"tempo", "mold_code", "molde_nome", "mold_type"}
        ),
        business_decision="Q.108.J.2: COUNT moldes activos com counter > 0.",
        description="Número de moldes com utilizações > 0",
        synonyms=("moldes com uso", "moldes com counter"),
    ),
    # ── Q.108.L.2: copilot latency ──
    "plataforma_copilot_latency.requests": MeasureSpec(
        name="plataforma_copilot_latency.requests",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "route"}),
        business_decision="Q.108.L.2: COUNT total requests por (dia, route).",
        description="Requests ao copilot por dia × route",
        synonyms=("copilot requests", "asks ao copilot", "queries"),
    ),
    "plataforma_copilot_latency.abstain": MeasureSpec(
        name="plataforma_copilot_latency.abstain",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "route"}),
        business_decision="Q.108.L.2: COUNT requests com status=abstain.",
        description="Requests onde o copilot se absteve",
        synonyms=("abstain count", "copilot absteve"),
    ),
    "plataforma_copilot_latency.errors": MeasureSpec(
        name="plataforma_copilot_latency.errors",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "route"}),
        business_decision="Q.108.L.2: COUNT requests com status=error.",
        description="Requests com erro (LLM down, etc.)",
        synonyms=("copilot errors", "LLM errors"),
    ),
    "plataforma_copilot_latency.latency_avg": MeasureSpec(
        name="plataforma_copilot_latency.latency_avg",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "route"}),
        aggregation="AVG",
        business_decision="Q.108.L.2: AVG latency_ms; cross-row AVG.",
        description="Latency média do copilot (ms)",
        synonyms=("copilot latency", "tempo resposta", "AVG latency"),
    ),
    "plataforma_copilot_latency.latency_p50": MeasureSpec(
        name="plataforma_copilot_latency.latency_p50",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "route"}),
        aggregation="AVG",
        business_decision="Q.108.L.2: P50 latency (mediana).",
        description="P50 latency do copilot (ms)",
        synonyms=("P50 latency",),
    ),
    "plataforma_copilot_latency.latency_p95": MeasureSpec(
        name="plataforma_copilot_latency.latency_p95",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "route"}),
        aggregation="AVG",
        business_decision="Q.108.L.2: P95 — SLA target. Cross-row AVG.",
        description="P95 latency do copilot (ms)",
        synonyms=("P95 latency", "SLA copilot"),
    ),
    "plataforma_copilot_latency.latency_p99": MeasureSpec(
        name="plataforma_copilot_latency.latency_p99",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "route"}),
        aggregation="AVG",
        business_decision="Q.108.L.2: P99 latency — worst case observado.",
        description="P99 latency do copilot (ms)",
        synonyms=("P99 latency", "pior latency"),
    ),
    # ── Q.108.L.2: RAG hit rate + citações ──
    "plataforma_copilot_rag.hit_rate": MeasureSpec(
        name="plataforma_copilot_rag.hit_rate",
        unit=CanonicalUnit.FRACAO,
        dimensions_supported=frozenset({"tempo", "route"}),
        business_decision=(
            "Q.108.L.2: ratio SUM(n_rag_hit)/SUM(n_requests). FRACAO 0-1; "
            "NUNCA SUM(taxa)."
        ),
        description="% requests com chunks RAG retrieved > 0",
        synonyms=(
            "RAG hit rate", "RAG hits", "% RAG", "chunks retrieved rate",
        ),
    ),
    "plataforma_copilot_rag.chunks_avg": MeasureSpec(
        name="plataforma_copilot_rag.chunks_avg",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "route"}),
        aggregation="AVG",
        business_decision="Q.108.L.2: AVG chunks RAG retrieved.",
        description="Chunks RAG médios retrieved por request",
        synonyms=("chunks RAG", "AVG chunks"),
    ),
    "plataforma_copilot_rag.citations_avg": MeasureSpec(
        name="plataforma_copilot_rag.citations_avg",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "route"}),
        aggregation="AVG",
        business_decision="Q.108.L.2: AVG citations_count.",
        description="Citações médias por resposta",
        synonyms=("citações por resposta", "AVG citations"),
    ),
    "plataforma_copilot_rag.requests": MeasureSpec(
        name="plataforma_copilot_rag.requests",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "route"}),
        business_decision="Q.108.L.2: COUNT requests no scope RAG.",
        description="Requests considerados na taxa RAG",
        synonyms=("requests RAG",),
    ),
    # ── Q.108.L.2: copilot feedback ──
    "plataforma_copilot_feedback.taxa_positivo": MeasureSpec(
        name="plataforma_copilot_feedback.taxa_positivo",
        unit=CanonicalUnit.FRACAO,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.108.L.2: ratio SUM(n_positive)/SUM(n_feedback). FRACAO 0-1; "
            "NUNCA SUM(taxa)."
        ),
        description="% feedback positivo no copilot",
        synonyms=(
            "feedback positivo", "votos positivos", "taxa aprovação copilot",
        ),
    ),
    "plataforma_copilot_feedback.total": MeasureSpec(
        name="plataforma_copilot_feedback.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision="Q.108.L.2: COUNT feedback total recebido.",
        description="Total de feedback no mês",
        synonyms=("total feedback", "votos copilot"),
    ),
    "plataforma_copilot_feedback.rating_avg": MeasureSpec(
        name="plataforma_copilot_feedback.rating_avg",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        aggregation="AVG",
        business_decision="Q.108.L.2: AVG rating (1-5). NULL se sem rating.",
        description="Rating médio (escala 1-5)",
        synonyms=("rating médio", "estrelas copilot"),
    ),
    # ── Q.108.F.3b: throughput semanal por modelo × disciplina ──
    # ── Q.108.G: consumo material POR OF ──
    "consumo_by_of.custo_eur": MeasureSpec(
        name="consumo_by_of.custo_eur",
        unit=CanonicalUnit.DINHEIRO,
        dimensions_supported=frozenset(
            {"tempo", "work_order_id", "sku_id", "material"}
        ),
        business_decision=(
            "Q.108.G: SUM(qty_out × P_PRECOCUSTO) preservando work_order_id. "
            "Source: marts.v_consumo_by_of_dia sobre "
            "supply.inventory_ledger_entries (com MOV_OF_ID populado desde "
            "Q.108.G). DINHEIRO aditivo. Destrava margem por OF + "
            "`corr_custo_por_of_vs_facturacao`."
        ),
        description="Custo material em € agregado por OF (e dia/sku/material)",
        synonyms=(
            "custo por OF", "consumo por OF", "custo material OF",
            "matéria-prima por OF", "€ material por OF",
        ),
    ),
    "consumo_by_of.consumo_qty": MeasureSpec(
        name="consumo_by_of.consumo_qty",
        unit=CanonicalUnit.QUANTIDADE_FISICA,
        dimensions_supported=frozenset(
            {"tempo", "work_order_id", "sku_id", "material"}
        ),
        business_decision=(
            "Q.108.G: SUM(qty_out) preservando work_order_id. NUNCA somar "
            "entre materiais com unidades distintas (kg + tambor inválido) — "
            "filtrar/agrupar pelo material primeiro."
        ),
        description="Quantidade física consumida agregada por OF",
        synonyms=(
            "qty por OF", "quantidade por OF", "consumo qty por OF",
        ),
    ),
    "consumo_by_of.n_movimentos": MeasureSpec(
        name="consumo_by_of.n_movimentos",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(
            {"tempo", "work_order_id", "sku_id", "material"}
        ),
        business_decision=(
            "Q.108.G: COUNT movimentos de consumo (transaction_type=consume) "
            "por OF. CONTAGEM aditiva."
        ),
        description="Número de movimentos de consumo por OF",
        synonyms=("movimentos por OF", "linhas consumo OF"),
    ),
    # ── Q.108.M: horas trabalhadas (mão-de-obra real) ──
    "operadores_horas.horas_total": MeasureSpec(
        name="operadores_horas.horas_total",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset(
            {"tempo", "operador_id", "fase_id", "fase"}
        ),
        business_decision=(
            "Q.108.M: SUM(AT_HORAS) sobre marts.v_horas_operador_mes "
            "(factory_raw.apontamento_trabalho, mirror Q.108.M). TEMPO em "
            "horas; aditiva entre operadores e fases dentro do mesmo período."
        ),
        description="Horas trabalhadas (mão-de-obra real)",
        synonyms=(
            "horas trabalhadas", "horas operador", "mão-de-obra",
            "horas apontadas", "AT_HORAS", "labor hours",
        ),
    ),
    "operadores_horas.n_apontamentos": MeasureSpec(
        name="operadores_horas.n_apontamentos",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(
            {"tempo", "operador_id", "fase_id", "fase"}
        ),
        business_decision=(
            "Q.108.M: COUNT entradas de apontamento. CONTAGEM aditiva."
        ),
        description="Número de apontamentos de trabalho",
        synonyms=("apontamentos", "linhas apontamento", "n entries"),
    ),
    "operadores_horas.n_ofs_distintas": MeasureSpec(
        name="operadores_horas.n_ofs_distintas",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(
            {"tempo", "operador_id", "fase_id", "fase"}
        ),
        business_decision=(
            "Q.108.M: COUNT(DISTINCT AT_OF_ID) por linha — já agregada. "
            "NÃO somar entre meses (mesma OF aparece em vários)."
        ),
        description="OFs distintas trabalhadas no período",
        synonyms=("OFs trabalhadas", "ordens distintas"),
    ),
    # ── Q.108.M2: defeitos e operações por operador ──
    "qualidade_defeitos_operador.n_defeitos": MeasureSpec(
        name="qualidade_defeitos_operador.n_defeitos",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "operador_id"}),
        business_decision=(
            "Q.108.M2: SUM(rework_entry) atribuído por operação ao operador "
            "(JOIN offp_eq+of_fp+rework_entry). Workers only (OFFPEQ_CHEFE=FALSE). "
            "CONTAGEM aditiva entre meses e operadores."
        ),
        description="Incidentes de rework atribuídos ao operador",
        synonyms=(
            "defeitos por operador", "rework por operador",
            "incidentes operador",
        ),
    ),
    "qualidade_defeitos_operador.n_ops": MeasureSpec(
        name="qualidade_defeitos_operador.n_ops",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "operador_id"}),
        business_decision=(
            "Q.108.M2: COUNT operações de fase trabalhadas pelo operador. "
            "Denominador natural para taxa de defeitos por operador."
        ),
        description="Operações trabalhadas pelo operador",
        synonyms=("operações por operador", "ops trabalhadas"),
    ),
    "qualidade_defeitos_operador.n_ofs": MeasureSpec(
        name="qualidade_defeitos_operador.n_ofs",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "operador_id"}),
        business_decision=(
            "Q.108.M2: COUNT DISTINCT OFs trabalhadas. NÃO somar entre meses."
        ),
        description="OFs distintas trabalhadas pelo operador",
        synonyms=("OFs por operador",),
    ),
    # ── Q.108.N: devoluções (notas de crédito EPHCF<0) ──
    "comercial_devolucoes.valor_eur": MeasureSpec(
        name="comercial_devolucoes.valor_eur",
        unit=CanonicalUnit.DINHEIRO,
        dimensions_supported=frozenset(
            {"tempo", "cliente", "disciplina", "pais"}
        ),
        business_decision=(
            "Q.108.N: SUM(ABS(EPHCF_FACTURADO)) WHERE facturado<0 sobre "
            "marts.v_devolucoes_mes. Source canónica das devoluções NELO "
            "(não existe tabela DEVOLUCAO dedicada — sinal negativo em EPHCF "
            "é o marcador, decisão Q.102.B). DINHEIRO aditivo entre meses."
        ),
        description="Valor de devoluções/notas de crédito (€)",
        synonyms=(
            "devoluções", "notas de crédito", "reclamações",
            "credit notes", "facturação negativa",
        ),
    ),
    "comercial_devolucoes.n_notas": MeasureSpec(
        name="comercial_devolucoes.n_notas",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(
            {"tempo", "cliente", "disciplina", "pais"}
        ),
        business_decision=(
            "Q.108.N: COUNT notas de crédito por (mês, cliente, disciplina, país)."
        ),
        description="Número de notas de crédito emitidas",
        synonyms=("número devoluções", "n notas crédito"),
    ),
    "producao_throughput_modelo.total": MeasureSpec(
        name="producao_throughput_modelo.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset(
            {"tempo", "modelo", "modelo_id", "disciplina"}
        ),
        business_decision=(
            "Q.108.F.3b: COUNT OFs concluídas (OF_DATAFIM preenchida) por "
            "semana × modelo × disciplina. Source: marts.v_throughput_modelo_sem "
            "(JOIN ordemfabrico → produto → produto_tipo, este último mirror "
            "Q.102.A). CONTAGEM aditiva."
        ),
        description="OFs concluídas por semana × modelo × disciplina",
        synonyms=(
            "throughput modelo", "throughput semanal", "OFs por modelo",
            "produção por modelo", "barcos por modelo", "K1 throughput",
            "K2 throughput", "K4 throughput",
        ),
    ),
    # ── Q.152: OFs produzidas/fechadas por DIA (granularidade diária) ──
    "producao_ofs_fechadas_dia.total": MeasureSpec(
        name="producao_ofs_fechadas_dia.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo"}),
        business_decision=(
            "Q.152: COUNT(*) de OFs fechadas por DIA em "
            "marts.v_ofs_fechadas_dia (OF_DATAFIM preenchida no header de "
            "factory_raw.ordemfabrico). MESMA definição canónica de fecho que "
            "producao_throughput_modelo (OF_DATAFIM), mas granularidade DIÁRIA "
            "— responde 'quantas OFs hoje'. CONTAGEM aditiva. NÃO confundir com "
            "producao_lead_time_of.ofs_fechadas (envelope of_fp, MENSAL)."
        ),
        description="Número de OFs produzidas/fechadas por dia (OF_DATAFIM)",
        synonyms=(
            "OFs produzidas", "ofs produzidas", "ordens produzidas",
            "produção do dia", "OFs fechadas hoje", "barcos produzidos",
            "produzidas hoje", "throughput diário", "OFs concluídas hoje",
            "quantas ofs hoje", "produzimos hoje", "barcos feitos hoje",
            "ordens de fabrico produzidas",
        ),
    ),
    # ── Q.106 Medida 1: colaboradores NELO activos ──
    "workforce.colaboradores_activos.total": MeasureSpec(
        name="workforce.colaboradores_activos.total",
        unit=CanonicalUnit.CONTAGEM,
        dimensions_supported=frozenset({"tempo", "departamento", "colaborador"}),
        business_decision=(
            "Q.106 Medida 1: COUNT(DISTINCT MOVENT_E_ID) sobre "
            "marts.v_workforce_colaboradores_mes. Definição canónica "
            "(Q.82): colaborador NELO = entidade.E_ACTIVO=1 AND "
            "E_ENT_ID em sub-tipos de ENT_ID=19 Empregado. 'Activo "
            "num período' = teve ≥1 evento em ENT_MOV no período. "
            "Anchor 158 colaboradores activos totais (view "
            "FuncionariosActivos canónica); 144 com eventos em "
            "ENT_MOV no histórico; 124 activos em 2024. "
            "Decisão Luís: transparência total — dim `colaborador` "
            "é normal (análoga a `cliente`/`agente`) e permite "
            "ranking individual + drill por pessoa. SEM k-anonymity."
        ),
        description="Contagem de colaboradores NELO activos no período (E_ACTIVO=1 + evento ENT_MOV)",
        synonyms=(
            "colaboradores", "trabalhadores", "funcionários",
            "operadores", "pessoas", "equipa", "headcount",
            "quantas pessoas", "tamanho equipa", "n colaboradores",
            "FTE", "activos", "empregados", "staff",
            "workforce", "RH", "recursos humanos",
        ),
    ),
    # ── Q.106 Medida 2: horas extra (MET=1) ──
    "workforce.horas_extra.total": MeasureSpec(
        name="workforce.horas_extra.total",
        unit=CanonicalUnit.TEMPO,
        dimensions_supported=frozenset({"tempo", "departamento", "colaborador"}),
        business_decision=(
            "Q.106 Medida 2: SUM(DATEDIFF horas) sobre "
            "marts.v_workforce_horas_extra_mes WHERE MOVENT_MET_ID=1 "
            "(Horas Extra). Q.82 documentou: MOVENT_HORAS é SEMPRE "
            "0 no ERP — calcular sempre via EXTRACT(EPOCH FROM "
            "(DATA_F - DATA_I)) / 3600. Anchor histórico: 220 057h "
            "em 64 784 eventos por 220 colaboradores. 2024: "
            "13 196h em 2 721 eventos por 83 colaboradores. Top "
            "2024: Albino Mesquita 525h, Isilda Moreira 496h, Bruno "
            "Costa Martins 412h. Decisão Luís: transparência total "
            "— ranking individual permitido; drill por pessoa "
            "permitido. SEM k-anonymity."
        ),
        description="Horas extra (h) dos colaboradores NELO (MET=1 em ENT_MOV)",
        synonyms=(
            "horas extra", "h extra", "extra", "overtime",
            "MET=1", "Horas Extra", "horas suplementares",
            "trabalho extra", "horas a mais",
            "quem fez mais horas", "top horas extra", "ranking horas",
        ),
    ),
}


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ API — única forma de outros módulos consumirem o contrato.               ║
# ╚══════════════════════════════════════════════════════════════════════════╝


def is_physical_unit_measure(measure: str) -> bool:
    """True se a medida tem unidade física com sub-unidades (kg/tambor/€/kg).

    Substitui `PHYSICAL_UNIT_MEASURES` do Q.95.1 — agora derivado do REGISTRY.
    A regra anti-soma-cega dispara em medidas com sub-unidades co-identidade
    via `unidade_id`. Q.102 refinamento: ser DINHEIRO/QUANTIDADE_FISICA já
    NÃO é suficiente — `comercial_facturacao.total` é DINHEIRO mas em base
    monetária única (€) sem `unidade_id` em `dimensions_supported`, logo
    SUM é sempre semântico. A condição real é "a medida pode SOMAR
    sub-unidades incompatíveis se não filtrar/separar". Isso requer:
      (a) unit em {QUANTIDADE_FISICA, DINHEIRO} (não-CONTAGEM/FRACAO/TEMPO);
      (b) `unidade_id` em `dimensions_supported` (a medida tem sub-unidades).
    Sem (b), a regra Q.95.1 é falso positivo.
    """
    spec = MEASURE_REGISTRY.get(measure)
    if spec is None:
        return False
    if spec.unit not in {CanonicalUnit.QUANTIDADE_FISICA, CanonicalUnit.DINHEIRO}:
        return False
    return "unidade_id" in spec.dimensions_supported


def is_monetary_measure(measure: str) -> bool:
    """True se a medida é em € (DINHEIRO). Usado pelo guard de narração."""
    spec = MEASURE_REGISTRY.get(measure)
    return spec is not None and spec.unit == CanonicalUnit.DINHEIRO


def is_derived_measure_request(question: str) -> str | None:
    """Detecta pergunta sobre medida derivada inexistente (Q.95.1 c07).

    Devolve a substring que disparou o match, ou None se não bate. Defesa
    primária é o prompt [cube_interpret.md regra 6]; este regex é rede de
    segurança pós-pergunta.
    """
    m = _DERIVED_MEASURE_PATTERNS.search(question)
    return m.group(0) if m else None


def is_causal_question(question: str) -> str | None:
    """Detecta pergunta CAUSAL ("porque", "causa", "gargalo", …) (Q.96).

    Devolve a substring que disparou ou None. O Cube responde
    "quanto/qual", nunca "porquê". Causalidade tem rota separada
    (`_DIAGNOSTIC_TRIGGERS` em [src/copilot/intent_router.py] +
    [src/copilot/causal/nelo_dag.py]). O `/ask-cube` abstém com referência.
    """
    m = _CAUSAL_QUESTION_PATTERNS.search(question)
    return m.group(0) if m else None


def is_fractional_measure(measure: str) -> bool:
    """True se a medida é FRACAO (0-1, apresentar como % na narração)."""
    spec = MEASURE_REGISTRY.get(measure)
    return spec is not None and spec.unit == CanonicalUnit.FRACAO


def measure_display_unit(measure: str) -> str:
    """Unidade de apresentação ('€' | '%' | '') de um card de KPI.

    Espelha a convenção do `formatValue` do frontend (KPIsTab): DINHEIRO → €,
    FRACAO → % (ratio 0-1 mostrado como percentagem), restantes → '' (número
    cru — contagem, quantidade física, horas, temperatura). Medida fora do
    registo → ''.
    """
    if is_monetary_measure(measure):
        return "€"
    if is_fractional_measure(measure):
        return "%"
    return ""


def list_measure_catalog() -> list[dict[str, object]]:
    """Catálogo serializável das measures registadas — alimenta o picker de KPIs.

    Itera o `MEASURE_REGISTRY` (fonte única) e devolve, por medida, os campos
    que o menu "Adicionar indicador" do frontend precisa. NÃO toca no Cube REST
    (lê só o contrato) → determinístico e barato. Ordenado por (domínio, nome)
    para um menu estável.

    Cada entrada:
      - `name`: id canónico ("consumo_material.consumo").
      - `label`: `description` PT-PT (fallback para `name`).
      - `unit`: '€' | '%' | '' (ver `measure_display_unit`).
      - `domain`: prefixo do cube ("consumo_material") — agrupa o menu.
      - `dimensions`: lista ordenada de `dimensions_supported`.
      - `supports_period`: True se a medida tem a dimensão `tempo` (habilita o
        filtro "este mês" no card).
    """
    catalog: list[dict[str, object]] = []
    for name, spec in MEASURE_REGISTRY.items():
        catalog.append(
            {
                "name": name,
                "label": spec.description or name,
                "unit": measure_display_unit(name),
                "domain": name.split(".", 1)[0],
                "dimensions": sorted(spec.dimensions_supported),
                "supports_period": "tempo" in spec.dimensions_supported,
            }
        )
    catalog.sort(key=lambda m: (m["domain"], m["name"]))
    return catalog


def can_sum_measures(measures: list[str]) -> tuple[bool, str | None]:
    """Verifica matriz de soma (SUM_COMPATIBILITY).

    Devolve `(True, None)` se todas as medidas partilham a mesma `CanonicalUnit`
    (podem somar/coexistir num só agregado); `(False, razão)` caso contrário.

    Preparado para D3 (€ + horas) quando OEE/workforce trouxerem outras
    unidades. Para o registo actual (consumo/custo/n_movimentos), apanha
    quando o LLM tenta misturar consumo+n_movimentos numa só agregação.
    """
    if not measures:
        return True, None
    specs = [(m, MEASURE_REGISTRY.get(m)) for m in measures]
    unknown = [m for m, s in specs if s is None]
    if unknown:
        return False, f"medidas desconhecidas no contrato: {sorted(unknown)}"
    units = {s.unit for _, s in specs if s is not None}
    if len(units) > 1:
        return False, (
            f"medidas têm unidades canónicas distintas {sorted(u.value for u in units)} "
            f"— soma só é permitida dentro da mesma unidade canónica"
        )
    return True, None


def assert_soma_safe(query: "CubeQuery") -> list[str]:
    """Subsume Q.95.1 anti-soma-cega como invariante do contrato.

    Regras a nível de query (Cube devolve colunas, não soma cross-measure):
      1. Medida com unidade física (QUANTIDADE_FISICA / DINHEIRO) numa query
         que não separa por `unidade_id` E não filtra material com `equals`
         → soma cega (D1 / c03 Q.95.1).
      2. Caso preservado (histórico Q.93.C): filter `contains material` exige
         `material` E `unidade_id` em dims — mensagem mais informativa.

    **Nota D3**: mistura de medidas com `CanonicalUnit` distintas no MESMO
    Cube query NÃO é proibida aqui — o Cube devolve cada medida em sua
    coluna, não as agrega entre si. A defesa D3 (€ + horas → recusa) vive
    em `can_sum_measures` como API para agentes que COMPÕEM medidas (e.g.,
    quando OEE/workforce trouxerem outras unidades e um agente quiser somar
    explicitamente). Aplicar a defesa cross-unit aqui partiria queries
    legítimas como `measures=[consumo, custo]` (Q.94 c02 "gastámos" ambas).

    Devolve lista de violações (vazia = OK).
    """
    violations: list[str] = []

    # Regra 1 — soma cega de medida física sem grouping/equals (Q.95.1 c03).
    physical_measures = [m for m in query.measures if is_physical_unit_measure(m)]
    if physical_measures:
        has_unidade_dim = any(d.endswith(".unidade_id") for d in query.dimensions)
        has_equals_material = any(
            f.member.endswith(".material") and f.operator == "equals"
            for f in query.filters
        )
        if not has_unidade_dim and not has_equals_material:
            violations.append(
                "medida com unidade física (consumo/custo) sem `unidade_id` em "
                "dimensions e sem filter `equals` em material — produz soma cega "
                "de unidades incompatíveis (kg + tambor + m² + €/kg + €/tambor). "
                "Acrescenta `unidade_id` às dimensions OU filtra um material "
                "específico com `equals`."
            )

    # Regra 2 — filter `contains material` exige material + unidade_id em dims
    # (preservada de Q.93.C com mensagem informativa específica).
    has_ambiguous_material_filter = any(
        f.member.endswith(".material") and f.operator in {"contains", "notContains"}
        for f in query.filters
    )
    if has_ambiguous_material_filter:
        has_material_dim = any(d.endswith(".material") for d in query.dimensions)
        has_unidade_dim = any(d.endswith(".unidade_id") for d in query.dimensions)
        if not (has_material_dim and has_unidade_dim):
            violations.append(
                "filtro ambíguo de material (contains) exige `dimensions` "
                "com `material` E `unidade_id` para não somar unidades "
                "diferentes (kg + tambor + unidades)"
            )

    return violations


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ Q.97 FIX 2 — `assert_dims_supported` enforced no validator.              ║
# ╚══════════════════════════════════════════════════════════════════════════╝


def _canonical_dim_name(member: str) -> str:
    """Extrai o nome canónico do dim (sufixo após o último '.').

    `qualidade.fase` → `fase`. `consumo_material.unidade_id` → `unidade_id`.
    """
    if "." in member:
        return member.rsplit(".", 1)[-1]
    return member


def assert_dims_supported(query: "CubeQuery") -> list[str]:
    """Q.97 FIX 2 — `MeasureSpec.dimensions_supported` enforced.

    Para cada measure conhecida em `query.measures`, verifica se todas as
    dimensions (e timeDimensions) usadas estão em `dimensions_supported` da
    spec. Se alguma dim não é suportada → violation, abstain.

    Não-paranóia: medidas não registadas (e.g. fakes em testes) são
    saltadas — o `validate_against_catalog` já apanha esses por outro
    caminho. Time dim usa o nome canónico `tempo` (convenção do REGISTRY).
    """
    violations: list[str] = []
    used_dim_names: set[str] = set()
    for d in query.dimensions:
        used_dim_names.add(_canonical_dim_name(d))
    if query.time_dimensions:
        # Convenção: a time dim canónica é "tempo".
        used_dim_names.add("tempo")

    if not used_dim_names:
        return violations

    for measure_name in query.measures:
        spec = MEASURE_REGISTRY.get(measure_name)
        if spec is None:
            continue  # já tratado por validate_against_catalog
        unsupported = used_dim_names - spec.dimensions_supported
        if unsupported:
            violations.append(
                f"medida {measure_name!r} não suporta a(s) dimensão(ões) "
                f"{sorted(unsupported)} — declarada para "
                f"{sorted(spec.dimensions_supported)} apenas. Refaz a query "
                f"ou abstém."
            )
    return violations


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ Q.97 FIX 3 — `is_unsupported_concept_request` (refugo/scrap/rework).    ║
# ╚══════════════════════════════════════════════════════════════════════════╝

# Conceitos coloquiais PT-PT que se assemelham a medidas existentes mas
# têm semântica INDUSTRIAL DISTINTA. Refugo (scrap descartado) ≠ defeito
# (problema potencialmente recuperável). Sem medida registada → abstain.
# Decisão de negócio (Q.97): default abstain. Refinar quando o gestor
# definir se refugo é medida distinta ou sinónimo aceitável.
_UNSUPPORTED_CONCEPT_PATTERNS = re.compile(
    r"\b(?:"
    r"refugos?|scraps?|rejeitad[oa]s?|rejei[çc][ãa]o|"
    r"reprocessament[oa]|retrabalh[oa]s?|rework|"
    r"pe[çc]as?\s+(?:perdidas?|descartad[ao]s?)|"
    r"lixo\s+industrial"
    r")\b",
    re.IGNORECASE,
)


def is_unsupported_concept_request(question: str) -> str | None:
    """Detecta conceito industrial sem medida registada (Q.97 FIX 3).

    Devolve o termo que disparou ou None. Defesa primária no prompt
    (regra 8); este regex é rede pré-LLM.
    """
    m = _UNSUPPORTED_CONCEPT_PATTERNS.search(question)
    return m.group(0) if m else None


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ Q.97 FIX 1 — `is_period_mismatch` (pergunta↔dateRange concordância).    ║
# ╚══════════════════════════════════════════════════════════════════════════╝


# Q.97b — padrões PT-PT de intervalo aberto onde o LLM TEM de manter o
# poder de decidir o fim do range (c09 "Maio até hoje" = [2026-05-01, today]).
# Resolução determinística NÃO se aplica a estes casos — o end depende de
# "hoje" ou outra ancora não-fixa.
_OPEN_INTERVAL_PATTERNS = re.compile(
    r"\b(?:"
    r"at[ée]\s+(?:hoje|agora|ao\s+momento|dia\s+\d{1,2})"
    r"|desde\s+\d|desde\s+(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)"
    r"|entre\s+.+\s+e\s+"
    r"|do\s+dia\s+\d{1,2}.+ao\s+dia\s+\d{1,2}"
    r")",
    re.IGNORECASE,
)


def resolve_question_period(
    question: str,
    today: _dt.date | None = None,
) -> tuple[str, str] | None:
    """Q.97b FIX A — resolução determinística do dateRange da PERGUNTA.

    Devolve `(start_iso, end_iso)` Cube-inclusivo OU `None` se a pergunta
    não permite resolução determinística (intervalo aberto, sem período,
    código de produto confundível com ano, etc.).

    Estratégia "datas determinísticas": o LLM perde o poder de errar o
    período. Quando esta função devolve um range, o caller (interpret.py)
    SOBREPÕE `query.time_dimensions[0].date_range` antes de qualquer
    outro override.

    Casos onde retorna None (deixa LLM):
      - Pergunta sem período explícito.
      - Intervalo aberto ("Maio até hoje", "desde Janeiro", "entre X e Y").
      - Resolução com ano fora [1990, 2100] (código de produto tipo "HX-9000").
      - Resolução "este mês" disparada por "no mês passado" (slot_filler bug).

    Reutiliza `resolve_periodo` de slot_filler com as MESMAS defesas
    aplicadas em `is_period_mismatch`.
    """
    if today is None:
        today = _dt.date.today()

    # 1. Intervalo aberto → LLM decide.
    if _OPEN_INTERVAL_PATTERNS.search(question):
        return None

    try:
        from src.copilot.cube.periods import resolve_periodo
    except ImportError:
        return None

    now_dt = _dt.datetime(today.year, today.month, today.day)
    resolved = resolve_periodo(question, now=now_dt)
    if resolved is None:
        return None

    start, end_exclusive, descricao = resolved

    # Defesa 1: anos fora [1990, 2100] são códigos de produto.
    if not (1990 <= start.year <= 2100):
        return None

    # Defesa 2: "mês passado" mal mapeado para "este mês".
    q_low = question.lower()
    if (
        ("mês passado" in q_low or "mes passado" in q_low
         or "último mês" in q_low or "ultimo mes" in q_low)
        and "este mês" in descricao.lower()
    ):
        return None

    # Cube-inclusivo: end_exclusive - 1 dia.
    end_inclusive = (end_exclusive - _dt.timedelta(days=1)).date()
    return start.date().isoformat(), end_inclusive.isoformat()


def is_period_mismatch(
    question: str,
    query: "CubeQuery",
    today: _dt.date | None = None,
) -> str | None:
    """Q.97 FIX 1 — concordância entre período da PERGUNTA e dateRange Cube.

    Compara os 3 pontos críticos:
      1. PERGUNTA — resolvida deterministicamente via `resolve_periodo()`
         (slot_filler — já cobre PT-PT: "Maio", "Maio de 2026", "último
         mês", "este mês", "este ano", "esta semana", YYYY-MM, etc).
      2. dateRange Cube — `query.timeDimensions[0].dateRange`.
      3. (Narração — separadamente em `narrate.guard_context`.)

    Se a pergunta tem período explícito e o dateRange não o cobre →
    devolve string explicativa para abstain. Caso contrário → None.

    Não-paranóia: pergunta sem período explícito → None (não bloqueia).
    DateRange que cobre o período pedido (e.g. trimestre que inclui o
    mês) → None.
    """
    # Import tardio para evitar ciclo measure_contract ↔ slot_filler.
    try:
        from src.copilot.cube.periods import resolve_periodo
    except ImportError:
        return None  # graceful degrade se rotearmos para outros usos

    if today is None:
        today = _dt.date.today()
    now_dt = _dt.datetime(today.year, today.month, today.day)

    resolved = resolve_periodo(question, now=now_dt)
    if resolved is None:
        return None  # pergunta sem período explícito → não valida

    pergunta_start, pergunta_end, descricao = resolved

    # Q.97 defesa contra falsos positivos do resolve_periodo:
    # 1. Anos fora de [1990, 2100] são códigos de produto (ex.: "HX-9000",
    #    "EN 720") — slot_filler apanha-os com `\b\d{4}\b`. Skip.
    if not (1990 <= pergunta_start.year <= 2100):
        return None
    # 2. "no mês passado" / "mês passado" devia bater "último mês", mas o
    #    slot_filler captura primeiro "no mês" → este mês. Detectar e skip.
    q_low = question.lower()
    if (
        ("mês passado" in q_low or "mes passado" in q_low or "último mês" in q_low
         or "ultimo mes" in q_low)
        and "este mês" in descricao.lower()
    ):
        return None

    # Extrair dateRange do query (primeiro timeDimension com dateRange).
    payload_range: tuple[_dt.date, _dt.date] | None = None
    for td in query.time_dimensions:
        if td.date_range and len(td.date_range) == 2:
            try:
                d0 = _dt.date.fromisoformat(td.date_range[0][:10])
                d1 = _dt.date.fromisoformat(td.date_range[1][:10])
                payload_range = (d0, d1)
                break
            except ValueError:
                continue

    if payload_range is None:
        # Query sem dateRange — não bloqueia (a defesa é só para discordância).
        return None

    # Pergunta resolve para [start, end) — converter para datas inclusivas
    # comparáveis: end é exclusivo, último dia coberto é end - 1.
    p_start = pergunta_start.date()
    p_end_inclusive = (pergunta_end - _dt.timedelta(days=1)).date()

    # Concordância: dateRange Cube tem de COBRIR pelo menos parte do período
    # da pergunta. Se o `payload_range` cai inteiramente fora do
    # `[p_start, p_end_inclusive]` → mismatch.
    if payload_range[1] < p_start or payload_range[0] > p_end_inclusive:
        return (
            f"pergunta refere {descricao!r} ({p_start} a {p_end_inclusive}) "
            f"mas dateRange do query é {payload_range[0]} a {payload_range[1]} "
            f"— período discordante. Re-formula com o período certo ou abstém."
        )

    return None


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ Q.97b FIX B — guard de cobertura da pergunta (fidelidade).               ║
# ╚══════════════════════════════════════════════════════════════════════════╝


# Score mínimo do top-1 retrieval para considerar que um material está
# mencionado. Conservador: muito baixo apanha falsos positivos (pergunta
# "taxa global" + top-1 com score 0.1); muito alto perde casos legítimos.
# 0.3 foi validado empiricamente — top-1 de "Resina Lavesan EN 720" na
# pergunta correspondente tem score ~0.7+.
_MATERIAL_MENTION_SCORE_THRESHOLD = 0.3


# Q.97b — patterns determinísticos PT-PT que sinalizam menção explícita
# de material. Cobre o caso qd04 onde o retrieval híbrido erra o top-1
# (pergunta "do material Resina Lavesan EN 720" — captura o nome após
# "material "). Greedy até stop-word/pontuação.
_EXPLICIT_MATERIAL_KEYWORD = re.compile(
    r"\b(?:material|produto|matéria-prima|materia-prima)\s+",
    re.IGNORECASE,
)

# Q.108.F — mapeamento keyword PT-PT → nome canónico de FASE
# (FP_NOME em factory_raw.fases_producao). Usado para FIX A injecção
# determinística de filter fase + FIX B coverage de fidelidade.
# Pergunta "taxa de defeitos na laminagem em Abril" → fase="Laminagem"
# → filter `contains 'Laminagem'`. Nomes que mapeiam várias sub-fases
# (Acabamento → 8 sub-fases) usam `contains` para agregar.
FASE_CANONICAL_MAP: dict[str, str] = {
    "laminagem": "Laminagem",
    "pintura": "Pintura",
    "corte": "Corte",
    "acabamento": "Acabamento",
    "cura": "Cura",
    "estufa": "Estufa",
    "manutenção": "Manutenção",
    "manutencao": "Manutenção",
    "montagem": "Montagem",
    "soldadura": "Soldadura",
    "preparação": "Preparação",
    "preparacao": "Preparação",
    "envernizamento": "Envernizamento",
    "verniz": "Envernizamento",
}

# Regex que apanha qualquer keyword de fase como palavra inteira PT-PT.
_FASE_KEYWORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in FASE_CANONICAL_MAP) + r")\b",
    re.IGNORECASE,
)


def extract_mentioned_fase(question: str) -> str | None:
    """Q.108.F — detecta fase canónica mencionada na pergunta.

    Devolve o nome canónico (FP_NOME-compatible) ou None. Procura
    keyword PT-PT (laminagem/pintura/corte/acabamento/...) como
    palavra inteira; mapeia para a forma canónica via
    `FASE_CANONICAL_MAP`.

    Família qd04: análogo a `extract_mentioned_material` mas para
    dim `fase`. Usado em FIX A injecção e FIX B coverage.

    Não-paranóia: pergunta sem keyword de fase → None.

    Excepção: se a pergunta tem "por fase" / "cada fase" / "todas as
    fases" (drill-down), NÃO é menção específica de fase → None.
    """
    if not question:
        return None
    q_low = question.lower()
    # Drill-down explícito → não é menção específica.
    if re.search(
        r"\b(?:por\s+fase|cada\s+fase|todas\s+as\s+fases|de\s+todas\s+as\s+fases)\b",
        q_low,
    ):
        return None
    m = _FASE_KEYWORD_RE.search(question)
    if m is None:
        return None
    return FASE_CANONICAL_MAP[m.group(1).lower()]


# Q.108.F — patterns PT-PT que sinalizam pergunta CUMULATIVA/ACUMULADA
# (sem período específico — total histórico do espelho). Família do
# Q.97b mas em sentido OPOSTO: aqui REMOVEMOS o dateRange em vez de
# injectar. Caso fd01: "Faturação em Canoe Sprint acumulada?" — LLM
# injecta dateRange=ano-atual; a regex apanha "acumulada" e força a
# remoção do range, devolvendo o total histórico (€73M vs €1,26M).
_ACCUMULATED_REQUEST_RE = re.compile(
    r"\b(?:"
    r"acumulad[oa]s?"
    r"|hist[óo]ric[oa]s?"
    r"|desde\s+sempre"
    r"|desde\s+o\s+in[ií]cio"
    r"|total\s+(?:geral|hist[óo]rico|de\s+sempre)"
    r"|all[\s-]?time"
    r")\b",
    re.IGNORECASE,
)


def is_accumulated_request(question: str) -> bool:
    """Q.108.F — pergunta pede TOTAL acumulado/histórico (sem período)?

    True para "Canoe Sprint acumulada", "Total histórico de vendas",
    "vendas desde sempre", "all-time top". False para perguntas com
    período explícito ou neutras.

    Usado em conjugação com `resolve_question_period`: se ambos
    disparam ("vendas acumuladas em 2024" — pouco provável), o período
    explícito vence — "acumulado" passa a ser adjectivo retórico, não
    instrução de range.
    """
    if not question:
        return False
    return _ACCUMULATED_REQUEST_RE.search(question) is not None
# Tokens stop que terminam o nome do material (palavras de contexto).
_MATERIAL_STOP_WORDS = {
    "em", "no", "na", "nos", "nas", "de", "do", "da", "dos", "das",
    "durante", "este", "esta", "esse", "essa", "último", "ultima",
    "hoje", "ontem", "para", "que", "porque",
}


def extract_mentioned_material(
    question: str,
    top_materials: list[tuple[str, float]] | None,
) -> str | None:
    """Q.97b FIX B helper — detecta material **mencionado explicitamente**.

    Devolve o nome canónico do material se detectado. Combina 2 estratégias:

    **1. Patterns explícitos** (determinístico, sempre tentado primeiro):
       "material X em Abril" / "produto Y" / "matéria-prima Z" → captura X.

    **2. Top-1 retrieval híbrido** (fallback):
       `top_materials[0]` com score ≥ threshold E ≥1 token (≥4 chars) do
       nome aparecendo literalmente na pergunta.

    Caso contrário devolve None. Não-paranóia: pergunta sem material
    identificado → None → caller não bloqueia.
    """
    # Estratégia 1: pattern explícito — "material X em ...".
    m = _EXPLICIT_MATERIAL_KEYWORD.search(question)
    if m is not None:
        after = question[m.end():].strip()
        # Captura tokens até stop-word PT-PT ou pontuação.
        captured_tokens: list[str] = []
        for tok in re.findall(r"[A-Za-zÀ-ÿ0-9./\-]+|\W+", after):
            t_low = tok.strip().lower()
            if not t_low:
                continue
            # Pontuação terminal interrompe.
            if any(p in tok for p in (",", "?", "!", ":", ";", ".")) and tok.strip() in "?.!:;,":
                break
            # Stop-word (palavra de contexto) interrompe.
            if t_low in _MATERIAL_STOP_WORDS:
                break
            captured_tokens.append(tok.strip())
        captured = " ".join(t for t in captured_tokens if t).strip()
        captured = captured.rstrip("?.,;:").strip()
        if captured and len(captured) >= 4:
            return captured

    # Estratégia 2: top-1 retrieval.
    if not top_materials:
        return None
    name, score = top_materials[0]
    if score < _MATERIAL_MENTION_SCORE_THRESHOLD:
        return None
    tokens = [t.lower() for t in re.findall(r"[A-Za-zÀ-ÿ0-9]{4,}", name)]
    if not tokens:
        return None
    q_low = question.lower()
    if any(tok in q_low for tok in tokens):
        return name
    return None


def assert_question_coverage(
    query: "CubeQuery",
    *,
    material_mencionado: str | None = None,
    fase_mencionada: str | None = None,
) -> list[str]:
    """Q.97b FIX B — guard de fidelidade: entidades MENCIONADAS na pergunta
    têm de estar honradas na query.

    Q.108.F: estendido para `fase_mencionada` (qd01 família qd04).

    Regras:
      1. Se `material_mencionado` is not None E a query NÃO honra material
         (sem filter equals/contains + sem dim material):
         - Se alguma measure tem `material` FORA de `dimensions_supported`
           → violação "medida X não se decompõe por material" (qd04).
         - Senão → violação "pergunta menciona material X mas query
           não o honra" (genérico).
      2. Q.108.F: análogo para `fase_mencionada` (qd01).

    Não-paranóia: parâmetro None → sem violação. Após FIX A injecção
    determinística, esta rede só dispara para casos que escaparam
    (e.g. measure sem dim fase em dimensions_supported).
    """
    violations: list[str] = []

    if material_mencionado:
        has_material_filter = any(
            f.member.endswith(".material")
            and f.operator == "equals"
            and any(
                material_mencionado.lower() == str(v).lower()
                or material_mencionado.lower() in str(v).lower()
                for v in f.values
            )
            for f in query.filters
        )
        # Também aceita contains (filtro ambíguo que apanha o material).
        has_material_contains = any(
            f.member.endswith(".material")
            and f.operator in {"contains", "notContains"}
            for f in query.filters
        )
        has_material_dim = any(d.endswith(".material") for d in query.dimensions)

        if not (has_material_filter or has_material_contains or has_material_dim):
            # Caso especial: medida não suporta material em dimensions_supported.
            for measure_name in query.measures:
                spec = MEASURE_REGISTRY.get(measure_name)
                if spec is not None and "material" not in spec.dimensions_supported:
                    violations.append(
                        f"a pergunta menciona material {material_mencionado!r} mas "
                        f"a medida {measure_name!r} não se decompõe por material "
                        f"(dimensions_supported={sorted(spec.dimensions_supported)}). "
                        "Re-formula sem material OU usa outra medida que suporte."
                    )
                    return violations
            violations.append(
                f"a pergunta menciona material {material_mencionado!r} mas a "
                "query não o filtra nem o agrupa — fidelidade comprometida."
            )

    if fase_mencionada:
        fase_lower = fase_mencionada.lower()
        has_fase_filter_eq = any(
            f.member.endswith(".fase")
            and f.operator == "equals"
            and any(
                fase_lower == str(v).lower() or fase_lower in str(v).lower()
                for v in f.values
            )
            for f in query.filters
        )
        has_fase_contains = any(
            f.member.endswith(".fase")
            and f.operator in {"contains", "notContains"}
            and any(fase_lower in str(v).lower() for v in f.values)
            for f in query.filters
        )
        has_fase_dim = any(d.endswith(".fase") for d in query.dimensions)

        if not (has_fase_filter_eq or has_fase_contains or has_fase_dim):
            # Medida não suporta fase em dimensions_supported (Q.108.F qd01).
            for measure_name in query.measures:
                spec = MEASURE_REGISTRY.get(measure_name)
                if spec is not None and "fase" not in spec.dimensions_supported:
                    violations.append(
                        f"a pergunta menciona fase {fase_mencionada!r} mas "
                        f"a medida {measure_name!r} não se decompõe por fase "
                        f"(dimensions_supported={sorted(spec.dimensions_supported)}). "
                        "Re-formula sem fase OU usa outra medida que suporte."
                    )
                    return violations
            violations.append(
                f"a pergunta menciona fase {fase_mencionada!r} mas a "
                "query não a filtra nem a agrupa — fidelidade comprometida."
            )

    return violations


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ Sanity checks à carga — validar coerência do REGISTRY contra zona fixa. ║
# ╚══════════════════════════════════════════════════════════════════════════╝


def _validate_registry() -> None:
    """Garante que toda entrada no REGISTRY usa unidades/dims canónicas.

    Corre uma vez na importação do módulo. Se um agente adicionar uma medida
    com unit/dim fora da zona fixa, a importação FALHA — não passa pelo
    pytest, não passa pelo backend.
    """
    valid_units = set(CanonicalUnit)
    for name, spec in MEASURE_REGISTRY.items():
        if spec.unit not in valid_units:
            raise ValueError(
                f"measure_contract: medida {name!r} tem unit {spec.unit!r} "
                f"que não é uma `CanonicalUnit` válida. Adiciona à zona fixa "
                f"OU usa uma das existentes: {sorted(u.value for u in valid_units)}"
            )
        invalid_dims = spec.dimensions_supported - CANONICAL_DIMENSIONS
        if invalid_dims:
            raise ValueError(
                f"measure_contract: medida {name!r} suporta dimensões "
                f"{sorted(invalid_dims)} fora de `CANONICAL_DIMENSIONS`. "
                f"Adiciona à zona fixa OU usa uma das existentes: "
                f"{sorted(CANONICAL_DIMENSIONS)}"
            )
        if spec.name != name:
            raise ValueError(
                f"measure_contract: chave {name!r} != spec.name {spec.name!r}"
            )
        # Q.105.A — warning (não-bloqueante) se descrição/sinónimos em falta.
        # O retrieval de medida (BM25+embedding) precisa destes campos; sem eles
        # a medida não é descoberta pela pergunta natural do utilizador.
        if not spec.description or not spec.synonyms:
            import warnings as _warnings
            _warnings.warn(
                f"measure_contract: medida {name!r} sem description/synonyms — "
                "não será descoberta pelo retrieval Q.105 (BM25+embedding). "
                "Preenche os campos para entrar no índice.",
                UserWarning,
                stacklevel=2,
            )


_validate_registry()


# ─── Q.157.D — catálogo de measures gerado para o prompt do interpret ──────
#
# O `cube_interpret.md` descreve à mão só ~14 dos 48 cubes. Quando o retrieval
# de medida (Q.105.A) traz uma medida de um dos outros 34 cubes, o LLM recebe-a
# no enum (constrained decoding) mas SEM bloco de catálogo a descrever o que é.
# Este gerador produz um bloco no mesmo formato dos escritos à mão, a partir do
# MEASURE_REGISTRY — usado como fallback no `_filter_catalog_blocks` do
# interpret para os cubes sem bloco curado. Auto-gerado → nunca diverge.

_UNIT_LABEL: dict[CanonicalUnit, str] = {
    CanonicalUnit.QUANTIDADE_FISICA: "quantidade física (kg/m²/unidade — não somar entre sub-unidades)",
    CanonicalUnit.DINHEIRO: "€ (dinheiro)",
    CanonicalUnit.TEMPO: "tempo (horas)",
    CanonicalUnit.CONTAGEM: "contagem (nº)",
    CanonicalUnit.FRACAO: "fração 0-1 (apresentar como %)",
    CanonicalUnit.TEMPERATURA: "temperatura (°C — agrega MAX/AVG, nunca SUM)",
}


def render_catalog_block(cube_name: str) -> str:
    """Q.157.D — bloco Markdown de catálogo para um cube, gerado do
    ``MEASURE_REGISTRY``, no formato dos blocos ``### Cube: `x``` escritos à
    mão no ``cube_interpret.md``. Devolve "" se o cube não tiver medidas.

    Inclui, por medida: nome canónico, descrição, unidade canónica, dimensões
    suportadas e sinónimos — o suficiente para o LLM a usar correctamente
    mesmo sem bloco curado.
    """
    specs = [
        spec for name, spec in MEASURE_REGISTRY.items()
        if name.split(".", 1)[0] == cube_name
    ]
    if not specs:
        return ""
    lines = [
        f"### Cube: `{cube_name}`",
        "(catálogo auto-gerado do MEASURE_REGISTRY — Q.157.D)",
        "",
        "**Measures**",
    ]
    for spec in sorted(specs, key=lambda s: s.name):
        unit = _UNIT_LABEL.get(spec.unit, getattr(spec.unit, "value", str(spec.unit)))
        dims = ", ".join(sorted(spec.dimensions_supported)) or "—"
        desc = (spec.description or "").strip().rstrip(".")
        line = f"- `{spec.name}` — {desc}. Unidade: {unit}; dimensões: {dims}."
        if spec.synonyms:
            line += f" Sinónimos: {', '.join(spec.synonyms[:8])}."
        lines.append(line)
    return "\n".join(lines) + "\n"
