from __future__ import annotations

import json
from typing import List, Tuple, Optional

import streamlit as st

from estimation.estimator import EstimatorInputs, estimate
from estimation.Water_exchange_estimation import PumpingModelInputs, EnergySource, GRID_COUNTRIES
from estimation.Aeration_energy import AerationInputs
from estimation.FeedEmissions import DEFAULT_FEED_EF_A, DEFAULT_SEED_EF_A
from estimation.LULUC import LulucInputs
from estimation.Carbon_Sequestration import SequestrationInputs
from estimation.otherghg import PondGHGInputs

from ui.geo_utils import polygon_from_lonlat
from ui.soilgrids_wcs import fetch_soc_for_bbox_mean, DEFAULT_SOC_WCS_MAP

st.set_page_config(page_title="Shrimpl Carbon Footprint Prototype", layout="wide")
st.title("Shrimpl Carbon Footprint Prototype (Cycle-based)")

st.caption(
    "Enter cycle inputs and a pond/farm polygon. The app computes area and can try to fetch SoilGrids SOC via WCS "
    "(best-effort). If SoilGrids is unreachable, select soil type / SOC manually."
)

# --------- Helpers ---------
def parse_polygon(text: str) -> List[Tuple[float, float]]:
    """Accept JSON list of [lon,lat] pairs or a GeoJSON Polygon coordinates array."""
    obj = json.loads(text)
    # If GeoJSON Feature
    if isinstance(obj, dict) and obj.get("type") == "Feature":
        obj = obj["geometry"]
    if isinstance(obj, dict) and obj.get("type") == "Polygon":
        obj = obj["coordinates"][0]
    if not isinstance(obj, list):
        raise ValueError("Expected a JSON array of coordinate pairs or a GeoJSON Polygon/Feature.")
    coords = []
    for pt in obj:
        if not (isinstance(pt, list) or isinstance(pt, tuple)) or len(pt) < 2:
            raise ValueError("Each coordinate must be [lon, lat].")
        coords.append((float(pt[0]), float(pt[1])))
    return coords

