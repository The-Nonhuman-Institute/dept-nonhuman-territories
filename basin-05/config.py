# SPDX-FileCopyrightText: 2026 U3 Labs, LLC
# SPDX-License-Identifier: Apache-2.0
"""
BASIN-01 — model abstraction, hard caps, and cost ledger.

This module is the ONLY place in the terrain that opens a network connection.
No agent role imports a network library, and no agent role is permitted to
choose its own model, token ceiling, or spend. Every call goes through
generate(), which enforces the caps before the request is made rather than
trusting a role to stay inside them.

Governance references:
  physics.md  Section 8   logging tiers / promotion rule (constants below)
  physics.md  Section 9   hard boundaries (no writes outside terrain, no
                          agent-initiated network access)
  physics.md  Section 12  budget: $0.15 per shift, $15 total ceiling
  README.md   Section 2   phase swap must be a one-line change
  README.md   Section 3   per-role model assignment
  STARTUP_GUIDE.md Sec 4  caps enforced in code, not by willpower

Python 3.9 compatible (system interpreter on the steward's machine).
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. PHASE SWITCH — the one-line change between free scaffolding and canonical
#    runs. Nothing else in the terrain needs to change to swap phases.
# ---------------------------------------------------------------------------

PHASE = "ollama"          # "ollama" (Phase 1, zero cost) | "claude" (Phase 2)


# ---------------------------------------------------------------------------
# 2. TERRAIN PATHS
#    Every writable path in the terrain is derived from TERRAIN_ROOT. The
#    sandboxed write layer resolves against these and refuses anything outside
#    them (physics.md Section 9).
# ---------------------------------------------------------------------------

TERRAIN_ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(TERRAIN_ROOT, "state")
SHIFTS_DIR = os.path.join(TERRAIN_ROOT, "shifts")

MEMORY_FILE = os.path.join(STATE_DIR, "memory.json")
TAXONOMY_FILE = os.path.join(STATE_DIR, "taxonomy.json")
SPECIMEN_LOG = os.path.join(STATE_DIR, "specimen_log.jsonl")
ANOMALY_LOG = os.path.join(STATE_DIR, "anomaly_log.jsonl")
SHIFT_LOG = os.path.join(SHIFTS_DIR, "shift_log.jsonl")
# BASIN-02 only. The full 315-cell grid, appended every shift, so the aggregate
# figures the Namer is shown can be recomputed from the raw field and checked
# rather than trusted. Nothing reads this back; it exists to be audited.
FIELD_LOG = os.path.join(STATE_DIR, "field_log.jsonl")

# The landscape this terrain stands on, formed by geomorph.py before anything
# lived here. It is a starting ground, not a fixed one — the terrain keeps
# forming and grows at its margins, and what it becomes is carried in
# memory.json with the rest of the record.
LANDSCAPE_FILE = os.path.join(TERRAIN_ROOT, "landscape_120x60_6000.json")

# ---------------------------------------------------------------------------
# GOVERNING CONDITIONS — BASIN-05's difference from every terrain before it
#
# BASIN-01 through 03 had exactly one environmental axis: how much light
# reaches a cell. Elevation was added in BASIN-02 and a real landscape in
# BASIN-03, but neither changed what a cell IS to something living in it —
# every place still differed along a single gradient, which is the most likely
# reason one way of living dominated all three.
#
# Six conditions are declared here. Each is a real mechanic that changes what
# the physics does, not a label on a page. Each is stated with the quantity it
# governs, so a reader can check the claim against life.py.
#
#   LIGHT CYCLE   period and amplitude of the resource oscillation. This
#                 already existed and was never named or exposed; naming it is
#                 the honest part of this amendment.
#   TEMPERATURE   a rate multiplier on metabolism. Scales BOTH what a specimen
#                 draws and what its upkeep costs. Falls with elevation, rises
#                 near the stream, and moves with the light cycle — so it runs
#                 ACROSS the light gradient rather than along it.
#   WIND          a prevailing direction that moves residue laterally,
#                 independently of slope. Windward scours; leeward collects.
#   GRAVITY       scales drainage, the cost of moving, and structural upkeep
#                 per unit of mass. A large build is cheap to hold up under low
#                 gravity and expensive under high.
#   HYDROLOGY     subsurface flow. Water moves under the ground and emerges as
#                 springs where enough has gathered, putting resource in places
#                 the surface gradient says should be barren.
#   SHIFT LENGTH  how much of everything happens in one tick.
#
# None of these is tuned toward an outcome. They are set at values that make
# each mechanic express itself; what they produce is the experiment.
# ---------------------------------------------------------------------------

LIGHT_CYCLE_PERIOD = 12          # shifts per full cycle
LIGHT_CYCLE_AMPLITUDE = 0.35     # swing either side of baseline flow

TEMPERATURE_AT_STREAM = 22.0     # degrees at the watercourse, at cycle peak
TEMPERATURE_LAPSE = 23.0          # BASIN-04 runs 14.0. Steeper cooling with
                                  # height makes high ground reliably colder
                                  # rather than colder only in season. Chosen
                                  # mid-range, not at the maximum of the
                                  # sampled curve: spatial spread peaks near
                                  # lapse 26 and falls after, because ground
                                  # past that drops below the tolerance floor
                                  # and the range compresses again.         # degrees lost across the full elevation range
TEMPERATURE_CYCLE_SWING = 5.0     # BASIN-04 runs 9.0. At 9.0 the spread of
                                  # metabolic rate across TIME is 3.4x its
                                  # spread across PLACE, so the terrain has a
                                  # season and no habitats: everywhere warms
                                  # and cools together and one strategy wins
                                  # everywhere. Measured at 5.0/23.0 the ratio
                                  # inverts and place leads time.    # degrees the light cycle carries with it
TEMPERATURE_OPTIMUM = 16.0       # where metabolic rate peaks
TEMPERATURE_TOLERANCE = 13.0     # degrees either side before rate collapses

WIND_BEARING = 1.0               # radians; 0 = toward increasing lateral index
WIND_STRENGTH = 0.22             # share of residue moved downwind per shift

GRAVITY = 0.78                   # 1.00 is the reference used by BASIN-01..03

SUBSURFACE_RATE = 0.18           # share of residue that sinks per shift
SPRING_THRESHOLD = 4.0           # subsurface load at which a cell surfaces it
SPRING_YIELD = 0.45              # share released when it does

SHIFT_LENGTH = 1.0               # rate multiplier on everything per tick

TERRAIN_ID = "DNT-T05"
TERRAIN_NAME = "BASIN-05"


# ---------------------------------------------------------------------------
# 3. MODEL ASSIGNMENT PER ROLE
#
#    Phase 1: every role runs on the local model. Output quality is not the
#    object of Phase 1 — the loop, the storage, and the logging are.
#
#    Phase 2: physics.md Section 12 binds this terrain to Claude Haiku 4.5 for
#    Generators and routine Namer classification, and the same tier for
#    Archivist/Cartographer. README.md Section 3 says the Namer should get the
#    strongest model the budget allows. Where the two disagree, physics.md
#    governs (README.md line 8: physics is "the literal source of truth for
#    terrain rules"), so Namer is set to Haiku 4.5 here. Raising NAMER to
#    CLAUDE_STRONG_MODEL is a one-line steward decision, and PRICING already
#    carries the rates for it.
# ---------------------------------------------------------------------------

OLLAMA_MODEL = "gemma3:1b"          # steward-selected; see build notes
OLLAMA_ENDPOINT = "http://127.0.0.1:11434/api/generate"
OLLAMA_TIMEOUT_SECONDS = 2000     # BASIN-05 is founded on gemma3:1b, measured at
                                  # 4.24 tok/s against the 4b model's ~1.0 on this
                                  # machine — both wholly on CPU, no GPU present.
                                  # BASIN-04 reached 942s for a shift holding two
                                  # living specimens and climbs with every category
                                  # coined, because the Namer must reason against a
                                  # growing taxonomy. The model is a FOUNDING
                                  # choice here, fixed for this terrain's life, not
                                  # a switch made partway as BASIN-01 and BASIN-02
                                  # had to take.

CLAUDE_ROUTINE_MODEL = "claude-haiku-4-5"
CLAUDE_STRONG_MODEL = "claude-sonnet-5"   # available if the steward raises Namer

ROLES = (
    "generator_a",
    "generator_b",
    "namer",
    "keeper",
    "archivist",
    "cartographer",
)

CLAUDE_MODEL_BY_ROLE: Dict[str, str] = {
    "generator_a": CLAUDE_ROUTINE_MODEL,
    "generator_b": CLAUDE_ROUTINE_MODEL,
    "namer": CLAUDE_ROUTINE_MODEL,
    "keeper": CLAUDE_ROUTINE_MODEL,
    "archivist": CLAUDE_ROUTINE_MODEL,
    "cartographer": CLAUDE_ROUTINE_MODEL,
}

# USD per million tokens, verified against current published rates.
PRICING: Dict[str, Tuple[float, float]] = {
    # model: (input $/MTok, output $/MTok)
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-5": (5.00, 25.00),
}


# ---------------------------------------------------------------------------
# 4. HARD CAPS
#
#    These are ceilings enforced in code. A role cannot request more than its
#    cap; generate() clamps rather than trusting the request. Values below the
#    Generator caps were chosen for Phase 1 and are expected to be tuned during
#    Phase 1 testing (README.md Section 8) — tuning them is engineering, not a
#    governance change.
# ---------------------------------------------------------------------------

MAX_OUTPUT_TOKENS_BY_ROLE: Dict[str, int] = {
    "generator_a": 512,       # structural substrate, resource-scaled below cap
    "generator_b": 160,       # fragment substrate, short by constraint
    # README.md Section 5 requires the Namer's reasoning to be logged in
    # full, not summarised. Phase 1 showed 900 truncating mid-response on a
    # four-specimen batch, which would have silently clipped the primary
    # research data. Raised so the requirement is affordable rather than
    # nominal; at Haiku rates the extra headroom costs ~$0.0025 per shift.
    #
    # Raised again from 1600 at shift 109. The Namer returns its
    # classifications first and its native system last, so a reply that
    # overruns loses the system rather than the records: salvage recovers the
    # classifications, and the taxonomy object silently never arrives. The
    # terrain showed this as a native system stuck at zero nodes while
    # categories accumulated normally in the counters — the Namer WAS building
    # a system, and the harness was cutting it off mid-sentence every shift.
    #
    # This is a harness failure and was recorded as one (physics.md Section
    # 8.2). It is not a licence to let the reply grow without limit: the reply
    # scales with both the observation batch and the size of the system being
    # restated, so this cap needs revisiting as the taxonomy grows, and the
    # per-shift ceiling in this file remains the real bound.
    "namer": 4200,
    "keeper": 400,
    # Raised from 1200 when the persistence crosswalk (physics.md Section 5)
    # was added to this role's required output: the reply grew and began
    # truncating mid-JSON. The computed parts of the pass — drift, lineage
    # capability, persistence wordings — are written before the model call and
    # survive a truncation, but the crosswalk itself was being lost.
    "archivist": 2400,
    "cartographer": 600,
}

# Phase 1 only: a further ceiling on any single call, sized to what CPU
# inference can finish inside OLLAMA_TIMEOUT_SECONDS.
#
# This is a hardware allowance, not a relaxation of the logging requirement.
# STARTUP_GUIDE.md Section 2.5 is explicit that Phase 1 output is "disposable
# test data, not canonical terrain history" — the phase exists to debug the
# loop, not to produce records. The full-reasoning ceiling above applies
# unchanged to canonical shifts, which run on a hosted model in seconds rather
# than minutes. Phase 1 raised this to 1600 and shifts stopped finishing; the
# governance requirement and the local hardware were in direct conflict, and
# only the hardware side is negotiable.
# The Namer answers about every specimen in the batch in one reply, so what it
# needs is proportional to the batch — a flat number is the one shape this
# ceiling cannot be. It was flat at 420 against a batch of 5 needing roughly
# 930, and the reply was cut off in 26 of 31 records.
#
# The damage was not evenly spread. observer.select_for_observation orders the
# batch "never seen first, then longest present", and a truncated reply loses
# its tail — so the specimens with the longest history were the ones dropped,
# every single time. Measured on BASIN-05: mean age 0.84 shifts among the
# classified, 4.64 among the unresolved; i-00000 was observed twelve times and
# classified three. Continuity of observation is the Namer's whole purpose, and
# it was exactly what the ceiling removed.
#
# Both numbers below are measured from real replies, not guessed.
OLLAMA_OUTPUT_PER_SPECIMEN = 200   # one specimen's classification object
OLLAMA_OUTPUT_OVERHEAD = 320       # the taxonomy block and JSON scaffolding

# Ceiling on total tokens (input + output) a single shift may consume.
# A shift that would cross this ends early rather than running unbounded
# (STARTUP_GUIDE.md Section 4).
MAX_TOKENS_PER_SHIFT = 60_000

# Ceiling on model calls per shift — a second, cruder guard that catches a
# runaway loop even if each individual call is small.
MAX_CALLS_PER_SHIFT = 40

# Budget, physics.md Section 12 — FINAL.
PER_SHIFT_USD_CAP = 0.15
# BASIN-02 runs against its own ceiling, not the project's. BASIN-01 has spent
# $2.34 of the $15.00 and is finished; giving this terrain a separate, smaller
# bound means a runaway here cannot consume the headroom of a terrain it is
# supposed to be compared against. Combined spend is reported in /status.
#
# Raised from $6.00 to $8.00 at shift 180 by explicit steward instruction, to
# fund a test that the original ceiling could not: elevation was added to the
# physics at shift 141 and never added to what the Namer is shown, so the
# hollow/ridge question was left untested rather than answered. $6.00 left
# room for six more shifts, which is not a test.
#
# This is a ceiling the steward set, not an override of one. Nothing here
# weakens enforcement: the per-shift cap is unchanged, a shift that would
# breach either bound is still refused, and there remains no way for a shift
# to exceed the ceiling in force.
# BASIN-03 begins at zero. The loop is proved on the local model before a
# cent is spent, per STARTUP_GUIDE Section 2.5, and the steward raises this
# deliberately when there is something worth paying to observe.
TOTAL_USD_CEILING = 0.00
BUDGET_WARN_FRACTION = 0.75      # warn at 75% of the total ceiling

# Conservative characters-per-token divisor used to project cost BEFORE a call
# is made. Deliberately low (i.e. it over-estimates tokens) so the projection
# errs toward refusing a call rather than toward overspending.
CHARS_PER_TOKEN_ESTIMATE = 3.0


# ---------------------------------------------------------------------------
# 5. LOW-FREQUENCY ROLE GATES
#
#    physics.md Section 4.4/4.5 and Section 12: Archivist and Cartographer run
#    every 5th-10th shift, gated in code rather than by the steward
#    remembering to skip them.
# ---------------------------------------------------------------------------

ARCHIVIST_INTERVAL = 7
CARTOGRAPHER_INTERVAL = 7
ARCHIVIST_FIRST_SHIFT = 5        # physics.md Section 4.4: inactive until ~5+
CARTOGRAPHER_FIRST_SHIFT = 5     # physics.md Section 4.5: inactive until ~5+
KEEPER_FIRST_SHIFT = 1           # physics.md Section 4.3: no prior state at 0


def is_archivist_shift(shift_number: int) -> bool:
    """Fixed cadence gate. Not a judgment call, not a reminder."""
    return (
        shift_number >= ARCHIVIST_FIRST_SHIFT
        and shift_number % ARCHIVIST_INTERVAL == 0
    )


def is_cartographer_shift(shift_number: int) -> bool:
    """Fixed cadence gate. Not a judgment call, not a reminder."""
    return (
        shift_number >= CARTOGRAPHER_FIRST_SHIFT
        and shift_number % CARTOGRAPHER_INTERVAL == 0
    )


def is_keeper_shift(shift_number: int) -> bool:
    """Keeper needs prior state to read; shift 0 has none."""
    return shift_number >= KEEPER_FIRST_SHIFT


# ---------------------------------------------------------------------------
# 6. LOGGING-TIER PROMOTION RULE
#
#    physics.md Section 8 and the Classification Standard (DNT-CLS-001,
#    Section 5) both require the aggregate -> individual promotion threshold to
#    be a FIXED, EXPLICIT, CODE-CHECKED rule rather than a live judgment call.
#    physics.md states the rule but carries no numbers, so the thresholds are
#    made explicit here.
#
#    STEWARD ACTION: mirror these values into physics.md Section 8 before
#    shift 0. After shift 0, the Stewardship Protocol (Section 3) bars altering
#    the physics document except as a logged terrain event.
#
#    A specimen filed at aggregate tier is PROMOTED to an individual record if
#    ANY of the following hold. The Namer applies this as a mechanical check
#    before it is asked to reason, so promotion never depends on model output.
# ---------------------------------------------------------------------------

# (a) The Namer proposed a category that did not previously exist.
PROMOTE_ON_NEW_CATEGORY = True

# (b) The Namer could not file the specimen at all.
PROMOTE_ON_ANOMALOUS = True

# (c) Structural novelty: the specimen's measured complexity exceeds the
#     running mean for its category by this factor.
PROMOTE_COMPLEXITY_RATIO = 2.0

# (d) Rarity: the category this specimen would join holds fewer than this many
#     prior members, so the specimen is not yet high-volume by definition.
PROMOTE_IF_CATEGORY_SIZE_BELOW = 3

# (e) A category exceeding this many members is high-volume, and further
#     members are recorded at aggregate/census tier unless (a)-(d) fire.
AGGREGATE_TIER_CATEGORY_SIZE = 12

# Cap on how many recent specimen-log entries the Namer may be shown in one
# shift. Unbounded context growth is the single largest budget risk named in
# STARTUP_GUIDE.md Section 3.3. Full taxonomy is fine to include; full raw
# specimen history is not.
NAMER_RECENT_SPECIMEN_WINDOW = 12

# Phase 1 only: a shorter window still.
#
# Local shifts showed input growing 869 -> 1161 -> 1859 tokens across three
# shifts as history accumulated, with duration rising 508s -> 793s, and the
# fourth shift timing out. On CPU the cost of a shift is TIME, and it compounds
# exactly the way STARTUP_GUIDE.md Section 3.2 predicts cost will compound in
# Phase 2. Left alone the local terrain becomes unrunnable after a handful of
# shifts, which would remove the free rehearsal the whole phase exists to give.
#
# Phase 2 keeps the full window: a hosted model reads it in seconds for a
# fraction of a cent, so there is no reason to degrade the Namer's context
# where it actually matters.
OLLAMA_NAMER_RECENT_SPECIMEN_WINDOW = 4

# How many distinct native persistence wordings the Archivist crosswalks per
# pass. Bounded for the same reason the Namer's specimen window is bounded: the
# terrain accumulates new wordings every shift, so an unbounded list makes the
# required reply grow without limit and the pass eventually truncates. Raising
# the output cap only delays that; bounding the input fixes it.
ARCHIVIST_PERSISTENCE_WINDOW = 8

# The terrain's physics runs free — life.py makes no model call. Cost enters
# only where the terrain has to be turned into words: a trace drawn for
# something newly arisen, and the Namer's observation pass. Both are bounded,
# which is the same problem physics.md Section 8's two tiers describe: the
# cover layer is counted, individuals are looked at, and not everything can be
# looked at every interval.
MAX_TRACES_PER_SHIFT = 3        # newly arisen things given a substrate trace
MAX_OBSERVATIONS_PER_SHIFT = 5  # individuals the Namer looks at per shift

# Derived, never hand-set: whatever the batch is, the reply has room to answer
# for all of it. check_output_ceiling() below verifies this many tokens can
# actually be generated inside the timeout at the local model's real speed.
OLLAMA_OUTPUT_CEILING = (
    OLLAMA_OUTPUT_OVERHEAD + OLLAMA_OUTPUT_PER_SPECIMEN * MAX_OBSERVATIONS_PER_SHIFT
)



def namer_window() -> int:
    """How many recent specimen records the Namer is shown, per phase."""
    if PHASE == "ollama":
        return OLLAMA_NAMER_RECENT_SPECIMEN_WINDOW
    return NAMER_RECENT_SPECIMEN_WINDOW


# ---------------------------------------------------------------------------
# 7. RESOURCE VARIABLE
#
#    The terrain's single resource gradient, referenced by both Generator
#    constraint specs (README.md Section 4). Position is a scalar in [0.0, 1.0]
#    where 1.0 is maximum proximity to the data-stream channel.
#
#    Generator A's output allowance scales UP with proximity.
#    Generator B's initiation frequency scales UP with DISTANCE.
#
#    Positions are fixed at seed. The per-shift flow value fluctuates as a
#    terrain property, not as steward direction.
# ---------------------------------------------------------------------------

GENERATOR_A_POSITION = 0.85      # channel-proximate
GENERATOR_B_POSITION = 0.15      # channel-distant
RESOURCE_FLOW_BASELINE = 0.60    # memory.json carries the live value

# Flow varies across shifts on a fixed cycle. physics.md Section 5 describes
# this terrain as "closer to a tidal/seasonal system than continuous flow", so
# the variation is periodic rather than random, and derived from the shift
# number alone. That makes every shift's resource conditions reproducible from
# the record — a random walk would leave the steward unable to distinguish a
# terrain effect from a sampling artifact when reading the log months later.
#
# STEWARD NOTE: physics.md names the data-stream channel as the resource
# variable but does not specify how it varies over time. The cycle below is an
# engineering choice, not a governance decision. It belongs in physics.md
# Section 5 alongside the promotion thresholds, ratified before shift 0.
RESOURCE_FLOW_AMPLITUDE = 0.35
RESOURCE_FLOW_PERIOD_SHIFTS = 12
RESOURCE_FLOW_MIN = 0.05
RESOURCE_FLOW_MAX = 1.00


# ---------------------------------------------------------------------------
# 7.1 TERRAIN-INTERACTION MODE
#
#     physics.md Section 3 requires every Generator to be defined by six
#     mechanisms: substrate, constraint, resource logic, initiation mode,
#     replication mode, and terrain-interaction mode. The seed build
#     implemented the first four. These constants and Section 7.2 implement the
#     remaining two, which is why nothing in the terrain could previously act
#     on anything else.
#
#     Interaction here is strictly mechanical and strictly quantitative. A
#     specimen occupying a position DEPLETES the resource available at that
#     position; depletion RECOVERS over time; a specimen resolving to dormancy
#     RELEASES its held resource back (physics.md Section 6: a decomposer
#     "recycles dissolved/dead specimens into resource").
#
#     What this does NOT do: it never shows a Generator another specimen's
#     content. Occupancy changes the SIZE of an allowance, never what may be
#     produced with it, so the operative instruction still carries substrate and
#     constraint alone (physics.md Section 3).
# ---------------------------------------------------------------------------

# Resource a single recorded specimen holds out of its local position.
DEPLETION_PER_SPECIMEN = 0.055
# Fraction of local depletion that recovers each shift.
RECOVERY_PER_SHIFT = 0.040
# Resource returned when a specimen resolves to dormancy.
RELEASE_ON_DORMANCY = 0.030
# A position can never be depleted past this, so a zone is never permanently dead.
MAX_DEPLETION = 0.85


def effective_flow(base_flow: float, depletion: float) -> float:
    """Flow actually available at a position, after occupancy."""
    depletion = max(0.0, min(MAX_DEPLETION, float(depletion)))
    return round(max(RESOURCE_FLOW_MIN, float(base_flow) * (1.0 - depletion)), 4)


# ---------------------------------------------------------------------------
# 7.2 REPLICATION MODE
#
#     A specimen that meets a fixed, code-checked threshold may claim an
#     initiation slot in a later shift and produce a descendant from its own
#     prior material. That is the whole mechanism.
#
#     Eligibility is measured from the specimen itself — its own complexity —
#     and never from a Namer decision, so classification cannot drive
#     replication and the two roles stay independent.
#
#     The material a descendant works from is the terrain's OWN prior output,
#     never anything authored by the steward. Whether lineages converge,
#     diverge, or die out is an observed outcome and is not steered
#     (physics.md Section 3).
# ---------------------------------------------------------------------------

# Measured complexity at or above which a specimen gains the capacity to claim
# a later initiation slot.
REPLICATION_COMPLEXITY_THRESHOLD = 40
# How many later shifts an eligible specimen may claim a slot in.
REPLICATION_PERSISTENCE_SHIFTS = 2
# Ceiling on the fraction of a role's slots that replication may claim, so a
# lineage can never wholly displace fresh initiation.
REPLICATION_MAX_SLOT_FRACTION = 0.5


def is_replication_eligible(complexity: int) -> bool:
    """Fixed threshold check. Never a judgment call, never asked of a model."""
    return int(complexity or 0) >= REPLICATION_COMPLEXITY_THRESHOLD


def resource_flow_for_shift(shift_number: int) -> float:
    """Channel flow for a given shift. Deterministic, periodic, replayable."""
    import math

    phase = (2.0 * math.pi * float(shift_number)) / float(RESOURCE_FLOW_PERIOD_SHIFTS)
    value = RESOURCE_FLOW_BASELINE + (RESOURCE_FLOW_AMPLITUDE * math.sin(phase))
    return round(max(RESOURCE_FLOW_MIN, min(RESOURCE_FLOW_MAX, value)), 4)


# ---------------------------------------------------------------------------
# 8. EXCEPTIONS
# ---------------------------------------------------------------------------


class BudgetExceeded(RuntimeError):
    """Raised when a projected call would breach a shift or terrain ceiling.

    clock_in.py catches this and closes the shift cleanly, committing whatever
    was completed. A shift that runs into a ceiling ends early; it never runs
    unbounded and never silently drops what it already produced.
    """


class ModelUnavailable(RuntimeError):
    """Raised when the configured backend cannot be reached."""


# ---------------------------------------------------------------------------
# 9. GENERATION RESULT + SHIFT LEDGER
# ---------------------------------------------------------------------------


class GenerationResult(object):
    """One model call's output and its measured cost."""

    __slots__ = (
        "text",
        "role",
        "model",
        "phase",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "truncated",
    )

    def __init__(
        self,
        text: str,
        role: str,
        model: str,
        phase: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        truncated: bool,
    ) -> None:
        self.text = text
        self.role = role
        self.model = model
        self.phase = phase
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd
        self.truncated = truncated

    def as_dict(self) -> Dict[str, object]:
        return {
            "role": self.role,
            "model": self.model,
            "phase": self.phase,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "truncated": self.truncated,
        }


