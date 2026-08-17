---
description: Switch between free local shifts (Phase 1) and paid canonical shifts (Phase 2).
allowed-tools: Bash(cd:*), Bash(python3:*), Read, Edit
---

Check the current `PHASE` in `basin-01/config.py` and report it. Then help the
steward switch if that is what he wants.

**Going to Phase 2 (`"claude"`) — real money, real terrain history.**

Before switching, confirm all of the following and report any that fail:

1. The loop has run cleanly on the local model several times in a row.
2. `physics.md` and `docs/01_DNT_Physics_Terrain01.docx` agree. After the first
   canonical shift, physics is frozen except as a logged terrain event
   (DNT-STW-001 Section 3) — this is the last moment to amend it.
3. The `anthropic` package is installed in a venv:
   `python3 -m venv .venv && .venv/bin/pip install anthropic`
4. `ANTHROPIC_API_KEY` is set in the environment. Never write it into a file in
   this repository.

Then change the single line in `basin-01/config.py` and confirm with
`--dry-run` that it reports the Claude model rather than the local one.

Remind the steward that from this point:

- each shift costs roughly $0.01–0.02, capped hard at $0.15
- the $15 ceiling is enforced, with no override
- the falsification checkpoint is 15 canonical shifts, so the checkpoint costs
  well under a dollar

**Going back to Phase 1 (`"ollama"`)** is always safe and free.

Do not switch phase without the steward explicitly asking. Spending his budget
is his decision, not an inference from context.
