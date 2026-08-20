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

FIELD_DEPTH = 21     # identical to BASIN-01's CELL_COUNT — the gradient axis
FIELD_WIDTH = 15     # lateral room. Carries no gradient; every column is equal.
CELL_COUNT = FIELD_DEPTH * FIELD_WIDTH


def cell_depth(index: int) -> int:
    """How far along the gradient a cell sits. 0 is the far margin."""
    return index // FIELD_WIDTH


def cell_lateral(index: int) -> int:
    """Where a cell sits across the field. Carries no resource meaning."""
    return index % FIELD_WIDTH


def cell_index(depth: int, lateral: int) -> int:
    return depth * FIELD_WIDTH + lateral


def neighbours(index: int) -> List[int]:
    """The four cardinal neighbours. The 2D analogue of BASIN-01's index +/- 1.

    Cardinal only, not diagonal: BASIN-01's neighbourhood is every cell one
    step away along its single axis, and this is every cell one step away along
    either axis. Adding diagonals would be a second change.
    """
    depth, lateral = cell_depth(index), cell_lateral(index)
    out = []
    if depth > 0:
        out.append(cell_index(depth - 1, lateral))
    if depth < FIELD_DEPTH - 1:
        out.append(cell_index(depth + 1, lateral))
    if lateral > 0:
        out.append(cell_index(depth, lateral - 1))
    if lateral < FIELD_WIDTH - 1:
        out.append(cell_index(depth, lateral + 1))
    return out


# ---------------------------------------------------------------------------
# RELIEF AND DRAINAGE  —  added at shift 141, logged as a terrain event
#
# For 140 shifts this field was 315 cells and only 21 kinds of place: a cell
# differed from another cell in exactly one way, its depth on the light
# gradient. 294 cells were duplicates of some other cell. The Namer classified
# 647 specimens into effectively one category across that whole run, and the
# most likely reason is that there was one way to make a living because there
# was one kind of place to make it in.
#
# Elevation is INDEPENDENT of depth. If it tracked depth it would be the light
# gradient again under another name and would add nothing. It is a second axis:
# two cells at the same depth, receiving identical light, can now sit at
# different heights.
#
# Height does exactly one thing: RESIDUE RUNS DOWNHILL. What falls on a ridge
# drains away; what falls in a hollow stays and pools. Light is untouched and
# remains a pure function of depth, so the gradient this terrain was built to
# hold constant is still held constant.
#
# The consequence is two ways of living where there was one. On a ridge a
# specimen must harvest the cover layer, because nothing accumulates under it.
# In a hollow it can live off what has drained in. Residue-affinity is already
# heritable and has been under almost no selection, because residue was spread
# thinly everywhere. Now where a thing stands decides whether that trait is
# worth anything.
#
# Nothing here decides what should evolve. It makes the field uneven and lets
# the light economy sort it out.
# ---------------------------------------------------------------------------

ELEVATION_RANGE = 6.0      # height between the lowest hollow and highest ridge
DRAINAGE_RATE = 0.34       # share of a cell's residue that runs downhill per shift
DRAINAGE_MIN_DROP = 0.15   # height difference below which nothing flows


def cell_elevation(index: int) -> float:
    """Height of a cell, 0.0 (hollow) to 1.0 (ridge). Independent of depth.

    Deterministic and smooth rather than random: the terrain must replay
    identically, and scattered noise would make isolated pits instead of the
    connected ridges and hollows that drainage needs to do anything.
    """
    d = cell_depth(index) / float(max(1, FIELD_DEPTH - 1))
    l = cell_lateral(index) / float(max(1, FIELD_WIDTH - 1))
    value = (math.sin(l * math.pi * 2.0 + 0.7) * 0.5
             + math.sin(d * math.pi * 1.5 + 1.9) * 0.32
             + math.sin((l + d) * math.pi * 3.1) * 0.18)
    return round((value + 1.0) / 2.0, 4)


