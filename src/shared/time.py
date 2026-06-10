"""Tempo canónico do nelinho (Q.168.B).

Política: timestamps novos são SEMPRE tz-aware UTC. `datetime.utcnow()`
está banido (ruff DTZ003): devolve naive, que (a) escrito numa coluna
``DateTime(timezone=True)`` entra sem offset explícito e (b) comparado com
um datetime aware lança ``TypeError`` — a classe de bugs do Q.130.U que a
auditoria 2026-06-10 voltou a encontrar em ~25 sítios.

``utc_now_naive()`` existe SÓ para os pontos que têm de continuar naive:
colunas legacy ``DateTime`` sem timezone (migração própria registada no
backlog da campanha) e o domínio de planeamento CPO (naive-consistente com
as datas-texto do mirror ERP até à migração coordenada em F2). É o MESMO
instante UTC, sem tzinfo — nunca hora local.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

__all__ = ["utc_now", "utc_now_naive", "local_today", "local_now_naive"]


def utc_now() -> datetime:
    """Agora, em UTC, tz-aware — o default para tudo."""
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """Agora, em UTC, naive — SÓ colunas legacy sem tz e domínio CPO (F2)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_now_naive() -> datetime:
    """Agora, em hora LOCAL da fábrica, naive (Q.171.E).

    Para comparar/anexar a timestamps do ERP, que são local-naive
    ('2024-09-19T08:16:00' em `factory_raw`): janelas de recência,
    feasibility vs calendário fabril, horizontes de planeamento. Usar
    `utc_now_naive()` aqui erraria 1h no verão (DST Lisboa). O servidor
    corre on-prem na NELO — hora local do processo É a hora da fábrica."""
    return datetime.now()  # noqa: DTZ005 — hora local É a intenção (vs ERP)


def local_today() -> date:
    """Data de NEGÓCIO da fábrica (dia local da NELO, Europe/Lisbon).

    `date.today()` está banido em chamadas diretas (ruff DTZ011) porque o
    leitor não sabe se o autor quis o dia UTC ou o dia da fábrica. Este
    helper torna a intenção explícita: KPIs diários, faturação do dia,
    backlog de expedição — tudo conta em dia LOCAL, porque o servidor corre
    on-prem na NELO e os relatórios falam a língua da produção."""
    return date.today()  # noqa: DTZ011 — dia local É a intenção (on-prem)