# --------- Sidebar inputs ---------
with st.sidebar:
    st.header("Cycle basis")
    cycle_days = st.number_input("Cycle length (days)", min_value=1, value=90, step=1)
    harvested_kg = st.number_input("Harvested shrimp (kg)", min_value=0.0, value=10000.0)

    st.divider()
    st.header("Boundary")
    boundary = st.selectbox(
        "Boundary (A or B)",
        ["A", "B"],
        index=0,
        help="Boundary A: no supplier-specific data. Boundary B: vertically integrated / supplier-specific data available.",
    )

    st.divider()
    st.header("Energy source")
    energy_source: EnergySource = st.selectbox("Energy source", ["grid", "diesel", "petrol"])
    grid_country = st.selectbox(
        "Grid country (for kgCO2e/kWh factor lookup)",
        list(GRID_COUNTRIES),
        index=list(GRID_COUNTRIES).index("Ecuador") if "Ecuador" in GRID_COUNTRIES else 0,
    )
    grid_ef_override = st.number_input(
        "Optional: override grid EF (kgCO2e/kWh)",
        min_value=0.0,
        value=0.0,
        help="If you have an official factor (utility, ministry, IEA, etc.), enter it here to override the country lookup.",
    )
    grid_ef_source = st.text_input(
        "Optional: grid EF source / citation",
        value="",
        help="Free text for audit trail (e.g., 'Ministry 2024', 'utility bill 2025-01', etc.).",
    )

    st.divider()
    st.header("Feed & seed (cycle totals)")
    feed_input_mode = st.radio(
        "Feed input mode",
        ["Total feed (kg)", "FCR (estimate feed = FCR × harvested biomass)"],
        index=0,
        help="Either provide total feed used over the cycle, or provide FCR and we estimate total feed as FCR × harvested biomass.",
    )
    total_feed_kg = None
    fcr = None
    if feed_input_mode == "Total feed (kg)":
        total_feed_kg = st.number_input("Total feed used in cycle (kg)", min_value=0.0, value=15000.0)
    else:
        fcr = st.number_input("FCR (kg feed / kg shrimp)", min_value=0.0, value=1.4)

    # UI default display: feed EF average of 1.43 (user request). This is not fixed.
    use_method_default_feed_ef = st.checkbox(
        "Use methodology default feed EF (conservative)",
        value=False,
        help="If checked, the model will ignore the feed EF input below and use the methodology default factor.",
    )
    st.caption("Default shown is Shrimpl average feed EF = 1.43 kgCO2e/kg feed (editable).")
    feed_ef = st.number_input(
        "Feed EF (kgCO2e/kg feed)",
        min_value=0.0,
        value=1.43,
        disabled=use_method_default_feed_ef,
    )
    feed_ef_source = st.text_input(
        "Optional: feed EF source / basis",
        value="",
        help="Free text for audit trail (e.g., supplier LCA, ecoinvent, internal average, GWP basis).",
    )
    seed_kpl = st.number_input("Seed (thousand PL) in cycle", min_value=0.0, value=0.0)
    seed_ef = st.number_input("Seed EF (kgCO2e / 1000 PL)", min_value=0.0, value=float(DEFAULT_SEED_EF_A))
    seed_ef_source = st.text_input(
        "Optional: seed EF source / basis",
        value="",
        help="Free text for audit trail (e.g., hatchery LCA, literature, internal factor).",
    )

    st.divider()
    st.header("Aeration")
    aeration_hp = st.number_input("Total aeration power (hp)", min_value=0.0, value=0.0)
    aeration_hours_per_day = st.number_input("Aeration hours/day", min_value=0.0, max_value=24.0, value=0.0)
    motor_eff = st.number_input("Motor efficiency (0-1)", min_value=0.01, max_value=1.0, value=0.90)
    blower_eff = st.number_input("Blower efficiency (0-1)", min_value=0.01, max_value=1.0, value=0.80)

    st.divider()
    st.header("Pumping / water exchange")
    water_exchange_pct = st.number_input(
        "Water exchanged over cycle (%)",
        min_value=0.0,
        max_value=1000.0,
        value=0.0,
        help="Percent of the pond water volume exchanged over the cycle. For example, 100% means exchanging one full pond volume across the cycle.",
    )
    pond_depth_m = st.number_input(
        "Average pond depth for pumping volume (m)",
        min_value=0.1,
        value=1.0,
        help="Used only to compute exchanged water volume = area × depth × exchange%. Default 1 m per current UI assumption.",
    )
    pumping_method = st.selectbox(
        "Pumping calculation method",
        [
            "Hydraulic estimate (volume + head + pipe)",
            "Measured electricity (kWh)",
            "Default specific energy (kWh/m³)",
        ],
        index=0,
        help="MRV preference: measured electricity > hydraulic estimate > specific energy proxy.",
    )

    # Defaults (overridden below depending on method)
    metered_pumping_kwh = 0.0
    specific_energy_kwh_m3 = 0.01
    assumed_velocity_m_s = 1.5
    pumping_duration_hours = 0.0

    pipe_diam_m = 1.5
    pipe_len_m = 100.0
    static_head_m = 2.0
    pump_eff = 0.70
    friction_factor = 0.02

    if pumping_method == "Measured electricity (kWh)":
        metered_pumping_kwh = st.number_input("Measured pumping electricity over cycle (kWh)", min_value=0.0, value=0.0)
    elif pumping_method == "Default specific energy (kWh/m³)":
        specific_energy_kwh_m3 = st.number_input(
            "Specific energy (kWh per m³ pumped)",
            min_value=0.0,
            value=0.01,
            help="Last-resort proxy. ~0.01 kWh/m³ corresponds roughly to a few meters of head at typical efficiencies.",
        )
    else:
        pipe_diam_m = st.number_input("Pipe diameter (m)", min_value=0.01, value=1.5)
        pipe_len_m = st.number_input("Pipe length (m)", min_value=0.0, value=100.0)
        static_head_m = st.number_input("Static head (m)", min_value=0.0, value=2.0)
        pump_eff = st.number_input("Pump efficiency (0-1)", min_value=0.01, max_value=1.0, value=0.70)
        friction_factor = st.number_input("Friction factor (dimensionless)", min_value=0.001, value=0.02)
        assumed_velocity_m_s = st.number_input(
            "Assumed mean pipe velocity (m/s)",
            min_value=0.1,
            value=1.5,
            help="Used to infer pumping duration and friction losses when total pumping hours are unknown.",
        )
        pumping_duration_hours = st.number_input(
            "Optional: total pumping hours over cycle (leave 0 to infer)",
            min_value=0.0,
            value=0.0,
        )

    st.divider()
    st.header("LULUC & GHG (optional)")
    include_luluc = st.checkbox("Include LULUC", value=True)
    include_pond_ghg = st.checkbox("Include pond CH4/N2O", value=False)

    # Pond GHG MRV tiering (only used when Include pond CH4/N2O is enabled)
    pond_method_tier = "tier1_default"
    pond_om_avg = None
    pond_om_p90 = None
    pond_calibration_id = ""
    pond_coverage_pct = None
    if include_pond_ghg:
        st.caption("Pond CH4/N2O supports MRV tiers. Tier 1 uses default EFs; Tier 2 scales by TOM (mg/L).")
        pond_method_tier = st.selectbox(
            "Pond CH4/N2O method tier",
            ["tier1_default", "tier2_tom_scaled"],
            index=0,
            help="Tier 2 requires TOM (total organic matter) in the water column, typically from satellite-calibrated model."
        )
        if pond_method_tier == "tier2_tom_scaled":
            pond_om_avg = st.number_input("TOM average over cycle (mg/L)", min_value=0.0, value=0.0)
            pond_om_p90 = st.number_input("TOM p90 over cycle (mg/L) (optional)", min_value=0.0, value=0.0)
            pond_coverage_pct = st.number_input("TOM coverage (%) (optional)", min_value=0.0, max_value=100.0, value=0.0)
            pond_calibration_id = st.text_input("TOM calibration model ID (optional)", value="")