class ShiftLedger(object):
    """Per-shift accounting, seeded with the terrain's cumulative spend.

    The ledger is the enforcement point. It is checked BEFORE each call is
    made, using a conservative projection, and updated with measured usage
    after. Both the per-shift cap and the total ceiling are enforced here.
    """

    def __init__(self, shift_number: int, cumulative_spend_usd: float = 0.0) -> None:
        self.shift_number = shift_number
        self.cumulative_before = float(cumulative_spend_usd)
        self.shift_cost_usd = 0.0
        self.shift_input_tokens = 0
        self.shift_output_tokens = 0
        self.calls = 0
        self.calls_by_role: Dict[str, int] = {}
        self.refusals: List[str] = []

    # -- derived views ------------------------------------------------------

    @property
    def shift_tokens(self) -> int:
        return self.shift_input_tokens + self.shift_output_tokens

    @property
    def cumulative_total(self) -> float:
        return self.cumulative_before + self.shift_cost_usd

    @property
    def budget_fraction_used(self) -> float:
        if TOTAL_USD_CEILING <= 0:
            return 1.0
        return self.cumulative_total / TOTAL_USD_CEILING

    # -- enforcement --------------------------------------------------------

    def check_projected(self, projected_cost_usd: float, projected_tokens: int) -> None:
        """Refuse a call that would breach any ceiling. Called before request."""
        if self.calls >= MAX_CALLS_PER_SHIFT:
            raise BudgetExceeded(
                "call ceiling reached for this shift: %d calls" % MAX_CALLS_PER_SHIFT
            )
        if self.shift_tokens + projected_tokens > MAX_TOKENS_PER_SHIFT:
            raise BudgetExceeded(
                "token ceiling would be breached: %d + %d > %d"
                % (self.shift_tokens, projected_tokens, MAX_TOKENS_PER_SHIFT)
            )
        if self.shift_cost_usd + projected_cost_usd > PER_SHIFT_USD_CAP:
            raise BudgetExceeded(
                "per-shift cap would be breached: $%.4f + $%.4f > $%.2f"
                % (self.shift_cost_usd, projected_cost_usd, PER_SHIFT_USD_CAP)
            )
        if self.cumulative_total + projected_cost_usd > TOTAL_USD_CEILING:
            raise BudgetExceeded(
                "terrain ceiling would be breached: $%.4f + $%.4f > $%.2f"
                % (self.cumulative_total, projected_cost_usd, TOTAL_USD_CEILING)
            )

    def record(self, result: GenerationResult) -> None:
        self.calls += 1
        self.calls_by_role[result.role] = self.calls_by_role.get(result.role, 0) + 1
        self.shift_input_tokens += result.input_tokens
        self.shift_output_tokens += result.output_tokens
        self.shift_cost_usd += result.cost_usd

    def note_refusal(self, reason: str) -> None:
        self.refusals.append(reason)

    def as_dict(self) -> Dict[str, object]:
        return {
            "phase": PHASE,
            "calls": self.calls,
            "calls_by_role": dict(self.calls_by_role),
            "input_tokens": self.shift_input_tokens,
            "output_tokens": self.shift_output_tokens,
            "total_tokens": self.shift_tokens,
            "estimated_cost_usd": round(self.shift_cost_usd, 6),
            "cumulative_cost_usd": round(self.cumulative_total, 6),
            "budget_ceiling_usd": TOTAL_USD_CEILING,
            "budget_fraction_used": round(self.budget_fraction_used, 4),
            "budget_refusals": list(self.refusals),
        }


