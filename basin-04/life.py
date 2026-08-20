# SPDX-FileCopyrightText: 2026 U3 Labs, LLC
# SPDX-License-Identifier: Apache-2.0
"""
BASIN-01 — the light economy.

This module is the terrain's physics. It makes NO model call, holds no prompt,
and names no role. It moves light around and records what happened.

Everything here is deterministic: the same state and shift number always
produce the same next state. That is deliberate. A terrain whose behaviour
cannot be replayed from its own record is a terrain whose findings cannot be
checked months later (physics.md Section 5.1 rejected a random walk for the
same reason).

WHAT IS ENCODED

  Light enters at the data-stream and falls off with distance.
  A census layer takes light directly, grows, spreads, and dies back.
  Individuals hold light, spend it existing, draw it from what is around them,
    move, and end when it runs out.
  What ends becomes residue, and residue can be taken up again.
  Proximity that lasts becomes a link, and light moves faster along links.

WHAT IS NOT ENCODED

  No producer, consumer, decomposer, connector, parasite or symbiont appears
  anywhere in this file. Those are positions in a light economy, and physics.md
  Section 6 is explicit that the terms are reference vocabulary for humans
  reading the record — never seeded as shape. If something ends up living off
  the dead, or bridging two clusters, or draining a neighbour, it found that
  position; the terrain did not assign it.

  There is no action menu. An individual's behaviour is where it moves and what
  it draws, and both fall out of the light around it.

  Movement is not pulled toward the data-stream. It follows available light.
  Because light enters at the stream, that produces stream-ward drift on its
  own — and when the near cells are drawn down, moving outward becomes the
  better move. The tendency is emergent, so the margins stay habitable.

TWO REGISTERS, PER physics.md SECTION 8

  The census layer is high-volume and low-complexity, recorded as density per
  cell rather than per instance — the "base-producer tier" that section names.
  Individuals carry their own records. An individual can ARISE from the census
  layer where it is dense and light-rich, which is that section's promotion
  rule read as ecology rather than as a logging saving.

Python 3.9 compatible.
"""

from __future__ import annotations

import math
import config
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# The ground
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# THE FIELD  —  the one intentional difference between BASIN-02 and BASIN-01
#
# BASIN-01 is a line: 21 cells from the far margin to the data-stream, and a
# specimen's only choices are toward the stream or away from it. BASIN-02 is a
# field of the same depth with room across it.
#
# The data-stream is an EDGE here, not a point. That is what keeps this a
# controlled comparison rather than a different world: light arriving at any
# given depth is computed by exactly the formula BASIN-01 uses, from exactly
# the same constants, so depth 2 receives what depth 2 received there and
# depth 20 receives what depth 20 received there. The gradient is untouched.
#
# What is added is lateral room at constant light. In BASIN-01, moving away
# from competition means moving up or down the gradient and paying for it in
# light. Here a specimen can move sideways along a contour of equal light and
# pay nothing. If clustering, spacing, or anything territorial appears in this
# terrain and not in BASIN-01, that is the mechanism it came from.
#
# Nothing else in this file differs from BASIN-01 except the consequences of
# a cell having four neighbours instead of two.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# THE LANDSCAPE  —  BASIN-03's one difference from BASIN-02
#
# BASIN-02's ground was a formula: cell_elevation(index) returned the same
# value at shift 1 and at shift 10,000, and the data-stream was a straight edge
# with light falling off by depth. That terrain could not change, and no
# feature in it had a cause. Wanting a river there would have meant drawing
# one, and a drawn river is authored terrain — the same failure as authoring a
# specimen's form, one layer down.
#
# Here the ground is the output of a process (geomorph.py) that was run before
# anything lived: substrate lifts, flow accumulates downhill, concentrated flow
# cuts, slow flow settles, steep faces creep. Channels, divides, basins and
# plains are what that loop left behind. Nothing placed them.
#
# TWO CONSEQUENCES FOR THE LIGHT ECONOMY
#
#   The data-stream is no longer an edge. It is wherever flow gathered — the
#   watercourses the process cut. Influx is a function of DISTANCE TO THE
#   NEAREST WATERCOURSE, so a cell beside a bend is rich, a cell on a divide
#   between two courses is poor, and remoteness is a real property of a place
#   rather than a coordinate.
#
#   Height is the real ground. Residue runs down the landscape that was cut,
#   so it collects in the basins the process made.
#
# The landscape also KEEPS EVOLVING while things live on it, at the same rate
# it formed. Courses shift, channels deepen. Nothing here decides where.
# ---------------------------------------------------------------------------

import json as _json
import os as _os

LANDSCAPE_FILE = None       # set by load_landscape()
FIELD_DEPTH = 40            # replaced by whatever the landscape says
FIELD_WIDTH = 60
CELL_COUNT = FIELD_DEPTH * FIELD_WIDTH
GROUND: List[float] = []    # height per cell — STATE, and it changes
FLOW: List[float] = []      # how much passes through each cell
STREAM_DISTANCE: List[int] = []   # steps to the nearest watercourse

WATERCOURSE_FLOW_MULTIPLE = 12.0  # flow above this multiple of median is a course

# ---------------------------------------------------------------------------
# WHERE THE TERRAIN ENDS
#
# BASIN-01 and BASIN-02 were rectangles because I drew rectangles. The extent
# was a number in a file and the edge was wherever that number ran out.
#
# Here the boundary is not drawn. A water level is set — one physical
# parameter, a fraction of the landscape that lies beneath the data-stream's
# surface — and everything below it is stream rather than standing ground.
# The SHAPE of that boundary is entirely the process's: the basins, inlets,
# lakes and headlands are wherever erosion and settling happened to leave the
# ground low, and they change as the ground keeps forming.
#
# So the terrain has a coastline nobody authored, and no cell knows it is on
# an edge.
# ---------------------------------------------------------------------------

SUBMERGED_FRACTION = 0.14    # share of the landscape lying below the stream
_water_level = None


def _recompute_water_level() -> None:
    global _water_level
    if not GROUND:
        _water_level = None
        return
    ordered = sorted(GROUND)
    _water_level = ordered[int(len(ordered) * SUBMERGED_FRACTION)]


def is_land(index: int) -> bool:
    """Whether a cell is standing ground. Cover and individuals need land."""
    if _water_level is None:
        return True
    return GROUND[index] > _water_level


# ---------------------------------------------------------------------------
# THE TERRAIN GROWS
#
# Every terrain before this one had an extent I picked: 21 cells, then 315,
# then 18,000. Larger each time, and each time still a box whose edge was a
# number in a file. A boundary chosen in advance is a cap however far away it
# sits.
#
# Here extent is an OUTCOME. When cover or anything living reaches within a
# few cells of a margin, the terrain extends on that side: new ground is
# brought into being, carrying the same roughness the original started from,
# and the landscape process immediately begins working it — cutting, settling,
# draining, exactly as it did everywhere else.
#
# Nothing decides how far the terrain goes. It goes as far as something has
# reached, and it stops growing wherever nothing has arrived. Two runs from the
# same seed grow the same way; a run where life spreads north and not south
# grows north and not south.
#
# The cost is real and worth stating: every cell added is a cell the landscape
# process must work every shift, so a terrain that keeps spreading keeps
# getting slower. That is a property of the thing, not a bug to hide.
# ---------------------------------------------------------------------------

GROWTH_MARGIN = 3        # how close to an edge something must be to extend it
GROWTH_BAND = 6          # cells added on a side when it extends
MAX_CELLS = 400000       # a memory bound, not a terrain bound. Logged if reached.


def _edge_pressure(state: Dict[str, Any]) -> Dict[str, bool]:
    """Which margins something has reached. Nothing else consults this."""
    press = {"north": False, "south": False, "west": False, "east": False}
    occupied = set()
    for cell in state["cells"]:
        if cell["census_density"] > 0.0:
            occupied.add(cell["index"])
    for being in state["individuals"].values():
        occupied.add(int(being.get("cell", 0)))
    for i in occupied:
        d, l = cell_depth(i), cell_lateral(i)
        if d < GROWTH_MARGIN:
            press["north"] = True
        if d >= FIELD_DEPTH - GROWTH_MARGIN:
            press["south"] = True
        if l < GROWTH_MARGIN:
            press["west"] = True
        if l >= FIELD_WIDTH - GROWTH_MARGIN:
            press["east"] = True
    return press


