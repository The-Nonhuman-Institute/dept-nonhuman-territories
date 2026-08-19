"""
DNT — terrain formation. A landscape that has a history rather than a layout.

    python3 geomorph.py --run 20000        evolve a landscape, write it out
    python3 geomorph.py --run 20000 --show  ...and print what formed

WHY THIS EXISTS

  Until now the ground was a formula. `cell_elevation(index)` returned the same
  value at shift 1 and at shift 10,000, so the terrain could not change and no
  feature in it had a cause. If a river had been wanted, someone would have had
  to draw one — and a drawn river is authored terrain, which is the same
  failure as authoring a specimen's shape, one layer down.

  So the ground is a process here. Nothing below places a channel, a ridge, a
  basin or a plain. It moves substrate according to where flow goes, runs the
  loop, and whatever the loop leaves is the terrain.

THE PROCESS, IN FULL

  1. SOURCE. Substrate is lifted, most strongly at the far margin. Without it
     everything erodes to a featureless plain and the run ends in nothing.

  2. FLOW. Every cell passes what it carries to its lowest neighbour. Flow
     therefore ACCUMULATES: a cell downhill of many others carries all of them.
     This is the whole mechanism — no channel is placed, but cells that happen
     to lie low gather flow from everything above.

  3. INCISION. Flow wears substrate away, and it wears faster where flow is
     large and the ground steep. A cell that gathers flow lowers; lowering makes
     it gather more; that feedback is what a canyon IS. Nothing in the code
     knows the word.

  4. SETTLING. Where flow slows — shallow ground, low places — what was carried
     drops out and the ground rises. Fans, floors, plains.

  5. CREEP. Steep faces shed material to their neighbours, so nothing stands at
     an impossible angle forever.

  Run it long enough and the same rules produce channels that deepen, divides
  between them, basins that fill, and slopes that grade. Run it twice with the
  same seed and it produces the same world, because there is no randomness in
  it — variation comes from the initial roughness, which is itself deterministic.

WHAT IS NOT DECIDED HERE

  Where the water goes. Where the high ground is. Whether there is one channel
  or nine. How deep anything cuts. Those are outcomes, and reading them off the
  result is the point of running it.

Python 3.9 compatible. Writes one JSON file. Makes no model call and costs
nothing to run.
"""

from __future__ import annotations

import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))

# --- the process --------------------------------------------------------
# Calibrated by sweeping the process against itself, not against a picture of
# a landscape. At the first values nothing persisted: creep diffused the ground
# faster than flow could cut it, so by 40,000 shifts a single channel cell
# remained and the terrain was a smooth ramp. That is a broken process, not a
# terrain that chose to be flat — a mechanism that cannot express itself has
# not been given a chance to fail honestly.
#
# Uplift turned out to be the binding one: too little and erosion outruns
# renewal, so nothing stands long enough to be cut into. What was tuned is
# whether the loop CAN produce features, never which features it produces.
UPLIFT_BASE = 0.0015         # substrate added per shift, everywhere
UPLIFT_MARGIN_BIAS = 4.0     # how much more is added at the far margin
INCISION = 0.055             # how readily concentrated flow cuts
INCISION_FLOW_POWER = 0.62   # how much cutting scales with flow volume
INCISION_SLOPE_POWER = 1.05  # how much cutting scales with steepness
SETTLING = 0.10              # share of carried substrate dropped where flow slows
SETTLE_SLOPE = 0.012         # slope below which flow is considered slow
CREEP = 0.003                # share of a steep difference shed to neighbours
RAIN_PER_CELL = 1.0          # flow entering every cell each shift


def neighbours(index: int, width: int, height: int) -> List[int]:
    """Four cardinal neighbours — the same neighbourhood the terrain moves on."""
    d, l = index // width, index % width
    out = []
    if d > 0:
        out.append(index - width)
    if d < height - 1:
        out.append(index + width)
    if l > 0:
        out.append(index - 1)
    if l < width - 1:
        out.append(index + 1)
    return out


def initial_roughness(index: int, width: int, height: int) -> float:
    """A slightly uneven starting surface. Deterministic, and NOT a landscape.

    This is grit, not terrain: low-amplitude noise with no channels, ridges or
    basins in it. Everything that later looks like a feature was cut by the
    loop, not seeded here. It exists only because a perfectly flat plane erodes
    symmetrically and would produce nothing.
    """
    d, l = index // width, index % width
    total = 0.0
    for k, (fd, fl, amp) in enumerate((
            (2.7, 3.3, 0.55), (5.9, 4.7, 0.28), (11.3, 9.1, 0.13), (19.7, 17.3, 0.06))):
        total += amp * math.sin(d / float(height) * fd * math.pi + k * 1.7) \
                     * math.cos(l / float(width) * fl * math.pi + k * 2.3)
    return total * 0.5


