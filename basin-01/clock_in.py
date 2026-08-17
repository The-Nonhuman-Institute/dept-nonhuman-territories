"""
BASIN-01 — clock in. The shift loop.

    python3 clock_in.py            start a shift
    python3 clock_in.py --status   read-only summary, no model calls, no writes
    python3 clock_in.py --dry-run  show what a shift would run, then stop

A shift is a bounded, steward-initiated period during which the terrain's
active roles run (DNT-SLP-001 Section 1). Between shifts the terrain is
dormant: no activity, no cost. That discontinuity is terrain physics, not a
limitation to apologise for (physics.md Section 5).

  load state -> run active roles -> write state -> log shift -> exit

What the loop guarantees:

  Nothing is written until the shift closes cleanly. Every role writes into a
  buffered transaction; a single atomic commit lands at clock-out. A machine
  that dies mid-shift leaves state/ at its last good checkpoint
  (STARTUP_GUIDE.md Section 6).

  A shift that hits a ceiling ends early rather than running unbounded. Roles
  return whatever they completed along with a halt reason, the shift closes,
  and the halt is recorded (physics.md Section 12).

  A shift that fails outright commits nothing, and says so. The emissions it
  produced are discarded rather than half-recorded — an incomplete shift is not
  terrain history. The failure itself is still written to the terrain event
  record, because the Charter (Section 3) forbids omitting an outcome for being
  inconvenient, but it does not claim a shift number.

  Low-frequency roles are gated in code (config.is_archivist_shift and
  friends), never by the steward remembering to skip them.

Steward boundary (DNT-STW-001 Section 2/3): this script initiates and ends
shifts and reads everything. It offers no way to edit taxonomy or specimen
records, no way to direct a Generator, and no override for a Namer decision. A
budget ceiling has no force flag.

Python 3.9 compatible.
"""

from __future__ import annotations

import datetime
import os
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents"))

import config
import terrain_io

import generator_a
import generator_b
import namer


# A specimen not seen again after this many shifts resolves to a defined
# end-state rather than being silently dropped (physics.md Section 7).
DORMANCY_AFTER_SHIFTS = 1

RULE = "-" * 68


def _utc_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ---------------------------------------------------------------------------
# Role availability
#
# Roles are built in the order README.md Section 2 sets out. A role whose
# cadence gate is open but whose module is not built yet is reported as such
# rather than silently skipped.
# ---------------------------------------------------------------------------


def _load_optional_role(module_name: str):
    try:
        return __import__(module_name)
    except ImportError:
        return None


def active_roles(shift_number: int) -> Tuple[List[str], List[str]]:
    """Return (active, gated_but_unbuilt) for this shift."""
    active = ["generator_a", "generator_b", "namer"]
    unbuilt: List[str] = []

    if config.is_keeper_shift(shift_number):
        if _load_optional_role("keeper"):
            active.insert(0, "keeper")
        else:
            unbuilt.append("keeper")

    if config.is_archivist_shift(shift_number):
        if _load_optional_role("archivist"):
            active.append("archivist")
        else:
            unbuilt.append("archivist")

    if config.is_cartographer_shift(shift_number):
        if _load_optional_role("cartographer"):
            active.append("cartographer")
        else:
            unbuilt.append("cartographer")

    return active, unbuilt


# ---------------------------------------------------------------------------
# End-state resolution
# ---------------------------------------------------------------------------


def resolve_end_states(memory: Dict[str, Any], shift_number: int) -> int:
    """Give every specimen that stopped updating a defined end-state.

    physics.md Section 7: a specimen that stops updating resolves to
    dissolution, dormancy, or unresolved — logged, never silently dropped.
    Emissions in this terrain do not recur across shifts, so one that is not
    seen again settles into dormancy: an inert feature of the terrain rather
    than an active specimen.
    """
    index = memory.setdefault("specimen_index", {})
    resolved = 0
    for specimen_id, entry in index.items():
        if entry.get("end_state"):
            continue
        last_seen = int(entry.get("last_seen_shift", shift_number))
        if shift_number - last_seen >= DORMANCY_AFTER_SHIFTS:
            entry["end_state"] = "dormant"
            entry["resolved_at_shift"] = shift_number
            resolved += 1
    return resolved


