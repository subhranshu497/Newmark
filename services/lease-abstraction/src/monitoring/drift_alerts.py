"""Drift alerting (T038, FR-015).

Compares measured accuracy against baseline and raises when the drop
exceeds a configured margin, satisfying spec.md SC-005: "alerts within one
monitoring cycle of dropping below its established baseline."
"""

from __future__ import annotations

import logging

from src.models.accuracy_metric import AccuracyMetricSnapshot

logger = logging.getLogger(__name__)

# How far measured accuracy may fall below baseline before it counts as
# drift. A config value, not a hardcoded business threshold like FR-004's
# confidence threshold — this governs alerting sensitivity, not extraction behavior.
DRIFT_MARGIN = 0.05


class AccuracyDriftAlert(Exception):
    """Raised (and caught by the monitoring scheduler) to trigger an operational alert."""

    def __init__(self, snapshot: AccuracyMetricSnapshot) -> None:
        self.snapshot = snapshot
        super().__init__(
            f"Accuracy drift on {snapshot.field_type.value} "
            f"(model {snapshot.model_version}): "
            f"{snapshot.measured_accuracy:.2%} vs baseline {snapshot.baseline_accuracy:.2%}"
        )


def check_for_drift(snapshots: list[AccuracyMetricSnapshot]) -> list[AccuracyDriftAlert]:
    """Return one AccuracyDriftAlert per snapshot flagged as drifting.

    Callers (a scheduled monitoring job) are expected to route these to
    whatever the platform's existing alerting channel is (out of scope for
    this service to own).
    """
    alerts = []
    for snapshot in snapshots:
        if snapshot.drift_flag:
            alert = AccuracyDriftAlert(snapshot)
            logger.warning(str(alert))
            alerts.append(alert)
    return alerts
