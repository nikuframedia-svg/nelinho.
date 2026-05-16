/* ============================================================================
   ProdPlan ONE / NELO — views_pp1.sql  (Q.20.A)
   ----------------------------------------------------------------------------
   Stable read-only contract between the NELO ERP (SQL Server MAR-KAYAKS) and
   ProdPlan ONE. Apply ONCE on the ERP database. After this, the ProdPlan
   adapter (`src/infrastructure/erp/sqlserver/nelo_erp.py`) only ever touches
   `vw_pp1_*` — if a raw table is renamed, only the matching view changes here.

   >>> ACTION FOR IT NELO <<<
   The raw table / column names below are ProdPlan's best guess. Where a name
   is uncertain it is marked  -- CONFIRM. Please:
     1. Verify each raw table + column against the live schema.
     2. Fix the names so each view compiles.
     3. Grant SELECT on all `vw_pp1_*` to the read-only ProdPlan login.
   The OUTPUT column names (the `AS xxx` aliases) must NOT change — ProdPlan
   depends on them. Only the right-hand side (raw names) may need editing.

   Read-only: these are views over existing tables. No writes, no DDL on data.
   ============================================================================ */

/* ─── vw_pp1_produto — products master ───────────────────────────────────── */
CREATE OR ALTER VIEW vw_pp1_produto AS
SELECT
    p.Produto_Id            AS product_id,        -- CONFIRM
    p.Produto_Codigo        AS product_code,      -- CONFIRM
    p.Produto_Nome          AS product_name,      -- CONFIRM
    p.Produto_Tipo          AS product_type_raw,  -- CONFIRM (K1/K2/K4/recreio…)
    p.Produto_ModeloId      AS modelo_id,         -- CONFIRM
    p.Produto_Activo        AS active             -- CONFIRM (1/0)
FROM PRODUTO p;

/* ─── vw_pp1_produto_fase — routing structure (product × phase × seq) ─────── */
/* coeficiente_x is MONEY (€ bonus), never a duration. Exposed verbatim. */
CREATE OR ALTER VIEW vw_pp1_produto_fase AS
SELECT
    pf.ProdutoFase_ProdutoId    AS product_id,     -- CONFIRM
    pf.ProdutoFase_FaseId       AS fase_id,        -- CONFIRM
    pf.ProdutoFase_Sequencia    AS sequencia,      -- CONFIRM
    pf.ProdutoFase_RequerMolde  AS requires_mold,  -- CONFIRM (1/0)
    pf.ProdutoFase_Coeficiente  AS coeficiente,    -- CONFIRM
    pf.ProdutoFase_CoeficienteX AS coeficiente_x   -- CONFIRM (€, not time)
FROM PRODUTO_FASE pf;

/* ─── vw_pp1_fases_producao — phase catalogue (41 active of 71) ───────────── */
CREATE OR ALTER VIEW vw_pp1_fases_producao AS
SELECT
    f.Fase_Id        AS fase_id,         -- CONFIRM
    f.Fase_Nome      AS fase_nome,       -- CONFIRM
    f.Fase_Sequencia AS fase_sequencia,  -- CONFIRM
    f.Fase_Activo    AS fase_activo      -- CONFIRM (1/0)
FROM FASES_PRODUCAO f;

/* ─── vw_pp1_entidade — workers / operators ───────────────────────────────── */
CREATE OR ALTER VIEW vw_pp1_entidade AS
SELECT
    e.Entidade_Id           AS entidade_id,    -- CONFIRM
    e.Entidade_Nome         AS nome,           -- CONFIRM
    e.Entidade_Activo       AS activo,         -- CONFIRM (1/0)
    e.Entidade_CustoHora    AS custo_hora,     -- CONFIRM
    e.Entidade_DataAdmissao AS data_admissao   -- CONFIRM
FROM ENTIDADE e;

/* ─── vw_pp1_entidade_fase — skill matrix (worker × phase, ~1269 rows) ────── */
CREATE OR ALTER VIEW vw_pp1_entidade_fase AS
SELECT
    ef.EntidadeFase_EntidadeId AS entidade_id,  -- CONFIRM
    ef.EntidadeFase_FaseId     AS fase_id,      -- CONFIRM
    ef.EntidadeFase_Apto       AS apto,         -- CONFIRM (1/0)
    ef.EntidadeFase_Nivel      AS nivel         -- CONFIRM (1-5, NULL ok)
FROM ENTIDADE_FASE ef;

/* ─── vw_pp1_produto_componente — BOM (parent × component) ────────────────── */
CREATE OR ALTER VIEW vw_pp1_produto_componente AS
SELECT
    pc.ProdutoComp_ProdutoId    AS produto_id,    -- CONFIRM
    pc.ProdutoComp_ComponenteId AS componente_id, -- CONFIRM
    pc.ProdutoComp_Quantidade   AS quantidade,    -- CONFIRM
    pc.ProdutoComp_Unidade      AS unidade,       -- CONFIRM
    pc.ProdutoComp_Sequencia    AS sequencia      -- CONFIRM