# ---------------------------------------------------------------------------
# Read-only views
# ---------------------------------------------------------------------------


def show_status() -> int:
    terrain_io.initialize_terrain()
    memory = terrain_io.read_memory()
    taxonomy = terrain_io.read_taxonomy()
    clean, findings = terrain_io.verify_integrity()

    spent = float(memory.get("cumulative_cost_usd", 0.0))
    next_shift = int(memory.get("last_committed_shift", -1)) + 1
    structure = namer.measure_taxonomy_structure(taxonomy.get("native", {}))

    print(RULE)
    print("%s (%s) — %s" % (config.TERRAIN_NAME, config.TERRAIN_ID, "status"))
    print(RULE)
    print("phase                 : %s (%s)" % (config.PHASE, config.model_for_role("namer")))
    print("shifts completed      : %s" % memory.get("shifts_completed", 0))
    print("next shift            : %d" % next_shift)
    print("resource flow next    : %.4f" % config.resource_flow_for_shift(next_shift))
    print("")
    print("cumulative cost       : $%.4f of $%.2f (%.1f%%)"
          % (spent, config.TOTAL_USD_CEILING, (spent / config.TOTAL_USD_CEILING) * 100.0))
    print("per-shift cap         : $%.2f" % config.PER_SHIFT_USD_CAP)
    print("")
    print("specimen records      : %d" % len(terrain_io.read_log(config.SPECIMEN_LOG)))
    print("anomaly records       : %d" % len(terrain_io.read_anomalies()))
    print("categories coined     : %d" % len(memory.get("category_stats", {})))
    print("taxonomy depth        : %d  (diverged from a flat list: %s)"
          % (structure["max_depth"], structure["diverged_from_flat_list"]))
    print("terrain events        : %d" % len(memory.get("terrain_events", [])))
    print("")

    # physics.md Section 11 — the checkpoint is read from the record.
    canonical = [
        record
        for record in terrain_io.read_shift_log()
        if record.get("phase") == "claude"
    ]
    print("canonical shifts run  : %d of 15 to the falsification checkpoint"
          % len(canonical))

    print("integrity             : %s" % ("clean" if clean else "SEE FINDINGS"))
    for finding in findings:
        print("  - %s" % finding)
    print(RULE)
    return 0 if clean else 1


# ---------------------------------------------------------------------------
# The shift
# ---------------------------------------------------------------------------


