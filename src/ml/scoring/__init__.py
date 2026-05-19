"""ProdPlan ONE — ML scoring (inference at rest).

Sprint Q.41 — turns trained models into batch-scored rows on the
operational tables. The first member is the QualityRiskModel scorer that
the APScheduler ``_quality_risk_scoring_job`` invokes.
"""