FROM PRODUTO_COMPONENTE pc;

/* ─── vw_pp1_moldes — ERP-side mold catalogue (~91 rows) ──────────────────── */
/* The 510 production molds live in Excel; this is only the ERP subset, used
   by ProdPlan as a reconcile cross-check. */
CREATE OR ALTER VIEW vw_pp1_moldes AS
SELECT
    m.Molde_Id           AS molde_id,      -- CONFIRM
    m.Molde_Nome         AS molde_nome,    -- CONFIRM
    m.Molde_Estado       AS estado,        -- CONFIRM
    m.Molde_ModeloId     AS modelo_id,     -- CONFIRM
    m.Molde_NumeroPocos  AS numero_pocos,  -- CONFIRM
    m.Molde_TamanhoId    AS tamanho_id     -- CONFIRM
FROM MOLDES m;

/* ─── vw_pp1_of_fp — operation history (~2.6M rows) ───────────────────────── */
/* fase_of_inicio / fase_of_fim are the real timestamps. ProdPlan recomputes
   durations from these and NEVER trusts standard coefficients. */
CREATE OR ALTER VIEW vw_pp1_of_fp AS
SELECT
    o.OfFp_OfId        AS of_id,          -- CONFIRM
    o.OfFp_ProdutoId   AS produto_id,     -- CONFIRM
    o.OfFp_ModeloId    AS modelo_id,      -- CONFIRM
    o.OfFp_FaseId      AS fase_id,        -- CONFIRM
    o.OfFp_EntidadeId  AS entidade_id,    -- CONFIRM
    o.FaseOf_Inicio    AS fase_of_inicio, -- CONFIRM
    o.FaseOf_Fim       AS fase_of_fim,    -- CONFIRM
    o.OfFp_DuracaoH    AS duracao_horas   -- CONFIRM (ERP-side span; ProdPlan
                                          --  recomputes from inicio/fim)
FROM OF_FP o;

/* ─── vw_pp1_offp_probs — quality incidents (~90k rows) ───────────────────── */
CREATE OR ALTER VIEW vw_pp1_offp_probs AS
SELECT
    pr.Prob_Id              AS prob_id,             -- CONFIRM
    pr.Prob_OfId            AS of_id,               -- CONFIRM
    pr.Prob_FaseCulpadaId   AS fase_culpada_id,     -- CONFIRM
    pr.Prob_FaseAvaliacaoId AS fase_avaliacao_id,   -- CONFIRM
    pr.Prob_Descricao       AS descricao,           -- CONFIRM
    pr.Prob_Gravidade       AS gravidade,           -- CONFIRM (1/2/3)
    pr.Prob_DataRegisto     AS data_registo,        -- CONFIRM
    pr.Prob_ChefeId         AS chefe_id,            -- CONFIRM
    pr.Prob_EntidadeCulpada AS entidade_culpada_id, -- CONFIRM
    pr.Prob_ModeloId        AS modelo_id            -- CONFIRM
FROM OFFP_PROBS pr;

/* ─── vw_pp1_of_checklist — checklist results ─────────────────────────────── */
CREATE OR ALTER VIEW vw_pp1_of_checklist AS
SELECT
    c.Checklist_Id          AS checklist_id,  -- CONFIRM
    c.Checklist_OfId        AS of_id,         -- CONFIRM
    c.Checklist_FaseId      AS fase_id,       -- CONFIRM
    c.Checklist_Item        AS item,          -- CONFIRM
    c.Checklist_Resultado   AS resultado,     -- CONFIRM (OK/NOK)
    c.Checklist_DataRegisto AS data_registo   -- CONFIRM
FROM OF_CHECKLIST c;

/* ─── Grants ──────────────────────────────────────────────────────────────── */
/* Replace `prodplan_ro` with the read-only login ProdPlan connects with. */
-- GRANT SELECT ON vw_pp1_produto            TO prodplan_ro;
-- GRANT SELECT ON vw_pp1_produto_fase       TO prodplan_ro;
-- GRANT SELECT ON vw_pp1_fases_producao     TO prodplan_ro;
-- GRANT SELECT ON vw_pp1_entidade           TO prodplan_ro;
-- GRANT SELECT ON vw_pp1_entidade_fase      TO prodplan_ro;
-- GRANT SELECT ON vw_pp1_produto_componente TO prodplan_ro;
-- GRANT SELECT ON vw_pp1_moldes             TO prodplan_ro;
-- GRANT SELECT ON vw_pp1_of_fp              TO prodplan_ro;
-- GRANT SELECT ON vw_pp1_offp_probs         TO prodplan_ro;
-- GRANT SELECT ON vw_pp1_of_checklist       TO prodplan_ro;