def _grow(state: Dict[str, Any], events: Dict[str, Any]) -> None:
    """Extend the terrain wherever something has reached a margin."""
    global FIELD_WIDTH, FIELD_DEPTH, CELL_COUNT, GROUND, FLOW
    press = _edge_pressure(state)
    if not any(press.values()):
        return
    add_n = GROWTH_BAND if press["north"] else 0
    add_s = GROWTH_BAND if press["south"] else 0
    add_w = GROWTH_BAND if press["west"] else 0
    add_e = GROWTH_BAND if press["east"] else 0
    new_w = FIELD_WIDTH + add_w + add_e
    new_d = FIELD_DEPTH + add_n + add_s
    if new_w * new_d > MAX_CELLS:
        events["growth_refused"] = "would exceed the memory bound of %d cells" % MAX_CELLS
        return

    import geomorph
    old_w, old_d = FIELD_WIDTH, FIELD_DEPTH
    new_ground = [0.0] * (new_w * new_d)
    new_flow = [1.0] * (new_w * new_d)
    # New ground carries the same roughness the terrain started from, continued
    # outward. It is not a copy of anything and holds no features.
    for d in range(new_d):
        for l in range(new_w):
            ni = d * new_w + l
            od, ol = d - add_n, l - add_w
            if 0 <= od < old_d and 0 <= ol < old_w:
                oi = od * old_w + ol
                new_ground[ni] = GROUND[oi]
                new_flow[ni] = FLOW[oi]
            else:
                # New ground continues the landscape it extends, at the height
                # of the nearest existing edge, with the same small roughness
                # the terrain started from laid over it.
                #
                # It previously took initial_roughness() alone — an amplitude
                # suited to a fresh surface at step zero, not to ground that has
                # been uplifted for thousands of steps. Every new cell therefore
                # arrived far below the standing landscape and instantly fell
                # under the water level, so the terrain grew a drowned rim
                # instead of more country.
                sd = min(max(od, 0), old_d - 1)
                sl = min(max(ol, 0), old_w - 1)
                edge = GROUND[sd * old_w + sl]
                new_ground[ni] = edge + geomorph.initial_roughness(ni, new_w, new_d) * 0.5

    remap = {}
    for d in range(old_d):
        for l in range(old_w):
            remap[d * old_w + l] = (d + add_n) * new_w + (l + add_w)

    old_cells = {c["index"]: c for c in state["cells"]}
    FIELD_WIDTH, FIELD_DEPTH, CELL_COUNT = new_w, new_d, new_w * new_d
    GROUND, FLOW = new_ground, new_flow
    clear_elevation_cache()
    clear_elevation_cache()
    _recompute_water_level()
    _recompute_stream_distance()

    cells = []
    for i in range(CELL_COUNT):
        cells.append({"index": i, "position": cell_position(i), "census_density": 0.0,
                      "census_light": 0.0, "census_substrate": None, "residue": 0.0})
    for old_index, cell in old_cells.items():
        ni = remap[old_index]
        cells[ni].update({k: cell[k] for k in
                          ("census_density", "census_light", "census_substrate", "residue")})
        cells[ni]["position"] = cell_position(ni)
    state["cells"] = cells
    for being in state["individuals"].values():
        being["cell"] = remap.get(int(being.get("cell", 0)), being.get("cell", 0))
    for gone in state.get("ended") or []:
        if "cell" in gone:
            gone["cell"] = remap.get(int(gone["cell"]), gone["cell"])

    events["terrain_grew"] = {
        "sides": [k for k, v in press.items() if v],
        "cells_before": old_w * old_d, "cells_after": CELL_COUNT,
        "extent": "%dx%d" % (new_w, new_d),
    }


REGION_COUNT = 12    # bands the observation sample rotates through


