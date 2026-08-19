# Pre-seed build debris — not terrain history

One shift record was written here on 2026-08-17 during BASIN-02's Phase 1
build, before the terrain was seeded and before any canonical shift ran.

## What happened

`terrain_io._guard()` refused to write `state/field_log.jsonl` because the file
had been added to the commit path but not to the writable allowlist. The guard
was correct and did its job. Because the commit writes append-only logs before
`memory.json`, the shift record landed and the shift never closed, leaving one
record ahead of `last_committed_shift`. The integrity check detected exactly
that and the loop refused to start rather than paper over it.

## What was decided, and why it is not a deleted record

The record was moved here rather than removed. It is retained in full.

It is not terrain history: BASIN-02 had not seeded, no canonical shift had run,
the phase was `ollama`, and STARTUP_GUIDE.md Section 2.5 is explicit that
Phase 1 output is disposable test data rather than terrain history. Charter
Section 3 forbids dropping a record because it is inconvenient; this is a
harness crash during a build, kept and labelled, not an outcome omitted.

The remaining state files were empty of records and were reset so the terrain
could seed from a clean shift 0.

## The fix

`config.FIELD_LOG` was added to `terrain_io._WRITABLE_FILES` and
`_APPEND_ONLY_FILES`. The guard still refuses every path outside the terrain.
