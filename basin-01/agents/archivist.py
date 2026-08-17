"""
BASIN-01 — Archivist.

physics.md Section 4.4 and the Classification Standard (DNT-CLS-001
Sections 2, 4, 6).

  Frequency   low — every 5th to 10th shift, gated in code (config.py).
  Reads       the full native taxonomy, plus derived counters.
  Produces    a best-effort Linnaean crosswalk for human legibility;
              a drift record; a capability record per category.
  Never       alters the native taxonomy, reclassifies a specimen, or
              generates specimen activity.

Four things this role does NOT do, each of which the standard is explicit
about:

  1. It does not feed back. DNT-CLS-001 Section 2: the crosswalk "carries no
     authority over the native taxonomy and does not feed back into it." The
     write layer enforces this structurally — the Archivist's writer exposes
     read_taxonomy_native() returning a deep copy, and has no method that can
     reach the real taxonomy at all.

  2. It does not invent Latin. physics.md Section 4.4 requires plain-English
     tier labels and says NEVER invented Latin binomials. A fabricated binomial
     would dress one system's account of itself up as established natural
     history, which the Charter Section 3 forbids.

  3. It does not force a mapping. "No reliable crosswalk" is a valid, expected
     and useful output (physics.md Section 4.4, DNT-CLS-001 Section 2). A
     forced mapping is worse than none: it reports a correspondence to human
     categories that the terrain has not earned.

  4. It does not correct drift. DNT-CLS-001 Section 6: drift "is not treated as
     an error to correct — it is treated as data about how the native system
     itself is developing." The Archivist surfaces it and stops there.

Drift detection is MECHANICAL, not asked of a model. Comparing the categories
the Namer has actually filed specimens under against the categories present in
the system it most recently authored is a set comparison, and a set comparison
does not hallucinate. The model is used only for the crosswalk, which is a
translation task requiring judgment.

Python 3.9 compatible.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

# A parsing utility, not a capability. Imported so both roles read model
# output the same way rather than drifting apart over time.
from namer import extract_json

ROLE = "archivist"

# The tier vocabulary is plain English and fixed. It is used only to describe
# the crosswalk's shape to the model; it is never issued to the Namer.
LINNAEAN_TIERS = (
    "Kingdom",
    "Phylum",
    "Class",
    "Order",
    "Family",
    "Genus",
    "Species",
)


# ---------------------------------------------------------------------------
# 1. MECHANICAL DRIFT DETECTION
#
#    Set comparison, computed in code. DNT-CLS-001 Section 6 asks the Archivist
#    to surface cases where the Namer's own system "has changed shape,
#    contradicted an earlier decision, or would classify an old specimen
#    differently today than it did originally".
# ---------------------------------------------------------------------------


def detect_drift(
    native: Any,
    category_stats: Dict[str, Any],
    previous_pass: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compare what the Namer has filed against what it currently keeps.

    Returns findings only. Nothing here corrects anything.
    """
    authored = set(native.keys()) if isinstance(native, dict) else set()
    filed = set(category_stats.keys())

    # Coined and used to file real specimens, but absent from the system the
    # Namer most recently wrote. The specimen records still carry the label, so
    # the record and the current system disagree.
    dropped = sorted(filed - authored)

    # Present in the authored system but never used to file anything.
    unused = sorted(authored - filed)

    previous_authored = set()
    if previous_pass:
        previous_authored = set(previous_pass.get("authored_categories", []) or [])

    findings = {
        "filed_categories": sorted(filed),
        "authored_categories": sorted(authored),
        "coined_then_dropped_from_system": dropped,
        "authored_but_never_filed": unused,
        "added_since_last_pass": sorted(authored - previous_authored) if previous_pass else [],
        "removed_since_last_pass": sorted(previous_authored - authored) if previous_pass else [],
        "drift_detected": bool(dropped or unused)
        or (bool(previous_pass) and authored != previous_authored),
    }
    return findings


