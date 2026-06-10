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

__all__ = ["utc_now", "utc_now_naive", "local_today"]


def utc_now() -> datetime:
    """Agora, em UTC, tz-aware — o default para tudo."""
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """Agora, em UTC, naive — SÓ colunas legacy sem tz e domínio CPO (F2)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_today() -> date:
    """Data de NEGÓCIO da fábrica (dia local da NELO, Europe/Lisbon).

    `date.today()` está banido em chamadas diretas (ruff DTZ011) porque o
    leitor não sabe se o autor quis o dia UTC ou o dia da fábrica. Este
    helper torna a intenção explícita: KPIs diários, faturação do dia,
    backlog de expedição — tudo conta em dia LOCAL, porque o servidor corre
    on-prem na NELO e os relatórios falam a língua da produção."""
    return date.today()  # noqa: DTZ011 — dia local É a intenção (on-prem)
