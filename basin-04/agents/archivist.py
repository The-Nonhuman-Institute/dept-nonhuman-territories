# SPDX-FileCopyrightText: 2026 U3 Labs, LLC
# SPDX-License-Identifier: Apache-2.0
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
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


# Keys a classification system might use to name one of its own categories.
# Checked in addition to a plain walk of the whole structure, never instead of
# it — the Namer owns the shape and may use none of these.
_LABEL_KEYS = ("category", "subcategory", "label", "name", "id", "key")


def collect_labels(node: Any) -> Tuple[set, set]:
    """Walk the authored system and return (all_strings, label_like_strings).

    The Namer's system has no fixed shape by design (DNT-CLS-001 Section 1), so
    this cannot assume categories live at the top level, or in dict keys, or
    under any particular field. It walks the whole structure.

    That assumption is exactly what broke the first version of this function.
    The Namer restructured into two top-level containers with its categories
    nested inside them as objects — a genuine hierarchy. Comparing only
    top-level keys then reported every live category as "coined then dropped",
    which is the opposite of what had happened: they had moved deeper, not
    disappeared. A detector that mistakes a system developing structure for a
    system losing categories would feed exactly the wrong signal into the
    Section 11 checkpoint.
    """
    all_strings = set()
    explicit_labels = set()      # named under a label-like key
    top_level_keys = set()       # dict keys at depth 0

    def walk(node: Any, parent_key: Optional[str] = None, depth: int = 0) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str):
                    all_strings.add(key)
                    if depth == 0:
                        top_level_keys.add(key)
                walk(value, key if isinstance(key, str) else None, depth + 1)
        elif isinstance(node, list):
            for item in node:
                walk(item, parent_key, depth)
        elif isinstance(node, str):
            all_strings.add(node)
            if parent_key and parent_key.lower() in _LABEL_KEYS:
                explicit_labels.add(node)

    walk(node)

    # If the system names its categories explicitly, those names are the
    # categories and the surrounding dict keys are its field names — `members`,
    # `complexity_range`, `subcategories` are structure, not categories, and
    # reporting them as "authored but never filed" would be noise dressed up as
    # a finding. Only when nothing is named explicitly do dict keys serve as the
    # labels, which is the flat shape a simpler system would produce.
    labels = explicit_labels if explicit_labels else top_level_keys
    return all_strings, labels


def _salvage_objects(text: str, required_key: str) -> List[Dict[str, Any]]:
    """Recover complete JSON objects carrying a given key, from a cut-off reply."""
    recovered: List[Dict[str, Any]] = []
    cursor = 0
    while True:
        start = text.find("{", cursor)
        if start == -1:
            break
        depth, end, in_string, escaped = 0, -1, False, False
        for position in range(start, len(text)):
            character = text[position]
            if in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
                continue
            if character == '"':
                in_string = True
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    end = position
                    break
        if end == -1:
            cursor = start + 1
            continue
        chunk = text[start : end + 1]
        if ('"%s"' % required_key) in chunk:
            try:
                parsed = json.loads(chunk)
            except ValueError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get(required_key):
                recovered.append(parsed)
                cursor = end + 1
                continue
        cursor = start + 1
    return recovered


