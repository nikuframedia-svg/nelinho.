# Decision Intelligence Platform - Architecture

## System Overview

The Decision Intelligence Platform is built on top of ProdPlan ONE's existing APS foundation, adding interactive decision-making capabilities with:
- **KPI Explanations**: Root cause analysis for metrics
- **Sandbox Isolation**: Safe "what-if" testing
- **Decision Ledger**: Formal approval workflow
- **Audit Trail**: Complete decision history

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
├─────────────────────────────────────────────────────────────────┤
│  Dashboard  │  KPIsPage  │  COGSPage  │  PricingPage │ Decisions│
│  ┌────────┐ │ ┌────────┐ │ ┌────────┐ │ ┌─────────┐ │ ┌───────┐│
│  │KPICard │ │ │Heatmap │ │ │Waterfall│ │ │ Sliders │ │ │Table  ││
│  │Explain │ │ │ OTD    │ │ │  Chart  │ │ │ Margin  │ │ │Audit  ││
│  └────────┘ │ └────────┘ │ └────────┘ │ └─────────┘ │ └───────┘│
└─────────────────────────────────────────────────────────────────┘
                              │ HTTP/REST
┌─────────────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │ KPI API        │  │ Decisions API  │  │ Sandbox API      │  │
│  │ /snapshot-     │  │ /propose       │  │ /sandbox         │  │
│  │  explained     │  │ /approve       │  │ (isolated exec)  │  │
│  │ /otd-heatmap   │  │ /execute       │  │                  │  │
│  └────────────────┘  │ /rollback      │  └──────────────────┘  │
│                      │ /audit         │                          │
│  ┌────────────────┐  └────────────────┘  ┌──────────────────┐  │
│  │ExplanationEngine│  ┌────────────────┐ │ ActionExecutor   │  │
│  │explain_kpi()   │  │ RBAC/SoD       │ │ _capture_state() │  │
│  │explain_otd()   │  │ check_sod()    │ │ _calculate_      │  │
│  └────────────────┘  └────────────────┘ │  actual_impact() │  │
│                                          └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    Data Layer (PostgreSQL)                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │ DecisionRun    │  │ DecisionApproval│ │ ProductionSchedule│  │
│  │ - status       │  │ - approver_id  │ │ - scheduled_*    │  │
│  │ - before_state │  │ - status       │ │ - actual_*       │  │
│  │ - after_state  │  │ - comment      │ │ - setup_time     │  │
│  └────────────────┘  └────────────────┘ └──────────────────┘  │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐                        │
│  │ CostCalculation│  │ Product        │                        │
│  │ - breakdown    │  │ - safety_stock │                        │
│  │ - material     │  │ - lead_time    │                        │
│  └────────────────┘  └────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                 Infrastructure (Redis, Kafka)                   │
├─────────────────────────────────────────────────────────────────┤
│  Redis (Caching)      │  Kafka (Events)                         │
│  - Session storage    │  - Decision events                      │
│  - Rate limiting      │  - Action executed                      │
│  - Connection pool    │  - Circuit breaker                      │
│  (10 connections)     │  (20+ topics)                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### Frontend Components

**KPICard** (`frontend/src/components/KPICard.tsx`):
- Displays KPI value, target, status badge
- "Why?" button triggers explanation modal
- Integrates with `/snapshot-explained` endpoint

**Heatmap** (`frontend/src/components/charts/Heatmap.tsx`):
- Visual matrix (product type × week)
- Color-coded OTD values
- Interactive hover tooltips

**WaterfallChart** (`frontend/src/components/charts/WaterfallChart.tsx`):
- Cumulative breakdown visualization
- Material → Labor → Machine → Total progression
- Color-coded components

**SuggestionsPanel** (`frontend/src/components/SuggestionsPanel.tsx`):
- Displays AI suggestions from Copilot
- "Preview in Sandbox" and "Propose Decision" buttons
- Shows estimated impact and risk level

**SandboxVisualizer** (`frontend/src/components/SandboxVisualizer.tsx`):
- Before/after state comparison
- KPI impact table
- Risk assessment panel

