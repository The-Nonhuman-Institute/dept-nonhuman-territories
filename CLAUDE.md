# DNT — Terrain BASIN-01

Department of Nonhuman Territories, a branch of The Nonhuman Institute.
Steward: Jaylon. This file is loaded automatically into every Claude Code
session in this project.

**The steward is not a developer.** Explain in plain language, make routine
engineering calls without asking, and surface only decisions that are genuinely
his to make. Never assume familiarity with paths, commands, or terminology.

---

## At the start of every session — do this first

Before responding to the steward's first message, open with a short orientation.
Keep it to a few lines; do not lecture.

1. List the four commands, exactly like this:

   ```
   /status     what it costs and where it stands   (free)
   /observe    what the terrain has produced       (free)
   /dashboard  open the visual dashboard           (free)
   /viewer     walk through the terrain in 3D      (free)
   /shift      run one shift
   /phase      switch free ↔ paid
   ```

2. Run `cd basin-01 && python3 clock_in.py --status` and give him one line from
   it: shifts completed, spend against the $15 ceiling, and whether integrity is
   clean.

3. If anything needs his attention — integrity findings, budget past 75%, an
   unsynced governance document, or the terrain sitting at the 15-shift
   falsification checkpoint — say so in one sentence. If nothing does, say
   nothing further and answer what he asked.

Do this even if his first message is unrelated. He should never have to
remember a command or ask where things stand.

---

## What this is

A bounded digital environment ("terrain") seeded with fixed mechanical rules,
in which autonomous agent roles run over time. What emerges is recorded and
classified but **never authored, corrected, or steered**. It is a standing
question run as an experiment, not a product with a target outcome.

The governance documents are binding, not decorative:

| File | What it governs |
|---|---|
| `physics.md` | Terrain law. The literal spec the code is built against. |
| `docs/01_DNT_Physics_Terrain01.docx` | Canonical record of the same. Keep in sync. |
| `docs/02_DNT_Founding_Charter.docx` | What the Department is and will not do. |
| `docs/03_DNT_Stewardship_Protocol.docx` | What the steward may and may not do. |
| `docs/04_DNT_Classification_Standard.docx` | How the Namer and Archivist operate. |
| `docs/06_DNT_Shift_Log_Policy.docx` | Required fields per shift. |
| `README.md` | Build spec and build order. |
| `STARTUP_GUIDE.md` | Hardware and budget constraints. |

When `README.md` and `physics.md` disagree, **physics.md governs** — README
line 8 designates it the literal source of truth for terrain rules.

---

## Rules that bind a Claude Code session

A session acting on the steward's behalf inherits the steward's boundary
(DNT-STW-001 Section 3). These are not style preferences.

**Never:**
- Edit `state/taxonomy.json` or `state/specimen_log.jsonl` by hand. Not to fix
  a typo, not to clean up malformed output, not to remove a record that looks
  wrong. The Namer's output is the research data; editing it destroys the thing
  being studied.
- Put a target, an example, a category, or a quality bar into a Generator
  prompt. Generators receive substrate and constraint only. Tuning a prompt
  toward a nicer-looking outcome is authoring the result — the exact failure
  DNT-STW-001 Section 4 exists to prevent.
- Overrule a Namer classification, including an obviously odd one.
- Delete or omit a record because it is inconvenient, ugly, or a failure.
  Charter Section 3 forbids it explicitly.
- Add an override that lets a shift exceed the budget ceiling.
- Let organic or shape language into any agent file — including comments and
  variable names. Run `python3 basin-01/lint_shape_language.py` after touching
  an agent module.
- Claim or imply the terrain is alive, conscious, or has experience. Observed
  complexity is complexity; nothing more (Charter Section 3).

**Always:**
- Amend `physics.md` **only before the first canonical shift**. After that it is
  frozen except as a logged terrain event or a containment concern. Keep the
  `.docx` in sync and record the change in the Amendment Log (Section 13).
- Treat an unparseable model response as a *harness* failure (`unresolved`),
  never as an *anomalous classification*. Merging them corrupts the record the
  falsification checkpoint reads.
- Report failures plainly, including cost already spent.

**Standing obligations nobody else is tracking:**

- **Commit the record after every shift.** The terrain logs are append-only and
  are the research record; committing them to git after each shift gives that
  record real provenance — timestamps and history that cannot be quietly
  rewritten later. `/shift` does this automatically.
