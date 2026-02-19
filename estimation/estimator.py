
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
from .otherghg import PondGHGInputs, pond_ch4_n2o_kgco2e, pond_ch4_n2o_mrv


Boundary = Literal["A", "B"]
Period = Literal["cycle", "year"]

@dataclass(frozen=True)
class EstimatorInputs:
    # Output basis
    harvested_shrimp_kg: float
    # Time basis
    period: Period = "cycle"
    cycle_days: int = 90  # used when period == "cycle" (MRV: integer days)
    # Boundary
    boundary: Boundary = "A"

    # Energy
    pumping: Optional[PumpingModelInputs] = None
    aeration: Optional[AerationInputs] = None

    # Feed & seed
    # Feed can be provided directly (total_feed_kg) or estimated from FCR * harvested biomass.
    feed_input_mode: Literal["total", "fcr"] = "total"
    total_feed_kg: Optional[float] = None  # total feed used in the period (cycle or year)
    fcr: Optional[float] = None  # if feed_input_mode == "fcr", used to estimate total feed
    feed_emission_intensity_kgco2e_per_kg: Optional[float] = None  # Boundary B override
    seed_thousand_pl: Optional[float] = None  # number of PL in thousands in the period
    seed_emission_intensity_kgco2e_per_thousand_pl: Optional[float] = None  # Boundary B override

    # Land use / sequestration
    luluc: Optional[LulucInputs] = None
    sequestration: Optional[SequestrationInputs] = None

    # Pond CH4/N2O
    pond_ghg: Optional[PondGHGInputs] = None

    # Optional MRV metadata (provenance, factor sources, notes). Not used in calculations.
    mrv_metadata: Optional[Dict[str, Any]] = None


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

    # MRV: store resolved inputs/assumptions used in calculations
    resolved_inputs: Dict[str, Any] = {}

    if inputs.mrv_metadata:
        resolved_inputs["mrv_metadata"] = inputs.mrv_metadata

    # 1) Pumping
    if inputs.pumping is not None:
        breakdown["pumping"] = pumping_emissions_kgco2e(inputs.pumping)
        resolved_inputs["pumping"] = inputs.pumping.__dict__

    # 2) Aeration
    if inputs.aeration is not None:
        breakdown["aeration"] = aeration_emissions_kgco2e(inputs.aeration)
        resolved_inputs["aeration"] = inputs.aeration.__dict__

    # 3) Feed
    # MRV: allow either direct total feed or FCR-based estimate.
    total_feed_kg: Optional[float] = inputs.total_feed_kg
    if inputs.feed_input_mode == "fcr":
        if inputs.fcr is None:
            raise ValueError("feed_input_mode is 'fcr' but fcr is None")
        if inputs.fcr < 0:
            raise ValueError("fcr must be >= 0")
        total_feed_kg = float(inputs.fcr) * float(inputs.harvested_shrimp_kg)

    if total_feed_kg is not None:
        breakdown["feed"] = feed_emissions_kgco2e(
            total_feed_kg=total_feed_kg,
            boundary=inputs.boundary,
            emission_intensity_kgco2e_per_kg=inputs.feed_emission_intensity_kgco2e_per_kg,
        )
        resolved_inputs["feed"] = {
            "feed_input_mode": inputs.feed_input_mode,
            "total_feed_kg": total_feed_kg,
            "fcr": inputs.fcr,
            "boundary": inputs.boundary,
            "emission_intensity_kgco2e_per_kg": inputs.feed_emission_intensity_kgco2e_per_kg,
        }

    # 4) Seed
    if inputs.seed_thousand_pl is not None:
        breakdown["seed"] = seed_emissions_kgco2e(
            thousand_pl=inputs.seed_thousand_pl,
            boundary=inputs.boundary,
            emission_intensity_kgco2e_per_thousand_pl=inputs.seed_emission_intensity_kgco2e_per_thousand_pl,
        )
        resolved_inputs["seed"] = {
            "thousand_pl": inputs.seed_thousand_pl,
            "boundary": inputs.boundary,
            "emission_intensity_kgco2e_per_thousand_pl": inputs.seed_emission_intensity_kgco2e_per_thousand_pl,
        }

    # 5) LULUC (annualized then scaled to period)
    if inputs.luluc is not None:
        breakdown["luluc"] = luluc_emissions_kgco2e(inputs.luluc) * frac_year
        resolved_inputs["luluc"] = inputs.luluc.__dict__

    # 6) Vegetation sequestration (annual then scaled to period) — subtract as removals
    if inputs.sequestration is not None:
        breakdown["sequestration"] = -sequestration_kgco2e(inputs.sequestration) * frac_year
        resolved_inputs["sequestration"] = inputs.sequestration.__dict__

    # 7) Pond CH4/N2O (daily factors integrated over period)
    if inputs.pond_ghg is not None:
        pond_res = pond_ch4_n2o_mrv(inputs.pond_ghg, period=inputs.period, cycle_days=inputs.cycle_days)
        breakdown["pond_ch4_n2o"] = pond_res.total_kgco2e
        resolved_inputs["pond_ch4_n2o"] = {
            "inputs": inputs.pond_ghg.__dict__,
            "method_tier_used": pond_res.method_tier_used,
            "efs_used_g_m2_day": pond_res.efs_used_g_m2_day,
            "gwps_used": pond_res.gwps_used,
            "tom_used": pond_res.tom_used,
            "note": pond_res.note,
        }

    total_kgco2e = float(sum(breakdown.values()))
    intensity = total_kgco2e / float(inputs.harvested_shrimp_kg)

    return {
        "period": inputs.period,
        "cycle_days": int(inputs.cycle_days) if inputs.period == "cycle" else None,
        "boundary": inputs.boundary,
        "total_kgco2e": total_kgco2e,
        "intensity_kgco2e_per_kg_shrimp": intensity,
        "breakdown_kgco2e": breakdown,
        "inputs": resolved_inputs,
    }
