# DNT — Terrain BASIN-01 — Build Spec
## Kickoff brief for Claude Code

This is the working instruction file for building the first DNT terrain. It sits
alongside `/docs` (the six formal governance documents — Charter, Stewardship
Protocol, Classification Standard, Terrain Registry, Shift Log Policy, and this
file's canonical sibling, the Physics document) and `/physics.md` (the plain-text
working spec Claude Code should treat as the literal source of truth for terrain
rules).

**Read `/docs` for context on why these rules exist. Read `physics.md` for what to
actually build. This file is how.**

---

## 1. Project Structure to Build

```
/dnt-project/
  docs/                       — six formal governance docs (already exists, read-only)
  physics.md                  — terrain law (already exists, read-only during runtime)
  README.md                   — this file
  /basin-01/
    agents/
      namer.py
      generator_a.py
      generator_b.py
      keeper.py                — build, but inactive until shift ~2+
      archivist.py              — build, but inactive until shift ~5+
      cartographer.py            — build, but inactive until shift ~5+
    state/
      memory.json               — persistent terrain state
      taxonomy.json              — Namer's native classification (living structure)
      specimen_log.jsonl         — append-only, individual + aggregate records
      anomaly_log.jsonl          — unclassifiable specimens/events
    shifts/
      shift_log.jsonl            — append-only, one entry per shift (see Shift Log Policy)
    clock_in.py                  — entry point script; starts a shift
    config.py                    — model selection, token caps, budget ceiling
```

---

## 2. Build Order (do not skip ahead)

1. `config.py` — model abstraction (`generate(prompt, role)`), swappable between
   Ollama and Claude API via one setting. Hard token/call caps enforced here, not
   left to agent discretion.
2. `state/` file scaffolding — empty but valid JSON structures matching the schemas
   below.
3. `generator_a.py`, `generator_b.py` — see Section 4 for constraint specs. No shape
   language anywhere in these files, including comments and variable names — keep
   even internal naming mechanism-based (e.g. `substrate_output`, not `plant_output`).
4. `namer.py` — see Section 5.
5. `clock_in.py` — the actual shift loop: load state → run active roles → write
   state → log shift → exit. Must run cleanly end-to-end on Ollama before any Claude
   API credit is spent.
6. Only after step 5 works reliably: `keeper.py`, then later `archivist.py` and
   `cartographer.py`.

**Do not build all six roles simultaneously.** Namer + 2 Generators + clock_in
running cleanly is a complete, valid first milestone.

---

## 3. Model Configuration

- **Phase 1 (scaffolding/testing):** Ollama, local model TBD by steward. Used to
  debug the loop, storage, and logging at zero cost.
- **Phase 2 (canonical runs):** Claude API.
  - Generators → Claude Haiku 4.5 (cost-efficient; volume of cycles matters more
    than depth per call for this role)
  - Namer → strongest model the budget allows (classification quality matters more
    than call volume)
  - Archivist/Cartographer → same tier as Namer, run infrequently
- Swapping phases should be a one-line config change, not a rewrite. Build the
  `generate()` abstraction to make this true from the start.
- **Budget ceiling: $15 total for Phase 2.** `config.py` should track cumulative
  spend and refuse to start a new shift if projected cost would exceed the ceiling.

---

## 4. Generator Constraint Specs

FINAL for seed. Written as mechanism-only, no shape language, per
physics.md Section 3.

> **AMENDED 2026-08-17, post-checkpoint (physics.md v1.2).** The specs below
> originally defined four mechanisms each. physics.md Section 3 requires SIX —
> substrate, constraint, resource logic, initiation mode, **replication mode**,
> **terrain-interaction mode**. The two missing ones are now specified and
> implemented; see physics.md Section 13 Amendment Log v1.2 and the
> `checkpoint_reconfiguration` terrain event in memory.json. Without them no
> specimen could act on any other, and Section 6's functional roles were
> unreachable.

**Generator A — code/structure-native**
- Substrate: structural/code-form output only (functions, loops, nested
  structures, symbolic notation). No natural-language prose.
- Resource dependency: output complexity/length scales UP with proximity to
  the data-stream resource variable (river-proximate = more material to work
  with = larger/more complex output permitted).
- Initiation: self-initiating each shift.
- Constraint: hard max output token length (tuned during Phase 1 testing);
  no external references; no instruction implying visual/organic target.
- Terrain-interaction: receives the flow available at its own position after
  occupancy, not the terrain-wide figure. Its own recorded specimens hold
  resource out of that position until they resolve.
