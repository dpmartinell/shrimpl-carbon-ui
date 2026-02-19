
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

EnergySource = Literal["grid", "diesel", "petrol"]
PumpingCalcMethod = Literal["metered_kwh", "hydraulic", "specific_energy"]

@dataclass(frozen=True)
class PumpingModelInputs:
    """Inputs for estimating pumping energy and emissions.

    MRV guidance:
    - Prefer `method="metered_kwh"` when electricity/fuel is directly measured.
    - If only exchange volume is known, `method="hydraulic"` provides an auditable estimate based on
      hydraulic work (rho*g*V*H/eta) plus friction losses.
    - `method="specific_energy"` is a last-resort Tier 1 proxy (kWh/m3) that should be justified/benchmarked.

    Important: Spreading pumping uniformly over the entire cycle can materially under-estimate
    friction losses. If pumping duration is not provided, this module infers duration from an
    assumed mean pipe velocity (see `assumed_velocity_m_s`).
    """

    # Total pumped volume over the reporting period (cycle or year)
    volume_m3: float

    # Reporting-period definition (cycle length in days). Integer days for MRV.
    cycle_days: int = 90

    # Calculation method
    method: PumpingCalcMethod = "hydraulic"

    # If method == "metered_kwh", provide measured electricity use for pumping over the period.
    metered_kwh: Optional[float] = None

    # If method == "specific_energy", energy per unit volume (kWh/m3)
    specific_energy_kwh_per_m3: Optional[float] = None

    # Hydraulics
    pipe_diameter_m: float = 1.5
    pipe_length_m: float = 100.0
    # Static head: default 2 m (typical/conservative for pond exchange depending on site).
    static_head_m: float = 2.0
    water_density_kg_m3: float = 1025.0
    friction_factor: float = 0.02
    pump_efficiency: float = 0.70
    gravity_m_s2: float = 9.81

    # Total hours spent pumping during the reporting period.
    # If None (hydraulic method), duration is inferred from volume and an assumed mean pipe velocity.
    pumping_duration_hours: Optional[float] = None

    # Assumed mean water velocity in the pipe (m/s) when duration is inferred.
    # Typical design velocities are ~1–2 m/s; 1.5 m/s is a reasonable default.
    assumed_velocity_m_s: float = 1.5

    # Emissions settings
    energy_source: EnergySource = "grid"
    grid_country: str = "Mexico"
    grid_ef_kgco2e_per_kwh: Optional[float] = None  # if provided, overrides grid_country mapping
    fuel_ef_kgco2e_per_liter: Optional[float] = None  # for diesel/petrol override


# Default factors (kg CO2e per unit), consistent with methodology statement that grid factors are in CO2e/kWh.
_DEFAULT_GRID_EF_KG_PER_KWH = {
    "Mexico": 0.415,
    "Vietnam": 0.525,
    "Ecuador": 0.206,
    "Brazil": 0.074,
    "India": 0.618,
    "Thailand": 0.401,
}

# Public list for UI dropdowns (MRV: restrict to known defaults; allow overrides separately)
GRID_COUNTRIES = tuple(sorted(_DEFAULT_GRID_EF_KG_PER_KWH.keys()))

_DEFAULT_FUEL_EF_KG_PER_LITER = {
    "diesel": 2.64,
    "petrol": 2.31,
}

