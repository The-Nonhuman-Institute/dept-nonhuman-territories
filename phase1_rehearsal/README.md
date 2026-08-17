# Phase 1 rehearsal data — NOT terrain history

These files are the local-model (`gemma3:4b`) shifts run while building and
debugging BASIN-01. They are preserved here, and they are **not** part of the
terrain's canonical record.

STARTUP_GUIDE.md Section 2.5: Phase 1 output is "disposable test data, not
canonical terrain history. Treat any output during this phase as disposable."

## Why this was archived rather than carried forward

The Namer's taxonomy in these files contains categories coined by a small local
model from throwaway output. Continuing canonical shifts on top of it would
have meant every real shift building on a classification system seeded by
rehearsal data — and the 15-shift falsification checkpoint (physics.md Section
11) would then be reading a taxonomy that was partly an artifact of the
rehearsal, not of the terrain's actual physics.

So the terrain was reset to pristine before the first canonical shift, and
canonical shift 0 is the terrain's real seeding.

Archived rather than deleted: the Charter (Section 3) commits the Department to
not omitting records, and these cost nothing to keep.

## What the rehearsal established

3 shifts completed (0, 1, 2), 2 shifts aborted cleanly, 8 specimen records,
4 categories coined, taxonomy depth 2.

Verified during the rehearsal:

- the full loop end to end, all six roles
- atomic commit at clock-out; a shift killed mid-flight left state at its last
  good checkpoint with the shift number unused
- both branches of the code-enforced promotion rule
- the inverse resource logic across shifts (Generator B's initiations fell from
  3 to 2 as channel flow rose 0.60 -> 0.90)
- mechanical drift detection, which found the Namer coining categories and then
  dropping them from its own system
- budget refusal, integrity refusal, and abort-with-terrain-event paths
- containment: writes outside the terrain refused, symlink escape refused,
  Generators holding no write capability at all

Cost of the entire rehearsal: $0.00.
