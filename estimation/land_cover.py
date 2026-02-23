from __future__ import annotations

"""Land cover carbon balance (non-pond areas) for MRV.

Satellite (or manual) classification provides *areas by class* (ha). Each class
is assigned a *net flux factor* in kgCO2e/ha/year:

- Positive = emissions (source)
- Negative = removals/sequestration (sink)
- Zero = neutral

The estimator converts annual fluxes to the reporting period (cycle vs year).

This is intentionally simple, auditable, and UI-editable.
"""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Literal

Period = Literal["cycle", "year"]


@dataclass(frozen=True)
class LandCoverClass:
    class_name: str
    area_ha: float
    # Net flux in kgCO2e/ha/year. Negative values represent removals.
    net_flux_kgco2e_per_ha_year: float
    # MRV metadata (optional)
    tier: Optional[str] = None
    factor_source: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class LandCoverResult:
    total_net_kgco2e: float
    total_emissions_kgco2e: float
    total_removals_kgco2e: float  # negative number
    classes_used: List[Dict[str, Any]]


def land_cover_balance_kgco2e(
    classes: List[LandCoverClass],
    *,
    period: Period = "cycle",
    cycle_days: int = 90,
) -> LandCoverResult:
    if period not in ("cycle", "year"):
        raise ValueError("period must be 'cycle' or 'year'")
    if cycle_days <= 0:
        raise ValueError("cycle_days must be > 0")

    frac_year = 1.0 if period == "year" else float(int(cycle_days)) / 365.0

    total_net = 0.0
    total_pos = 0.0
    total_neg = 0.0
    used: List[Dict[str, Any]] = []

    for c in classes:
        if c.area_ha < 0:
            raise ValueError("area_ha must be >= 0")
        annual = float(c.area_ha) * float(c.net_flux_kgco2e_per_ha_year)
        period_val = annual * frac_year
        total_net += period_val
        if period_val >= 0:
            total_pos += period_val
        else:
            total_neg += period_val
        used.append({**asdict(c), "annual_kgco2e": annual, "period_kgco2e": period_val})

    return LandCoverResult(
        total_net_kgco2e=float(total_net),
        total_emissions_kgco2e=float(total_pos),
        total_removals_kgco2e=float(total_neg),
        classes_used=used,
    )


# Conservative, editable defaults (replace/validate per MRV program).
DEFAULT_LAND_COVER_CLASSES: List[LandCoverClass] = [
    LandCoverClass(
        class_name="Mangrove (existing)",
        area_ha=0.0,
        net_flux_kgco2e_per_ha_year=-8000.0,
        tier="tier2",
        factor_source="placeholder (validate per program)",
        notes="Negative = removals. Replace with program-approved factor.",
    ),
    LandCoverClass(
        class_name="Mangrove (co-production inside ponds)",
        area_ha=0.0,
        net_flux_kgco2e_per_ha_year=-8000.0,
        tier="tier2",
        factor_source="placeholder (validate per program)",
        notes="Use pond-water area (not total pond polygon) for CH4/N2O to avoid double counting.",
    ),
    LandCoverClass(
        class_name="Other woody vegetation",
        area_ha=0.0,
        net_flux_kgco2e_per_ha_year=-3000.0,
        tier="tier2",
        factor_source="placeholder (validate per program)",
    ),
    LandCoverClass(
        class_name="Grassland / low vegetation",
        area_ha=0.0,
        net_flux_kgco2e_per_ha_year=-500.0,
        tier="tier2",
        factor_source="placeholder (validate per program)",
    ),
    LandCoverClass(
        class_name="Bare soil / infrastructure",
        area_ha=0.0,
        net_flux_kgco2e_per_ha_year=0.0,
        tier="tier1",
        factor_source="assumed neutral unless program specifies otherwise",
    ),
]
