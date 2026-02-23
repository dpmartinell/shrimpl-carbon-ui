from __future__ import annotations

import json
import io
import datetime as _dt
from typing import List, Tuple, Optional

import streamlit as st

import pandas as pd
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet

from estimation.estimator import EstimatorInputs, estimate
from estimation.Water_exchange_estimation import PumpingModelInputs, EnergySource, GRID_COUNTRIES
from estimation.Aeration_energy import AerationInputs
from estimation.FeedEmissions import DEFAULT_FEED_EF_A, DEFAULT_SEED_EF_A
from estimation.LULUC import LulucInputs
from estimation.Carbon_Sequestration import SequestrationInputs
from estimation.land_cover import LandCoverClass, DEFAULT_LAND_COVER_CLASSES
from estimation.connectors.land_cover_io import (
    land_cover_from_csv_bytes,
    land_cover_from_json_bytes,
)
from estimation.otherghg import PondGHGInputs

from ui.geo_utils import polygon_from_lonlat
from ui.soilgrids_wcs import fetch_soc_for_bbox_mean, DEFAULT_SOC_WCS_MAP

st.set_page_config(page_title="Shrimpl Carbon Footprint Prototype", layout="wide")
st.title("Shrimpl Carbon Footprint Prototype (Cycle-based)")

st.caption(
    "Enter cycle inputs and a pond/farm polygon. The app computes area and can try to fetch SoilGrids SOC via WCS "
    "(best-effort). If SoilGrids is unreachable, select soil type / SOC manually."
)


def _make_pie_chart(breakdown: dict) -> plt.Figure:
    """Pie chart of positive contributions only (kgCO2e).

    Negative components (removals) are excluded from the pie to avoid misleading
    charts (pie charts require non-negative magnitudes). Removals are displayed
    separately in tables/notes.
    """
    # Avoid double-counting helper lines
    items = [(k, float(v)) for k, v in breakdown.items() if not (str(k).endswith("_emissions") or str(k).endswith("_removals"))]
    pos = [(k, v) for k, v in items if v > 0]
    if not pos:
        fig = plt.figure(figsize=(6, 4))
        plt.text(0.5, 0.5, "No positive emissions to plot", ha="center", va="center")
        plt.axis("off")
        return fig

    labels = [k for k, _ in pos]
    values = [v for _, v in pos]
    fig = plt.figure(figsize=(7, 4.5))
    plt.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    plt.title("Contribution by component (gross emissions)")
    plt.tight_layout()
    return fig