def pumping_energy_kwh(inp: PumpingModelInputs) -> float:
    """Estimate energy (kWh) required to pump 'volume_m3' of water.

    Implements an MRV-tiered approach:
    - metered_kwh: return metered kWh directly
    - hydraulic: compute hydraulic work + friction using auditable assumptions
    - specific_energy: compute kWh as volume * kWh/m3

    Hydraulic method steps (Annex I.1 style): area -> infer flow rate -> velocity -> friction loss -> TDH -> energy.
    """
    if inp.volume_m3 < 0:
        raise ValueError("volume_m3 must be >= 0")

    # Tier 0 (best): direct metered energy
    if inp.method == "metered_kwh":
        if inp.metered_kwh is None:
            raise ValueError("method='metered_kwh' requires metered_kwh")
        if inp.metered_kwh < 0:
            raise ValueError("metered_kwh must be >= 0")
        return float(inp.metered_kwh)

    # Tier 1 proxy: specific energy
    if inp.method == "specific_energy":
        if inp.specific_energy_kwh_per_m3 is None:
            raise ValueError("method='specific_energy' requires specific_energy_kwh_per_m3")
        if inp.specific_energy_kwh_per_m3 < 0:
            raise ValueError("specific_energy_kwh_per_m3 must be >= 0")
        return float(inp.volume_m3 * inp.specific_energy_kwh_per_m3)
    if inp.pipe_diameter_m <= 0:
        raise ValueError("pipe_diameter_m must be > 0")
    if inp.pump_efficiency <= 0 or inp.pump_efficiency > 1:
        raise ValueError("pump_efficiency must be in (0, 1]")

    # Cross-sectional area
    import math
    area_m2 = math.pi * (inp.pipe_diameter_m / 2) ** 2

    # Infer flow from either duration or an assumed mean velocity.
    if inp.pumping_duration_hours is not None:
        pumping_hours = float(inp.pumping_duration_hours)
        if pumping_hours <= 0:
            raise ValueError("pumping_duration_hours must be > 0")
        t_s = pumping_hours * 3600.0
        q_m3_s = inp.volume_m3 / t_s
        v_m_s = q_m3_s / area_m2 if area_m2 > 0 else 0.0
    else:
        v_m_s = float(inp.assumed_velocity_m_s)
        if v_m_s <= 0:
            raise ValueError("assumed_velocity_m_s must be > 0")
        q_m3_s = v_m_s * area_m2
        if q_m3_s <= 0:
            return 0.0
        t_s = inp.volume_m3 / q_m3_s

    # Frictional head loss hx = f * (L/D) * (v^2 / (2g))
    hx_m = inp.friction_factor * (inp.pipe_length_m / inp.pipe_diameter_m) * (v_m_s ** 2 / (2.0 * inp.gravity_m_s2))

    # Total dynamic head TDH
    tdh_m = float(inp.static_head_m) + float(hx_m)

    # Hydraulic energy: E = rho * g * V * TDH / eta
    e_j = (inp.water_density_kg_m3 * inp.gravity_m_s2 * inp.volume_m3 * tdh_m) / inp.pump_efficiency
    e_kwh = e_j / 3_600_000.0
    return float(e_kwh)

def pumping_emissions_kgco2e(inp: PumpingModelInputs) -> float:
    """Convert pumping energy to kg CO2e using grid or fuel factors."""
    e_kwh = pumping_energy_kwh(inp)

    if inp.energy_source == "grid":
        ef = inp.grid_ef_kgco2e_per_kwh if inp.grid_ef_kgco2e_per_kwh is not None else _DEFAULT_GRID_EF_KG_PER_KWH.get(inp.grid_country)
        if ef is None:
            raise ValueError(f"Unknown grid_country '{inp.grid_country}'. Provide grid_ef_kgco2e_per_kwh to override.")
        return float(e_kwh * ef)

    # Fuel-based: convert kWh -> MJ and then MJ -> liters using default energy content (if you don't have measured liters).
    # Methodology notes Tier 1 fossil assumption when data missing (Section 4.1.1). Here we implement a simple conversion.
    # Use 3.6 MJ per kWh.
    mj = e_kwh * 3.6

    # Lower heating value approximations (MJ/L). These can be parameterized if needed.
    lhv_mj_per_liter = 36.0 if inp.energy_source == "diesel" else 34.2  # petrol approx

    liters = mj / lhv_mj_per_liter if lhv_mj_per_liter > 0 else 0.0

    ef_l = inp.fuel_ef_kgco2e_per_liter if inp.fuel_ef_kgco2e_per_liter is not None else _DEFAULT_FUEL_EF_KG_PER_LITER[inp.energy_source]
    return float(liters * ef_l)