def evolve(width: int, height: int, shifts: int,
           report: Optional[Any] = None) -> Dict[str, Any]:
    n = width * height
    ground = [initial_roughness(i, width, n // width) for i in range(n)]
    # The far margin is the source side; the opposite edge is the outlet, held
    # at a fixed level so the system has somewhere to drain TO.
    outlet = set(range(n - width, n))

    for shift in range(shifts):
        # 1. source
        for i in range(n):
            d = i // width
            bias = 1.0 + UPLIFT_MARGIN_BIAS * (1.0 - d / float(height - 1))
            ground[i] += UPLIFT_BASE * bias

        # 2. flow, accumulated downhill. Cells are processed high to low so a
        #    cell always passes on everything that reached it from above.
        order = sorted(range(n), key=lambda i: -ground[i])
        flow = [RAIN_PER_CELL] * n
        steepest: List[Optional[int]] = [None] * n
        drop: List[float] = [0.0] * n
        for i in order:
            if i in outlet:
                continue
            low, best = None, 0.0
            for j in neighbours(i, width, height):
                diff = ground[i] - ground[j]
                if diff > best:
                    low, best = j, diff
            steepest[i], drop[i] = low, best
            if low is not None:
                flow[low] += flow[i]

        # 3 & 4. incision where flow is concentrated and the ground steep;
        #        settling where it is not.
        carried = 0.0
        for i in order:
            if i in outlet:
                continue
            slope = drop[i]
            if slope > SETTLE_SLOPE and steepest[i] is not None:
                cut = INCISION * (flow[i] ** INCISION_FLOW_POWER) * (slope ** INCISION_SLOPE_POWER)
                cut = min(cut, slope * 0.45)      # cannot cut below what it flows to
                ground[i] -= cut
                carried += cut
            elif carried > 0.0:
                laid = carried * SETTLING
                ground[i] += laid
                carried -= laid

        # 5. creep
        for i in range(n):
            for j in neighbours(i, width, height):
                diff = ground[i] - ground[j]
                if diff > 0.05:
                    move = diff * CREEP * 0.25
                    ground[i] -= move
                    ground[j] += move

        for i in outlet:
            ground[i] = 0.0

        if report and shift % max(1, shifts // 10) == 0:
            report(shift, ground, flow)

    return {"width": width, "height": height, "shifts": shifts,
            "ground": [round(g, 5) for g in ground],
            "flow": [round(f, 2) for f in flow]}


def describe(result: Dict[str, Any]) -> Dict[str, Any]:
    """Read the landscape off the result. Measures features; does not place them."""
    g, f = result["ground"], result["flow"]
    w, h = result["width"], result["height"]
    n = len(g)
    lo, hi = min(g), max(g)
    span = max(1e-9, hi - lo)

    # A channel is a cell carrying far more flow than typical — that is the
    # only definition used, and it is a threshold on a measurement.
    ordered = sorted(f)
    median = ordered[n // 2]
    channel = [i for i in range(n) if f[i] > median * 12]

    # How connected are the channels? Contiguous runs = distinct watercourses.
    seen, courses = set(), []
    cs = set(channel)
    for start in sorted(cs):
        if start in seen:
            continue
        stack, size = [start], 0
        seen.add(start)
        while stack:
            c = stack.pop()
            size += 1
            for j in neighbours(c, w, h):
                if j in cs and j not in seen:
                    seen.add(j)
                    stack.append(j)
        courses.append(size)

    # Relief: how deep is a channel below the ground beside it?
    incision = []
    for i in channel:
        sides = [g[j] for j in neighbours(i, w, h) if j not in cs]
        if sides:
            incision.append(max(sides) - g[i])

    ridges = [i for i in range(n) if g[i] > lo + span * 0.72]
    basins = [i for i in range(n) if g[i] < lo + span * 0.16 and f[i] < median * 4]
    return {
        "relief": round(span, 3),
        "channel_cells": len(channel),
        "distinct_courses": len(courses),
        "longest_course": max(courses) if courses else 0,
        "mean_incision": round(sum(incision) / len(incision), 3) if incision else 0.0,
        "deepest_incision": round(max(incision), 3) if incision else 0.0,
        "ridge_cells": len(ridges),
        "basin_cells": len(basins),
        "max_flow": round(max(f), 1),
    }


def render(result: Dict[str, Any]) -> str:
    """The landscape as text. Height in shade, watercourses marked."""
    g, f = result["ground"], result["flow"]
    w, h = result["width"], result["height"]
    lo, hi = min(g), max(g)
    span = max(1e-9, hi - lo)
    ramp = " .:-=+*#%@"
    ordered = sorted(f)
    median = ordered[len(f) // 2]
    out = []
    for d in range(h):
        row = []
        for l in range(w):
            i = d * w + l
            if f[i] > median * 12:
                row.append("~")
            else:
                row.append(ramp[min(len(ramp) - 1, int((g[i] - lo) / span * len(ramp)))])
        out.append("".join(row))
    return "\n".join(out)


def main(argv: List[str]) -> int:
    shifts = 20000
    width, height = 15, 21
    if "--run" in argv:
        shifts = int(argv[argv.index("--run") + 1])
    if "--size" in argv:
        width, height = (int(x) for x in argv[argv.index("--size") + 1].split("x"))
    print("evolving %dx%d for %d shifts (free — no model call)..." % (width, height, shifts))
    result = evolve(width, height, shifts)
    stats = describe(result)
    result["formed"] = stats
    path = os.path.join(ROOT, "landscape_%dx%d_%d.json" % (width, height, shifts))
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(result, stream)
    print("\nWHAT FORMED (measured off the result, not placed):")
    for k, v in stats.items():
        print("   %-20s %s" % (k, v))
    if "--show" in argv:
        print("\n" + render(result))
        print("\n  ~ watercourse    space..@ low..high")
    print("\nwrote %s" % path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