def _build_pdf_report(result: dict, pie_fig: plt.Figure) -> bytes:
    """Create a clean PDF report (bytes) suitable for sharing/audit packages."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Shrimpl Carbon Footprint Report", styles["Title"]))
    story.append(Paragraph(f"Generated: {_dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
    story.append(Spacer(1, 0.4 * cm))

    total_kg = float(result["total_kgco2e"])
    intensity = float(result["intensity_kgco2e_per_kg_shrimp"])
    harvested = float(result.get("inputs", {}).get("feed", {}).get("harvested_shrimp_kg", result.get("harvested_shrimp_kg", 0.0)) or 0.0)
    harvested = float(result.get("inputs", {}).get("harvested_shrimp_kg", result.get("harvested_shrimp_kg", 0.0)) or 0.0)
    # If not present, the UI already displays harvested; keep report robust
    story.append(Paragraph("Summary", styles["Heading2"]))
    summary_tbl = Table(
        [
            ["Total emissions", f"{total_kg:,.0f} kgCO2e ({total_kg/1000.0:,.2f} tCO2e)"],
            ["Intensity", f"{intensity:,.4f} kgCO2e/kg shrimp"],
            ["Reporting period", str(result.get("period"))],
            ["Cycle days", str(result.get("cycle_days") or "-")],
            ["Boundary", str(result.get("boundary"))],
        ],
        colWidths=[5 * cm, 10.5 * cm],
    )
    summary_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(summary_tbl)
    story.append(Spacer(1, 0.5 * cm))

    # Tier classification (MRV)
    tiers = result.get("tiers") or {}
    if isinstance(tiers, dict) and len(tiers) > 0:
        story.append(Paragraph("Data quality & tier classification", styles["Heading2"]))
        tdata = [["Component", "Tier", "Data source", "Method"]]
        for comp, info in tiers.items():
            if not isinstance(info, dict):
                continue
            tdata.append(
                [
                    str(comp),
                    str(info.get("tier", "")),
                    str(info.get("data_source", "")),
                    str(info.get("method", "")),
                ]
            )
        tt = Table(tdata, colWidths=[3.2 * cm, 3.0 * cm, 4.8 * cm, 5.5 * cm])
        tt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                    ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(tt)
        story.append(Spacer(1, 0.5 * cm))

    # Pie chart image
    img_buf = io.BytesIO()
    pie_fig.savefig(img_buf, format="png", dpi=180, bbox_inches="tight")
    img_buf.seek(0)
    story.append(Paragraph("Component contributions", styles["Heading2"]))
    story.append(RLImage(img_buf, width=16 * cm, height=9 * cm))
    story.append(Spacer(1, 0.5 * cm))

    # Breakdown table
    story.append(Paragraph("Breakdown", styles["Heading2"]))
    breakdown = result["breakdown_kgco2e"]
    data = [["Component", "kgCO2e", "tCO2e"]]
    for k, v in breakdown.items():
        vv = float(v)
        data.append([k, f"{vv:,.0f}", f"{vv/1000.0:,.2f}"])
    bt = Table(data, colWidths=[6 * cm, 5 * cm, 4.5 * cm])
    bt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(bt)
    story.append(Spacer(1, 0.4 * cm))

    # Explicit removals / sequestration section
    inputs = result.get("inputs") or {}
    land_cover_info = inputs.get("land_cover") if isinstance(inputs, dict) else None
    if isinstance(land_cover_info, dict) and (
        land_cover_info.get("total_removals_kgco2e") is not None or land_cover_info.get("total_emissions_kgco2e") is not None
    ):
        story.append(Paragraph("Land-cover emissions & removals", styles["Heading2"]))
        lc_em = float(land_cover_info.get("total_emissions_kgco2e") or 0.0)
        lc_rm = float(land_cover_info.get("total_removals_kgco2e") or 0.0)
        lc_net = float(result.get("breakdown_kgco2e", {}).get("land_cover_net", 0.0) or 0.0)
        lct = Table(
            [
                ["Land-cover emissions", f"{lc_em:,.0f} kgCO2e", f"{lc_em/1000.0:,.2f} tCO2e"],
                ["Land-cover removals", f"{lc_rm:,.0f} kgCO2e", f"{lc_rm/1000.0:,.2f} tCO2e"],
                ["Land-cover net", f"{lc_net:,.0f} kgCO2e", f"{lc_net/1000.0:,.2f} tCO2e"],
            ],
            colWidths=[6 * cm, 5 * cm, 4.5 * cm],
        )
        lct.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                    ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ]
            )
        )
        story.append(lct)
        story.append(Spacer(1, 0.4 * cm))

        classes_used = land_cover_info.get("classes_used")
        if isinstance(classes_used, list) and len(classes_used) > 0:
            story.append(Paragraph("Land-cover classes used", styles["Heading3"]))
            cdata = [["Class", "Area (ha)", "Net flux (kgCO2e/ha/year)", "Tier", "Source"]]
            for c in classes_used:
                if not isinstance(c, dict):
                    continue
                cdata.append(
                    [
                        str(c.get("class_name", "")),
                        f"{float(c.get('area_ha', 0.0) or 0.0):,.2f}",
                        f"{float(c.get('net_flux_kgco2e_per_ha_year', 0.0) or 0.0):,.0f}",
                        str(c.get("tier", "") or ""),
                        str(c.get("factor_source", "") or ""),
                    ]
                )
            ct = Table(cdata, colWidths=[4.2 * cm, 2.6 * cm, 4.0 * cm, 2.2 * cm, 3.0 * cm])
            ct.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                        ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (1, 1), (2, -1), "RIGHT"),
                    ]
                )
            )
            story.append(ct)
            story.append(Spacer(1, 0.4 * cm))

    # Data provenance (optional)
    mrv_meta = (inputs.get("mrv_metadata") if isinstance(inputs, dict) else None) or {}
    if isinstance(mrv_meta, dict) and len(mrv_meta) > 0:
        story.append(Paragraph("Data provenance", styles["Heading2"]))
        pdata = [["Field", "Value"]]
        for k, v in mrv_meta.items():
            pdata.append([str(k), str(v)])
        pt = Table(pdata, colWidths=[5 * cm, 10.5 * cm])
        pt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                    ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(pt)
        story.append(Spacer(1, 0.4 * cm))

    # Notes about removals
    neg = {k: float(v) for k, v in breakdown.items() if float(v) < 0}
    if neg:
        story.append(Paragraph("Notes", styles["Heading2"]))
        story.append(
            Paragraph(
                "Some components are negative (removals). These are excluded from the pie chart and shown in the breakdown table.",
                styles["Normal"],
            )
        )

    doc.build(story)
    return buf.getvalue()

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


st.divider()
st.subheader("Land cover carbon balance (optional)")
include_land_cover = st.checkbox(
    "Include land-cover net flux (non-pond areas)",
    value=False,
    help=(
        "Use this for vegetation/land classes within the project boundary (e.g., mangrove co-production areas, "
        "buffer vegetation, infrastructure). Enter areas and net flux factors in kgCO2e/ha/year (negative = removals)."
    ),
)

if "land_cover_df" not in st.session_state:
    # Initialize from defaults
    st.session_state.land_cover_df = pd.DataFrame(
        [
            {
                "class_name": c.class_name,
                "area_ha": float(c.area_ha),
                "net_flux_kgco2e_per_ha_year": float(c.net_flux_kgco2e_per_ha_year),
                "tier": c.tier or "",
                "factor_source": c.factor_source or "",
                "notes": c.notes or "",
            }
            for c in DEFAULT_LAND_COVER_CLASSES
        ]
    )

land_cover_classes: Optional[list[LandCoverClass]] = None
if include_land_cover:
    st.markdown("**Import from GIS / databases (optional)**")
    uploaded_lc = st.file_uploader(
        "Upload land-cover summary (CSV or JSON)",
        type=["csv", "json"],
        help=(
            "Expected columns: class_name, area_ha. Optional: net_flux_kgco2e_per_ha_year, tier, factor_source, notes. "
            "This is designed to accept GIS outputs (e.g., a table summarized by class)."
        ),
    )

    if uploaded_lc is not None:
        try:
            raw = uploaded_lc.getvalue()
            if uploaded_lc.name.lower().endswith(".csv"):
                imp = land_cover_from_csv_bytes(
                    raw,
                    default_flux_kgco2e_per_ha_year=0.0,
                    source="external_upload",
                    notes=f"Uploaded file: {uploaded_lc.name}",
                )
            else:
                imp = land_cover_from_json_bytes(
                    raw,
                    default_flux_kgco2e_per_ha_year=0.0,
                    source="external_upload",
                    notes=f"Uploaded file: {uploaded_lc.name}",
                )

            # Merge imported areas into the editable table, preserving existing flux factors where names match.
            existing = st.session_state.land_cover_df.copy()
            existing["_key"] = existing["class_name"].astype(str).str.strip().str.lower()
            imp_df = pd.DataFrame(
                [
                    {
                        "class_name": c.class_name,
                        "area_ha": c.area_ha,
                        "net_flux_kgco2e_per_ha_year": c.net_flux_kgco2e_per_ha_year,
                        "tier": c.tier or "",
                        "factor_source": c.factor_source or "",
                        "notes": c.notes or "",
                        "_key": c.class_name.strip().lower(),
                    }
                    for c in imp.classes
                ]
            )

            merged = imp_df.merge(
                existing[["_key", "net_flux_kgco2e_per_ha_year", "tier", "factor_source", "notes"]],
                on="_key",
                how="left",
                suffixes=("", "_old"),
            )

            # Prefer imported flux if provided (non-zero or explicitly present); else keep previous.
            def _pick(row):
                v = row.get("net_flux_kgco2e_per_ha_year")
                old = row.get("net_flux_kgco2e_per_ha_year_old")
                if pd.isna(v):
                    return float(old) if not pd.isna(old) else 0.0
                return float(v)

            merged["net_flux_kgco2e_per_ha_year"] = merged.apply(_pick, axis=1)
            merged["tier"] = merged["tier"].fillna(merged["tier_old"]).fillna("")
            merged["factor_source"] = merged["factor_source"].fillna(merged["factor_source_old"]).fillna("")
            merged["notes"] = merged["notes"].fillna(merged["notes_old"]).fillna("")

            st.session_state.land_cover_df = merged[
                ["class_name", "area_ha", "net_flux_kgco2e_per_ha_year", "tier", "factor_source", "notes"]
            ]

            st.session_state.land_cover_import_meta = imp.provenance

            if imp.warnings:
                st.warning("; ".join(imp.warnings))
            st.success("Land-cover areas imported. Review/edit factors before running estimation.")
        except Exception as e:
            st.error(f"Failed to import land-cover table: {e}")

    st.caption(
        "Edit the table freely (add/remove rows). Net flux factor sign convention: positive = emissions, negative = removals. "
        "These factors must be validated per MRV program."
    )
    edited = st.data_editor(
        st.session_state.land_cover_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "class_name": st.column_config.TextColumn("Class name", required=True),
            "area_ha": st.column_config.NumberColumn("Area (ha)", min_value=0.0, step=0.1),
            "net_flux_kgco2e_per_ha_year": st.column_config.NumberColumn(
                "Net flux (kgCO2e/ha/year)",
                help="Negative values represent removals/sequestration.",
                step=100.0,
            ),
            "tier": st.column_config.TextColumn("Tier"),
            "factor_source": st.column_config.TextColumn("Factor source"),
            "notes": st.column_config.TextColumn("Notes"),
        },
    )
    st.session_state.land_cover_df = edited

    # Export current table for re-use in GIS workflows
    out_csv = st.session_state.land_cover_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download current land-cover table (CSV)",
        data=out_csv,
        file_name="land_cover_table.csv",
        mime="text/csv",
        help="Use this as a template or to share factors/areas with other tools.",
    )

    # Convert to model inputs (ignore blank/invalid rows)
    land_cover_classes = []
    for _, r in edited.iterrows():
        name = str(r.get("class_name", "")).strip()
        if not name:
            continue
        area = float(r.get("area_ha", 0.0) or 0.0)
        flux = float(r.get("net_flux_kgco2e_per_ha_year", 0.0) or 0.0)
        land_cover_classes.append(
            LandCoverClass(
                class_name=name,
                area_ha=area,
                net_flux_kgco2e_per_ha_year=flux,
                tier=str(r.get("tier", "")).strip() or None,
                factor_source=str(r.get("factor_source", "")).strip() or None,
                notes=str(r.get("notes", "")).strip() or None,
            )
        )

    # Helpful totals
    total_lc_area = sum(c.area_ha for c in land_cover_classes)
    st.write(f"Total land-cover area entered: **{total_lc_area:,.2f} ha**")


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
    land_cover_classes=land_cover_classes,
    pond_ghg=pond_ghg_inputs,
    mrv_metadata={
        "grid_ef_source": grid_ef_source.strip() or None,
        "grid_ef_override": (float(grid_ef_override) if float(grid_ef_override) > 0 else None),
        "feed_ef_source": feed_ef_source.strip() or None,
        "seed_ef_source": seed_ef_source.strip() or None,
        "pumping_method": pumping_method,
        "land_cover_import": st.session_state.get("land_cover_import_meta"),
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

        st.subheader("Contribution chart")
        pie_fig = _make_pie_chart(breakdown)
        st.pyplot(pie_fig, clear_figure=False)

        # PDF report
        pdf_bytes = _build_pdf_report(result, pie_fig)
        st.download_button(
            "Download PDF report",
            data=pdf_bytes,
            file_name="shrimpl_carbon_report.pdf",
            mime="application/pdf",
        )

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
