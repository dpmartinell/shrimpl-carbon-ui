
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VegetationType = Literal["Mangroves", "Tropical Forests", "Grasslands", "Wetlands", "Temperate Forests", "Peatlands"]

_C_TO_CO2 = 3.67

_AGB_TC_PER_HA = {
    "Mangroves": 150.0,
    "Tropical Forests": 120.0,
    "Grasslands": 40.0,
    "Wetlands": 60.0,
    "Temperate Forests": 100.0,
    "Peatlands": 70.0,
}

_ROOT_TO_SHOOT = {
    "Mangroves": 0.45,
    "Tropical Forests": 0.24,
    "Grasslands": 0.20,
    "Wetlands": 0.50,
    "Temperate Forests": 0.25,
    "Peatlands": 0.30,
}

_GROWTH_RATE = {
    "Mangroves": 0.015,
    "Tropical Forests": 0.015,
    "Grasslands": 0.03,
    "Wetlands": 0.02,
    "Temperate Forests": 0.02,
    "Peatlands": 0.01,
}

@dataclass(frozen=True)
class SequestrationInputs:
    vegetation_type: VegetationType
    area_ha: float

def sequestration_kgco2e(inp: SequestrationInputs) -> float:
    """Annual CO2 sequestration (removals) in kg CO2e/year.

    Annex IV logic:
    - Biomass C stock = AGB + BGB (BGB from root-to-shoot)
    - Annual increment approximated by growth rate
    - Convert C to CO2 with 3.67
    """
    if inp.area_ha < 0:
        raise ValueError("area_ha must be >= 0")

    veg = inp.vegetation_type
    agb = _AGB_TC_PER_HA[veg]
    bgb = agb * _ROOT_TO_SHOOT[veg]
    total_biomass_c = agb + bgb  # tC/ha

    annual_c_increase_tC = total_biomass_c * _GROWTH_RATE[veg] * float(inp.area_ha)
    annual_co2_t = annual_c_increase_tC * _C_TO_CO2
    return float(annual_co2_t * 1000.0)
