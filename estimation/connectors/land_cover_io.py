from __future__ import annotations

import json
import io
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..land_cover import LandCoverClass


@dataclass(frozen=True)
class LandCoverImportResult:
    classes: List[LandCoverClass]
    provenance: Dict[str, Any]
    warnings: List[str]


def land_cover_from_dataframe(
    df: pd.DataFrame,
    *,
    default_flux_kgco2e_per_ha_year: float = 0.0,
    source: str = "external",
    model_version: Optional[str] = None,
    notes: Optional[str] = None,
) -> LandCoverImportResult:
    """Convert a tabular land-cover summary into internal LandCoverClass inputs.

    Expected columns (case-insensitive):
      - class_name (or class, land_cover)
      - area_ha (or area)
    Optional columns:
      - net_flux_kgco2e_per_ha_year (or net_flux)
      - tier
      - factor_source
      - notes

    This is designed for GIS outputs such as:
      - PostGIS summary tables
      - QGIS 'Group Stats'
      - Satellite classification summaries
    """
    warnings: List[str] = []
    cols = {c.lower().strip(): c for c in df.columns}

    def _pick(*names: str) -> Optional[str]:
        for n in names:
            if n in cols:
                return cols[n]
        return None

    c_name = _pick("class_name", "class", "land_cover", "landcover")
    c_area = _pick("area_ha", "area", "ha")
    c_flux = _pick("net_flux_kgco2e_per_ha_year", "net_flux", "flux")
    c_tier = _pick("tier")
    c_src = _pick("factor_source", "source")
    c_notes = _pick("notes")

    if c_name is None or c_area is None:
        raise ValueError("Land-cover import requires columns: class_name and area_ha (or equivalents).")

    out: List[LandCoverClass] = []
    for _, r in df.iterrows():
        name = str(r.get(c_name, "")).strip()
        if not name:
            continue
        try:
            area = float(r.get(c_area, 0.0) or 0.0)
        except Exception:
            warnings.append(f"Invalid area for class '{name}', set to 0.")
            area = 0.0

        flux = default_flux_kgco2e_per_ha_year
        if c_flux is not None:
            try:
                flux = float(r.get(c_flux, default_flux_kgco2e_per_ha_year) or default_flux_kgco2e_per_ha_year)
            except Exception:
                warnings.append(f"Invalid flux for class '{name}', using default {default_flux_kgco2e_per_ha_year}.")

        out.append(
            LandCoverClass(
                class_name=name,
                area_ha=area,
                net_flux_kgco2e_per_ha_year=flux,
                tier=(str(r.get(c_tier, "")).strip() or None) if c_tier is not None else None,
                factor_source=(str(r.get(c_src, "")).strip() or None) if c_src is not None else None,
                notes=(str(r.get(c_notes, "")).strip() or None) if c_notes is not None else None,
            )
        )

    prov = {
        "source": source,
        "model_version": model_version,
        "notes": notes,
        "rows": int(len(df)),
    }
    return LandCoverImportResult(classes=out, provenance=prov, warnings=warnings)


def land_cover_from_csv_bytes(
    data: bytes,
    *,
    encoding: str = "utf-8",
    **kwargs: Any,
) -> LandCoverImportResult:
    df = pd.read_csv(io.BytesIO(data), encoding=encoding)
    return land_cover_from_dataframe(df, **kwargs)


def land_cover_from_json_bytes(
    data: bytes,
    **kwargs: Any,
) -> LandCoverImportResult:
    obj = json.loads(data.decode("utf-8"))
    if isinstance(obj, dict) and "data" in obj:
        obj = obj["data"]
    if not isinstance(obj, list):
        raise ValueError("JSON land-cover import expects a list of records.")
    df = pd.DataFrame(obj)
    return land_cover_from_dataframe(df, **kwargs)
