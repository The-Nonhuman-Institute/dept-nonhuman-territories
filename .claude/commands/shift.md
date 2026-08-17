---
description: Run one terrain shift end to end (clock in, run active roles, commit, clock out).
allowed-tools: Bash(cd:*), Bash(python3:*)
---

Run one shift of terrain BASIN-01.

**Before running, check `basin-01/config.py` for the `PHASE` setting.**

- `PHASE = "ollama"` — free. Just run it.
- `PHASE = "claude"` — this spends real money from the $15 ceiling and produces
  canonical terrain history. Say so plainly and confirm with the steward before
  running, unless he has already said to go ahead in this conversation.

Run it from the terrain directory:

```bash
cd basin-01 && python3 clock_in.py
```

A local shift takes 8–13 minutes. Run it in the background and report when it
lands — do not sit blocking on it.

When it finishes, report in plain language:

- what each role did, and what the Namer classified
- any new category it coined, and any drift the Archivist surfaced
- what it cost, and the running total against $15
- anything flagged anomalous or unresolved, keeping those two distinct:
  anomalous is a finding about the taxonomy, unresolved is a harness failure

If the shift aborts, that is a designed outcome, not a crash: nothing was
committed, the shift number stays unused, and the failure is on the record.
Say what happened and offer to run it again.

Never edit state files to make a shift look better, and never re-run a shift to
get a nicer result — the first result is the record.