def run_shift(dry_run: bool = False) -> int:
    started_monotonic = time.time()
    start_timestamp = _utc_now()

    terrain_io.initialize_terrain()

    # An interrupted commit leaves records from a shift that never closed. A new
    # shift would reuse that shift number and make the record ambiguous, so the
    # loop refuses to start and hands the decision to the steward rather than
    # quietly writing over the question.
    clean, findings = terrain_io.verify_integrity()
    if not clean:
        print("REFUSING TO START — terrain integrity findings:")
        for finding in findings:
            print("  - %s" % finding)
        print("")
        print("These records stand; they are not corruption. Read them, decide")
        print("how the interrupted shift should be treated, and note the")
        print("decision. The loop will not overwrite the question for you.")
        return 1

    memory = terrain_io.read_memory()
    shift_number = int(memory.get("last_committed_shift", -1)) + 1
    cumulative = float(memory.get("cumulative_cost_usd", 0.0))

    try:
        warnings = config.preflight(shift_number, cumulative)
    except config.BudgetExceeded as exc:
        print("REFUSING TO START — %s" % (exc,))
        print("")
        print("physics.md Section 12: no new shift may begin if its projected")
        print("cost would breach the terrain ceiling. There is no override.")
        return 1

    active, unbuilt = active_roles(shift_number)
    flow = config.resource_flow_for_shift(shift_number)

    print(RULE)
    print("CLOCK IN — shift %d — %s" % (shift_number, start_timestamp))
    print(RULE)
    print("phase          : %s (%s)" % (config.PHASE, config.model_for_role("namer")))
    print("active roles   : %s" % ", ".join(active))
    if unbuilt:
        print("gated, unbuilt : %s" % ", ".join(unbuilt))
    print("resource flow  : %.4f" % flow)
    print("cumulative cost: $%.4f of $%.2f" % (cumulative, config.TOTAL_USD_CEILING))
    for warning in warnings:
        print("!! %s" % warning)
    print("")

    if dry_run:
        print("--dry-run: nothing was run, nothing was written.")
        return 0

    ledger = config.ShiftLedger(shift_number, cumulative_spend_usd=cumulative)
    transaction = terrain_io.Transaction(shift_number)
    halts: List[str] = []

    try:
        # -- Keeper: continuity across a discontinuous system ---------------
        continuity_summary: Optional[str] = None
        keeper_module = _load_optional_role("keeper") if "keeper" in active else None
        if keeper_module is not None:
            keeper_outcome = keeper_module.run(
                shift_number=shift_number,
                writer=terrain_io.writer_for_role(transaction, "keeper"),
                ledger=ledger,
                memory=transaction.memory,
                recent_specimens=terrain_io.read_recent_specimens(),
            )
            if keeper_outcome.get("halt_reason"):
                halts.append("keeper %s" % keeper_outcome["halt_reason"])
            # Carried to the roles that reason over history. Deliberately NOT
            # carried to the Generators: the calls below take no summary
            # argument, so there is no wiring by which a description of prior
            # output could reach a role that is only ever told its substrate
            # and its constraint (see keeper.py).
            continuity_summary = keeper_outcome.get("summary")
            print("keeper       : %s"
                  % ("summary written" if keeper_outcome.get("written")
                     else "no summary this shift (previous retained)"))

        # -- Generators: self-initiating, no write capability ---------------
        emissions_a, halt_a = generator_a.run(shift_number, flow, ledger)
        if halt_a:
            halts.append("generator_a %s" % halt_a)
        print("generator_a  : %d emission(s)%s"
              % (len(emissions_a), "  HALTED" if halt_a else ""))

        emissions_b, halt_b = generator_b.run(shift_number, flow, ledger)
        if halt_b:
            halts.append("generator_b %s" % halt_b)
        print("generator_b  : %d emission(s)%s"
              % (len(emissions_b), "  HALTED" if halt_b else ""))

        emissions = emissions_a + emissions_b

        # -- Namer: classification and the code-enforced logging tier -------
        outcome = namer.run(
            shift_number=shift_number,
            emissions=emissions,
            writer=terrain_io.writer_for_role(transaction, "namer"),
            ledger=ledger,
            native=transaction.taxonomy.get("native", {}),
            recent_specimens=terrain_io.read_recent_specimens(),
            category_stats=transaction.memory.get("category_stats", {}),
            continuity_summary=continuity_summary,
        )
        if outcome.get("halt_reason"):
            halts.append("namer %s" % outcome["halt_reason"])
        print("namer        : %d classified (%d individual, %d aggregate, "
              "%d anomalous, %d unresolved)"
              % (outcome["classified"], outcome["individual_records"],
                 outcome["aggregate_records"], outcome["anomalous"],
                 outcome["unresolved"]))
        if outcome.get("parse_failed"):
            print("               response unparseable — logged as unresolved, "
                  "not as anomalies")

        # -- Low-frequency roles, behind their cadence gates ----------------
        for role_name in ("archivist", "cartographer"):
            if role_name not in active:
                continue
            module = _load_optional_role(role_name)
            if module is None:
                continue
            kwargs = {
                "shift_number": shift_number,
                "writer": terrain_io.writer_for_role(transaction, role_name),
                "ledger": ledger,
                "taxonomy_native": transaction.taxonomy.get("native", {}),
                "memory": transaction.memory,
            }
            if role_name == "cartographer":
                # Positional tracking needs the full placed record, which is a
                # free read — this role makes no model call.
                kwargs["specimen_records"] = terrain_io.read_log(config.SPECIMEN_LOG)

            role_outcome = module.run(**kwargs)
            if role_outcome.get("halt_reason"):
                halts.append("%s %s" % (role_name, role_outcome["halt_reason"]))

            if role_name == "archivist":
                drift = role_outcome.get("drift") or {}
                print("archivist    : crosswalk %s; drift %s"
                      % ("produced" if role_outcome.get("crosswalk") else "not available",
                         "DETECTED" if drift.get("drift_detected") else "none"))
                for label in drift.get("coined_then_dropped_from_system", []):
                    print("               dropped from its own system: %s" % label)
            else:
                print("cartographer : %d specimen(s) placed across %d zone(s), no model call"
                      % (role_outcome.get("specimens_placed", 0),
                         role_outcome.get("zones", 0)))

    except config.ModelUnavailable as exc:
        return _abort(transaction, shift_number, start_timestamp, ledger,
                      "model backend unavailable: %s" % (exc,))
    except Exception as exc:                       # unexpected — never silent
        detail = "%s: %s" % (exc.__class__.__name__, exc)
        traceback.print_exc()
        return _abort(transaction, shift_number, start_timestamp, ledger, detail)

    # -- Update terrain state ----------------------------------------------
    memory = transaction.memory
    memory["category_stats"] = outcome.get("category_stats", memory.get("category_stats", {}))
    memory["resource"]["flow"] = flow
    memory["cumulative_cost_usd"] = round(ledger.cumulative_total, 6)
    memory["taxonomy_structure"] = outcome.get("taxonomy_structure")

    index = memory.setdefault("specimen_index", {})
    for position, emission in enumerate(emissions):
        specimen_id = namer._specimen_id(shift_number, position)
        index[specimen_id] = {
            "source_role": emission["source_role"],
            "substrate": emission["substrate"],
            "complexity": emission.get("complexity"),
            "first_seen_shift": shift_number,
            "last_seen_shift": shift_number,
            "end_state": None,
        }
    dormant = resolve_end_states(memory, shift_number)

    counts = memory.setdefault("specimen_counts", {})
    counts["total"] = int(counts.get("total", 0)) + outcome["classified"]
    counts["individual_records"] = int(counts.get("individual_records", 0)) + outcome["individual_records"]
    counts["aggregate_members"] = int(counts.get("aggregate_members", 0)) + outcome["aggregate_records"]
    counts["anomalous"] = int(counts.get("anomalous", 0)) + outcome["anomalous"]

    anomalies_this_shift = outcome["anomalous"] + outcome["unresolved"]
    notable = bool(
        anomalies_this_shift
        or outcome["new_categories"]
        or outcome["individual_records"]
        or halts
        or warnings
        or outcome.get("parse_failed")
    )

    ended_timestamp = _utc_now()
    duration = round(time.time() - started_monotonic, 1)

    # -- The shift record, per DNT-SLP-001 Section 2 ------------------------
    transaction.append_shift_record(
        {
            "shift_id": shift_number,
            "start_timestamp": start_timestamp,
            "end_timestamp": ended_timestamp,
            "duration_seconds": duration,
            "active_seed_agents": active,
            "gated_but_unbuilt_roles": unbuilt,
            "estimated_cost_usd": round(ledger.shift_cost_usd, 6),
            "cumulative_cost_usd": round(ledger.cumulative_total, 6),
            "notable_events": notable,
            "anomalies_logged": anomalies_this_shift,
            # Beyond the required minimum, for cost and falsification tracking.
            "phase": config.PHASE,
            "model": config.model_for_role("namer"),
            "resource_flow": flow,
            "emissions": len(emissions),
            "classified": outcome["classified"],
            "individual_records": outcome["individual_records"],
            "aggregate_records": outcome["aggregate_records"],
            "anomalous": outcome["anomalous"],
            "unresolved": outcome["unresolved"],
            "new_categories": outcome["new_categories"],
            "taxonomy_structure": outcome.get("taxonomy_structure"),
            "specimens_resolved_dormant": dormant,
            "tokens": {
                "input": ledger.shift_input_tokens,
                "output": ledger.shift_output_tokens,
                "total": ledger.shift_tokens,
            },
            "model_calls": ledger.calls,
            "halts": halts,
            "budget_warnings": warnings,
            "budget_fraction_used": round(ledger.budget_fraction_used, 4),
        }
    )

    written = transaction.commit()

    # -- Clock out ----------------------------------------------------------
    print("")
    print(RULE)
    print("CLOCK OUT — shift %d — %s (%.1fs)" % (shift_number, ended_timestamp, duration))
    print(RULE)
    print("records written : %d specimen, %d anomaly, %d shift"
          % (written["specimen_records"], written["anomaly_records"],
             written["shift_records"]))
    print("new categories  : %s" % (", ".join(outcome["new_categories"]) or "none"))
    structure = outcome.get("taxonomy_structure") or {}
    print("taxonomy        : depth %s, diverged from a flat list: %s"
          % (structure.get("max_depth"), structure.get("diverged_from_flat_list")))
    print("resolved dormant: %d" % dormant)
    print("notable events  : %s" % ("yes" if notable else "no"))
    print("tokens          : %d in, %d out (%d calls)"
          % (ledger.shift_input_tokens, ledger.shift_output_tokens, ledger.calls))
    print("shift cost      : $%.6f" % ledger.shift_cost_usd)
    print("cumulative      : $%.4f of $%.2f (%.1f%%)"
          % (ledger.cumulative_total, config.TOTAL_USD_CEILING,
             ledger.budget_fraction_used * 100.0))
    for halt in halts:
        print("!! halted: %s" % halt)
    for warning in warnings:
        print("!! %s" % warning)
    print(RULE)
    return 0


