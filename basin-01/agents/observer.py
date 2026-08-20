# SPDX-FileCopyrightText: 2026 U3 Labs, LLC
# SPDX-License-Identifier: Apache-2.0
"""
BASIN-01 — how the terrain is put in front of the Namer.

The Namer's spec has never changed (README.md Section 5, DNT-CLS-001): compare
specimens against its own system, file or coin or flag, log its reasoning in
full. What changed is what a specimen IS. It used to be a fragment of text with
an integer attached. Now it is something that lived in the terrain — that held
light, drew on something, moved or stayed, persisted or ended.

So this module does one job: turn the state of a living thing into an
observation the Namer can reason about.

WHAT IS DESCRIBED, AND WHAT IS NOT

  Described: what it did. Where it was, what it drew on, how long it has been
  there, whether it moved, whether it left descendants, what it is holding, and
  how it is built — its reach, how many links it can carry, how much it holds,
  and what that build costs it every shift.

  The build is reported as measurement, not as form. It says "reach 1.7,
  costs 1.38 light a shift". It does not say tall, branched, spined or heavy.
  What that adds up to is the Namer's to decide.

  Not described: what it is. No role, no kind, no category, no comparison to
  anything. The words "producer", "consumer", "predator", "parasite" and their
  neighbours appear nowhere in an observation, because naming is the Namer's
  job and an observation that arrives pre-named has already answered the
  question (DNT-CLS-001 Section 1).

  Also not described: any organic analogy. Nothing here says a thing resembles
  anything that exists. It says what the terrain measured.

WHY BEHAVIOUR RATHER THAN CONTENT

  A specimen's substrate — structural notation, language fragment — is still
  recorded, and a trace is drawn from a Generator when something arises. But
  the observation leads with what the thing DID across shifts, because that is
  what the Namer now has to work with and what physics.md Section 6 defines its
  reference roles by. A thing is what it does here.

Python 3.9 compatible.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import life


def _share(part: float, total: float) -> int:
    return int(round(100.0 * part / total)) if total > 0 else 0


def describe_individual(being: Dict[str, Any], shift: int,
                        trace: Optional[str] = None) -> Dict[str, Any]:
    """One living thing, as measured. No interpretation."""
    drawn_census = float(being.get("drawn_from_census", 0.0))
    drawn_residue = float(being.get("drawn_from_residue", 0.0))
    drawn_links = float(being.get("drawn_from_links", 0.0))
    total = drawn_census + drawn_residue + drawn_links

    return {
        "specimen_id": being["id"],
        "substrate": being.get("substrate"),
        "first_seen_shift": being.get("arose_at_shift"),
        "shifts_present": int(being.get("age", 0)),
        "sightings": int(being.get("sightings", 0)),
        "position_cell": being.get("cell"),
        "position_on_gradient": life.cell_position(int(being.get("cell", 0))),
        "light_held": round(float(being.get("light", 0.0)), 2),
        "light_taken_total": round(total, 2),
        "light_from_cover_pct": _share(drawn_census, total),
        "light_from_residue_pct": _share(drawn_residue, total),
        "light_from_links_pct": _share(drawn_links, total),
        "light_given_to_links": round(float(being.get("given_to_links", 0.0)), 2),
        "times_moved": int(being.get("moves", 0)),
        "descendants": int(being.get("descendants", 0)),
        "generation": int(being.get("generation", 0) or 0),
        "parent_id": being.get("parent_id"),
        "arrived_by": being.get("origin"),
        "affinities": being.get("traits", {}),
        "structure": being.get("structure", {}),
        "structural_upkeep": round(life.structural_upkeep(being.get("structure", {})), 2),
        "light_capacity": round(life.light_capacity(being.get("structure", {})), 2),
        "trace": trace,
    }


def observation_text(record: Dict[str, Any]) -> str:
    """The plain description a Namer is shown. Measurements, in sentences."""
    lines = [
        "id: %s" % record["specimen_id"],
        "substrate: %s" % record["substrate"],
        "present for %d shift(s), first seen shift %s, %d sighting(s)"
        % (record["shifts_present"], record["first_seen_shift"], record["sightings"]),
        "position on the gradient: %.2f (0.00 far from the data-stream, 1.00 at it)"
        % record["position_on_gradient"],
        "moved %d time(s)" % record["times_moved"],
        "holding %.2f light; has taken %.2f in total"
        % (record["light_held"], record["light_taken_total"]),
        "of what it took: %d%% from the cover layer, %d%% from residue, "
        "%d%% along links to others"
        % (record["light_from_cover_pct"], record["light_from_residue_pct"],
           record["light_from_links_pct"]),
        "passed %.2f light to others along links" % record["light_given_to_links"],
        "descendants: %d" % record["descendants"],
    ]
    structure = record.get("structure") or {}
    if structure:
        lines.append(
            "how it is built: reach %.2f, holds up to %d link(s) at once, "
            "carries %.2f — which costs %.2f light every shift to maintain, and "
            "lets it hold at most %.2f light at a time"
            % (structure.get("extent", 0.0),
               1 + int(structure.get("junctions", 0.0)),
               structure.get("mass", 0.0),
               record.get("structural_upkeep", 0.0),
               record.get("light_capacity", 0.0)))
    if record.get("parent_id"):
        lines.append("descended from %s (generation %d)"
                     % (record["parent_id"], record["generation"]))
    else:
        lines.append("arose from the cover layer (generation 0)")
    if record.get("trace"):
        lines.append("its substrate as recorded:")
        lines.append(record["trace"])
    return "\n".join(lines)


def census_observation(state: Dict[str, Any]) -> Dict[str, Any]:
    """The cover layer, as a census rather than as instances.

    physics.md Section 8: high-volume, low-complexity activity is recorded as
    count and density per interval, not per instance. This is that record.
    """
    summary = life.census_summary(state)
    cells = state["cells"]
    substrates: Dict[str, int] = {}
    for cell in cells:
        if cell["census_density"] > 0.0 and cell["census_substrate"]:
            substrates[cell["census_substrate"]] = substrates.get(
                cell["census_substrate"], 0) + 1
    return {
        "record_tier": "aggregate",
        "cells_occupied": summary["cells_with_cover"],
        "cells_total": life.CELL_COUNT,
        "total_density": summary["total_density"],
        "mean_density_where_present": summary["mean_density_where_present"],
        "furthest_cell_from_stream": summary["furthest_from_stream"],
        "residue_pool": summary["total_residue"],
        "density_by_cell": summary["density_by_cell"],
        "substrates_present": substrates,
    }


def select_for_observation(state: Dict[str, Any], shift: int,
                           already_observed: Sequence[str],
                           limit: int) -> List[Dict[str, Any]]:
    """Choose which living things the Namer looks at this shift.

    Not everything can be observed every shift — that is true of a terrain with
    a budget and it is true of a field study. physics.md Section 8's two tiers
    are exactly this problem: the cover layer is counted, and individuals are
    looked at.

    The choice is mechanical, so it cannot become a way of showing the Namer
    only the interesting ones. Never seen before comes first, then longest
    present, then most descendants. Ties break on identifier.
    """
    seen = set(already_observed)
    individuals = list(state["individuals"].values())

    unseen = sorted(
        [b for b in individuals if b["id"] not in seen],
        key=lambda b: (-int(b.get("age", 0)), b["id"]),
    )
    known = sorted(
        [b for b in individuals if b["id"] in seen],
        key=lambda b: (-int(b.get("age", 0)), -int(b.get("descendants", 0)), b["id"]),
    )
    return (unseen + known)[:limit]


def ended_since(state: Dict[str, Any], shift: int) -> List[Dict[str, Any]]:
    """Everything that ended this shift. Nothing is dropped silently
    (physics.md Section 7)."""
    return [dict(b) for b in state["ended"] if b.get("ended_at_shift") == shift]
