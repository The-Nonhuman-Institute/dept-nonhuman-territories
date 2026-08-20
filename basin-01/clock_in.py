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
import fcntl
import os
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents"))

import config


def _reexec_in_venv_if_needed() -> None:
    """Re-run this script under the project venv when Phase 2 needs it.

    Canonical shifts need the `anthropic` package, which lives in the project
    virtual environment rather than the system interpreter. Without this, the
    steward has to remember to type a different interpreter path for Phase 2
    than for Phase 1 — an easy thing to get wrong, and a confusing failure when
    it happens. `python3 clock_in.py` now works in both phases.
    """
    if config.PHASE != "claude":
        return
    try:
        import anthropic  # noqa: F401
        return
    except ImportError:
        pass

    # Loop guard via the environment, not by comparing interpreter paths. A
    # venv's bin/python is a symlink to the base interpreter, so realpath()
    # reports the two as identical and a path comparison silently concludes it
    # is already inside the venv when it is not.
    if os.environ.get("BASIN01_VENV_REEXEC") == "1":
        return

    venv_python = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".venv", "bin", "python",
    )
    if os.path.exists(venv_python):
        environment = dict(os.environ)
        environment["BASIN01_VENV_REEXEC"] = "1"
        os.execve(venv_python, [venv_python] + sys.argv, environment)


_reexec_in_venv_if_needed()

import terrain_io

import generator_a
import generator_b
import namer
import observer
import life


# A specimen not seen again after this many shifts resolves to a defined
# end-state rather than being silently dropped (physics.md Section 7).
DORMANCY_AFTER_SHIFTS = 1


def position_key(position: float) -> str:
    """Positions are held to two places, so occupancy accumulates per locale."""
    return "%.2f" % float(position)


def local_depletion(memory: Dict[str, Any], position: float) -> float:
    return float((memory.get("resource", {}).get("depletion") or {}).get(
        position_key(position), 0.0))


def apply_terrain_interaction(memory: Dict[str, Any], emissions: List[Dict[str, Any]],
                              dormant_positions: List[float]) -> Dict[str, float]:
    """Occupancy depletes local resource; time and dormancy return it.

    physics.md Section 3 requires a terrain-interaction mode; Section 6 defines a
    decomposer as recycling dissolved specimens back into resource. This is that,
    quantitatively: a specimen holds resource out of its position while it
    persists, and releases it when it resolves.
    """
    resource = memory.setdefault("resource", {})
    depletion = resource.setdefault("depletion", {})

    # Recovery first — the terrain regains ground before this shift's occupancy.
    for key in list(depletion):
        depletion[key] = max(0.0, float(depletion[key]) - config.RECOVERY_PER_SHIFT)

    # Dormancy releases held resource back into the position that held it.
    for position in dormant_positions:
        key = position_key(position)
        depletion[key] = max(0.0, float(depletion.get(key, 0.0)) - config.RELEASE_ON_DORMANCY)

    # This shift's occupancy takes resource out.
    for emission in emissions:
        key = position_key(emission.get("position", 0.0))
        depletion[key] = min(
            config.MAX_DEPLETION,
            float(depletion.get(key, 0.0)) + config.DEPLETION_PER_SPECIMEN,
        )

    return {k: round(v, 4) for k, v in depletion.items()}


