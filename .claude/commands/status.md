---
description: Terrain status — cost, shifts run, integrity, checkpoint progress. Free, read-only.
allowed-tools: Bash(cd:*), Bash(python3:*)
---

Run the terrain's read-only status view:

```bash
cd basin-01 && python3 clock_in.py --status
```

Then report it back in plain language, covering:

- how much of the $15 has been spent, and how much remains
- how many shifts have run, and how many were canonical (the falsification
  checkpoint at physics.md Section 11 counts only canonical shifts)
- whether integrity is clean, and if not, what the finding means and what the
  steward's options are

This command spends nothing and writes nothing. If integrity findings appear,
do not attempt to repair them by editing state files — report them and let the
steward decide (DNT-STW-001 Section 3).
