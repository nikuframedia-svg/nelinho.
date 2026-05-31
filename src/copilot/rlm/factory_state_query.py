"""
ProdPlan ONE — FactoryStateQuery (Sprint F.4)
===============================================

Typed sub-query surface the RLM agent hands to the LLM. The LLM never
gets the full ``FactoryState`` blob (20–200k tokens; doesn't fit in
the prompt). Instead it picks one of the small, named queries below,
we execute it, and we inject the ≤100-token result back into the
conversation.

Why a thin wrapper over SemanticQueries?

* **Budget control** — each method trims its output to a few rows so
  the agent loop stays within the context budget.
* **Contract stability** — the LLM's system prompt lists these names
  verbatim. Changes to SemanticQueries shapes can't leak into the
  prompt without a deliberate update here.
* **Test hermeticity** — tests pass a stub `queries=` object that
  implements whichever sub-queries the scenario under test hits; no
  DB / ingestion-engine fixture needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


# Every query returns a small dict ready to inject into the prompt.
QueryResult = Dict[str, Any]


# ─── Typed result dataclasses (Q.115.I) ─────────────────────────────────────

@dataclass
class PhaseRisk:
    phase: str
    p_defect: Optional[float]
    sample_n: int


@dataclass
class BoatRiskProfile:
    boat_id: str
    top_phases_at_risk: List[PhaseRisk] = field(default_factory=list)
    avg_quality_score: Optional[float] = None
    completed_ops_30d: Optional[int] = None
    note: Optional[str] = None


@dataclass
class AffinitySignal:
    operator_name: str
    phase_name: str
    score: float
    sample_count: int


@dataclass
class RunbookEntry:
    id: str
    steps_md_truncated: str
    confidence: float
    approved: bool


@dataclass
class RunbookLookupResult:
    error_code: str
    runbooks: List[RunbookEntry] = field(default_factory=list)
    total_history_count: int = 0
    note: Optional[str] = None


@dataclass
class CostBaseline:
    daily_target_eur: Optional[float] = None
    current_baseline_margin_eur: Optional[float] = None
    top_revenue_clients_30d: List[Dict[str, Any]] = field(default_factory=list)
    note: Optional[str] = None


@dataclass
class FactoryStateQuery:
    """Typed sub-queries the RLM agent can call.

    ``state`` is the :class:`FactoryState` snapshot (for
    ``preference_rules``, mould + skill lookups). ``queries`` is the
    semantic layer (``SemanticQueriesInMemory`` or a test stub). Both
    are optional — each method degrades to a clear "not available"
    dict so the LLM can decide to ask something else.
    """

    state: Optional[Any] = None
    queries: Optional[Any] = None

    # ─── Introspection for the system prompt ─────────────────────────

    @classmethod
    def describe(cls) -> List[Dict[str, str]]:
        """Return a catalogue of `(name, description)` pairs so the LLM
        knows exactly which queries exist without reading Python."""
        return [
            {"name": "wip", "description":
                "Work-in-progress snapshot: open_orders_count + top 5 orders."},
            {"name": "bottlenecks", "description":
                "Phases with the deepest queue (top 5, score 0-100)."},
            {"name": "open_orders", "description":
                "Total open orders + top 5 by due date."},
            {"name": "backlog", "description":
                "Aggregate backlog hours + top 5 orders."},
            {"name": "skills_risk", "description":
                "Phases where <3 workers have the skill; flags critical gaps."},
            {"name": "quality", "description":
                "Total errors + top 5 error types."},
            {"name": "lead_time", "description":
                "Average lead time (days) over the window."},
            {"name": "mold_conflicts", "description":
                "Moulds scheduled on >1 order in the horizon."},
            {"name": "preference_rules", "description":
                "Camada 1 confirmed rules currently enforced by the GA."},
            {"name": "overview", "description":
                "One-shot global summary (WIP + bottlenecks + quality)."},
            {"name": "causal_query", "description":
                "Numerical kernel — exact magnitudes for hypothetical scenarios. "
                "Use BEFORE answering 'what if' / 'se' / 'caso' questions with "
                "numbers. Params: target (DAG node id), do (dict {node: value}), "
                "observe (dict). Returns delta vs no-intervention baseline."},
            {"name": "world_model_forecast", "description":
                "Monte Carlo rollout do DAG ao longo de N turnos (8h cada) "
                "com banda de incerteza (p05/p25/p50/p75/p95). USA quando "
                "a pergunta tem horizonte temporal ('próximos N turnos', "
                "'trajectória', 'como vai evoluir') ou pede range/intervalo "
                "de incerteza. Para um delta exacto num único cenário, usa "
                "causal_query. Params: target (DAG node id), do (dict), "
                "observe (dict), horizon_steps (1-30), samples (50-500)."},
            {"name": "boat_risk_profile", "description":
                "Perfil de risco de um barco específico: fases com maior "
                "probabilidade de defeito + score médio de qualidade. "
                "Param: boat_id (str)."},
            {"name": "affinity_signals", "description":
                "Top-10 afinidades operador-fase (score aprendido). "
                "Params opcionais: phase_id, operator_id. "
                "Vazio até Q.115.G correr."},
            {"name": "runbook_lookup", "description":
                "Runbooks de remediação para um código de erro. "
                "Param: error_code (str). Vazio até Q.115.H correr."},
            {"name": "cost_baseline", "description":
                "Baseline de custos: alvo diário €, margem baseline, "
                "top clientes 30d. Param opcional: commit_id."},
        ]

    @classmethod
    def catalogue_text(cls) -> str:
        """Render the catalogue as a plain bulleted list for the prompt."""
        rows = cls.describe()
        return "\n".join(f"- {r['name']}: {r['description']}" for r in rows)

    # ─── Query methods ───────────────────────────────────────────────

    def wip(self) -> QueryResult:
        raw = self._call_semantic("get_wip")
        if raw is None:
            # Fallback to FactoryState.open_orders when semantic layer is
            # unreachable — keeps the LLM productive in degraded mode.
            ops = (self.state.open_orders if self.state is not None else []) or []
            return _cap({
                "available": bool(ops),
                "open_orders_count": len(ops),
                "top": [self._condense_order(o) for o in ops[:5]],
                "source": "factory_state_fallback",
            })
        data = raw.get("data") or {}
        return _cap({
            "open_orders_count": data.get("total", len(data.get("open_orders_list", []))),
            "top": [self._condense_order(o) for o in (data.get("open_orders_list") or [])[:5]],
            "trust_index": raw.get("trust_index"),
        })

    def bottlenecks(self) -> QueryResult:
        raw = self._call_semantic("get_bottlenecks", top_n=5)
        if raw is None:
            return _unavailable("bottlenecks")
        data = raw.get("data") or {}
        rows = data.get("bottlenecks") or []
        return _cap({
            "count": len(rows),
            "top": [
                {
                    "phase": b.get("fase_nome") or b.get("fase_id"),
                    "score": b.get("bottleneck_score"),
                    "backlog_hours": b.get("backlog_hours"),
                    "is_critical": b.get("is_critical"),
                }
                for b in rows[:5]
            ],
            "trust_index": raw.get("trust_index"),
        })

    def open_orders(self) -> QueryResult:
        raw = self._call_semantic("get_wip")
        if raw is None:
            ops = (self.state.open_orders if self.state is not None else []) or []
            return _cap({
                "total": len(ops),
                "top_by_due": [self._condense_order(o) for o in ops[:5]],
                "source": "factory_state_fallback",
            })
        data = raw.get("data") or {}
        ords = data.get("open_orders_list") or []
        ords_sorted = sorted(
            ords, key=lambda o: o.get("due_date") or "9999",
        )[:5]
        return _cap({
            "total": data.get("total", len(ords)),
            "top_by_due": [self._condense_order(o) for o in ords_sorted],
        })

    def backlog(self) -> QueryResult:
        raw = self._call_semantic("get_backlog", top_n=5)
        if raw is None:
            return _unavailable("backlog")
        data = raw.get("data") or {}
        return _cap({
            "total_hours": data.get("total_backlog_hours"),
            "top": [
                {
                    "order_id": r.get("order_id"),
                    "hours": r.get("backlog_hours"),
                    "phase": r.get("fase_nome"),
                }
                for r in (data.get("top_orders") or [])[:5]
            ],
            "trust_index": raw.get("trust_index"),
        })

    def skills_risk(self, min_capable: int = 3) -> QueryResult:
        raw = self._call_semantic("get_skills_risk", min_capable=min_capable)
        if raw is None:
            return _unavailable("skills_risk")
        data = raw.get("data") or {}
        return _cap({
            "phases_at_risk": data.get("phases_at_risk") or data.get("critical_phases", 0),
            "critical_phases": data.get("critical_phases"),
            "high_risk_phases": data.get("high_risk_phases"),
            "top": [
                {
                    "phase": r.get("fase_nome") or r.get("fase_id"),
                    "capable_workers": r.get("capable_worker_count"),
                    "severity": r.get("severity"),
                }
                for r in (data.get("risk_rows") or [])[:5]
            ],
            "trust_index": raw.get("trust_index"),
        })

    def quality(self) -> QueryResult:
        raw = self._call_semantic("get_quality", top_errors=5)
        if raw is None:
            return _unavailable("quality")
        data = raw.get("data") or {}
        return _cap({
            "total_errors": data.get("total_errors"),
            "top_types": [
                {
                    "type": r.get("error_type") or r.get("descricao"),
                    "count": r.get("count"),
                }
                for r in (data.get("by_type") or data.get("top_items") or [])[:5]
            ],
            "trust_index": raw.get("trust_index"),
        })

    def lead_time(self) -> QueryResult:
        raw = self._call_semantic("get_lead_time")
        if raw is None:
            return _unavailable("lead_time")
        data = raw.get("data") or {}
        return _cap({
            "avg_days": data.get("avg_lead_time_days"),
            "median_days": data.get("median_lead_time_days"),
            "sample_size": data.get("sample_size"),
            "trust_index": raw.get("trust_index"),
        })

    def mold_conflicts(self) -> QueryResult:
        raw = self._call_semantic("get_mold_conflicts")
        if raw is None:
            return _unavailable("mold_conflicts")
        data = raw.get("data") or {}
        return _cap({
            "conflict_count": data.get("conflict_count", 0),
            "top": [
                {
                    "mold_code": r.get("mold_code"),
                    "order_count": r.get("order_count"),
                }
                for r in (data.get("conflicts") or [])[:5]
            ],
            "trust_index": raw.get("trust_index"),
        })

    def preference_rules(self) -> QueryResult:
        rules = getattr(self.state, "preference_rules", None) or []
        return _cap({
            "count": len(rules),
            "by_type": _tally([r.get("type") for r in rules if isinstance(r, Mapping)]),
            "top": [
                {
                    "type": r.get("type"),
                    "description": r.get("description", "")[:120],
                    "confidence": r.get("confidence"),
                }
                for r in rules[:5]
            ],
        })

    def overview(self) -> QueryResult:
        """One call that returns the headline numbers — cheap shortcut
        when the LLM wants a global picture before drilling in."""
        return _cap({
            "wip": self.wip().get("open_orders_count"),
            "bottleneck_count": self.bottlenecks().get("count"),
            "phases_at_risk": self.skills_risk().get("phases_at_risk"),
            "total_errors": self.quality().get("total_errors"),
            "confirmed_rules": self.preference_rules().get("count"),
        })

    @staticmethod
    def _suggest_node_ids(bad: str, max_suggestions: int = 3) -> List[str]:
        """Return up to ``max_suggestions`` known node ids closest to
        ``bad`` by string similarity. Used to turn unknown-node errors
        into actionable hints — without this the LLM tends to retry
        with another invented variant.
        """
        try:
            from difflib import get_close_matches
            from src.copilot.causal.nelo_dag import NODES_BY_ID
        except ImportError:
            return []
        return get_close_matches(
            str(bad), list(NODES_BY_ID.keys()),
            n=max_suggestions, cutoff=0.4,
        )

    def causal_query(
        self,
        target: str,
        *,
        do: Optional[Mapping[str, Any]] = None,
        observe: Optional[Mapping[str, Any]] = None,
    ) -> QueryResult:
        """Numerical kernel sub-query — wraps :func:`nelo_dag.causal_query`.

        Sprint F+ (kernel grounding): the LLM cannot reliably estimate
        magnitudes for NELO's KPIs because the numbers live in the
        DAG, not in pre-trained weights. This sub-query lets it fetch
        the exact ``delta`` from the kernel before composing its
        CausalChain answer.

        Returns a flat, JSON-friendly dict — never raises. ``target``
        unknown / nodes in ``do``/``observe`` unknown → structured
        ``{"error": ...}``. The dispatcher's blanket TypeError fallback
        is overridden here (see ``run``) so a malformed call returns
        an explicit error instead of silently re-running with
        baseline=baseline.
        """
        try:
            from src.copilot.causal.nelo_dag import causal_query as _kernel
        except ImportError as exc:  # pragma: no cover — defensive
            return {"error": f"causal kernel unavailable: {exc}"}

        do_dict: Dict[str, float] = {}
        for k, v in (do or {}).items():
            try:
                do_dict[str(k)] = float(v)
            except (TypeError, ValueError):
                # Common LLM trap: passing the categorical label
                # ("B", "double") instead of the encoded number.
                hint = ""
                if str(k) == "routing_variant":
                    hint = " — use 0.0 (primário) ou 1.0 (variante B)"
                elif str(k) == "shift_mode":
                    hint = " — use 1.0 (turno único) ou 2.0 (duplo)"
                return {
                    "error": (
                        f"do[{k!r}] must be numeric, got {type(v).__name__}"
                        f" ({v!r}){hint}"
                    ),
                }
        observe_dict: Dict[str, float] = {}
        for k, v in (observe or {}).items():
            try:
                observe_dict[str(k)] = float(v)
            except (TypeError, ValueError):
                return {
                    "error": (
                        f"observe[{k!r}] must be numeric, got {type(v).__name__}"
                    ),
                }

        # Validate node ids before handing to the kernel so we can
        # turn "unknown node" into actionable did_you_mean hints.
        from src.copilot.causal.nelo_dag import NODES_BY_ID as _NODES

        if target not in _NODES:
            return {
                "error": f"unknown DAG node: {target!r}",
                "did_you_mean": self._suggest_node_ids(target),
                "field": "target",
            }
        for k in list(do_dict.keys()) + list(observe_dict.keys()):
            if k not in _NODES:
                return {
                    "error": f"unknown DAG node: {k!r}",
                    "did_you_mean": self._suggest_node_ids(k),
                    "field": "do" if k in do_dict else "observe",
                }

        try:
            result = _kernel(target, do=do_dict, observe=observe_dict)
        except KeyError as exc:
            # Defensive fallback — validation above should catch all,
            # but if a kernel internal mapping changes we still hint.
            bad = str(exc).strip("'\"")
            return {
                "error": f"unknown DAG node: {exc}",
                "did_you_mean": self._suggest_node_ids(bad),
            }
        except Exception as exc:  # pragma: no cover — defensive
            return {"error": f"causal_query failed: {exc}"}

        delta = float(result.delta)
        if delta > 1e-9:
            direction = "increase"
        elif delta < -1e-9:
            direction = "decrease"
        else:
            direction = "unchanged"

        return _cap({
            "target": result.target,
            "target_value": round(float(result.target_value), 4),
            "baseline_value": round(float(result.baseline_value), 4),
            "delta": round(delta, 4),
            "direction": direction,
            "magnitude": round(abs(delta), 4),
            "path": list(result.path)[:8],
            "intervention": dict(do_dict) or None,
            "observation": dict(observe_dict) or None,
        })

    def world_model_forecast(
        self,
        target: str,
        *,
        do: Optional[Mapping[str, Any]] = None,
        observe: Optional[Mapping[str, Any]] = None,
        horizon_steps: int = 7,
        samples: int = 200,
    ) -> QueryResult:
        """Monte Carlo rollout sub-query — wraps :func:`world_model.forecast`.

        Devolve um payload reduzido (≤8 rows da trajectória + summary)
        para caber no orçamento de tokens. Ao contrário do
        ``causal_query`` (single-step exacto), este sub-query existe
        para perguntas com horizonte temporal e/ou pedido de
        incerteza ("range esperado", "trajectória", "próximos N
        turnos").
        """
        try:
            from src.copilot.causal.world_model import forecast as _fc
        except ImportError as exc:  # pragma: no cover — defensive
            return {"error": f"world_model unavailable: {exc}"}

        # Validate target before calling — turns "unknown node" into
        # the same did_you_mean diagnostic causal_query produces.
        try:
            from src.copilot.causal.nelo_dag import NODES_BY_ID as _NODES
        except ImportError as exc:  # pragma: no cover — defensive
            return {"error": f"NELO_DAG unavailable: {exc}"}
        if target not in _NODES:
            return {
                "error": f"unknown DAG node: {target!r}",
                "did_you_mean": self._suggest_node_ids(target),
                "field": "target",
            }
        for k in list((do or {}).keys()) + list((observe or {}).keys()):
            if str(k) not in _NODES:
                return {
                    "error": f"unknown DAG node: {k!r}",
                    "did_you_mean": self._suggest_node_ids(str(k)),
                    "field": "do" if k in (do or {}) else "observe",
                }

        report = _fc(
            target=target,
            do=do or None,
            observe=observe or None,
            horizon_steps=horizon_steps,
            samples=samples,
        )
        if report.status == "unavailable":
            return {
                "error": report.reason or "forecast unavailable",
                "did_you_mean": self._suggest_node_ids(target),
            }

        # Trim trajectory to keep the LLM-facing payload small. We
        # round numbers so the JSON dump stays compact.
        trim_rows = min(len(report.trajectory), 8)
        step_rows = [
            {
                "step": s.step,
                "mean": round(s.mean, 4),
                "std": round(s.std, 4),
                "p05": round(s.p05, 4),
                "p50": round(s.p50, 4),
                "p95": round(s.p95, 4),
            }
            for s in report.trajectory[:trim_rows]
        ]

        return _cap({
            "target": report.target,
            "step_unit": report.step_unit,
            "horizon_steps": report.horizon_steps,
            "samples": report.samples,
            "jitter": report.jitter,
            "status": report.status,
            "trajectory": step_rows,
            "summary": report.summary,
            "intervention": report.intervention,
            "observation": report.observation,
        })

    # ─── Q.115.I methods ─────────────────────────────────────────────

    def boat_risk_profile(self, boat_id: str) -> QueryResult:
        """Perfil de risco de um barco: fases com maior p_defect + score qualidade.

        Lê de quality.rework_entry. Por agora usa aggregate pois Q.115.E
        (exposição de boat_id em rework_entry) ainda não correu.
        Budget ≤120 tokens.
        """
        try:
            raw = self._call_semantic("get_boat_risk_profile", boat_id=boat_id)
        except Exception:
            raw = None
        if raw is not None:
            data = raw.get("data") or {}
            phases = [
                PhaseRisk(
                    phase=r.get("phase", ""),
                    p_defect=r.get("p_defect"),
                    sample_n=r.get("sample_n", 0),
                )
                for r in (data.get("top_phases_at_risk") or [])[:3]
            ]
            result = BoatRiskProfile(
                boat_id=boat_id,
                top_phases_at_risk=phases,
                avg_quality_score=data.get("avg_quality_score"),
                completed_ops_30d=data.get("completed_ops_30d"),
            )
        else:
            result = BoatRiskProfile(
                boat_id=boat_id,
                note="perfil de risco por barco disponível após Q.115.E",
            )
        from dataclasses import asdict
        return _cap(asdict(result))

    def affinity_signals(
        self,
        phase_id: Optional[str] = None,
        operator_id: Optional[str] = None,
    ) -> QueryResult:
        """Top-10 afinidades operador-fase (score desc).

        Lê de governance.phase_operator_affinity (Q.115.A.04).
        Tabela vazia até Q.115.G correr — devolve [] + nota.
        Budget ≤120 tokens.
        """
        try:
            raw = self._call_semantic(
                "get_affinity_signals",
                phase_id=phase_id,
                operator_id=operator_id,
            )
        except Exception:
            raw = None
        if raw is not None:
            data = raw.get("data") or {}
            rows = data.get("signals") or []
            signals = [
                AffinitySignal(
                    operator_name=r.get("operator_name", ""),
                    phase_name=r.get("phase_name", ""),
                    score=float(r.get("score", 0.0)),
                    sample_count=int(r.get("sample_count", 0)),
                )
                for r in rows[:10]
            ]
            return _cap({
                "signals": [
                    {
                        "operator_name": s.operator_name,
                        "phase_name": s.phase_name,
                        "score": s.score,
                        "sample_count": s.sample_count,
                    }
                    for s in signals
                ],
                "total": len(signals),
            })
        return _cap({
            "signals": [],
            "total": 0,
            "note": "afinidades ainda não computadas — Q.115.G pendente",
        })

    def runbook_lookup(self, error_code: str) -> QueryResult:
        """Runbooks associados a um código de erro.

        Lê de quality.runbook + quality.error_type_runbook_link.
        Vazio até Q.115.H correr — devolve [] + nota.
        Budget ≤150 tokens.
        """
        try:
            raw = self._call_semantic("get_runbook_lookup", error_code=error_code)
        except Exception:
            raw = None
        if raw is not None:
            data = raw.get("data") or {}
            entries = [
                RunbookEntry(
                    id=r.get("id", ""),
                    steps_md_truncated=(r.get("steps_md") or "")[:200],
                    confidence=float(r.get("confidence", 0.0)),
                    approved=bool(r.get("approved", False)),
                )
                for r in (data.get("runbooks") or [])[:5]
            ]
            result = RunbookLookupResult(
                error_code=error_code,
                runbooks=entries,
                total_history_count=data.get("total_history_count", 0),
            )
        else:
            result = RunbookLookupResult(
                error_code=error_code,
                note="runbooks ainda não carregados — Q.115.H pendente",
            )
        from dataclasses import asdict
        return _cap(asdict(result))

    def cost_baseline(self, commit_id: Optional[str] = None) -> QueryResult:
        """Baseline de custos: alvo diário + margem + top clientes 30d.

        Lê de core.daily_revenue_target + client_priority + core.entities.
        Budget ≤100 tokens.
        """
        try:
            raw = self._call_semantic("get_cost_baseline", commit_id=commit_id)
        except Exception:
            raw = None
        if raw is not None:
            data = raw.get("data") or {}
            result = CostBaseline(
                daily_target_eur=data.get("daily_target_eur"),
                current_baseline_margin_eur=data.get("current_baseline_margin_eur"),
                top_revenue_clients_30d=(data.get("top_revenue_clients_30d") or [])[:5],
            )
        else:
            result = CostBaseline(
                note="dados de custo não disponíveis — tabelas core.daily_revenue_target vazias",
            )
        from dataclasses import asdict
        return _cap(asdict(result))

    # ─── Dispatcher ──────────────────────────────────────────────────

    def run(self, name: str, **params: Any) -> QueryResult:
        """Run a named sub-query with arbitrary params (filtered to the
        method's signature). Unknown names return a structured error
        the LLM can parse instead of a Python exception.
        """
        fn = getattr(self, name, None)
        if fn is None or not callable(fn) or name.startswith("_") or name in {
            "describe", "catalogue_text", "run",
        }:
            return {
                "error": f"unknown query {name!r}",
                "hint": "valid names: " + ", ".join(r["name"] for r in self.describe()),
            }
        try:
            return fn(**params)
        except TypeError as exc:
            # LLM passed a param the method doesn't accept — for most
            # sub-queries the no-arg fallback gives a sane "default"
            # answer (e.g. `wip()` ignores any spurious filter). For
            # `causal_query` that is dangerous: a no-arg call would
            # explode on the missing `target` and we'd lose the
            # diagnostic. Surface the error verbatim instead.
            if name == "causal_query":
                return {
                    "error": (
                        "causal_query needs target (str) and optional "
                        "do={node: value} / observe={node: value} dicts"
                    ),
                    "received_params": list(params.keys()),
                    "underlying": str(exc),
                }
            if name == "world_model_forecast":
                return {
                    "error": (
                        "world_model_forecast needs target (str). "
                        "Optional: do={node: value}, observe={node: value}, "
                        "horizon_steps (1-30), samples (50-500)."
                    ),
                    "received_params": list(params.keys()),
                    "underlying": str(exc),
                }
            return fn()
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("FactoryStateQuery.%s failed: %s", name, exc)
            return {"error": f"{name} failed: {exc}"}

    # ─── Internals ───────────────────────────────────────────────────

    def _call_semantic(self, method: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        if self.queries is None:
            return None
        fn: Optional[Callable[..., Any]] = getattr(self.queries, method, None)
        if fn is None:
            return None
        try:
            return fn(**kwargs)
        except TypeError:
            try:
                return fn()
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug("semantic %s fallback failed: %s", method, exc)
                return None
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("semantic %s failed: %s", method, exc)
            return None

    @staticmethod
    def _condense_order(o: Mapping[str, Any]) -> Dict[str, Any]:
        """Trim an open_order row to the 4 fields the LLM cares about."""
        return {
            "order_id": o.get("order_id") or o.get("id"),
            "model": o.get("modelo_id") or o.get("model_id"),
            "qty": o.get("quantidade") or o.get("quantity"),
            "due": o.get("due_date") or o.get("delivery_date"),
        }


# ─── Small helpers ────────────────────────────────────────────────────


def _tally(items: List[Any]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in items:
        if item is None:
            continue
        key = str(item)
        out[key] = out.get(key, 0) + 1
    return out


def _unavailable(name: str) -> QueryResult:
    return {"available": False, "query": name,
            "reason": "semantic layer not loaded"}


def _cap(payload: QueryResult, *, max_chars: int = 800) -> QueryResult:
    """Budget hint: every query result must fit in ~100 tokens. We
    keep a per-call character cap so an unusually chatty upstream
    (e.g. overview on a big tenant) still fits."""
    import json

    serialised = json.dumps(payload, default=str)
    if len(serialised) <= max_chars:
        return payload
    # Truncate nested "top" arrays progressively.
    capped = dict(payload)
    if "top" in capped and isinstance(capped["top"], list):
        capped["top"] = capped["top"][:2]
        capped["_truncated"] = True
    elif "top_by_due" in capped and isinstance(capped["top_by_due"], list):
        capped["top_by_due"] = capped["top_by_due"][:2]
        capped["_truncated"] = True
    return capped
