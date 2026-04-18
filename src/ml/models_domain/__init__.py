"""
ProdPlan ONE — Concrete ML Models (Sprint H)
==============================================

Domain-specific model wrappers built on top of Sprint G infrastructure
(`RetrainJob`, `ModelRegistry`, `FeatureExtractor`). Each module exposes:

- A `*Model` class: `train(X, y)`, `predict(X)`, `get_metadata()`.
  Models are scikit-learn-backed for portability (CI doesn't need xgboost).
- A `*RetrainJob` subclass of `RetrainJob`: wires feature extraction from
  the curated layer, training, validation, and governance-tracked
  promotion.
- A `build_training_dataset(semantic_queries)` helper for batch retrains.

Models in this package:
- `quality_risk`: probability of quality event on the next phase execution.
- `duration`: median + p90 duration for (fase_id, modelo_id) — replaces
  the useless `horas_standard`.
- `surrogate`: meta-model that estimates CPO GA fitness to skip expensive
  real evaluations when the predicted fitness is far from the best known.
"""
