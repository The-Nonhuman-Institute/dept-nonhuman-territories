"""
BASIN-01 — Cartographer.

physics.md Section 4.5.

  Frequency   low — every 5th to 10th shift, gated in code (config.py).
  Maintains   a lightweight positional and relational record: proximity,
              density, zones.
  Does NOT    generate, and does NOT classify.

THIS ROLE MAKES NO MODEL CALL.

physics.md Section 4.5 is explicit that the Cartographer is "purely positional
and relational tracking" and "feeds future visualization honestly, from real
data". Every quantity it records — which zone a specimen occupied, how dense a
zone is, which categories co-occurred within a shift — is already determined by
the record. Asking a model to describe those numbers would introduce a
paraphrase where a measurement exists, and a paraphrase can be wrong in ways a
count cannot.

So the pass is arithmetic. It costs nothing, it cannot hallucinate a
relationship that is not in the data, and "honestly, from real data" is
satisfied literally rather than by intention. The ledger still receives the
pass so the shift record shows it ran.

Zones are defined by position on the resource channel, which is the only
spatial dimension this terrain has. They are descriptive containers for the
record, not places anything is seeded toward.

Python 3.9 compatible.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

ROLE = "cartographer"

# Channel position bands. The boundaries are fixed and descriptive.
ZONE_BOUNDARIES = (
    ("channel_proximate", 0.66, 1.00),
    ("channel_intermediate", 0.34, 0.66),
    ("channel_distant", 0.00, 0.34),
)


def zone_for_position(position: float) -> str:
    for name, lower, upper in ZONE_BOUNDARIES:
        if lower <= float(position) <= upper:
            return name
    return "unplaced"


def build_record(
    shift_number: int,
    specimen_records: Sequence[Dict[str, Any]],
    memory: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute the positional and relational record. Pure arithmetic."""

    zones: Dict[str, Dict[str, Any]] = {}
    for name, lower, upper in ZONE_BOUNDARIES:
        zones[name] = {
            "position_range": [lower, upper],
            "specimen_count": 0,
            "categories_present": {},
            "complexity_total": 0,
        }

    # Which categories appeared together within the same shift. Co-occurrence
    # is a relation the record already contains; it is counted, not inferred.
    per_shift_categories: Dict[int, List[str]] = {}

    for record in specimen_records:
        position = record.get("position")
        if position is None:
            position = (
                config.GENERATOR_A_POSITION
                if record.get("source_role") == "generator_a"
                else config.GENERATOR_B_POSITION
            )
        zone_name = zone_for_position(position)
        zone = zones.setdefault(
            zone_name,
            {"position_range": None, "specimen_count": 0,
             "categories_present": {}, "complexity_total": 0},
        )
        zone["specimen_count"] += 1
        zone["complexity_total"] += int(record.get("complexity") or 0)

        category = (record.get("classification") or {}).get("category")
        if category:
            zone["categories_present"][category] = (
                zone["categories_present"].get(category, 0) + 1
            )
            shift_of = int(record.get("shift", -1))
            per_shift_categories.setdefault(shift_of, [])
            if category not in per_shift_categories[shift_of]:
                per_shift_categories[shift_of].append(category)

    for zone in zones.values():
        count = zone["specimen_count"]
        zone["mean_complexity"] = (
            round(zone["complexity_total"] / count, 3) if count else None
        )
        zone.pop("complexity_total")

    co_occurrence: Dict[str, int] = {}
    for categories in per_shift_categories.values():
        ordered = sorted(set(categories))
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                key = "%s | %s" % (ordered[i], ordered[j])
                co_occurrence[key] = co_occurrence.get(key, 0) + 1

    total = sum(zone["specimen_count"] for zone in zones.values())

    return {
        "pass_at_shift": shift_number,
        "method": "computed from the record; no model call made",
        "zone_definition": "position on the resource channel",
        "zones": zones,
        "specimens_placed": total,
        "density_by_zone": {
            name: (round(zone["specimen_count"] / total, 4) if total else 0.0)
            for name, zone in zones.items()
        },
        "category_co_occurrence_within_a_shift": co_occurrence,
        "resource_flow_this_pass": config.resource_flow_for_shift(shift_number),
        "note": (
            "Positional and relational only. This record does not classify, "
            "rank, or interpret; it counts what the specimen record already "
            "contains (physics.md Section 4.5)."
        ),
    }


def run(
    shift_number: int,
    writer: Any,
    ledger: config.ShiftLedger,
    taxonomy_native: Any,
    memory: Dict[str, Any],
    specimen_records: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Write the positional record. Makes no model call, so it cannot halt on
    budget and cannot fail on an unparseable response."""
    record = build_record(shift_number, specimen_records, memory)
    writer.write_annotation(record)
    return {
        "written": True,
        "halt_reason": None,
        "specimens_placed": record["specimens_placed"],
        "zones": len([z for z in record["zones"].values() if z["specimen_count"]]),
        "cost_usd": 0.0,
    }