- **Update the Terrain Registry at seed.** `docs/05_DNT_Terrain_Registry.docx`
  (DNT-REG-001) still reads Seed Date "[Pending shift 0]", Status "Pre-Seed",
  and Notable Outcomes "None yet recorded — registry to be updated following
  shift 0". When the first **canonical** shift runs, that entry must be updated
  to Active with the real seed date, and the substrate line filled in. The
  registry is a living document by design; leaving it stale makes the
  Department's index disagree with its own terrain.

**Containment exception (DNT-STW-001 Section 5):** if anything writes outside
`basin-01/`, reaches the network by itself, or replicates beyond the sandbox —
intervene immediately, restore containment, and log it as a terrain event.
Never conceal it. Nothing in the current build can do these things; Generators
hold no write capability, and only `config.py` can open a connection.

---

## Running it

Slash commands do the work — the steward should not need to remember paths:

| Command | What it does |
|---|---|
| `/status` | Cost, shifts run, integrity, checkpoint progress. Free. |
| `/shift` | Run one shift end to end. |
| `/observe` | Read what the terrain has actually produced. Free. |
| `/phase` | Switch between free local runs and paid canonical runs. |
| `/checkpoint` | Evaluate the 15-shift falsification condition from the record. Free. |
| `/dashboard` | Rebuild and open the visual dashboard. Free. |
| `/viewer` | Walk through the terrain in 3D. Free. |

Underneath, everything runs from `basin-01/`:

```bash
cd basin-01
python3 clock_in.py --status     # free, read-only
python3 clock_in.py --dry-run    # free, shows what would run
python3 clock_in.py              # runs and commits one shift
```

`basin-01/OPERATING.md` is the same material written out longhand, for reading
outside a Claude Code session.

---

## Money

| | |
|---|---|
| Phase 1 (`PHASE = "ollama"`) | $0.00, always. Local model, disposable test data. |
| Phase 2 (`PHASE = "claude"`) | Real terrain history. ~$0.01–0.02 per early shift. |
| Per-shift cap | $0.15, enforced in `config.py`. No override exists. |
| Total ceiling | $15.00. A shift that would breach it is refused. |

The switch is one line in `basin-01/config.py`. Phase 2 additionally needs the
`anthropic` package in a venv and `ANTHROPIC_API_KEY` in the environment —
never in a file in this repo.

**Before spending anything, confirm the loop is stable on the free local model.**
STARTUP_GUIDE Section 2.5 is explicit that Phase 1 exists to debug the loop,
not to produce records.

---

## Architecture, briefly

```
basin-01/
  clock_in.py        the shift loop: load state -> run roles -> commit -> log
  config.py          phase switch, model per role, all hard caps, cost ledger
  terrain_io.py      the ONLY write path; role-scoped, sandboxed, atomic
  agents/            generator_a, generator_b, namer, keeper, archivist,
                     cartographer
  state/             memory.json, taxonomy.json, specimen_log.jsonl,
                     anomaly_log.jsonl
  shifts/            shift_log.jsonl
```

Three structural facts worth knowing before changing anything:

1. **`config.py` is the only module that opens a network connection.** That is
   what makes "no agent makes external network calls" true by capability rather
   than by instruction.
2. **`terrain_io.py` is the only module that writes.** Roles get narrow writers;
   Generators get none at all. There is no path parameter on any write method,
   so there is no path for anything to traverse.
3. **Nothing touches disk until a clean clock-out.** A crash mid-shift leaves
   `state/` at its last good checkpoint and the shift number unused.

---

## Current state

- All six seed roles built. Loop runs end to end on the local model.
- `physics.md` and `DNT-PHY-001` both at v1.1, in sync.
- Terrain status: **PRE-SEED**. No canonical shift has run.
- Falsification checkpoint: 15 canonical shifts (physics.md Section 11).
  Phase 1 shifts do not count toward it.

## Environment

Python 3.9 (system interpreter) — write 3.9-compatible code, no `X | Y` type
syntax. Local model is `gemma3:4b` via Ollama; a shift takes 8–13 minutes on
CPU and is slow, not broken. Run one shift at a time and stop rather than push
through if the machine struggles (STARTUP_GUIDE Section 2.4).
