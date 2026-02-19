from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

SoilType = Literal["desert", "tropical", "temperate", "boreal", "peatland", "mangrove"]

# SOC defaults (tonnes C per ha, by 3 layers)
_DEFAULT_SOC_TONNES_C_PER_HA = {
    "desert":    (10.0, 8.0, 6.0),
    "tropical":  (70.0, 55.0, 40.0),
    "temperate": (85.0, 70.0, 50.0),
    "boreal":    (200.0, 150.0, 100.0),
    "peatland":  (500.0, 400.0, 300.0),
    "mangrove":  (300.0, 250.0, 200.0),
}

_C_TO_CO2 = 3.67  # Annex III conversion


@dataclass(frozen=True)
class LulucInputs:
    """
    LULUC inputs for cycle-based intensity reporting.

    Compatibility:
      - `farm_age_years` is kept for backwards compatibility with older code/UI.
      - Prefer using `years_since_conversion` going forward.

    Time basis:
      - `cycle_days` defines the cycle length (pond prep -> harvest).
      - Function returns kgCO2e for that cycle.
    """
    soil_type: SoilType
    area_ha: float

    # Backwards compatible name (older UI/code)
    farm_age_years: Optional[float] = None

    # Preferred name (clearer)
    years_since_conversion: Optional[float] = None

    # Cycle definition
    cycle_days: int = 120

    # Method parameters
    immediate_release_fraction: float = 0.7
    immediate_window_years: float = 5.0  # <= this age triggers immediate fraction logic
    amortization_years: int = 20  # lifetime/discounting proxy for intensity reporting


def _resolve_years_since_conversion(inp: LulucInputs) -> float:
    """
    Resolve years since conversion using either field.
    """
    if inp.years_since_conversion is not None:
        return float(inp.years_since_conversion)
    if inp.farm_age_years is not None:
        return float(inp.farm_age_years)
    raise ValueError("Provide either years_since_conversion or farm_age_years.")


def luluc_emissions_kgco2e_per_year(inp: LulucInputs) -> float:
    """
    Annual LULUC CO2 emissions allocation (kg CO2e / year) for the *current* year,
    based on years since conversion.

    Logic:
      - Total loss assumed: baseline SOC -> shrimp (full loss) for the converted area.
      - Immediate fraction applies only if conversion is recent (<= immediate_window_years).
      - Immediate portion is counted in the current year (not amortized).
      - Remaining portion is allocated evenly over amortization_years.
      - If years_since_conversion >= amortization_years, gradual allocation is 0 (already allocated).
    """
    if inp.area_ha < 0:
        raise ValueError("area_ha must be >= 0")
    if inp.cycle_days <= 0:
        raise ValueError("cycle_days must be > 0")
    if inp.amortization_years <= 0:
        raise ValueError("amortization_years must be > 0")

    y = _resolve_years_since_conversion(inp)
    if y < 0:
        raise ValueError("years_since_conversion (or farm_age_years) must be >= 0")

    imm_frac = max(0.0, min(1.0, float(inp.immediate_release_fraction)))

    soc_layers = _DEFAULT_SOC_TONNES_C_PER_HA[inp.soil_type]
    total_soc_tC_per_ha = float(sum(soc_layers))

    # Total carbon loss (tC) for converted area (assumes full loss from baseline to shrimp)
    total_loss_tC = total_soc_tC_per_ha * float(inp.area_ha)
    total_tco2 = total_loss_tC * _C_TO_CO2  # tCO2 total "event" magnitude

    # Immediate is only applied for "recent" conversions
    immediate_tco2_this_year = total_tco2 * imm_frac if y <= float(inp.immediate_window_years) else 0.0

    # Remaining portion is allocated across amortization period, but only while inside it
    gradual_total_tco2 = total_tco2 * (1.0 - imm_frac)
    gradual_tco2_this_year = (
        gradual_total_tco2 / float(inp.amortization_years)
        if y < float(inp.amortization_years)
        else 0.0
    )

    annual_tco2 = immediate_tco2_this_year + gradual_tco2_this_year
    return float(annual_tco2 * 1000.0)  # kgCO2e/year


def luluc_emissions_kgco2e(inp: LulucInputs) -> float:
    """
    Cycle-based LULUC CO2 emissions allocation (kg CO2e / cycle).

    Converts the annual allocation into the cycle period using cycle_days/365.
    """
    annual_kg = luluc_emissions_kgco2e_per_year(inp)
    cycle_fraction = float(inp.cycle_days) / 365.0
    return float(annual_kg * cycle_fraction)
