"""
A picture of a terrain, drawn from the terrain.

The mockups this follows put a photograph of a mountain valley on each terrain
card. A photograph of somewhere else, captioned as BASIN-03, is the one thing
this project cannot do: it would be a picture of a place that does not exist,
presented as a record of one that does.

So the card carries the terrain instead. Every quad below is one real cell,
lifted by its own recorded elevation, tinted by its own recorded cover density,
and coloured as water where the terrain records water. It is the same grid the
observation deck walks through and the same grid the hub thumbnails draw, seen
from an angle. Nothing here is illustrated.

Python 3.9 compatible.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load(terrain: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(ROOT, terrain, "viewer", "world.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except ValueError:
        return None


def isometric(terrain: str, w: int = 330, h: int = 150, target_cols: int = 56) -> str:
    """The terrain as a lit heightfield, drawn back to front."""
    world = _load(terrain)
    if not world or not world.get("cells"):
        return ('<div class="snapshot none">no exported terrain yet</div>')

    cells = world["cells"]
    cols = int(world.get("field_width") or 0) or len(cells)
    rows = max(1, len(cells) // max(1, cols))

    by_index = {}
    for c in cells:
        by_index[c.get("index", 0)] = c

    step = max(1, int(round(cols / float(target_cols))))
    sc = max(1, cols // step)
    sr = max(1, rows // step)

    elevs = [c.get("elevation") for c in cells if c.get("elevation") is not None]
    lo, hi = (min(elevs), max(elevs)) if elevs else (0.0, 1.0)
    span = (hi - lo) or 1.0

    # Isometric projection sized so the whole field lands inside the box.
    tile_w = w / float(sc + sr) * 1.9
    tile_h = tile_w * 0.5
    lift = h * 0.30
    ox = w / 2.0
    oy = h * 0.30

    def project(cx: float, cy: float, e: float) -> Tuple[float, float]:
        x = ox + (cx - cy) * tile_w / 2.0
        y = oy + (cx + cy) * tile_h / 2.0 - ((e - lo) / span) * lift
        return x, y

    quads = []
    # Back to front, so nearer ground covers the ground behind it.
    for ry in range(sr):
        for rx in range(sc):
            idx = (ry * step) * cols + (rx * step)
            c = by_index.get(idx)
            if c is None:
                continue
            e = c.get("elevation")
            if e is None:
                e = lo
            land = c.get("land", True)
            cover = min(1.0, float(c.get("cover", 0.0) or 0.0))
            shade = 0.24 + ((e - lo) / span) * 0.62
            if land is False:
                # water: recorded, not decided here
                col = "rgb(%d,%d,%d)" % (int(38 + shade * 40), int(78 + shade * 60),
                                         int(120 + shade * 70))
            elif cover > 0.02:
                g = 0.30 + cover * 0.60
                col = "rgb(%d,%d,%d)" % (int(52 * shade * 2 * g), int(150 * shade * 1.6 * g),
                                         int(62 * shade * 2 * g))
            else:
                col = "rgb(%d,%d,%d)" % (int(126 * shade), int(134 * shade), int(112 * shade))
            p0 = project(rx, ry, e)
            p1 = project(rx + 1, ry, e)
            p2 = project(rx + 1, ry + 1, e)
            p3 = project(rx, ry + 1, e)
            quads.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" '
                         'fill="%s"/>'
                         % (p0[0], p0[1], p1[0], p1[1], p2[0], p2[1], p3[0], p3[1], col))

    return ('<svg viewBox="0 0 %d %d" class="snapshot" role="img" '
            'aria-label="%s drawn from its own elevation and cover, %d cells">'
            '<rect width="%d" height="%d" fill="#070906"/>%s</svg>'
            % (w, h, terrain.upper(), len(cells), w, h, "".join(quads)))


CSS = """
.snapshot{width:100%;height:auto;display:block;border:1px solid #1D231B}
.snapshot.none{display:grid;place-items:center;height:110px;color:#4E574C;
font:10.5px ui-monospace,monospace;font-style:italic}
"""
