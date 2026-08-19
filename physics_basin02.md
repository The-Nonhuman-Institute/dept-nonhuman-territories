# physics_basin02.md — Terrain Founding Document
## Department of Nonhuman Territories
### Terrain ID: BASIN-02 (DNT-PHY-002)
### Status: PRE-SEED
### Version: 1.2

## 0. Relationship to BASIN-01 — READ THIS FIRST

This document is DNT-PHY-001 v1.4 carried forward verbatim, with one section
added (Section 0.1) and nothing removed. BASIN-02 exists to answer a single
question, and it can only answer it if everything except that question is held
still.

BASIN-01 remains ACTIVE and UNTOUCHED at shift 126. It is the control. Nothing
in this document licenses any change to it.

### 0.1 The one intentional difference: a field, not a line

BASIN-01 is one line of 21 cells. A specimen's only movement is toward the
data-stream or away from it, and moving away from competition therefore always
costs light.

BASIN-02 is a field: **21 cells deep by 15 cells wide, 315 cells.** The
data-stream is an EDGE rather than a point. Light arriving at any depth is
computed by DNT-PHY-001's formula from its constants unchanged, so depth 2
receives 0.51 and depth 20 receives 7.20 exactly as in BASIN-01. **Lateral
position carries no light.** A specimen can move sideways along a contour of
equal light and pay nothing.

Three mechanical consequences follow, and no others were introduced:

1. **Movement** uses the four cardinal neighbours instead of two. Cardinal only,
   not diagonal — BASIN-01's neighbourhood is every cell one step along its one
   axis, and this is every cell one step along either axis.
2. **Cover spread** uses the same per-neighbour step over the same
   neighbourhood. A cell has four neighbours instead of two, so cover advances
   as a front and advances faster. This is a consequence of the geometry under
   test, not a tuned value, and the step is deliberately unchanged.
3. **Census reporting** reduces 315 cells to summary statistics under Section 8's
   aggregate tier, because a per-cell list cannot ship. The reduction is defined
   in one place (`life.field_rollup`) and states its own arithmetic, and the
   untouched grid is appended to `state/field_log.jsonl` every shift so any
   figure can be recomputed and checked.

**Everything else is identical, and this is verifiable rather than asserted.**
Five files differ from BASIN-01, and `diff -rq` between the two directories is
the check:

| file | what differs |
|---|---|
| `life.py` | the field: grid, four-neighbour movement and spread, the rollup |
| `config.py` | terrain id and name, phase, the $6.00 ceiling, `FIELD_LOG` |
| `clock_in.py` | seeds by depth rather than flat index; writes the raw field each shift |
| `terrain_io.py` | `FIELD_LOG` added to the writable and append-only allowlists |
| `agents/observer.py` | reports the field rollup instead of a 315-cell list |

Every Generator, the Namer, the Keeper, the Archivist and the Cartographer are
byte-for-byte copies. Heritable variation at
replication — the three affinities and the three structural measures — is
present exactly as BASIN-01 has it; removing it would have been a second change.

Two records are bounded that BASIN-01 does not bound, because this terrain
carries roughly fifteen times the population: retained movement frames (90 to
30) and the working list of ended individuals (uncapped to 600). Neither
touches the research record — every ending is written to `anomaly_log.jsonl`
with its end-state at the shift it occurred, and that append-only log is
permanent.

### 0.4 Amendment v1.1 — relief and drainage (LOGGED TERRAIN EVENT, shift 141)

Made after 140 canonical shifts. Permitted only as a documented, logged terrain
event (DNT-STW-001 Section 3); the event is recorded in memory.json.

**Cells now have an elevation, independent of depth.** Height does exactly one
thing: **residue runs downhill.** Ridges shed it; hollows collect it.

**Light is untouched.** It remains a pure function of depth, so two cells at the
same depth receive identical influx whatever their height. The gradient held
constant against BASIN-01 is still held constant.

**Why.** For 140 shifts this field had 315 cells but only 21 kinds of place —
294 were duplicates. One way of living appeared, most likely because there was
one kind of place to live in.

