"""Render local county boundaries as an interactive atlas without map tile requests."""

from __future__ import annotations

import math
from html import escape

import pandas as pd

from vis._brand import COUNTY_TIER_COLORS

_WIDTH, _HEIGHT = 840, 520


def _rings(feature: dict) -> list:
    """Flatten Polygon and MultiPolygon rings from a county feature."""
    geometry = feature["geometry"]
    if geometry["type"] == "Polygon":
        return geometry["coordinates"]
    return [ring for polygon in geometry["coordinates"] for ring in polygon]


def _project(longitude: float, latitude: float) -> tuple[float, float]:
    """Project geographic coordinates with a US Albers equal area projection."""
    radians = math.pi / 180
    n = (math.sin(29.5 * radians) + math.sin(45.5 * radians)) / 2
    constant = math.cos(29.5 * radians) ** 2 + 2 * n * math.sin(29.5 * radians)
    radius = math.sqrt(max(0, constant - 2 * n * math.sin(latitude * radians))) / n
    origin = math.sqrt(constant - 2 * n * math.sin(38 * radians)) / n
    angle = n * (longitude + 96) * radians
    return radius * math.sin(angle), origin - radius * math.cos(angle)


class CountyAtlas:
    """Cache projected source rings and build a map for the requested county scope."""

    def __init__(self, frame: pd.DataFrame, geometry: dict):
        """Join county boundaries by validated FIPS and prepare display coordinates."""
        known = set(frame["county_fips"])
        features = [item for item in geometry["features"] if str(item["id"]) in known]
        self.polygons = {}
        self.states = dict(zip(frame["county_fips"], frame["practice_state"]))
        lower = [
            _project(*point[:2])
            for feature in features
            if self.states[str(feature["id"])] not in ("AK", "HI")
            for ring in _rings(feature)
            for point in ring
        ]
        xmin = min(point[0] for point in lower)
        xmax = max(point[0] for point in lower)
        ymin = min(point[1] for point in lower)
        ymax = max(point[1] for point in lower)
        scale = min(790 / (xmax - xmin), 420 / (ymax - ymin))

        for feature in features:
            fips = str(feature["id"])
            state = self.states[fips]
            rings = []
            for ring in _rings(feature):
                points = []
                for longitude, latitude, *_ in ring:
                    if state == "AK":
                        longitude = longitude - 360 if longitude > 0 else longitude
                        point = ((longitude + 180) * 3.1 + 25, (72 - latitude) * 3.1 + 368)
                    elif state == "HI":
                        point = ((longitude + 161) * 17 + 235, (23 - latitude) * 17 + 413)
                    else:
                        x, y = _project(longitude, latitude)
                        point = ((x - xmin) * scale + 25, 25 + (ymax - y) * scale)
                    # Discard subpixel detail while preserving each geographic ring.
                    if not points or math.dist(point, points[-1]) >= 0.45:
                        points.append(point)
                if len(points) >= 3:
                    rings.append(points)
            self.polygons[fips] = rings

    def render(self, frame: pd.DataFrame, state: str | None = None) -> str:
        """Return escaped SVG county paths for a dynamic dataset, including US insets.

        State views fit the complete state's boundaries before tier filtering so
        changing the tier does not change the user's geographic reference.
        """
        if frame.empty:
            return ""
        viewbox = f"0 0 {_WIDTH} {_HEIGHT}"
        if state:
            points = [
                point
                for fips, rings in self.polygons.items()
                if self.states[fips] == state
                for ring in rings
                for point in ring
            ]
            if points:
                xmin = min(point[0] for point in points)
                xmax = max(point[0] for point in points)
                ymin = min(point[1] for point in points)
                ymax = max(point[1] for point in points)
                pad = max(xmax - xmin, ymax - ymin) * 0.08
                viewbox = f"{xmin-pad:.2f} {ymin-pad:.2f} {xmax-xmin+2*pad:.2f} {ymax-ymin+2*pad:.2f}"
        paths = []
        for row in frame.itertuples():
            path = "".join(
                "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in ring) + "Z"
                for ring in self.polygons.get(row.county_fips, [])
            )
            label = escape(
                f"{row.county_name}: {row.provider_count:g} registered providers, "
                f"{row.providers_per_100k:.2f} per 100,000 residents",
                quote=True,
            )
            paths.append(
                f'<path data-fips="{row.county_fips}" d="{path}" '
                f'fill="{COUNTY_TIER_COLORS[row.risk_tier]}" '
                f'vector-effect="non-scaling-stroke"><title>{label}</title></path>'
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" '
            'preserveAspectRatio="xMidYMid meet" role="img" '
            'aria-label="County provider supply map. Use county search or the list to select a county by keyboard.">'
            + "".join(paths) + "</svg>"
        )
