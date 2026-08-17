# DNT — Startup Guide
## Terrain BASIN-01 — Build & Launch Walkthrough

This document is the practical, step-by-step companion to `README.md` and
`physics.md`. Where those define *what* to build and the rules it must follow,
this document covers *how to actually get it running* on your specific hardware
and budget, safely.

Read this before opening Claude Code.

---

## 1. Your Constraints, Stated Plainly

- **Local machine:** 8–16GB RAM, no dedicated GPU (integrated graphics only).
  You've had crashes running Ollama before. This is a real constraint, not a
  minor inconvenience — the plan below is built around it, not in spite of it.
- **Budget:** ~$15 total in Anthropic API credit, reserved for canonical
  (real, logged) shifts only.
- **Goal split:** Ollama handles free, low-stakes scaffolding and debugging.
  Claude API handles the shifts that actually count, spent sparingly and
  tracked closely.

---

## 2. Phase 1 — Ollama Setup (Hardware-Safe)

### 2.1 Why smaller, on purpose

With no dedicated GPU, every token Ollama generates is processed on your CPU
using system RAM. A model that's too large doesn't just run slowly — it can
exhaust available memory, spike CPU sustained load (the loud fan you've heard),
and crash the machine, exactly as you described. The fix isn't a workaround,
it's picking a model sized honestly for this hardware.

**"Near-frontier" is not a safe goal on this hardware.** A genuinely strong
small model, run reliably, is worth more to this project than a bigger model
that crashes your machine mid-shift and corrupts a run.

### 2.2 Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```
(macOS/Linux. For Windows, download the installer directly from ollama.com.)

### 2.3 Recommended model — start here

```bash
ollama pull llama3.2:3b
```

- ~2GB download, quantized, designed to run on modest hardware.
- This is the safest realistic starting point for 8–16GB RAM with no GPU.
- Capable enough for Generator and Keeper roles during scaffolding — you are
  testing the *loop*, not final output quality, at this stage.

**If that runs stably for a few sessions** (no crashes, fan stays reasonable,
machine stays responsive), you can cautiously try one step up:

```bash
ollama pull qwen2.5:7b-instruct-q4_0
```

- Roughly 4–4.5GB. Only attempt this if you have closer to 16GB RAM and the
  3B model ran completely cleanly first. If you notice any slowdown, fan
  spike, or system lag, stop and drop back to the 3B model — don't push
  through it.

**Do not attempt models above 7B parameters on this hardware.** This isn't
conservative for its own sake — it's the actual line between "slow but safe"
and "the crash you've already experienced."

### 2.4 Thermal/stability safety checklist, every session

- Close other heavy applications (browser tabs, other apps) before starting
  Ollama — free up all the RAM you can.
- Run one shift at a time, not multiple in parallel.
- If your fan ramps up hard and stays there, or the system starts lagging,
  stop the process (`Ctrl+C`) rather than waiting to see if it resolves.
- Keep shifts short during Phase 1 — you're debugging the scaffold, not
  running long creative sessions yet.
- Consider running Ollama sessions plugged into power, not on battery — CPU
  throttling on battery can cause its own instability under sustained load.

### 2.5 What Phase 1 is actually for

Phase 1 exists to get `clock_in.py`, the state files, and the logging loop
working *correctly* — not to produce meaningful specimens yet. Bugs are cheap
to hit and fix here. Treat any output during this phase as disposable test
data, not canonical terrain history. Once the loop runs cleanly, end-to-end,
without crashing, for a few consecutive test shifts — you're ready for Phase 2.

---

## 3. Phase 2 — Claude API (Canonical Shifts)

### 3.1 Current pricing (verified today)

| Model | Input | Output |
|---|---|---|
| Claude Haiku 4.5 | $1.00 / MTok | $5.00 / MTok |

Use Haiku 4.5 for Generators and for most Namer classification passes — it's
the cost-efficient tier and well-suited to frequent, shorter calls. Pricing
changes over time; check `docs.claude.com` before a long run if it's been a
while since you last checked.

### 3.2 Realistic cost per shift

Rough estimate, early in the terrain's life (small taxonomy, short context):

| Action | Approx. tokens (in/out) | Approx. cost |
|---|---|---|
| 1 Generator call | ~400 / ~300 | ~$0.002 |
| 1 Namer classification pass | ~800 / ~300 | ~$0.0025 |
| Early shift (2 Generators + 2 Namer passes) | — | **~$0.01–$0.02** |

This will grow over time as taxonomy.json and recent specimen history get
included in Namer context — a shift a few months in might cost several times
more than an early one. That growth is normal and expected, not a bug — but
it's exactly why tracking cumulative cost every shift (Section 4) matters more
as the terrain matures, not less.

Archivist and Cartographer passes (low-frequency, every 5th–10th shift) cost
more per run since they read the *full* taxonomy — budget roughly $0.05–$0.20
per pass depending on how much has accumulated by then.

### 3.3 What this means for your $15

**Locked for BASIN-01: $0.15 hard cap per shift, $15 total ceiling.**

This is a ceiling, not a target — early shifts (per Section 3.2 math) should
cost well under it, likely $0.01–$0.05. The cap exists to catch the case
where context has grown large and a shift would otherwise run unexpectedly
expensive, not to make every shift expensive by default.

At this cap, your 15-shift falsification checkpoint (physics.md Section 11)
costs at most ~$2.25 of your $15 — leaving the large majority of budget
available either to keep running BASIN-01 past the checkpoint if it's
producing real structure, or to seed a second terrain under different
physics if it isn't.

The realistic risk to the budget was never shift volume — it's:
- Unbounded context growth (Namer reading the entire specimen history every
  time instead of a capped recent window)
- Accidentally running Archivist/Cartographer every shift instead of on their
  intended low-frequency cadence
- Leaving a loop running unattended without the hard cap enforced

All three are solved in code, not by willpower — see Section 4.

---

## 4. Budget Enforcement (Build These Into `config.py`)

- **Hard per-shift token cap.** Set a maximum total tokens (input + output)
  allowed per shift. If a shift would exceed it, truncate context or end the
  shift early — never silently let a single shift run unbounded.
- **Capped context window for the Namer.** Feed it the last N specimen log
  entries, not the full history, with N tuned down as the log grows. Full
  taxonomy is fine to include (it should stay relatively compact); full raw
  specimen history is not.
- **Cumulative spend tracker.** Every shift, log estimated cost and running
  total against the $15 ceiling in `shift_log.jsonl` (per the Shift Log
  Policy). `clock_in.py` should refuse to start a new shift if projected cost
  would breach the ceiling, and warn well before that point — e.g., at 75%
  of budget spent.
- **Low-frequency roles stay low-frequency in code, not just in intent.**
  Archivist and Cartographer should have an explicit shift-count gate
  (`if shift_number % 7 == 0:` or similar) — don't rely on remembering to
  skip them manually.

### 4.1 Suggested cadence

- **Week 1–2:** Ollama only. Get the loop stable. Zero API cost.
- **Once stable:** Switch `config.py` to Claude API. Run short, infrequent
  shifts (a few minutes each, a few times a week) rather than long daily
  sessions — this keeps you observing deliberately rather than burning budget
  on volume for its own sake, which also fits the Stewardship Protocol's
  spirit better than constant intervention would.
- **Check cumulative cost every session**, out loud, before clocking in again.
  It's a five-second habit that prevents the "where did my credits go"
  surprise.

---

## 5. Order of Operations — Full Startup Sequence

1. Confirm the five open decisions from `README.md` Section 8 (storage format,
   falsification condition, per-shift cap, Ollama model, Generator A/B specs).
2. Install Ollama, pull `llama3.2:3b`.
3. Open Claude Code in `/dnt-project`. Point it at `README.md` and
   `physics.md` as the build spec.
4. Build in the order specified in `README.md` Section 2 — `config.py` first,
   with the Ollama/Claude API swap and budget caps built in from the start,
   not added later.
5. Run test shifts on Ollama until `clock_in.py` runs cleanly, repeatedly,
   with no crashes.
6. Switch `config.py` to Claude API (Haiku 4.5). Run shift 0 for real.
7. Check `shift_log.jsonl` after every shift. Watch cumulative cost.
8. Resist the urge to run Archivist/Cartographer early or to lengthen shifts
   just because nothing dramatic has happened yet — per the falsification
   condition you set, give it real time before judging the terrain.

---

## 6. If Something Goes Wrong

- **Machine crashes during an Ollama shift:** the shift is incomplete, not
  corrupted terrain history — `clock_in.py` should only commit state to the
  JSON files at a clean shift-end, not incrementally, so a crash mid-shift
  should leave `state/` at its last good checkpoint. Confirm this behavior
  exists before your first real shift, on Ollama, where a crash costs nothing.
- **API cost tracking looks off:** stop, don't guess — check the Anthropic
  Console's actual usage dashboard against your own `shift_log.jsonl` numbers
  before running another shift.
- **A replication-capable specimen behaves unexpectedly:** this is the one
  case where the Stewardship Protocol's containment exception applies —
  intervene to restore containment, log it as a terrain event, don't wait to
  see what happens next.
