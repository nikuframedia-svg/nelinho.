# Decision Intelligence Platform - User Guide

## Introduction

The Decision Intelligence Platform enables users to act on insights with confidence through:
- **KPI Explanations**: Understand why metrics are at current values
- **AI Suggestions**: Get actionable recommendations from Copilot
- **Sandbox Preview**: Test actions in isolation without committing changes
- **Decision Ledger**: Formal approval workflow with audit trail
- **Rollback Capability**: Undo decisions within 24-hour window

---

## Getting Started

### Accessing the Platform

1. Navigate to the Dashboard (`/`)
2. View KPI snapshot with explanations
3. Explore PROFIT pages for drill-down analysis
4. Access Decision Ledger (`/decisions`) for workflow management

---

## Viewing KPIs with Explanations

### Dashboard Overview

The Dashboard displays 8 key KPIs:
- OEE (Overall Equipment Effectiveness)
- Availability
- Performance
- Quality (FPY)
- Rework Rate
- Orders Total
- Orders In Progress
- Orders Completed

Each KPI card includes:
- **Current Value**: Real-time metric
- **Status Badge**: Visual indicator (healthy/warning/critical)
- **"Why?" Button**: Click to see explanation

### Understanding KPI Explanations

Click the **"Why?"** button on any KPI card to see:

1. **Root Cause Analysis**: Top factors contributing to the KPI value
2. **Weighted Impact**: Percentage contribution of each factor
3. **Action Suggestions**: Recommended improvements

**Example OTD Explanation**:
```
Top Factors:
- Machine issues: 45% (7 occurrences)
- Setup delays: 30% (5 occurrences)
- Material shortages: 25% (4 occurrences)

Suggestion: Increase safety stock by 10% to reduce material shortages
```

---

## PROFIT Drill-Down Pages

### KPIs Page (`/profit/kpis`)

**Features**:
- KPI cards with explanations
- **OTD Heatmap**: Visual matrix showing On-Time Delivery by product type and week
  - **Colors**: Green (high OTD) → Red (low OTD)
  - **Hover**: See exact OTD percentage
  - **Filter**: Adjust time range (default: 12 weeks)

**Usage**:
1. Navigate to `/profit/kpis`
2. View OTD heatmap below KPI cards
3. Identify problem products/weeks (red cells)
4. Click product/week to see details

---

### COGS Page (`/profit/cogs`)

**Features**:
- Standard hours analysis by product type
- **Waterfall Chart**: Visual breakdown showing:
  - Base → Labor → Machine → Total
  - Cumulative cost progression

**Usage**:
1. Navigate to `/profit/cogs`
2. View waterfall chart showing cost breakdown
3. Filter by product type
4. Analyze labor vs machine hours ratio

---

### Pricing Page (`/profit/pricing`)

**Features**:
- **Price Slider**: Adjust selling price in real-time
- **Margin Calculator**: Instant margin calculation
- **Impact Analysis**: Table comparing different price points

**Usage**:
1. Navigate to `/profit/pricing`
2. Enter COGS per unit (or select from order)
3. Set quantity
4. Drag price slider to adjust selling price
5. View real-time margin impact:
   - **Healthy Margin**: ≥30% (green)
   - **Profitable but Low**: 0-30% (amber)
   - **Unprofitable**: <0% (red)
6. Compare scenarios in price impact table

**Tips**:
- Margins above 30% are considered healthy
- Use price impact table to evaluate multiple price points
- Consider volume effects (higher price = lower volume)

---

## Making Decisions

### Complete Decision Flow

#### Step 1: View KPI and Explanation

1. Navigate to Dashboard
2. Click "Why?" on any KPI
3. Review root causes and suggestions

#### Step 2: Get AI Suggestion

1. Copilot provides action suggestions
2. Review suggested action:
   - **Title**: Action description
   - **Estimated Impact**: Expected improvement
   - **Risk Level**: Low/Medium/High

#### Step 3: Preview in Sandbox

1. Click **"Preview in Sandbox"** button
2. Sandbox executes action in isolation
3. View **before/after comparison**:
   - State changes
   - KPI impact
   - Risk assessment
4. All changes are **automatically rolled back**

**Sandbox Benefits**:
- Safe "what-if" analysis
- No risk to production data
- Deterministic results (same input = same output)

#### Step 4: Propose Decision

1. If satisfied with sandbox preview, click **"Propose Decision"**
2. Decision proposal created with status `PROPOSED`
3. Automatically routed to approvers (based on SoD policy)

#### Step 5: Approve Decision

**For Approvers**:
1. Navigate to Decision Ledger (`/decisions`)
2. Filter by status: `PROPOSED`
3. Review decision:
   - Title and description
   - Sandbox preview results
   - Before/after state comparison
4. Click **"Approve"** or **"Reject"**
5. Add optional comment

**SoD Protection**: You cannot approve your own proposals.

#### Step 6: Execute Decision

