from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple, List
import xml.etree.ElementTree as ET

import requests

# SoilGrids WCS documentation: https://docs.isric.org/globaldata/soilgrids/wcs.html
# Service catalog / map files: https://maps.isric.org/

DEFAULT_SOC_WCS_MAP = "https://maps.isric.org/mapserv?map=/map/soc.map"


@dataclass(frozen=True)
class SoilGridsSOCResult:
    coverage_id: str
    soc_mean: float
    soc_unit: str
    note: str


def _get_capabilities_xml(wcs_base_url: str, timeout_s: int = 30) -> str:
    params = {"SERVICE": "WCS", "VERSION": "2.0.0", "REQUEST": "GetCapabilities"}
    r = requests.get(wcs_base_url, params=params, timeout=timeout_s)
    r.raise_for_status()
    return r.text


def _pick_coverage_id_for_soc_stock(capabilities_xml: str) -> Optional[str]:
    """Try to pick a coverage that looks like SOC stock 0-30cm mean/median.
    SoilGrids naming can vary; we use heuristics.
    """
    root = ET.fromstring(capabilities_xml)

    # coverage IDs are usually in wcs:CoverageSummary / wcs:CoverageId
    # Namespaces vary; we match by localname.
    coverage_ids: List[str] = []
    for el in root.iter():
        if el.tag.lower().endswith("coverageid") and el.text:
            coverage_ids.append(el.text.strip())

    if not coverage_ids:
        return None

    # Prefer SOC stock 0-30cm (t/ha) if present, else SOC content 0-30cm.
    patterns = [
        r"(?i)ocs.*0-30",        # organic carbon stock
        r"(?i)soc.*stock.*0-30",
        r"(?i)soc.*0-30.*mean",
        r"(?i)soc.*0-30",
    ]
    for pat in patterns:
        for cid in coverage_ids:
            if re.search(pat, cid):
                return cid

    # fallback: any soc layer at 0-30
    for cid in coverage_ids:
        if "soc" in cid.lower() and "0-30" in cid:
            return cid

    return None


def fetch_soc_for_bbox_mean(
    bbox_lonlat: Tuple[float, float, float, float],
    *,
    wcs_base_url: str = DEFAULT_SOC_WCS_MAP,
    coverage_id: Optional[str] = None,
    resolution_deg: float = 0.0025,  # ~250m at equator (rough)
    timeout_s: int = 60,
) -> SoilGridsSOCResult:
    """Fetch SOC (best-effort) over a bounding box as a GeoTIFF and compute mean.
    NOTE: This is a *prototype* approach; for production, prefer clipping to the polygon precisely.
    """
    try:
        caps_xml = _get_capabilities_xml(wcs_base_url, timeout_s=timeout_s)
    except Exception as e:
        raise RuntimeError(f"Could not reach SoilGrids WCS service: {e}")

    if coverage_id is None:
        coverage_id = _pick_coverage_id_for_soc_stock(caps_xml)
    if not coverage_id:
        raise RuntimeError("Could not identify a SOC coverage ID from WCS GetCapabilities.")

    minx, miny, maxx, maxy = bbox_lonlat

    # WCS 2.0 GetCoverage with subsets in EPSG:4326
    params = {
        "SERVICE": "WCS",
        "VERSION": "2.0.0",
        "REQUEST": "GetCoverage",
        "COVERAGEID": coverage_id,
        "FORMAT": "image/tiff",
        # Subset parameters often accepted as SUBSET=Long(min,max)&SUBSET=Lat(min,max)
        "SUBSET": [f"Long({minx},{maxx})", f"Lat({miny},{maxy})"],
        # optional: limit size via RESX/RESY (server-dependent); we keep it simple
    }

    r = requests.get(wcs_base_url, params=params, timeout=timeout_s)
    r.raise_for_status()

    # Read GeoTIFF bytes and compute mean
    import numpy as np
    import rasterio
    from rasterio.io import MemoryFile

    with MemoryFile(r.content) as mem:
        with mem.open() as ds:
            arr = ds.read(1, masked=True)
            # avoid nodata
            if hasattr(arr, "mask"):
                data = arr.compressed()
            else:
                data = arr.flatten()
            if data.size == 0:
                raise RuntimeError("Returned coverage has no valid data in the requested bbox.")
            soc_mean = float(np.mean(data))

    return SoilGridsSOCResult(
        coverage_id=coverage_id,
        soc_mean=soc_mean,
        soc_unit="unknown (depends on coverage)",
        note="Mean computed over bbox. For a more accurate polygon-mean, clip raster to polygon.",
    )
