"""
BASIN-01 — Keeper.

physics.md Section 4.3 and DNT-SLP-001 Section 5.

  Runs        at the start of each shift.
  Reads       prior terrain state and a capped window of recent specimen
              records.
  Produces    a short factual "state of the terrain" summary.
  Inactive    at shift 0 — there is no prior state to read.

The Keeper is this terrain's continuity mechanism. Shifts are discontinuous by
design (physics.md Section 5), so without it every shift would begin cold. The
summary is itself logged, because it is the means by which a human-clocked,
gap-separated system carries behavior forward rather than restarting.

ONE HARD RESTRICTION, ENFORCED BY WIRING RATHER THAN BY INSTRUCTION:

  The Keeper's summary never reaches a Generator.

  physics.md Section 4.1 says a Generator is "never told what to produce — only
  what it may work with", and README.md Section 4 restricts a Generator's
  operative instruction to substrate and constraint alone. A summary describing
  what the terrain already contains, injected into a Generator's prompt, would
  be exactly the shape-seeding physics.md Section 3 forbids — the Generator
  would be reading a description of prior output and could converge toward it.
  It would also be creative direction arriving through the back door, which
  DNT-STW-001 Section 4 identifies as the specific way non-interference gets
  quietly compromised without any rule technically breaking.

  The summary is therefore written to terrain state and passed only to roles
  that reason over history: the Namer, and later the Archivist and
  Cartographer. The Generators take no summary argument at all, so there is no
  wiring through which it could arrive.

This role holds a narrow write capability: the continuity summary, and nothing
else. It cannot write specimen records, cannot touch the taxonomy, and cannot
address a path.

Python 3.9 compatible.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

ROLE = "keeper"

# How many recent specimen records the Keeper is shown. Smaller than the
# Namer's window: the Keeper is summarising terrain state, not classifying, and
# its output feeds every later shift, so its input stays cheap.
KEEPER_RECENT_WINDOW = 6


def _system_prompt() -> str:
    return (
        "You produce a short factual summary of the current state of a bounded "
        "environment, for continuity between separated intervals of "
        "activity.\n"
        "\n"
        "Describe what is present now and how it has changed. Report only what "
        "the figures and records in front of you show.\n"
        "\n"
        "Do not recommend what should happen next.\n"
        "Do not evaluate whether the state is good, interesting, or "
        "successful.\n"
        "Do not speculate about what any category might represent.\n"
        "\n"
        "Write at most six sentences of plain prose. No headings, no lists."
    )


def _build_input(
    shift_number: int,
    memory: Dict[str, Any],
    recent_specimens: Sequence[Dict[str, Any]],
) -> str:
    counts = memory.get("specimen_counts", {}) or {}
    category_stats = memory.get("category_stats", {}) or {}
    structure = memory.get("taxonomy_structure") or {}
    previous = memory.get("keeper_summary") or {}

    lines = [
        "INTERVAL: %d" % shift_number,
        "COMPLETED INTERVALS SO FAR: %s" % memory.get("shifts_completed", 0),
        "",
        "RECORD COUNTS:",
        "  specimens recorded      : %s" % counts.get("total", 0),
        "  individual-tier records : %s" % counts.get("individual_records", 0),
        "  aggregate-tier records  : %s" % counts.get("aggregate_members", 0),
        "  flagged anomalous       : %s" % counts.get("anomalous", 0),
        "",
        "CATEGORIES IN USE (label, members, mean complexity):",
    ]
    if category_stats:
        for label, entry in sorted(category_stats.items()):
            lines.append(
                "  %s — %s member(s), mean complexity %.1f, first seen interval %s"
                % (
                    label,
                    entry.get("count", 0),
                    float(entry.get("mean_complexity", 0.0)),
                    entry.get("first_seen_shift"),
                )
            )
    else:
        lines.append("  (none coined yet)")

    lines += [
        "",
        "CLASSIFICATION SYSTEM SHAPE:",
        "  top-level entries: %s, maximum depth: %s"
        % (structure.get("top_level_entries"), structure.get("max_depth")),
        "",
        "RESOURCE LEVEL THIS INTERVAL: %.4f"
        % config.resource_flow_for_shift(shift_number),
    ]

    if previous.get("text"):
        lines += [
            "",
            "YOUR SUMMARY FROM INTERVAL %s:" % previous.get("shift"),
            previous["text"],
        ]

    if recent_specimens:
        lines += ["", "MOST RECENT SPECIMEN RECORDS:"]
        for record in recent_specimens:
            classification = record.get("classification") or {}
            lines.append(
                "  id=%s substrate=%s category=%s tier=%s complexity=%s"
                % (
                    record.get("specimen_id"),
                    record.get("substrate"),
                    classification.get("category"),
                    record.get("record_tier"),
                    record.get("complexity"),
                )
            )

    return "\n".join(lines)


def run(
    shift_number: int,
    writer: Any,
    ledger: config.ShiftLedger,
    memory: Dict[str, Any],
    recent_specimens: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Write this shift's continuity summary.

    Returns a small result dict. A budget ceiling or an empty response keeps
    the previous summary in place rather than overwriting it with nothing —
    losing continuity is worse than carrying a slightly stale summary, and the
    shift record shows that the pass did not complete.
    """
    outcome: Dict[str, Any] = {"written": False, "halt_reason": None, "summary": None}

    window = list(recent_specimens)[-KEEPER_RECENT_WINDOW:]

    try:
        result = config.generate(
            prompt=_build_input(shift_number, memory, window),
            role=ROLE,
            system=_system_prompt(),
            ledger=ledger,
        )
    except config.BudgetExceeded as exc:
        outcome["halt_reason"] = "budget: %s" % (exc,)
        return outcome

    summary = result.text.strip()
    if not summary:
        outcome["halt_reason"] = "empty summary returned; previous summary retained"
        return outcome

    writer.set_summary(summary)
    outcome["written"] = True
    outcome["summary"] = summary
    outcome["tokens"] = {
        "input": result.input_tokens,
        "output": result.output_tokens,
        "cost_usd": result.cost_usd,
    }
    return outcome
