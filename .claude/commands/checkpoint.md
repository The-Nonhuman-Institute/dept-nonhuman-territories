---
description: Evaluate the 15-shift falsification checkpoint against the record, mechanically. Free.
allowed-tools: Bash(cd:*), Bash(python3:*), Read
---

Evaluate physics.md Section 11 against what is actually recorded. Spend
nothing; read only.

The condition, verbatim: if after **15 canonical (Claude API) shifts** the
Namer's native taxonomy has not diverged from a flat, unstructured list — no
groupings, no relational structure, no anomalies flagged, nothing promoted from
aggregate to individual record — that is a **null result for this seed
configuration**.

The whole point of stating it in advance was so the outcome is not judged by
impression afterwards. So evaluate each criterion from the record, and report
the measured value beside it:

1. **Canonical shifts run** — count entries in `basin-01/shifts/shift_log.jsonl`
   with `"phase": "claude"`. Phase 1 shifts do not count. If fewer than 15, say
   how many remain and stop there; the checkpoint is not due.
2. **Groupings / relational structure** — `taxonomy_structure.diverged_from_flat_list`
   in `basin-01/state/memory.json`, plus `max_depth`. Depth 1 is a flat list.
3. **Anomalies flagged** — count records in `basin-01/state/anomaly_log.jsonl`
   with `record_tier: "anomalous"`. Do **not** count `unresolved` records: those
   are harness failures, not classification findings, and counting them would
   make the terrain look more structured than it is.
4. **Promotions to individual record** — specimen records whose
   `promotion_triggers` is non-empty.

Then state the verdict plainly: **null result** or **not a null result**, and
which specific criteria carried it.

If it is a null result, say so directly and without softening. That finding is
worth exactly as much as a positive one, and the Charter (Section 2) commits the
Department to reporting it with equal seriousness. Do not suggest running more
shifts to see if it improves — physics.md Section 11 explicitly rejects
"continuing the same run indefinitely hoping the result changes". The response
is to reconfigure the Generators or seed a second terrain under different
physics, and that is the steward's decision to make.

Do not interpret the taxonomy's content as meaningful natural history. It is
one system's account of itself under the conditions it was given
(DNT-CLS-001 Section 7).