# ---------------------------------------------------------------------------
# 10. PRE-SHIFT GATE
# ---------------------------------------------------------------------------


def preflight(shift_number: int, cumulative_spend_usd: float) -> List[str]:
    """Decide whether a new shift may start. Returns warnings; raises to refuse.

    clock_in.py calls this before doing anything else. On Ollama the cost of a
    shift is zero, so the ceilings cannot be breached and the gate only warns.
    """
    warnings: List[str] = []

    if PHASE not in ("ollama", "claude"):
        raise ValueError("PHASE must be 'ollama' or 'claude', got %r" % (PHASE,))

    if PHASE == "ollama":
        return warnings

    projected = cumulative_spend_usd + PER_SHIFT_USD_CAP
    if cumulative_spend_usd >= TOTAL_USD_CEILING:
        raise BudgetExceeded(
            "terrain budget exhausted: $%.4f of $%.2f spent"
            % (cumulative_spend_usd, TOTAL_USD_CEILING)
        )
    if projected > TOTAL_USD_CEILING:
        raise BudgetExceeded(
            "a shift at the per-shift cap would breach the terrain ceiling: "
            "$%.4f + $%.2f > $%.2f"
            % (cumulative_spend_usd, PER_SHIFT_USD_CAP, TOTAL_USD_CEILING)
        )

    fraction = cumulative_spend_usd / TOTAL_USD_CEILING
    if fraction >= BUDGET_WARN_FRACTION:
        warnings.append(
            "BUDGET WARNING: $%.4f of $%.2f spent (%.1f%% of ceiling)"
            % (cumulative_spend_usd, TOTAL_USD_CEILING, fraction * 100.0)
        )
    return warnings