- Replication: a specimen of its own whose measured complexity reaches the
  fixed threshold may claim its initiation slot and produce a descendant from
  its own prior material.

**Generator B — language-fragment-native**
- Substrate: short natural-language text fragments only. No code, no markup,
  no structural notation.
- Resource dependency: INVERSE of Generator A — output frequency/novelty
  scales UP with DISTANCE from the data-stream (scarcity-driven, upland
  behavior rather than river-proximate abundance).
- Initiation: self-initiating each shift.
- Constraint: hard max fragment length; no narrative continuity requirement
  imposed (any continuity across fragments is Generator B's own emergent
  behavior, not seeded).
- Terrain-interaction: as Generator A, at its own position. Because its
  resource logic is inverse, local depletion RAISES its initiation count.
- Replication: as Generator A, capped so replication never claims more than
  half its slots. A descendant works from its parent's material only — never
  from another specimen's, and never from anything the steward wrote.

**Generator C** — deferred. Do not add at seed. Revisit only after the
15-shift falsification checkpoint (physics.md Section 11), and only if
Generators A and B have produced enough taxonomy depth to make a third
substrate meaningful rather than diluting.

System prompt for each Generator should state ONLY substrate and constraint —
never a target output description, category, or example of what a "good" output
looks like. If a Generator's prompt could be answered with "make something that
looks like X," rewrite it.

---

## 5. Namer Operating Spec

- Input each shift: current `taxonomy.json` + last N entries from
  `specimen_log.jsonl` (N to be tuned for cost)
- For each new specimen from a Generator this shift, Namer must:
  1. Compare against existing categories in its own native taxonomy
  2. File under existing category, propose a new category, OR flag anomalous
  3. Log reasoning (this reasoning is itself the primary research data — log it
     in full, not summarized)
  4. Apply the logging-tier rule (Section 8, physics.md) — individual vs.
     aggregate — as a fixed check, not a judgment call
- Namer is NOT given the Linnaean structure as a starting template. It is only
  given the constraint: "for any two specimens, be able to say whether they are
  more or less alike, and why."
- Namer does NOT generate the Linnaean crosswalk — that is the Archivist's job,
  run at low frequency, separately, so the Namer's native reasoning stays
  uncontaminated by human categorical language in the moment of classification.

---

## 6. Hard Boundaries (Non-Negotiable — Enforce in Code)

- No file writes outside `/basin-01/`.
- No external network calls from any agent role.
- Any replication-capable (viral/parasitic) specimen logic must be logically
  incapable of writing to any file/process outside `/basin-01/state/`. Enforce
  this at the code level (e.g., sandboxed write function all roles must use — no
  raw filesystem access), not by prompt instruction alone.

---

## 7. Steward Interface (Minimum Viable)

For now, terminal-only is sufficient:
- `python clock_in.py` — starts a shift, runs active roles, writes state, logs,
  exits cleanly
- `tail -f basin-01/shifts/shift_log.jsonl` and `basin-01/state/specimen_log.jsonl`
  for live observation during a shift
- A simple local dashboard (reads the same JSON files, no live socket needed) is a
  reasonable Phase 2 addition once shift 0 has run successfully — not a blocker
  for starting.

---

## 8. Steward Decisions — Status: ALL FINALIZED

All five pre-shift-0 decisions are locked. Confirmed for BASIN-01:

1. **Storage format:** flat JSON files (physics.md Section 2) — FINAL
2. **Falsification condition:** 15-shift checkpoint (physics.md Section 11) — FINAL
3. **Per-shift budget cap:** $0.15/shift, $15 total ceiling (physics.md Section 12) — FINAL
4. **Ollama model:** llama3.2:3b, hardware-safe for 8–16GB RAM / no dedicated GPU
   (see STARTUP_GUIDE.md Section 2) — FINAL
5. **Generator A/B constraint specs** (Section 4, above) — FINAL

Claude Code may proceed with the full build per Section 2's build order. No
further steward decisions block starting the build itself — remaining
judgment calls during implementation (e.g., exact token-length limits tuned
during Phase 1 testing) are expected engineering iteration, not open
governance questions.

---

## 9. Reminders Worth Keeping in View

- Nothing gets missed — all activity is logged, at a tier appropriate to scale.
- Nothing is shape-seeded — mechanism only, everywhere, including in code comments
  and internal naming.
- The steward does not edit taxonomy or specimen records directly, ever, outside
  the containment exception.
- Nothing here claims or implies sentience. Observed complexity is not evidence of
  experience.