# --------- Polygon input & soil ---------
st.subheader("Farm / pond polygon (for area + soil)")
default_poly = json.dumps(
    [[-80.05, -2.25], [-80.00, -2.25], [-80.00, -2.20], [-80.05, -2.20], [-80.05, -2.25]],
    indent=2
)
poly_text = st.text_area(
    "Paste polygon coordinates as JSON [[lon,lat], ...] OR GeoJSON Polygon/Feature",
    value=default_poly,
    height=150,
)

poly_info = None
soc_result = None

c1, c2 = st.columns([1, 1])
with c1:
    st.markdown("**Polygon diagnostics**")
    try:
        coords = parse_polygon(poly_text)
        poly_info = polygon_from_lonlat(coords)
        st.write(f"Area: **{poly_info.area_ha:,.2f} ha** ({poly_info.area_m2:,.0f} m²)")
        st.write(f"Centroid: lon **{poly_info.centroid_lon:.6f}**, lat **{poly_info.centroid_lat:.6f}**")
    except Exception as e:
        st.error(f"Polygon error: {e}")

with c2:
    st.markdown("**Soil / SOC (auto, best-effort)**")
    st.caption("Uses SoilGrids WCS. If unavailable, set LULUC inputs manually.")
    wcs_url = st.text_input("SoilGrids WCS base URL", value=DEFAULT_SOC_WCS_MAP)
    fetch_soc = st.button("Fetch SOC (bbox mean)", disabled=(poly_info is None))
    if fetch_soc and poly_info is not None:
        minx, miny, maxx, maxy = poly_info.polygon.bounds
        try:
            soc_result = fetch_soc_for_bbox_mean((minx, miny, maxx, maxy), wcs_base_url=wcs_url)
            st.success("Fetched SOC")
            st.write(f"Coverage ID: `{soc_result.coverage_id}`")
            st.write(f"Mean value: **{soc_result.soc_mean:.3f}** ({soc_result.soc_unit})")
            st.caption(soc_result.note)
        except Exception as e:
            st.warning(f"Could not fetch SOC automatically: {e}")