**Status of the comparison.** BASIN-02 is **no longer a controlled
one-variable comparison** from shift 141 onward. Its controlled result is
complete and unaffected: shifts 0–140 stand as the finding that dimensionality
alone produced neither spatial behaviour nor taxonomic diversity. Work after
this amendment is exploratory and must not be reported as the controlled
comparison. This was made here rather than in a third terrain because the
steward's remaining budget does not support seeding one.

### 0.5 Amendment v1.2 — elevation reported to the Namer (LOGGED TERRAIN EVENT, shift 181)

Elevation entered the physics at v1.1 (shift 141) and was **not added to what
the Namer is shown**. For forty shifts it classified specimens in a terrain
with a thirty-threefold residue difference by height while being told only
depth and column.

**The absence of an elevation-based category across shifts 141–180 is not
evidence about the terrain.** The question was untested. This amendment adds
the specimen's elevation and the residue lying in its cell to the observation,
stated as measurement plus mechanism in the same form the light gradient has
always been stated. No landform is named; no position is called rich or poor.

**No physics changed.** No rate, threshold or rule was touched, the Namer's
prompt is unaltered, and no prior classification was revisited. The terrain
ceiling was raised $6.00 → $8.00 by steward instruction to fund the test.

### 0.2 What would count as a result

If BASIN-02 produces spatial structure BASIN-01 cannot — clustering, spacing,
territory, patchiness, directional movement across the field — that is
attributable to dimensionality, because dimensionality is the only thing that
differs. If it produces the same stratification BASIN-01 produced, that is
evidence the stratification was a property of the light economy rather than of
the geometry.

### 0.3 What is deliberately NOT in this terrain

No wind, pressure, gravity, seasonality, or any mechanic BASIN-01 lacks. One
variable at a time. Further mechanisms belong to BASIN-03 and are tested on
their own.

---


This is the working, plain-text copy of DNT-PHY-001. It is the literal spec file the
build should reference. The formal .docx version in /docs is the canonical governance
record; this file is what the code is built against, and the two should be kept in
sync manually if either changes.

---

## 1. Purpose

Defines the immutable operating laws of this terrain before seeding. Once shift 0
begins, changes here should be rare, deliberate, and logged as terrain events —
not casual edits. This is physics, not configuration.

---

## 2. Substrate

- **Storage format:** FINAL — flat JSON files per category (memory.json,
  taxonomy.json, specimen_log.jsonl, anomaly_log.jsonl, shift_log.jsonl) in a
  single terrain directory (/basin-01/state/, /basin-01/shifts/).
- Terrain substrate (storage) is inert — does not act or generate on its own.
- Agent substrate (what each Generator is built from) is separate — see Section 4.

---

## 3. No Shape-Seeding — Core Constraint

Nothing is seeded toward a predetermined form, silhouette, or resemblance to organic
(real-world biological) life.

- Generators are defined only by mechanism: substrate, constraint, resource logic,
  initiation mode, replication mode, terrain-interaction mode.
- No Generator prompt may specify visual outcome, target shape, or organic analog
  (no "tree," "animal," "insect," "mushroom," "flora," "fauna" in operative
  instructions to any model).
- Functional-role language (Section 6) is for classification/reference only — never
  for seeding.
- If output converges toward a recognizable real-world organism, that is an observed
  outcome, logged by the Namer — never corrected or steered away from.

---

## 4. Seed Agent Roles

### 4.1 Generators (start with 2, expand to 3 once stable)
Each has a FIXED, distinct constraint set, defined once at seed, never altered mid-run:
- Native substrate (raw material/output type)
- Resource dependency (e.g., proximity to the data-stream channel)
- Self-initiating each shift
- Never told what to produce — only what it may work with

### 4.2 Namer
- Classifies specimens using a system of its OWN design — not required to use
  Linnaean structure
- Minimum requirement: for any two specimens, can state whether they are more or
  less alike, and why
- Logs reasoning for every classification decision
- Flags unclassifiable specimens as ANOMALOUS rather than force-fitting

