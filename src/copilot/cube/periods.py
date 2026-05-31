"""Q.R2.1 — resolução de períodos PT-PT para o Cube.

Extraído de `src/copilot/routing/slot_filler.py` (e7772d9). Esse package
`routing` não existe neste ramo e o resto dele (fill_slots/RouteSpec) não é
preciso para o Cube — só `resolve_periodo` e os seus 3 helpers. Manter aqui
auto-contido evita arrastar `route_loader.RouteSpec`.

`interpret.py` importa `resolve_periodo` deste módulo. Cube interpreta
`dateRange` como inclusivo nos dois extremos; quem chama trata a conversão
da janela `[início, fim)` que estas funções devolvem.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

_MESES = {
    "janeiro": 1, "jan": 1,
    "fevereiro": 2, "fev": 2,
    "março": 3, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "maio": 5, "mai": 5,
    "junho": 6, "jun": 6,
    "julho": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "setembro": 9, "set": 9,
    "outubro": 10, "out": 10,
    "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}


def _norm(s: str) -> str:
    return s.lower().strip()


def _month_window(year: int, month: int) -> Tuple[datetime, datetime]:
    """[início do mês, início do mês seguinte)."""
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def _year_window(year: int) -> Tuple[datetime, datetime]:
    return datetime(year, 1, 1), datetime(year + 1, 1, 1)


def resolve_periodo(
    pergunta: str,
    now: Optional[datetime] = None,
) -> Optional[Tuple[datetime, datetime, str]]:
    """Extrai um período da pergunta. Devolve (data_inicio, data_fim, descricao)
    ou None se nada explícito.

    Coberturas (em PT-PT):
      - "este mês" / "no último mês" / "do último mês"
      - "última semana" / "ultima semana"
      - "este ano" / "no ano corrente"
      - "março" / "em março" / "março de 2025" (ano default: corrente)
      - "2025" / "em 2025" / "no ano 2026"
      - YYYY-MM (período de um mês ISO)
    """
    now = now or datetime.now()
    p = _norm(pergunta)

    # YYYY-MM (mais específico — tenta primeiro)
    m = re.search(r"\b(\d{4})-(\d{1,2})\b", p)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            start, end = _month_window(y, mo)
            return start, end, f"{y:04d}-{mo:02d}"

    if "último mês" in p or "ultimo mes" in p:
        # mês anterior completo
        y, mo = now.year, now.month
        mo -= 1
        if mo == 0:
            mo = 12
            y -= 1
        start, end = _month_window(y, mo)
        return start, end, f"último mês ({y:04d}-{mo:02d})"

    if "este mês" in p or "este mes" in p or "no mês" in p or "no mes" in p:
        start, end = _month_window(now.year, now.month)
        return start, end, f"este mês ({now.year:04d}-{now.month:02d})"

    if "última semana" in p or "ultima semana" in p or "semana passada" in p:
        end = now
        start = now - timedelta(days=7)
        return start, end, "última semana (7 dias)"

    if "esta semana" in p:
        weekday = now.weekday()  # 0 = segunda
        start = (now - timedelta(days=weekday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start + timedelta(days=7)
        return start, end, "esta semana"

    if "este ano" in p or "ano corrente" in p or "neste ano" in p:
        start, end = _year_window(now.year)
        return start, end, f"este ano ({now.year})"

    if "último ano" in p or "ultimo ano" in p or "ano passado" in p:
        start, end = _year_window(now.year - 1)
        return start, end, f"ano passado ({now.year - 1})"

    # Mês nominal (ex.: "em março", "março de 2025")
    for nome, mo in _MESES.items():
        if re.search(rf"\b{nome}\b", p):
            year = now.year
            ym = re.search(rf"{nome}\s+de\s+(\d{{4}})", p) or re.search(
                r"\b(\d{4})\b", p
            )
            if ym:
                year = int(ym.group(1))
            start, end = _month_window(year, mo)
            return start, end, f"{nome} de {year}"

    # Ano isolado (ex.: "em 2025", "2026")
    m = re.search(r"\b(20\d{2})\b", p)
    if m:
        year = int(m.group(1))
        start, end = _year_window(year)
        return start, end, f"ano {year}"

    return None


__all__ = ["resolve_periodo"]
