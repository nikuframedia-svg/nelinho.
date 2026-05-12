/* =============================================================================
   ProdPlan ONE — read-only views over MAR-KAYAKS
   =============================================================================

   These views expose a stable, English-named, planning-relevant subset of the
   NELO ERP for ProdPlan ONE to consume via its read-only SQL Server adapter.

   Conventions
   -----------
   - Prefix: `vw_pp1_` (PP1 = ProdPlan ONE, version 1 of the integration surface).
   - All source reads use `WITH (NOLOCK)` — ERP is a live production system and
     we MUST NOT take shared locks. We accept dirty-read semantics.
   - Column names in English snake_case. Original PT-PT physical columns are
     aliased — see comments mapping `nome_pt` → `english`.
   - Filter for soft-deleted / inactive rows where applicable (e.g. routings
     with `PRODF_DATA_ELIMINADO IS NULL`).
   - **Do NOT execute this file blindly.** Review with Nelo IT and run inside
     a transaction with rollback first. Each view is `CREATE OR ALTER` so it is
     idempotent.

   Discovery reference: agent_docs/mar_kayaks_schema_discovery.md (2026-05-12).
   ============================================================================= */

USE [MAR-KAYAKS];
GO

/* -----------------------------------------------------------------------------
   vw_pp1_orders — Work orders enriched with customer + order state.

   One row per OF (work order). Joins ORDEMFABRICO with ENCOMENDA + ENCOMENDA_
   ESTADO (state lookup) and the customer entity. Excludes legacy rows where
   ordered_at is the SQL Server epoch (1900-01-01).
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW dbo.vw_pp1_orders AS
SELECT
    of_.OF_ID                 AS work_order_id,
    of_.OF_DATA               AS ordered_at,
    of_.OF_DATATRANSPORTE     AS transport_date,
    of_.OF_DATAENTREGA        AS delivery_date,
    of_.OF_DATAINICIO         AS start_date,
    of_.OF_DATAFIM            AS end_date,
    of_.OF_DATAPAGAMENTO      AS payment_date,
    of_.OF_DATAACTUALIZACAO   AS updated_at,
    of_.OF_NOME               AS customer_name,
    of_.OF_REFERENCIA         AS reference,
    of_.OF_EMAIL              AS customer_email,
    of_.OF_TELEFONE           AS customer_phone,
    of_.OF_MORADAENTREGA      AS delivery_address,
    of_.OF_PRECOCUSTO         AS cost_price,
    of_.OF_PRECOVENDA         AS sale_price,
    of_.OF_DESCONTO           AS discount,
    of_.OF_VALORPAGO          AS paid_amount,
    of_.OF_COEFICIENTE        AS coefficient_eur,        -- € (NOT time)
    of_.OF_PAGO               AS is_paid,
    of_.OF_SUPERVISAO         AS supervised,
    of_.OF_SUPERVISAOLAMINAGEM AS supervised_lamination,
    of_.OF_SEQUENCIA          AS sequence,
    of_.OF_P_ID               AS product_id,
    of_.OF_E_ID               AS customer_entity_id,
    of_.OF_E_ID_ENC           AS ordering_entity_id,
    of_.OF_FP_ID              AS current_phase_id,
    of_.OF_ARM_ID             AS warehouse_id,
    of_.OF_OF_ID_MLD          AS parent_work_order_id,
    of_.OF_OFTU_ID            AS type_of_use_id,
    of_.OF_TURN_ID            AS shift_id,
    of_.OF_ENC_ID             AS encomenda_id,
    enc.ENC_DATAENCOMENDA     AS encomenda_ordered_at,
    enc.ENC_DATAPREVISTAENTREGA AS encomenda_expected_delivery,
    enc.ENC_DATAENTREGA       AS encomenda_actual_delivery,
    enc.ENC_PRECOTOTAL        AS encomenda_total_price,
    enc.ENC_TOTALPAGO         AS encomenda_total_paid,
    enc.ENC_EE_ID             AS encomenda_state_id,
    est.EE_NOME               AS encomenda_state,        -- 'Recebida' / 'Em Curso' / 'Fechada'
    cust.E_NOME               AS customer_full_name,
    cust.E_PAIS               AS customer_country,
    cust.E_EMAIL              AS customer_email_master,
    cust.E_CONTRIBUINTE       AS customer_vat
FROM        dbo.ORDEMFABRICO     of_   WITH (NOLOCK)
LEFT JOIN   dbo.ENCOMENDA        enc   WITH (NOLOCK) ON enc.ENC_ID  = of_.OF_ENC_ID
LEFT JOIN   dbo.ENCOMENDA_ESTADO est   WITH (NOLOCK) ON est.EE_ID   = enc.ENC_EE_ID
LEFT JOIN   dbo.ENTIDADE         cust  WITH (NOLOCK) ON cust.E_ID   = of_.OF_E_ID
WHERE of_.OF_DATA > '1900-01-02';
GO


/* -----------------------------------------------------------------------------
   vw_pp1_routings — Per-product routing with phase K1/K2/K4 reference times.

   Joins PRODUTO_FASE (the routing per product) with FASES_PRODUCAO (work
   centre master) to surface the reference time per boat class. Excludes
   soft-deleted routing rows.
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW dbo.vw_pp1_routings AS
SELECT
    pf.PRODF_ID               AS routing_id,
    pf.PRODF_P_ID             AS product_id,
    pf.PRODF_FP_ID            AS phase_id,
    fp.FP_NOME                AS phase_name,
    fp.FP_DESCRICAO           AS phase_description,
    pf.PRODF_DESCRICAO        AS routing_description,
    pf.PRODF_SEQUENCIA        AS sequence,
    pf.PRODF_TEMPO            AS time_hours,
    fp.FP_HORA_COEF           AS phase_hour_coefficient,
    fp.FP_VALOR_REF_K1        AS k1_reference_hours,
    fp.FP_VALOR_REF_K2        AS k2_reference_hours,
    fp.FP_VALOR_REF_K4        AS k4_reference_hours,
    fp.FP_PRODUCAO            AS phase_is_production,
    fp.FP_AUTOMATICA          AS phase_is_automatic,
    fp.FP_PODE_REPETIR        AS phase_can_repeat,
    fp.FP_PLANEAMENTO         AS phase_planning_enabled,
    fp.FP_COR                 AS phase_color,
    pf.PRODF_AUTOMATICA       AS routing_automatic,
    pf.PRODF_FABRICO          AS routing_in_production,
    pf.PRODF_COEFICIENTE      AS routing_coefficient,
    pf.PRODF_COEFICIENTE_X    AS routing_coefficient_x,
    pf.PRODF_PLANEAMENTO      AS routing_planning_enabled,
    pf.PRODF_TPCAM_ID         AS layer_type_id,
    pf.PRODF_DATA             AS created_at,
    pf.PRODF_DATAACTUALIZACAO AS updated_at
FROM        dbo.PRODUTO_FASE   pf  WITH (NOLOCK)
INNER JOIN  dbo.FASES_PRODUCAO fp  WITH (NOLOCK) ON fp.FP_ID = pf.PRODF_FP_ID
WHERE pf.PRODF_DATA_ELIMINADO IS NULL;
GO


/* -----------------------------------------------------------------------------
   vw_pp1_bom — Bill of materials: parent product × component product.

   Active BOM lines (`COMP_ELIMINADO IS NULL`). Each row gives the parent, the
   component, the quantity, the consumption phase, and resolved names for both
   sides to spare consumers a join back to PRODUTO.
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW dbo.vw_pp1_bom AS
SELECT
    c.COMP_ID                AS bom_id,
    c.COMP_P_ID              AS parent_product_id,
    pp.P_NOME                AS parent_product_name,
    pp.P_NOME_EN             AS parent_product_name_en,
    pp.P_TP_ID               AS parent_product_type_id,
    c.COMP_P_P_ID            AS component_product_id,
    cp.P_NOME                AS component_product_name,
    cp.P_NOME_EN             AS component_product_name_en,
    cp.P_TP_ID               AS component_product_type_id,
    cp.P_UNI_ID              AS component_unit_id,
    cp.P_STOCK               AS component_stock,
    cp.P_STOCKMIN            AS component_stock_min,
    cp.P_PRECOCUSTO          AS component_cost_price,
    c.COMP_QUANTIDADE        AS quantity,
    c.COMP_TPCOMP_ID         AS component_type_id,
    c.COMP_FP_ID             AS consumption_phase_id,
    c.COMP_FASE_FINAL        AS is_final_phase,
    c.COMP_CONFIGURAVEL      AS configurable,
    c.COMP_UNICO             AS is_unique,
    c.COMP_VALOR_EXTRA       AS is_extra_value,
    c.COMP_L_ID              AS list_id,
    c.COMP_OBS               AS observations,
    c.COMP_DATA_ALT          AS changed_at
FROM        dbo.PRODUTO_COMPONENTE c   WITH (NOLOCK)
LEFT JOIN   dbo.PRODUTO            pp  WITH (NOLOCK) ON pp.P_ID = c.COMP_P_ID
INNER JOIN  dbo.PRODUTO            cp  WITH (NOLOCK) ON cp.P_ID = c.COMP_P_P_ID
WHERE c.COMP_ELIMINADO IS NULL;
GO


/* -----------------------------------------------------------------------------
   vw_pp1_schedule — Today's manual daily schedule (PLANEAMENTO_DIARIO).

   This is the painfully manual planning the gestor maintains today — only
   64 rows total, sparsely populated. ProdPlan ONE replaces this surface with
   the GA + CPO scheduler. View is exposed so PP1 can ingest the legacy plan
   for baseline comparison.
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW dbo.vw_pp1_schedule AS
SELECT
    p.PlaneamentoDiarioId    AS schedule_id,
    p.Dia                    AS day,
    p.HoraInicio             AS start_hour,
    p.HoraFim                AS end_hour,
    p.NumeroFuncionarios     AS headcount,
    p.TransporteId           AS transport_id,
    -- Computed: hours in shift (assumes start/end in 24h numeric form).
    CAST(p.HoraFim - p.HoraInicio AS int) AS shift_hours
FROM dbo.PLANEAMENTO_DIARIO p WITH (NOLOCK);
GO


/* -----------------------------------------------------------------------------
   vw_pp1_movements — Stock + WIP ledger, LAST 12 MONTHS only.

   MOVIMENTO has 12 M+ rows in total. ProdPlan ONE only needs recent activity
   for WIP / cura tracking and last-known-good stock balances; long-term
   analytics should query the source table directly with a wider window.
   ----------------------------------------------------------------------------- */
