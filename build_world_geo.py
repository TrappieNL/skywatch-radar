"""Build globally reusable, small geographic tiles for the radar Canvas.

Natural Earth data is public domain.  The tiles deliberately contain linework
only: a radar needs coastlines, land borders and lake shorelines, not filled
map polygons.  The browser loads only the tiles around its current centre.
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path


TILE_DEGREES = 10
ROOT = Path("www/skywatch-world")
SOURCES = {
    "coastlines": (Path("ne_50m_coastline.geojson"), 0.025),
    "borders": (Path("ne_50m_admin_0_boundary_lines_land.geojson"), 0.04),
    "lakes": (Path("ne_10m_lakes.geojson"), 0.035),
}


def tile_index(value: float, low: int) -> int:
    return min(int((180 - low) / TILE_DEGREES) - 1, max(0, math.floor((value - low) / TILE_DEGREES)))


def simplify(points: list[list[float]], minimum: float) -> list[list[float]]:
    """Keep a representative, radar-scale outline without a geometry library."""
    if len(points) < 3:
        return points
    output = [points[0]]
    for point in points[1:-1]:
        previous = output[-1]
        if math.hypot(point[0] - previous[0], point[1] - previous[1]) >= minimum:
            output.append(point)
    output.append(points[-1])
    return output


def geometry_lines(geometry: dict) -> list[list[list[float]]]:
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    if kind == "LineString":
        return [coordinates]
    if kind == "MultiLineString":
        return coordinates
    if kind == "Polygon":
        return coordinates
    if kind == "MultiPolygon":
        return [ring for polygon in coordinates for ring in polygon]
    return []


def clip_segment(a: list[float], b: list[float], xmin: float, ymin: float, xmax: float, ymax: float) -> tuple[list[float], list[float]] | None:
    x0, y0 = a
    x1, y1 = b
    dx, dy = x1 - x0, y1 - y0
    lower, upper = 0.0, 1.0
    for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
        if p == 0:
            if q < 0:
                return None
            continue
        value = q / p
        if p < 0:
            if value > upper:
                return None
            lower = max(lower, value)
        else:
            if value < lower:
                return None
            upper = min(upper, value)
    return ([round(x0 + lower * dx, 4), round(y0 + lower * dy, 4)], [round(x0 + upper * dx, 4), round(y0 + upper * dy, 4)])


def add_segment(tiles: dict[tuple[int, int], dict[str, list]], layer: str, a: list[float], b: list[float]) -> None:
    """Clip a segment into every world tile it crosses, including the date line."""
    x0, y0 = a
    x1, y1 = b
    if x1 - x0 > 180:
        x1 -= 360
    elif x1 - x0 < -180:
        x1 += 360
    for shift in (-360, 0, 360):
        start, end = [x0 + shift, y0], [x1 + shift, y1]
        left, right = max(-180, min(start[0], end[0])), min(180, max(start[0], end[0]))
        bottom, top = max(-90, min(start[1], end[1])), min(90, max(start[1], end[1]))
        if left > right or bottom > top:
            continue
        for lat_index in range(tile_index(bottom, -90), tile_index(top, -90) + 1):
            for lon_index in range(tile_index(left, -180), tile_index(right, -180) + 1):
                xmin, ymin = -180 + lon_index * TILE_DEGREES, -90 + lat_index * TILE_DEGREES
                clipped = clip_segment(start, end, xmin, ymin, xmin + TILE_DEGREES, ymin + TILE_DEGREES)
                if clipped:
                    tiles.setdefault((lat_index, lon_index), {"borders": [], "coastlines": [], "lakes": []})[layer].append(clipped)


def add_source(tiles: dict[tuple[int, int], dict[str, list]], layer: str, source: Path, tolerance: float) -> None:
    for feature in json.loads(source.read_text(encoding="utf-8")).get("features", []):
        properties = feature.get("properties", {})
        # Natural Earth 10m has very many tiny lakes.  This keeps lakes useful
        # at radar scale while retaining named regional and major water bodies.
        if layer == "lakes" and source.name != "markermeer.geojson" and float(properties.get("scalerank", 10)) > 5:
            continue
        for line in geometry_lines(feature.get("geometry") or {}):
            points = simplify([[float(point[0]), float(point[1])] for point in line if len(point) >= 2], tolerance)
            for start, end in zip(points, points[1:]):
                add_segment(tiles, layer, start, end)


def main() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)
    tiles: dict[tuple[int, int], dict[str, list]] = {}
    for layer, (source, tolerance) in SOURCES.items():
        add_source(tiles, layer, source, tolerance)
    # Markermeer is absent from Natural Earth at this scale; retain the prior,
    # locally compiled OSM shoreline so the Dutch radar keeps its detail.
    add_source(tiles, "lakes", Path("markermeer.geojson"), 0.01)
    for (lat_index, lon_index), tile in tiles.items():
        if not any(tile.values()):
            continue
        (ROOT / f"{lat_index}_{lon_index}.json").write_text(
            json.dumps(tile, separators=(",", ":")), encoding="utf-8"
        )
    (ROOT / "manifest.json").write_text(
        json.dumps({"tile_degrees": TILE_DEGREES, "source": "Natural Earth coastline/admin borders/lakes; Markermeer © OpenStreetMap contributors (ODbL)", "license": "Natural Earth public domain; cartographic reference only"}, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Wrote {len(list(ROOT.glob('*.json'))) - 1} populated world tiles to {ROOT}")


if __name__ == "__main__":
    main()
