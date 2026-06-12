"""
ProdPlan ONE — Schedule-as-Code commits (Sprint K.1)
=====================================================

Each time the CPO scheduler produces a plan, the result is stored as an
immutable commit — very much like a git commit. The chain of commits
(`parent_id` self-FK) gives us:

- Full audit trail: when was this plan produced, by whom, with which
  `trust_index`, what KPIs?
- Diff view (K.3): compare `operations` between two commits.
- Timeline (K.2): expose the MAP-Elites representatives stored alongside
  the commit so a human can pick one to execute.

The SHA-256 is deterministic over the commit's content (kpis + delta +
operations + parent_sha) so duplicate plans are detected and any tamper
with the JSONB breaks the chain.

ORM model: `plan_schedule_commits`. Created by migration 012.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Index, Integer, String, Text, desc, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase
from src.shared.time import utc_now_naive

logger = logging.getLogger(__name__)


# =============================================================================
# ORM
# =============================================================================

class ScheduleCommit(TenantBase):
    """
    An immutable, hash-chained snapshot of a CPO schedule run.

    - `parent_id`: self-FK to the previous commit for this tenant (None on
      the very first commit — like git root).
    - `commit_sha256`: SHA-256 of a canonical JSON of {parent_sha256, kpis,
      operations, delta}. Same inputs → same hash → replay is verifiable.
    - `operations`: full list of scheduled ops (serializable dicts). Keeps
      the commit self-contained for diff + timeline without touching
      `production_schedule` rows.
    - `alternatives`: MAP-Elites representatives (for the Timeline endpoint).
    - `delta`: optional structured user-provided modification that led to
      this commit (POETIQ input); NULL for a plain re-plan.

    Sprint B CO1 — learning data points:
    - `rejected_alternatives`: each MAP-Elites alternative the operator
      explicitly DID NOT pick, with its KPIs, delta vs chosen, and reason.
    - `user_preference_signal`: who decided, when, on which weekday/hour —
      so temporal patterns can be learned.
    - `evidence_refs`: upstream events/state refs that fed this plan.
    - `scenarios_tested`: how many POETIQ iterations / MAP-Elites cells
      were considered before committing.
    """

    __tablename__ = "plan_schedule_commits"
    __table_args__ = (
        Index("idx_commits_tenant_created", "tenant_id", "created_at"),
        Index("idx_commits_sha", "commit_sha256"),
    )

    parent_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    commit_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    author: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")

    kpis: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    operations: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    delta: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    alternatives: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    cpo_meta: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Sprint B CO1 — learning fields
    rejected_alternatives: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list,
    )
    user_preference_signal: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    evidence_refs: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list,
    )
    scenarios_tested: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )

    # Q.116.D — snapshot dos inputs de boost que entraram neste commit.
    # Forma: {"<work_order_id>": {"client": int, "order": int, "boat": int,
    # "effective": int}}. Sem isto, replay perde reprodutibilidade quando
    # o boost manual muda entre commits.
    boost_inputs_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}",
    )

    trust_index: Mapped[float] = mapped_column(nullable=False, default=0.0)
    operations_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Q.62.D.4 — DRAFT | LIVE. CPO scheduler cria DRAFT por defeito;
    # approver promove via PUT /v1/plan/cpo/schedule/job/{job_id}/approve.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="DRAFT", server_default="DRAFT",
    )


# =============================================================================
# Hash computation
# =============================================================================

def compute_commit_hash(
    parent_sha256: Optional[str],
    kpis: Dict[str, Any],
    operations: List[Dict[str, Any]],
    delta: Optional[Dict[str, Any]] = None,
    boost_inputs_snapshot: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Deterministic SHA-256 of (parent, kpis, operations, delta, boost_inputs).

    Canonical JSON is produced via `sort_keys=True` + stable UTF-8 encode.

    Q.116.D: boost_inputs_snapshot enters the hash so that two commits with
    identical operations/KPIs but different boost inputs produce distinct
    SHAs — replay reproducibility holds when manual boost values change.

    Backward-compat: the new key is only added to the payload when the
    snapshot is non-empty. Pre-Q.116.D callsites (no snapshot, or empty
    dict) keep yielding the SAME hash as before, so historical commits
    survive verification.
    """
    payload: Dict[str, Any] = {
        "parent_sha256": parent_sha256,
        "kpis": kpis,
        "operations": operations,
        "delta": delta or {},
    }
    if boost_inputs_snapshot:
        payload["boost_inputs_snapshot"] = boost_inputs_snapshot
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Q.142.C — overrides manuais ativos (para o robô re-aplicar após cada solve)
# =============================================================================

