"""
Excel Parser — Contrato 010
===========================

Parse Excel files to extract sheets and rows.

Handles:
- Multiple sheets
- Header detection
- Type normalization
- Empty cell handling
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SheetData:
    """Parsed data from a single sheet."""
    
    name: str
    headers: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    
    # Business key fields (if identifiable)
    business_key_fields: Optional[List[str]] = None


@dataclass
class ParsedExcel:
    """Result of parsing an Excel file."""
    
    sheets: Dict[str, SheetData]
    total_rows: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# Known business keys per sheet
# NOTE: Column names must match EXACTLY what's in the Excel file (case-sensitive)
BUSINESS_KEY_MAP = {
    "OrdensFabrico": ["Of_Id"],  # Excel uses Of_Id not OF_Id
    "FasesOrdemFabrico": ["FaseOf_Id"],
    "FuncionariosFaseOrdemFabrico": ["FuncionarioFaseOf_FaseOfId", "FuncionarioFaseOf_FuncionarioId"],  # Composite key
    "OrdemFabricoErros": ["OrdemFabricoErro_Id"],
    "Funcionarios": ["Funcionario_Id"],
    "FuncionariosFasesAptos": ["FuncionarioFase_FuncionarioId", "FuncionarioFase_FaseId"],  # Composite key
    "Fases": ["Fase_Id"],
    "Moldes": ["Molde_Id"],
    "Modelos": ["Modelo_Id"],
    "FasesStandardModelos": ["FaseStandardModelo_Id"],
}


class ExcelParser:
    """
    Parse Excel files to structured data.
    
    Features:
    - Handles .xlsx and .xls
    - Auto-detects headers
    - Normalizes values (strips whitespace, handles empty)
    - Identifies business keys
    """
    
    def __init__(self):
        self._pandas = None
    
    def _get_pandas(self):
        """Lazy import pandas."""
        if self._pandas is None:
            import pandas as pd
            self._pandas = pd
        return self._pandas
    
    def parse(self, file_path: Path) -> ParsedExcel:
        """
        Parse an Excel file.
        
        Args:
            file_path: Path to Excel file
        
        Returns:
            ParsedExcel with all sheets and rows
        """
        pd = self._get_pandas()
        result = ParsedExcel(sheets={})
        
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            for sheet_name in sheet_names:
                try:
                    sheet_data = self._parse_sheet(excel_file, sheet_name)
                    result.sheets[sheet_name] = sheet_data
                    result.total_rows += sheet_data.row_count
                except Exception as e:
                    result.errors.append(f"Error parsing sheet '{sheet_name}': {str(e)}")
                    logger.error(f"Error parsing sheet {sheet_name}: {e}")
            
        except Exception as e:
            result.errors.append(f"Error reading Excel file: {str(e)}")
            logger.error(f"Error reading Excel file: {e}")
        
        return result
    
    def _parse_sheet(self, excel_file, sheet_name: str) -> SheetData:
        """Parse a single sheet."""
        pd = self._get_pandas()
        
        # Read sheet
        df = excel_file.parse(sheet_name)
        
        # Get headers (column names)
        headers = [str(col) for col in df.columns.tolist()]
        
        # Get business key fields
        business_key_fields = BUSINESS_KEY_MAP.get(sheet_name)
        
        # Convert to list of dicts with normalization
        rows = []
        for idx, row in df.iterrows():
            normalized_row = self._normalize_row(row.to_dict())
            rows.append(normalized_row)
        
        return SheetData(
            name=sheet_name,
            headers=headers,
            rows=rows,
            row_count=len(rows),
            business_key_fields=business_key_fields,
        )
    
    def _normalize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize row values.
        
        - Strip whitespace from strings
        - Convert NaN to None
        - Convert numpy types to Python types
        """
        pd = self._get_pandas()
        normalized = {}
        
        for key, value in row.items():
            # Handle pandas NA / NaN
            if pd.isna(value):
                normalized[key] = None
            # Handle numpy types
            elif hasattr(value, "item"):
                normalized[key] = value.item()
            # Handle strings
            elif isinstance(value, str):
                stripped = value.strip()
                normalized[key] = stripped if stripped else None
            else:
                normalized[key] = value
        
        return normalized
    
    def iter_rows(
        self,
        file_path: Path,
    ) -> Generator[Tuple[str, int, Dict[str, Any], Optional[List[str]]], None, None]:
        """
        Iterate over all rows in an Excel file.
        
        Yields:
            (sheet_name, row_number, payload, business_key_fields)
        """
        parsed = self.parse(file_path)
        
        for sheet_name, sheet_data in parsed.sheets.items():
            for idx, row in enumerate(sheet_data.rows, start=2):  # Start at 2 (header is row 1)
                yield (
                    sheet_name,
                    idx,
                    row,
                    sheet_data.business_key_fields,
                )


