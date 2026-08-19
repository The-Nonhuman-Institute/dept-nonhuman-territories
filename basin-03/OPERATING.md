# BASIN-01 — Operating Guide

A plain-language guide to running this terrain. Written for the steward, not
for a developer. Nothing here overrides `physics.md`, the `/docs` governance
documents, or `README.md` — this is only *how to work the controls*.

---

## The three commands

Everything happens from the `basin-01` folder. Open Terminal and run:

```bash
cd ~/Desktop/dnt-project/basin-01
```

Then:

| Command | What it does | Costs money? |
|---|---|---|
| `python3 clock_in.py --status` | Shows cost, shift count, integrity. Reads nothing else. | No |
| `python3 clock_in.py --dry-run` | Shows what the next shift *would* run, then stops. | No |
| `python3 clock_in.py` | Runs one full shift and commits it. | Only in Phase 2 |

**Check `--status` before every session.** It takes five seconds and it is the
habit that prevents a "where did my credits go" surprise
(STARTUP_GUIDE.md Section 4.1).

To watch a shift as it happens, open a second Terminal window and run:

```bash
tail -f shifts/shift_log.jsonl
tail -f state/specimen_log.jsonl
```

---

## Phase 1 vs Phase 2 — the one line that matters

Open `config.py`. Near the top:

```python
PHASE = "ollama"          # free, local, disposable test data
```

Change `"ollama"` to `"claude"` and shifts become **canonical** — real terrain
history, and real money. Change it back and they are free again. Nothing else
in the terrain needs to change.

**Before switching to `"claude"` you need two things:**

1. The Anthropic library installed:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install anthropic
   ```
   Then run shifts with `.venv/bin/python clock_in.py` instead of `python3`.

2. Your API key available to the terminal:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```
   Never put the key in a file inside this folder. `.gitignore` is set up to
   keep keys out of the repository, but the safest key is one that was never
   written down there in the first place.

---

## What a shift costs

| | |
|---|---|
| Phase 1 (local) | $0.00 — always |
| Early canonical shift | roughly $0.01–$0.02 |
| Hard cap per shift | $0.15 — enforced in code, no override |
| Total ceiling | $15.00 — the terrain refuses to start a shift that would breach it |

You will get a warning once 75% of the $15 is spent. At the ceiling, shifts
stop. There is deliberately no flag to force past it.

---

## What the machine is doing, in order

1. **Keeper** reads what happened before and writes a short summary. (Skipped on
   shift 0 — there is nothing prior to read.)
2. **Generator A** produces structural output. Gets a bigger allowance when the
   resource channel is flowing well.
3. **Generator B** produces short text fragments. Initiates *more often* when
   the channel is low — it works the opposite way round from A.
4. **Namer** classifies everything from this shift using its own system, and
   writes down its reasoning in full.
5. **Archivist** and **Cartographer** run only on shift 7, 14, 21, and so on.

Nothing is saved to disk until the shift finishes cleanly. If the machine
crashes halfway through, you lose that shift and nothing else.

---

## When something goes wrong

**"REFUSING TO START — terrain integrity findings"**
A previous shift was interrupted after it wrote some records but before it
finished. The records are real, not corrupt. The terrain will not start a new
shift over the top of that ambiguity. Read what it reports, decide how you want
to treat the interrupted shift, and note the decision.

**"SHIFT ABORTED — nothing committed"**
Something failed mid-shift, usually the local model timing out. Nothing was
saved, the shift number stays unused, and the failure is recorded as a terrain
event. Just run it again.

**Local model too slow / fan pinning / machine lagging**
Press `Ctrl+C`. Nothing is lost. `gemma3:4b` on a CPU is doing minutes of work
that Haiku does in seconds — this is why Phase 1 output is disposable.

**Cost tracking looks wrong**
Stop. Compare `clock_in.py --status` against the Anthropic Console's own usage
page before running anything else (STARTUP_GUIDE.md Section 6).

---

## What you may and may not do

From the Stewardship Protocol (DNT-STW-001) — these are your own rules, and the
code is built so the second list is difficult rather than merely discouraged.

**You may:** start and end shifts; read every file, at any time; improve the
software; upgrade which model a role runs on.

**You may not:** edit `taxonomy.json` or `specimen_log.jsonl` by hand; tell a
Generator what to make; overrule a Namer classification; leave an inconvenient
result out of the record.

The one exception is containment: if something ever writes outside
`basin-01/`, reaches the network on its own, or replicates beyond the sandbox,
you intervene immediately and log it as a terrain event. Nothing in the current
build can do any of those — the Generators hold no write capability at all, and
only `config.py` can open a connection — but that is the standing exception.

---

## The checkpoint you set

After **15 canonical shifts**, look at whether the Namer's taxonomy has
developed groupings or relationships, whether anything was flagged anomalous,
and whether anything was promoted from aggregate to individual record.

If none of that happened, that is a **null result for this configuration** —
not a failure of the idea. The response is to reconfigure the Generators or
seed a second terrain under different physics, rather than running the same
setup indefinitely hoping it changes.

`clock_in.py --status` counts canonical shifts for you. Phase 1 shifts do not
count toward the 15.

---

## Where everything lives

```
basin-01/
  clock_in.py       the only thing you run
  config.py         the phase switch, the caps, the budget
  terrain_io.py     the only code that writes to disk
  OPERATING.md      this file
  agents/           the six roles
  state/
    memory.json         terrain state, costs, category counters
    taxonomy.json       the Namer's own system, exactly as it wrote it
    specimen_log.jsonl  one line per specimen record
    anomaly_log.jsonl   unclassifiable specimens, and harness failures
  shifts/
    shift_log.jsonl     one line per shift
```

Two files answer most questions: `state/taxonomy.json` for what the terrain
thinks it contains, and `shifts/shift_log.jsonl` for what each shift cost and
produced.
