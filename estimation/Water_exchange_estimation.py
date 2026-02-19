
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

EnergySource = Literal["grid", "diesel", "petrol"]

@dataclass(frozen=True)
class PumpingModelInputs:
    # Total pumped volume over the reporting period (cycle or year)
    volume_m3: float

    # Reporting-period definition (cycle length in days). Used to infer pumping time if not provided.
    cycle_days: float = 90.0

    # Hydraulics
    pipe_diameter_m: float = 1.5
    pipe_length_m: float = 100.0
    static_head_m: float = 0.0
    water_density_kg_m3: float = 1025.0
    friction_factor: float = 0.02
    pump_efficiency: float = 0.70
    gravity_m_s2: float = 9.81

    # Total hours spent pumping during the reporting period.
    # If None, defaults to cycle_days * 24 (i.e., pumping distributed over the cycle).
    pumping_duration_hours: Optional[float] = None

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

_DEFAULT_FUEL_EF_KG_PER_LITER = {
    "diesel": 2.64,
    "petrol": 2.31,
}

def pumping_energy_kwh(inp: PumpingModelInputs) -> float:
    """Estimate energy (kWh) required to pump 'volume_m3' of water.

    Implements Annex I.1 steps: area -> flow rate -> velocity -> friction loss -> TDH -> power -> energy.
    """
    if inp.volume_m3 < 0:
        raise ValueError("volume_m3 must be >= 0")
    if inp.pipe_diameter_m <= 0:
        raise ValueError("pipe_diameter_m must be > 0")
    if inp.pump_efficiency <= 0 or inp.pump_efficiency > 1:
        raise ValueError("pump_efficiency must be in (0, 1]")

    # Cross-sectional area
    import math
    area_m2 = math.pi * (inp.pipe_diameter_m / 2) ** 2

    # Flow rate Q = V / t
    pumping_hours = inp.pumping_duration_hours
    if pumping_hours is None:
        if inp.cycle_days <= 0:
            raise ValueError("cycle_days must be > 0")
        pumping_hours = float(inp.cycle_days) * 24.0
    if pumping_hours <= 0:
        raise ValueError("pumping_duration_hours must be > 0")
    t_s = float(pumping_hours) * 3600.0
    q_m3_s = inp.volume_m3 / t_s

    # Velocity v = Q / A
    v_m_s = q_m3_s / area_m2 if area_m2 > 0 else 0.0

    # Frictional head loss hx = f * (L/D) * (v^2 / (2g))
    hx_m = inp.friction_factor * (inp.pipe_length_m / inp.pipe_diameter_m) * (v_m_s ** 2 / (2.0 * inp.gravity_m_s2))

    # Total dynamic head TDH
    tdh_m = inp.static_head_m + hx_m

    # Power required P = (rho * g * Q * TDH) / eta
    p_w = (inp.water_density_kg_m3 * inp.gravity_m_s2 * q_m3_s * tdh_m) / inp.pump_efficiency

    # Energy E = P * t  (J) -> kWh using 3.6e6 J/kWh
    e_j = p_w * t_s
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