**DecisionsPage** (`frontend/src/pages/shared/DecisionsPage.tsx`):
- Decision ledger table with filters
- Action buttons (Approve, Execute, Rollback)
- Decision detail modal with audit trail

---

### Backend Services

**ExplanationEngine** (`src/shared/explanation_engine.py`):
- `explain_kpi(kpi_name)`: Generic KPI explanation dispatcher
- `explain_otd()`: OTD root cause analysis
- Analyzes contributing factors and weights by impact

**ActionExecutor** (`src/copilot/actions.py`):
- `_capture_state()`: Captures system state before action
- `_calculate_actual_impact()`: Compares before/after states
- Three modes: PREVIEW, SANDBOX, EXECUTE

**SandboxExecutor** (`src/copilot/sandbox.py`):
- Uses SQLAlchemy nested transactions (savepoints)
- Auto-rollback on exit
- Isolation guarantees

**DecisionRun Model** (`src/shared/models/governance.py`):
- Stores decision proposals and execution history
- `before_state` / `after_state` snapshots
- Workflow status tracking

**SoD Enforcement** (`src/shared/auth/rbac.py`):
- `check_sod()`: Validates approver ≠ proposer
- `SOD_POLICIES`: Maps action types to required roles
- Integrated into approval endpoint

---

## Data Flow

### Decision Flow (End-to-End)

```
1. User views KPI → ExplanationEngine.explain_kpi() → Returns root causes
2. Copilot suggests action → ActionExecutor.execute_action(PREVIEW) → Returns estimated_impact
3. User clicks "Preview in Sandbox" → ActionExecutor.execute_action(SANDBOX) → Returns before/after/deltas
4. User clicks "Propose Decision" → POST /v1/decisions/propose → Creates DecisionRun(PROPOSED)
5. Approver reviews → POST /v1/decisions/{id}/approve → Updates DecisionRun(APPROVED) + DecisionApproval
6. Executor runs → POST /v1/decisions/{id}/execute → Updates DecisionRun(EXECUTED) + Commits changes
7. (Optional) Rollback → POST /v1/decisions/{id}/rollback → Restores before_state + Updates DecisionRun(ROLLED_BACK)
```

### Sandbox Execution Flow

```
1. ActionExecutor._capture_state() → Queries relevant tables (schedules/products/operations)
2. Create savepoint (begin_nested()) → Isolated transaction
3. Execute action → Modify state (schedules, products, etc.)
4. ActionExecutor._calculate_actual_impact() → Compare before/after, compute deltas
5. Auto-rollback (savepoint.rollback()) → All changes reverted
6. Return before_state, after_state, actual_impact
```

### KPI Explanation Flow

```
1. GET /v1/profit/kpis/snapshot-explained
2. Calculate KPIs (existing logic)
3. ExplanationEngine.explain_kpi("otd")
   - Query late orders from ProductionSchedule
   - Analyze root causes (machine issues, setup delays, material shortages)
   - Weight by impact (count × delay_hours)
   - Generate top 3 factors with percentages
   - Suggest improvement action
4. Return KPI snapshot + explanations
```

---

## Event Bus Architecture

### Kafka Topics

**Decision Events**:
- `prodplan.copilot.action.executed`: Action execution event

**KPI Events** (existing):
- `prodplan.profit.cogs_calculated`
- `prodplan.profit.pricing_recommended`

**Event Structure**:
```json
{
  "event_id": "uuid",
  "event_type": "copilot.action.executed",
  "tenant_id": "uuid",
  "timestamp": "2025-01-XXT...",
  "source_module": "copilot",
  "payload": {
    "action_id": "...",
    "action_type": "...",
    "transaction_id": "..."
  }
}
```

---

## Database Schema

### Decision Ledger Tables

