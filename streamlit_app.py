from __future__ import annotations

import json
from typing import List, Tuple, Optional

import streamlit as st

from estimation.estimator import EstimatorInputs, estimate
from estimation.Water_exchange_estimation import PumpingModelInputs, EnergySource
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
    cycle_days = st.number_input("Cycle length (days)", min_value=1.0, value=90.0)
    harvested_kg = st.number_input("Harvested shrimp (kg)", min_value=0.0, value=10000.0)

    st.divider()
    st.header("Energy source")
    energy_source: EnergySource = st.selectbox("Energy source", ["grid", "diesel", "petrol"])
    grid_country = st.text_input("Grid country (for kgCO2e/kWh factor lookup)", value="Ecuador")

    st.divider()
    st.header("Feed & seed (cycle totals)")
    total_feed_kg = st.number_input("Total feed used in cycle (kg)", min_value=0.0, value=15000.0)
    feed_ef = st.number_input("Feed EF (kgCO2e/kg feed)", min_value=0.0, value=float(DEFAULT_FEED_EF_A))
    seed_kpl = st.number_input("Seed (thousand PL) in cycle", min_value=0.0, value=0.0)
    seed_ef = st.number_input("Seed EF (kgCO2e / 1000 PL)", min_value=0.0, value=float(DEFAULT_SEED_EF_A))

    st.divider()
    st.header("Aeration")
    aeration_hp = st.number_input("Total aeration power (hp)", min_value=0.0, value=0.0)
    aeration_hours_per_day = st.number_input("Aeration hours/day", min_value=0.0, max_value=24.0, value=0.0)
    motor_eff = st.number_input("Motor efficiency (0-1)", min_value=0.01, max_value=1.0, value=0.90)
    blower_eff = st.number_input("Blower efficiency (0-1)", min_value=0.01, max_value=1.0, value=0.80)

    st.divider()
    st.header("Pumping / water exchange")
    pumped_volume_m3 = st.number_input("Total pumped volume over cycle (m³)", min_value=0.0, value=0.0)
    pipe_diam_m = st.number_input("Pipe diameter (m)", min_value=0.01, value=1.5)
    pipe_len_m = st.number_input("Pipe length (m)", min_value=0.0, value=100.0)
    static_head_m = st.number_input("Static head (m)", min_value=0.0, value=0.0)
    pump_eff = st.number_input("Pump efficiency (0-1)", min_value=0.01, max_value=1.0, value=0.70)
    friction_factor = st.number_input("Friction factor (dimensionless)", min_value=0.001, value=0.02)

    st.divider()
    st.header("LULUC & GHG (optional)")
    include_luluc = st.checkbox("Include LULUC", value=True)
    include_pond_ghg = st.checkbox("Include pond CH4/N2O", value=False)

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
if pumped_volume_m3 > 0:
    pumping_inputs = PumpingModelInputs(
        volume_m3=float(pumped_volume_m3),
        pipe_diameter_m=float(pipe_diam_m),
        pipe_length_m=float(pipe_len_m),
        static_head_m=float(static_head_m),
        pump_efficiency=float(pump_eff),
        friction_factor=float(friction_factor),
        energy_source=energy_source,
        grid_country=grid_country,
        cycle_days=float(cycle_days),
    )

aeration_inputs: Optional[AerationInputs] = None
if aeration_hp > 0 and aeration_hours_per_day > 0:
    operating_hours = float(aeration_hours_per_day) * float(cycle_days)
    aeration_inputs = AerationInputs(
        total_aeration_hp=float(aeration_hp),
        operating_hours=operating_hours,
        motor_efficiency=float(motor_eff),
        blower_efficiency=float(blower_eff),
        energy_source=energy_source,
        grid_country=grid_country,
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
    pond_ghg_inputs = PondGHGInputs(
        pond_area_m2=float(luluc_area_ha) * 10000.0,  # ha -> m2
        system_type=system_type,
    )

inputs = EstimatorInputs(
    harvested_shrimp_kg=float(harvested_kg),
    period="cycle",
    cycle_days=float(cycle_days),
    boundary="A",
    pumping=pumping_inputs,
    aeration=aeration_inputs,
    total_feed_kg=float(total_feed_kg) if total_feed_kg > 0 else None,
    feed_emission_intensity_kgco2e_per_kg=float(feed_ef),
    seed_thousand_pl=float(seed_kpl) if seed_kpl > 0 else None,
    seed_emission_intensity_kgco2e_per_thousand_pl=float(seed_ef),
    luluc=luluc_inputs,
    sequestration=None,
    pond_ghg=pond_ghg_inputs,
)

st.divider()
run = st.button("Calculate footprint", type="primary", disabled=(harvested_kg <= 0))

if run:
    try:
        result = estimate(inputs)
        st.success("Calculated")

        m1, m2, m3 = st.columns(3)
        m1.metric("Total emissions (kgCO2e)", f"{result['total_kgco2e']:.2f}")
        m2.metric("Intensity (kgCO2e/kg shrimp)", f"{result['intensity_kgco2e_per_kg_shrimp']:.4f}")
        m3.metric("Harvested (kg)", f"{float(harvested_kg):.0f}")

        st.subheader("Breakdown (kgCO2e)")
        st.json(result["breakdown_kgco2e"])

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
