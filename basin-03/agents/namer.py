"""
BASIN-01 — Namer.

Operating spec: README.md Section 5, physics.md Section 4.2, and the
Classification Standard (DNT-CLS-001).

  Input per shift     the current native taxonomy, plus a CAPPED window of
                      recent specimen records. Never the full history.
  Per specimen        compare against its own existing categories; file under
                      an existing one, propose a new one, or flag anomalous;
                      log its reasoning in full.
  Logging tier        applied as a fixed, code-enforced check — never a live
                      judgment call, and never asked of the model.
  Not issued          the Linnaean structure, any template, any vocabulary.
  Not its job         the Linnaean crosswalk. That is the Archivist's, run
                      separately and at low frequency, so this role's native
                      reasoning stays uncontaminated by human categorical
                      language at the moment of classification.

Three design consequences worth stating, because each one is a place where a
convenient implementation would have quietly violated the standard:

  1. The native taxonomy is stored exactly as this role authors it. This module
     does not define what a category, a member, or a relation is, and does not
     merge its own shape into the result. A flat label-to-members map would
     have been easy and would have pre-decided the falsification condition
     (physics.md Section 11 counts "no groupings, no relational structure" as a
     null result) — hardcoding a flat list would make that outcome inevitable
     rather than observed.

  2. The functional-role vocabulary of physics.md Section 6 (producer,
     consumer, decomposer, connector, and the rest) is NOT placed in this
     role's prompt. DNT-CLS-001 Section 3 permits this role to use those terms
     as reference points, but issuing the list up front would hand it a
     categorical framework to fill in — the same defect as issuing the
     Linnaean ranks. The terms remain available to human readers and to the
     Archivist.

  3. A response this module cannot parse is recorded as an unresolved
     mechanism failure, NOT as an anomalous classification. Conflating the two
     would corrupt the primary research record: "this role found something it
     could not classify" and "the harness could not read the reply" are
     different findings, and only the first is data about the taxonomy.

This role holds a narrow write capability: specimen records, anomaly records,
and its own taxonomy. It cannot write the shift log, cannot address a path, and
never reads storage directly — every input arrives as an argument.

Python 3.9 compatible.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

ROLE = "namer"

# The whole of this role's structural obligation (DNT-CLS-001 Section 1).
# Nothing beyond this line constrains the shape of the system it builds.
MINIMUM_OBLIGATION = (
    "For any two specimens, you must be able to state whether they are more "
    "alike or less alike than one another, and why."
)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


# ---------------------------------------------------------------------------
# 1. THE CODE-ENFORCED LOGGING TIER
#
#    physics.md Section 8 and DNT-CLS-001 Section 5 both require the
#    aggregate -> individual promotion threshold to be fixed, explicit, and
#    checked mechanically rather than decided in the moment. This function is
#    that check. It is pure, it takes no model output beyond the decision label
#    and a measured integer, and it is unit-testable without a model.
#
#    Thresholds live in config.py Section 6.
# ---------------------------------------------------------------------------


def apply_promotion_rule(
    decision: str,
    category: Optional[str],
    complexity: int,
    category_stats: Dict[str, Any],
) -> Tuple[str, List[str]]:
    """Return (tier, triggers). Never consults the model.

    tier is 'individual', 'aggregate', or 'anomalous'.
    triggers names every rule clause that fired, so the record shows why.
    """
    triggers: List[str] = []

    if decision == "anomalous":
        return "anomalous", ["flagged_anomalous"]

    if decision == "new_category" and config.PROMOTE_ON_NEW_CATEGORY:
        triggers.append("new_category")

    stats = category_stats.get(category or "", {})
    member_count = int(stats.get("count", 0))
    mean_complexity = float(stats.get("mean_complexity", 0.0))

    if member_count < config.PROMOTE_IF_CATEGORY_SIZE_BELOW:
        triggers.append("category_below_aggregate_threshold")

    if (
        mean_complexity > 0.0
        and complexity >= mean_complexity * config.PROMOTE_COMPLEXITY_RATIO
    ):
        triggers.append("complexity_ratio_exceeded")

    if triggers:
        return "individual", triggers

    if member_count >= config.AGGREGATE_TIER_CATEGORY_SIZE:
        return "aggregate", ["high_volume_category"]

    return "aggregate", []


def update_category_stats(
    category_stats: Dict[str, Any], category: str, complexity: int, shift_number: int
) -> Dict[str, Any]:
    """Maintain the derived counters the promotion rule reads.

    These counters live in memory.json, not in the native taxonomy, so that a
    counting requirement never leaks a shape back into the Namer's own system.
    """
    stats = dict(category_stats)
    entry = dict(stats.get(category, {}))
    count = int(entry.get("count", 0))
    mean = float(entry.get("mean_complexity", 0.0))
    new_count = count + 1
    entry["count"] = new_count
    entry["mean_complexity"] = ((mean * count) + complexity) / new_count
    entry["first_seen_shift"] = entry.get("first_seen_shift", shift_number)
    entry["last_seen_shift"] = shift_number
    stats[category] = entry
    return stats


# ---------------------------------------------------------------------------
# 2. STRUCTURAL DIVERGENCE MEASURE
#
#    Supports the 15-shift falsification checkpoint (physics.md Section 11),
#    which turns on whether the native taxonomy has diverged from "a flat,
#    unstructured list". Measured mechanically so the checkpoint is decided by
#    the record rather than by impression.
# ---------------------------------------------------------------------------


def measure_taxonomy_structure(native: Any) -> Dict[str, Any]:
    """Describe the shape of whatever the Namer authored, without judging it."""

    def depth_of(node: Any, level: int = 0) -> int:
        if isinstance(node, dict) and node:
            return max(depth_of(v, level + 1) for v in node.values())
        if isinstance(node, list) and node:
            return max(depth_of(v, level + 1) for v in node)
        return level

    def count_nodes(node: Any) -> int:
        if isinstance(node, dict):
            return 1 + sum(count_nodes(v) for v in node.values())
        if isinstance(node, list):
            return 1 + sum(count_nodes(v) for v in node)
        return 1

    top_level_keys = list(native.keys()) if isinstance(native, dict) else []
    depth = depth_of(native)
    return {
        "top_level_entries": len(top_level_keys),
        "max_depth": depth,
        "total_nodes": count_nodes(native),
        # A flat, unstructured list is depth <= 1: labels with nothing beneath
        # them. Anything deeper carries grouping or relation.
        "diverged_from_flat_list": depth > 1,
    }


# ---------------------------------------------------------------------------
# 3. OPERATIVE INSTRUCTION
#
#    Carries the minimum obligation and the output contract. No ranks, no
#    example taxonomy, no functional-role list, no suggestion of how many
#    categories there should be or what shape the system should take.
# ---------------------------------------------------------------------------


def _system_prompt() -> str:
    return (
        "You classify specimens observed in a bounded environment, using a "
        "system of your own design.\n"
        "\n"
        "Each specimen is something that has been present in the environment "
        "over one or more intervals. You are given what was measured about it: "
        "how long it has been present, where it sits on the environment's "
        "gradient, what it has drawn on, what it has passed to others, whether "
        "it moved, and whether anything has descended from it.\n"
        "\n"
        "You are not issued a classification structure to fill in. The shape "
        "of your system is yours: it may be hierarchical, relational, "
        "spectral, or something with no established analog. You may revise it "
        "as you observe more specimens.\n"
        "\n"
        "Your only structural obligation:\n"
        "%s\n"
        "\n"
        "For each specimen you are given, decide one of:\n"
        "  file        it belongs to a category already in your system\n"
        "  new         it warrants a category you are coining now\n"
        "  anomalous   it fits no category and you decline to force it into "
        "one\n"
        "\n"
        "Flagging a specimen anomalous is a valid and expected outcome. Do not "
        "force a specimen into a category to avoid it.\n"
        "\n"
        "For each specimen also state how it persists, in your own words. You "
        "are not given a set of persistence states to choose from; describe "
        "what you observe.\n"
        "\n"
        "Classify by what a specimen does, not by what its substrate looks "
        "like. Two specimens made of the same material may live entirely "
        "differently; two made of different material may live the same way.\n"
        "\n"
        "Reply with JSON only, in this form:\n"
        "{\n"
        '  "classifications": [\n'
        "    {\n"
        '      "specimen_id": "<the id given to you>",\n'
        '      "decision": "file" | "new" | "anomalous",\n'
        '      "category": "<your label, or null if anomalous>",\n'
        '      "comparison": "<whether this specimen is more or less alike '
        'than a named other specimen, and why>",\n'
        '      "reasoning": "<your full reasoning, at whatever length it '
        'takes>",\n'
        '      "persistence": "<in your own words, how this specimen '
        'persists>"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "\n"
        "Return the classifications and nothing else. You will be asked for "
        "your system separately, in its own reply, so it is not competing "
        "with these for room." % (MINIMUM_OBLIGATION,)
    )


# ---------------------------------------------------------------------------
# THE SYSTEM IS ASKED FOR SEPARATELY.
#
# It used to be the last object in the same reply as the classifications, and
# an output ceiling cuts a reply from the end. So the Namer's account of its
# own system was the first thing lost whenever a reply ran long, which was
# often. BASIN-01 files specimens into 32 categories and its stored system
# holds 10 nodes; BASIN-03, 12 categories and 5 nodes; BASIN-04, 2 and 1.
#
# The damage is not only to the archive. The stored system is handed back to
# the Namer at the start of every shift as YOUR CURRENT SYSTEM, so it was
# being given a mutilated copy of its own filing system every shift and asked
# to work coherently from it. What looked like a Namer that could not build
# much of a taxonomy was a Namer with induced amnesia.
#
# The question is unchanged. Only the room to answer it is.
# ---------------------------------------------------------------------------
def _system_prompt_taxonomy() -> str:
    return (
        "You maintain a classification system for a population you have been "
        "observing.\n\n"
        "Return your system IN FULL, in whatever structure you choose, "
        "including any revision you are making to it now. It is stored exactly "
        "as you write it and it is handed back to you next time as your own "
        "record, so anything you leave out is lost to you as well.\n\n"
        "Reply with JSON only, in this form:\n"
        "{\n"
        '  "taxonomy": { }\n'
        "}\n"
    )


def _taxonomy_input(native, just_filed) -> str:
    lines = ["YOUR CURRENT SYSTEM:",
             json.dumps(native, indent=2) if native else "(empty)",
             ""]
    if just_filed:
        lines.append("WHAT YOU FILED IN THIS INTERVAL:")
        for entry in just_filed:
            lines.append("- %s -> %s" % (entry.get("specimen_id"),
                                         entry.get("category")))
        lines.append("")
    lines.append("Return your system in full, revised if you are revising it.")
    return "\n".join(lines)


def _build_input(
    batch: Sequence[Dict[str, Any]],
    native: Any,
    recent: Sequence[Dict[str, Any]],
    continuity_summary: Optional[str] = None,
) -> str:
    lines: List[str] = []

    if continuity_summary:
        # The Keeper's state-of-terrain summary. It reaches this role because
        # this role reasons over history; it never reaches a Generator, where
        # it would function as creative direction (see keeper.py).
        lines.append("STATE OF THE ENVIRONMENT AT THE START OF THIS INTERVAL:")
        lines.append(continuity_summary)
        lines.append("")

    lines.append("YOUR CURRENT SYSTEM:")
    lines.append(json.dumps(native, indent=2) if native else "(empty — nothing recorded yet)")
    lines.append("")

    if recent:
        lines.append("PREVIOUSLY RECORDED SPECIMENS (most recent %d):" % len(recent))
        for record in recent:
            lines.append(
                "- id=%s substrate=%s category=%s complexity=%s\n  content: %s"
                % (
                    record.get("specimen_id"),
                    record.get("substrate"),
                    (record.get("classification") or {}).get("category"),
                    record.get("complexity"),
                    _clip(str(record.get("content", "")), 240),
                )
            )
        lines.append("")

    lines.append("SPECIMENS TO CLASSIFY THIS INTERVAL:")
    for record in batch:
        lines.append(
            "- id=%s substrate=%s complexity=%s\n  content: %s"
            % (
                record["specimen_id"],
                record["substrate"],
                record["complexity"],
                _clip_observation(str(record.get("content", ""))),
            )
        )
    return "\n".join(lines)


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + " ...[clipped]"


# The line observer.py writes immediately before a specimen's substrate.
_SUBSTRATE_MARKER = "its substrate as recorded:"

# Measured across every observation the five terrains have ever recorded:
# the measurement block runs to 911 characters at its longest, and a substrate
# budget of 1200 keeps 98.8% of substrates whole.
_MEASUREMENT_CEILING = 1400
_SUBSTRATE_BUDGET = 1200


def _clip_observation(text: str) -> str:
    """Clip an observation without removing what it is being classified on.

    An observation is written in two parts: everything the terrain measured
    (position, light, intake, how the specimen is built, how it arose), then
    the substrate the Generator emitted. Only the second part is unbounded.

    A single clip across the whole thing therefore removed exactly the wrong
    end. At the previous 600-character limit only 8.7% of observations
    survived whole, and what fell off every one of the rest was the structure,
    the lineage and the substrate — while position and light were always kept.
    The Namer is asked to classify by what a specimen does; what it does was
    the part being cut, and it has never once seen a substrate.

    So the measurements are kept whole and the model's own output carries the
    budget, which is the only part that can run away.
    """
    text = text.strip()
    split = text.find(_SUBSTRATE_MARKER)
    if split < 0:
        return _clip(text, _MEASUREMENT_CEILING + _SUBSTRATE_BUDGET)
    return _clip(text[:split], _MEASUREMENT_CEILING) + _clip(
        text[split:], _SUBSTRATE_BUDGET
    )


# ---------------------------------------------------------------------------
# 4. RESPONSE PARSING
#
#    Tolerant of fenced blocks and surrounding prose. A response that cannot be
#    read is a harness failure, recorded as such, and never dressed up as a
#    classification decision.
# ---------------------------------------------------------------------------


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text or not text.strip():
        return None

    fenced = _FENCE.search(text)
    candidates = []
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(text)

    for candidate in candidates:
        candidate = candidate.strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(candidate[start : end + 1])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    return None


def salvage_classifications(text: str) -> List[Dict[str, Any]]:
    """Recover the classification objects that completed before a cut-off.

    A response truncated by the output ceiling is valid JSON up to the point it
    stops. Discarding the whole reply would throw away real classification
    decisions — including their reasoning, which is the primary research data —
    over an unterminated bracket at the end.

    Every object recovered here is marked salvaged in the record it produces,
    so the log never presents a partially-read response as a clean one.
    """
    recovered: List[Dict[str, Any]] = []
    seen_ids = set()
    cursor = 0

    while True:
        start = text.find("{", cursor)
        if start == -1:
            break

        depth = 0
        end = -1
        in_string = False
        escaped = False
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
            # Unterminated: this object was cut off. Step inside it and look
            # for smaller objects that did complete.
            cursor = start + 1
            continue

        chunk = text[start : end + 1]
        if '"specimen_id"' in chunk:
            try:
                parsed = json.loads(chunk)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("specimen_id"):
                identifier = str(parsed["specimen_id"]).strip()
                if identifier not in seen_ids:
                    seen_ids.add(identifier)
                    recovered.append(parsed)
                cursor = end + 1
                continue
        cursor = start + 1

    return recovered


_DECISION_MAP = {
    "file": "filed",
    "filed": "filed",
    "existing": "filed",
    "new": "new_category",
    "new_category": "new_category",
    "coin": "new_category",
    "anomalous": "anomalous",
    "anomaly": "anomalous",
    "unclassifiable": "anomalous",
}


def normalise_decision(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return _DECISION_MAP.get(value.strip().lower())


# ---------------------------------------------------------------------------
# 5. THE PASS
# ---------------------------------------------------------------------------


def run(
    shift_number: int,
    emissions: Sequence[Dict[str, Any]],
    writer: Any,
    ledger: config.ShiftLedger,
    native: Any,
    recent_specimens: Sequence[Dict[str, Any]],
    category_stats: Dict[str, Any],
    continuity_summary: Optional[str] = None,
) -> Dict[str, Any]:
    """Classify this shift's emissions.

    Returns a summary for the shift record, including the updated category
    counters and the structural measure of the native taxonomy. Writes specimen
    and anomaly records through the role-scoped writer.
    """
    outcome: Dict[str, Any] = {
        "classified": 0,
        "individual_records": 0,
        "aggregate_records": 0,
        "anomalous": 0,
        "unresolved": 0,
        "new_categories": [],
        "category_stats": dict(category_stats),
        "taxonomy_structure": measure_taxonomy_structure(native),
        "halt_reason": None,
        "parse_failed": False,
        "records": [],
    }

    batch = [dict(e) for e in emissions]
    for index, record in enumerate(batch):
        # A specimen that already carries an identity keeps it. Something
        # observed across many shifts has to stay the same specimen in the
        # record, or its history is a series of strangers and no continuity of
        # observation is possible at all.
        if not record.get("specimen_id"):
            record["specimen_id"] = _specimen_id(shift_number, index)

    if not batch:
        return outcome

    try:
        result = config.generate(
            prompt=_build_input(batch, native, recent_specimens, continuity_summary),
            role=ROLE,
            system=_system_prompt(),
            ledger=ledger,
        )
    except config.BudgetExceeded as exc:
        outcome["halt_reason"] = "budget: %s" % (exc,)
        # Nothing is dropped. Every emission still resolves to a defined
        # end-state (physics.md Section 7), here an unresolved one.
        for record in batch:
            _record_unresolved(writer, record, "shift ended at a budget ceiling "
                                               "before classification")
            outcome["unresolved"] += 1
        return outcome

    outcome["response_truncated"] = result.truncated
    parsed = extract_json(result.text)
    salvaged = False

    if parsed is None:
        # Recover whatever completed before the cut-off rather than discarding
        # real decisions over a missing bracket.
        recovered = salvage_classifications(result.text)
        if recovered:
            parsed = {"classifications": recovered, "taxonomy": None}
            salvaged = True
            outcome["salvaged_from_truncated_response"] = True
        else:
            outcome["parse_failed"] = True
            for record in batch:
                _record_unresolved(
                    writer,
                    record,
                    "classification response could not be parsed as JSON",
                    raw_response=result.text,
                )
                outcome["unresolved"] += 1
            return outcome

    by_id = {}
    for entry in parsed.get("classifications", []) or []:
        if isinstance(entry, dict) and entry.get("specimen_id"):
            by_id[str(entry["specimen_id"]).strip()] = entry

    stats = dict(category_stats)

    for record in batch:
        entry = by_id.get(record["specimen_id"])
        decision = normalise_decision((entry or {}).get("decision"))

        if entry is None or decision is None:
            # When entry is None the specimen was not in the reply at all,
            # which is what truncation looks like from here. Recording None
            # for the raw response threw away the only evidence of why —
            # it was null in 33 of 33 unresolved records. Keep the reply.
            _record_unresolved(
                writer,
                record,
                ("this specimen was absent from the reply — the reply ended "
                 "before reaching it"
                 if entry is None else
                 "no readable decision returned for this specimen"),
                raw_response=(json.dumps(entry) if entry
                              else getattr(result, "text", None)),
                truncated=(entry is None),
            )
            outcome["unresolved"] += 1
            continue

        category = entry.get("category")
        category = str(category).strip() if isinstance(category, str) and category.strip() else None
        if decision != "anomalous" and category is None:
            _record_unresolved(
                writer, record,
                "a filing decision was returned with no category label",
                raw_response=json.dumps(entry),
            )
            outcome["unresolved"] += 1
            continue

        # The tier is decided here, in code, before anything is written.
        tier, triggers = apply_promotion_rule(
            decision=decision,
            category=category,
            complexity=int(record.get("complexity", 0)),
            category_stats=stats,
        )

        classification = {
            "decision": decision,
            "category": category,
            # Logged in full, never summarised — this reasoning is the primary
            # research data (README.md Section 5).
            "reasoning": entry.get("reasoning", ""),
            "comparison": entry.get("comparison", ""),
            # physics.md Section 5: specimen state is assigned by the Namer
            # "natively" and crosswalked later. Stored exactly as written. The
            # three reference terms are never issued to this role — doing so
            # would hand it a template (DNT-CLS-001 Section 1).
            "persistence_native": entry.get("persistence", ""),
            # A record recovered from a truncated response says so, so the log
            # never presents a partially-read reply as a clean one.
            "salvaged_from_truncated_response": salvaged,
        }

        if decision == "anomalous":
            writer.append_anomaly(
                {
                    "specimen_id": record["specimen_id"],
                    "source_role": record["source_role"],
                    "substrate": record["substrate"],
                    "complexity": record.get("complexity"),
                    "content": record.get("content"),
                    "classification": classification,
                    "record_tier": "anomalous",
                    "resolution": "flagged_anomalous",
                    "note": (
                        "Flagged by the Namer as fitting no category. Not "
                        "force-fitted (DNT-CLS-001 Section 5)."
                    ),
                }
            )
            outcome["anomalous"] += 1
            outcome["classified"] += 1
            continue

        if decision == "new_category":
            outcome["new_categories"].append(category)

        stats = update_category_stats(stats, category, int(record.get("complexity", 0)), shift_number)

        specimen_record = {
                "specimen_id": record["specimen_id"],
                "source_role": record["source_role"],
                "substrate": record["substrate"],
                "record_tier": tier,
                "promotion_triggers": triggers,
                "complexity": record.get("complexity"),
                "resource_available": record.get("resource_available"),
                "scarcity": record.get("scarcity"),
                # Lineage, carried through from the emission. physics.md
                # Section 4.4 tracks capability drift "per specimen/lineage",
                # which needs the parentage to be in the record itself and not
                # only in derived state.
                "replicated": bool(record.get("replicated")),
                "parent_id": record.get("parent_id"),
                "generation": int(record.get("generation", 0) or 0),
                "content": record.get("content"),
                "classification": classification,
                # Named "emission", not "generation". It used to be the second
                # of two keys both called "generation" in this same literal, so
                # it silently overwrote the lineage integer four lines above and
                # the specimen's generation never once reached the record — a
                # dict is what sits in that field in all 2,262 rows written
                # before this fix. This describes the model call; the integer
                # above describes descent.
                "emission": {
                    "model": record.get("model"),
                    "output_tokens": record.get("output_tokens"),
                    "truncated": record.get("truncated"),
                },
        }
        writer.append_specimen(specimen_record)
        outcome["records"].append(specimen_record)
        outcome["classified"] += 1
        if tier == "individual":
            outcome["individual_records"] += 1
        else:
            outcome["aggregate_records"] += 1

    # The native taxonomy is stored exactly as authored, in whatever shape.
    # Asked for in its own reply now, with its own room — see the note above
    # _system_prompt_taxonomy. A failure here keeps the stored system exactly
    # as it was rather than replacing it with nothing.
    authored = parsed.get("taxonomy")
    if not (isinstance(authored, (dict, list)) and authored):
        just_filed = [{"specimen_id": k, "category": (v or {}).get("category"),
                       "decision": (v or {}).get("decision")}
                      for k, v in by_id.items()]
        try:
            tax_result = config.generate(
                prompt=_taxonomy_input(native, just_filed),
                role=ROLE,
                system=_system_prompt_taxonomy(),
                ledger=ledger,
            )
            tax_parsed = extract_json(tax_result.text)
            if isinstance(tax_parsed, dict):
                candidate = tax_parsed.get("taxonomy")
                if isinstance(candidate, (dict, list)) and candidate:
                    authored = candidate
                    outcome["taxonomy_asked_separately"] = True
        except Exception as exc:
            outcome["taxonomy_call_failed"] = str(exc)[:120]

    if isinstance(authored, (dict, list)) and authored:
        writer.replace_taxonomy_native(authored)
        writer.note_revision(
            "native system rewritten by the Namer during shift %d" % shift_number
        )
        outcome["taxonomy_structure"] = measure_taxonomy_structure(authored)

    outcome["category_stats"] = stats
    outcome["namer_tokens"] = {
        "input": result.input_tokens,
        "output": result.output_tokens,
        "cost_usd": result.cost_usd,
    }
    return outcome


def _specimen_id(shift_number: int, index: int) -> str:
    return "s-%04d-%02d" % (shift_number, index)


def _record_unresolved(
    writer: Any,
    record: Dict[str, Any],
    reason: str,
    raw_response: Optional[str] = None,
    truncated: bool = False,
) -> None:
    """Log a mechanism failure as unresolved — explicitly not an anomaly.

    physics.md Section 7 allows 'unresolved (flagged)' as an end-state. Keeping
    it distinct from 'anomalous' matters: one is a finding about the taxonomy,
    the other is a finding about the harness, and merging them would corrupt
    the record the falsification checkpoint reads.
    """
    writer.append_anomaly(
        {
            "specimen_id": record.get("specimen_id"),
            "source_role": record.get("source_role"),
            "substrate": record.get("substrate"),
            "complexity": record.get("complexity"),
            "content": record.get("content"),
            "record_tier": "unresolved",
            "resolution": "unresolved",
            "is_classification_outcome": False,
            "mechanism_failure": reason,
            # Whether the reply was cut off rather than merely unreadable.
            # The two need telling apart: one is a ceiling that is too low,
            # the other is a model that answered badly, and the fix differs.
            "reply_truncated": bool(truncated),
            "raw_response": _clip(raw_response, 1200) if raw_response else None,
            "note": (
                "Harness failure, not a Namer classification decision. This "
                "record is not evidence about the taxonomy."
            ),
        }
    )
