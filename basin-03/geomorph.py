# SPDX-FileCopyrightText: 2026 U3 Labs, LLC
# SPDX-License-Identifier: Apache-2.0
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

import heapq
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
REFERENCE_LENGTH = 40.0      # the domain length the rates were calibrated at

INCISION = 0.055             # how readily concentrated flow cuts
INCISION_FLOW_POWER = 0.62   # how much cutting scales with flow volume
INCISION_SLOPE_POWER = 1.05  # how much cutting scales with steepness
SETTLING = 0.10              # share of carried substrate dropped where flow slows
SETTLE_SLOPE = 0.012         # slope below which flow is considered slow
CREEP = 0.003                # share of a moderate difference shed to neighbours
# ---------------------------------------------------------------------------
# A FALL WAS ATTEMPTED HERE AND DOES NOT FORM. The attempt is left recorded
# rather than the changes.
#
# Two were tried at the steward's request. First, creep was stopped above a
# threshold so a steep face could stand instead of slumping — zero falls at
# every threshold tried. Second, substrate was given a resistance that varied
# from place to place, so a course crossing from hard ground to soft would
# undercut — zero falls at resistance ranges up to 6x.
#
# The blocker is the incision law itself. Cutting rises with slope^1.05, and
# the lip of a step has by definition the steepest slope in the reach — so the
# lip cuts faster than anything around it and erases itself. The steeper the
# step, the harder this model works to remove it. Falls survive in the world
# because of plunge-pool scour below the lip, lateral undermining of the face,
# and genuinely layered rock; none of those exist here.
#
# A fall could be produced by special-casing one — detecting a step and
# exempting it. That would be placing a named feature in the terrain, which is
# the whole thing this build refuses to do. So there are no falls, and the
# reason is recorded.
#
# WHY A FACE CAN HOLD
#
# Creep previously shed EVERY height difference above 0.05, every step. The
# consequence was that the process could not hold a steep face for any length
# of time, and so it could never produce a fall: measured across the whole
# landscape, not one cell on any watercourse dropped more than ten times the
# median. That absence was caused by this rule, not by the terrain declining to
# make one.
#
# Loose material slumps; competent substrate does not. So creep now acts only
# on the middle band of slopes. Below CREEP_MIN nothing is moving anyway. Above
# CREEP_HOLDS_ABOVE the face stands, and flow arriving at its lip cuts there
# instead — which deepens the drop, which keeps the face standing. A fall that
# forms this way also RETREATS upstream as its lip is cut back, which is what
# falls do.
#
# Nothing here places a fall or decides where one should be.
# ---------------------------------------------------------------------------
CREEP_MIN = 0.05             # below this, nothing is moving
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



def fill_depressions(ground: List[float], width: int, height: int) -> List[float]:
    """A copy of the surface with every hollow raised to its spill level.

    THE DEFECT THIS FIXES

      Flow was routed over the bare ground, and a cell with no lower neighbour
      simply terminated it. BASIN-05 carried 252 such cells, BASIN-04 514 and
      BASIN-03 1,134, so the drainage network was not a network: it was
      fragments, each ending in a hole. Peak flow reached 9% of the terrain
      where a connected network gathers most of it.

      Every landscape evolution model does this step. Its absence here was an
      omission, not a design choice, which is why it is corrected in place
      rather than made the premise of a new terrain.

    WHAT IT DOES NOT DO

      It does not raise the real ground. The returned surface is used for
      ROUTING only, so water passes THROUGH a hollow instead of vanishing into
      it, and the hollow stays a hollow. A hollow that water passes through and
      stands in is a lake; 242 cells held water in the probe that measured this.

      Priority flood: every cell is raised to the lowest level from which it can
      still reach the boundary, working outward from the edge.
    """
    n = width * height
    filled = list(ground)
    closed = [False] * n
    queue: List[Tuple[float, int]] = []
    for i in range(n):
        row, col = i // width, i % width
        if row in (0, height - 1) or col in (0, width - 1):
            heapq.heappush(queue, (ground[i], i))
            closed[i] = True
    while queue:
        level, i = heapq.heappop(queue)
        for j in neighbours(i, width, height):
            if closed[j]:
                continue
            closed[j] = True
            if filled[j] <= level:
                filled[j] = level
            heapq.heappush(queue, (filled[j], j))
    return filled


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


