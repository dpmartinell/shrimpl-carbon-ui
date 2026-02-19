from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal, Optional, Dict, Any, Tuple

SystemType = Literal["extensive", "semi_intensive", "intensive"]
Period = Literal["cycle", "year"]
MethodTier = Literal["tier1_default", "tier2_tom_scaled", "tier3_measured"]
GWPVersion = Literal["ar6"]  # extend if needed

# ---------------------------------------------------------------------
# Tier 1 default EFs (Annex V ranges, g gas / m2 / day). Use midpoints.
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# MRV consistency: use a single GWP horizon/version.
# Default: AR6 100-year (non-fossil CH4 for ponds).
# Values: CH4=27, N2O=273.
# ---------------------------------------------------------------------
_GWP100_AR6 = {"ch4": 27.0, "n2o": 273.0}


def _period_days(period: Period, cycle_days: float) -> float:
    days = 365.0 if period == "year" else float(cycle_days)
    if days < 0:
        raise ValueError("cycle_days must be >= 0")
    return days


def _tom_multiplier_saturating(om_mg_l: float, *, om_min: float, k: float, a: float) -> float:
    """Bounded saturating multiplier in [1, 1+a).

    mult = 1 + a * x/(x+k), where x=max(0, OM-OM_min)
    - stable (won't explode at high OM)
    - monotonic (MRV-friendly)
    """
    if k <= 0:
        raise ValueError("tom_k_mg_l must be > 0")
    x = max(0.0, float(om_mg_l) - float(om_min))
    return 1.0 + float(a) * (x / (x + float(k)))


@dataclass(frozen=True)
class TOMSummary:
    """Satellite-calibrated total organic matter (TOM) in water column (mg/L).

    This is treated as an MRV activity-data enhancer (Tier 2).
    Keep calibration metadata so results remain auditable.
    """
    om_avg_mg_l: float
    om_p90_mg_l: Optional[float] = None
    coverage_pct: Optional[float] = None  # % valid obs over cycle window
    source: str = "satellite_calibrated"
    calibration_model_id: Optional[str] = None
    calibration_rmse_mg_l: Optional[float] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class PondGHGInputs:
    """Inputs for pond CH4+N2O module.

    - Tier 1: system-type default EFs (or manual EF override).
    - Tier 2: Tier 1 EFs scaled by satellite-calibrated TOM (bounded).
    - Tier 3: measured flux rates (future-ready).
    """
    pond_area_m2: float
    system_type: SystemType = "semi_intensive"

    # Method tier selection
    method_tier: MethodTier = "tier1_default"

    # Optional Tier 1 overrides (g/m2/day)
    ch4_ef_g_m2_day: Optional[float] = None
    n2o_ef_g_m2_day: Optional[float] = None

    # Tier 2 enhancer
    tom: Optional[TOMSummary] = None

    # TOM scaling parameters (version-controlled defaults; tune/calibrate later)
    tom_om_min_mg_l: float = 0.0
    tom_k_mg_l: float = 20.0
    tom_a_ch4: float = 1.5
    tom_a_n2o: float = 0.7
    tom_use_p90_for_ch4: bool = True

    # Tier 3 (measured)
    measured_ch4_g_m2_day: Optional[float] = None
    measured_n2o_g_m2_day: Optional[float] = None

    # GWPs (consistent)
    gwp_version: GWPVersion = "ar6"


@dataclass(frozen=True)
class PondGHGResult:
    total_kgco2e: float
    ch4_kg: float
    n2o_kg: float
    ch4_kgco2e: float
    n2o_kgco2e: float

    method_tier_used: MethodTier
    days_used: float
    efs_used_g_m2_day: Dict[str, float]  # {"ch4":..., "n2o":...}
    tom_used: Optional[Dict[str, Any]]
    gwps_used: Dict[str, float]
    note: str