def cell_height(index: int) -> float:
    """Elevation in the same units residue and light are measured against."""
    return cell_elevation(index) * ELEVATION_RANGE


def _drain(state: Dict[str, Any], events: Dict[str, Any]) -> None:
    """Residue runs downhill. Ridges shed; hollows collect."""
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
        moving = here * DRAINAGE_RATE
        deltas[index] -= moving
        for n in downhill:
            deltas[n] += moving * (drop[n] / total_drop)
        moved_total += moving
    for cell in cells:
        cell["residue"] = round(max(0.0, cell["residue"] + deltas[cell["index"]]), 4)
    events["residue_drained"] = round(moved_total, 3)


def cell_position(index: int) -> float:
    """Position on the gradient, 0.0 (far margin) to 1.0 (data-stream).

    A function of depth only. Lateral position does not affect light, which is
    what makes sideways movement free and is the whole point of this terrain.
    """
    return round(cell_depth(index) / float(FIELD_DEPTH - 1), 4)


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
LINK_PULL_RATE = 0.16
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

    # -- 1. Light arrives, and the census layer takes its share --------------
    for cell in cells:
        arriving = influx(cell["index"], flow)
        events["influx_total"] += arriving
        if cell["census_density"] > 0.0:
            cell["census_light"] += arriving * CENSUS_UPTAKE * (cell["census_density"] ** 0.5)
        cell["residue"] = round(cell["residue"] * (1.0 - RESIDUE_DECAY), 4)

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
        being["light"] -= INDIVIDUAL_BASE_UPKEEP + structural_upkeep(
            being.get("structure", {}))

        # Draw from the census layer where it stands.
        if cell["census_density"] > 0.0:
            reach = 1.0 + being.get("structure", {}).get("extent", 1.0) * EXTENT_DRAW_BONUS
            affinity = being["traits"]["cover"] * reach
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
            affinity = being["traits"]["residue"] * reach
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
        here = _cell_offer(cells[being["cell"]], occupancy.get(being["cell"], 1))
        best_index, best_offer = being["cell"], here
        for neighbour in neighbours(being["cell"]):
            offer = _cell_offer(cells[neighbour], occupancy.get(neighbour, 0) + 1)
            if offer > best_offer + INDIVIDUAL_MOVE_COST:
                best_index, best_offer = neighbour, offer
        if best_index != being["cell"] and being["light"] > INDIVIDUAL_MOVE_COST:
            being["cell"] = best_index
            being["light"] -= INDIVIDUAL_MOVE_COST
            being["moves"] += 1
            events["moved"] += 1

    # -- 4. Links: proximity that lasts becomes a channel ---------------------
    _update_links(state, shift, events)

    # -- 5. Replication, where there is surplus -------------------------------
    for identifier in sorted(list(individuals)):
        being = individuals[identifier]
        if being["light"] >= REPLICATION_SURPLUS:
            spend = being["light"] * REPLICATION_COST_FRACTION
            being["light"] -= spend
            child = add_individual(
                state, being["cell"], being["substrate"], shift,
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
            record["end_state"] = "dissolved"
            state["ended"].append(record)
            events["ended"].append(identifier)
            del individuals[identifier]
            for key in [k for k in state["links"] if identifier in k.split("|")]:
                del state["links"][key]

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
            moved -= min(second["light"] * LINK_PULL_RATE * affinity_gap * resist(second),
                         max(0.0, second["light"]) * 0.5)
        elif affinity_gap < 0:
            moved += min(first["light"] * LINK_PULL_RATE * (-affinity_gap) * resist(first),
                         max(0.0, first["light"]) * 0.5)
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
    coords = [(cell_depth(b["cell"]), cell_lateral(b["cell"])) for b in beings]
    nearest = []
    for i, (d1, l1) in enumerate(coords):
        best = None
        for j, (d2, l2) in enumerate(coords):
            if i == j:
                continue
            dist = abs(d1 - d2) + abs(l1 - l2)      # steps, the way they move
            if best is None or dist < best:
                best = dist
        nearest.append(best)
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
