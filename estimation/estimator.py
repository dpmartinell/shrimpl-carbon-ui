
"""Shrimpl shrimp aquaculture carbon footprint estimator (cradle-to-farm-gate).

Implements the methodology described in 'Shrimp Aquaculture Carbon Footprint Estimation Guidelines'
(ISO 14064-aligned), including:
- Energy for pumping (Annex I.1)
- Energy for aeration (Annex I.2)
- Feed & seed emissions with Boundary A/B logic (Section 4.1.2, Annex II)
- LULUC soil carbon emissions (Annex III) with amortization
- Vegetation sequestration (Annex IV) converted to the same time basis
- Optional CH4 and N2O via area-based emission factors (Annex V ranges)

All component functions return kg CO2e for the chosen reporting period.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal

from .Water_exchange_estimation import PumpingModelInputs, pumping_energy_kwh, pumping_emissions_kgco2e
from .Aeration_energy import AerationInputs, aeration_energy_kwh, aeration_emissions_kgco2e
from .FeedEmissions import feed_emissions_kgco2e, seed_emissions_kgco2e
from .LULUC import LulucInputs, luluc_emissions_kgco2e
from .Carbon_Sequestration import SequestrationInputs, sequestration_kgco2e
from .otherghg import PondGHGInputs, pond_ch4_n2o_kgco2e


Boundary = Literal["A", "B"]
Period = Literal["cycle", "year"]

@dataclass(frozen=True)
class EstimatorInputs:
    # Output basis
    harvested_shrimp_kg: float
    # Time basis
    period: Period = "cycle"
    cycle_days: float = 90.0  # used when period == "cycle"
    # Boundary
    boundary: Boundary = "A"

    # Energy
    pumping: Optional[PumpingModelInputs] = None
    aeration: Optional[AerationInputs] = None

    # Feed & seed
    total_feed_kg: Optional[float] = None  # total feed used in the period (cycle or year)
    feed_emission_intensity_kgco2e_per_kg: Optional[float] = None  # Boundary B override
    seed_thousand_pl: Optional[float] = None  # number of PL in thousands in the period
    seed_emission_intensity_kgco2e_per_thousand_pl: Optional[float] = None  # Boundary B override

    # Land use / sequestration
    luluc: Optional[LulucInputs] = None
    sequestration: Optional[SequestrationInputs] = None

    # Pond CH4/N2O
    pond_ghg: Optional[PondGHGInputs] = None


def _period_fraction_of_year(period: Period, cycle_days: float) -> float:
    if period == "year":
        return 1.0
    # cycle
    return float(cycle_days) / 365.0


def estimate(inputs: EstimatorInputs) -> Dict[str, Any]:
    """Return total emissions and intensity for the selected boundary and period."""
    if inputs.harvested_shrimp_kg <= 0:
        raise ValueError("harvested_shrimp_kg must be > 0")

    frac_year = _period_fraction_of_year(inputs.period, inputs.cycle_days)

    breakdown: Dict[str, float] = {}

    # 1) Pumping
    if inputs.pumping is not None:
        breakdown["pumping"] = pumping_emissions_kgco2e(inputs.pumping)

    # 2) Aeration
    if inputs.aeration is not None:
        breakdown["aeration"] = aeration_emissions_kgco2e(inputs.aeration)

    # 3) Feed
    if inputs.total_feed_kg is not None:
        breakdown["feed"] = feed_emissions_kgco2e(
            total_feed_kg=inputs.total_feed_kg,
            boundary=inputs.boundary,
            emission_intensity_kgco2e_per_kg=inputs.feed_emission_intensity_kgco2e_per_kg,
        )

    # 4) Seed
    if inputs.seed_thousand_pl is not None:
        breakdown["seed"] = seed_emissions_kgco2e(
            thousand_pl=inputs.seed_thousand_pl,
            boundary=inputs.boundary,
            emission_intensity_kgco2e_per_thousand_pl=inputs.seed_emission_intensity_kgco2e_per_thousand_pl,
        )

    # 5) LULUC (annualized then scaled to period)
    if inputs.luluc is not None:
        breakdown["luluc"] = luluc_emissions_kgco2e(inputs.luluc) * frac_year

    # 6) Vegetation sequestration (annual then scaled to period) — subtract as removals
    if inputs.sequestration is not None:
        breakdown["sequestration"] = -sequestration_kgco2e(inputs.sequestration) * frac_year

    # 7) Pond CH4/N2O (daily factors integrated over period)
    if inputs.pond_ghg is not None:
        breakdown["pond_ch4_n2o"] = pond_ch4_n2o_kgco2e(inputs.pond_ghg, period=inputs.period, cycle_days=inputs.cycle_days)

    total_kgco2e = float(sum(breakdown.values()))
    intensity = total_kgco2e / float(inputs.harvested_shrimp_kg)

    return {
        "period": inputs.period,
        "cycle_days": inputs.cycle_days if inputs.period == "cycle" else None,
        "boundary": inputs.boundary,
        "total_kgco2e": total_kgco2e,
        "intensity_kgco2e_per_kg_shrimp": intensity,
        "breakdown_kgco2e": breakdown,
    }