def detect_drift(
    native: Any,
    category_stats: Dict[str, Any],
    previous_pass: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compare what the Namer has filed against what it currently keeps.

    Returns findings only. Nothing here corrects anything.
    """
    present_anywhere, authored = collect_labels(native)
    filed = set(category_stats.keys())
    # A label is only "dropped" if it appears nowhere in the authored system at
    # any depth — not merely absent from the top level.
    still_present = {label for label in filed if label in present_anywhere}

    # Coined and used to file real specimens, but absent from the system the
    # Namer most recently wrote, at any depth. The specimen records still carry
    # the label, so the record and the current system disagree.
    dropped = sorted(filed - still_present)

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


def lineage_record(specimen_index: Dict[str, Any]) -> Dict[str, Any]:
    """Capability drift per specimen/lineage, computed from parentage.

    physics.md Section 4.4 and DNT-CLS-001 Section 4 both ask for capability
    drift "per specimen/lineage", not only per category. Until replication mode
    existed there were no lineages to follow; now there are.

    Arithmetic, not a model question: a lineage is a chain of parent_id links,
    and its drift is the change in measured complexity along that chain.
    """
    children: Dict[str, List[str]] = {}
    for specimen_id, entry in specimen_index.items():
        parent = entry.get("parent_id")
        if parent:
            children.setdefault(parent, []).append(specimen_id)

    # A founder is any specimen with descendants but no parent of its own.
    founders = [
        specimen_id for specimen_id, entry in specimen_index.items()
        if not entry.get("parent_id") and specimen_id in children
    ]

    lineages: Dict[str, Any] = {}
    for founder in sorted(founders):
        chain, cursor = [], founder
        while cursor and cursor in specimen_index:
            entry = specimen_index[cursor]
            chain.append({
                "specimen_id": cursor,
                "generation": int(entry.get("generation", 0)),
                "complexity": int(entry.get("complexity") or 0),
                "shift": entry.get("first_seen_shift"),
                "end_state": entry.get("end_state"),
                "persistence_native": entry.get("persistence_native"),
            })
            descendants = sorted(children.get(cursor, []))
            cursor = descendants[0] if descendants else None

        complexities = [link["complexity"] for link in chain]
        lineages[founder] = {
            "length": len(chain),
            "generations_reached": max(link["generation"] for link in chain),
            "chain": chain,
            "complexity_at_founding": complexities[0],
            "complexity_at_latest": complexities[-1],
            "capability_drift": complexities[-1] - complexities[0],
            "still_active": any(link["end_state"] is None for link in chain),
        }
    return {
        "lineages_found": len(lineages),
        "lineages": lineages,
        "note": (
            "Capability drift tracked per lineage as its own axis, separate "
            "from taxonomic rank (DNT-CLS-001 Section 4). Computed from "
            "parentage; no model consulted."
        ),
    }


def persistence_reported(specimen_index: Dict[str, Any]) -> Dict[str, int]:
    """The Namer's own persistence wordings, counted verbatim.

    physics.md Section 5 has the Namer assign specimen state natively, to be
    crosswalked later. These are its words, gathered for the crosswalk — never
    normalised or rewritten here.
    """
    counts: Dict[str, int] = {}
    for entry in specimen_index.values():
        wording = (entry.get("persistence_native") or "").strip()
        if wording:
            counts[wording] = counts.get(wording, 0) + 1
    return counts


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
        "You will also be given the author's own wordings for how specimens "
        "persist. Map each to one of three reference states — "
        "stateless/ephemeral, persistent-singular, distributed — or to null "
        "where no mapping is reliable. The author was never shown these three "
        "terms; they are yours for translation only, and carry no authority "
        "over its wording.\n"
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
        'itself, or empty>",\n'
        '  "persistence_crosswalk": [\n'
        "    {\n"
        '      "native_wording": "<the wording exactly as given to you>",\n'
        '      "reference_state": "stateless/ephemeral" | "persistent-singular" '
        '| "distributed" | null,\n'
        '      "note": "<one short sentence: why, or why no reliable '
        'equivalent>"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "\n"
        "Keep every note to one short sentence. A truncated reply loses the "
        "whole crosswalk." % (", ".join(LINNAEAN_TIERS),)
    )


def _build_input(native: Any, drift: Dict[str, Any], capability: Dict[str, Any],
                 persistence: Optional[Dict[str, int]] = None) -> str:
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
    if persistence:
        ranked = sorted(persistence.items(), key=lambda kv: -kv[1])
        shown = ranked[: config.ARCHIVIST_PERSISTENCE_WINDOW]
        lines.append("")
        lines.append(
            "THE AUTHOR'S OWN WORDINGS FOR HOW SPECIMENS PERSIST "
            "(%d most frequent of %d):" % (len(shown), len(ranked)))
        for wording, count in shown:
            lines.append("  (%d) %s" % (count, wording))
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
    specimen_index = memory.get("specimen_index", {}) or {}
    lineages = lineage_record(specimen_index)
    persistence = persistence_reported(specimen_index)

    outcome: Dict[str, Any] = {
        "drift": drift,
        "capability": capability,
        "lineages": lineages,
        "crosswalk": None,
        "halt_reason": None,
    }

    payload: Dict[str, Any] = {
        "pass_at_shift": shift_number,
        "authored_categories": drift["authored_categories"],
        "drift": drift,
        "capability": capability,
        "lineages": lineages,
        "persistence_native_wordings": persistence,
        "persistence_crosswalk": None,
        "crosswalk": None,
        "consistency_notes": None,
        "crosswalk_available": False,
    }

    try:
        result = config.generate(
            prompt=_build_input(taxonomy_native, drift, capability, persistence),
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
        # A reply cut off by the ceiling is valid JSON up to the cut. Recover
        # the entries that completed rather than discarding real translation
        # work over a missing bracket (same principle as namer.salvage).
        recovered_cross = _salvage_objects(result.text, "category")
        recovered_pers = _salvage_objects(result.text, "native_wording")
        if recovered_cross or recovered_pers:
            parsed = {
                "crosswalk": recovered_cross,
                "persistence_crosswalk": recovered_pers,
                "consistency_notes": None,
            }
            payload["salvaged_from_truncated_response"] = True
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
    if isinstance(parsed.get("persistence_crosswalk"), list):
        payload["persistence_crosswalk"] = parsed["persistence_crosswalk"]
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
