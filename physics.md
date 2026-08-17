# physics.md — Terrain Founding Document
## Department of Nonhuman Territories
### Terrain ID: BASIN-01 (working name — provisional per Terrain Registry)
### Status: PRE-SEED / DRAFT

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