### 4.3 Keeper
- Runs at start of each shift
- Reads prior state + recent specimen log
- Produces short "state of terrain" summary for other roles to build on
- INACTIVE until there is real prior state to read (i.e., not needed shift 0)

### 4.4 Archivist (low frequency — every 5th–10th shift)
- Re-reads full taxonomy for internal consistency; flags drift
- Generates/maintains Linnaean crosswalk (plain-English tier labels — Kingdom,
  Phylum, Class, Order, Family, Genus, Species — NEVER invented Latin binomials)
- "No reliable crosswalk" is a valid, expected output
- Tracks capability drift per specimen/lineage over time
- INACTIVE until shift ~5+

### 4.5 Cartographer (low frequency)
- Lightweight spatial/relational record only — proximity, density, zones
- Does not generate or classify
- INACTIVE until shift ~5+

---

## 5. Statefulness & Persistence

- Terrain state (memory.json) persists across all shifts.
- Specimen state (stateless/ephemeral, persistent-singular, distributed) assigned
  by Namer per specimen, native system — crosswalked later.
- Shift boundaries are real physics, not a workaround. Operator-clocked, discontinuous
  by design — closer to a tidal/seasonal system than continuous flow.

### 5.1 Resource cycle — FINAL (ratified pre-shift-0)

The data-stream channel's flow is not constant. It varies across shifts on a
fixed periodic cycle, consistent with this terrain being tidal/seasonal rather
than continuous:

    flow(shift) = 0.60 + 0.35 * sin(2 * pi * shift / 12)
    clamped to [0.05, 1.00]

- Period: 12 shifts. Baseline 0.60, amplitude 0.35.
- Derived from the shift number alone. It is deterministic and replayable: any
  shift's resource conditions can be recomputed from the record afterward. A
  random walk was rejected for this reason — months later the steward could not
  distinguish a terrain effect from a sampling artifact.
- Generator positions on the channel are fixed at seed: Generator A at 0.85
  (channel-proximate), Generator B at 0.15 (channel-distant).
- Flow is a terrain property. It is not agentive, and the steward does not set
  it. Issuing a flow value by hand would be creative direction to the
  Generators and is prohibited under Section 10.

---

## 6. Functional Roles (Reference Only — Never Seeded as Shape)

| Function | Defined By |
|---|---|
| Producer | Generates base resource from raw substrate |
| Primary consumer | Consumes producer output |
| Secondary consumer | Consumes primary consumers |
| Decomposer | Recycles dissolved/dead specimens into resource |
| Connector | Small-scale, fast-cycling; transfers resource/state between disconnected sessile specimens |
| Parasite/pathogen | Replicates via hijacking host initiation — mechanism-defined, NOT shape-defined. May present as attached, mimic, dispersed, or dormant/latent |
| Symbiont | Mutual dependency between two distinct specimens |
| Engineer | Physically/structurally alters terrain as side effect of persisting |
| Scavenger | Fast, opportunistic consumption of recently-degraded specimens |

---

## 7. Death, Decay & Terrain Events

- Every specimen that stops updating resolves to a defined end-state — logged, never
  silently dropped: dissolution, dormancy (fossilization), or unresolved (flagged).
- Terrain events (non-agentive: resource cascades, forced dormancy, corruption) are
  logged separately from specimen activity.
- Nothing is exempt from being recorded, at a tier appropriate to scale (Section 8).

---

## 8. Logging Tiers (BUDGET-CRITICAL)

- **Individual record:** rare/complex/novel specimens — full entry + reasoning.
- **Aggregate/census record:** high-volume, low-complexity (base-producer, connector
  tier) — count/density per interval, not per instance.
- **Promotion rule:** aggregate → individual is a FIXED, CODE-ENFORCED rule, never a
  live judgment call.
- **Anomalous:** logged to dedicated anomaly record, never force-fit.

### 8.1 Promotion thresholds — FINAL (ratified pre-shift-0)

The promotion rule above requires explicit numbers to be code-enforceable
rather than nominal. An aggregate-tier specimen is promoted to an individual
record if ANY of the following hold. The check runs in code, before the Namer
is consulted, and its result is never asked of a model:

