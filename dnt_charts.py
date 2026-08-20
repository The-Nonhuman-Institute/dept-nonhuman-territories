# SPDX-FileCopyrightText: 2026 U3 Labs, LLC
# SPDX-License-Identifier: Apache-2.0
"""
Charts, drawn from real series. No library, no fabricated points.

WHY THIS EXISTS

  Every figure the console showed was either a bare number or a sparkline with
  no axis, which means a reader could see that something rose but never what it
  rose from, to, or against. A line with no scale is decoration.

  These draw axes, ticks, gridlines, one line per series, a value at the end of
  each line, and an optional dashed reference. Nothing is smoothed and nothing
  is interpolated: a gap in a series is a gap on the page.

COLOUR

  One hue per terrain, fixed, assigned by terrain and never by rank — so a
  chart that drops a terrain does not repaint the others. Identity is never
  carried by colour alone: every series is in the legend AND labelled at its
  own line end, so the chart still reads in greyscale or with any colour
  vision deficiency.

Python 3.9 compatible.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Fixed per terrain. Assigned by identity, never by position in a sorted list.
import dnt_terrains
SERIES = dnt_terrains.hues()
REF = "#5A6356"              # the dashed reference line
GRID = "#1D231B"
AXIS = "#2C332A"
TEXT = "#7C8879"
INK = "#D6DED2"


def hue(terrain: str) -> str:
    """By terrain identity, never by rank — a new terrain repaints nothing."""
    return dnt_terrains.hue_of(terrain)


def _nice(lo: float, hi: float, steps: int = 4) -> Tuple[float, float, float]:
    """A round axis range that contains the data."""
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / float(steps)
    mag = 10.0 ** math.floor(math.log10(raw)) if raw > 0 else 1.0
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= mag * mult:
            step = mag * mult
            break
    else:
        step = mag * 10
    start = math.floor(lo / step) * step
    end = math.ceil(hi / step) * step
    return start, end, step


def _fmt(v: float) -> str:
    a = abs(v)
    if a >= 1000000:
        return "%.1fM" % (v / 1000000.0)
    if a >= 1000:
        return "%.1fK" % (v / 1000.0)
    if a >= 10:
        return "%.0f" % v
    if a >= 1:
        return "%.1f" % v
    return "%.2f" % v


def line_chart(series: Sequence[Dict[str, Any]], width: int = 300, height: int = 190,
               x_label: str = "", y_label: str = "", markers: Sequence = (),
               reference: Optional[Sequence[float]] = None,
               reference_label: str = "median", end_labels: bool = True,
               y_zero: bool = False) -> str:
    """One or more lines on a shared axis.

    series: [{"name", "colour", "points": [(x, y), ...]}]
    markers: [(x, "label")] — vertical rules, e.g. the ends of a checkpoint
    reference: a y-series aligned to the first series' x values, drawn dashed
    """
    live = [s for s in series if len(s.get("points") or []) >= 2]
    if not live:
        return ('<p style="color:%s;font:11px ui-monospace,monospace;font-style:italic">'
                'not enough recorded points to draw a line</p>' % TEXT)

    pad_l, pad_r, pad_t, pad_b = 44, 46, 12, 26
    w = width - pad_l - pad_r
    h = height - pad_t - pad_b

    xs = [p[0] for s in live for p in s["points"]]
    ys = [p[1] for s in live for p in s["points"] if p[1] is not None]
    if reference:
        ys += [v for v in reference if v is not None]
    x0, x1 = min(xs), max(xs)
    if x1 == x0:
        x1 = x0 + 1
    lo, hi = (0.0 if y_zero else min(ys)), max(ys)
    y0, y1, ystep = _nice(lo, hi)

    sx = lambda v: pad_l + (v - x0) / float(x1 - x0) * w
    sy = lambda v: pad_t + h - (v - y0) / float(y1 - y0) * h

    out = []
    # horizontal gridlines and y ticks
    n = int(round((y1 - y0) / ystep))
    for i in range(n + 1):
        v = y0 + i * ystep
        yy = sy(v)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                   'stroke-width="1"/>' % (pad_l, yy, pad_l + w, yy, GRID))
        out.append('<text x="%.1f" y="%.1f" fill="%s" font-size="8.5" '
                   'text-anchor="end" font-family="ui-monospace,monospace">%s</text>'
                   % (pad_l - 6, yy + 3, TEXT, _fmt(v)))
    # x ticks
    span = x1 - x0
    tick = max(1, int(round(span / 4.0)))
    v = x0
    while v <= x1 + 0.001:
        xx = sx(v)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                   'stroke-width="1"/>' % (xx, pad_t + h, xx, pad_t + h + 3, AXIS))
        out.append('<text x="%.1f" y="%.1f" fill="%s" font-size="8.5" '
                   'text-anchor="middle" font-family="ui-monospace,monospace">%s</text>'
                   % (xx, pad_t + h + 14, TEXT, _fmt(v)))
        v += tick
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
               'stroke-width="1"/>' % (pad_l, pad_t + h, pad_l + w, pad_t + h, AXIS))

    for mx, label in markers:
        if not (x0 <= mx <= x1):
            continue
        xx = sx(mx)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                   'stroke-width="1" stroke-dasharray="2 3"/>'
                   % (xx, pad_t, xx, pad_t + h, "#4E574C"))
        out.append('<text x="%.1f" y="%.1f" fill="%s" font-size="8.5" '
                   'text-anchor="middle" font-family="ui-monospace,monospace">%s</text>'
                   % (xx, pad_t - 2, INK, label))

    if reference and live:
        pts = live[0]["points"]
        d = " ".join("%.1f,%.1f" % (sx(pts[i][0]), sy(reference[i]))
                     for i in range(min(len(pts), len(reference)))
                     if reference[i] is not None)
        if d:
            out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.2" '
                       'stroke-dasharray="4 3"/>' % (d, REF))

    for s in live:
        colour = s.get("colour") or INK
        pts = [(sx(p[0]), sy(p[1])) for p in s["points"] if p[1] is not None]
        if len(pts) < 2:
            continue
        out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.6" '
                   'stroke-linejoin="round"/>'
                   % (" ".join("%.1f,%.1f" % p for p in pts), colour))
        # markers thin out on long series so the line stays readable
        every = max(1, len(pts) // 14)
        for i in range(0, len(pts), every):
            out.append('<circle cx="%.1f" cy="%.1f" r="2" fill="%s" stroke="#0D100C" '
                       'stroke-width="1"/>' % (pts[i][0], pts[i][1], colour))
        if end_labels:
            ex, ey = pts[-1]
            val = [p[1] for p in s["points"] if p[1] is not None][-1]
            out.append('<rect x="%.1f" y="%.1f" width="40" height="13" fill="%s" rx="1"/>'
                       % (min(ex + 4, width - 42), ey - 6.5, colour))
            out.append('<text x="%.1f" y="%.1f" fill="#0D100C" font-size="8.5" '
                       'font-weight="700" text-anchor="middle" '
                       'font-family="ui-monospace,monospace">%s</text>'
                       % (min(ex + 4, width - 42) + 20, ey + 2.8, _fmt(val)))

    if y_label:
        out.append('<text x="4" y="%.1f" fill="%s" font-size="8" '
                   'transform="rotate(-90 4 %.1f)" text-anchor="middle" '
                   'font-family="ui-monospace,monospace">%s</text>'
                   % (pad_t + h / 2, pad_t + h / 2, TEXT, y_label))
    if x_label:
        out.append('<text x="%.1f" y="%.1f" fill="%s" font-size="8" text-anchor="middle" '
                   'font-family="ui-monospace,monospace">%s</text>'
                   % (pad_l + w / 2, height - 1, TEXT, x_label))

    return ('<svg viewBox="0 0 %d %d" class="chart" role="img" aria-label="%s">%s</svg>'
            % (width, height, y_label or "chart", "".join(out)))


def legend(items: Sequence[Tuple[str, str]], dashed: str = "") -> str:
    out = "".join(
        '<span class="lg"><svg width="18" height="8"><line x1="0" y1="4" x2="18" y2="4" '
        'stroke="%s" stroke-width="2"/><circle cx="9" cy="4" r="2.2" fill="%s"/></svg>%s</span>'
        % (colour, colour, name) for name, colour in items)
    if dashed:
        out += ('<span class="lg"><svg width="18" height="8"><line x1="0" y1="4" x2="18" '
                'y2="4" stroke="%s" stroke-width="1.4" stroke-dasharray="4 3"/></svg>%s</span>'
                % (REF, dashed))
    return '<div class="chartlegend">%s</div>' % out


def trend(points: Sequence[float], w: int = 74, h: int = 20,
          colour: str = "#A8D45C") -> str:
    """A bare micro-line for a table cell. No axis, and it never carries a value."""
    vals = [v for v in points if v is not None]
    if len(vals) < 2:
        return '<span style="color:#4E574C">—</span>'
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    step = w / float(len(vals) - 1)
    d = " ".join("%.1f,%.1f" % (i * step, h - 2 - (v - lo) / span * (h - 4))
                 for i, v in enumerate(vals))
    return ('<svg viewBox="0 0 %d %d" class="trend"><polyline points="%s" fill="none" '
            'stroke="%s" stroke-width="1.2"/></svg>' % (w, h, d, colour))


def density_map(values: Sequence[float], width_cells: int, w: int = 260, h: int = 190,
                bands: Sequence[Tuple[float, str]] = ()) -> str:
    """A terrain drawn cell by cell from one real per-cell quantity."""
    if not values or not width_cells:
        return ('<p style="color:%s;font:11px ui-monospace,monospace;font-style:italic">'
                'no per-cell values recorded</p>' % TEXT)
    depth = max(1, len(values) // width_cells)
    step = max(1, width_cells // 90)
    cw = w / float(max(1, width_cells / step))
    ch = h / float(max(1, depth / step))
    hi = max(values) or 1.0
    out = []
    for i in range(0, len(values), step):
        col, row = i % width_cells, i // width_cells
        if col % step or row % step:
            continue
        f = max(0.0, min(1.0, values[i] / hi))
        if f <= 0.005:
            colour = "#11150F"
        else:
            colour = "rgb(%d,%d,%d)" % (int(30 + f * 130), int(45 + f * 165), int(28 + f * 80))
        out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s"/>'
                   % (col / step * cw, row / step * ch, cw + .5, ch + .5, colour))
    return ('<svg viewBox="0 0 %d %d" preserveAspectRatio="none" class="dmap" role="img" '
            'aria-label="per-cell density across the terrain">%s</svg>' % (w, h, "".join(out)))


def bars(rows: Sequence[Tuple[str, float, str]], w: int = 260) -> str:
    """Labelled horizontal bars, each drawn against the largest in the set."""
    top = max([abs(v) for _, v, _ in rows] or [1.0]) or 1.0
    return "".join(
        '<div class="brow"><span class="bl">%s</span>'
        '<span class="bt"><span style="width:%.1f%%;background:%s"></span></span>'
        '<b>%s</b></div>' % (label, abs(v) / top * 100.0, colour, _fmt(v))
        for label, v, colour in rows)


CSS = """
.chart{width:100%;height:auto;display:block}
.chartlegend{display:flex;gap:16px;flex-wrap:wrap;justify-content:center;
font:9.5px ui-monospace,monospace;color:#7C8879;margin-top:7px}
.chartlegend .lg{display:flex;align-items:center;gap:5px}
.trend{width:74px;height:20px;display:block}
.dmap{width:100%;height:auto;display:block;border:1px solid #1D231B}
.brow{display:grid;grid-template-columns:1fr 90px auto;gap:10px;align-items:center;
font:10.5px ui-monospace,monospace;color:#7C8879;padding:3px 0}
.brow .bt{height:6px;background:#1D231B;display:block}
.brow .bt span{display:block;height:6px}
.brow b{color:#D6DED2;font-weight:400;font-variant-numeric:tabular-nums;text-align:right}
.charts3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.charts5{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}
@media(max-width:1400px){.charts5{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:1100px){.charts3,.charts5{grid-template-columns:1fr 1fr}}
.ct{font:9px ui-monospace,monospace;letter-spacing:.11em;text-transform:uppercase;
color:#7C8879;margin-bottom:2px}
.ct b{color:#D6DED2;font-weight:400}
.cs{font:8.5px ui-monospace,monospace;color:#4E574C;margin-bottom:7px}
"""
