
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

SystemType = Literal["extensive", "semi_intensive", "intensive"]
Period = Literal["cycle", "year"]

# Annex V ranges (g gas / m2 / day). We use midpoints unless overridden.
_CH4_G_M2_DAY = {
    "extensive": (0.005 + 0.015) / 2.0,
    "semi_intensive": (0.020 + 0.050) / 2.0,
    "intensive": (0.060 + 0.120) / 2.0,
}

_N2O_G_M2_DAY = {
    "extensive": (0.001 + 0.005) / 2.0,
    "semi_intensive": (0.005 + 0.015) / 2.0,
    "intensive": (0.020 + 0.045) / 2.0,
}

# GWP values mentioned in the methodology narrative
_GWP_CH4 = 84.0   # 20-year
_GWP_N2O = 298.0  # 100-year (as stated in the doc)

@dataclass(frozen=True)
class PondGHGInputs:
    pond_area_m2: float
    system_type: SystemType = "semi_intensive"
    ch4_ef_g_m2_day: Optional[float] = None
    n2o_ef_g_m2_day: Optional[float] = None
    gwp_ch4: float = _GWP_CH4
    gwp_n2o: float = _GWP_N2O

def pond_ch4_n2o_kgco2e(inp: PondGHGInputs, *, period: Period = "cycle", cycle_days: float = 90.0) -> float:
    """CH4+N2O emissions in kg CO2e for the selected period.

    This implements Annex V's area-based emission factor approach (ranges by system type).
    If you want to use the OM-based equations, we can extend inputs to include OM and the EF per unit OM.
    """
    if inp.pond_area_m2 < 0:
        raise ValueError("pond_area_m2 must be >= 0")
    days = 365.0 if period == "year" else float(cycle_days)
    if days < 0:
        raise ValueError("cycle_days must be >= 0")

    ch4_ef = inp.ch4_ef_g_m2_day if inp.ch4_ef_g_m2_day is not None else _CH4_G_M2_DAY[inp.system_type]
    n2o_ef = inp.n2o_ef_g_m2_day if inp.n2o_ef_g_m2_day is not None else _N2O_G_M2_DAY[inp.system_type]
    if ch4_ef < 0 or n2o_ef < 0:
        raise ValueError("emission factors must be >= 0")

    ch4_g = ch4_ef * inp.pond_area_m2 * days
    n2o_g = n2o_ef * inp.pond_area_m2 * days

    ch4_kgco2e = (ch4_g / 1000.0) * inp.gwp_ch4
    n2o_kgco2e = (n2o_g / 1000.0) * inp.gwp_n2o
    return float(ch4_kgco2e + n2o_kgco2e)
