from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from shapely.geometry import Polygon
from shapely.validation import explain_validity
from pyproj import Geod

WGS84_GEOD = Geod(ellps="WGS84")

LonLat = Tuple[float, float]

@dataclass(frozen=True)
class PolygonInfo:
    polygon: Polygon
    area_m2: float
    area_ha: float
    centroid_lon: float
    centroid_lat: float


def polygon_from_lonlat(coords: List[LonLat]) -> PolygonInfo:
    """Create a polygon from (lon, lat) coordinates in EPSG:4326 and compute geodesic area."""
    if len(coords) < 3:
        raise ValueError("Polygon needs at least 3 coordinate pairs (lon, lat).")

    # Ensure closed ring
    ring = coords[:]
    if ring[0] != ring[-1]:
        ring.append(ring[0])

    poly = Polygon(ring)
    if not poly.is_valid:
        raise ValueError(f"Invalid polygon: {explain_validity(poly)}")

    area_m2 = abs(WGS84_GEOD.geometry_area_perimeter(poly)[0])
    area_ha = area_m2 / 10_000.0
    c = poly.centroid
    return PolygonInfo(
        polygon=poly,
        area_m2=area_m2,
        area_ha=area_ha,
        centroid_lon=float(c.x),
        centroid_lat=float(c.y),
    )