1. Once approved, decision status becomes `APPROVED`
2. Click **"Execute"** to apply changes
3. Decision status becomes `EXECUTED`
4. Changes are committed to production

---

## Decision Ledger

### Accessing the Ledger

Navigate to `/decisions` to view the Decision Ledger.

### Features

**Filtering**:
- Filter by status: `PROPOSED`, `APPROVED`, `EXECUTED`, `ROLLED_BACK`, `REJECTED`
- Filter by action type
- Filter by date range

**Actions**:
- **View Details**: Click decision to see full information
- **Approve/Reject**: For approvers (if status is `PROPOSED`)
- **Execute**: For approved decisions
- **Rollback**: For executed decisions (within 24h window)
- **View Audit Trail**: Complete history of decision lifecycle

### Decision Detail Modal

Shows:
- **Title & Description**: What the decision does
- **Action Type & Target**: What is being changed
- **Status**: Current workflow state
- **Sandbox Preview**: Before/after comparison
- **Approvals**: List of approvers and their decisions
- **Audit Trail**: Complete event history

---

## Rollback

### Rolling Back a Decision

**When**: Within 24 hours of execution

**How**:
1. Navigate to Decision Ledger
2. Find executed decision (within 24h window)
3. Click **"Rollback"** button
4. Confirm rollback
5. State is restored to `before_state`

**Rollback Window**: 
- Only available for 24 hours after execution
- After 24h, rollback is blocked (business logic)

**Verification**:
- Rollback restores exact `before_state`
- All changes are reversed
- Audit trail records rollback event

---

## Sandbox What-If Analysis

### Using Sandbox for Analysis

**Example: Testing Setup Time Reduction**

1. Copilot suggests: "Reduce setup time by 15 minutes"
2. Click **"Preview in Sandbox"**
3. Sandbox executes action:
   - Captures current state (schedules, KPIs)
   - Applies setup time reduction
   - Calculates actual impact
4. View results:
   - **Setup Time Reduction**: 15 minutes per operation
   - **Impact on KPIs**: OTD improvement, makespan reduction
   - **Schedules Modified**: List of affected operations
5. **All changes are rolled back automatically**

**Safe Testing**: You can run sandbox as many times as needed without risk.

---

## Troubleshooting

### KPI Values Show "—" (No Data)

**Cause**: Insufficient data for calculation

**Solution**:
- Check data sources (ProductionSchedule, etc.)
- Verify tenant has production data
- Review KPI `reason` field for explanation

---

### Sandbox Preview Shows No Changes

**Cause**: Action may not affect captured state, or action logic not implemented

**Solution**:
- Verify action type is supported
- Check `capture_state` includes relevant tables
- Review sandbox executor logs

---

### Cannot Approve Own Decision

**Expected Behavior**: SoD (Segregation of Duties) prevents self-approval

**Solution**:
- Request approval from another user with required role
- SoD policies are enforced by business logic

---

### Rollback Button Disabled

**Cause**: Outside 24-hour rollback window

**Solution**:
- Rollback only available within 24 hours of execution
- After 24h, rollback is blocked for data integrity

---

### Decision Status Stuck in "PROPOSED"

**Cause**: Waiting for approval

**Solution**:
- Check if approver has correct role (see SoD policies)
- Verify approver is different from proposer
- Review approval requirements for action type

---

## Best Practices

### Decision Making

1. **Always Preview First**: Use sandbox before proposing decisions
2. **Review Impact**: Check before/after comparison carefully
3. **Document Reasoning**: Add comments when approving
4. **Monitor Results**: Track executed decisions for validation

### KPI Analysis

1. **Use Explanations**: Click "Why?" to understand root causes
2. **Drill Down**: Use heatmaps and waterfall charts for details
3. **Track Trends**: Monitor OTD heatmap over time
4. **Act on Insights**: Use explanations to drive decisions

### Sandbox Testing

1. **Test Multiple Scenarios**: Try different parameters
2. **Verify Determinism**: Same input should produce same output
3. **Review Impact**: Check actual_impact vs estimated_impact
4. **Document Findings**: Note results before proposing

---

## Quick Reference

| Task | Location | Action |
|------|----------|--------|
| View KPIs | Dashboard (`/`) | Click KPI cards |
| See Explanation | Dashboard | Click "Why?" button |
| View OTD Heatmap | `/profit/kpis` | Scroll below KPI cards |
| View COGS Waterfall | `/profit/cogs` | View waterfall chart |
| Adjust Pricing | `/profit/pricing` | Drag price slider |
| Preview Action | Copilot suggestions | Click "Preview in Sandbox" |
| Propose Decision | Sandbox preview | Click "Propose Decision" |
| Approve Decision | `/decisions` | Click "Approve" button |
| Execute Decision | `/decisions` | Click "Execute" button |
| Rollback Decision | `/decisions` | Click "Rollback" button |
| View Audit Trail | `/decisions` | Click decision → "Audit Trail" |

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review API documentation (`/docs`)
3. Consult architecture documentation
4. Check audit trail for decision history