# Manual LULUC fallbacks
luluc_area_ha = poly_info.area_ha if poly_info is not None else 0.0
st.divider()
st.subheader("LULUC inputs (manual override)")

colA, colB, colC = st.columns(3)
with colA:
    land_use_years = st.number_input("Years since land conversion (for immediate fraction rule)", min_value=0.0, value=0.0)
with colB:
    amort_years = st.number_input("Farm expected lifetime / amortization (years)", min_value=1.0, value=20.0)
with colC:
    soil_type = st.selectbox(
    "Soil type (method defaults)",
    ["desert", "tropical", "temperate", "boreal", "peatland", "mangrove"]
)


# --------- Build estimator inputs ---------
pumping_inputs: Optional[PumpingModelInputs] = None
computed_pumped_volume_m3: Optional[float] = None
if water_exchange_pct > 0 and poly_info is not None:
    # MRV/UI assumption: exchanged volume = pond area × depth × (% exchange)
    computed_pumped_volume_m3 = float(poly_info.area_m2) * float(pond_depth_m) * (float(water_exchange_pct) / 100.0)

if computed_pumped_volume_m3 is not None and computed_pumped_volume_m3 > 0:
    # Map UI label -> model method
    if pumping_method == "Measured electricity (kWh)":
        method = "metered_kwh"
    elif pumping_method == "Default specific energy (kWh/m³)":
        method = "specific_energy"
    else:
        method = "hydraulic"

    pumping_inputs = PumpingModelInputs(
        volume_m3=float(computed_pumped_volume_m3),
        cycle_days=int(cycle_days),
        method=method,  # type: ignore[arg-type]
        metered_kwh=(float(metered_pumping_kwh) if method == "metered_kwh" else None),
        specific_energy_kwh_per_m3=(float(specific_energy_kwh_m3) if method == "specific_energy" else None),
        pipe_diameter_m=float(pipe_diam_m),
        pipe_length_m=float(pipe_len_m),
        static_head_m=float(static_head_m),
        pump_efficiency=float(pump_eff),
        friction_factor=float(friction_factor),
        assumed_velocity_m_s=float(assumed_velocity_m_s),
        pumping_duration_hours=(float(pumping_duration_hours) if pumping_duration_hours and pumping_duration_hours > 0 else None),
        energy_source=energy_source,
        grid_country=grid_country,
        grid_ef_kgco2e_per_kwh=(float(grid_ef_override) if float(grid_ef_override) > 0 else None),
    )

aeration_inputs: Optional[AerationInputs] = None
if aeration_hp > 0 and aeration_hours_per_day > 0:
    operating_hours = float(aeration_hours_per_day) * float(int(cycle_days))
    aeration_inputs = AerationInputs(
        total_aeration_hp=float(aeration_hp),
        operating_hours=operating_hours,
        motor_efficiency=float(motor_eff),
        blower_efficiency=float(blower_eff),
        energy_source=energy_source,
        grid_country=grid_country,
        grid_ef_kgco2e_per_kwh=(float(grid_ef_override) if float(grid_ef_override) > 0 else None),
    )

luluc_inputs: Optional[LulucInputs] = None
if include_luluc and luluc_area_ha > 0:
    luluc_inputs = LulucInputs(
        soil_type=soil_type,
        area_ha=float(luluc_area_ha),
        years_since_conversion=float(land_use_years),
        cycle_days=int(cycle_days),
        amortization_years=int(amort_years),
    )

system_type = "semi_intensive"
if include_pond_ghg:
    system_type = st.selectbox(
        "Farming intensity (for CH4/N2O defaults)",
        ["extensive", "semi_intensive", "intensive"],
        index=1
    )

