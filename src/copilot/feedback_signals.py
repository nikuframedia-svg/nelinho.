"""Q.32.C.1 — agregação do feedback 👍/👎 do copiloto, por intent.

O endpoint `/feedback/user` grava cada 👍/👎 em `copilot_user_feedback`,
agora com `suggestion_id` (Q.32.B.2). Este serviço lê essas linhas, faz
JOIN à `copilot_suggestion` para descobrir o `intent` da resposta avaliada,
e devolve a taxa de aprovação por intent.

É **este** o sinal que o copiloto passa a usar para melhorar ao longo do
tempo: o `_render_prompt` injecta-o no prompt (Q.32.C.2) e o
`daily_feedback` resume-o para o humano (Q.32.C.3). Determinístico, sem
LLM, sem retrain — pura agregação SQL.

Feedback sem `suggestion_id` (linhas antigas, anteriores a Q.32.B.2) não
pode ser atribuído a um intent e fica de fora — o JOIN é inner.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.models import CopilotSuggestion, CopilotUserFeedback

logger = logging.getLogger(__name__)

# Abaixo deste nº de avaliações o sinal é ruído — não vale a pena
# injectá-lo no prompt nem alarmar o gestor.
MIN_SAMPLES_FOR_SIGNAL = 3


@dataclass
class IntentFeedback:
    """Contagem de 👍/👎 para um intent do copiloto."""

    intent: str
    up: int = 0
    down: int = 0

    @property
    def total(self) -> int:
        return self.up + self.down

    @property
    def up_pct(self) -> float:
        return round(100.0 * self.up / self.total, 1) if self.total else 0.0

    @property
    def is_significant(self) -> bool:
        return self.total >= MIN_SAMPLES_FOR_SIGNAL

    def to_dict(self) -> Dict[str, object]:
        return {
            "intent": self.intent,
            "up": self.up,
            "down": self.down,
            "total": self.total,
            "up_pct": self.up_pct,
        }


class FeedbackSignalsService:
    """Agregador read-only do feedback do copiloto. Nunca escreve."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def by_intent(self, *, window_days: int = 90) -> Dict[str, IntentFeedback]:
        """Taxa de aprovação por intent na janela. Chave = intent."""
        # `copilot_user_feedback.created_at` é TIMESTAMP WITHOUT TIME ZONE —
        # naive-UTC, como o resto do código pós-Q.32.A.1.
        since = (
            datetime.now(timezone.utc) - timedelta(days=max(1, window_days))
        ).replace(tzinfo=None)

        stmt = (
            select(
                CopilotUserFeedback.thumb,
                CopilotSuggestion.response_json,
            )
            .join(
                CopilotSuggestion,
                CopilotSuggestion.id == CopilotUserFeedback.suggestion_id,
            )
            .where(
                and_(
                    CopilotUserFeedback.tenant_id == self.tenant_id,
                    CopilotUserFeedback.created_at >= since,
                )
            )
        )
        rows = (await self.session.execute(stmt)).all()

        out: Dict[str, IntentFeedback] = {}
        for thumb, response_json in rows:
            intent = "generic"
            if isinstance(response_json, dict):
                intent = str(response_json.get("intent") or "generic")
            bucket = out.setdefault(intent, IntentFeedback(intent=intent))
            if thumb == "up":
                bucket.up += 1
            elif thumb == "down":
                bucket.down += 1
        return out

    async def overall(self, *, window_days: int = 7) -> IntentFeedback:
        """Agregado de todos os intents numa janela curta (para o daily-feedback)."""
        by_intent = await self.by_intent(window_days=window_days)
        total = IntentFeedback(intent="__all__")
        for fb in by_intent.values():
            total.up += fb.up
            total.down += fb.down
        return total