def region_of(index: int) -> int:
    """Which region a cell falls in. A grid over the terrain, nothing more.

    Regions carry no physics: nothing about a cell changes because of which
    band it lands in. They exist so that observation is spread across a large
    terrain rather than concentrated wherever the population is oldest.
    """
    across = 4
    down = REGION_COUNT // across
    col = min(across - 1, cell_lateral(index) * across // max(1, FIELD_WIDTH))
    row = min(down - 1, cell_depth(index) * down // max(1, FIELD_DEPTH))
    return row * across + col


def land_cells() -> List[int]:
    return [i for i in range(CELL_COUNT) if is_land(i)]
LANDSCAPE_EVOLVES = True          # the ground keeps forming under the living


def load_landscape(path: str) -> None:
    """Adopt an evolved landscape as this terrain's ground."""
    global LANDSCAPE_FILE, FIELD_DEPTH, FIELD_WIDTH, CELL_COUNT
    global GROUND, FLOW, STREAM_DISTANCE
    with open(path, "r", encoding="utf-8") as stream:
        data = _json.load(stream)
    LANDSCAPE_FILE = path
    FIELD_WIDTH = int(data["width"])
    FIELD_DEPTH = int(data["height"])
    CELL_COUNT = FIELD_WIDTH * FIELD_DEPTH
    GROUND = [float(v) for v in data["ground"]]
    FLOW = [float(v) for v in data["flow"]]
    clear_elevation_cache()
    _recompute_water_level()
    _recompute_stream_distance()


def watercourses() -> List[int]:
    """Cells carrying far more flow than typical. The only definition used."""
    if not FLOW:
        return []
    median = sorted(FLOW)[len(FLOW) // 2]
    return [i for i in range(len(FLOW)) if FLOW[i] > median * WATERCOURSE_FLOW_MULTIPLE]


def _recompute_stream_distance() -> None:
    """Steps from every cell to the nearest watercourse, by the way things move."""
    global STREAM_DISTANCE
    STREAM_DISTANCE = [-1] * CELL_COUNT
    frontier = watercourses()
    if not frontier:
        frontier = [i for i in range(CELL_COUNT - FIELD_WIDTH, CELL_COUNT)]
    for i in frontier:
        STREAM_DISTANCE[i] = 0
    step = 0
    while frontier:
        step += 1
        nxt = []
        for i in frontier:
            for j in neighbours(i):
                if STREAM_DISTANCE[j] == -1:
                    STREAM_DISTANCE[j] = step
                    nxt.append(j)
        frontier = nxt
    far = max(STREAM_DISTANCE) or 1
    for i in range(CELL_COUNT):
        if STREAM_DISTANCE[i] < 0:
            STREAM_DISTANCE[i] = far


def cell_depth(index: int) -> int:
    return index // FIELD_WIDTH


def cell_lateral(index: int) -> int:
    return index % FIELD_WIDTH


def cell_index(depth: int, lateral: int) -> int:
    return depth * FIELD_WIDTH + lateral


def neighbours(index: int) -> List[int]:
    """The four cardinal neighbours."""
    d, l = cell_depth(index), cell_lateral(index)
    out = []
    if d > 0:
        out.append(index - FIELD_WIDTH)
    if d < FIELD_DEPTH - 1:
        out.append(index + FIELD_WIDTH)
    if l > 0:
        out.append(index - 1)
    if l < FIELD_WIDTH - 1:
        out.append(index + 1)
    return out


_ELEV_RANGE_CACHE = None


def _elev_bounds():
    """Lowest and highest ground, cached.

    This was recomputed with min(GROUND) and max(GROUND) on EVERY call — a scan
    of every cell in the terrain, inside loops that already run over every cell
    and its neighbours. At 16,524 cells that made drainage cost 14 seconds a
    shift, subsurface flow 12, and a single temperature lookup 1ms, which at
    10,589 specimens is another 30 seconds. Shifts stopped completing.
    The cache is cleared wherever GROUND is replaced.
    """
    global _ELEV_RANGE_CACHE
    if _ELEV_RANGE_CACHE is None:
        _ELEV_RANGE_CACHE = (min(GROUND), max(GROUND)) if GROUND else (0.0, 1.0)
    return _ELEV_RANGE_CACHE


def clear_elevation_cache() -> None:
    global _ELEV_RANGE_CACHE
    _ELEV_RANGE_CACHE = None


def cell_elevation(index: int) -> float:
    """Height, normalised 0..1 across the landscape as it currently stands."""
    if not GROUND:
        return 0.5
    lo, hi = _elev_bounds()
    return round((GROUND[index] - lo) / max(1e-9, hi - lo), 4)


def cell_height(index: int) -> float:
    """Height in the units residue drains against."""
    return cell_elevation(index) * ELEVATION_RANGE


ELEVATION_RANGE = 6.0      # height span the landscape is measured across
DRAINAGE_RATE = 0.34       # share of a cell's residue that runs downhill per shift
DRAINAGE_MIN_DROP = 0.15   # height difference below which nothing flows


def _drain(state: Dict[str, Any], events: Dict[str, Any]) -> None:
    """Residue runs downhill, over the landscape the process actually cut."""
    cells = state["cells"]
    moved_total = 0.0
    deltas = [0.0] * len(cells)
    for cell in cells:
        here = cell["residue"]
        if here <= 0.01:
            continue
        index = cell["index"]
        downhill = [n for n in neighbours(index)
                    if cell_height(index) - cell_height(n) > DRAINAGE_MIN_DROP]
        if not downhill:
            continue
        drop = {n: cell_height(index) - cell_height(n) for n in downhill}
        total_drop = sum(drop.values())
        moving = here * DRAINAGE_RATE * config.GRAVITY * config.SHIFT_LENGTH
        deltas[index] -= moving
        for n in downhill:
            deltas[n] += moving * (drop[n] / total_drop)
        moved_total += moving
    for cell in cells:
        cell["residue"] = round(max(0.0, cell["residue"] + deltas[cell["index"]]), 4)
    events["residue_drained"] = round(moved_total, 3)


# ---------------------------------------------------------------------------
# The ground keeps forming
#
# BASIN-02's terrain was fixed once and never moved again. Here the same loop
# that cut the landscape continues to run while things live on it, so courses
# migrate and channels deepen underneath the inhabitants. It costs nothing —
# no model is involved — and nothing in it knows anything is living there.
# ---------------------------------------------------------------------------

# The ground was already shaped by 6,000 steps before anything lived on it.
# Running 40 more every shift over 13,500 cells cost 29.7 seconds per shift —
# more than every model call combined — to keep re-forming a landscape that is
# already formed. Ongoing change should be slow: a course migrating, a channel
# deepening, over many shifts rather than within one.
LANDSCAPE_STEP_EVERY = 6     # shifts between a bout of landscape formation
LANDSCAPE_STEPS = 5          # steps of formation in each bout


def _evolve_landscape(events: Dict[str, Any]) -> None:
    """Advance the ground itself. The living are not consulted."""
    global GROUND, FLOW
    if not (LANDSCAPE_EVOLVES and GROUND):
        return
    import geomorph
    before = list(GROUND)
    result = geomorph.evolve_from(GROUND, FIELD_WIDTH, FIELD_DEPTH, LANDSCAPE_STEPS)
    GROUND = result["ground"]
    FLOW = result["flow"]
    clear_elevation_cache()
    clear_elevation_cache()
    _recompute_water_level()
    _recompute_stream_distance()
    events["ground_moved"] = round(
        sum(abs(a - b) for a, b in zip(before, GROUND)), 4)


# ---------------------------------------------------------------------------
# THE GOVERNING CONDITIONS
#
# Every quantity below is read from config and does something. None of them is
# a label: temperature scales metabolism, wind moves material, gravity changes
# what mass costs, subsurface flow puts water where the surface says there is
# none. What they produce together is the experiment.
# ---------------------------------------------------------------------------

def light_cycle(shift: int) -> float:
    """Where the cycle stands this shift, -1.0 to 1.0."""
    return math.sin(2.0 * math.pi * shift / float(config.LIGHT_CYCLE_PERIOD))


def cell_temperature(index: int, shift: int) -> float:
    """Temperature at a cell, this shift.

    Falls with elevation the way air does over ground, rises toward the
    watercourse, and moves with the light cycle. Because elevation and nearness
    to water are not the same axis, temperature runs ACROSS the light gradient
    rather than along it — which is the point of adding it. A cold ridge close
    to water and a warm hollow far from it are now different places.
    """
    base = config.TEMPERATURE_AT_STREAM
    base -= cell_elevation(index) * config.TEMPERATURE_LAPSE
    base -= (1.0 - cell_position(index)) * 4.0
    base += light_cycle(shift) * config.TEMPERATURE_CYCLE_SWING
    return round(base, 3)


_METAB_CACHE = {}


def metabolic_rate(index: int, shift: int) -> float:
    """How fast living runs here. 1.0 at the optimum, falling either side.

    Scales BOTH intake and upkeep, which is what makes it a temperature and not
    just a second food supply: somewhere warm is not simply better, it is
    faster in both directions. Cold ground is cheap to live on and slow to
    gather from; warm ground is the reverse.
    """
    key = (index, shift)
    hit = _METAB_CACHE.get(key)
    if hit is not None:
        return hit
    if len(_METAB_CACHE) > 200000:
        _METAB_CACHE.clear()
    t = cell_temperature(index, shift)
    off = abs(t - config.TEMPERATURE_OPTIMUM) / config.TEMPERATURE_TOLERANCE
    val = round(max(0.12, 1.0 - off * off), 4)
    _METAB_CACHE[key] = val
    return val


def _wind_offsets():
    """Which neighbour lies downwind, and how much of the push it takes."""
    dx = math.cos(config.WIND_BEARING)
    dy = math.sin(config.WIND_BEARING)
    return dx, dy


def _blow(state: Dict[str, Any], events: Dict[str, Any]) -> None:
    """Wind moves residue laterally, regardless of slope.

    Drainage already moves material downhill. Wind moves it along a bearing,
    so windward faces are scoured and leeward ones collect — an asymmetry the
    terrain could not previously have, because every transport process it had
    followed the same gradient.
    """
    cells = state["cells"]
    dx, dy = _wind_offsets()
    moved = 0.0
    deltas = [0.0] * len(cells)
    for cell in cells:
        here = cell["residue"]
        if here <= 0.01:
            continue
        i = cell["index"]
        l, d = cell_lateral(i), cell_depth(i)
        tl = min(FIELD_WIDTH - 1, max(0, l + (1 if dx > 0.25 else (-1 if dx < -0.25 else 0))))
        td = min(FIELD_DEPTH - 1, max(0, d + (1 if dy > 0.25 else (-1 if dy < -0.25 else 0))))
        target = cell_index(td, tl)
        if target == i:
            continue
        amount = here * config.WIND_STRENGTH * config.SHIFT_LENGTH
        deltas[i] -= amount
        deltas[target] += amount
        moved += amount
    for cell in cells:
        cell["residue"] = round(max(0.0, cell["residue"] + deltas[cell["index"]]), 4)
    events["residue_blown"] = round(moved, 3)


def _subsurface(state: Dict[str, Any], events: Dict[str, Any]) -> None:
    """Water moves under the ground and surfaces where enough has gathered.

    Some residue sinks each shift and travels downhill out of sight, pooling in
    a hidden store. Where that store passes a threshold the cell springs, and
    returns part of it to the surface. The consequence is resource appearing in
    places the surface gradient says should be barren — the first mechanism in
    any terrain here that can put light somewhere the light gradient did not.
    """
    cells = state["cells"]
    store = state.setdefault("subsurface", [0.0] * len(cells))
    if len(store) != len(cells):
        store = state["subsurface"] = (store + [0.0] * len(cells))[:len(cells)]
    sank = sprung = 0.0
    for cell in cells:
        take = cell["residue"] * config.SUBSURFACE_RATE * config.SHIFT_LENGTH
        if take > 0.001:
            cell["residue"] = round(cell["residue"] - take, 4)
            store[cell["index"]] += take
            sank += take
    # the hidden store follows the ground, like everything else that flows
    deltas = [0.0] * len(cells)
    for i in range(len(cells)):
        if store[i] <= 0.01:
            continue
        low = [n for n in neighbours(i) if cell_height(n) < cell_height(i)]
        if not low:
            continue
        share = store[i] * 0.5 / len(low)
        for n in low:
            deltas[i] -= share
            deltas[n] += share
    for i in range(len(cells)):
        store[i] = max(0.0, store[i] + deltas[i])
        if store[i] > config.SPRING_THRESHOLD:
            out = store[i] * config.SPRING_YIELD
            store[i] -= out
            cells[i]["residue"] = round(cells[i]["residue"] + out, 4)
            sprung += out
    events["water_sank"] = round(sank, 3)
    events["springs_yielded"] = round(sprung, 3)


def cell_position(index: int) -> float:
    """Position on the gradient, 0.0 (most remote) to 1.0 (on a watercourse).

    Nearness to the nearest watercourse, not depth. The courses are wherever
    the landscape process gathered flow, so this is a property of the ground
    that formed rather than of a coordinate someone chose.
    """
    if not STREAM_DISTANCE:
        return 0.5
    far = max(1, max(STREAM_DISTANCE))
    return round(1.0 - (STREAM_DISTANCE[index] / float(far)), 4)


# Light arriving per shift at the stream itself, before terrain flow is applied.
LIGHT_INFLUX_AT_STREAM = 12.0
# How sharply influx falls with distance. Higher concentrates light at the edge.
INFLUX_FALLOFF = 1.15


def influx(index: int, flow: float) -> float:
    """Light entering a cell this shift."""
    return round(
        LIGHT_INFLUX_AT_STREAM * (cell_position(index) ** INFLUX_FALLOFF) * float(flow),
        4,
    )


# ---------------------------------------------------------------------------
# The census layer
# ---------------------------------------------------------------------------

CENSUS_UPTAKE = 0.85          # share of a cell's influx the census layer takes
CENSUS_UPKEEP = 0.85          # light spent per unit density per shift
CENSUS_GROWTH_COST = 2.60     # light spent to add one unit of density
CENSUS_GROWTH_STEP = 0.16     # density added when growth is afforded
CENSUS_MAX_DENSITY = 1.0
CENSUS_SPREAD_THRESHOLD = 0.55   # density above which a cell seeds its neighbours
CENSUS_SPREAD_STEP = 0.06        # density passed to each neighbour
CENSUS_DIEBACK_STEP = 0.10       # density lost when light runs short
CENSUS_RESIDUE_PER_DENSITY = 2.2  # light returned to residue when density is lost

# ---------------------------------------------------------------------------
# Individuals
# ---------------------------------------------------------------------------

INDIVIDUAL_BASE_UPKEEP = 1.6
INDIVIDUAL_MOVE_COST = 0.9
INDIVIDUAL_DRAW_FROM_CENSUS = 2.2     # light taken from the census layer per shift
INDIVIDUAL_DRAW_FROM_RESIDUE = 2.8    # light taken from residue per shift
CENSUS_LOSS_PER_DRAW = 0.04           # density the cover layer loses per unit drawn
STARTING_LIGHT = 9.0

# Surplus at which an individual can produce a descendant, and what that costs.
REPLICATION_SURPLUS = 7.0
REPLICATION_COST_FRACTION = 0.5

# An individual arises from the census layer where it is dense and light-rich.
ARISE_DENSITY = 0.72
ARISE_LIGHT = 9.0
ARISE_DENSITY_COST = 0.22
ARISE_LIGHT_COST = 7.0

# Links
LINK_AFTER_SHIFTS = 2        # consecutive shifts sharing a cell before a link forms
LINK_TRANSFER_RATE = 0.10    # share of a light difference that levels out along a link
# Light additionally moves toward whichever end holds the greater link
# affinity, in proportion to what the other end is carrying. This is what makes
# drawing on a neighbour a living in its own right rather than a worse version
# of drawing on the cover layer: a well-stocked neighbour is worth more than a
# thin patch of ground, and holding a great deal of light makes something worth
# drawing on. Nothing here says who should do it.
# ---------------------------------------------------------------------------
# TAKING, AND BEING TAKEN FROM
#
# Links already moved light between specimens by affinity gap, and 306 of them
# were net takers — but nothing could ever be taken past the point of ending.
# Every one of the 600 deaths on record reads "dissolved": ran out of light on
# its own. In a terrain where nothing can be killed there is no second trophic
# level, no refuge worth seeking, and nothing for a classifier to call anything
# but a variation on gathering.
#
# So a pull is no longer capped at half of what the other holds. A strong taker
# on a weak neighbour can draw it to nothing, and what it takes it keeps. The
# taken specimen ends as any other does — its light gone — but the record now
# distinguishes HOW: "dissolved" where it simply ran out, "taken" where another
# specimen drew it down.
#
# Nothing here names a predator, and no specimen is given a role. What exists
# is an affinity gap that can now be fatal. Whether that produces a way of
# living worth naming is the Namer's to decide.
# ---------------------------------------------------------------------------
# RAISED FROM 0.16 AT SHIFT 150, by steward decision.
#
# The steward asked for the pull CEILING to be raised. Measured first: the
# ceiling was never binding. At a mean holding of 3.19 light and a typical
# affinity gap of 0.37, the rate limits a pull to 0.187 light while the ceiling
# would allow 2.937 — sixteen times looser. Raising it would have changed
# nothing and produced a null result from a change that could not have had an
# effect. So the rate is what moves.
#
# 0.16 was chosen before predation existed, when a pull only shuffled light
# between two survivors. It has never been a number set with a predator in mind
# because there were none. Revisiting a constant that predates the mechanism it
# now governs is a different act from tuning until the result is likeable.
#
# CHOSEN SO THAT TAKING IS A LIVE CHOICE, NOT A DOMINANT ONE. At 0.90 an
# average specimen taking from an average neighbour yields about 1.06 against
# grazing's 2.20 — still the worse option. A specimen with a genuinely high
# links-affinity against a low-affinity neighbour yields around 4.9, which
# beats grazing. Specialists can win where generalists cannot. That is the
# condition under which a niche can exist, and it is deliberately not the
# condition under which one must.
#
# The outcome is to be recorded either way, including if no predator appears.
LINK_PULL_RATE = 0.90
PULL_CEILING = 0.95          # share of a neighbour's light a pull may take
PULL_LETHAL_BELOW = 0.35     # a specimen drawn under this is recorded as taken

# How strongly the presence of others changes where a specimen wants to be.
# Above PURSUIT_NEUTRAL a links-affinity reads as attraction; below it, as
# avoidance. The threshold is the population's founding mean, so neither
# direction is privileged at the start.
PURSUIT_NEUTRAL = 1.0
PURSUIT_WEIGHT = 0.55
LINK_DECAY_SHIFTS = 4        # shifts apart before a link lapses

RESIDUE_DECAY = 0.02         # share of residue that dissipates per shift

# ---------------------------------------------------------------------------
# Traits
#
# Everything above describes a world. This describes the only way a thing can
# differ from another thing.
#
# An individual holds three affinities — how well it draws from the census
# layer, from residue, and along links. They are drawn from a FIXED BUDGET, so
# being good at everything is impossible and specialising in one costs the
# others. That constraint is the whole point: without a trade-off there is no
# niche, and without a niche everything lives the same way.
#
# Affinities are heritable. A descendant inherits its parent's, perturbed. The
# perturbation is derived from the parent's identity and the shift number, so
# it varies without being random and the terrain still replays exactly from its
# own record.
#
# No affinity combination is named or preferred. Whether the terrain fills all
# three corners, collapses onto one, or finds something between them is the
# question, not the setting.
# ---------------------------------------------------------------------------

TRAIT_BUDGET = 3.0           # total affinity an individual may hold
TRAIT_FLOOR = 0.15           # no affinity ever reaches zero
TRAIT_DRIFT = 0.34           # how far a descendant may differ from its parent


def _deterministic_unit(seed_text: str) -> float:
    """A repeatable value in [0,1) from a string. Not randomness — a hash.

    Variation has to come from somewhere, and a random number generator would
    make the terrain unreplayable. This gives difference without unpredictability.
    """
    total = 0
    for position, character in enumerate(seed_text):
        total = (total * 131 + ord(character) + position) % 1000003
    return (total % 10007) / 10007.0


def _normalise(traits: Dict[str, float]) -> Dict[str, float]:
    for key in traits:
        traits[key] = max(TRAIT_FLOOR, traits[key])
    scale = TRAIT_BUDGET / sum(traits.values())
    return {k: round(v * scale, 4) for k, v in traits.items()}


def founding_traits(seed_text: str) -> Dict[str, float]:
    """Affinities for something arising from the census layer."""
    return _normalise({
        "cover": 0.4 + _deterministic_unit(seed_text + "|cover") * 2.2,
        "residue": 0.4 + _deterministic_unit(seed_text + "|residue") * 2.2,
        "links": 0.4 + _deterministic_unit(seed_text + "|links") * 2.2,
    })


# ---------------------------------------------------------------------------
# Structure
#
# Affinities say HOW a thing makes its living. Structure says WHAT IT IS BUILT
# LIKE. Three measures, each of which costs light to maintain every shift and
# each of which does something:
#
#   extent     how far it reaches. Multiplies what it can draw from the ground
#              it stands on. Costs upkeep.
#   junctions  how many others it can be linked to at once. Costs upkeep.
#   mass       how much light it can hold before the rest is wasted, and how
#              much it resists being drawn on by others. Costs upkeep.
#
# There is no budget cap here, unlike the affinities. The constraint is the
# bill: an elaborate structure is affordable where light is plentiful and
# ruinous where it is thin. That is the whole mechanism. Nothing decides what
# a thing should look like — structure is inherited, it is paid for every
# shift, and what survives is whatever the light in that part of the terrain
# could actually support.
#
# So form is not designed and not decorative. It is a bet the terrain either
# pays out on or does not.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# WHAT SIZE COSTS  —  amended at shift 184
#
# v1.3 set STRUCTURE_CEILING = 3.2 while the comment beside it claimed "there
# is no budget cap here; the constraint is the bill". Those contradicted, and
# the ceiling was not a refinement on top of a working economy — it was the
# only thing holding size back. Capacity rose 11.0 per unit of mass while
# upkeep rose 0.38, so at every size bigger was strictly better and nothing
# but that number stopped anything from inflating without end.
#
# A ceiling is a decision about how large a thing is allowed to become, made
# by whoever picks the number. That is not this Department's to decide.
#
# So the ceiling is gone and the bill is made real instead. Upkeep on mass and
# on reach now scales SUPER-LINEARLY: doubling either more than doubles what it
# costs to hold together every shift. Nothing forbids a large specimen. What
# limits size is whether the light where it stands can pay for it — which means
# the same physics permits something small on a poor ridge and something large
# in a rich hollow, and neither outcome was chosen in advance.
#
# The exponent is the whole mechanism, so it is stated plainly rather than
# buried: cost grows with the 1.5 power of the measure.
# ---------------------------------------------------------------------------

EXTENT_UPKEEP = 0.22          # light per shift, at the 1.5 power of extent
JUNCTION_UPKEEP = 0.30        # light per shift per junction (discrete, linear)
MASS_UPKEEP = 0.38            # light per shift, at the 1.5 power of mass
SIZE_COST_EXPONENT = 1.5      # how much worse it gets to be large

EXTENT_DRAW_BONUS = 0.90      # how much extent multiplies what it draws
CAPACITY_PER_MASS = 11.0       # light it can hold per unit of mass
MASS_RESISTANCE = 0.22        # how much mass blunts what others pull from it

STRUCTURE_FLOOR = 0.25
STRUCTURE_CEILING = 3.2
STRUCTURE_DRIFT = 0.55


def founding_structure(seed_text: str) -> Dict[str, float]:
    return {
        "extent": round(0.6 + _deterministic_unit(seed_text + "|extent") * 1.2, 3),
        "junctions": round(0.5 + _deterministic_unit(seed_text + "|junctions") * 1.6, 3),
        "mass": round(0.6 + _deterministic_unit(seed_text + "|mass") * 1.2, 3),
    }


def inherited_structure(parent: Dict[str, float], seed_text: str) -> Dict[str, float]:
    out = {}
    for key in ("extent", "junctions", "mass"):
        moved = parent.get(key, 1.0) + (
            _deterministic_unit(seed_text + "|s|" + key) - 0.5) * 2.0 * STRUCTURE_DRIFT
        out[key] = round(max(STRUCTURE_FLOOR, min(STRUCTURE_CEILING, moved)), 3)
    return out


def structural_upkeep(structure: Dict[str, float]) -> float:
    """What this structure costs to hold together, every shift."""
    return (structure.get("extent", 1.0) * EXTENT_UPKEEP
            + structure.get("junctions", 1.0) * JUNCTION_UPKEEP
            + structure.get("mass", 1.0) * MASS_UPKEEP)


def light_capacity(structure: Dict[str, float]) -> float:
    """The most light a thing of this build can hold. Beyond it, intake is lost."""
    return structure.get("mass", 1.0) * CAPACITY_PER_MASS


def inherited_traits(parent: Dict[str, float], seed_text: str) -> Dict[str, float]:
    """A descendant's affinities: the parent's, moved a little."""
    return _normalise({
        key: parent.get(key, 1.0)
        + (_deterministic_unit(seed_text + "|" + key) - 0.5) * 2.0 * TRAIT_DRIFT
        for key in ("cover", "residue", "links")
    })


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def seed_state() -> Dict[str, Any]:
    """A terrain with ground but nothing living in it yet."""
    return {
        "cells": [
            {
                "index": i,
                "position": cell_position(i),
                "census_density": 0.0,
                "census_light": 0.0,
                "census_substrate": None,
                "residue": 0.0,
            }
            for i in range(CELL_COUNT)
        ],
        "individuals": {},
        "links": {},
        "next_individual_number": 0,
        "ended": [],
    }


def seed_census(state: Dict[str, Any], index: int, substrate: str,
                density: float = 0.35, light: float = 6.0) -> None:
    """Place census layer into a cell. Used when a Generator seeds the terrain."""
    cell = state["cells"][index]
    cell["census_density"] = min(CENSUS_MAX_DENSITY, cell["census_density"] + density)
    cell["census_light"] += light
    if cell["census_substrate"] is None:
        cell["census_substrate"] = substrate


def add_individual(state: Dict[str, Any], index: int, substrate: str,
                   shift: int, light: float = STARTING_LIGHT,
                   parent_id: Optional[str] = None,
                   origin: str = "arrival",
                   traits: Optional[Dict[str, float]] = None,
                   structure: Optional[Dict[str, float]] = None) -> str:
    number = state["next_individual_number"]
    state["next_individual_number"] = number + 1
    identifier = "i-%05d" % number
    state["individuals"][identifier] = {
        "id": identifier,
        "cell": index,
        "light": float(light),
        "substrate": substrate,
        "arose_at_shift": shift,
        "last_seen_shift": shift,
        "age": 0,
        "parent_id": parent_id,
        "generation": 0 if parent_id is None else -1,  # set by caller if known
        "origin": origin,
        "moves": 0,
        "drawn_from_census": 0.0,
        "drawn_from_residue": 0.0,
        "drawn_from_links": 0.0,
        "given_to_links": 0.0,
        "descendants": 0,
        "sightings": 1,
        "traits": traits or founding_traits("%s|%d|%d" % (identifier, index, shift)),
        "distance": 0.0,
        "links_severed": 0,
        "links_formed": 0,
        "structure": structure or founding_structure("%s|%d|%d" % (identifier, index, shift)),
    }
    return identifier


# ---------------------------------------------------------------------------
# One shift of physics
# ---------------------------------------------------------------------------


# BASIN-02 holds an order of magnitude more individuals than BASIN-01, because
# it has fifteen times the area at the same per-cell physics. Two of the
# terrain's RECORDS scale with population and had to be bounded so state stays
# workable. Neither bound touches the research record:
#
#   HISTORY_FRAMES   shifts of movement retained for replay. Reduced from 90.
#                    This is a viewing aid; no physics reads it.
#   ENDED_RETAINED   how many ended individuals stay in live state. Every
#                    ending, without exception, is already written to
#                    anomaly_log.jsonl with its end-state at the shift it
#                    happened (clock_in.py). That append-only log is the
#                    permanent record; this list is a working copy.
HISTORY_FRAMES = 30
ENDED_RETAINED = 600


def _record_frame(state: Dict[str, Any], shift: int) -> None:
    """Keep a compact record of where everything was, shift by shift.

    The terrain has always known that things move; nothing was keeping the
    record of it, so an observer could only ever see the latest instant. This
    stores position and light per shift so movement can be watched rather than
    inferred. It is a record of what happened, not an extra mechanism — nothing
    in the physics reads it.
    """
    frames = state.setdefault("history", [])
    frames.append({
        "shift": shift,
        "beings": [
            [b["id"], b["cell"], round(float(b.get("light", 0.0)), 2),
             b.get("structure", {}).get("extent", 1.0),
             b.get("structure", {}).get("junctions", 1.0),
             b.get("structure", {}).get("mass", 1.0),
             int(b.get("generation", 0) or 0), int(b.get("descendants", 0)),
             int(b.get("age", 0))]
            for b in sorted(state["individuals"].values(), key=lambda x: x["id"])
        ],
        "cover": [round(float(c.get("census_density", 0.0)), 3) for c in state["cells"]],
        "residue": [round(float(c.get("residue", 0.0)), 2) for c in state["cells"]],
    })
    if len(frames) > HISTORY_FRAMES:
        del frames[:len(frames) - HISTORY_FRAMES]
    ended = state.get("ended") or []
    if len(ended) > ENDED_RETAINED:
        del ended[:len(ended) - ENDED_RETAINED]


def _backfill_structure(state: Dict[str, Any], shift: int) -> int:
    """Give a build to anything that predates the idea of one.

    Structure arrived at shift 84. The things already living had none. They are
    not re-rolled or replaced — they are each assigned a founding build from
    their own identifier, the same way anything arriving does. What they do next
    is theirs.
    """
    filled = 0
    for identifier, being in state["individuals"].items():
        if not being.get("structure"):
            being["structure"] = founding_structure(
                "%s|backfill|%d" % (identifier, being.get("arose_at_shift", 0)))
            filled += 1
    return filled


def step(state: Dict[str, Any], shift: int, flow: float) -> Dict[str, Any]:
    backfilled = _backfill_structure(state, shift)
    """Advance the terrain one shift. Deterministic. No model call.

    Order matters and is fixed: light arrives, the census layer lives, then
    individuals live, then what ended is settled. Anything that ends this shift
    leaves residue the next shift can take up, never the same one — so nothing
    can consume something that has not finished ending.
    """
    events: Dict[str, Any] = {
        "influx_total": 0.0,
        "census_grew": 0,
        "census_spread": 0,
        "census_died_back": 0,
        "arose_from_census": [],
        "moved": 0,
        "ended": [],
        "replicated": [],
        "links_formed": [],
        "links_lapsed": [],
        "light_along_links": 0.0,
    }

    cells = state["cells"]
    individuals = state["individuals"]

    # -- 0. The terrain extends where something has reached a margin ---------
    _grow(state, events)
    cells = state["cells"]

    # -- 0b. The ground moves -------------------------------------------------
    if shift % LANDSCAPE_STEP_EVERY == 0:
        _evolve_landscape(events)
        for cell in cells:
            cell["position"] = cell_position(cell["index"])

    # -- 1. Light arrives, and the census layer takes its share --------------
    for cell in cells:
        arriving = influx(cell["index"], flow)
        events["influx_total"] += arriving
        if cell["census_density"] > 0.0:
            cell["census_light"] += arriving * CENSUS_UPTAKE * (cell["census_density"] ** 0.5)
        cell["residue"] = round(cell["residue"] * (1.0 - RESIDUE_DECAY), 4)

    # Submerged ground carries no cover and holds nothing standing. What was
    # there when the water reached it is released as residue, which then drains
    # like anything else.
    for cell in cells:
        if not is_land(cell["index"]):
            if cell["census_density"] > 0.0:
                cell["residue"] += cell["census_light"] * 0.5
                cell["census_density"] = 0.0
                cell["census_light"] = 0.0
                cell["census_substrate"] = None

    # -- 2. The census layer lives -------------------------------------------
    spread_into: Dict[int, float] = {}
    for cell in cells:
        density = cell["census_density"]
        if density <= 0.0:
            continue
        cell["census_light"] -= CENSUS_UPKEEP * density

        if cell["census_light"] < 0.0:
            # Not enough light to hold the density it has.
            lost = min(density, CENSUS_DIEBACK_STEP)
            cell["census_density"] = max(0.0, density - lost)
            cell["residue"] += lost * CENSUS_RESIDUE_PER_DENSITY
            cell["census_light"] = 0.0
            events["census_died_back"] += 1
            if cell["census_density"] <= 0.0:
                cell["census_substrate"] = cell["census_substrate"]
            continue

        if (cell["census_light"] >= CENSUS_GROWTH_COST
                and cell["census_density"] < CENSUS_MAX_DENSITY):
            cell["census_light"] -= CENSUS_GROWTH_COST
            cell["census_density"] = min(
                CENSUS_MAX_DENSITY, cell["census_density"] + CENSUS_GROWTH_STEP)
            events["census_grew"] += 1

        if cell["census_density"] >= CENSUS_SPREAD_THRESHOLD:
            # The same per-neighbour step BASIN-01 uses. A cell here has four
            # neighbours rather than two, so cover advances as a front and
            # advances faster. That is a consequence of the geometry under
            # test, not a tuned value, and the step is deliberately unchanged.
            for neighbour in neighbours(cell["index"]):
                spread_into[neighbour] = spread_into.get(neighbour, 0.0) + CENSUS_SPREAD_STEP

    for index, amount in sorted(spread_into.items()):
        cell = cells[index]
        if cell["census_density"] < CENSUS_MAX_DENSITY:
            before = cell["census_density"]
            cell["census_density"] = min(CENSUS_MAX_DENSITY, before + amount)
            if cell["census_substrate"] is None:
                # Inherits from whichever neighbour is denser; ties to the lower
                # index, so the outcome is replayable. Four candidates here
                # rather than two — the same rule over the field neighbourhood.
                best = max(
                    [cells[n] for n in neighbours(index) if cells[n]["census_substrate"]],
                    key=lambda c: (c["census_density"], -c["index"]),
                    default=None,
                )
                if best:
                    cell["census_substrate"] = best["census_substrate"]
            if cell["census_density"] > before:
                events["census_spread"] += 1

    # -- 3. Individuals live --------------------------------------------------
    # What a cell offers is shared among everything standing in it. This is the
    # whole of density-dependence: crowding makes a place poorer, so a place
    # cannot support unlimited occupants and something eventually runs out.
    occupancy: Dict[int, int] = {}
    for identifier in individuals:
        occupancy[individuals[identifier]["cell"]] = occupancy.get(
            individuals[identifier]["cell"], 0) + 1

    for identifier in sorted(individuals):
        being = individuals[identifier]
        cell = cells[being["cell"]]
        share = 1.0 / float(occupancy.get(being["cell"], 1))

        being["age"] += 1
        being["last_seen_shift"] = shift
        being["sightings"] += 1
        # Upkeep runs at the local metabolic rate, and gravity decides what a
        # build costs to hold up. Both scale the same bill, from opposite
        # causes: how fast living runs here, and how heavy being large is.
        rate = metabolic_rate(being["cell"], shift)
        being["light"] -= (INDIVIDUAL_BASE_UPKEEP
                           + structural_upkeep(being.get("structure", {}))
                           * config.GRAVITY) * rate * config.SHIFT_LENGTH

        # Draw from the census layer where it stands.
        if cell["census_density"] > 0.0:
            reach = 1.0 + being.get("structure", {}).get("extent", 1.0) * EXTENT_DRAW_BONUS
            affinity = being["traits"]["cover"] * reach * metabolic_rate(being["cell"], shift)
            taken = min(INDIVIDUAL_DRAW_FROM_CENSUS * share * affinity,
                        (cell["census_light"] + cell["census_density"] * 2.0) * share)
            if taken > 0:
                being["light"] += taken
                being["drawn_from_census"] += taken
                cell["census_light"] = max(0.0, cell["census_light"] - taken * 0.6)
                # Loss scales with how much was actually taken, so sustained
                # drawing strips a cell rather than nibbling it forever. A place
                # that supports one way of living indefinitely is a place where
                # nothing else ever gets an opening.
                cell["census_density"] = max(
                    0.0, cell["census_density"] - CENSUS_LOSS_PER_DRAW * taken)

        # Draw from residue where it stands.
        if cell["residue"] > 0.0:
            reach = 1.0 + being.get("structure", {}).get("extent", 1.0) * EXTENT_DRAW_BONUS
            affinity = being["traits"]["residue"] * reach * metabolic_rate(being["cell"], shift)
            taken = min(INDIVIDUAL_DRAW_FROM_RESIDUE * share * affinity,
                        cell["residue"] * share)
            being["light"] += taken
            being["drawn_from_residue"] += taken
            cell["residue"] -= taken

        capacity = light_capacity(being.get("structure", {}))
        if being["light"] > capacity:
            being["light"] = capacity

        # Move toward whichever neighbouring cell offers more light. Not toward
        # the stream — toward light. The two coincide until the near cells are
        # drawn down, and then they stop coinciding.
        # WHAT A CELL IS WORTH TO THIS PARTICULAR SPECIMEN
        #
        # Movement used to weigh one thing: how much light a cell offers. Every
        # specimen therefore wanted the same places, and nothing ever moved
        # toward or away from another specimen. Taking could only happen where
        # two things were already stuck together, so predation reinforced
        # crowding instead of breaking it — measured across 260 shifts, 51% of
        # deaths became predation and yet 2 specimens in 3,959 lived by it.
        #
        # A cell is now worth what it offers PLUS what its occupants are worth
        # to this specimen, and that second term has opposite sign depending on
        # the specimen's own links-affinity. Something that lives by drawing on
        # others is drawn toward them; something that does not is pushed away,
        # because to it a neighbour is only competition and risk.
        #
        # No specimen is assigned a role. The same rule reads as pursuit for one
        # and avoidance for another, purely from a heritable trait that was
        # already there and already under selection.
        pull = being["traits"]["links"] - PURSUIT_NEUTRAL

        def worth(index, extra):
            occupants = occupancy.get(index, 0) + extra
            offer = _cell_offer(cells[index], max(1, occupants))
            others = occupants - (1 if index == being["cell"] else 0)
            return offer + pull * others * PURSUIT_WEIGHT

        here = worth(being["cell"], 0)
        best_index, best_offer = being["cell"], here
        for neighbour in neighbours(being["cell"]):
            offer = worth(neighbour, 1)
            if offer > best_offer + INDIVIDUAL_MOVE_COST:
                best_index, best_offer = neighbour, offer
        move_cost = INDIVIDUAL_MOVE_COST * config.GRAVITY
        if best_index != being["cell"] and being["light"] > move_cost:
            being["cell"] = best_index
            being["light"] -= move_cost
            being["moves"] += 1
            # Distance travelled, not just a count of moves. A specimen that
            # crosses the terrain and one that shuffles between two cells were
            # previously indistinguishable in the record.
            being["distance"] = round(being.get("distance", 0.0) + 1.0, 2)
            events["moved"] += 1

    # -- 4. Links: proximity that lasts becomes a channel ---------------------
    _update_links(state, shift, events)

    # -- 5. Replication, where there is surplus -------------------------------
    for identifier in sorted(list(individuals)):
        being = individuals[identifier]
        if being["light"] >= REPLICATION_SURPLUS:
            spend = being["light"] * REPLICATION_COST_FRACTION
            being["light"] -= spend
            # Offspring leave. They previously appeared in the parent's own
            # cell, with nothing in the physics ever moving them away from it —
            # which is the whole reason the population piled into a tenth of
            # the terrain and left nine-tenths empty. A descendant now settles
            # in a neighbouring cell, chosen deterministically from its own
            # identifier so the terrain still replays exactly.
            #
            # Nothing here decides WHERE anything should live. It only stops
            # everything being born on top of its parent.
            nearby = neighbours(being["cell"])
            landed = [c for c in nearby if is_land(c)] or [being["cell"]]
            where = landed[int(_deterministic_unit(
                "%s|disperse|%d" % (identifier, being["descendants"])) * len(landed)) % len(landed)]
            child = add_individual(
                state, where, being["substrate"], shift,
                light=spend * 0.8, parent_id=identifier, origin="replication",
                traits=inherited_traits(being["traits"],
                                        "%s|%d|%d" % (identifier, shift, being["descendants"])),
                structure=inherited_structure(being.get("structure", {}),
                                        "%s|%d|%d" % (identifier, shift, being["descendants"])))
            individuals[child]["generation"] = int(being.get("generation", 0) or 0) + 1
            being["descendants"] += 1
            events["replicated"].append((identifier, child))

    # -- 6. An individual arises where the census layer is dense and rich -----
    for cell in cells:
        if (cell["census_density"] >= ARISE_DENSITY
                and cell["census_light"] >= ARISE_LIGHT):
            cell["census_density"] -= ARISE_DENSITY_COST
            cell["census_light"] -= ARISE_LIGHT_COST
            identifier = add_individual(
                state, cell["index"], cell["census_substrate"] or "unknown",
                shift, light=ARISE_LIGHT_COST, origin="arose_from_census")
            individuals[identifier]["generation"] = 0
            events["arose_from_census"].append(identifier)

    # -- 7. What ran out, ends. Its light stays where it fell -----------------
    for identifier in sorted(list(individuals)):
        being = individuals[identifier]
        if being["light"] <= 0.0:
            cell = cells[being["cell"]]
            # What it was carrying stays where it fell, plus what it was made
            # of. A larger, slower pool means an opening exists for long enough
            # that something could come to depend on it.
            cell["residue"] += max(0.0, being["light"]) + 4.5
            record = dict(being)
            record["ended_at_shift"] = shift
            # How it ended is now distinguishable: drawn down by another
            # specimen, or simply out of light.
            taker = being.get("drawn_down_by")
            record["end_state"] = "taken" if taker else "dissolved"
            if taker:
                record["taken_by"] = taker
                events.setdefault("taken_ended", []).append((taker, identifier))
            state["ended"].append(record)
            events["ended"].append(identifier)
            del individuals[identifier]
            for key in [k for k in state["links"] if identifier in k.split("|")]:
                other = [x for x in key.split("|") if x != identifier]
                if other and other[0] in individuals:
                    individuals[other[0]]["links_severed"] = \
                        individuals[other[0]].get("links_severed", 0) + 1
                events.setdefault("links_severed", 0)
                events["links_severed"] += 1
                del state["links"][key]

    # -- 7b. Wind, then water underground ------------------------------------
    _blow(state, events)
    _subsurface(state, events)
    events["metabolic_rate_here"] = metabolic_rate(cells[len(cells)//2]["index"], shift)
    events["light_cycle"] = round(light_cycle(shift), 4)

    # -- 8. Residue runs downhill -------------------------------------------
    # Last, so that what fell this shift drains with everything else. It is
    # still not takeable until the next shift (Section 7); draining moves it,
    # it does not offer it.
    _drain(state, events)

    events["influx_total"] = round(events["influx_total"], 3)
    events["structures_backfilled"] = backfilled
    _record_frame(state, shift)
    return events


def _cell_offer(cell: Dict[str, Any], occupants: int = 1) -> float:
    """What a cell offers ONE occupant, given how many are already sharing it."""
    total = (cell["census_density"] * 3.0) + cell["residue"]
    return total / float(max(1, occupants))


def key_new_link(links, a, b) -> bool:
    """Whether this pairing has not been seen before. Counts formations."""
    return _link_key(a, b) not in links


def _link_key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


def _update_links(state: Dict[str, Any], shift: int, events: Dict[str, Any]) -> None:
    individuals = state["individuals"]
    links = state["links"]

    by_cell: Dict[int, List[str]] = {}
    for identifier in sorted(individuals):
        by_cell.setdefault(individuals[identifier]["cell"], []).append(identifier)

    # Proximity accumulates.
    for cell_index in sorted(by_cell):
        present = by_cell[cell_index]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                a_id, b_id = present[i], present[j]
                held = lambda who: sum(
                    1 for k, v in links.items()
                    if v.get("formed_at_shift") is not None and who in k.split("|"))
                a_cap = 1 + int(individuals[a_id].get("structure", {}).get("junctions", 1.0))
                b_cap = 1 + int(individuals[b_id].get("structure", {}).get("junctions", 1.0))
                if held(a_id) >= a_cap or held(b_id) >= b_cap:
                    continue
                key = _link_key(present[i], present[j])
                for who in (a_id, b_id):
                    if key_new_link(links, a_id, b_id):
                        individuals[who]["links_formed"] = \
                            individuals[who].get("links_formed", 0) + 1
                link = links.setdefault(
                    key, {"together": 0, "last_together_shift": shift,
                          "formed_at_shift": None, "light_moved": 0.0})
                link["together"] += 1
                link["last_together_shift"] = shift
                if link["formed_at_shift"] is None and link["together"] >= LINK_AFTER_SHIFTS:
                    link["formed_at_shift"] = shift
                    events["links_formed"].append(key)

    # Light moves along formed links, down the gradient.
    for key in sorted(links):
        link = links[key]
        if link["formed_at_shift"] is None:
            continue
        a, b = key.split("|")
        if a not in individuals or b not in individuals:
            continue
        first, second = individuals[a], individuals[b]
        difference = first["light"] - second["light"]
        if abs(difference) < 0.1:
            continue
        # Levelling: light drifts from the fuller end toward the emptier one.
        pull = (first["traits"]["links"] + second["traits"]["links"]) / 2.0
        moved = difference * LINK_TRANSFER_RATE * pull

        # Pulling: the end with the greater link affinity draws on what the
        # other end is holding, regardless of which of them holds more.
        affinity_gap = first["traits"]["links"] - second["traits"]["links"]
        resist = lambda b: 1.0 / (1.0 + b.get("structure", {}).get("mass", 1.0) * MASS_RESISTANCE)
        if affinity_gap > 0:
            taken = min(second["light"] * LINK_PULL_RATE * affinity_gap * resist(second),
                        max(0.0, second["light"]) * PULL_CEILING)
            moved -= taken
            if second["light"] - taken < PULL_LETHAL_BELOW:
                second["drawn_down_by"] = first["id"]
                events.setdefault("taken", []).append((first["id"], second["id"]))
        elif affinity_gap < 0:
            taken = min(first["light"] * LINK_PULL_RATE * (-affinity_gap) * resist(first),
                        max(0.0, first["light"]) * PULL_CEILING)
            moved += taken
            if first["light"] - taken < PULL_LETHAL_BELOW:
                first["drawn_down_by"] = second["id"]
                events.setdefault("taken", []).append((second["id"], first["id"]))
        first["light"] -= moved
        second["light"] += moved
        link["light_moved"] += abs(moved)
        events["light_along_links"] += abs(moved)
        giver, taker = (first, second) if moved > 0 else (second, first)
        giver["given_to_links"] += abs(moved)
        taker["drawn_from_links"] += abs(moved)

    # Links lapse when the pair has been apart too long.
    for key in [k for k in sorted(links)
                if shift - links[k]["last_together_shift"] >= LINK_DECAY_SHIFTS]:
        if links[key]["formed_at_shift"] is not None:
            events["links_lapsed"].append(key)
        del links[key]

    events["light_along_links"] = round(events["light_along_links"], 3)


# ---------------------------------------------------------------------------
# Reading the terrain
# ---------------------------------------------------------------------------


def field_rollup(state: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce a 315-cell field to numbers a model can be shown, showing the work.

    BASIN-01 hands the Namer a 21-number density list — one per cell, the whole
    terrain. This field has 315 cells and that list cannot ship, so physics.md
    Section 8's aggregate tier does the reducing. Every number below is defined
    here in one place, and none of it is a black box:

      density_by_depth    21 numbers. The SUM of density across the 15 cells at
                          each depth. Directly comparable in shape and meaning
                          to BASIN-01's per-cell list, because BASIN-01's list
                          IS the depth profile of a one-column field.
      density_by_column   15 numbers. The SUM of density down each column. This
                          is the information a line does not have. A flat
                          profile means cover is spread evenly across the field;
                          a peaked one means it is gathered somewhere.
      patches             count of contiguous occupied regions, by the same
                          four-neighbour adjacency movement uses, and the size
                          of the largest. A line can only ever produce
                          intervals; a field can produce islands.
      occupied_extent     the bounding box of everything occupied, as
                          (min_depth, max_depth, min_lateral, max_lateral).

    The complete untouched grid is written to state/field_log.jsonl every shift,
    so any of these can be recomputed and checked against the raw cells rather
    than taken on trust.
    """
    cells = state["cells"]
    by_depth = [0.0] * FIELD_DEPTH
    by_column = [0.0] * FIELD_WIDTH
    occupied = []
    for cell in cells:
        density = float(cell["census_density"])
        if density <= 0.0:
            continue
        by_depth[cell_depth(cell["index"])] += density
        by_column[cell_lateral(cell["index"])] += density
        occupied.append(cell["index"])

    occupied_set = set(occupied)
    seen = set()
    patch_sizes = []
    for start in sorted(occupied_set):
        if start in seen:
            continue
        stack, size = [start], 0
        seen.add(start)
        while stack:
            here = stack.pop()
            size += 1
            for n in neighbours(here):
                if n in occupied_set and n not in seen:
                    seen.add(n)
                    stack.append(n)
        patch_sizes.append(size)

    depths = [cell_depth(i) for i in occupied]
    laterals = [cell_lateral(i) for i in occupied]
    return {
        "density_by_depth": [round(v, 3) for v in by_depth],
        "density_by_column": [round(v, 3) for v in by_column],
        "patches": len(patch_sizes),
        "largest_patch_cells": max(patch_sizes) if patch_sizes else 0,
        "occupied_extent": {
            "min_depth": min(depths) if depths else None,
            "max_depth": max(depths) if depths else None,
            "min_lateral": min(laterals) if laterals else None,
            "max_lateral": max(laterals) if laterals else None,
        },
        "rollup_note": (
            "depth/column figures are sums of census_density over that row or "
            "column; patches use the same four-neighbour adjacency as movement. "
            "The full grid for this shift is in state/field_log.jsonl."
        ),
    }


def population_spread(state: Dict[str, Any]) -> Dict[str, Any]:
    """How the living are arranged across the field, as distances.

    A line can report how far apart two things are only along one axis. This
    reports mean distance to the nearest other individual, which is the
    measurement that would show spacing or clustering if either occurs. It is
    an observation and nothing in the physics reads it.
    """
    beings = list(state["individuals"].values())
    if len(beings) < 2:
        return {"count": len(beings), "mean_nearest_distance": None,
                "distinct_cells_occupied": len(set(b["cell"] for b in beings))}
    # Nearest-neighbour distance, found through a grid rather than by comparing
    # every pair. The pairwise version is O(n squared): at 10,589 living that is
    # 56 million comparisons every shift, in Python, for one summary number.
    # Bucketing by cell and searching outward from each specimen gives the same
    # answer — these are integer step distances on a grid — at a fraction of the
    # cost, and it is exact rather than sampled.
    buckets = {}
    for b in beings:
        buckets.setdefault((cell_depth(b["cell"]), cell_lateral(b["cell"])), []).append(b["id"])
    nearest = []
    for b in beings:
        d1, l1 = cell_depth(b["cell"]), cell_lateral(b["cell"])
        if len(buckets.get((d1, l1), ())) > 1:
            nearest.append(0)
            continue
        found = None
        for ring in range(1, 24):
            for dd in range(-ring, ring + 1):
                rem = ring - abs(dd)
                for dl in ({-rem, rem} if rem else {0}):
                    if buckets.get((d1 + dd, l1 + dl)):
                        found = ring
                        break
                if found is not None:
                    break
            if found is not None:
                break
        nearest.append(found if found is not None else 24)
    return {
        "count": len(beings),
        "mean_nearest_distance": round(sum(nearest) / float(len(nearest)), 3),
        "max_nearest_distance": max(nearest),
        "distinct_cells_occupied": len(set(b["cell"] for b in beings)),
    }


def census_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    cells = state["cells"]
    occupied = [c for c in cells if c["census_density"] > 0.0]
    return {
        "cells_with_cover": len(occupied),
        "total_density": round(sum(c["census_density"] for c in cells), 3),
        "mean_density_where_present": round(
            sum(c["census_density"] for c in occupied) / len(occupied), 3) if occupied else 0.0,
        "furthest_from_stream": min([c["index"] for c in occupied], default=None),
        "total_residue": round(sum(c["residue"] for c in cells), 3),
        "density_by_cell": [round(c["census_density"], 3) for c in cells],
        "field": field_rollup(state),
    }


def population_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    individuals = state["individuals"]
    if not individuals:
        return {"count": 0, "ended_total": len(state["ended"])}
    lights = [b["light"] for b in individuals.values()]
    ages = [b["age"] for b in individuals.values()]
    formed = [k for k, v in state["links"].items() if v["formed_at_shift"] is not None]
    return {
        "count": len(individuals),
        "ended_total": len(state["ended"]),
        "mean_light": round(sum(lights) / len(lights), 3),
        "max_light": round(max(lights), 3),
        "mean_age": round(sum(ages) / len(ages), 2),
        "oldest_age": max(ages),
        "links_formed": len(formed),
        "by_cell": _population_by_cell(state),
        "origins": _count(individuals, "origin"),
        "substrates": _count(individuals, "substrate"),
    }


def _population_by_cell(state: Dict[str, Any]) -> List[int]:
    counts = [0] * CELL_COUNT
    for being in state["individuals"].values():
        counts[being["cell"]] += 1
    return counts


def _count(individuals: Dict[str, Any], field: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for being in individuals.values():
        key = str(being.get(field))
        out[key] = out.get(key, 0) + 1
    return out