# Cap defensivo: no cold-start (sem commit LIVE) a janela de overrides seria
# "desde sempre". Varremos só os N commits mais recentes (DESC+limit) e
# revertemos para ASC — chega para o last-wins sem percorrer o histórico todo.
_OVERRIDE_SCAN_LIMIT = 500

# Q.173.R — TTL default (dias) de um override manual sem aprovação LIVE.
# Override de `planning`/`manual_override.ttl_days`; <=0 desliga.
_OVERRIDE_TTL_DAYS_DEFAULT = 14


def _reduce_overrides(rows: List["ScheduleCommit"]) -> List[Dict[str, Any]]:
    """Last-wins por `operation_id` sobre commits de drag manual ordenados por
    `created_at` ascendente. Lógica pura (sem BD) → testável isoladamente.

    Cada commit traz um delta `tipo="manual_drag"`; um drag posterior do mesmo
    `operation_id` substitui o anterior. Devolve a lista dos overrides efetivos:
    `{operation_id, to_phase, to_ts, new_operator_id}`.
    """
    overrides: Dict[str, Dict[str, Any]] = {}
    for c in rows:
        d = dict(getattr(c, "delta", None) or {})
        op = d.get("operation_id")
        if not op:
            continue
        overrides[str(op)] = {
            "operation_id": str(op),
            "to_phase": d.get("to_phase"),
            "to_ts": d.get("to_ts"),
            "new_operator_id": d.get("new_operator_id"),
        }
    return list(overrides.values())


# =============================================================================
# Service
# =============================================================================

