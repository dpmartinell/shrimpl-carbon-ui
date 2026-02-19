
from __future__ import annotations

from typing import Any, Dict
from .estimator import EstimatorInputs, estimate

def estimate_carbon_footprint(inputs: EstimatorInputs) -> Dict[str, Any]:
    """Backward-compatible entry point."""
    return estimate(inputs)
