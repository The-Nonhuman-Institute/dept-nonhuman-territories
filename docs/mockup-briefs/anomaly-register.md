# Mockup brief — DNT Anomaly Register

Paste everything below into ChatGPT. It is written so the mockup can only use
fields that exist in our record.

---

## Who you are designing for

The **Department of Nonhuman Territories (DNT)**, a research body that runs
bounded digital environments ("terrains") seeded with fixed mechanical rules.
Autonomous agent roles live in them and a classifying agent called **the Namer**
observes what emerges and decides for itself what kinds of thing are there.
DNT records and classifies. It never authors, corrects, or steers, and it does
not evaluate or rank terrains.

I need mockups for one page we have not designed yet: the **Anomaly Register**.

## The house style you must match

This page belongs to the dark **console** family (the live-state views of a
running terrain), not the cream **paper** family (reference documents).

- Background `#080A07`; panels `#0D100C`; panel borders `#1D231B`
- Body text `#D6DED2`; secondary `#7C8879`; faint `#4E574C`
- Accent moss `#8FC96B` / `#A8D45C`; amber `#C9A227`; rose `#D4614A`;
  violet `#B37BD6`; blue `#4FA3E3`
- Terrain colours are fixed by identity: BASIN-01 blue `#4FA3E3`,
  BASIN-02 violet `#B37BD6`, BASIN-03 lime `#A8D45C`, BASIN-04 amber `#E0A44C`
- Serif (Georgia) for page titles and big figures; monospace for everything
  else — labels, tables, data, captions. Uppercase mono for panel headers with
  wide letter-spacing.
- Layout: fixed top bar (logo, breadcrumb, shift/status, action buttons), a
  left rail, a wide centre column, a right rail, and a footer reading
  `DNT ANOMALY REGISTER v1.0` / `WE OBSERVE. WE DO NOT INTERFERE.` /
  `A BRANCH OF THE NONHUMAN INSTITUTE`
- The logo is a rectangular bracket outline with a gap in the middle of its
  base; the letters `DNT` sit inside that gap.
- Top bar carries: `Back to observation deck`, `Field compendium`,
  `Classification structure`, `Linnaean crosswalk`
- Status reads `HOLDING`, never `RUNNING` — a terrain advances only when a
  shift is run against it and is otherwise exactly still.

## The one rule that matters most

**Every field on the page must map to a real field in the data inventory
below.** Do not invent metrics, confidence scores, severity ratings, risk
levels, assessments, review states, assignees, or an authority who signed
anything. If a panel would need a number we do not record, leave that panel out
and tell me what it would have needed. I would rather have a sparser page than
a plausible one.

Also: do not invent terrains. There are exactly four — BASIN-01, BASIN-02,
BASIN-03, BASIN-04. No DELTA-07, no RIDGE-11.

## What the anomaly log actually contains

Our file is called `anomaly_log.jsonl`, and the single most important design
problem is that **it holds three completely different kinds of record**, told
apart by a `record_tier` field. Blurring them would corrupt the thing the page
exists to show. Real counts, right now:

| terrain | total rows | anomalous | unresolved | ended: dissolved | ended: taken |
|---|---|---|---|---|---|
| BASIN-01 | 201 | 10 | 78 | 113 | 0 |
| BASIN-02 | 6,912 | 4 | 1 | 6,907 | 0 |
| BASIN-03 | 41,446 | 17 | 0 | 31,599 | 9,830 |
| BASIN-04 | 0 | 0 | 0 | 0 | 0 |

**1. `anomalous`** — the Namer looked at a specimen and could not fit it into
any category, and said so rather than forcing it. This is the real subject of
the page. It is a *finding*, not a fault. Fields on each record:

```
specimen_id        "i-00001"
shift              4
logged_at          "2026-08-18T17:33:57Z"   (UTC; we display in the reader's zone)
source_role        "terrain"
substrate          "fragment" | "structural"
complexity         1
record_tier        "anomalous"
resolution         "flagged_anomalous"
flagged_by         "namer"
note               "Flagged by the Namer as fitting no category. Not
                    force-fitted (DNT-CLS-001 Section 5)."
content            the full observation text the Namer was shown — position on
                   the gradient, elevation, light held, what it drew from,
                   descendants, how it is built, and its substrate as recorded
classification.decision     "anomalous"
classification.category     null
classification.reasoning    826–1,568 characters of the Namer's own prose
classification.comparison   how it sat against what it had already filed
classification.persistence_native  how it persists, in the Namer's words
```

BASIN-03's 17 anomalies fall at shifts 4, 73, 75, 83, 87, 89, 96, 98, 103, 116,
122, 134, 137, 137, 138, 143, 144 — and split 9 fragment / 8 structural.

**2. `unresolved`** — a *harness* failure. The model returned nothing readable.
This is emphatically NOT evidence about the taxonomy, and our governance
requires it be counted apart from anomalies. Fields:

```
record_tier        "unresolved"
resolution         "unresolved"
mechanism_failure  "no readable decision returned for this specimen"
raw_response       whatever came back, often null
note               "Harness failure, not a Namer classification decision.
                    This record is not evidence about the taxonomy."
```

BASIN-01 has 78 of these against only 10 real anomalies — the register has to
make that ratio impossible to misread.

**3. `ended`** — a specimen ran out of light and died. `resolution` is either
`dissolved` (31,599 in BASIN-03) or `taken` (9,830), where **taken means it was
drawn down by another specimen** — our predation mechanic showing up in the
record. These are 99.9% of the file and are not anomalies at all.

## Questions the page should answer

1. What could the Namer not place, and what did it say about each one?
2. Is the rate of anomalies rising, falling, or steady over the terrain's life?
3. Do anomalies cluster — in time, in one region of the terrain, in one
   substrate, at one point in a specimen's life?
4. What became of a flagged specimen afterwards — did it survive, did the
   Namer later file it somewhere, did it leave descendants?
5. How much of this file is a real finding versus a harness failure versus an
   ordinary death, and how do those three lines compare across terrains?
6. For deaths specifically: how does `dissolved` compare with `taken` over
   time — that is the only view we have of predation as it actually ran.

## What I want back

Three or four full-page mockups, wide desktop (about 1600px):

1. **Anomaly Register — overview for one terrain (BASIN-03).** The three record
   kinds separated and never summed together, a rate over time, clustering
   views, and the list of the 17 real anomalies.
2. **A single anomaly record.** One flagged specimen in full — the observation
   the Namer was shown, its own reasoning in its own words, where it stood, and
   what happened to it after.
3. **Cross-terrain view.** All four terrains' anomaly and unresolved rates side
   by side, per hundred shifts so terrains of different ages compare.
4. *(optional)* **Endings view** — dissolved versus taken over time.

Show real-looking values consistent with the counts above, and label anything
you had to fill in as a placeholder. Where you think a panel needs a field we do
not record, draw it anyway but flag it in a note beside the mockup so I can
decide whether to build the datapoint.