**`shared.decision_runs`**:
- `id` (UUID, PK)
- `tenant_id` (UUID, FK)
- `title` (String)
- `action_type` (String)
- `target` (String)
- `status` (Enum: PROPOSED, APPROVED, EXECUTED, ROLLED_BACK, REJECTED)
- `sandbox_result` (JSONB)
- `before_state` (JSONB)
- `after_state` (JSONB)
- `proposed_by` (UUID, FK to users)
- `proposed_at` (Timestamp)
- `executed_at` (Timestamp, nullable)
- `rolled_back_at` (Timestamp, nullable)

**`shared.decision_approvals`**:
- `id` (UUID, PK)
- `decision_id` (UUID, FK to decision_runs)
- `approver_id` (UUID, FK to users)
- `status` (Enum: PENDING, APPROVED, REJECTED)
- `comment` (Text, nullable)
- `approved_at` (Timestamp, nullable)

### Relationships

- `DecisionRun` 1:N `DecisionApproval`
- `DecisionRun.proposed_by` → `core.users.id`
- `DecisionApproval.approver_id` → `core.users.id`

---

## Security & Governance

### Segregation of Duties (SoD)

**Policies** (`src/shared/auth/rbac.py`):
```python
SOD_POLICIES = {
    "INCREASE_SS": {"approver_roles": ["PLANNER", "MANAGER"]},
    "ADJUST_INVENTORY": {"approver_roles": ["PLANNER", "MANAGER"]},
    "ADJUST_PRICE": {"approver_roles": ["FINANCE", "MANAGER"]},
    ...
}
```

**Enforcement**:
- `check_sod()` validates approver ≠ proposer
- Validates approver has required role
- Integrated into `/v1/decisions/{id}/approve` endpoint

---

### Audit Trail

**Immutable Records**:
- DecisionRun records cannot be modified after creation
- DecisionApproval records immutable after approval
- All status changes logged with timestamp and actor

**Audit Trail Query**:
- `GET /v1/decisions/{id}/audit` returns complete history
- Includes: PROPOSED, APPROVED, EXECUTED, ROLLED_BACK events
- Each event includes: timestamp, actor, details

---

## Infrastructure

### Database Connection Pooling

- **Pool Size**: 10 connections
- **Max Overflow**: 20 connections
- **Pool Pre-Ping**: Enabled (auto-reconnect on stale connections)
- **Total Capacity**: 30 concurrent connections

### Redis Connection Pooling

- **Pool Size**: 10 connections
- **Async Operations**: `redis.asyncio`
- **Auto-Reconnection**: Enabled

### Kafka Circuit Breaker

- **Failure Threshold**: 5 consecutive failures
- **Timeout**: 60 seconds
- **States**: CLOSED → OPEN → HALF_OPEN → CLOSED
- **Retry**: Exponential backoff (max 3 retries)

---

## Performance Targets

| Endpoint | Concurrent | p95 Target |
|----------|-----------|------------|
| `/v1/profit/kpis/snapshot-explained` | 1000 | <200ms |
| `/api/copilot/sandbox` | 100 | <2s |
| `/v1/decisions` (list) | 500 | <500ms |

---

## Deployment Architecture

```
┌─────────────────┐
│  Load Balancer  │
└────────┬────────┘
         │
    ┌────┴────┐
    │ FastAPI │ (Multiple instances)
    │  App    │
    └────┬────┘
         │
    ┌────┴────┐
    │PostgreSQL│ (Primary + Replica)
    │  (Pool)  │
    └──────────┘
         │
    ┌────┴────┐
    │  Redis  │ (Cache + Rate Limiting)
    └─────────┘
         │
    ┌────┴────┐
    │  Kafka  │ (Event Bus)
    └─────────┘
```

---

## Technology Stack

**Backend**:
- FastAPI 0.109.0 (async web framework)
- SQLAlchemy 2.0.25 (async ORM)
- PostgreSQL (database)
- Redis 5.0.1 (caching)
- Kafka 0.10.0 (event bus)

**Frontend**:
- React 19.2.0
- TypeScript 5.9.3
- React Query 5.90.16 (data fetching)
- Recharts 3.6.0 (visualizations)
- Tailwind CSS 4.1.18

**Testing**:
- pytest 7.4.4
- pytest-asyncio 0.23.3