def _abort(
    transaction: terrain_io.Transaction,
    shift_number: int,
    start_timestamp: str,
    ledger: config.ShiftLedger,
    detail: str,
) -> int:
    """Discard the shift, record that it failed, and exit non-zero.

    Everything the shift produced is dropped. An incomplete shift is not
    terrain history, and half-recording it would put specimens into the record
    that were never classified. The failure itself is written — with
    mark_shift=False, so it does not claim a shift number — because the Charter
    (Section 3) forbids leaving an outcome out of the record for being
    inconvenient.
    """
    transaction.abort()

    print("")
    print(RULE)
    print("SHIFT ABORTED — nothing committed")
    print(RULE)
    print("reason: %s" % detail)
    print("")
    print("state/ is unchanged, at its last good checkpoint. This shift did")
    print("not occur: shift %d remains unused." % shift_number)

    try:
        failure = terrain_io.Transaction(shift_number)
        failure.record_terrain_event(
            kind="shift_aborted",
            detail=(
                "Shift %d began at %s and failed before clock-out: %s. "
                "No specimen or classification records were written. "
                "%d model call(s) had been made, $%.6f spent."
                % (shift_number, start_timestamp, detail, ledger.calls,
                   ledger.shift_cost_usd)
            ),
        )
        # Spend that already occurred is real and stays on the ledger even
        # though the shift produced nothing.
        failure.memory["cumulative_cost_usd"] = round(ledger.cumulative_total, 6)
        failure.commit(mark_shift=False)
        print("The failure is recorded as a terrain event in memory.json.")
    except Exception as exc:
        print("Could not record the failure as a terrain event: %s" % (exc,))

    print(RULE)
    return 1


def main(argv: List[str]) -> int:
    flags = set(argv[1:])
    unknown = flags - {"--status", "--dry-run"}
    if unknown:
        print("unknown option(s): %s" % ", ".join(sorted(unknown)))
        print(__doc__.strip().splitlines()[2])
        return 2
    if "--status" in flags:
        return show_status()
    return run_shift(dry_run="--dry-run" in flags)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
