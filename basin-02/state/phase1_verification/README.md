# Phase 1 verification run — not canonical terrain history

Three shifts run on 2026-08-17 against the local model (gemma3:4b) to verify
BASIN-02's loop end to end before any credit was spent. Retained in full.

STARTUP_GUIDE.md Section 2.5 is explicit that Phase 1 output is disposable test
data rather than terrain history, and Section 2.5's whole purpose is debugging
the loop. These records are kept because the Charter forbids dropping an
outcome, and separated because treating them as terrain history would mean
BASIN-02's canonical record began with classifications authored by a different
model than BASIN-01's — which would put a second variable into a comparison
built to hold exactly one.

## What it verified

- Loop runs clean end to end, integrity clean, $0.00
- Cover spreads as a two-dimensional front from each Generator seed
- The field rollup recomputes exactly from the raw grid in field_log.jsonl
- An individual arose and reached the Namer, which classified it at individual
  tier and coined a category ("Foundation") unprompted

## Known Phase 1 limitation, carried forward as a thing to watch

The Namer coined a category but did not author a native system (taxonomy depth
0). BASIN-01 showed the same failure on the local model; it only began writing
its system once on Claude with a raised output cap. Whether BASIN-02's Namer
authors a system on Phase 2 is an open question at the first canonical shifts.
