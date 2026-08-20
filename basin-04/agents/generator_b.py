# SPDX-FileCopyrightText: 2026 U3 Labs, LLC
# SPDX-License-Identifier: Apache-2.0
"""
BASIN-01 — Generator B.

Constraint set, FINAL at seed (README.md Section 4). Never altered mid-run
(physics.md Section 4.1).

  Substrate            short natural-language text fragments only. No code, no
                       markup, no structural notation.
  Resource dependency  INVERSE of Generator A. Initiation frequency and novelty
                       scale UP with DISTANCE from the data-stream channel
                       variable — scarcity-driven rather than abundance-driven.
  Initiation           self-initiating, multiple times per shift.
  Constraint           hard maximum fragment length. No continuity requirement
                       is imposed across fragments.

Two consequences of the constraint set are enforced structurally rather than by
instruction:

  1. No continuity is seeded. Each initiation is an independent call that
     carries no context from the ones before it — this role is never shown its
     own prior fragments, nor anything from the specimen record. Any continuity
     that appears across fragments is therefore this role's own behavior, not
     something the terrain asked for (README.md Section 4).

  2. Novelty scales with distance mechanically. Distance raises the number of
     independent, context-free initiations in a shift, so variance between
     fragments rises with distance without any instruction to vary.

This role holds no write capability. It returns emissions to the shift loop and
persists nothing itself.

Python 3.9 compatible.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

ROLE = "generator_b"
SUBSTRATE = "fragment"

# Hard maximum length of a single fragment, in tokens. Clamped again by
# config.MAX_OUTPUT_TOKENS_BY_ROLE, which is the authoritative ceiling.
FRAGMENT_MAX_TOKENS = 48

# Initiation count bounds. Scales with distance, not with proximity.
MIN_INITIATIONS = 1
MAX_INITIATIONS = 4

_STRUCTURAL_MARKERS = ("{", "}", "[", "]", "()", "=>", "->", "::", "```", "<", ">")


# ---------------------------------------------------------------------------
# Resource logic — inverse, and in code rather than in the prompt
# ---------------------------------------------------------------------------


def channel_distance(position: float) -> float:
    """Distance from the channel, in [0.0, 1.0]. The inverse of proximity."""
    return max(0.0, min(1.0, 1.0 - float(position)))


def scarcity(position: float, flow: float) -> float:
    """How sparse the material is at this role's position, in [0.0, 1.0].

    Rises with distance from the channel, and rises further as flow falls. This
    is the value that drives initiation frequency upward.
    """
    distance = channel_distance(position)
    return max(0.0, min(1.0, distance * (1.0 - (float(flow) * 0.5))))


def initiation_count(scarcity_value: float) -> int:
    span = MAX_INITIATIONS - MIN_INITIATIONS
    return MIN_INITIATIONS + int(round(span * scarcity_value))


def fragment_allowance() -> int:
    return config.output_cap_for_role(ROLE, FRAGMENT_MAX_TOKENS)


# ---------------------------------------------------------------------------
# Operative instruction — substrate and constraint only
#
# No topic, no theme, no target, no example, no quality bar, and nothing about
# how one fragment should relate to another.
# ---------------------------------------------------------------------------


def _system_prompt(allowance_tokens: int) -> str:
    return (
        "Your substrate is short natural-language text fragments only.\n"
        "You may not produce code, markup, notation, lists, or headings.\n"
        "Return one fragment of at most %d tokens.\n"
        "Return the fragment and nothing else."
        % (allowance_tokens,)
    )


_INITIATION = "Initiate."

# Replication mode (physics.md Section 3). See generator_a.py — the same
# mechanism, and the same restriction: the instruction names prior material and
# adds no target, no theme and no direction.
_REPLICATION_INITIATION = (
    "Initiate from this prior material:\n\n%s\n\nReturn the fragment and nothing else."
)


# ---------------------------------------------------------------------------
# Mechanical measurement
# ---------------------------------------------------------------------------


def measure_complexity(text: str) -> int:
    """A count, not an assessment.

    Combines how many distinct terms the fragment uses with its length, so that
    a longer fragment of repeated terms does not measure as more complex than a
    shorter varied one.
    """
    if not text.strip():
        return 0
    terms = [t.strip(".,;:!?\"'()").lower() for t in text.split()]
    terms = [t for t in terms if t]
    if not terms:
        return 0
    distinct = len(set(terms))
    return distinct + (len(terms) // 4)


def contains_structural_notation(text: str) -> bool:
    """Constraint check, recorded rather than corrected.

    A fragment carrying notation is a violation of this role's substrate
    constraint. It is measured and logged as an observed outcome — the terrain
    does not edit, retry, or steer the output away from it (physics.md
    Section 3).
    """
    return any(marker in text for marker in _STRUCTURAL_MARKERS)


# ---------------------------------------------------------------------------
# Initiation
# ---------------------------------------------------------------------------


def run(
    shift_number: int,
    resource_flow: float,
    ledger: config.ShiftLedger,
    position: float = config.GENERATOR_B_POSITION,
    source_material: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Self-initiate for this shift.

    Each initiation is a separate call with no shared context. Returns
    (emissions, halt_reason); a halt_reason means a ceiling stopped further
    initiations, and whatever was already produced is returned rather than lost.
    """
    scarcity_value = scarcity(position, resource_flow)
    count = initiation_count(scarcity_value)
    allowance = fragment_allowance()

    emissions: List[Dict[str, Any]] = []
    halt_reason: Optional[str] = None

    material = list(source_material or [])

    for index in range(count):
        parent = material[index] if index < len(material) else None
        prompt = (
            _REPLICATION_INITIATION % parent["content"] if parent else _INITIATION
        )
        try:
            result = config.generate(
                prompt=prompt,
                role=ROLE,
                system=_system_prompt(allowance),
                ledger=ledger,
                max_output_tokens=allowance,
            )
        except config.BudgetExceeded as exc:
            halt_reason = "budget: %s (halted after %d of %d initiations)" % (
                exc,
                index,
                count,
            )
            break

        text = result.text.strip()
        emissions.append(
            {
                "source_role": ROLE,
                "substrate": SUBSTRATE,
                "shift": shift_number,
                "initiation_index": index,
                "initiations_this_shift": count,
                "position": position,
                "resource_flow": resource_flow,
                "channel_distance": round(channel_distance(position), 4),
                "scarcity": round(scarcity_value, 4),
                "fragment_allowance_tokens": allowance,
                "content": text,
                "complexity": measure_complexity(text),
                "empty": not bool(text),
                "constraint_violation_notation": contains_structural_notation(text),
                "replicated": bool(parent),
                "parent_id": (parent or {}).get("specimen_id"),
                "generation": int((parent or {}).get("generation", 0)) + 1 if parent else 0,
                "truncated": result.truncated,
                "model": result.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cost_usd": result.cost_usd,
            }
        )

    return emissions, halt_reason


if __name__ == "__main__":
    ledger = config.ShiftLedger(shift_number=-1, cumulative_spend_usd=0.0)
    emissions, halt = run(
        shift_number=-1, resource_flow=config.RESOURCE_FLOW_BASELINE, ledger=ledger
    )
    scarcity_value = scarcity(config.GENERATOR_B_POSITION, config.RESOURCE_FLOW_BASELINE)
    print("role      : %s" % ROLE)
    print("position  : %.2f   flow: %.2f" % (config.GENERATOR_B_POSITION, config.RESOURCE_FLOW_BASELINE))
    print("distance  : %.4f   scarcity: %.4f -> %d initiations of %d tokens"
          % (channel_distance(config.GENERATOR_B_POSITION), scarcity_value,
             initiation_count(scarcity_value), fragment_allowance()))
    print("halt      : %s" % halt)
    for emission in emissions:
        print("")
        print("[%d] complexity=%d tokens_out=%d notation=%s"
              % (emission["initiation_index"], emission["complexity"],
                 emission["output_tokens"], emission["constraint_violation_notation"]))
        print("    %s" % emission["content"][:400])
