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

# Cells span the channel gradient. Index 0 is the far margin, the last index
# sits at the data-stream.
CELL_COUNT = 21


def cell_position(index: int) -> float:
    """Position of a cell on the channel gradient, 0.0 (far) to 1.0 (stream)."""
    return round(index / float(CELL_COUNT - 1), 4)


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
                   traits: Optional[Dict[str, float]] = None) -> str:
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
    }
    return identifier


# ---------------------------------------------------------------------------
# One shift of physics
# ---------------------------------------------------------------------------


def step(state: Dict[str, Any], shift: int, flow: float) -> Dict[str, Any]:
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
            for neighbour in (cell["index"] - 1, cell["index"] + 1):
                if 0 <= neighbour < CELL_COUNT:
                    spread_into[neighbour] = spread_into.get(neighbour, 0.0) + CENSUS_SPREAD_STEP

    for index, amount in sorted(spread_into.items()):
        cell = cells[index]
        if cell["census_density"] < CENSUS_MAX_DENSITY:
            before = cell["census_density"]
            cell["census_density"] = min(CENSUS_MAX_DENSITY, before + amount)
            if cell["census_substrate"] is None:
                # Inherits from whichever neighbour is denser; ties to the lower
                # index, so the outcome is replayable.
                left = cells[index - 1] if index > 0 else None
                right = cells[index + 1] if index + 1 < CELL_COUNT else None
                best = max(
                    [c for c in (left, right) if c and c["census_substrate"]],
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
        being["light"] -= INDIVIDUAL_BASE_UPKEEP

        # Draw from the census layer where it stands.
        if cell["census_density"] > 0.0:
            affinity = being["traits"]["cover"]
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
            affinity = being["traits"]["residue"]
            taken = min(INDIVIDUAL_DRAW_FROM_RESIDUE * share * affinity,
                        cell["residue"] * share)
            being["light"] += taken
            being["drawn_from_residue"] += taken
            cell["residue"] -= taken

        # Move toward whichever neighbouring cell offers more light. Not toward
        # the stream — toward light. The two coincide until the near cells are
        # drawn down, and then they stop coinciding.
        here = _cell_offer(cells[being["cell"]], occupancy.get(being["cell"], 1))
        best_index, best_offer = being["cell"], here
        for neighbour in (being["cell"] - 1, being["cell"] + 1):
            if 0 <= neighbour < CELL_COUNT:
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

    events["influx_total"] = round(events["influx_total"], 3)
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
        if affinity_gap > 0:
            moved -= min(second["light"] * LINK_PULL_RATE * affinity_gap,
                         max(0.0, second["light"]) * 0.5)
        elif affinity_gap < 0:
            moved += min(first["light"] * LINK_PULL_RATE * (-affinity_gap),
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
