"""Q.173.Z — Motor de previsão de ruturas de material.

Para cada material relevante, projeta a posição de stock no horizonte
pedido e identifica ruturas prováveis com sugestões honestas (compra,
transferência, replaneamento).

Invariante #8: toda a estimativa está ETIQUETADA. Zero valores inventados.
Campos com incerteza têm flags explícitas (`eta_estimada`, `lead_time_source`,
`consumo_baseado_em_bom`, etc.).

Fontes:
- Stock:       supply.warehouse_stock  (ERP mirror; pode ser negativo — é dado real)
- POs OPEN:    supply.purchase_orders  (ETL do ERP)
- Reservas:    factory_raw.movimento TPMOV=4 MOV_SATISFEITO=false
- BOM:         factory_raw.produto_componente  (COMP_ELIMINADO IS NULL)
- Plano atual: último ScheduleCommit saudável (CommitsService)
- Mínimos:     supply.supply_material_master
- ROPs:        supply.supply_rop_configs
- Nomes:       factory_raw.produto P_NOME
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Número máximo de ordens afetadas a incluir por material
_TOP_ORDERS = 5


# ---------------------------------------------------------------------------
# Tipos de output (algoritmo puro, sem FastAPI)
# ---------------------------------------------------------------------------

class OrdemAfetada:
    """Uma ordem de fabrico cujas ops consomem o material até à data de rutura."""

    __slots__ = ("modelo", "order_id", "start_time")

    def __init__(self, order_id: str, modelo: str, start_time: datetime) -> None:
        self.order_id = order_id
        self.modelo = modelo
        self.start_time = start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "modelo": self.modelo,
            "start_time": self.start_time.isoformat(),
        }


class MaterialEmRisco:
    """Projeção de rutura para um material."""

    def __init__(
        self,
        *,
        product_code: str,
        product_name: str,
        stock_atual: float,
        stock_negativo_erp: bool,
        min_stock: float,
        min_stock_source: str,
        data_rutura_prevista: Optional[date],
        defice: float,
        ordens_afetadas: List[OrdemAfetada],
        sugestao: str,
        sugestao_detalhe: str,
        lead_time_days: int,
        lead_time_source: str,
        data_limite_encomenda: Optional[date],
        outros_armazens: List[Dict[str, Any]],
        consumo_mediano_por_barco: Optional[float],
        pedidos_internos: float = 0.0,
        producao_interna_aberta: float = 0.0,
    ) -> None:
        self.product_code = product_code
        self.product_name = product_name
        self.stock_atual = stock_atual
        self.stock_negativo_erp = stock_negativo_erp
        self.min_stock = min_stock
        self.min_stock_source = min_stock_source
        self.data_rutura_prevista = data_rutura_prevista
        self.defice = defice
        self.ordens_afetadas = ordens_afetadas
        self.sugestao = sugestao
        self.sugestao_detalhe = sugestao_detalhe
        self.lead_time_days = lead_time_days
        self.lead_time_source = lead_time_source
        self.data_limite_encomenda = data_limite_encomenda
        self.outros_armazens = outros_armazens
        self.consumo_mediano_por_barco = consumo_mediano_por_barco
        # Q.174.F0.3 — canais TPMOV=12 (canónico produto_Stock_Necessidades):
        # procura interna aberta (entra no saldo) e produção interna já pedida
        # à Fábrica (alimenta a sugestão).
        self.pedidos_internos = pedidos_internos
        self.producao_interna_aberta = producao_interna_aberta

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_code": self.product_code,
            "product_name": self.product_name,
            "stock_atual": self.stock_atual,
            "stock_negativo_erp": self.stock_negativo_erp,
            "min_stock": self.min_stock,
            "min_stock_source": self.min_stock_source,
            "data_rutura_prevista": (
                self.data_rutura_prevista.isoformat()
                if self.data_rutura_prevista else None
            ),
            "defice": self.defice,
            "ordens_afetadas": [o.to_dict() for o in self.ordens_afetadas],
            "sugestao": self.sugestao,
            "sugestao_detalhe": self.sugestao_detalhe,
            "lead_time_days": self.lead_time_days,
            "lead_time_source": self.lead_time_source,
            "data_limite_encomenda": (
                self.data_limite_encomenda.isoformat()
                if self.data_limite_encomenda else None
            ),
            "outros_armazens": self.outros_armazens,
            "consumo_mediano_por_barco": self.consumo_mediano_por_barco,
            "pedidos_internos": self.pedidos_internos,
            "producao_interna_aberta": self.producao_interna_aberta,
        }


class ShortageforecastResult:
    """Resultado completo da previsão de ruturas."""

    def __init__(
        self,
        *,
        materiais_em_risco: List[MaterialEmRisco],
        excluidos_sem_stock_rastreado: int,
        horizonte_dias: int,
        commit_sha: Optional[str],
        commit_ops: int,
        gerado_em: datetime,
        fontes: List[str],
    ) -> None:
        self.materiais_em_risco = materiais_em_risco
        self.excluidos_sem_stock_rastreado = excluidos_sem_stock_rastreado
        self.horizonte_dias = horizonte_dias
        self.commit_sha = commit_sha
        self.commit_ops = commit_ops
        self.gerado_em = gerado_em
        self.fontes = fontes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "materiais_em_risco": [m.to_dict() for m in self.materiais_em_risco],
            "total_em_risco": len(self.materiais_em_risco),
            "excluidos_sem_stock_rastreado": self.excluidos_sem_stock_rastreado,
            "horizonte_dias": self.horizonte_dias,
            "commit_sha": self.commit_sha,
            "commit_ops": self.commit_ops,
            "gerado_em": self.gerado_em.isoformat(),
            "fontes": self.fontes,
        }


# ---------------------------------------------------------------------------
# Algoritmo de projeção (puro — testável sem BD)
# ---------------------------------------------------------------------------

def _project_stock(
    *,
    stock_atual: float,
    reservas: float,
    entradas: List[Tuple[date, float, bool]],
    consumos: List[Tuple[date, float]],
    min_stock: float,
    horizonte_dias: int,
    hoje: date,
) -> Tuple[Optional[date], float]:
    """Projeta o saldo ao longo do horizonte completo.

    Args:
        stock_atual: Stock actual (pode ser negativo — dado real ERP).
        reservas: Total de reservas abertas (TPMOV=4 não satisfeitas) — deduz já.
        entradas: Lista de (eta_date, qty, eta_estimada) — POs OPEN.
        consumos: Lista de (date, qty) — consumo previsto do plano.
        min_stock: Stock mínimo (abaixo deste = rutura).
        horizonte_dias: Número de dias a projectar.
        hoje: Data de referência.

    Returns:
        (primeiro dia com saldo < min_stock ou None, saldo mínimo projetado
        no horizonte). O saldo mínimo permite calcular o défice REAL contra o
        min_stock (Q.173.AO — o défice antigo media contra zero e dava 0.0
        quando o saldo era positivo mas abaixo do mínimo).
    """
    # saldo inicial = stock - reservas abertas (picking pendente)
    saldo = stock_atual - reservas
    saldo_minimo = saldo

    # índice: data → qty_entrada
    entradas_por_dia: Dict[date, float] = defaultdict(float)
    for eta_d, qty, _ in entradas:
        if eta_d >= hoje:
            entradas_por_dia[eta_d] += qty

    # índice: data → qty_consumo
    consumos_por_dia: Dict[date, float] = defaultdict(float)
    for cons_d, qty in consumos:
        if cons_d >= hoje:
            consumos_por_dia[cons_d] += qty

    # verificar já hoje (stock pode já ser rutura pré-plano)
    data_rutura: Optional[date] = None
    if saldo < min_stock:
        data_rutura = hoje

    # percorre o horizonte INTEIRO (não para na 1ª rutura) para conhecer o
    # ponto mais fundo — é esse que dita quanto é preciso repor.
    for delta in range(1, horizonte_dias + 1):
        dia = hoje + timedelta(days=delta)
        saldo += entradas_por_dia.get(dia, 0.0)
        saldo -= consumos_por_dia.get(dia, 0.0)
        if saldo < saldo_minimo:
            saldo_minimo = saldo
        if data_rutura is None and saldo < min_stock:
            data_rutura = dia

    return data_rutura, saldo_minimo


def _calcular_sugestao(
    *,
    data_rutura: Optional[date],
    hoje: date,
    lead_time_days: int,
    defice: float,
    producao_interna_aberta: float = 0.0,
) -> Tuple[str, str, Optional[date]]:
    """Devolve (sugestao, detalhe, data_limite_encomenda).

    Regras:
    1. "producao_interna" — Q.174.F0.3: a Fábrica JÁ tem pedido interno aberto
       (TPMOV=12 para e_id=19747) que cobre o défice — mandar comprar o que
       já está pedido internamente seria desperdício; a ação é confirmar/
       acelerar a produção interna.
    2. "compra" — se lead time permite chegar antes da rutura.
    3. "replaneamento" — a rutura é causada pelo plano e não há compra a tempo.

    Q.173.AO: "transferência" foi REMOVIDA — o saldo projeta o stock agregado
    de todos os armazéns, por isso mover stock entre armazéns nunca altera o
    total (a sugestão antiga contava o mesmo stock duas vezes). A repartição
    por armazém continua no payload (`outros_armazens`) como contexto.
    """
    if data_rutura is None:
        return ("ok", "Sem rutura prevista no horizonte.", None)

    # Data limite para encomenda
    data_limite = data_rutura - timedelta(days=lead_time_days)
    dias_restantes = (data_limite - hoje).days

    if producao_interna_aberta >= defice > 0:
        detail = (
            f"A Fábrica já tem pedido interno aberto de "
            f"{producao_interna_aberta:.1f} unidades (cobre o défice de "
            f"{defice:.1f}). Confirmar/acelerar a produção interna antes de "
            f"{data_rutura.isoformat()} — não comprar em duplicado."
        )
        return ("producao_interna", detail, data_limite)

    if dias_restantes >= 0:
        detail = (
            f"Encomendar {defice:.1f} unidades até {data_limite.isoformat()} "
            f"({dias_restantes}d) — lead time {lead_time_days}d."
        )
        if producao_interna_aberta > 0:
            detail += (
                f" Produção interna já pedida: {producao_interna_aberta:.1f} "
                "un (cobre parte do défice)."
            )
        return ("compra", detail, data_limite)

    # Sem tempo para compra
    detail = (
        f"Rutura em {data_rutura.isoformat()} mas lead time {lead_time_days}d "
        f"já não chega (data-limite encomenda era {data_limite.isoformat()}). "
        "Rever sequência do plano."
    )
    if producao_interna_aberta > 0:
        detail += (
            f" Produção interna já pedida: {producao_interna_aberta:.1f} un — "
            "acelerá-la pode evitar o replaneamento."
        )
    return ("replaneamento", detail, data_limite)


# ---------------------------------------------------------------------------
# Serviço com acesso à BD
# ---------------------------------------------------------------------------

class ShortageForecastService:
    """Motor de previsão de ruturas (Q.173.Z)."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    # ------------------------------------------------------------------
    # Ponto de entrada público
    # ------------------------------------------------------------------

    async def forecast(self, horizonte_dias: int = 60) -> ShortageforecastResult:
        """Corre o forecast completo e devolve os materiais em risco."""
        hoje = datetime.now(timezone.utc).date()
        fontes: List[str] = []

        # 1. Carregar o último commit saudável
        commit_sha, commit_ops, ops = await self._load_plan_ops()
        fontes.append("plan_schedule_commits")

        if not ops:
            logger.warning("shortage_forecast: sem ops no commit atual — horizon vazio")
            return ShortageforecastResult(
                materiais_em_risco=[],
                excluidos_sem_stock_rastreado=0,
                horizonte_dias=horizonte_dias,
                commit_sha=commit_sha,
                commit_ops=commit_ops,
                gerado_em=datetime.now(timezone.utc),
                fontes=fontes,
            )

        # 2. Enriquecer ops com model_id (OF_P_ID) a partir de order_id
        #    As ops do commit têm order_id (ID da OF) mas não product_id.
        order_model_map = await self._load_order_model_map(ops)
        fontes.append("factory_raw.ordemfabrico")

        # 3. BOM estrutural (Q.174.F0.2): COMP_P_ID = PAI (o barco/modelo),
        #    COMP_P_P_ID = FILHO (componente) — provado live 2026-06-12 nos 5
        #    modelos com mais WIP (ex. Ocean Ski 510 Pl: 20 filhos como
        #    COMP_P_ID, 0 como COMP_P_P_ID). O comentário anterior ("a BOM é
        #    invertida") estava ERRADO e o filtro usava a coluna trocada →
        #    bom_map ficava SEMPRE vazio para barcos reais e o forecast caía
        #    em silêncio no consumo histórico. Fallback mantém-se para
        #    modelos sem BOM.
        bom_map = await self._load_bom(ops, order_model_map)
        fontes.append("factory_raw.produto_componente")

        # 4. Consumo previsto por material → lista (date, qty)
        # Fonte A (preferida): BOM estrutural × plano
        # Fonte B (fallback): mediana histórica por (modelo, material) × plano
        if bom_map:
            consumos_por_material = _compute_consumos(
                ops, bom_map, order_model_map, hoje, horizonte_dias
            )
        else:
            # BOM estrutural vazia → usar consumo histórico real como proxy
            model_ids_no_plano = set(order_model_map.values())
            consumos_por_material = await self._compute_consumos_historicos(
                ops, order_model_map, model_ids_no_plano, hoje, horizonte_dias
            )
            fontes.append("factory_raw.movimento(TPMOV=11,consumo_historico)")

        # Materiais relevantes = os que têm consumo previsto no horizonte
        materiais_relevantes: Set[str] = set(consumos_por_material.keys())

        if not materiais_relevantes:
            return ShortageforecastResult(
                materiais_em_risco=[],
                excluidos_sem_stock_rastreado=0,
                horizonte_dias=horizonte_dias,
                commit_sha=commit_sha,
                commit_ops=commit_ops,
                gerado_em=datetime.now(timezone.utc),
                fontes=fontes,
            )

        # 5. Stock actual por material (agrega por warehouse)
        stock_map, warehouse_map = await self._load_stock(materiais_relevantes)
        fontes.append("supply.warehouse_stock")

        # Excluir materiais sem stock rastreado (pseudo-componentes)
        excluidos = 0
        materiais_com_stock: Set[str] = set()
        for pc in materiais_relevantes:
            if pc in stock_map:
                materiais_com_stock.add(pc)
            else:
                excluidos += 1

        # 6. POs OPEN → entradas previstas
        entradas_map = await self._load_pos(materiais_com_stock, hoje)
        fontes.append("supply.purchase_orders")

        # 7. Reservas abertas por material (canónico: só OFs de barco de cliente)
        reservas_map = await self._load_reservas(materiais_com_stock)
        fontes.append("factory_raw.movimento(TPMOV=4)")

        # 7b. Q.174.F0.3 — pedidos internos abertos (TPMOV=12, canónico
        # produto_Stock_Necessidades): procura (≠19747, sem OF) entra no
        # saldo como as reservas; produção interna já pedida (=19747)
        # alimenta a sugestão (não mandar comprar o que a Fábrica já vai fazer).
        pedintern_map, prodintern_map = await self._load_pedidos_internos(
            materiais_com_stock
        )
        fontes.append("factory_raw.movimento(TPMOV=12)")

        # 8. Mínimos e lead times
        master_map = await self._load_masters(materiais_com_stock)
        fontes.append("supply.supply_material_master")

        # 9. Nomes dos materiais
        nomes_map = await self._load_nomes(materiais_com_stock)
        fontes.append("factory_raw.produto")

        # 10. Consumo mediano por modelo (Q.173.AA — campo de contexto)
        medianas_map = await self._load_medianas(materiais_com_stock)

        # 11. Projeção por material
        materiais_em_risco: List[MaterialEmRisco] = []

        for pc in sorted(materiais_com_stock):
            stock_total = stock_map.get(pc, 0.0)
            stock_negativo = stock_total < 0
            reservas = reservas_map.get(pc, 0.0)
            pedidos_internos = pedintern_map.get(pc, 0.0)
            producao_interna = prodintern_map.get(pc, 0.0)
            entradas = entradas_map.get(pc, [])
            consumos = consumos_por_material.get(pc, [])
            master = master_map.get(pc, {})
            min_stock = master.get("min_stock_qty", 0.0)
            min_stock_source = master.get("min_stock_source", "default")
            lead_time = master.get("lead_time_days", 7)
            lead_time_source = master.get("lead_time_source", "default")
            nome = nomes_map.get(pc, pc)

            # Q.174.F0.3 — a procura comprometida = reservas de barcos +
            # pedidos internos abertos (fórmula canónica necTotal).
            data_rutura, saldo_minimo = _project_stock(
                stock_atual=stock_total,
                reservas=reservas + pedidos_internos,
                entradas=entradas,
                consumos=consumos,
                min_stock=min_stock,
                horizonte_dias=horizonte_dias,
                hoje=hoje,
            )

            if data_rutura is None:
                continue  # sem rutura no horizonte

            # Q.173.AO — défice = quanto falta repor para voltar ao mínimo no
            # ponto mais fundo do horizonte (o cálculo antigo media contra zero
            # e devolvia 0.0 sempre que o saldo era positivo mas < min_stock).
            defice = max(0.0, min_stock - saldo_minimo)

            # Repartição por armazém — contexto informativo (não é sugestão)
            outros_armazens = warehouse_map.get(pc, [])

            sugestao, detalhe, data_limite = _calcular_sugestao(
                data_rutura=data_rutura,
                hoje=hoje,
                lead_time_days=lead_time,
                defice=defice,
                producao_interna_aberta=producao_interna,
            )

            if sugestao == "ok":
                continue

            # Ordens afetadas (ops que consomem este material até data_rutura)
            if bom_map:
                ordens_afetadas = _ordens_afetadas_para(
                    pc, ops, bom_map, data_rutura, hoje, order_model_map
                )
            else:
                # Sem BOM estrutural: ordens afetadas = ordens com consumo histórico
                # do material e ops dentro do horizonte até data_rutura
                ordens_afetadas = _ordens_afetadas_historico(
                    pc, ops, order_model_map, consumos_por_material, data_rutura, hoje
                )

            mediana = medianas_map.get(pc)

            materiais_em_risco.append(MaterialEmRisco(
                product_code=pc,
                product_name=nome,
                stock_atual=stock_total,
                stock_negativo_erp=stock_negativo,
                min_stock=min_stock,
                min_stock_source=min_stock_source,
                data_rutura_prevista=data_rutura,
                defice=round(defice, 4),
                ordens_afetadas=ordens_afetadas,
                sugestao=sugestao,
                sugestao_detalhe=detalhe,
                lead_time_days=lead_time,
                lead_time_source=lead_time_source,
                data_limite_encomenda=data_limite,
                outros_armazens=outros_armazens,
                consumo_mediano_por_barco=mediana,
                pedidos_internos=pedidos_internos,
                producao_interna_aberta=producao_interna,
            ))

        # Ordenar por data de rutura ascendente
        materiais_em_risco.sort(
            key=lambda m: m.data_rutura_prevista or date.max
        )

        return ShortageforecastResult(
            materiais_em_risco=materiais_em_risco,
            excluidos_sem_stock_rastreado=excluidos,
            horizonte_dias=horizonte_dias,
            commit_sha=commit_sha,
            commit_ops=commit_ops,
            gerado_em=datetime.now(timezone.utc),
            fontes=fontes,
        )

    # ------------------------------------------------------------------
    # Loaders de BD (SQL directo — tabelas ERP case-sensitive)
    # ------------------------------------------------------------------

    async def _load_plan_ops(
        self,
    ) -> Tuple[Optional[str], int, List[Dict[str, Any]]]:
        """Carrega ops do último commit saudável."""
        from src.plan.cpo.commits import CommitsService

        svc = CommitsService(self._session, self._tenant_id)
        commits = await svc.list_commits(limit=1, healthy_only=True)
        if not commits:
            return None, 0, []
        commit = commits[0]
        ops = list(commit.operations or [])
        return commit.commit_sha256, commit.operations_count, ops

    async def _compute_consumos_historicos(
        self,
        ops: List[Dict[str, Any]],
        order_model_map: Dict[str, int],
        model_ids: Set[int],
        hoje: date,
        horizonte_dias: int,
    ) -> Dict[str, List[Tuple[date, float]]]:
        """Consumo previsto usando medianas históricas por (modelo, material).

        Usado quando a BOM estrutural (produto_componente) está vazia para os
        modelos do plano — situação normal na NELO onde a BOM é invertida.

        Para cada op do plano:
          consumo_material_neste_dia += mediana_historica(modelo, material) × 1 op

        Etiquetado: fonte='consumo_historico_mediano' — não é BOM estrutural.
        """
        if not model_ids:
            return {}

        # Carrega medianas por (modelo, material) de uma vez
        int_model_ids = [mid for mid in model_ids if isinstance(mid, int)]
        if not int_model_ids:
            return {}

        q = text("""
            WITH consumo_por_of AS (
                SELECT
                    of."OF_P_ID"         AS model_id,
                    m."MOV_P_ID"         AS mat_id,
                    m."MOV_OF_ID"        AS of_id,
                    SUM(m."MOV_QUANTIDADE") AS qty
                FROM factory_raw.movimento m
                JOIN factory_raw.ordemfabrico of ON of."OF_ID" = m."MOV_OF_ID"
                WHERE m."MOV_TPMOV_ID" = 11
                  AND m."MOV_OF_ID" IS NOT NULL
                  AND of."OF_P_ID" = ANY(:model_ids)
                GROUP BY of."OF_P_ID", m."MOV_P_ID", m."MOV_OF_ID"
            )
            SELECT
                model_id,
                mat_id::text                                                AS product_code,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY qty)            AS mediana_qty
            FROM consumo_por_of
            GROUP BY model_id, mat_id
            HAVING PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY qty) > 0
        """)
        result = await self._session.execute(q, {"model_ids": int_model_ids})
        rows = result.fetchall()

        # medianas[(model_id, product_code)] = mediana_qty
        medianas: Dict[Tuple[int, str], float] = {}
        for row in rows:
            medianas[(int(row[0]), str(row[1]))] = float(row[2])

        if not medianas:
            return {}

        # Calcular consumos por dia: para cada op do plano
        horizonte_fim = hoje + timedelta(days=horizonte_dias)
        consumos: Dict[str, List[Tuple[date, float]]] = defaultdict(list)

        # Agregar ops por (model_id, day) para performance
        agg: Dict[Tuple[int, date], float] = defaultdict(float)
        for op in ops:
            oid = str(op.get("order_id") or "")
            mid = order_model_map.get(oid)
            start_raw = op.get("start_time")
            if mid is None or start_raw is None:
                continue
            try:
                if isinstance(start_raw, datetime):
                    op_date = start_raw.date()
                else:
                    op_date = datetime.fromisoformat(str(start_raw)).date()
            except (ValueError, AttributeError):
                continue
            if op_date < hoje or op_date > horizonte_fim:
                continue
            agg[(mid, op_date)] += 1.0

        # Índice por model_id para performance
        medianas_por_modelo: Dict[int, List[Tuple[str, float]]] = defaultdict(list)
        for (mid, pc), mediana in medianas.items():
            medianas_por_modelo[mid].append((pc, mediana))

        # Cruzar com medianas
        for (mid, op_date), n_ops in agg.items():
            for pc, mediana in medianas_por_modelo.get(mid, []):
                consumos[pc].append((op_date, mediana * n_ops))

        return dict(consumos)

    async def _load_order_model_map(
        self,
        ops: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """Mapeamento order_id → OF_P_ID (modelo) via factory_raw.ordemfabrico.

        As ops do commit têm order_id (= OF_ID legacy) mas não têm product_id.
        Este lookup preenche o gap.
        """
        order_ids_raw: Set[str] = set()
        for op in ops:
            oid = op.get("order_id")
            if oid is not None:
                order_ids_raw.add(str(oid))

        if not order_ids_raw:
            return {}

        # Converter para int (OF_ID é int no ERP)
        try:
            int_ids = [int(oid) for oid in order_ids_raw if str(oid).isdigit()]
        except ValueError:
            return {}

        if not int_ids:
            return {}

        q = text("""
            SELECT "OF_ID"::text, "OF_P_ID"
            FROM factory_raw.ordemfabrico
            WHERE "OF_ID" = ANY(:ids)
              AND "OF_P_ID" IS NOT NULL
        """)
        result = await self._session.execute(q, {"ids": int_ids})
        return {str(row[0]): int(row[1]) for row in result.fetchall()}

    async def _load_bom(
        self,
        ops: List[Dict[str, Any]],
        order_model_map: Dict[str, int],
    ) -> Dict[Tuple[int, Optional[int]], List[Tuple[str, float, bool]]]:
        """BOM por (model_id, phase_id) → [(comp_code, qty, tem_fase)].

        Carrega só os modelos × fases presentes no plano (WHERE IN).
        Filtra COMP_ELIMINADO IS NULL.
        """
        # Conjuntos de (model_id, phase_id) únicos no plano
        model_phase_pairs: Set[Tuple[int, Optional[int]]] = set()
        for op in ops:
            oid = str(op.get("order_id") or "")
            mid = order_model_map.get(oid)
            pid = op.get("phase_id")
            if mid is not None:
                try:
                    model_phase_pairs.add((mid, int(pid) if pid is not None else None))
                except (ValueError, TypeError):
                    pass

        if not model_phase_pairs:
            return {}

        model_ids = list({mp[0] for mp in model_phase_pairs})

        # Carrega BOM para todos os modelos do plano de uma vez.
        # Q.174.F0.2 — direção CERTA: COMP_P_ID = pai (modelo do plano),
        # COMP_P_P_ID = filho (componente consumido). As linhas do configurador
        # (COMP_P_ID NULL, ~25k, ligadas a atributo/linha) ficam fora por
        # construção (o filtro por pai nunca casa NULL).
        q = text("""
            SELECT
                "COMP_P_ID"::text    AS model_id,
                "COMP_P_P_ID"::text  AS comp_id,
                "COMP_QUANTIDADE"    AS qty,
                "COMP_FP_ID"         AS fase_id
            FROM factory_raw.produto_componente
            WHERE "COMP_ELIMINADO" IS NULL
              AND "COMP_P_ID" = ANY(:model_ids)
        """)
        result = await self._session.execute(q, {"model_ids": model_ids})
        rows = result.fetchall()

        # Agrupa: (model_id, phase_id_or_None) → [(comp, qty, tem_fase)]
        bom: Dict[Tuple[int, Optional[int]], List[Tuple[str, float, bool]]] = defaultdict(list)
        # Também: model_id → [(comp, qty)] para componentes sem fase
        bom_sem_fase: Dict[int, List[Tuple[str, float]]] = defaultdict(list)

        for row in rows:
            model_id = int(row[0])
            comp_code = str(row[1])
            qty = float(row[2]) if row[2] is not None else 0.0
            fase_id = int(row[3]) if row[3] is not None else None

            if fase_id is not None:
                bom[(model_id, fase_id)].append((comp_code, qty, True))
            else:
                bom_sem_fase[model_id].append((comp_code, qty))

        # Componentes sem fase → atribuir à PRIMEIRA op do modelo
        # Determinamos "primeira op por modelo" a partir das ops do plano
        primeira_fase_por_modelo: Dict[int, Optional[int]] = {}
        # Ordenar por start_time para encontrar a primeira
        ops_sorted = sorted(ops, key=lambda o: o.get("start_time") or "")
        for op in ops_sorted:
            oid = str(op.get("order_id") or "")
            mid = order_model_map.get(oid)
            if mid is None:
                continue
            if mid not in primeira_fase_por_modelo:
                pid_raw = op.get("phase_id")
                try:
                    primeira_fase_por_modelo[mid] = int(pid_raw) if pid_raw is not None else None
                except (ValueError, TypeError):
                    primeira_fase_por_modelo[mid] = None

        for model_id, comps in bom_sem_fase.items():
            key = (model_id, primeira_fase_por_modelo.get(model_id))
            for comp_code, qty in comps:
                bom[key].append((comp_code, qty, False))  # tem_fase=False

        return dict(bom)

    async def _load_stock(
        self,
        product_codes: Set[str],
    ) -> Tuple[Dict[str, float], Dict[str, List[Dict[str, Any]]]]:
        """Stock total e repartição por armazém.

        Devolve:
        - stock_map: product_code → total (pode ser negativo — dado real ERP)
        - warehouse_map: product_code → [{"warehouse_name": ..., "stock": ...}]
        """
        if not product_codes:
            return {}, {}

        q = text("""
            SELECT product_code, warehouse_name, SUM(stock) AS stock
            FROM supply.warehouse_stock
            WHERE tenant_id = :tid
              AND product_code = ANY(:codes)
            GROUP BY product_code, warehouse_name
        """)
        result = await self._session.execute(
            q,
            {"tid": str(self._tenant_id), "codes": list(product_codes)},
        )
        rows = result.fetchall()

        stock_total: Dict[str, float] = defaultdict(float)
        warehouse_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for row in rows:
            pc, wh_name, stk = str(row[0]), str(row[1]), float(row[2] or 0)
            stock_total[pc] += stk
            warehouse_map[pc].append({"warehouse_name": wh_name, "stock": stk})

        return dict(stock_total), dict(warehouse_map)

    async def _load_pos(
        self,
        product_codes: Set[str],
        hoje: date,
    ) -> Dict[str, List[Tuple[date, float, bool]]]:
        """POs OPEN → entradas previstas por material.

        ETA NULL: ETA estimada = ordered_at + lead_time_days do material
        (flag eta_estimada=True). Sem lead time real → ainda estima, com flag.
        """
        if not product_codes:
            return {}

        # Carrega masters para estimar ETA quando NULL
        q_master = text("""
            SELECT sku_id, lead_time_days, lead_time_source
            FROM supply.supply_material_master
            WHERE tenant_id = :tid
              AND sku_id = ANY(:codes)
        """)
        r = await self._session.execute(
            q_master,
            {"tid": str(self._tenant_id), "codes": list(product_codes)},
        )
        master_lt: Dict[str, Tuple[int, str]] = {}
        for row in r.fetchall():
            master_lt[str(row[0])] = (int(row[1]), str(row[2]))

        q = text("""
            SELECT product_code, qty_ordered - qty_received AS qty_outstanding,
                   ordered_at, eta
            FROM supply.purchase_orders
            WHERE tenant_id = :tid
              AND status = 'OPEN'
              AND product_code = ANY(:codes)
              AND (qty_ordered - qty_received) > 0
        """)
        result = await self._session.execute(
            q,
            {"tid": str(self._tenant_id), "codes": list(product_codes)},
        )
        rows = result.fetchall()

        entradas: Dict[str, List[Tuple[date, float, bool]]] = defaultdict(list)
        for row in rows:
            pc = str(row[0])
            qty = float(row[1] or 0)
            ordered_at = row[2]
            eta = row[3]

            if eta is not None:
                eta_date = eta if isinstance(eta, date) else eta.date()
                eta_estimada = False
            elif ordered_at is not None:
                lt_days, _ = master_lt.get(pc, (7, "default"))
                eta_date = (
                    ordered_at if isinstance(ordered_at, date) else ordered_at.date()
                ) + timedelta(days=lt_days)
                eta_estimada = True
            else:
                # Sem ordered_at nem eta → assume hoje + lead_time
                lt_days, _ = master_lt.get(pc, (7, "default"))
                eta_date = hoje + timedelta(days=lt_days)
                eta_estimada = True

            entradas[pc].append((eta_date, qty, eta_estimada))

        return dict(entradas)

    async def _load_reservas(
        self,
        product_codes: Set[str],
    ) -> Dict[str, float]:
        """Reservas abertas (TPMOV=4 MOV_SATISFEITO=false) por product_code.

        Q.173.AO: exclui reservas cuja OF já fechou (OF_DATAFIM preenchida) —
        lixo histórico do ERP que nunca foi satisfeito nem cancelado (10.268
        movimentos globais). Reservas sem OF ou cuja OF não está no espelho
        contam (conservador).
        """
        if not product_codes:
            return {}

        # product_codes são strings (códigos TEXT em warehouse_stock)
        # MOV_P_ID é int no ERP → converter
        try:
            int_codes = [int(pc) for pc in product_codes if pc.isdigit()]
        except ValueError:
            int_codes = []

        if not int_codes:
            return {}

        # Q.174.F0.3 — filtros CANÓNICOS de produto_Stock_Necessidades (corpo
        # lido live 2026-06-12): as necessidades de OF contam SÓ reservas de
        # OFs de BARCO de cliente (OF_ID < 10M e OF_E_ID_ENC <> 19747). As
        # reservas de OFs de peças (>= 10M) ficam fora porque a procura de
        # peças entra pelo canal TPMOV=12 (pedidos internos) — contar ambas
        # duplicaria; as do Cliente Fábrica (19747) não são procura de cliente.
        q = text("""
            SELECT m."MOV_P_ID"::text, SUM(m."MOV_QUANTIDADE") AS reserva
            FROM factory_raw.movimento m
            LEFT JOIN factory_raw.ordemfabrico o ON o."OF_ID" = m."MOV_OF_ID"
            WHERE m."MOV_TPMOV_ID" = 4
              AND m."MOV_SATISFEITO" = false
              AND m."MOV_P_ID" = ANY(:ids)
              AND (o."OF_ID" IS NULL
                   OR (o."OF_DATAFIM" IS NULL
                       AND o."OF_ID" < 10000000
                       AND o."OF_E_ID_ENC" <> 19747))
            GROUP BY m."MOV_P_ID"
        """)
        result = await self._session.execute(q, {"ids": int_codes})
        reservas: Dict[str, float] = {}
        for row in result.fetchall():
            reservas[str(row[0])] = float(row[1] or 0)
        return reservas

    async def _load_pedidos_internos(
        self,
        product_codes: Set[str],
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Q.174.F0.3 — pedidos internos abertos (TPMOV=12, MOV_SATISFEITO=false)
        nos DOIS canais canónicos de ``produto_Stock_Necessidades``:

        * ``pedidos_internos`` (MOV_E_ID <> 19747, sem OF) — PROCURA: requisições
          internas em aberto que o ERP soma às necessidades. Ignorá-las
          subestimava o défice (caso live Inserts M8: ERP défice 249, nós
          víamos saldo +495).
        * ``producao_interna`` (MOV_E_ID = 19747 = a própria Fábrica) — sinal de
          OFERTA: a fábrica já tem pedido interno para PRODUZIR o material.
          Não entra no saldo (sem ETA fiável); alimenta a sugestão
          "produção interna" em vez de mandar comprar o que já está pedido.
        """
        if not product_codes:
            return {}, {}
        try:
            int_codes = [int(pc) for pc in product_codes if pc.isdigit()]
        except ValueError:
            int_codes = []
        if not int_codes:
            return {}, {}

        q = text("""
            SELECT m."MOV_P_ID"::text,
                   SUM(m."MOV_QUANTIDADE") FILTER (
                     WHERE m."MOV_E_ID" <> 19747 AND m."MOV_OF_ID" IS NULL
                   ) AS pedidos_internos,
                   SUM(m."MOV_QUANTIDADE") FILTER (
                     WHERE m."MOV_E_ID" = 19747
                   ) AS producao_interna
            FROM factory_raw.movimento m
            WHERE m."MOV_TPMOV_ID" = 12
              AND m."MOV_SATISFEITO" = false
              AND m."MOV_P_ID" = ANY(:ids)
            GROUP BY m."MOV_P_ID"
        """)
        result = await self._session.execute(q, {"ids": int_codes})
        pedidos: Dict[str, float] = {}
        producao: Dict[str, float] = {}
        for row in result.fetchall():
            code = str(row[0])
            if row[1]:
                pedidos[code] = float(row[1])
            if row[2]:
                producao[code] = float(row[2])
        return pedidos, producao

    async def _load_masters(
        self,
        product_codes: Set[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Carrega mínimos e lead times de supply.supply_material_master."""
        if not product_codes:
            return {}

        q = text("""
            SELECT sku_id, min_stock_qty, min_stock_source,
                   lead_time_days, lead_time_source
            FROM supply.supply_material_master
            WHERE tenant_id = :tid
              AND sku_id = ANY(:codes)
        """)
        result = await self._session.execute(
            q,
            {"tid": str(self._tenant_id), "codes": list(product_codes)},
        )
        masters: Dict[str, Dict[str, Any]] = {}
        for row in result.fetchall():
            masters[str(row[0])] = {
                "min_stock_qty": float(row[1] or 0),
                "min_stock_source": str(row[2] or "default"),
                "lead_time_days": int(row[3] or 7),
                "lead_time_source": str(row[4] or "default"),
            }
        return masters

    async def _load_nomes(
        self,
        product_codes: Set[str],
    ) -> Dict[str, str]:
        """Nomes dos materiais de factory_raw.produto."""
        if not product_codes:
            return {}

        try:
            int_codes = [int(pc) for pc in product_codes if pc.isdigit()]
        except ValueError:
            int_codes = []

        if not int_codes:
            return {}

        q = text("""
            SELECT "P_ID"::text, "P_NOME"
            FROM factory_raw.produto
            WHERE "P_ID" = ANY(:ids)
        """)
        result = await self._session.execute(q, {"ids": int_codes})
        return {str(row[0]): str(row[1] or "") for row in result.fetchall()}

    async def _load_medianas(
        self,
        product_codes: Set[str],
    ) -> Dict[str, Optional[float]]:
        """Consumo mediano por barco (contexto para validação humana).

        Versão leve: percentile_cont(0.5) de MOV_QUANTIDADE por produto
        nos consumos TPMOV=11 com OF.
        """
        if not product_codes:
            return {}

        try:
            int_codes = [int(pc) for pc in product_codes if pc.isdigit()]
        except ValueError:
            int_codes = []

        if not int_codes:
            return {}

        q = text("""
            SELECT
                m."MOV_P_ID"::text AS product_code,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY m."MOV_QUANTIDADE") AS mediana
            FROM factory_raw.movimento m
            WHERE m."MOV_TPMOV_ID" = 11
              AND m."MOV_OF_ID" IS NOT NULL
              AND m."MOV_P_ID" = ANY(:ids)
            GROUP BY m."MOV_P_ID"
        """)
        result = await self._session.execute(q, {"ids": int_codes})
        return {
            str(row[0]): float(row[1]) if row[1] is not None else None
            for row in result.fetchall()
        }


# ---------------------------------------------------------------------------
# Funções de cálculo puras (testáveis sem BD)
# ---------------------------------------------------------------------------

def _compute_consumos(
    ops: List[Dict[str, Any]],
    bom_map: Dict[Tuple[int, Optional[int]], List[Tuple[str, float, bool]]],
    order_model_map: Dict[str, int],
    hoje: date,
    horizonte_dias: int,
) -> Dict[str, List[Tuple[date, float]]]:
    """Consumo previsto por material a partir das ops e BOM.

    PERFORMANCE: agrega ops por (model_id, phase_id, dia) ANTES de cruzar
    com a BOM — evita loop op×componente (8k ops × N comp).

    Retorna: material_code → [(date, qty), ...]
    """
    horizonte_fim = hoje + timedelta(days=horizonte_dias)

    # Passo 1: agregar qty de ops por (model_id, phase_id, day)
    agg: Dict[Tuple[int, Optional[int], date], float] = defaultdict(float)
    for op in ops:
        oid = str(op.get("order_id") or "")
        mid = order_model_map.get(oid)
        pid_raw = op.get("phase_id")
        start_raw = op.get("start_time")
        if mid is None or start_raw is None:
            continue
        try:
            pid = int(pid_raw) if pid_raw is not None else None
        except (ValueError, TypeError):
            pid = None
        try:
            if isinstance(start_raw, datetime):
                op_date = start_raw.date()
            else:
                op_date = datetime.fromisoformat(str(start_raw)).date()
        except (ValueError, AttributeError):
            continue
        if op_date < hoje or op_date > horizonte_fim:
            continue
        # qty da op = 1 unidade de produto (BOM em unidades por produto)
        agg[(mid, pid, op_date)] += 1.0

    # Passo 2: para cada (model, phase) com consumo, cruzar com BOM
    consumos: Dict[str, List[Tuple[date, float]]] = defaultdict(list)
    for (mid, pid, op_date), n_ops in agg.items():
        key = (mid, pid)
        componentes = bom_map.get(key, [])
        for comp_code, qty_per, _ in componentes:
            consumos[comp_code].append((op_date, qty_per * n_ops))

    return dict(consumos)


def _ordens_afetadas_para(
    product_code: str,
    ops: List[Dict[str, Any]],
    bom_map: Dict[Tuple[int, Optional[int]], List[Tuple[str, float, bool]]],
    data_rutura: date,
    hoje: date,
    order_model_map: Optional[Dict[str, int]] = None,
) -> List[OrdemAfetada]:
    """Devolve as top N ordens cujas ops consomem este material até data_rutura."""
    if order_model_map is None:
        order_model_map = {}

    ordens_vistas: Dict[str, OrdemAfetada] = {}
    for op in ops:
        oid = str(op.get("order_id") or "")
        mid = order_model_map.get(oid) if order_model_map else None
        # fallback: product_id se existir (testes sintéticos)
        if mid is None:
            mid_raw = op.get("product_id")
            if mid_raw is not None:
                try:
                    mid = int(mid_raw)
                except (ValueError, TypeError):
                    mid = None
        pid_raw = op.get("phase_id")
        start_raw = op.get("start_time")
        if mid is None or start_raw is None:
            continue
        try:
            pid = int(pid_raw) if pid_raw is not None else None
        except (ValueError, TypeError):
            pid = None
        try:
            if isinstance(start_raw, datetime):
                op_date = start_raw.date()
                op_dt = start_raw
            else:
                op_dt = datetime.fromisoformat(str(start_raw))
                op_date = op_dt.date()
        except (ValueError, AttributeError):
            continue
        if op_date < hoje or op_date > data_rutura:
            continue
        componentes = bom_map.get((mid, pid), [])
        if not any(c[0] == product_code for c in componentes):
            continue
        order_id = oid if oid else f"model_{mid}"
        if order_id not in ordens_vistas:
            ordens_vistas[order_id] = OrdemAfetada(
                order_id=order_id,
                modelo=str(mid),
                start_time=op_dt,
            )

    # Top N por start_time
    sorted_ordens = sorted(ordens_vistas.values(), key=lambda o: o.start_time)
    return sorted_ordens[:_TOP_ORDERS]


def _ordens_afetadas_historico(
    product_code: str,
    ops: List[Dict[str, Any]],
    order_model_map: Dict[str, int],
    consumos_por_material: Dict[str, List[Tuple[date, float]]],
    data_rutura: date,
    hoje: date,
) -> List[OrdemAfetada]:
    """Ordens afetadas quando se usa consumo histórico (sem BOM estrutural).

    Devolve as primeiras N ordens do plano cujas ops caem antes da data de
    rutura. Sem BOM, não conseguimos saber QUAIS materiais cada op específica
    consome — só que o modelo consome esse material. Identificamos as ordens
    cujo start_time é no horizonte até data_rutura.
    """
    # Materiais com consumo previsto até data_rutura
    datas_consumo = {d for d, _ in consumos_por_material.get(product_code, []) if d <= data_rutura}
    if not datas_consumo:
        return []

    ordens_vistas: Dict[str, OrdemAfetada] = {}
    for op in ops:
        oid = str(op.get("order_id") or "")
        mid = order_model_map.get(oid)
        start_raw = op.get("start_time")
        if mid is None or start_raw is None:
            continue
        try:
            if isinstance(start_raw, datetime):
                op_date = start_raw.date()
                op_dt = start_raw
            else:
                op_dt = datetime.fromisoformat(str(start_raw))
                op_date = op_dt.date()
        except (ValueError, AttributeError):
            continue
        if op_date not in datas_consumo:
            continue
        if oid not in ordens_vistas:
            ordens_vistas[oid] = OrdemAfetada(
                order_id=oid,
                modelo=str(mid),
                start_time=op_dt,
            )

    sorted_ordens = sorted(ordens_vistas.values(), key=lambda o: o.start_time)
    return sorted_ordens[:_TOP_ORDERS]
