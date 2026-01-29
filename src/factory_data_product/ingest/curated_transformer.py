"""
Data transformations for the CURATED layer.

Implements normalization rules based on kayak_production/curated/transformers.py:
- Handle "0" semantics (UNKNOWN/NOT_SET)
- Create derived fields (HorasPrevistas_Final)
- Resolve standard duplicates
- Flag outliers and invalid records
- Calculate mold occupancy windows

Adapted from pandas-based kayak_production to work with SQLAlchemy models.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import (
    MOLD_OCCUPANCY_HOURS,
    VALOR_HORA_MIN,
    VALOR_HORA_MAX_PERCENTILE,
    TRUST_INDEX,
)

logger = logging.getLogger(__name__)


# ============================================================================
# QUARANTINE CODES
# ============================================================================

class QuarantineCode:
    """Machine-readable quarantine codes."""
    MISSING_KEY = "MISSING_KEY"           # Required business key is missing
    INVALID_TIMING = "INVALID_TIMING"     # End date before start date
    INVALID_VALUE = "INVALID_VALUE"       # Value out of valid range
    DUPLICATE_KEY = "DUPLICATE_KEY"       # Duplicate business key
    ORPHAN_RECORD = "ORPHAN_RECORD"       # Foreign key references non-existent record
    DATA_CONFLICT = "DATA_CONFLICT"       # Conflicting data within same record
    OUTLIER = "OUTLIER"                   # Statistical outlier


def quarantine_row(
    row: Dict,
    code: str,
    reason: str,
) -> Dict:
    """
    Mark a row as quarantined instead of deleting/ignoring.
    
    Args:
        row: The data row
        code: QuarantineCode value
        reason: Human-readable explanation
        
    Returns:
        Row with quarantine fields set
    """
    row["is_quarantined"] = True
    row["quarantine_code"] = code
    row["quarantine_reason"] = reason
    row["quarantined_at"] = datetime.now().isoformat()
    return row


class CuratedTransformer:
    """
    Transforms RAW Excel data into CURATED layer with derived fields and quality flags.
    
    Works with SQLAlchemy async session for database-backed storage.
    """
    
    def __init__(self, db: AsyncSession, ingestion_id: UUID):
        """
        Initialize transformer.
        
        Args:
            db: AsyncSession for database operations
            ingestion_id: ID of the ingestion run being processed
        """
        self.db = db
        self.ingestion_id = ingestion_id
        self._standards_lookup: Dict[Tuple[str, str], float] = {}
    
    async def transform_raw_to_curated(self, raw_data: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """
        Transform all RAW data to CURATED layer.
        
        Args:
            raw_data: Dictionary of sheet_name -> list of row dicts from RAW
            
        Returns:
            Summary of transformation results
        """
        logger.info(f"Starting CURATED transformation for ingestion {self.ingestion_id}")
        
        results = {
            "ingestion_id": str(self.ingestion_id),
            "tables_processed": 0,
            "rows_transformed": 0,
            "derived_fields_created": [],
            "flags_created": [],
            "errors": [],
        }
        
        # Build standards lookup first
        if "FasesStandardModelos" in raw_data:
            self._build_standards_lookup(raw_data["FasesStandardModelos"])
            results["derived_fields_created"].append("standards_lookup")
        
        # Transform each table
        for table_name, rows in raw_data.items():
            try:
                transformed = await self._transform_table(table_name, rows)
                results["tables_processed"] += 1
                results["rows_transformed"] += len(transformed)
            except Exception as e:
                logger.error(f"Error transforming {table_name}: {e}")
                results["errors"].append(f"{table_name}: {str(e)}")
        
        logger.info(f"CURATED transformation complete: {results['tables_processed']} tables, {results['rows_transformed']} rows")
        
        return results
    
    def _build_standards_lookup(self, standards_rows: List[Dict]) -> None:
        """
        Build lookup table for standard hours (resolved duplicates).
        
        For duplicates, takes max(non_zero) value.
        """
        # Group by (ProdutoId, FaseId) and take max non-zero value
        grouped: Dict[Tuple[str, str], List[float]] = {}
        
        for row in standards_rows:
            produto_id = str(row.get("ProdutoFase_ProdutoId", ""))
            fase_id = str(row.get("ProdutoFase_FaseId", ""))
            horas = float(row.get("ProdutoFase_HorasPrevistas", 0) or 0)
            
            key = (produto_id, fase_id)
            if key not in grouped:
                grouped[key] = []
            if horas > 0:
                grouped[key].append(horas)
        
        # Take max for each key
        for key, values in grouped.items():
            self._standards_lookup[key] = max(values) if values else 0
        
        logger.info(f"Built standards lookup: {len(self._standards_lookup)} unique keys")
    
    async def _transform_table(self, table_name: str, rows: List[Dict]) -> List[Dict]:
        """Transform a single table's rows."""
        
        if table_name == "OrdensFabrico":
            return self._transform_ordens(rows)
        elif table_name == "FasesOrdemFabrico":
            return self._transform_fases_of(rows)
        elif table_name == "Funcionarios":
            return self._transform_funcionarios(rows)
        elif table_name == "Fases":
            return self._transform_fases(rows)
        elif table_name == "Moldes":
            return self._transform_moldes(rows)
        elif table_name == "OrdemFabricoErros":
            return self._transform_erros(rows)
        elif table_name == "FuncionariosFasesAptos":
            return self._transform_aptos(rows)
        elif table_name == "FuncionariosFaseOrdemFabrico":
            return self._transform_alocacoes(rows)
        else:
            # Pass through without transformation
            return rows
    
    def _transform_ordens(self, rows: List[Dict]) -> List[Dict]:
        """Transform OrdensFabrico table."""
        transformed = []
        
        for row in rows:
            r = row.copy()
            
            # Open/closed status
            data_acabamento = r.get("Of_DataAcabamento")
            r["is_open"] = data_acabamento is None or data_acabamento == ""
            
            # Lead time calculation
            data_criacao = r.get("Of_DataCriacao")
            if data_criacao and data_acabamento:
                try:
                    if isinstance(data_criacao, str):
                        data_criacao = datetime.fromisoformat(data_criacao.replace("Z", "+00:00"))
                    if isinstance(data_acabamento, str):
                        data_acabamento = datetime.fromisoformat(data_acabamento.replace("Z", "+00:00"))
                    
                    lead_time = (data_acabamento - data_criacao).total_seconds() / 86400
                    r["lead_time_days"] = round(lead_time, 2)
                    r["has_valid_dates"] = lead_time >= 0
                except Exception:
                    r["lead_time_days"] = None
                    r["has_valid_dates"] = False
            else:
                r["lead_time_days"] = None
                r["has_valid_dates"] = True
            
            transformed.append(r)
        
        logger.info(f"Transformed OrdensFabrico: {len(transformed)} rows, {sum(1 for r in transformed if r['is_open'])} open")
        return transformed
    
    def _transform_fases_of(self, rows: List[Dict]) -> List[Dict]:
        """
        Transform FasesOrdemFabrico with derived fields.
        
        CRITICAL: Implements HorasPrevistas_Final derivation.
        """
        transformed = []
        hp_from_fase = 0
        hp_from_standard = 0
        hp_missing = 0
        
        for row in rows:
            r = row.copy()
            
            # Open/closed status
            data_fim = r.get("FaseOf_Fim")
            r["is_phase_open"] = data_fim is None or data_fim == ""
            
            # Duration calculation
            data_inicio = r.get("FaseOf_Inicio")
            if data_inicio and data_fim:
                try:
                    if isinstance(data_inicio, str):
                        data_inicio = datetime.fromisoformat(data_inicio.replace("Z", "+00:00"))
                    if isinstance(data_fim, str):
                        data_fim = datetime.fromisoformat(data_fim.replace("Z", "+00:00"))
                    
                    duration = (data_fim - data_inicio).total_seconds() / 3600
                    r["duration_hours"] = round(duration, 2)
                    r["is_event_marker"] = data_inicio == data_fim
                    r["is_invalid_timing"] = duration < 0
                    
                    # QUARANTINE: Invalid timing (end before start)
                    if duration < 0:
                        r = quarantine_row(
                            r,
                            QuarantineCode.INVALID_TIMING,
                            f"Fim ({data_fim}) antes de Início ({data_inicio}), duração={duration:.2f}h"
                        )
                except Exception:
                    r["duration_hours"] = None
                    r["is_event_marker"] = False
                    r["is_invalid_timing"] = False
            else:
                r["duration_hours"] = None
                r["is_event_marker"] = False
                r["is_invalid_timing"] = False
            
            # Initialize quarantine fields if not set
            if "is_quarantined" not in r:
                r["is_quarantined"] = False
                r["quarantine_code"] = None
                r["quarantine_reason"] = None
                r["quarantined_at"] = None
            
            # === HorasPrevistas_Final derivation (CRITICAL) ===
            
            # Try Coeficiente field first (actual column name in Excel)
            horas_fase = float(r.get("FaseOf_Coeficiente", 0) or 0)
            if horas_fase <= 0:
                horas_fase = float(r.get("FaseOf_HorasPrevistas", 0) or 0)
            
            if horas_fase > 0:
                # Use value from the phase itself
                r["HorasPrevistas_Final"] = horas_fase
                r["HorasPrevistas_Source"] = "fase"
                hp_from_fase += 1
            else:
                # Fallback to standard lookup
                produto_id = str(r.get("Of_ProdutoId", "") or r.get("ProdutoId", ""))
                fase_id = str(r.get("FaseOf_FaseId", ""))
                
                standard_key = (produto_id, fase_id)
                standard_horas = self._standards_lookup.get(standard_key, 0)
                
                if standard_horas > 0:
                    r["HorasPrevistas_Final"] = standard_horas
                    r["HorasPrevistas_Source"] = "standard"
                    hp_from_standard += 1
                else:
                    r["HorasPrevistas_Final"] = None
                    r["HorasPrevistas_Source"] = None
                    hp_missing += 1
            
            # Mold occupancy window
            molde_id = r.get("MoldeOfId")
            data_prevista = r.get("FaseOf_DataPrevista")
            if molde_id and data_prevista:
                try:
                    if isinstance(data_prevista, str):
                        data_prevista = datetime.fromisoformat(data_prevista.replace("Z", "+00:00"))
                    r["mold_occupancy_start"] = data_prevista.isoformat()
                    r["mold_occupancy_end"] = (data_prevista + timedelta(hours=MOLD_OCCUPANCY_HOURS)).isoformat()
                except Exception:
                    r["mold_occupancy_start"] = None
                    r["mold_occupancy_end"] = None
            else:
                r["mold_occupancy_start"] = None
                r["mold_occupancy_end"] = None
            
            r["has_mold_model_mismatch"] = False  # Would need join with Modelos
            
            transformed.append(r)
        
        total = len(transformed)
        coverage = (hp_from_fase + hp_from_standard) / total * 100 if total > 0 else 0
        
        logger.info(
            f"Transformed FasesOrdemFabrico: {total} rows, "
            f"HorasPrevistas coverage: {coverage:.1f}% "
            f"(fase: {hp_from_fase}, standard: {hp_from_standard}, missing: {hp_missing})"
        )
        
        return transformed
    
    def _transform_funcionarios(self, rows: List[Dict]) -> List[Dict]:
        """Transform Funcionarios table with ValorHora outlier flags."""
        transformed = []
        
        # Calculate p99 threshold for outlier detection
        valid_valores = [
            float(r.get("FuncionarioValorHora", 0) or 0)
            for r in rows
            if float(r.get("FuncionarioValorHora", 0) or 0) > VALOR_HORA_MIN
        ]
        
        p99_threshold = None
        if valid_valores:
            sorted_valores = sorted(valid_valores)
            p99_idx = int(len(sorted_valores) * VALOR_HORA_MAX_PERCENTILE / 100)
            p99_threshold = sorted_valores[min(p99_idx, len(sorted_valores) - 1)]
        
        for row in rows:
            r = row.copy()
            
            # Active flag
            r["is_active"] = r.get("Funcionario_Activo") == 1 or r.get("FuncionarioAtivo") == 1
            
            # ValorHora validation
            valor_hora = float(r.get("FuncionarioValorHora", 0) or 0)
            r["has_valid_valor_hora"] = valor_hora > VALOR_HORA_MIN
            r["is_valor_hora_outlier"] = valor_hora > p99_threshold if p99_threshold else False
            r["valor_hora_p99_threshold"] = p99_threshold
            
            transformed.append(r)
        
        active_count = sum(1 for r in transformed if r["is_active"])
        valid_vh_count = sum(1 for r in transformed if r["has_valid_valor_hora"])
        
        logger.info(f"Transformed Funcionarios: {len(transformed)} rows, {active_count} active, {valid_vh_count} with valid ValorHora")
        return transformed
    
    def _transform_fases(self, rows: List[Dict]) -> List[Dict]:
        """Transform Fases table."""
        transformed = []
        
        for row in rows:
            r = row.copy()
            
            # Production flag
            r["is_production"] = r.get("Fase_Producao") == 1
            
            # Capacity validation
            num_funcionarios = float(r.get("Fase_NumeroFuncionarios", 0) or 0)
            capacidade = float(r.get("Fase_CapacidadeHorasDia", 0) or 0)
            expected_capacity = num_funcionarios * 8  # 8 hours per day
            
            if expected_capacity > 0 and capacidade > 0:
                r["capacity_matches_employees"] = abs(capacidade - expected_capacity) / expected_capacity < 0.1
            else:
                r["capacity_matches_employees"] = True
            
            transformed.append(r)
        
        production_count = sum(1 for r in transformed if r["is_production"])
        logger.info(f"Transformed Fases: {len(transformed)} rows, {production_count} production")
        return transformed
    
    def _transform_moldes(self, rows: List[Dict]) -> List[Dict]:
        """Transform Moldes table."""
        transformed = []
        
        for row in rows:
            r = row.copy()
            # State decoding would need business dictionary
            r["estado_decoded"] = "UNKNOWN"
            transformed.append(r)
        
        logger.info(f"Transformed Moldes: {len(transformed)} rows")
        return transformed
    
    def _transform_erros(self, rows: List[Dict]) -> List[Dict]:
        """Transform OrdemFabricoErros table."""
        transformed = []
        
        for row in rows:
            r = row.copy()
            
            # Flag for missing fase culpada
            fase_culpada = r.get("Erro_FaseOfCulpada")
            r["has_fase_culpada"] = fase_culpada is not None and fase_culpada != ""
            
            transformed.append(r)
        
        with_culpada = sum(1 for r in transformed if r["has_fase_culpada"])
        pct = with_culpada / len(transformed) * 100 if transformed else 0
        
        logger.info(f"Transformed OrdemFabricoErros: {len(transformed)} rows, {with_culpada} ({pct:.1f}%) with fase culpada")
        return transformed
    
    def _transform_aptos(self, rows: List[Dict]) -> List[Dict]:
        """Transform FuncionariosFasesAptos table."""
        logger.info(f"Transformed FuncionariosFasesAptos: {len(rows)} rows")
        return rows
    
    def _transform_alocacoes(self, rows: List[Dict]) -> List[Dict]:
        """Transform FuncionariosFaseOrdemFabrico table."""
        transformed = []
        
        for row in rows:
            r = row.copy()
            r["is_chefe"] = r.get("FuncionarioFaseOf_Chefe") == 1
            transformed.append(r)
        
        chefes = sum(1 for r in transformed if r["is_chefe"])
        logger.info(f"Transformed FuncionariosFaseOrdemFabrico: {len(transformed)} rows, {chefes} chefes")
        return transformed