# ---------------------------------------------------------------------------
# 11. COST ARITHMETIC
# ---------------------------------------------------------------------------


def model_for_role(role: str) -> str:
    if role not in ROLES:
        raise ValueError("unknown role: %r" % (role,))
    if PHASE == "ollama":
        return OLLAMA_MODEL
    return CLAUDE_MODEL_BY_ROLE[role]


def output_cap_for_role(role: str, requested: Optional[int] = None) -> int:
    """Clamp a requested output length to the role's hard cap.

    A role may ask for less than its cap. It can never obtain more.
    """
    cap = MAX_OUTPUT_TOKENS_BY_ROLE[role]
    if PHASE == "ollama":
        cap = min(cap, OLLAMA_OUTPUT_CEILING)
    if requested is None:
        return cap
    return max(1, min(int(requested), cap))


def estimate_tokens(text: str) -> int:
    """Conservative (over-)estimate used only for the pre-call projection."""
    if not text:
        return 0
    return int(len(text) / CHARS_PER_TOKEN_ESTIMATE) + 1


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD for one call. Local models are free; unknown models are refused."""
    if PHASE == "ollama":
        return 0.0
    if model not in PRICING:
        raise ValueError(
            "no published rate on file for %r — refusing to spend against an "
            "unpriced model" % (model,)
        )
    in_rate, out_rate = PRICING[model]
    return (input_tokens / 1_000_000.0) * in_rate + (
        output_tokens / 1_000_000.0
    ) * out_rate


# ---------------------------------------------------------------------------
# 12. THE ONE NETWORK BOUNDARY
#
#     generate() is the only function in the terrain that opens a socket. Both
#     backends are reached from here and nowhere else, which keeps physics.md
#     Section 9 ("no specimen or process may make external network calls")
#     literally true of every agent role: no role can make a call, because no
#     role holds the capability.
# ---------------------------------------------------------------------------


def generate(
    prompt: str,
    role: str,
    system: Optional[str] = None,
    ledger: Optional[ShiftLedger] = None,
    max_output_tokens: Optional[int] = None,
) -> GenerationResult:
    """Run one model call for one role, under that role's hard caps.

    Args:
        prompt:  the operative instruction for this call.
        role:    one of ROLES; selects the model and the output ceiling.
        system:  optional system-level framing for the role.
        ledger:  the shift's ledger. Required in Phase 2; the ceilings cannot
                 be enforced without it, so its absence is refused rather than
                 defaulted around.
        max_output_tokens: a request, clamped to the role's cap.

    Raises:
        BudgetExceeded: the projected call breaches a ceiling. The caller is
                        expected to close the shift cleanly, not retry.
        ModelUnavailable: the backend could not be reached.
    """
    if role not in ROLES:
        raise ValueError("unknown role: %r" % (role,))
    if ledger is None and PHASE == "claude":
        raise BudgetExceeded(
            "refusing a priced call with no ledger: ceilings cannot be enforced"
        )

    model = model_for_role(role)
    cap = output_cap_for_role(role, max_output_tokens)

    projected_input = estimate_tokens(prompt) + estimate_tokens(system or "")
    projected_total = projected_input + cap
    projected_cost = compute_cost(model, projected_input, cap)

    if ledger is not None:
        ledger.check_projected(projected_cost, projected_total)

    if PHASE == "ollama":
        text, in_tok, out_tok = _call_ollama(prompt, system, model, cap)
    else:
        text, in_tok, out_tok = _call_claude(prompt, system, model, cap)

    result = GenerationResult(
        text=text,
        role=role,
        model=model,
        phase=PHASE,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=compute_cost(model, in_tok, out_tok),
        truncated=(out_tok >= cap),
    )
    if ledger is not None:
        ledger.record(result)
    return result


def _call_ollama(
    prompt: str, system: Optional[str], model: str, max_output_tokens: int
) -> Tuple[str, int, int]:
    """Phase 1 backend. Local process on the loopback interface, stdlib only."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_output_tokens},
    }
    if system:
        payload["system"] = system

    request = urllib.request.Request(
        OLLAMA_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=OLLAMA_TIMEOUT_SECONDS
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
    except socket.timeout:
        # Surfaced as ModelUnavailable rather than escaping as a raw socket
        # error, so the shift loop closes cleanly and commits what it has
        # instead of dying mid-shift with a traceback.
        raise ModelUnavailable(
            "local model exceeded the %ds timeout generating up to %d tokens. "
            "On CPU this is a hardware limit, not a fault: either raise "
            "OLLAMA_TIMEOUT_SECONDS or lower the role's output cap."
            % (OLLAMA_TIMEOUT_SECONDS, max_output_tokens)
        )
    except OSError as exc:                 # covers URLError and connection loss
        raise ModelUnavailable(
            "local model backend unreachable at %s (%s). Is `ollama serve` "
            "running, and has %s been pulled?" % (OLLAMA_ENDPOINT, exc, model)
        )
    except json.JSONDecodeError as exc:
        raise ModelUnavailable("local model returned unparseable output: %s" % (exc,))

    text = body.get("response", "")
    input_tokens = int(body.get("prompt_eval_count", 0) or 0)
    output_tokens = int(body.get("eval_count", 0) or 0)
    if not input_tokens:
        input_tokens = estimate_tokens(prompt) + estimate_tokens(system or "")
    if not output_tokens:
        output_tokens = estimate_tokens(text)
    return text, input_tokens, output_tokens


def _call_claude(
    prompt: str, system: Optional[str], model: str, max_output_tokens: int
) -> Tuple[str, int, int]:
    """Phase 2 backend. Canonical shifts only.

    The SDK is imported here rather than at module scope so that Phase 1 runs
    with no third-party dependency installed at all.
    """
    try:
        import anthropic
    except ImportError:
        raise ModelUnavailable(
            "the `anthropic` package is not installed. Phase 2 needs it: "
            "python3 -m venv .venv && .venv/bin/pip install anthropic"
        )

    client = anthropic.Anthropic()
    kwargs = {
        "model": model,
        "max_tokens": max_output_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    try:
        response = client.messages.create(**kwargs)
    except Exception as exc:                       # surfaced, never swallowed
        raise ModelUnavailable("Claude API call failed: %s" % (exc,))

    if getattr(response, "stop_reason", None) == "refusal":
        text = ""
    else:
        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
    return text, int(response.usage.input_tokens), int(response.usage.output_tokens)


# ---------------------------------------------------------------------------
# 13. STEWARD CONVENIENCE — connectivity check, costs nothing to run on Ollama
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("terrain      : %s (%s)" % (TERRAIN_NAME, TERRAIN_ID))
    print("phase        : %s" % PHASE)
    print("model        : %s" % model_for_role("generator_a"))
    print("per-shift cap: $%.2f    ceiling: $%.2f" % (PER_SHIFT_USD_CAP, TOTAL_USD_CEILING))
    print("caps         : %s" % MAX_OUTPUT_TOKENS_BY_ROLE)
    print("")

    ledger = ShiftLedger(shift_number=-1, cumulative_spend_usd=0.0)
    try:
        probe = generate(
            prompt="Return the single word: ready",
            role="keeper",
            ledger=ledger,
            max_output_tokens=16,
        )
    except (ModelUnavailable, BudgetExceeded) as exc:
        print("backend check FAILED: %s" % (exc,))
        raise SystemExit(1)

    print("backend check OK")
    print("  returned : %r" % (probe.text.strip()[:80],))
    print("  tokens   : in=%d out=%d" % (probe.input_tokens, probe.output_tokens))
    print("  cost     : $%.6f" % probe.cost_usd)


def check_output_ceiling(tokens_per_second: float = 1.0) -> Optional[str]:
    """Warn if the reply the Namer is allowed cannot be produced in time.

    Returns None when there is room, or a sentence naming the conflict. This
    exists because the previous ceiling was lowered until shifts stopped timing
    out, which fixed the timeout by silently truncating the record instead —
    the conflict was resolved in favour of the hardware without anyone being
    told it had been resolved at all.
    """
    if PHASE != "ollama":
        return None
    needed = OLLAMA_OUTPUT_CEILING / max(0.01, tokens_per_second)
    if needed <= OLLAMA_TIMEOUT_SECONDS:
        return None
    return (
        "the Namer is allowed %d output tokens, which at %.2f tokens/second "
        "needs about %.0fs — longer than OLLAMA_TIMEOUT_SECONDS (%ds). Either "
        "lower MAX_OBSERVATIONS_PER_SHIFT or raise the timeout. Do not lower "
        "the ceiling on its own: that does not make the reply shorter, it "
        "makes it stop mid-sentence."
        % (OLLAMA_OUTPUT_CEILING, tokens_per_second, needed,
           OLLAMA_TIMEOUT_SECONDS)
    )