class CommitsService:
    """CRUD + creation hook for ScheduleCommit rows."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    # -------------------- Locking ------------------------------------ #

    async def lock_by_id(self, commit_id) -> Optional[ScheduleCommit]:
        """Q.171.A — SELECT ... FOR UPDATE para a aprovação DRAFT→LIVE.

        A aprovação era read-check-write SEM lock (TOCTOU): dois
        aprovadores em paralelo passavam ambos o check "already LIVE" e
        promoviam os dois (auditoria 2026-06-10). O lock de linha segura
        até ao commit da transacção — o segundo aprovador bloqueia no
        SELECT e revê o estado já LIVE → 409 honesto."""
        from sqlalchemy import select as _select

        stmt = (
            _select(ScheduleCommit)
            .where(
                ScheduleCommit.tenant_id == self.tenant_id,
                ScheduleCommit.id == commit_id,
            )
            .with_for_update()
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # -------------------- Create ------------------------------------- #

    async def create_from_schedule(
        self,
        *,
        schedule_result: Dict[str, Any],
        mapelites_representatives: Optional[List[Dict[str, Any]]] = None,
        delta: Optional[Dict[str, Any]] = None,
        author: str = "system",
        message: str = "",
        trust_index: float = 0.0,
        boost_inputs_snapshot: Optional[Dict[str, Any]] = None,
        validation_state: Any = None,
    ) -> ScheduleCommit:
        """Persist a commit from the output of `CPOv4Engine.schedule()`.

        Q.169.B — NENHUM schedule estruturalmente inválido é persistido:
        `validate_schedule` corre SEMPRE (stateless; com `validation_state`
        = FactoryState liga também cura/skills/pares) e erros levantam
        `ScheduleValidationError` — o caller decide (o robô mantém o último
        plano saudável; o endpoint devolve o erro honesto). O relatório vai
        para `cpo_meta.validation` (não entra no hash)."""
        from src.plan.cpo.schedule_validator import (
            ScheduleValidationError,
            validate_schedule,
        )

        operations = list(schedule_result.get("operations") or [])
        kpis = _extract_kpis(schedule_result)
        cpo_meta = dict(schedule_result.get("cpo_meta") or {})

        report = validate_schedule(schedule_result, state=validation_state)
        cpo_meta["validation"] = report.as_meta()
        if not report.ok:
            raise ScheduleValidationError(report)
        # Q.133.A.2 — preservar o sinal de plano degradado (safety_net) no commit
        # para o grid o poder rotular. NAO entra no hash determinístico
        # (compute_commit_hash usa só parent/kpis/operations/delta).
        cpo_meta.setdefault(
            "safety_net_triggered",
            bool(schedule_result.get("safety_net_triggered", False)),
        )

        # Parent lido à hora de PERSISTIR (não antes do solver) — de propósito
        # (triagem F4.E, achado "stale parent read" arquivado como decisão):
        # o head mais fresco mantém a cadeia de hash íntegra, e uma edição
        # manual feita DURANTE o solver não se perde — o reapply (Q.142/Q.148)
        # re-aplica os deltas manuais por cima do DRAFT novo.
        parent = await self.get_latest()
        parent_sha = parent.commit_sha256 if parent else None
        parent_id = parent.id if parent else None

        # Q.168.C — fecha o gap Q.116.D apanhado pela auditoria 2026-06-10:
        # o snapshot existia no schema do hash e na coluna mas NENHUM caller
        # o passava — a coluna ficava {} e dois commits com boosts manuais
        # diferentes davam o MESMO sha (replay sem reprodutibilidade).
        sha = compute_commit_hash(
            parent_sha256=parent_sha,
            kpis=kpis,
            operations=operations,
            delta=delta,
            boost_inputs_snapshot=boost_inputs_snapshot,
        )

        commit = ScheduleCommit(
            id=uuid4(),
            tenant_id=self.tenant_id,
            parent_id=parent_id,
            commit_sha256=sha,
            author=author,
            message=message or _auto_message(delta, cpo_meta),
            kpis=kpis,
            operations=operations,
            delta=delta or {},
            alternatives=list(mapelites_representatives or []),
            cpo_meta=cpo_meta,
            trust_index=float(trust_index),
            operations_count=len(operations),
            boost_inputs_snapshot=dict(boost_inputs_snapshot or {}),
        )
        self.session.add(commit)
        await self.session.flush()
        # Q.133.A.1 — persistir imediatamente. get_session() só faz commit() se
        # houver session.dirty/new/deleted; após o flush essas flags ficam
        # vazias, por isso o INSERT do ScheduleCommit era silenciosamente
        # descartado (tanto no endpoint sync como no worker async). Este commit
        # explícito torna a pós-condição clara: create_from_schedule entrega um
        # commit PERSISTIDO. O write-gate DRAFT→LIVE fica intacto (nasce DRAFT).
        await self.session.commit()
        logger.info(
            f"Created schedule commit {sha[:12]} parent={str(parent_sha or '-')[:12]} "
            f"ops={len(operations)} tenant={self.tenant_id}"
        )
        return commit

    # -------------------- Retrieve ----------------------------------- #

    async def get_by_sha(self, sha: str) -> Optional[ScheduleCommit]:
        stmt = select(ScheduleCommit).where(
            (ScheduleCommit.tenant_id == self.tenant_id)
            & (ScheduleCommit.commit_sha256 == sha)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sha_prefix(self, prefix: str) -> Optional[ScheduleCommit]:
        """Support short-hash lookups like `abc1234` (>=7 chars)."""
        if len(prefix) < 7:
            return None
        stmt = select(ScheduleCommit).where(
            (ScheduleCommit.tenant_id == self.tenant_id)
            & (ScheduleCommit.commit_sha256.like(f"{prefix}%"))
        ).limit(2)
        rows = list((await self.session.execute(stmt)).scalars().all())
        return rows[0] if len(rows) == 1 else None  # return only if exactly one match; >1 means ambiguous (limit(2) catches this)

    async def get_latest(self) -> Optional[ScheduleCommit]:
        stmt = (
            select(ScheduleCommit)
            .where(ScheduleCommit.tenant_id == self.tenant_id)
            .order_by(desc(ScheduleCommit.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def latest_live(self) -> Optional[ScheduleCommit]:
        """O commit LIVE (aprovado) mais recente, ou None. Baseline da janela
        de overrides manuais ativos (Q.142.C)."""
        stmt = (
            select(ScheduleCommit)
            .where(
                (ScheduleCommit.tenant_id == self.tenant_id)
                & (ScheduleCommit.status == "LIVE")
            )
            .order_by(desc(ScheduleCommit.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def promote_to_live(
        self,
        sha: str,
        *,
        approver_id: UUID,
        approver_role: str = "",
    ) -> Optional[ScheduleCommit]:
        """Q.157.F.2 — promove um commit DRAFT→LIVE (mesma lógica do botão
        "Aprovar plano" do /overall, ``cpo_routers/commits.py``).

        Escreve ``audit_change`` na sessão mas **NÃO** faz commit — o chamador
        controla a transacção (ex.: ``approve_decision`` promove o plano na mesma
        tx em que aprova a decisão). Idempotente: já-LIVE → devolve sem mexer.
        ``None`` se o commit não existe.
        """
        from src.governance.audit_service import audit_change

        commit = await self.get_by_sha(sha) or await self.get_by_sha_prefix(sha)
        if commit is None:
            return None
        prev_status = str(getattr(commit, "status", "DRAFT") or "DRAFT")
        if prev_status == "LIVE":
            return commit  # idempotente
        commit.status = "LIVE"
        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="schedule_commit",
            entity_id=commit.id,
            action="UPDATE",
            old_values={"status": prev_status},
            new_values={"status": "LIVE"},
            actor_id=approver_id,
            actor_role=approver_role,
            reason=f"Q.157.F approve decisão → promove plano {sha[:8]} DRAFT->LIVE",
        )
        await self.session.flush()
        return commit

    async def _override_ttl_days(self) -> int:
        """Q.173.R — TTL (dias) de um override manual sem aprovação LIVE.

        A janela de coleta só fechava com um commit LIVE — e com 203 DRAFT
        vs 3 LIVE (último 2026-06-02, auditoria 2026-06-11) um override
        nunca expirava e era re-aplicado eternamente. Config
        `planning`/`manual_override.ttl_days` (default 14; <=0 desliga o
        TTL). Best-effort: sem config → default.
        """
        try:
            from src.core.services.tenant_config_service import (
                TenantConfigService,
            )
            planning = await TenantConfigService(
                self.session, self.tenant_id,
            ).get_category("planning")
            raw = planning.get("manual_override.ttl_days")
            if raw not in (None, ""):
                return int(raw)
        except (ImportError, ValueError, TypeError, AttributeError) as exc:
            logger.debug("manual_override.ttl_days indisponível (%s)", exc)
        except SQLAlchemyError as exc:
            logger.debug("manual_override.ttl_days indisponível (%s)", exc)
        return _OVERRIDE_TTL_DAYS_DEFAULT

    async def active_manual_overrides(self) -> List[Dict[str, Any]]:
        """Q.142.C — overrides manuais ATIVOS para o robô re-aplicar após cada
        solve automático (Q.142.D). São os deltas `tipo="manual_drag"` de
        autoria HUMANA (`author != "system"`) criados DESDE o último commit LIVE
        — a aprovação DRAFT→LIVE "assa" os ajustes no plano aprovado e reinicia
        a janela. Last-wins por `operation_id`.

        Q.173.R — TTL adicional (default 14 dias): sem nenhum LIVE a janela
        era infinita e um override órfão re-aplicava-se para sempre.

        Os commits re-aplicados pelo próprio robô usam `author="system"` → ficam
        excluídos daqui (não se auto-coletam em loop).
        """
        from datetime import timedelta

        live = await self.latest_live()
        stmt = select(ScheduleCommit).where(
            (ScheduleCommit.tenant_id == self.tenant_id)
            & (ScheduleCommit.author != "system")
            & (ScheduleCommit.delta["tipo"].astext == "manual_drag")
        )
        if live is not None:
            stmt = stmt.where(ScheduleCommit.created_at > live.created_at)
        ttl_days = await self._override_ttl_days()
        if ttl_days > 0:
            cutoff = utc_now_naive() - timedelta(days=ttl_days)
            stmt = stmt.where(ScheduleCommit.created_at > cutoff)
        # Safety-valve: aos N mais recentes (DESC+limit), depois ASC p/ last-wins.
        stmt = stmt.order_by(desc(ScheduleCommit.created_at)).limit(_OVERRIDE_SCAN_LIMIT)
        rows = list((await self.session.execute(stmt)).scalars().all())
        rows.reverse()  # ASC → _reduce_overrides faz o last-wins corretamente
        return _reduce_overrides(rows)

    async def list_commits(
        self, limit: int = 50, *, healthy_only: bool = False
    ) -> List[ScheduleCommit]:
        """Lista commits (mais recentes primeiro).

        Q.162.B — `healthy_only=True` salta os planos marcados
        `cpo_meta.degenerate=true` (cobertura colapsou face ao scope). É o que o
        /overall usa para escolher o plano a MOSTRAR: um plano degenerado nunca
        vira o "plano atual" só por ser o mais recente — mostra-se o último
        saudável. O default (False) preserva a listagem completa (histórico).
        """
        stmt = select(ScheduleCommit).where(
            ScheduleCommit.tenant_id == self.tenant_id
        )
        if healthy_only:
            _degen = ScheduleCommit.cpo_meta["degenerate"].astext
            stmt = stmt.where(or_(_degen.is_(None), _degen != "true"))
        stmt = stmt.order_by(desc(ScheduleCommit.created_at)).limit(
            max(1, min(limit, 500))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -------------------- Diff --------------------------------------- #

    async def diff(
        self,
        from_sha: str,
        to_sha: str,
    ) -> Dict[str, Any]:
        """Compare the operations of two commits. Returns the delta dict."""
        a = await self._resolve_commit(from_sha)
        b = await self._resolve_commit(to_sha)
        if a is None or b is None:
            raise ValueError(
                f"commit_not_found: from={from_sha} a={a is not None} "
                f"to={to_sha} b={b is not None}"
            )
        return compute_operations_diff(a, b)

    async def _resolve_commit(self, sha: str) -> Optional[ScheduleCommit]:
        return await self.get_by_sha(sha) or await self.get_by_sha_prefix(sha)

    # -------------------- Serialisation ----------------------------- #

    @staticmethod
    def to_dict(commit: ScheduleCommit, *, include_operations: bool = False) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": str(commit.id),
            "tenant_id": str(commit.tenant_id),
            "parent_id": str(commit.parent_id) if commit.parent_id else None,
            "commit_sha256": commit.commit_sha256,
            "short_sha": commit.commit_sha256[:12],
            "author": commit.author,
            "message": commit.message,
            "kpis": commit.kpis or {},
            "delta": commit.delta or {},
            "alternatives": commit.alternatives or [],
            "cpo_meta": commit.cpo_meta or {},
            # Sprint B CO1 — learning fields surfaced for the Timeline UI
            "rejected_alternatives": commit.rejected_alternatives or [],
            "user_preference_signal": commit.user_preference_signal or {},
            "evidence_refs": commit.evidence_refs or [],
            "scenarios_tested": commit.scenarios_tested or 0,
            "trust_index": commit.trust_index,
            "operations_count": commit.operations_count,
            # Q.133.A.2 — estado do plano (DRAFT|LIVE) + sinal de degradação, para
            # o grid rotular honestamente um plano não-aprovado/degradado.
            "status": getattr(commit, "status", "DRAFT") or "DRAFT",
            "safety_net_triggered": bool((commit.cpo_meta or {}).get("safety_net_triggered", False)),
            "created_at": commit.created_at.isoformat() if commit.created_at else None,
        }
        if include_operations:
            out["operations"] = commit.operations or []
        return out

    # -------------------- CO1 — learning decisions ------------------- #

    async def record_decision(
        self,
        *,
        commit_id: UUID,
        chosen_alt_idx: Optional[int],
        rejected_alt_idxs: List[int],
        decided_by: str,
        decided_at: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> ScheduleCommit:
        """Record the operator's choice among this commit's alternatives.

        Each rejected alternative's KPIs are captured together with its
        delta vs the chosen one — that's the data the four learning
        layers (PreferenceRuleDetector, AdaptiveFitnessWeights, DPO,
        ABLkit) will consume. The chosen_alt can be None when the
        operator accepts the primary commit without ranking alternatives
        (still useful signal: rejected_alt_idxs tells us what they
        looked at and declined).

        Raises `ValueError` on out-of-range indices so callers can fail
        loudly instead of silently dropping invalid decisions.
        """
        commit = await self.session.get(ScheduleCommit, commit_id)
        if commit is None or commit.tenant_id != self.tenant_id:
            raise ValueError(f"commit_not_found: {commit_id}")

        alternatives = list(commit.alternatives or [])
        n_alts = len(alternatives)

        if chosen_alt_idx is not None and not (0 <= chosen_alt_idx < n_alts):
            raise ValueError(
                f"chosen_alt_idx={chosen_alt_idx} out of range [0, {n_alts})"
            )
        for idx in rejected_alt_idxs:
            if not (0 <= idx < n_alts):
                raise ValueError(
                    f"rejected_alt_idx={idx} out of range [0, {n_alts})"
                )
        if chosen_alt_idx is not None and chosen_alt_idx in rejected_alt_idxs:
            raise ValueError(
                f"chosen_alt_idx={chosen_alt_idx} cannot appear in rejected_alt_idxs",
            )

        decided_at = decided_at or utc_now_naive()
        chosen = alternatives[chosen_alt_idx] if chosen_alt_idx is not None else None

        rejected_records = [
            _build_rejected_record(
                alt=alternatives[idx],
                chosen=chosen,
                reason=reason,
                rejected_at=decided_at,
                alt_idx=idx,
            )
            for idx in rejected_alt_idxs
        ]

        commit.rejected_alternatives = rejected_records
        commit.user_preference_signal = {
            "chose_alt_idx": chosen_alt_idx,
            "rejected_alt_idxs": list(rejected_alt_idxs),
            "decided_by": decided_by,
            "decided_at": decided_at.isoformat(),
            # Temporal features so Camada 1 can spot weekday/hour patterns
            "weekday": decided_at.isoweekday(),
            "hour": decided_at.hour,
            "reason": reason,
        }
        await self.session.flush()
        logger.info(
            "Decision recorded for commit %s: chosen=%s rejected=%s by %s",
            commit.commit_sha256[:12],
            chosen_alt_idx,
            rejected_alt_idxs,
            decided_by,
        )
        return commit


# =============================================================================
# Diff computation (self-contained, unit-tested)
# =============================================================================

def compute_operations_diff(
    a: ScheduleCommit,
    b: ScheduleCommit,
) -> Dict[str, Any]:
    """
    Compare two commits' `operations` lists, indexed by `operation_id`.

    Output:
        {
          "from_sha": ..., "to_sha": ...,
          "added":    [op],          # in b not in a
          "removed":  [op],          # in a not in b
          "changed":  [{op_id, field, before, after}],
          "kpi_deltas": {kpi: (from, to, delta)},
        }
    """
    by_id_a = {op.get("operation_id"): op for op in (a.operations or [])}
    by_id_b = {op.get("operation_id"): op for op in (b.operations or [])}

    added_ids = set(by_id_b) - set(by_id_a)
    removed_ids = set(by_id_a) - set(by_id_b)

    changed: List[Dict[str, Any]] = []
    for op_id in sorted(set(by_id_a) & set(by_id_b)):
        if op_id is None:
            continue
        op_a, op_b = by_id_a[op_id], by_id_b[op_id]
        for field in ("start_time", "end_time", "machine_id", "mold_id", "workers"):
            if op_a.get(field) != op_b.get(field):
                changed.append({
                    "operation_id": op_id,
                    "field": field,
                    "before": op_a.get(field),
                    "after": op_b.get(field),
                })

    kpi_deltas: Dict[str, Any] = {}
    for key in set(a.kpis or {}).union(b.kpis or {}):
        va = (a.kpis or {}).get(key)
        vb = (b.kpis or {}).get(key)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            kpi_deltas[key] = {"from": va, "to": vb, "delta": round(vb - va, 4)}
        elif va != vb:
            kpi_deltas[key] = {"from": va, "to": vb, "delta": None}

    return {
        "from_sha": a.commit_sha256,
        "to_sha": b.commit_sha256,
        "added": [by_id_b[op_id] for op_id in sorted(added_ids)],
        "removed": [by_id_a[op_id] for op_id in sorted(removed_ids)],
        "changed": changed,
        "kpi_deltas": kpi_deltas,
        "summary": {
            "added_count": len(added_ids),
            "removed_count": len(removed_ids),
            "changed_count": len(changed),
        },
    }


# =============================================================================
# Helpers
# =============================================================================

def _extract_kpis(schedule_result: Dict[str, Any]) -> Dict[str, Any]:
    """Pull a concise KPI subset from the scheduler output for the commit."""
    return {
        "makespan_hours": schedule_result.get("makespan_hours", 0.0),
        "total_tardiness_hours": schedule_result.get("total_tardiness_hours", 0.0),
        "num_late_orders": schedule_result.get("num_late_orders", 0),
        # Q.153.A2 — dívida herdada vs atraso novo/evitável (para o /overall
        # rotular honestamente "X já vencidos à entrada" vs "Y atrasados pelo plano").
        "num_already_overdue": schedule_result.get("num_already_overdue", 0),
        "num_newly_late": schedule_result.get("num_newly_late", 0),
        "tardiness_beyond_today_h": schedule_result.get("tardiness_beyond_today_h", 0.0),
        "setups": schedule_result.get("setups", 0),
        "throughput_eur_day": schedule_result.get("throughput_eur_day", 0.0),
        "throughput_eur_total": schedule_result.get("throughput_eur_total", 0.0),
        "avg_utilization": schedule_result.get("avg_utilization", 0.0),
        "solve_time_sec": schedule_result.get("solve_time_sec", 0.0),
        "status": schedule_result.get("status", "unknown"),
        "safety_net_triggered": bool(schedule_result.get("safety_net_triggered", False)),
        # Q.174.F5 — plano parcial DECLARADO: nº de ops/ordens que ficaram
        # fora por recurso em falta (detalhe em cpo_meta.unplannable). Entram
        # no hash — só commits novos (a verificação histórica fica intacta:
        # o hash de cada commit é o calculado na criação).
        "unplannable_count": len(schedule_result.get("unplannable") or []),
        "viable": not (schedule_result.get("unplannable") or []),
        # Q.174.F6 — ordens com risco de material anotado (constraint soft).
        "orders_material_risk": int(
            schedule_result.get("orders_material_risk") or 0
        ),
    }


def _build_rejected_record(
    *,
    alt: Dict[str, Any],
    chosen: Optional[Dict[str, Any]],
    reason: Optional[str],
    rejected_at: datetime,
    alt_idx: int,
) -> Dict[str, Any]:
    """Serialize one rejected MAP-Elites alternative with its KPIs and
    the delta vs the chosen plan. This is the per-alternative payload
    the four learning layers (PreferenceRuleDetector, AdaptiveFitness-
    Weights, DPO, ABLkit) consume.

    `alt` is the alternative dict as stored in `commit.alternatives`.
    Shape is heterogeneous across MAP-Elites sources, so we read KPIs
    defensively via `.get(...)` and fall back to `{}` when absent.
    """
    alt_kpis: Dict[str, Any] = {}
    if isinstance(alt, dict):
        raw_kpis = alt.get("kpis") if isinstance(alt.get("kpis"), dict) else alt
        if isinstance(raw_kpis, dict):
            for k in (
                "makespan_hours", "total_tardiness_hours", "num_late_orders",
                "setups", "throughput_eur_day", "throughput_eur_total",
                "avg_utilization", "quality_risk_score", "idle_ratio",
            ):
                if k in raw_kpis:
                    alt_kpis[k] = raw_kpis[k]

    delta_vs_chosen: Dict[str, Any] = {}
    if chosen and isinstance(chosen, dict):
        chosen_kpis = chosen.get("kpis") if isinstance(chosen.get("kpis"), dict) else chosen
        if isinstance(chosen_kpis, dict):
            for k, v in alt_kpis.items():
                cv = chosen_kpis.get(k)
                if isinstance(v, (int, float)) and isinstance(cv, (int, float)):
                    delta_vs_chosen[k] = round(v - cv, 4)

    return {
        "alt_idx": alt_idx,
        "kpis": alt_kpis,
        "delta_vs_chosen": delta_vs_chosen,
        "mapelites_cell": alt.get("mapelites_cell") if isinstance(alt, dict) else None,
        "rejection_reason": reason,
        "rejected_at": rejected_at.isoformat(),
    }


def _auto_message(delta: Optional[Dict[str, Any]], cpo_meta: Dict[str, Any]) -> str:
    if delta:
        entity = delta.get("entity_type") or "custom"
        return f"Scheduled with {entity} delta"
    gen = cpo_meta.get("generations_run")
    if gen:
        return f"Scheduled ({gen} generations, best_fitness={cpo_meta.get('best_fitness')})"
    return "Scheduled"