CREATE OR ALTER VIEW dbo.vw_pp1_movements AS
SELECT
    m.MOV_ID                 AS movement_id,
    m.MOV_DATA               AS moved_at,
    m.MOV_DATASAIDA          AS exit_date,
    m.MOV_QUANTIDADE         AS quantity,
    m.MOV_PRECOUNITARIO      AS unit_price,
    m.MOV_PRECOVENDA         AS sale_price,
    m.MOV_DESCONTO           AS discount,
    m.MOV_TPMOV_ID           AS movement_type_id,
    m.MOV_OF_ID              AS work_order_id,
    m.MOV_OFFP_ID            AS work_order_phase_id,
    m.MOV_P_ID               AS product_id,
    m.MOV_E_ID               AS entity_id,
    m.MOV_E_ID_RESPONSAVEL   AS responsible_entity_id,
    m.MOV_E_ID_APROVA        AS approving_entity_id,
    m.MOV_ARM_ID             AS warehouse_id,
    m.MOV_FP_ID              AS phase_id,
    m.MOV_PRODF_ID           AS routing_id,
    m.MOV_MOV_ID             AS parent_movement_id,
    m.MOV_LOTE               AS batch,
    m.MOV_QTD_BAL            AS balance_quantity,
    m.MOV_ACERTO             AS is_adjustment,
    m.MOV_DEFEITUOSO         AS is_defective,
    m.MOV_SATISFEITO         AS is_satisfied,
    m.MOV_DATA_APROVADO      AS approved_at,
    m.MOV_OBSERVACOES        AS observations,
    m.MOV_PROBLEMA           AS problem
FROM dbo.MOVIMENTO m WITH (NOLOCK)
WHERE m.MOV_DATA >= DATEADD(month, -12, CAST(GETDATE() AS date));
GO


/* -----------------------------------------------------------------------------
   Grants (template — Nelo IT to review).

   Suggested role: a dedicated SQL Server login `pp1_reader` that only has
   SELECT on these views (no direct access to base tables). Once the role
   exists:

      GRANT SELECT ON dbo.vw_pp1_orders     TO pp1_reader;
      GRANT SELECT ON dbo.vw_pp1_routings   TO pp1_reader;
      GRANT SELECT ON dbo.vw_pp1_bom        TO pp1_reader;
      GRANT SELECT ON dbo.vw_pp1_schedule   TO pp1_reader;
      GRANT SELECT ON dbo.vw_pp1_movements  TO pp1_reader;

   Current `nikufra` already has read on base tables; views work without
   additional grants for that login.
   ----------------------------------------------------------------------------- */