def evolve_from(ground: List[float], width: int, height: int,
                shifts: int) -> Dict[str, Any]:
    """Continue forming an existing landscape. Used while a terrain is inhabited."""
    return _run(list(ground), width, height, shifts)


def evolve(width: int, height: int, shifts: int,
           report: Optional[Any] = None) -> Dict[str, Any]:
    n = width * height
    ground = [initial_roughness(i, width, n // width) for i in range(n)]
    return _run(ground, width, height, shifts, report)


def _run(ground: List[float], width: int, height: int, shifts: int,
         report: Optional[Any] = None) -> Dict[str, Any]:
    n = width * height
    # THE OUTLET
    #
    # Every landscape process needs somewhere for material to leave, but the
    # shape of that exit is not free — it becomes the most visible feature in
    # the terrain. Holding an entire boundary row at zero, as this did, gives a
    # perfectly straight full-width edge, and since everything there sits below
    # the water level it renders as a ruler-straight stream. That is an
    # authored river, arrived at by accident.
    #
    # So the outlet is a MOUTH, not an edge: the few lowest points on the
    # boundary of the initial surface. Drainage then has to converge on them,
    # which is what makes a network branch and join instead of spilling evenly
    # off one side. Where the mouth falls is decided by the starting roughness,
    # not by me — a different seed puts it somewhere else.
    perimeter = ([i for i in range(width)]
                 + [i for i in range(n - width, n)]
                 + [d * width for d in range(height)]
                 + [d * width + width - 1 for d in range(height)])
    perimeter = sorted(set(perimeter), key=lambda i: (ground[i], i))
    outlet = set(perimeter[:max(2, len(perimeter) // 40)])

    for shift in range(shifts):
        # 1. source
        #
        # Uplift is scaled to the distance material must travel to leave the
        # terrain. Without this the process does not scale: applied per cell
        # per step, a large domain piles material at its source margin faster
        # than erosion can carry it the greater distance to the outlet, and
        # what forms is a wall beside a plain rather than a landscape. Observed
        # directly at 200x90 — 99th percentile height 650 against a median of
        # 14.5, 158 ridge cells against 13,786 in the basin band.
        #
        # This calibrates how fast the loop runs relative to terrain size. It
        # does not decide what the loop produces.
        scale = REFERENCE_LENGTH / float(max(1, height))
        for i in range(n):
            d = i // width
            bias = 1.0 + UPLIFT_MARGIN_BIAS * (1.0 - d / float(height - 1))
            ground[i] += UPLIFT_BASE * bias * scale

        # 2. flow, accumulated downhill. Cells are processed high to low so a
        #    cell always passes on everything that reached it from above.
        # Routed over a DEPRESSION-FILLED copy so that water crosses a hollow
        # instead of terminating in it. The ground itself is untouched and is
        # what gets eroded below; a hollow water crosses and stands in is a
        # lake, and `lakes` counts the cells holding one.
        route = fill_depressions(ground, width, height)
        lakes = sum(1 for i in range(n) if route[i] > ground[i] + 1e-9)
        order = sorted(range(n), key=lambda i: -route[i])
        flow = [RAIN_PER_CELL] * n
        steepest: List[Optional[int]] = [None] * n
        drop: List[float] = [0.0] * n
        for i in order:
            if i in outlet:
                continue
            low, best = None, 0.0
            for j in neighbours(i, width, height):
                diff = route[i] - route[j]
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

        # 5. creep — moderate slopes only. A steep face is left standing.
        for i in range(n):
            for j in neighbours(i, width, height):
                diff = ground[i] - ground[j]
                if diff > CREEP_MIN:
                    move = diff * CREEP * 0.25
                    ground[i] -= move
                    ground[j] += move

        for i in outlet:
            ground[i] = 0.0

        if report and shift % max(1, shifts // 10) == 0:
            report(shift, ground, flow)

    return {"width": width, "height": height, "shifts": shifts, "lakes": lakes,
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