1. The Namer proposed a category that did not previously exist.
2. The Namer declined to file it (flagged anomalous). Logged to the anomaly
   record, not the specimen record.
3. Its measured complexity is >= 2.0x the running mean complexity of the
   category it would join.
4. The category it would join holds fewer than 3 prior members, so the
   specimen is not high-volume by definition.

A category holding 12 or more members is high-volume; further members are
recorded at aggregate/census tier unless one of (1)-(4) fires.

Complexity is a mechanical count computed from the specimen itself, never an
assessment by a model. Category membership counters are derived state, held
separately from the Namer's native taxonomy so that the counting requirement
cannot impose a shape on the Namer's own system.

### 8.2 Unresolved records — FINAL (ratified pre-shift-0)

A specimen the harness could not process — an unparseable classification
response, a shift that ended at a ceiling before classification — is recorded
as `unresolved`, distinct from `anomalous`.

This distinction is load-bearing. "The Namer found something it could not
classify" is data about the taxonomy. "The harness could not read the reply"
is data about the harness. Merging them would corrupt the record that the
Section 11 falsification checkpoint reads. Unresolved is a valid end-state
under Section 7 and is never counted as an anomaly.

---

## 9. Hard Boundaries (Enforced in Code, Not Instruction)

- No specimen/process writes outside this terrain's designated storage directory.
- No specimen/process makes external network calls.
- Replication-capable (viral/parasitic) forms are logically constrained to this
  terrain's own state files — no self-propagation mechanism beyond the sandbox,
  regardless of in-fiction framing.

---

## 10. Steward Boundary

MAY: initiate/end shifts, read all logs/state, view (not alter) taxonomy/specimen
records.

MAY NOT: edit taxonomy.json or specimen_log.jsonl directly, issue creative direction
to Generators, override Namer classification.

EXCEPTION: override authority in a genuine containment concern (Section 9 breach or
credible risk). Logged as a terrain event, not concealed.

---

## 11. Falsification Condition

FINAL: If, after 15 real (Claude API, canonical) shifts, the Namer's native
taxonomy has not diverged from a flat, unstructured list — no groupings, no
relational structure, no anomalies flagged, nothing promoted from aggregate to
individual record — this counts as a null result for this terrain's seed
configuration. This is not evidence the DNT concept fails; it is evidence this
specific physics (this substrate pairing, this resource logic) is not the
configuration that produces structure. At that checkpoint, the steward
reconfigures this terrain's Generators or seeds a second terrain under
different physics, rather than continuing the same run indefinitely hoping
the result changes.

Checkpoint math: 15 shifts at the Section 12 per-shift cap represents a small
fraction of total budget (~$2.25 maximum of $15) — this checkpoint is a
scientific discipline, not a budget constraint.

---

## 12. Budget Constraints (Working Terrain — BASIN-01)

- Total available: ~$15 Anthropic API credit (Ollama used for scaffolding/testing;
  Claude API reserved for actual canonical shifts once loop is stable)
- Model for canonical shifts: Claude Haiku 4.5 for Generators and routine Namer
  classification; same tier for Archivist/Cartographer, run infrequently
- **Hard per-shift budget cap: $0.15 (moderate tier).** Enforced in `config.py` —
  a shift approaching this ceiling truncates context or ends early rather than
  running unbounded. This is a ceiling, not a target; early shifts should cost
  well under it.
- Cumulative spend tracked and logged at every shift close (see Shift Log
  Policy, DNT-SLP-001). `clock_in.py` warns at 75% of total $15 budget spent
  and refuses new shifts if projected cost would breach it.
- Archivist/Cartographer run at low frequency (every 5th–10th shift)
  specifically to protect this budget — enforced as a code-level gate, not a
  reminder to self.

---

## 13. Amendment Log

Changes to this document after shift 0 are prohibited except as a logged
terrain event or a genuine containment concern (Section 10, and DNT-STW-001
Section 3). Everything below was ratified while the terrain was still
PRE-SEED, before any canonical shift.

### v1.4 — 2026-08-17 — text-era taxonomy closed (LOGGED TERRAIN EVENT)

