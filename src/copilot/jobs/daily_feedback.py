"""
ProdPlan ONE - Daily Feedback Job
==================================

Gera feedback diário automático do COPILOT.
"""

import logging
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.schemas import DailyFeedbackResponse, DailyFeedbackBullet, Citation
from src.copilot.service import CopilotService

logger = logging.getLogger(__name__)


async def generate_daily_feedback(
    session: AsyncSession,
    tenant_id: UUID,
    target_date: str,
) -> DailyFeedbackResponse:
    """
    Gera feedback diário do COPILOT.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        target_date: Data no formato YYYY-MM-DD
    
    Returns:
        DailyFeedbackResponse com bullets de feedback
    """
    try:
        # Parse date
        if isinstance(target_date, str):
            feedback_date = date.fromisoformat(target_date)
        else:
            feedback_date = target_date
        
        # Criar serviço COPILOT
        # Usar system user para jobs (UUID zero e role admin_platform)
        system_actor_id = UUID('00000000-0000-0000-0000-000000000000')
        system_actor_role = 'admin_platform'
        service = CopilotService(session, tenant_id, system_actor_id, system_actor_role)
        
        # Gerar feedback usando o serviço
        # Por agora, retornamos um feedback básico
        # TODO: Implementar lógica completa de análise diária
        
        bullets: list[DailyFeedbackBullet] = []
        
        # Bullet 1: Resumo geral
        bullets.append(
            DailyFeedbackBullet(
                severity="INFO",
                title="Análise Diária",
                text=f"Análise do dia {feedback_date.isoformat()}. Sistema operacional.",
                citations=[],
                suggested_runbooks=[],
                suggested_actions=[],
            )
        )
        
        # Bullet 2: KPIs principais
        bullets.append(
            DailyFeedbackBullet(
                severity="INFO",
                title="KPIs Principais",
                text="Verifique o dashboard para métricas atualizadas de OEE, qualidade e produção.",
                citations=[],
                suggested_runbooks=[],
                suggested_actions=[],
            )
        )
        
        # Bullet 3: Recomendações
        bullets.append(
            DailyFeedbackBullet(
                severity="INFO",
                title="Recomendações",
                text="Consulte a secção de recomendações para sugestões de melhoria.",
                citations=[],
                suggested_runbooks=[],
                suggested_actions=[],
            )
        )
        
        # Garantir que temos pelo menos 3 bullets (requisito do schema)
        while len(bullets) < 3:
            bullets.append(
                DailyFeedbackBullet(
                    severity="INFO",
                    title="Feedback Adicional",
                    text="Análise adicional disponível no dashboard.",
                    citations=[],
                    suggested_runbooks=[],
                    suggested_actions=[],
                )
            )
        
        now = datetime.utcnow().isoformat()
        
        return DailyFeedbackResponse(
            date=feedback_date.isoformat(),
            bullets=bullets[:7],  # Máximo 7 bullets
            generated_at=now,
            last_updated=now,
        )
        
    except Exception as e:
        logger.error(f"Erro ao gerar daily feedback: {e}", exc_info=True)
        
        # Retornar feedback de erro
        return DailyFeedbackResponse(
            date=target_date if isinstance(target_date, str) else target_date.isoformat(),
            bullets=[
                DailyFeedbackBullet(
                    severity="WARN",
                    title="Erro ao Gerar Feedback",
                    text=f"Não foi possível gerar feedback completo: {str(e)}",
                    citations=[],
                    suggested_runbooks=[],
                    suggested_actions=[],
                ),
                DailyFeedbackBullet(
                    severity="INFO",
                    title="Sistema Operacional",
                    text="O sistema está operacional. Tente novamente mais tarde.",
                    citations=[],
                    suggested_runbooks=[],
                    suggested_actions=[],
                ),
                DailyFeedbackBullet(
                    severity="INFO",
                    title="Contacte Suporte",
                    text="Se o problema persistir, contacte o suporte técnico.",
                    citations=[],
                    suggested_runbooks=[],
                    suggested_actions=[],
                ),
            ],
            generated_at=datetime.utcnow().isoformat(),
            last_updated=datetime.utcnow().isoformat(),
        )
