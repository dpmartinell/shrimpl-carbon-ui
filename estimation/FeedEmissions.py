
from __future__ import annotations

from typing import Literal, Optional

Boundary = Literal["A", "B"]

# Boundary A defaults from methodology (Section 4.1.2) and Annex II
_DEFAULT_FEED_EF_KGCO2E_PER_KG = 8.7  # marine shrimp feed, kg CO2e per kg feed (per methodology default; ensure consistency with your chosen GWP horizon)
_DEFAULT_SEED_EF_KGCO2E_PER_1000_PL = 0.23  # kg CO2e per 1,000 PL

# Public constants (used by UI defaults)
DEFAULT_FEED_EF_A = _DEFAULT_FEED_EF_KGCO2E_PER_KG
DEFAULT_SEED_EF_A = _DEFAULT_SEED_EF_KGCO2E_PER_1000_PL

__all__ = [
    "Boundary",
    "DEFAULT_FEED_EF_A",
    "DEFAULT_SEED_EF_A",
    "feed_emissions_kgco2e",
    "seed_emissions_kgco2e",
]

def feed_emissions_kgco2e(
    *,
    total_feed_kg: float,
    boundary: Boundary = "A",
    emission_intensity_kgco2e_per_kg: Optional[float] = None,
) -> float:
    """Feed emissions for the reporting period.

    Boundary A: use default highest literature value when no supplier/LCA data is available.
    Boundary B: allow overriding with supplier/LCA-specific intensity.
    """
    if total_feed_kg < 0:
        raise ValueError("total_feed_kg must be >= 0")

    # MRV: if a feed EF is explicitly provided (supplier LCA, internal factor, policy factor), use it.
    # Boundary still matters for reporting/audit, but the calculation should follow the provided factor.
    if emission_intensity_kgco2e_per_kg is not None:
        ef = emission_intensity_kgco2e_per_kg
    else:
        ef = _DEFAULT_FEED_EF_KGCO2E_PER_KG

    if ef < 0:
        raise ValueError("feed emission factor must be >= 0")

    return float(total_feed_kg * ef)

def seed_emissions_kgco2e(
    *,
    thousand_pl: float,
    boundary: Boundary = "A",
    emission_intensity_kgco2e_per_thousand_pl: Optional[float] = None,
) -> float:
    """Seed emissions for the reporting period, in kg CO2e.

    Methodology default: 0.23 kg CO2e per 1,000 PL.
    Boundary B: allow override with hatchery-specific intensity if available.
    """
    if thousand_pl < 0:
        raise ValueError("thousand_pl must be >= 0")

    # MRV: if a hatchery EF is explicitly provided, use it.
    if emission_intensity_kgco2e_per_thousand_pl is not None:
        ef = emission_intensity_kgco2e_per_thousand_pl
    else:
        ef = _DEFAULT_SEED_EF_KGCO2E_PER_1000_PL

    if ef < 0:
        raise ValueError("seed emission factor must be >= 0")

    return float(thousand_pl * ef)