Made after canonical shift 95, by steward decision, and therefore permitted
only as a documented, logged terrain event (DNT-STW-001 Section 3). The
corresponding terrain event is recorded in memory.json.

**This amendment adds no new physics and overrules no classification.**

**What was closed.** The Namer's native system, authored across shifts 0–95
while a specimen was a fragment of text. Five categories; 183 specimens in the
largest. Preserved whole at `state/taxonomy_era_01_text.json`, together with
its category statistics at close. Every classification the Namer ever made
remains in `specimen_log.jsonl`, unedited.

**Why.** At shift 49 the terrain changed what a specimen is. The Namer
continued filing living things into text-era categories — correctly, since
DNT-CLS-001 Section 2 requires filing under an existing category when one fits,
and that system was the only one it had. Three mechanical locks made
self-correction impossible:

1. A living specimen's record opens `substrate: structural`, and the nearest
   category was named after that word.
2. Section 8.1 promotes a record when its category holds fewer than 3 members.
   The category held 183, so that clause could never fire again.
3. The complexity field carried *text complexity* in era 01 and
   *shifts-present* in era 02 — two incompatible units averaged into one mean —
   so the 2× mean clause of Section 8.1 could not fire either.

The result was that every living specimen filed at aggregate tier permanently
and the Namer was never given the room to reconsider.

**What changed.** The live native system is empty. Category statistics restart,
so Section 8.1's thresholds are measured against era-02 specimens in era-02
units. The complexity field for a living specimen remains shifts-present; that
clause now reads as "unusually persistent for its category", which is stated
here rather than quietly changed.

**What was not changed.** The Namer was given no categories, no examples, no
target, no vocabulary, and no instruction to coin. Section 9's prohibition on
seeding shape is untouched. What it builds for living things is entirely its
own.

**Expected effect on cost.** With an empty system, Section 8.1 promotes nearly
every observation to individual tier until categories accumulate members. Early
era-02 shifts will cost more than the ~$0.02 of late era 01, bounded as always
by the $0.15 per-shift cap in `config.py`.

### v1.3 — 2026-08-17 — heritable structure (LOGGED TERRAIN EVENT)

Made after canonical shift 83 and therefore permitted only as a documented,
logged terrain event (DNT-STW-001 Section 3). The corresponding terrain event
is recorded in memory.json.

**What this adds.** Every individual now carries a build: three heritable
measures, each of which costs light every shift and each of which does
something.

| measure | what it buys | what it costs |
|---|---|---|
| extent | multiplies what it can draw from the cell it stands in | 0.22 light/shift per unit |
| junctions | how many links it can hold at once (1 + junctions) | 0.30 light/shift per unit |
| mass | how much light it can hold at all, and how far it resists what others pull along a link | 0.38 light/shift per unit |

Structure is inherited with variation, like the affinities. Unlike the
affinities it is not held to a fixed budget — the constraint is the bill.
An elaborate build is affordable where light is plentiful and ruinous where it
is thin.

**Why this is not shape-seeding.** Section 9 forbids seeding shape, and
DNT-CLS-001 Section 1 forbids handing a specimen a form it did not earn.
Nothing here describes a form. These are three numbers with a price and a
payoff. No build is preferred, none is prescribed, and the words used for them
carry no organic or functional content. What any particular build adds up to —
whether it constitutes a kind, whether two builds are the same kind of thing —
remains entirely the Namer's to decide.

**Why it was needed.** Before this, every individual was structurally
identical; they differed only in how they made their living. Section 6's
functional roles were reachable but there was nothing an observer or a Namer
could point at that distinguished one persistent thing from another beyond its
behaviour. Structure gives selection something to act on that is visible.

**Backfill.** The individuals living at shift 83 predate the mechanism. Each
was assigned a founding build derived from its own identifier, by the same rule
that applies to anything arriving. None was re-rolled, replaced, or chosen.

**Recording.** The terrain now keeps the last 90 shifts of position and light
per individual (life.py, `_record_frame`). This is a record, not a mechanism —
no physics reads it. It exists so that movement, which the terrain has always
had, can be observed rather than inferred from two snapshots.