pond_ghg_inputs: Optional[PondGHGInputs] = None
if include_pond_ghg and luluc_area_ha > 0:
    tom_summary = None
    if pond_method_tier == "tier2_tom_scaled":
        # If p90/coverage inputs are left at 0, treat as missing
        from estimation.otherghg import TOMSummary
        om_avg = float(pond_om_avg) if pond_om_avg is not None and float(pond_om_avg) > 0 else 0.0
        om_p90 = float(pond_om_p90) if pond_om_p90 is not None and float(pond_om_p90) > 0 else None
        cov = float(pond_coverage_pct) if pond_coverage_pct is not None and float(pond_coverage_pct) > 0 else None
        cal_id = pond_calibration_id.strip() if isinstance(pond_calibration_id, str) and pond_calibration_id.strip() else None
        tom_summary = TOMSummary(
            om_avg_mg_l=om_avg,
            om_p90_mg_l=om_p90,
            coverage_pct=cov,
            calibration_model_id=cal_id,
        )

    pond_ghg_inputs = PondGHGInputs(
        pond_area_m2=float(luluc_area_ha) * 10000.0,  # ha -> m2
        system_type=system_type,
        method_tier=pond_method_tier,
        tom=tom_summary,
    )

inputs = EstimatorInputs(
    harvested_shrimp_kg=float(harvested_kg),
    period="cycle",
    cycle_days=int(cycle_days),
    boundary=str(boundary),
    pumping=pumping_inputs,
    aeration=aeration_inputs,
    feed_input_mode=("total" if feed_input_mode == "Total feed (kg)" else "fcr"),
    total_feed_kg=float(total_feed_kg) if (total_feed_kg is not None and float(total_feed_kg) > 0) else None,
    fcr=float(fcr) if (fcr is not None and float(fcr) >= 0) else None,
    feed_emission_intensity_kgco2e_per_kg=(None if use_method_default_feed_ef else float(feed_ef)),
    seed_thousand_pl=float(seed_kpl) if seed_kpl > 0 else None,
    seed_emission_intensity_kgco2e_per_thousand_pl=float(seed_ef),
    luluc=luluc_inputs,
    sequestration=None,
    pond_ghg=pond_ghg_inputs,
    mrv_metadata={
        "grid_ef_source": grid_ef_source.strip() or None,
        "grid_ef_override": (float(grid_ef_override) if float(grid_ef_override) > 0 else None),
        "feed_ef_source": feed_ef_source.strip() or None,
        "seed_ef_source": seed_ef_source.strip() or None,
        "pumping_method": pumping_method,
    },
)

st.divider()
run = st.button("Calculate footprint", type="primary", disabled=(harvested_kg <= 0))

if run:
    try:
        result = estimate(inputs)
        st.success("Calculated")

        total_kg = float(result["total_kgco2e"])
        total_t = total_kg / 1000.0

        m1, m2, m3 = st.columns(3)
        m1.metric("Total emissions", f"{total_kg:,.0f} kgCO2e ({total_t:,.2f} tCO2e)")
        m2.metric("Intensity (kgCO2e/kg shrimp)", f"{result['intensity_kgco2e_per_kg_shrimp']:.4f}")
        m3.metric("Harvested", f"{float(harvested_kg):,.0f} kg")

        st.subheader("Breakdown")
        # Present both kg and tons with comma formatting
        breakdown = result["breakdown_kgco2e"]
        rows = []
        for k, v in breakdown.items():
            vv = float(v)
            rows.append({"component": k, "kgCO2e": f"{vv:,.0f}", "tCO2e": f"{(vv/1000.0):,.2f}"})
        st.table(rows)
        st.caption("Underlying values in kgCO2e are still available in the JSON export below.")

        st.subheader("Breakdown (raw kgCO2e JSON)")
        st.json(breakdown)

        st.subheader("Inputs (resolved)")
        st.json(result.get("inputs", {}))

        st.download_button(
            "Download result JSON",
            data=json.dumps(result, indent=2),
            file_name="footprint_result.json",
            mime="application/json",
        )
    except Exception as e:
        st.error(f"Calculation error: {e}")