def claim_replication_slots(memory: Dict[str, Any], shift_number: int, role: str,
                            slots: int) -> List[Dict[str, Any]]:
    """Which prior specimens claim an initiation slot this shift.

    Eligibility was fixed when the specimen was recorded (its own measured
    complexity against a constant threshold), so nothing here is a judgment
    call and no model is consulted. A lineage can never take every slot.
    """
    ceiling = int(slots * config.REPLICATION_MAX_SLOT_FRACTION)
    if ceiling < 1:
        return []
    index = memory.get("specimen_index", {}) or {}
    candidates = []
    for specimen_id, entry in index.items():
        if entry.get("source_role") != role:
            continue
        if entry.get("end_state"):
            continue
        if int(entry.get("replication_remaining", 0)) <= 0:
            continue
        candidates.append((specimen_id, entry))
    # Most recent first, so a lineage continues from its latest form.
    candidates.sort(key=lambda kv: (-int(kv[1].get("last_seen_shift", 0)),
                                    -int(kv[1].get("complexity", 0))))
    claimed = []
    for specimen_id, entry in candidates[:ceiling]:
        claimed.append({
            "specimen_id": specimen_id,
            "content": entry.get("content", ""),
            "generation": int(entry.get("generation", 0)),
        })
        entry["replication_remaining"] = int(entry.get("replication_remaining", 0)) - 1
        entry["replicated_at_shifts"] = (entry.get("replicated_at_shifts") or []) + [shift_number]
    return claimed

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
    world = memory.get("world", {})
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
    # Deliberately does not initialise. --status is documented as read-only,
    # and seeding a half-present terrain would replace the Namer's taxonomy
    # with an empty one while memory.json still describes the real thing.
    absent = terrain_io.missing_terrain_files()
    if absent:
        print(RULE)
        print("%s (%s) — NOT INITIALISED" % (config.TERRAIN_NAME, config.TERRAIN_ID))
        print(RULE)
        print("missing: %s" % ", ".join(absent))
        print("")
        print("Nothing has been created. Run a shift to seed a new terrain, or")
        print("restore the missing file(s) if this terrain has run before.")
        print(RULE)
        return 1

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

    if dry_run:
        # --dry-run promises it writes nothing, so it may not seed either.
        absent = terrain_io.missing_terrain_files()
        if absent:
            print("--dry-run: this terrain is not initialised (missing %s)."
                  % ", ".join(absent))
            print("Nothing was run, nothing was written.")
            return 1
    else:
        terrain_io.initialize_terrain()

    # An interrupted commit leaves records from a shift that never closed. A new
    # shift would reuse that shift number and make the record ambiguous, so the
    # loop refuses to start and hands the decision to the steward rather than
    # quietly writing over the question.
    findings = terrain_io.integrity_findings()
    blocking = [m for severity, m in findings if severity == "blocking"]
    standing = [m for severity, m in findings if severity == "standing"]

    if blocking:
        print("REFUSING TO START — terrain integrity findings:")
        for finding in blocking:
            print("  - %s" % finding)
        print("")
        print("These records stand; they are not corruption. Read them, decide")
        print("how the interrupted shift should be treated, and note the")
        print("decision. The loop will not overwrite the question for you.")
        return 1

    # Standing findings describe damage this record already carries — a past
    # concurrency incident, a lost update. They do not make the next shift
    # ambiguous, so they do not stop one, but they are printed on every single
    # run rather than being quietly tolerated once and forgotten.
    if standing:
        print("STANDING INTEGRITY FINDINGS — this record already carries:")
        for finding in standing:
            print("  - %s" % finding)
        print("")

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

        # -- The terrain lives ----------------------------------------------
        # This is free: life.py makes no model call. Everything that follows is
        # the terrain being turned into a record, which is the part that costs.
        world = transaction.memory.setdefault("world", life.seed_state())
        if not any(c["census_density"] > 0 for c in world["cells"]):
            # First light. Two arrivals seed the ground, one at each Generator's
            # position; everything after this the terrain does itself.
            life.seed_census(world, int(config.GENERATOR_A_POSITION * (life.CELL_COUNT - 1)),
                             generator_a.SUBSTRATE)
            life.seed_census(world, int(config.GENERATOR_B_POSITION * (life.CELL_COUNT - 1)),
                             generator_b.SUBSTRATE)

        living = life.step(world, shift_number, flow)
        print("terrain      : %d living, %d arose, %d ended, %d links, cover in %d cell(s)"
              % (len(world["individuals"]), len(living["arose_from_census"]),
                 len(living["ended"]), len(living["links_formed"]),
                 life.census_summary(world)["cells_with_cover"]))

        # -- Generators: a substrate trace for what newly arrived -------------
        # Generators no longer produce the terrain's activity. They are how
        # something newly arisen acquires the material it is made of.
        traces: Dict[str, str] = transaction.memory.setdefault("traces", {})
        newly = living["arose_from_census"] + [c for _, c in living["replicated"]]
        for identifier in newly[: config.MAX_TRACES_PER_SHIFT]:
            being = world["individuals"].get(identifier)
            if not being or identifier in traces:
                continue
            module = generator_a if being["substrate"] == generator_a.SUBSTRATE else generator_b
            parent_trace = traces.get(being.get("parent_id") or "", None)
            material = ([{"content": parent_trace, "specimen_id": being["parent_id"]}]
                        if parent_trace else None)
            emissions, halt = module.run(
                shift_number, flow, ledger,
                source_material=material)
            if halt:
                halts.append("%s %s" % (module.ROLE, halt))
                break
            if emissions:
                traces[identifier] = emissions[0]["content"]

        # -- Namer: observes what is living ----------------------------------
        observed_before = transaction.memory.setdefault("observed_ids", [])
        chosen = observer.select_for_observation(
            world, shift_number, observed_before, config.MAX_OBSERVATIONS_PER_SHIFT)

        observations = []
        for being in chosen:
            record = observer.describe_individual(
                being, shift_number, traces.get(being["id"]))
            observations.append({
                "specimen_id": record["specimen_id"],
                "source_role": "terrain",
                "substrate": record["substrate"],
                "complexity": record["shifts_present"],
                "content": observer.observation_text(record),
                "measurements": record,
            })
        for being in chosen:
            if being["id"] not in observed_before:
                observed_before.append(being["id"])

        outcome = namer.run(
            shift_number=shift_number,
            emissions=observations,
            writer=terrain_io.writer_for_role(transaction, "namer"),
            ledger=ledger,
            native=transaction.taxonomy.get("native", {}),
            recent_specimens=terrain_io.read_recent_specimens(),
            category_stats=transaction.memory.get("category_stats", {}),
            continuity_summary=continuity_summary,
        )
        if outcome.get("halt_reason"):
            halts.append("namer %s" % outcome["halt_reason"])
        print("namer        : %d observed (%d individual, %d aggregate, "
              "%d anomalous, %d unresolved)"
              % (outcome["classified"], outcome["individual_records"],
                 outcome["aggregate_records"], outcome["anomalous"],
                 outcome["unresolved"]))

        # The cover layer, recorded as a census rather than per instance.
        census = observer.census_observation(world)
        transaction.memory["census"] = census

        # Everything that ended, with its end-state. Nothing dropped.
        for gone in observer.ended_since(world, shift_number):
            terrain_io.writer_for_role(transaction, "namer").append_anomaly({
                "specimen_id": gone["id"],
                "record_tier": "ended",
                "resolution": gone.get("end_state", "dissolved"),
                "is_classification_outcome": False,
                "shifts_present": gone.get("age"),
                "position_cell": gone.get("cell"),
                "descendants": gone.get("descendants"),
                "note": "Ran out of light and ended; what it held stayed where it fell.",
            })
        emissions = observations

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

    world = memory.get("world", {})
    index = memory.setdefault("specimen_index", {})
    # The Namer's own persistence wording per specimen, keyed by id, so the
    # index carries what it actually wrote (physics.md Section 5).
    persistence_by_id = {
        record.get("specimen_id"): (record.get("classification") or {}).get(
            "persistence_native", "")
        for record in outcome.get("records", []) or []
    }
    for emission in emissions:
        specimen_id = emission["specimen_id"]
        measurements = emission.get("measurements", {})
        complexity = int(emission.get("complexity") or 0)
        index[specimen_id] = {
            "source_role": emission["source_role"],
            "substrate": emission["substrate"],
            "complexity": complexity,
            "position": measurements.get("position_on_gradient"),
            "content": emission.get("content", ""),
            "first_seen_shift": shift_number,
            "last_seen_shift": shift_number,
            "end_state": None,
            # Replication mode: capacity granted by a fixed threshold on the
            # specimen's own measured complexity, never by a Namer decision.
            "replication_remaining": (
                config.REPLICATION_PERSISTENCE_SHIFTS
                if config.is_replication_eligible(complexity) else 0
            ),
            "parent_id": measurements.get("parent_id"),
            "generation": int(measurements.get("generation", 0) or 0),
            "persistence_native": persistence_by_id.get(specimen_id, ""),
        }

    # Positions releasing resource as their specimens resolve (physics.md
    # Section 6, decomposer: dissolved specimens recycled back into resource).
    # Specimens recorded before terrain-interaction mode existed carry no
    # position, so they hold no local resource and release none. They are not
    # retrofitted: the record says what it said.

    dormant = len(living.get("ended", []))

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
            "living": len(world.get("individuals", {})),
            "arose_this_shift": len(living.get("arose_from_census", [])),
            "ended_this_shift": len(living.get("ended", [])),
            "replicated_this_shift": len(living.get("replicated", [])),
            "links_formed": len(living.get("links_formed", [])),
            "light_along_links": living.get("light_along_links", 0.0),
            "census": census,
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
    print("arose / ended   : %d / %d   links formed %d"
          % (len(living.get("arose_from_census", [])), len(living.get("ended", [])),
             len(living.get("links_formed", []))))
    print("terrain         : %d living, cover in %d of %d cells, residue %.1f"
          % (len(world.get("individuals", {})), census["cells_occupied"],
             census["cells_total"], census["residue_pool"]))
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



