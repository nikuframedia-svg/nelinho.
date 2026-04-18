"""
ProdPlan ONE — ML Prometheus Metrics
=====================================

Counters + gauges + histograms dedicated to ML training and inference.
Kept in a single module so dashboards have a predictable namespace.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram


# Training -------------------------------------------------------------

ml_training_duration_seconds = Histogram(
    "ml_training_duration_seconds",
    "Time spent training an ML model (seconds).",
    labelnames=("model_name",),
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1800),
)

ml_training_samples_total = Counter(
    "ml_training_samples_total",
    "Total training samples consumed across all retrains.",
    labelnames=("model_name",),
)

ml_training_runs_total = Counter(
    "ml_training_runs_total",
    "Total retrain runs (success + failure).",
    labelnames=("model_name", "outcome"),  # outcome: success | failure | skipped
)

# Validation -----------------------------------------------------------

ml_validation_metric = Gauge(
    "ml_validation_metric",
    "Latest validation metric value for a trained model.",
    labelnames=("model_name", "metric_name"),  # metric_name: wmape, auc, ...
)

# Promotion ------------------------------------------------------------

ml_model_active_version = Gauge(
    "ml_model_active_version",
    "Currently active version per (tenant, model).",
    labelnames=("tenant_id", "model_name"),
)

ml_promotion_decisions_total = Counter(
    "ml_promotion_decisions_total",
    "Model promotion decisions proposed via governance.",
    labelnames=("model_name", "outcome"),  # outcome: proposed | approved | rejected
)

# Inference ------------------------------------------------------------

ml_inference_latency_ms = Histogram(
    "ml_inference_latency_ms",
    "Latency of a single ML inference call (milliseconds).",
    labelnames=("model_name",),
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500),
)

ml_inference_errors_total = Counter(
    "ml_inference_errors_total",
    "ML inference calls that raised an exception.",
    labelnames=("model_name", "error_type"),
)
