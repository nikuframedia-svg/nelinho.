"""
RAW → CURATED Transformer — Contrato 010
========================================

Transform RAW excel_row data into CURATED tables.

Handles:
- Sheet-specific transformations
- Field mapping
- Data type conversion
- Derived field calculation
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class TransformResult:
    """Result of transformation."""

    success: bool = True
    orders: List[Dict] = field(default_factory=list)
    order_phases: List[Dict] = field(default_factory=list)
    phase_capacities: List[Dict] = field(default_factory=list)
    molds: List[Dict] = field(default_factory=list)
    mold_usages: List[Dict] = field(default_factory=list)
    quality_events: List[Dict] = field(default_factory=list)
    skill_matrix: List[Dict] = field(default_factory=list)
    cost_references: List[Dict] = field(default_factory=list)
    # Sprint Q.8 Fase 2/3 — newly materialised dimensions.
    allocations: List[Dict] = field(default_factory=list)
    models: List[Dict] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def total_curated(self) -> int:
        return (
            len(self.orders) +
            len(self.order_phases) +
            len(self.phase_capacities) +
            len(self.molds) +
            len(self.mold_usages) +
            len(self.quality_events) +
            len(self.skill_matrix) +
            len(self.cost_references) +
            len(self.allocations) +
            len(self.models)
        )


class RawToCuratedTransformer:
    """
    Transform RAW data to CURATED tables.
    
    Each sheet maps to specific curated table(s).
    """
    
    # Sheet to transformer method mapping.
    # Sprint Q.8 Fase 2/3 — added two missing sheets:
    #   * FuncionariosFaseOrdemFabrico (423K rows) — worker × order-phase
    #     allocations. Without this handler the workforce-utilisation
    #     reports were running blind on synthetic data.
    #   * Modelos (899 rows) — product/model catalogue dimension. Without
    #     this handler, modelo_id stayed as a denormalised string on
    #     CuratedOrder/Phase with no master row.
    SHEET_HANDLERS = {
        "OrdensFabrico": "_transform_orders",
        "FasesOrdemFabrico": "_transform_order_phases",
        "Funcionarios": "_transform_employees",
        "FuncionariosFasesAptos": "_transform_skill_matrix",
        "FuncionariosFaseOrdemFabrico": "_transform_allocations",
        "Fases": "_transform_phases",
        "Moldes": "_transform_molds",
        "Modelos": "_transform_models",
        "OrdemFabricoErros": "_transform_quality_events",
        "FasesStandardModelos": "_transform_standards",
    }
    
    def transform(
        self,
        raw_rows: List[Dict],
        ingestion_id: UUID,
    ) -> TransformResult:
        """
        Transform RAW rows to CURATED records.
        
        Args:
            raw_rows: List of ExcelRow records (as dicts with payload_json)
            ingestion_id: The ingestion ID
        
        Returns:
            TransformResult with all curated records
        """
        result = TransformResult()
        
        # Group rows by sheet
        # Sprint Q.7 Fase 4 — skip rows without sheet_name; previously a
        # missing key created a `None` bucket silently dropped by the
        # SHEET_HANDLERS lookup downstream, hiding malformed input.
        rows_by_sheet: Dict[str, List[Dict]] = {}
        skipped_no_sheet = 0
        for row in raw_rows:
            sheet = row.get("sheet_name")
            if not sheet:
                skipped_no_sheet += 1
                continue
            if sheet not in rows_by_sheet:
                rows_by_sheet[sheet] = []
            rows_by_sheet[sheet].append(row)
        if skipped_no_sheet:
            logger.warning(
                "transform: skipped %d rows with empty sheet_name",
                skipped_no_sheet,
            )
        
        # Transform each sheet
        for sheet_name, sheet_rows in rows_by_sheet.items():
            handler_name = self.SHEET_HANDLERS.get(sheet_name)
            if handler_name:
                handler = getattr(self, handler_name, None)
                if handler:
                    try:
                        handler(sheet_rows, ingestion_id, result)
                    except Exception as e:
                        result.errors.append(f"Error transforming {sheet_name}: {str(e)}")
                        logger.error(f"Transform error for {sheet_name}: {e}")
        
        return result
    
    def _transform_orders(
        self,
        rows: List[Dict],
        ingestion_id: UUID,
        result: TransformResult,
    ) -> None:
        """Transform OrdensFabrico to curated.order."""
        for row in rows:
            payload = row.get("payload_json", {})
            
            order = {
                "ingestion_id": ingestion_id,
                "of_id": str(payload.get("OF_Id", "")),
                "produto_id": self._safe_str(payload.get("OF_Produto_Id")),
                "produto_nome": self._safe_str(payload.get("OF_Produto_Nome")),
                "modelo_id": self._safe_str(payload.get("OF_Modelo_Id")),
                "modelo_nome": self._safe_str(payload.get("OF_Modelo_Nome")),
                "data_entrada": self._parse_date(payload.get("OF_DataEntrada")),
                "data_entrega_prevista": self._parse_date(payload.get("OF_DataEntrega")),
                "data_conclusao": self._parse_date(payload.get("OF_DataConclusao")),
                "quantidade": self._safe_int(payload.get("OF_QtdPorFazer")),
                "quantidade_produzida": self._safe_int(payload.get("OF_QtdFeita")),
                "estado": self._safe_str(payload.get("OF_Estado")),
            }
            
            result.orders.append(order)
    
    def _transform_order_phases(
        self,
        rows: List[Dict],
        ingestion_id: UUID,
        result: TransformResult,
    ) -> None:
        """Transform FasesOrdemFabrico to curated.order_phase."""
        for row in rows:
            payload = row.get("payload_json", {})
            
            # Get hours fields
            horas_previstas = self._safe_decimal(payload.get("FaseOf_HorasPrevistas"))
            horas_reais = self._safe_decimal(payload.get("FaseOf_HorasReais"))
            horas_standard = self._safe_decimal(payload.get("StandardHoras"))
            
            # Calculate horas_finais: prioritize previstas > standard > None
            horas_finais = None
            if horas_previstas and horas_previstas > 0:
                horas_finais = horas_previstas
            elif horas_standard and horas_standard > 0:
                horas_finais = horas_standard
            
            phase = {
                "ingestion_id": ingestion_id,
                "of_id": str(payload.get("FaseOf_OrdemFabrico_Id", "")),
                "fase_id": str(payload.get("FaseOf_Fase_Id", "")),
                "fase_of_id": self._safe_str(payload.get("FaseOf_Id")),
                "fase_nome": self._safe_str(payload.get("FaseOf_FaseNome")),
                "horas_previstas": horas_previstas,
                "horas_reais": horas_reais,
                "horas_standard": horas_standard,
                "horas_finais": horas_finais,
                "estado": self._safe_str(payload.get("FaseOf_Estado")),
                "data_inicio": self._parse_date(payload.get("FaseOf_DataInicio")),
                "data_fim": self._parse_date(payload.get("FaseOf_DataFim")),
                "ordem": self._safe_int(payload.get("FaseOf_Ordem")),
                "molde_id": self._safe_str(payload.get("FaseOf_Molde_Id")),
            }

            result.order_phases.append(phase)

            # Sprint Q.8 Fase 4 — derive mold_usage from the order-phase
            # payload when molde_id is present. The Excel has no separate
            # mold-usage sheet; without this derivation, RoutingResolver
            # had to fall back to a regex over phase names to guess
            # whether a phase needed a mold. With this row the curated
            # layer carries the real (molde_id, of_id, fase_id) tuple.
            molde_id = phase["molde_id"]
            if molde_id:
                result.mold_usages.append(
                    {
                        "ingestion_id": ingestion_id,
                        "molde_id": molde_id,
                        "of_id": phase["of_id"],
                        "fase_id": phase["fase_id"],
                        "data_uso": phase["data_inicio"],
                    }
                )
    
    def _transform_employees(
        self,
        rows: List[Dict],
        ingestion_id: UUID,
        result: TransformResult,
    ) -> None:
        """Transform Funcionarios (used for reference)."""
        # Employees are used for skill matrix references
        # PII: Don't store names in curated if not needed
        pass
    
    def _transform_skill_matrix(
        self,
        rows: List[Dict],
        ingestion_id: UUID,
        result: TransformResult,
    ) -> None:
        """Transform FuncionariosFasesAptos to curated.skill_matrix."""
        for row in rows:
            payload = row.get("payload_json", {})
            
            skill = {
                "ingestion_id": ingestion_id,
                "funcionario_id": str(payload.get("FuncionarioApto_FuncionarioId", "")),
                "funcionario_nome": None,  # PII: Don't store name
                "fase_id": str(payload.get("FuncionarioApto_FaseId", "")),
                "fase_nome": self._safe_str(payload.get("FaseApto_Nome")),
                "apto": True,  # Being in this list means they're qualified
                "nivel": None,
            }
            
            result.skill_matrix.append(skill)
    
    def _transform_phases(
        self,
        rows: List[Dict],
        ingestion_id: UUID,
        result: TransformResult,
    ) -> None:
        """Transform Fases to curated.phase_capacity."""
        for row in rows:
            payload = row.get("payload_json", {})
            
            capacity = {
                "ingestion_id": ingestion_id,
                "fase_id": str(payload.get("Fase_Id", "")),
                "fase_nome": self._safe_str(payload.get("Fase_Nome")),
                "periodo": None,  # No specific period in base data
                "periodo_tipo": "static",
                "capacidade_horas": self._safe_decimal(payload.get("Fase_CapacidadeHoras")) or Decimal("8.0"),
                "funcionarios_count": self._safe_int(payload.get("Fase_NumFuncionarios")),
            }
            
            result.phase_capacities.append(capacity)
    
    def _transform_molds(
        self,
        rows: List[Dict],
        ingestion_id: UUID,
        result: TransformResult,
    ) -> None:
        """Transform Moldes to curated.mold."""
        for row in rows:
            payload = row.get("payload_json", {})
            
            mold = {
                "ingestion_id": ingestion_id,
                "molde_id": str(payload.get("Molde_Id", "")),
                "molde_nome": self._safe_str(payload.get("Molde_Nome")),
                "modelo_id": self._safe_str(payload.get("Molde_Modelo_Id")),
                "tamanho_id": self._safe_str(payload.get("Molde_Tamanho_Id")),
                "tipo": self._safe_str(payload.get("Molde_Tipo")),
                "estado": self._safe_str(payload.get("Molde_Estado")),
                "em_manutencao": False,
            }
            
            result.molds.append(mold)
    
    def _transform_quality_events(
        self,
        rows: List[Dict],
        ingestion_id: UUID,
        result: TransformResult,
    ) -> None:
        """Transform OrdemFabricoErros to curated.quality_event."""
        for row in rows:
            payload = row.get("payload_json", {})
            
            event = {
                "ingestion_id": ingestion_id,
                "of_id": str(payload.get("OrdemFabricoErro_OrdemFabrico_Id", "")),
                "fase_id": self._safe_str(payload.get("OrdemFabricoErro_Fase_Id")),
                "erro_tipo": self._safe_str(payload.get("OrdemFabricoErro_TipoErro")) or "unknown",
                "erro_descricao": self._safe_str(payload.get("OrdemFabricoErro_Descricao")),
                "quantidade": self._safe_int(payload.get("OrdemFabricoErro_Quantidade")) or 1,
                "data_evento": self._parse_date(payload.get("OrdemFabricoErro_Data")),
                "molde_id": self._safe_str(payload.get("OrdemFabricoErro_Molde_Id")),
            }
            
            result.quality_events.append(event)
    
    def _transform_standards(
        self,
        rows: List[Dict],
        ingestion_id: UUID,
        result: TransformResult,
    ) -> None:
        """Transform FasesStandardModelos (used for reference, merged into phases)."""
        # Standards are used to supplement horas_standard in order_phases
        pass

    def _transform_allocations(
        self,
        rows: List[Dict],
        ingestion_id: UUID,
        result: TransformResult,
    ) -> None:
        """Transform FuncionariosFaseOrdemFabrico → curated.allocation.

        The Excel sheet only carries 3 columns (FaseOfId, FuncionarioId,
        Chefe). We keep the curated row equally lean — hours are not on
        this sheet; consumers join with `CuratedOrderPhase.horas_reais`
        and divide by allocation count to derive per-worker hours.

        `Chefe` arrives as 0/1 (int) or True/False; cast through bool().
        """
        seen_keys: set[tuple[str, str]] = set()
        dup = 0
        for row in rows:
            payload = row.get("payload_json", {})

            fase_of_id = self._safe_str(
                payload.get("FuncionarioFaseOf_FaseOfId")
            )
            funcionario_id = self._safe_str(
                payload.get("FuncionarioFaseOf_FuncionarioId")
            )
            if not fase_of_id or not funcionario_id:
                # Composite key incomplete — drop silently into warnings;
                # without both halves the row can't be joined back to
                # CuratedOrderPhase.
                continue

            key = (fase_of_id, funcionario_id)
            if key in seen_keys:
                dup += 1
                continue
            seen_keys.add(key)

            allocation = {
                "ingestion_id": ingestion_id,
                "fase_of_id": fase_of_id,
                "funcionario_id": funcionario_id,
                "is_chefe": bool(payload.get("FuncionarioFaseOf_Chefe")),
            }
            result.allocations.append(allocation)

        if dup:
            result.warnings.append(
                f"_transform_allocations: {dup} duplicate (fase_of_id,"
                " funcionario_id) keys collapsed"
            )

    def _transform_models(
        self,
        rows: List[Dict],
        ingestion_id: UUID,
        result: TransformResult,
    ) -> None:
        """Transform Modelos → curated.modelo.

        The sheet's rows are products (`Produto_*` columns) but the
        curated table is named `modelo` because that's the planning
        concept. We persist all 9 source columns mapped to snake_case.
        """
        seen_keys: set[str] = set()
        dup = 0
        for row in rows:
            payload = row.get("payload_json", {})

            produto_id = self._safe_str(payload.get("Produto_Id"))
            if not produto_id:
                continue
            if produto_id in seen_keys:
                dup += 1
                continue
            seen_keys.add(produto_id)

            model = {
                "ingestion_id": ingestion_id,
                "produto_id": produto_id,
                "produto_nome": self._safe_str(payload.get("Produto_Nome")),
                "modelo_id": self._safe_str(payload.get("Produto_ModeloId")),
                "tamanho_id": self._safe_str(payload.get("Produto_TamanhoId")),
                "peso_desmolde_kg": self._safe_decimal(
                    payload.get("Produto_PesoDesmolde")
                ),
                "peso_acabamento_kg": self._safe_decimal(
                    payload.get("Produto_PesoAcabamento")
                ),
                "qtd_gel_deck": self._safe_decimal(
                    payload.get("Produto_QtdGelDeck")
                ),
                "qtd_gel_casco": self._safe_decimal(
                    payload.get("Produto_QtdGelCasco")
                ),
                "numero_pocos_id": self._safe_str(
                    payload.get("Produto_NumeroPocosId")
                ),
            }
            result.models.append(model)

        if dup:
            result.warnings.append(
                f"_transform_models: {dup} duplicate produto_id rows collapsed"
            )

    # Helper methods
    
    def _safe_str(self, value: Any) -> Optional[str]:
        """Convert value to string safely."""
        if value is None:
            return None
        s = str(value).strip()
        return s if s else None
    
    def _safe_int(self, value: Any) -> Optional[int]:
        """Convert value to int safely."""
        if value is None:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        """Convert value to Decimal safely."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None
    
    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse date from various formats."""
        if value is None:
            return None
        
        if isinstance(value, date):
            return value
        
        if isinstance(value, datetime):
            return value.date()
        
        try:
            # Try common formats
            s = str(value).strip()
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(s, fmt).date()
                except ValueError:
                    continue
        except Exception as exc:
            # Sprint Q.7 Fase 4 — was bare `pass`. Unparseable date →
            # caller treats as missing. Log under DEBUG so unusual
            # inputs surface during ingest debugging.
            logger.debug("date parse failed for %r: %s", value, exc)

        return None