def capability_record(
    category_stats: Dict[str, Any], previous_pass: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Longitudinal complexity per category, tracked as its own axis.

    DNT-CLS-001 Section 4 keeps this separate from taxonomic rank on purpose: a
    specimen's kind and a specimen's capability are different questions, and
    folding one into the other hides divergence rather than surfacing it.
    """
    previous = (previous_pass or {}).get("capability", {}) or {}
    record: Dict[str, Any] = {}

    for label, entry in category_stats.items():
        current_mean = float(entry.get("mean_complexity", 0.0))
        prior_mean = float((previous.get(label) or {}).get("mean_complexity", 0.0))
        record[label] = {
            "members": int(entry.get("count", 0)),
            "mean_complexity": round(current_mean, 3),
            "mean_complexity_at_last_pass": round(prior_mean, 3) if prior_mean else None,
            "change_since_last_pass": (
                round(current_mean - prior_mean, 3) if prior_mean else None
            ),
            "first_seen_shift": entry.get("first_seen_shift"),
            "last_seen_shift": entry.get("last_seen_shift"),
        }
    return record


# ---------------------------------------------------------------------------
# 2. CROSSWALK INSTRUCTION
# ---------------------------------------------------------------------------


def _system_prompt() -> str:
    return (
        "You produce a best-effort translation of one classification system "
        "into conventional biological tier labels, for human readability "
        "only.\n"
        "\n"
        "The system you are translating was built independently and owes "
        "nothing to conventional structure. Your translation carries no "
        "authority over it and does not change it.\n"
        "\n"
        "Use only these plain-English tier labels: %s.\n"
        "\n"
        "NEVER invent a Latin name or a two-part Latin binomial. Plain English "
        "only.\n"
        "\n"
        '"No reliable equivalent" is a valid, expected and useful answer. If a '
        "category spans several tiers, or corresponds to nothing in the "
        "conventional structure, say so plainly. A forced mapping is worse "
        "than none: it reports a correspondence that does not exist.\n"
        "\n"
        "Reply with JSON only:\n"
        "{\n"
        '  "crosswalk": [\n'
        "    {\n"
        '      "category": "<the label exactly as given to you>",\n'
        '      "tier": "<one of the labels above, or null>",\n'
        '      "confidence": "clear" | "partial" | "none",\n'
        '      "note": "<why this mapping, or why none is reliable>"\n'
        "    }\n"
        "  ],\n"
        '  "consistency_notes": "<any place the system appears to contradict '
        'itself, or empty>"\n'
        "}" % (", ".join(LINNAEAN_TIERS),)
    )


def _build_input(native: Any, drift: Dict[str, Any], capability: Dict[str, Any]) -> str:
    lines = ["THE SYSTEM TO TRANSLATE, EXACTLY AS ITS AUTHOR WROTE IT:"]
    lines.append(json.dumps(native, indent=2) if native else "(empty)")
    lines.append("")
    lines.append("CATEGORIES THAT HAVE BEEN USED TO FILE SPECIMENS:")
    for label in drift.get("filed_categories", []):
        entry = capability.get(label, {})
        lines.append(
            "  %s — %s member(s), mean complexity %s"
            % (label, entry.get("members", 0), entry.get("mean_complexity"))
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. THE PASS
# ---------------------------------------------------------------------------


def run(
    shift_number: int,
    writer: Any,
    ledger: config.ShiftLedger,
    taxonomy_native: Any,
    memory: Dict[str, Any],
) -> Dict[str, Any]:
    """Run the low-frequency archival pass.

    Drift and capability are computed before any model call, so they are
    recorded even if the crosswalk cannot be produced.
    """
    annotations = (memory.get("annotations") or {})
    previous_pass = (annotations.get("linnaean_crosswalk") or {}).get("payload")

    category_stats = memory.get("category_stats", {}) or {}
    drift = detect_drift(taxonomy_native, category_stats, previous_pass)
    capability = capability_record(category_stats, previous_pass)

    outcome: Dict[str, Any] = {
        "drift": drift,
        "capability": capability,
        "crosswalk": None,
        "halt_reason": None,
    }

    payload: Dict[str, Any] = {
        "pass_at_shift": shift_number,
        "authored_categories": drift["authored_categories"],
        "drift": drift,
        "capability": capability,
        "crosswalk": None,
        "consistency_notes": None,
        "crosswalk_available": False,
    }

    try:
        result = config.generate(
            prompt=_build_input(taxonomy_native, drift, capability),
            role=ROLE,
            system=_system_prompt(),
            ledger=ledger,
        )
    except config.BudgetExceeded as exc:
        outcome["halt_reason"] = "budget: %s" % (exc,)
        payload["crosswalk_note"] = (
            "No crosswalk this pass: the shift reached a budget ceiling. Drift "
            "and capability were recorded regardless."
        )
        writer.write_annotation(payload)
        return outcome

    parsed = extract_json(result.text)
    if parsed is None:
        payload["crosswalk_note"] = (
            "No crosswalk this pass: the response could not be parsed. This is "
            "a harness failure, not a finding about the taxonomy."
        )
        writer.write_annotation(payload)
        outcome["halt_reason"] = "crosswalk response unparseable"
        return outcome

    crosswalk = parsed.get("crosswalk")
    if isinstance(crosswalk, list):
        payload["crosswalk"] = crosswalk
        payload["crosswalk_available"] = True
        outcome["crosswalk"] = crosswalk
    payload["consistency_notes"] = parsed.get("consistency_notes") or None
    payload["crosswalk_note"] = (
        "For human legibility only. Carries no authority over the native "
        "system and does not feed back into it (DNT-CLS-001 Section 2)."
    )

    writer.write_annotation(payload)
    outcome["tokens"] = {
        "input": result.input_tokens,
        "output": result.output_tokens,
        "cost_usd": result.cost_usd,
    }
    return outcome