def pond_ch4_n2o_mrv(inp: PondGHGInputs, *, period: Period = "cycle", cycle_days: float = 90.0) -> PondGHGResult:
    """MRV-ready pond CH4+N2O calculation.

    Returns a structured result with an audit trail (tier used, EFs used, TOM metadata).
    """
    if inp.pond_area_m2 < 0:
        raise ValueError("pond_area_m2 must be >= 0")

    days = _period_days(period, cycle_days)

    # GWPs (currently only AR6 GWP100)
    gwp = _GWP100_AR6

    tom_used = asdict(inp.tom) if inp.tom is not None else None

    # Choose EFs
    if inp.method_tier == "tier3_measured":
        if inp.measured_ch4_g_m2_day is None or inp.measured_n2o_g_m2_day is None:
            raise ValueError("Tier 3 selected but measured CH4/N2O rates not provided.")
        ch4_ef = float(inp.measured_ch4_g_m2_day)
        n2o_ef = float(inp.measured_n2o_g_m2_day)
        note = "Tier 3: measured flux rates."
    else:
        ch4_ef = float(inp.ch4_ef_g_m2_day) if inp.ch4_ef_g_m2_day is not None else float(_CH4_G_M2_DAY[inp.system_type])
        n2o_ef = float(inp.n2o_ef_g_m2_day) if inp.n2o_ef_g_m2_day is not None else float(_N2O_G_M2_DAY[inp.system_type])

        if inp.method_tier == "tier2_tom_scaled":
            if inp.tom is None:
                raise ValueError("Tier 2 selected but TOMSummary not provided.")
            om_for_ch4 = inp.tom.om_p90_mg_l if (inp.tom_use_p90_for_ch4 and inp.tom.om_p90_mg_l is not None) else inp.tom.om_avg_mg_l
            m_ch4 = _tom_multiplier_saturating(om_for_ch4, om_min=inp.tom_om_min_mg_l, k=inp.tom_k_mg_l, a=inp.tom_a_ch4)
            m_n2o = _tom_multiplier_saturating(inp.tom.om_avg_mg_l, om_min=inp.tom_om_min_mg_l, k=inp.tom_k_mg_l, a=inp.tom_a_n2o)
            ch4_ef *= m_ch4
            n2o_ef *= m_n2o
            note = "Tier 2: Annex EFs scaled by satellite-calibrated TOM (bounded saturating response)."
        else:
            note = "Tier 1: Annex/system-type default EFs (or manual EF override)."

    if ch4_ef < 0 or n2o_ef < 0:
        raise ValueError("emission factors must be >= 0")

    # Masses over period
    ch4_g = ch4_ef * inp.pond_area_m2 * days
    n2o_g = n2o_ef * inp.pond_area_m2 * days
    ch4_kg = ch4_g / 1000.0
    n2o_kg = n2o_g / 1000.0

    ch4_kgco2e = ch4_kg * gwp["ch4"]
    n2o_kgco2e = n2o_kg * gwp["n2o"]
    total = float(ch4_kgco2e + n2o_kgco2e)

    return PondGHGResult(
        total_kgco2e=total,
        ch4_kg=float(ch4_kg),
        n2o_kg=float(n2o_kg),
        ch4_kgco2e=float(ch4_kgco2e),
        n2o_kgco2e=float(n2o_kgco2e),
        method_tier_used=inp.method_tier,
        days_used=float(days),
        efs_used_g_m2_day={"ch4": float(ch4_ef), "n2o": float(n2o_ef)},
        tom_used=tom_used,
        gwps_used=dict(gwp),
        note=note,
    )


def pond_ch4_n2o_kgco2e(inp: PondGHGInputs, *, period: Period = "cycle", cycle_days: float = 90.0) -> float:
    """Backward-compatible entry point (returns kg CO2e float).

    Use `pond_ch4_n2o_mrv` if you need MRV metadata (tier used, TOM, EFs).
    """
    return float(pond_ch4_n2o_mrv(inp, period=period, cycle_days=cycle_days).total_kgco2e)
