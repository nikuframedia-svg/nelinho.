"""
ProdPlan ONE — ML Learning Infrastructure (Sprint G)
=====================================================

Cross-cutting module for continuous ML: feature extraction, model registry,
scheduled retraining jobs, governance-tracked promotion, and Prometheus
observability.

Modules:
- `config`: ML configuration (paths, thresholds, schedules)
- `feature_engineering.extractors`: FeatureExtractor abstraction + impls
- `models.registry`: ModelRegistry (save/load/promote with DB row + joblib blob)
- `models.storage`: artifact storage (local filesystem MVP)
- `models.promotion`: integration with governance DecisionRun
- `jobs.base`: RetrainJob base class for APScheduler-driven retraining
- `observability.metrics`: Prometheus counters/histograms for ML

Models themselves (QualityRiskModel, DurationModel, SurrogateModel) live
in Sprint H under `src/ml/models_domain/`.
"""
