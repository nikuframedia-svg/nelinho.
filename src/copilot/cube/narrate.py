"""Payload Cube → texto PT-PT + guard de números E contexto.

O LLM narra o resultado mas só pode usar números que existem no payload.
Após a narração, extraímos:
  1. **Q.93.D.bis** — números do texto + confronto com payload (`guard_numbers`).
  2. **Q.93.E.C.2** — contexto temporal: meses/anos mencionados no texto
     têm de bater o `dateRange` da query. Q.93.E.B mostrou que o LLM podia
     narrar "em Abril 2026" quando o range era Maio (número correcto,
     contexto inventado) — agora é erro silencioso que o guard apanha.

Defesa contra alucinação número E contexto. Narração rejeitada → tabela
crua + aviso. Re-tentativa fica para Q.93.F (não implementada nesta sprint).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.copilot.cube.client import CubeResult
from src.copilot.llm.base import LLMClient


PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "cube_narrate.md"
)
DEFAULT_MODEL = "qwen3.5:9b"

# Tolerância relativa para arredondamentos. Ex.: payload 4.7236, narração
# pode ter "4.72" ou "4.724" — ambos dentro de 1% relativo.
GUARD_REL_TOL = 0.01

# Números pequenos que não fazem distinção (0, 1, 2, 3 = contagens
# genéricas — "3 lavesans", "2 unidades"). Não exigimos suporte para
# números inteiros pequenos < INTEGER_PASSTHROUGH.
INTEGER_PASSTHROUGH = 20

NUMBER_RE = re.compile(r"-?\d+(?:[\.,]\d+)?")


@dataclass(slots=True)
class NarrationResult:
    text: str
    ok: bool
    unsupported_numbers: list[float]
    # Q.93.E.C.2 — violações de contexto temporal/material/unidade.
    context_violations: list[str] = field(default_factory=list)


# Q.93.E.C.2 — guard de contexto temporal.
_PT_MONTHS: dict[str, int] = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3,
    "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}
_PT_MONTH_RE = re.compile(
    r"\b(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|"
    r"agosto|setembro|outubro|novembro|dezembro)\b",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")

# Nomes PT-PT dos meses para a formatação proactiva do período canónico.
_MONTH_NAMES_PT: dict[int, str] = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def _format_canonical_period(query: dict) -> str | None:
    """Q.93.E.C.2.A — período canónico em texto PT-PT injectado no prompt
    de narração. Força o LLM a usar o mês/período certo em vez de alucinar.

    Casos cobertos (em ordem de especificidade):
      - mês completo ("2026-05-01" a "2026-05-31") → "Maio de 2026"
      - mês parcial ("2026-05-01" a "2026-05-26") → "Maio de 2026 (1 a 26)"
      - trimestre completo → "1º trimestre de 2026"
      - ano completo → "ano 2026"
      - range cross-month/year → "[2026-05-01, 2026-06-15]" literal

    Retorna `None` se não houver `timeDimensions.dateRange` no query.
    """
    tds = query.get("timeDimensions") or []
    if not tds:
        return None
    dr = (tds[0] or {}).get("dateRange")
    if not isinstance(dr, list) or len(dr) != 2:
        return None
    try:
        start = _dt.date.fromisoformat(str(dr[0])[:10])
        end = _dt.date.fromisoformat(str(dr[1])[:10])
    except ValueError:
        return None
    if start > end:
        return None

    # Caso 1: mesmo ano + mesmo mês.
    if start.year == end.year and start.month == end.month:
        mes = _MONTH_NAMES_PT[start.month]
        # mês completo (1 a último dia)
        if start.day == 1:
            # último dia do mês:
            if end.month == 12:
                last = _dt.date(end.year + 1, 1, 1) - _dt.timedelta(days=1)
            else:
                last = _dt.date(end.year, end.month + 1, 1) - _dt.timedelta(days=1)
            if end == last:
                return f"{mes} de {start.year}"
        return f"{mes} de {start.year} ({start.day} a {end.day})"

    # Caso 2: trimestre completo (mesmo ano, mês-mês mapeia para trimestre).
    if start.year == end.year and start.day == 1:
        trimestres = {(1, 3): "1º", (4, 6): "2º", (7, 9): "3º", (10, 12): "4º"}
        for (m_ini, m_fim), nome in trimestres.items():
            if start.month == m_ini and end.month == m_fim:
                # Confirma que end é o último dia do mês final.
                if m_fim == 12:
                    last = _dt.date(end.year + 1, 1, 1) - _dt.timedelta(days=1)
                else:
                    last = _dt.date(end.year, m_fim + 1, 1) - _dt.timedelta(days=1)
                if end == last:
                    return f"{nome} trimestre de {start.year}"

    # Caso 3: ano completo.
    if (
        start.year == end.year
        and start.month == 1 and start.day == 1
        and end.month == 12 and end.day == 31
    ):
        return f"ano {start.year}"

    # Fallback: range literal.
    return f"[{start.isoformat()}, {end.isoformat()}]"


def _months_in_range(date_range: list[str]) -> set[int]:
    """Conjunto de meses (1-12) cobertos pelo dateRange Cube-inclusive."""
    if not date_range or len(date_range) != 2:
        return set()
    try:
        start = _dt.date.fromisoformat(date_range[0][:10])
        end = _dt.date.fromisoformat(date_range[1][:10])
    except ValueError:
        return set()
    if start > end:
        return set()
    months: set[int] = set()
    cur = start.replace(day=1)
    # Avança um mês de cada vez até passar `end`.
    while cur <= end:
        months.add(cur.month)
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return months


def _years_in_range(date_range: list[str]) -> set[int]:
    """Conjunto de anos cobertos pelo dateRange."""
    if not date_range or len(date_range) != 2:
        return set()
    try:
        start = _dt.date.fromisoformat(date_range[0][:10])
        end = _dt.date.fromisoformat(date_range[1][:10])
    except ValueError:
        return set()
    if start > end:
        return set()
    return set(range(start.year, end.year + 1))


def guard_context(text: str, result: CubeResult) -> tuple[bool, list[str]]:
    """Confronta CONTEXTO da narração (temporal + material + unidade) com payload.

    Q.93.E.C.2.B — alargado para 3 camadas:
      1. **Temporal**: meses/anos mencionados ∈ months_allowed (dateRange)
      2. **Material**: se data tem materiais, a narração TEM de mencionar
         pelo menos um deles (ou ser metanarração que não cita material).
      3. **Unidade**: se data tem unidade_id mapeada em `units.KNOWN_UNITS`,
         a narração que mencione unidade tem de ser coerente.

    Defesa em profundidade contra erro silencioso de CONTEXTO — o número certo
    com mês/material/unidade errado é tão perigoso como número errado.
    """
    violations: list[str] = []
    text_low = text.lower()

    # ──────────────────────────────────────────────────────────
    # 1. Temporal (Q.93.E.C.2)
    # ──────────────────────────────────────────────────────────
    date_ranges: list[list[str]] = []
    for td in (result.query.get("timeDimensions") or []):
        dr = td.get("dateRange")
        if isinstance(dr, list) and len(dr) == 2:
            date_ranges.append([str(dr[0]), str(dr[1])])

    if date_ranges:
        months_allowed: set[int] = set()
        years_allowed: set[int] = set()
        for dr in date_ranges:
            months_allowed |= _months_in_range(dr)
            years_allowed |= _years_in_range(dr)

        for m in _PT_MONTH_RE.findall(text_low):
            m_norm = m.lower().replace("ç", "c")
            m_num = _PT_MONTHS.get(m_norm)
            if m_num is None:
                continue
            if m_num not in months_allowed:
                violations.append(
                    f"narrou mes '{m}' (={m_num}) mas dateRange "
                    f"so cobre meses {sorted(months_allowed)}"
                )

        for y in _YEAR_RE.findall(text):
            y_num = int(y)
            if y_num not in years_allowed:
                violations.append(
                    f"narrou ano {y_num} mas dateRange cobre anos {sorted(years_allowed)}"
                )

    # ──────────────────────────────────────────────────────────
    # 2. Material (Q.93.E.C.2.B) — só verifica quando o payload tem material
    # ──────────────────────────────────────────────────────────
    payload_materials: set[str] = set()
    for row in result.data:
        mat = row.get("consumo_material.material")
        if isinstance(mat, str) and mat.strip():
            payload_materials.add(mat.lower())
    # Também aceita material via filter `equals` no query.
    for f in result.query.get("filters", []) or []:
        if "material" in str(f.get("member", "")).lower():
            for v in f.get("values", []) or []:
                if isinstance(v, str) and v.strip():
                    payload_materials.add(v.lower())

    if payload_materials:
        # Match laxo: pelo menos uma palavra de algum material aparece no texto.
        # Aceita "Resina Lavesan EN 720" cobrindo "lavesan" ou "resina" ou "720".
        text_tokens = set(re.findall(r"\w+", text_low))
        found_any = False
        for mat in payload_materials:
            mat_tokens = set(re.findall(r"\w+", mat))
            # Tira tokens triviais (artigos, prepositional words curtas).
            mat_tokens = {t for t in mat_tokens if len(t) > 2}
            if mat_tokens & text_tokens:
                found_any = True
                break
        if not found_any:
            violations.append(
                f"narração não menciona nenhum dos materiais do payload "
                f"({sorted(payload_materials)[:3]}...). Erro silencioso de contexto."
            )

    # ──────────────────────────────────────────────────────────
    # 3. Unidade (Q.93.E.C.2.B) — confronto com unit_label do mapping NELO
    # ──────────────────────────────────────────────────────────
    payload_unit_ids: set[int] = set()
    for row in result.data:
        uid = row.get("consumo_material.unidade_id")
        if isinstance(uid, (int, float)):
            payload_unit_ids.add(int(uid))

    # ──────────────────────────────────────────────────────────
    # 4. Custo (Q.94.C.2.3 → Q.95.2): narração só pode mencionar €/custo se
    # payload tem uma medida monetária. Pergunta ao `measure_contract` em
    # vez de fazer match por sufixo `.custo` (escalável para futuras medidas
    # monetárias em outros cubes).
    # ──────────────────────────────────────────────────────────
    from src.copilot.cube.measure_contract import is_monetary_measure

    payload_has_custo = False
    # data: alguma coluna com medida monetária e valor não-NULL.
    for row in result.data:
        for k, v in row.items():
            if v is not None and is_monetary_measure(str(k)):
                payload_has_custo = True
                break
        if payload_has_custo:
            break
    # query: medida monetária solicitada.
    if not payload_has_custo:
        for m in result.query.get("measures", []) or []:
            if is_monetary_measure(str(m)):
                payload_has_custo = True
                break

    if not payload_has_custo:
        # Procura "€" ou palavras-chave de custo no texto. Tolera "custos" plural
        # e "custou".
        _CUSTO_RE = re.compile(r"(?:€|\beuros?\b|\bcust(?:o|os|ou|ar|aram)\b)", re.IGNORECASE)
        if _CUSTO_RE.search(text):
            violations.append(
                "narração menciona €/custo mas payload não tem medida `custo` "
                "(possível invenção de custo)."
            )

    if payload_unit_ids:
        try:
            # Import tardio para evitar import-time coupling com routing.units.
            from src.copilot.cube.units import KNOWN_UNITS

            payload_unit_labels = {
                KNOWN_UNITS[uid].lower()
                for uid in payload_unit_ids
                if uid in KNOWN_UNITS
            }
            # **Só verifica palavras de unidade NÃO-AMBÍGUAS** — palavras como
            # "unidades" / "pares" / "tubos" / "conjunto" são polissémicas em
            # PT-PT (também significam "rows", "duos", "tubos de cola",
            # "conjunto de coisas"). Restringir a unidades **inequívocas**:
            # kg, m², m³, metros, litros, tambor, bidão, rolos, caixa,
            # horas, €/euro.
            _UNIDADES_INEQUIVOCAS = {
                "kg", "m²", "m³", "metros", "litros", "tambor", "bidão",
                "rolos", "caixa", "horas", "kwh", "gr", "lata",
            }
            forbidden_unit_labels = {
                name.lower() for uid, name in KNOWN_UNITS.items()
                if uid not in payload_unit_ids and name.lower() in _UNIDADES_INEQUIVOCAS
            }
            text_tokens_lower = set(re.findall(r"\w+", text_low))
            for forb in forbidden_unit_labels:
                if forb in text_tokens_lower and forb not in payload_unit_labels:
                    violations.append(
                        f"narrou unidade '{forb}' mas payload tem "
                        f"{sorted(payload_unit_labels)}"
                    )
                    break  # uma violação de unidade chega
        except ImportError:
            # Sem o mapping, salta o check de unidade (sem regredir o teste).
            pass

    # ──────────────────────────────────────────────────────────
    # 5. FRACAO (Q.96) — taxa não pode ser narrada como >100 %.
    # Se o payload tem uma medida FRACAO com valor >1 (denominador errado
    # = erro silencioso); se a narração apresenta "120%" / "150%" embora
    # o payload esteja correcto, igual. Defesa em profundidade.
    # ──────────────────────────────────────────────────────────
    try:
        from src.copilot.cube.measure_contract import is_fractional_measure

        # 5a. Payload tem taxa > 1?
        for row in result.data:
            for k, v in row.items():
                if (
                    isinstance(v, (int, float))
                    and not isinstance(v, bool)
                    and is_fractional_measure(str(k))
                    and v > 1.0001  # tolerância FP
                ):
                    violations.append(
                        f"medida FRACAO {k!r} tem valor {v} > 1.0 — "
                        "denominador errado, erro silencioso"
                    )

        # 5b. Narração com "X %" onde X > 100? Só apanha se o payload
        # tem uma medida fraccional (não interpretar outras % como erro).
        payload_has_fracao = False
        for row in result.data:
            for k in row:
                if is_fractional_measure(str(k)):
                    payload_has_fracao = True
                    break
            if payload_has_fracao:
                break
        if not payload_has_fracao:
            for m in result.query.get("measures", []) or []:
                if is_fractional_measure(str(m)):
                    payload_has_fracao = True
                    break

        if payload_has_fracao:
            _PCT_RE = re.compile(r"(\d{1,4}(?:[.,]\d+)?)\s*%")
            for m_pct in _PCT_RE.finditer(text):
                val_s = m_pct.group(1).replace(",", ".")
                try:
                    val = float(val_s)
                except ValueError:
                    continue
                if val > 100.0001:
                    violations.append(
                        f"narração apresenta {val}% (>100%) em medida "
                        "fraccional — taxa impossível"
                    )
                    break  # uma violação chega
    except ImportError:
        pass

    return (len(violations) == 0, violations)


def _extract_numbers_from_payload(result: CubeResult) -> list[float]:
    """Todos os números que aparecem em `data` (rows) OU no contexto da query.

    Inclui:
      1. Valores numéricos directos das rows (medidas, dimensões numéricas).
      2. Números embebidos em strings das rows — ex.: "Resina Lavesan EN 720"
         contém "720" que o LLM pode naturalmente repetir.
      3. Números embebidos nos `values` dos filtros do query — quando o
         filter é `equals "Resina Lavesan EN 720"` e o nome do material
         não vem em `dimensions`, o payload `data` não tem o nome, mas o
         LLM ainda pode (correctamente) repeti-lo da pergunta. O contexto
         é determinístico: vem do filter, não inventado.
    """
    numbers: list[float] = []

    def _harvest_from_str(s: str) -> None:
        for m in NUMBER_RE.findall(s):
            normalized = m.replace(",", ".")
            try:
                numbers.append(float(normalized))
            except ValueError:
                continue

    # Q.96 — para medidas FRACAO, acrescentar também a forma percentagem
    # (× 100). Payload tem 0.062, narração legítima escreve "6,2%" — sem
    # esta extensão, o guard rejeitava "6.2" como número fora do payload.
    try:
        from src.copilot.cube.measure_contract import is_fractional_measure
    except ImportError:
        is_fractional_measure = None  # type: ignore[assignment]

    # 1+2. Rows.
    for row in result.data:
        for k, v in row.items():
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                numbers.append(float(v))
                # Q.96: se a coluna é medida FRACAO, acrescentar % equivalente.
                if (
                    is_fractional_measure is not None
                    and is_fractional_measure(str(k))
                ):
                    numbers.append(float(v) * 100.0)
            elif isinstance(v, str):
                _harvest_from_str(v)

    # 3. Filters do query (contexto determinístico).
    for f in result.query.get("filters", []) or []:
        for v in f.get("values", []) or []:
            if isinstance(v, (int, float)):
                numbers.append(float(v))
            elif isinstance(v, str):
                _harvest_from_str(v)

    # Date range também conta — datas têm dígitos.
    for td in result.query.get("timeDimensions", []) or []:
        for v in td.get("dateRange", []) or []:
            if isinstance(v, str):
                _harvest_from_str(v)

    return numbers


def _extract_numbers_from_text(text: str) -> list[float]:
    out: list[float] = []
    for m in NUMBER_RE.findall(text):
        # Permitir ambos PT-PT (1,5) e PT-BR/US (1.5).
        normalized = m.replace(",", ".")
        try:
            out.append(float(normalized))
        except ValueError:
            continue
    return out


def _number_supported(value: float, payload_numbers: list[float]) -> bool:
    """Um número é suportado se aparece no payload OU é inteiro pequeno passthrough."""
    if (
        value == int(value)
        and abs(value) < INTEGER_PASSTHROUGH
    ):
        return True
    for ref in payload_numbers:
        if ref == 0.0:
            if abs(value) < 1e-9:
                return True
            continue
        if abs(value - ref) / max(abs(ref), 1e-9) <= GUARD_REL_TOL:
            return True
    return False


def guard_numbers(text: str, result: CubeResult) -> tuple[bool, list[float]]:
    """Confronta números do texto com os do payload.

    Devolve `(all_supported, unsupported)`. `all_supported` é True se cada
    número numérico do texto bate algo no payload (com tolerância) OU é
    um inteiro pequeno (contagem narrativa).
    """
    payload_numbers = _extract_numbers_from_payload(result)
    text_numbers = _extract_numbers_from_text(text)
    unsupported = [
        n for n in text_numbers if not _number_supported(n, payload_numbers)
    ]
    return (len(unsupported) == 0, unsupported)


async def narrate(
    result: CubeResult,
    ollama: LLMClient,
    model: str = DEFAULT_MODEL,
) -> str:
    """LLM gera texto PT-PT a partir do payload Cube (sem guard).

    Usa `format=None` (texto livre, não JSON) — o LLM responde em prosa.
    """
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload_json = json.dumps(
        {"data": result.data, "annotation": result.annotation},
        ensure_ascii=False,
        indent=2,
    )

    # Q.93.E.C.2.A — período canónico injectado proactivamente (defesa
    # primária contra alucinação temporal tipo q04 "Abril" quando era "Maio").
    # O guard reactivo (`guard_context`) continua a ser a 2ª linha.
    period_canonico = _format_canonical_period(result.query)
    period_block = (
        f"\n- PERÍODO: usa **{period_canonico}** EXACTAMENTE. Não inventes outro mês/ano."
        if period_canonico else ""
    )

    # Q.93.E.C.2.B — materiais do payload injectados proactivamente.
    # Reduz o falso-guard onde o LLM omite material para escapar à validação.
    payload_materials_list: list[str] = []
    for row in result.data:
        mat = row.get("consumo_material.material")
        if isinstance(mat, str) and mat.strip() and mat not in payload_materials_list:
            payload_materials_list.append(mat)
    for f in result.query.get("filters", []) or []:
        if "material" in str(f.get("member", "")).lower():
            for v in f.get("values", []) or []:
                if isinstance(v, str) and v.strip() and v not in payload_materials_list:
                    payload_materials_list.append(v)
    materials_block = (
        f"\n- MATERIAL: o resultado é sobre **{payload_materials_list[0]}**. "
        f"Menciona-o pelo nome no texto."
        if payload_materials_list else ""
    )

    user_prompt = (
        "Narra este resultado em PT-PT (2-4 frases), seguindo as regras "
        f"do system prompt:\n\n```json\n{payload_json}\n```"
        + (
            f"\n\n**INSTRUÇÕES DE CONTEXTO** (obrigatórias):"
            f"{period_block}{materials_block}"
            if (period_block or materials_block) else ""
        )
    )
    response = await ollama.chat(
        prompt=user_prompt,
        model=model,
        format=None,
        history=None,
        system_prompt=system_prompt,
    )
    # OllamaClient.chat devolve dict; o conteúdo está em "content" ou directo.
    if isinstance(response, dict):
        content = response.get("content") or response.get("response") or ""
        return str(content).strip()
    return str(response).strip()


async def narrate_with_guard(
    result: CubeResult,
    ollama: LLMClient,
    model: str = DEFAULT_MODEL,
) -> NarrationResult:
    """Narrate + guards (números + contexto). 1 retry se guard falhar; persistir
    a falha → devolve `ok=False` para o caller servir tabela crua + warning.

    Q.93.E.C.2 — retry coberto pelo brief: "Falha → rejeita e regenera 1x;
    se persiste → devolve tabela crua + aviso honesto."
    """
    for attempt in (1, 2):
        text = await narrate(result, ollama, model=model)
        ok_nums, unsupported = guard_numbers(text, result)
        ok_ctx, context_violations = guard_context(text, result)
        if ok_nums and ok_ctx:
            return NarrationResult(
                text=text,
                ok=True,
                unsupported_numbers=[],
                context_violations=[],
            )
        # 1ª falha: tenta uma vez mais (LLM não-determinístico). 2ª persistência:
        # devolve ok=False com os violators para o caller decidir.
        if attempt == 2:
            return NarrationResult(
                text="",
                ok=False,
                unsupported_numbers=unsupported,
                context_violations=context_violations,
            )
    # Inalcançável (loop sempre retorna acima), mas necessário para o type checker:
    return NarrationResult(
        text="",
        ok=False,
        unsupported_numbers=[],
        context_violations=[],
    )