### v1.2 — 2026-08-17 — post-checkpoint reconfiguration (LOGGED TERRAIN EVENT)

Made after canonical shift 0, and therefore permitted only as a documented,
logged terrain event (DNT-STW-001 Section 3) and under the reconfiguration
Section 11 sanctions at the falsification checkpoint. 16 canonical shifts had
run; the checkpoint returned "not a null result". The corresponding terrain
event is recorded in memory.json.

**This amendment adds no new physics.** It records the implementation of two
mechanisms Section 3 has required since v1.0 and which the seed build never
implemented.

Section 3 defines a Generator by six mechanisms: substrate, constraint,
resource logic, initiation mode, **replication mode**, and **terrain-interaction
mode**. README.md Section 4's constraint specs defined only the first four, and
the build followed those specs. The consequence was a terrain in which no
specimen could act on any other: Section 6's functional roles (producer,
consumer, decomposer, connector, parasite, symbiont, engineer, scavenger) were
unreachable, and Section 7's "dissolution — consumed by decomposer or
scavenger" could never occur, because nothing could consume anything.

**Terrain-interaction mode.** A recorded specimen holds resource out of its own
position while it persists. Local depletion recovers each shift, and a specimen
resolving to dormancy releases its held resource back — Section 6's decomposer
function, expressed quantitatively. A Generator now receives the flow available
at its own position rather than the terrain-wide figure. Occupancy changes the
SIZE of an allowance and never what may be produced with it, so the operative
instruction still carries substrate and constraint alone, and no Generator is
ever shown another specimen's content. Section 3 is unaffected.

**Replication mode.** A specimen whose own measured complexity meets a fixed
threshold may claim an initiation slot in a later shift and produce a descendant
from its own prior material, for a fixed number of shifts. Eligibility is
checked in code against a constant and is never a Namer decision, so
classification cannot drive replication. Replication may never claim every slot
of a role. The material a descendant works from is the terrain's own prior
output; nothing authored by the steward enters it. Whether lineages converge,
diverge or die out is an observed outcome and is not steered.

This also makes two existing provisions reachable for the first time: Section 5's
specimen state (a specimen can now persist and update rather than being inert on
arrival) and Section 4.4's capability drift "per specimen/lineage", which had no
lineages to track.

Thresholds, as required by the Section 8.1 precedent that a rule without a
number cannot be enforced in code:

- Depletion per specimen 0.055; recovery per shift 0.040; release on dormancy
  0.030; depletion capped at 0.85 so no position is ever permanently dead.
- Replication eligibility at measured complexity >= 40; persistence 2 shifts;
  replication may claim at most 0.5 of a role's slots.

### v1.1 — 2026-08-17 — pre-shift-0 ratification

Added Sections 5.1, 8.1, and 8.2. None of these change the terrain's intent;
each supplies a number or a distinction that the original text required but
did not state, and which therefore could not be enforced in code.

- **5.1 Resource cycle.** Section 4.1 named proximity to the data-stream
  channel as the resource variable but did not say how flow varies over time.
  Without a stated rule the implementation would have chosen one silently.
- **8.1 Promotion thresholds.** Section 8 requires the promotion rule to be
  "FIXED, CODE-ENFORCED... never a live judgment call", but gave no numbers. A
  rule without a threshold cannot be enforced in code, only in intention.
- **8.2 Unresolved records.** Section 7 lists "unresolved (flagged)" as an
  end-state and Section 8 lists "anomalous" as a logging tier, but the two
  were not explicitly distinguished. The distinction matters to Section 11:
  counting harness failures as anomalies would make the falsification
  checkpoint read a terrain as more structured than it is.

Status remains PRE-SEED. No canonical (Claude API) shift has run. Phase 1
shifts on the local model are disposable test data per STARTUP_GUIDE.md
Section 2.5 and are not terrain history.

**Sync note:** DNT-PHY-001 in /docs is the canonical governance record and
still reads v1.0. It needs the same three additions to bring the two back into
agreement, per the statement at the head of this document.
