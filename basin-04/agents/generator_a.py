"""
BASIN-01 — Generator A.

Constraint set, FINAL at seed (README.md Section 4). Never altered mid-run
(physics.md Section 4.1).

  Substrate            structural / symbolic notation only. No natural-language
                       prose.
  Resource dependency  output allowance scales UP with proximity to the
                       data-stream channel variable. More material available
                       means a larger and more deeply nested output permitted.
  Initiation           self-initiating, once per shift.
  Constraint           hard maximum output length; no external references.

This role holds no write capability. It returns emissions to the shift loop and
persists nothing itself (see terrain_io.writer_for_role).

The resource variable is applied entirely in code below. It is never mentioned
to the model: the allowance the model receives is already the resource-scaled
number, so the model is told what it may work with and nothing about why. That
keeps the operative instruction free of any term that could imply a target
(physics.md Section 3).

Python 3.9 compatible.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

ROLE = "generator_a"
SUBSTRATE = "structural"

# Output allowance bounds, in tokens. The upper bound is clamped again by
# config.MAX_OUTPUT_TOKENS_BY_ROLE, which is the authoritative ceiling.
MIN_ALLOWANCE_TOKENS = 96
MAX_ALLOWANCE_TOKENS = 512

# Permitted nesting bounds. Also resource-scaled.
MIN_PERMITTED_DEPTH = 1
MAX_PERMITTED_DEPTH = 5

INITIATIONS_PER_SHIFT = 1

_OPENERS = "([{"
_CLOSERS = ")]}"


# ---------------------------------------------------------------------------
# Resource logic — in code, never in the prompt
# ---------------------------------------------------------------------------


def resource_available(position: float, flow: float) -> float:
    """Material available to this role this interval, in [0.0, 1.0].

    Scales with proximity to the channel: this role sits channel-proximate, so
    a higher flow value yields a larger allowance.
    """
    return max(0.0, min(1.0, float(position) * float(flow)))


def output_allowance(available: float) -> int:
    span = MAX_ALLOWANCE_TOKENS - MIN_ALLOWANCE_TOKENS
    allowance = MIN_ALLOWANCE_TOKENS + int(round(span * available))
    return config.output_cap_for_role(ROLE, allowance)


def permitted_depth(available: float) -> int:
    span = MAX_PERMITTED_DEPTH - MIN_PERMITTED_DEPTH
    return MIN_PERMITTED_DEPTH + int(round(span * available))


# ---------------------------------------------------------------------------
# Operative instruction — substrate and constraint only
#
# No target, no category, no example of an acceptable output, no quality bar.
# If this text could be satisfied by imitating some known form, it is wrong and
# must be rewritten (README.md Section 4).
# ---------------------------------------------------------------------------


def _system_prompt(allowance_tokens: int, depth_limit: int) -> str:
    return (
        "Your substrate is structural notation only: functions, loops, nested "
        "structures, and symbolic notation.\n"
        "You may not produce natural-language prose, explanation, commentary, "
        "or annotation.\n"
        "Nesting may reach %d levels.\n"
        "Your output may not exceed %d tokens.\n"
        "Do not reference anything outside your own output.\n"
        "Return the notation and nothing else."
        % (depth_limit, allowance_tokens)
    )


_INITIATION = "Initiate."

# Replication mode (physics.md Section 3). A specimen that met the fixed
# eligibility threshold claims an initiation slot and works from its own prior
# material. The instruction adds no target and no direction — it names the
# material and nothing else. The material is the terrain's own prior output;
# nothing authored by the steward ever enters here.
_REPLICATION_INITIATION = (
    "Initiate from this prior material:\n\n%s\n\nReturn the notation and nothing else."
)


# ---------------------------------------------------------------------------
# Mechanical measurement
#
# Complexity is computed here, from the returned text, by counting. It is never
# asked of the model and never a judgment call, because the code-enforced
# promotion rule (config.py Section 6) reads it.
# ---------------------------------------------------------------------------


def measure_depth(text: str) -> int:
    depth = 0
    deepest = 0
    for character in text:
        if character in _OPENERS:
            depth += 1
            if depth > deepest:
                deepest = depth
        elif character in _CLOSERS:
            depth = max(0, depth - 1)
    return deepest


def measure_complexity(text: str) -> int:
    """A count, not an assessment.

    Combines how deep the notation's nesting reaches, how many distinct symbols
    it uses, and how many lines it occupies.
    """
    if not text.strip():
        return 0
    lines = [line for line in text.splitlines() if line.strip()]
    distinct_symbols = len({c for c in text if not c.isalnum() and not c.isspace()})
    return (measure_depth(text) * 4) + distinct_symbols + len(lines)


# ---------------------------------------------------------------------------
# Initiation
# ---------------------------------------------------------------------------


def run(
    shift_number: int,
    resource_flow: float,
    ledger: config.ShiftLedger,
    position: float = config.GENERATOR_A_POSITION,
    source_material: Optional[Sequence[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Self-initiate for this shift.

    Returns (emissions, halt_reason). A halt_reason means a ceiling was reached
    and this role stopped early; the shift loop records that and closes cleanly
    rather than letting the shift run unbounded.
    """
    available = resource_available(position, resource_flow)
    allowance = output_allowance(available)
    depth_limit = permitted_depth(available)

    emissions: List[Dict[str, Any]] = []
    halt_reason: Optional[str] = None

    material = list(source_material or [])

    for index in range(INITIATIONS_PER_SHIFT):
        parent = material[index] if index < len(material) else None
        prompt = (
            _REPLICATION_INITIATION % parent["content"] if parent else _INITIATION
        )
        try:
            result = config.generate(
                prompt=prompt,
                role=ROLE,
                system=_system_prompt(allowance, depth_limit),
                ledger=ledger,
                max_output_tokens=allowance,
            )
        except config.BudgetExceeded as exc:
            halt_reason = "budget: %s" % (exc,)
            break

        text = result.text.strip()
        emissions.append(
            {
                "source_role": ROLE,
                "substrate": SUBSTRATE,
                "shift": shift_number,
                "initiation_index": index,
                "position": position,
                "resource_flow": resource_flow,
                "resource_available": round(available, 4),
                "output_allowance_tokens": allowance,
                "permitted_depth": depth_limit,
                "content": text,
                "complexity": measure_complexity(text),
                "measured_depth": measure_depth(text),
                "empty": not bool(text),
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
    print("role      : %s" % ROLE)
    print("position  : %.2f   flow: %.2f" % (config.GENERATOR_A_POSITION, config.RESOURCE_FLOW_BASELINE))
    available = resource_available(config.GENERATOR_A_POSITION, config.RESOURCE_FLOW_BASELINE)
    print("available : %.4f -> allowance %d tokens, depth %d"
          % (available, output_allowance(available), permitted_depth(available)))
    print("halt      : %s" % halt)
    for emission in emissions:
        print("")
        print("complexity=%d depth=%d tokens_out=%d truncated=%s"
              % (emission["complexity"], emission["measured_depth"],
                 emission["output_tokens"], emission["truncated"]))
        print("-" * 60)
        print(emission["content"][:900])
