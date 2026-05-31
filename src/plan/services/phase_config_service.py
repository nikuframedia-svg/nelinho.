"""Q.135.F3.2 — PhaseConfigService: get/upsert de overrides de fase.

Validações Spelke (lança ValueError → 400):
  * allowed_worker_ids ⊆ skill_matrix[phase_id]          (axioma 5)
  * 1 ≤ num_stations_override ≤ _N_MAX                    (axioma 1)
  * Laminagem PAIR_PREFERRED → team_size_override não pode ser < 2  (axioma 4)

O boundary de commit fica na dependency get_session (FastAPI); este service
nunca chama session.commit().
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.models.phase_config import PhaseConfig

logger = logging.getLogger(__name__)

# teto de estações — alinhado com phase_workcenters._N_MAX = 40
_N_MAX = 40

# Fases onde team_size >= 2 é obrigatório (PAIR_PREFERRED no state.py)
# Usamos normalize_phase_code para a comparação
_PAIR_MIN_2_PHASES = ("LAMINAGEM",)


def _norm(s: str) -> str:
    """Normaliza nome de fase para comparação com PAIR_MIN_2_PHASES."""
    import unicodedata
    decomposed = unicodedata.normalize("NFKD", str(s))
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    result = ascii_only.strip().upper()
    for ch in (" ", "-", "/", "."):
        result = result.replace(ch, "_")
    while "__" in result:
        result = result.replace("__", "_")
    return result.strip("_")


def _requires_pair(phase_id: str, phase_name: str = "") -> bool:
    """Devolve True se a fase exige team_size >= 2 (LAMINAGEM standard)."""
    n_pid = _norm(phase_id)
    n_pnm = _norm(phase_name)
    return any(p in n_pid or p in n_pnm for p in _PAIR_MIN_2_PHASES)


class PhaseConfigService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def get(self, phase_id: str) -> Optional[PhaseConfig]:
        """Devolve o override de fase ou None se não existir."""
        stmt = select(PhaseConfig).where(
            PhaseConfig.tenant_id == self.tenant_id,
            PhaseConfig.phase_id == phase_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        phase_id: str,
        *,
        team_size_override: Optional[int] = None,
        num_stations_override: Optional[int] = None,
        allowed_worker_ids: Optional[List[str]] = None,
        note: Optional[str] = None,
        actor: Optional[UUID] = None,
        # Para validação Spelke: skill_matrix da fase
        known_workers: Optional[Set[str]] = None,
        phase_name: str = "",
    ) -> PhaseConfig:
        """Cria ou actualiza o override de fase.

        known_workers: conjunto de funcionario_id com skill nesta fase
        (skill_matrix[phase_id]). Se None, a validação allowed_worker_ids é
        ignorada (best-effort para testes sem DB completo).

        Lança ValueError se violar axiomas Spelke (→ HTTP 400).
        """
        # --- validações Spelke ---
        if num_stations_override is not None:
            if not (1 <= num_stations_override <= _N_MAX):
                raise ValueError(
                    f"num_stations_override={num_stations_override} fora de [1, {_N_MAX}] "
                    "(axioma capacity≥1)"
                )

        if team_size_override is not None:
            if team_size_override < 1:
                raise ValueError(
                    f"team_size_override={team_size_override} < 1 (inválido)"
                )
            if _requires_pair(phase_id, phase_name) and team_size_override < 2:
                raise ValueError(
                    f"Fase {phase_id!r} (Laminagem) exige team_size >= 2 "
                    "— PAIR_PREFERRED (axioma 4)"
                )

        if allowed_worker_ids is not None and known_workers is not None:
            outside = set(allowed_worker_ids) - known_workers
            if outside:
                raise ValueError(
                    f"allowed_worker_ids contém operadores sem skill na fase "
                    f"{phase_id!r}: {sorted(outside)} (axioma 5)"
                )

        existing = await self.get(phase_id)
        now = datetime.now(timezone.utc)

        if existing is None:
            row = PhaseConfig(
                id=uuid4(),
                tenant_id=self.tenant_id,
                phase_id=phase_id,
                team_size_override=team_size_override,
                num_stations_override=num_stations_override,
                allowed_worker_ids=allowed_worker_ids,
                note=note,
                updated_by=actor,
                updated_at=now,
            )
            self.session.add(row)
            action = "INSERT"
            old_values = None
            new_values = {
                "phase_id": phase_id,
                "team_size_override": team_size_override,
                "num_stations_override": num_stations_override,
                "allowed_worker_ids": allowed_worker_ids,
                "note": note,
            }
        else:
            old_values = {
                "team_size_override": existing.team_size_override,
                "num_stations_override": existing.num_stations_override,
                "allowed_worker_ids": existing.allowed_worker_ids,
                "note": existing.note,
            }
            existing.team_size_override = team_size_override
            existing.num_stations_override = num_stations_override
            existing.allowed_worker_ids = allowed_worker_ids
            existing.note = note
            existing.updated_by = actor
            existing.updated_at = now
            row = existing
            action = "UPDATE"
            new_values = {
                "team_size_override": team_size_override,
                "num_stations_override": num_stations_override,
                "allowed_worker_ids": allowed_worker_ids,
                "note": note,
            }

        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="phase_config",
            entity_id=row.id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            actor_id=actor,
        )
        await self.session.flush()
        return row
