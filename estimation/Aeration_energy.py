
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

EnergySource = Literal["grid", "diesel", "petrol"]

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

_HP_TO_KW = 0.7457  # Annex I.2.1

@dataclass(frozen=True)
class AerationInputs:
    total_aeration_hp: float
    operating_hours: float  # total hours in the reporting period
    motor_efficiency: float = 0.80  # Annex I.2
    blower_efficiency: float = 1.0  # optional extra efficiency term if using blowers

    energy_source: EnergySource = "grid"
    grid_country: str = "Mexico"
    grid_ef_kgco2e_per_kwh: Optional[float] = None
    fuel_ef_kgco2e_per_liter: Optional[float] = None
    # Fuel conversion assumptions (MJ/L)
    diesel_lhv_mj_per_liter: float = 36.0
    petrol_lhv_mj_per_liter: float = 34.2

def aeration_energy_kwh(inp: AerationInputs) -> float:
    """Energy use (kWh) from aeration, per Annex I.2.

    Steps:
    1) hp -> kW
    2) account for efficiency (divide)
    3) multiply by operating time (h)
    """
    if inp.total_aeration_hp < 0:
        raise ValueError("total_aeration_hp must be >= 0")
    if inp.operating_hours < 0:
        raise ValueError("operating_hours must be >= 0")
    if inp.motor_efficiency <= 0 or inp.motor_efficiency > 1:
        raise ValueError("motor_efficiency must be in (0,1]")
    if inp.blower_efficiency <= 0 or inp.blower_efficiency > 1:
        raise ValueError("blower_efficiency must be in (0,1]")

    kw_mech = inp.total_aeration_hp * _HP_TO_KW
    kw_electric = kw_mech / (inp.motor_efficiency * inp.blower_efficiency)
    return float(kw_electric * inp.operating_hours)

def aeration_emissions_kgco2e(inp: AerationInputs) -> float:
    e_kwh = aeration_energy_kwh(inp)

    if inp.energy_source == "grid":
        ef = inp.grid_ef_kgco2e_per_kwh if inp.grid_ef_kgco2e_per_kwh is not None else _DEFAULT_GRID_EF_KG_PER_KWH.get(inp.grid_country)
        if ef is None:
            raise ValueError(f"Unknown grid_country '{inp.grid_country}'. Provide grid_ef_kgco2e_per_kwh to override.")
        return float(e_kwh * ef)

    # Fuel: kWh -> MJ -> L
    mj = e_kwh * 3.6
    lhv = inp.diesel_lhv_mj_per_liter if inp.energy_source == "diesel" else inp.petrol_lhv_mj_per_liter
    liters = mj / lhv if lhv > 0 else 0.0

    ef_l = inp.fuel_ef_kgco2e_per_liter if inp.fuel_ef_kgco2e_per_liter is not None else _DEFAULT_FUEL_EF_KG_PER_LITER[inp.energy_source]
    return float(liters * ef_l)