# ---------------------------------------------------------------------------
# ONE SHIFT AT A TIME, ENFORCED.
#
# Two batches were started against BASIN-05 without the first being stopped.
# Both read the same next shift number, both ran it, and both committed:
# shifts 8 and 9 each appear twice in that terrain's shift log, with different
# figures, and its specimen log carries records from a run whose state was then
# overwritten by the other. The terrain's state stayed internally coherent —
# atomic commit did its job — but the RECORD now contains work that did not
# produce the state beside it.
#
# Nothing in the harness prevented that, so nothing stopped it happening. This
# does: a shift takes an exclusive kernel lock on the terrain directory and
# refuses to start if another already holds it.
#
# The lock is held by the kernel, not by a file we write and check. An earlier
# version looked for a pid file and then created one, which is two separate
# steps with a gap in between: four processes released together took the lock
# simultaneously in 60 trials out of 60, because all four looked before any of
# them wrote. It also read a live process owned by another user as dead, and a
# recycled pid as alive. flock has none of those failure modes, and the kernel
# drops it on every exit path including SIGKILL and power loss, so a crash
# cannot wedge the terrain either.
# ---------------------------------------------------------------------------
def _acquire_shift_lock():
    """Refuse to run if another shift is already running on this terrain.

    Returns an open file descriptor that must stay open for the whole shift —
    the lock lives on the descriptor, and closing it releases the terrain.
    """
    path = os.path.join(config.TERRAIN_ROOT, ".shift.lock")
    handle = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        try:
            with open(path, encoding="utf-8") as stream:
                holder = stream.read().strip() or "unknown"
        except IOError:
            holder = "unknown"
        os.close(handle)
        print(RULE)
        print("REFUSED — a shift is already running on this terrain (pid %s)" % holder)
        print(RULE)
        print("Two shifts running at once both read the same next shift number,")
        print("both run it, and both commit. Wait for that one to finish, or stop")
        print("it. Nothing has been read or written by this attempt.")
        return None

    os.ftruncate(handle, 0)
    os.write(handle, str(os.getpid()).encode("utf-8"))
    os.fsync(handle)
    return handle


def _release_shift_lock(handle):
    """Release the terrain. Closing the descriptor is what drops the lock."""
    if handle is None:
        return
    try:
        fcntl.flock(handle, fcntl.LOCK_UN)
    except (IOError, OSError):
        pass
    try:
        os.close(handle)
    except OSError:
        pass


def main(argv: List[str]) -> int:
    flags = set(argv[1:])
    unknown = flags - {"--status", "--dry-run"}
    if unknown:
        print("unknown option(s): %s" % ", ".join(sorted(unknown)))
        print(__doc__.strip().splitlines()[2])
        return 2
    if "--status" in flags:
        return show_status()
    lock = None
    if "--dry-run" not in flags:
        lock = _acquire_shift_lock()
        if lock is None:
            return 3
    try:
        return run_shift(dry_run="--dry-run" in flags)


    finally:
        _release_shift_lock(lock)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
