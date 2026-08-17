---
description: Read what the terrain has actually produced — taxonomy, specimens, anomalies, drift. Free.
allowed-tools: Bash(cd:*), Bash(python3:*), Read
---

Show the steward what the terrain has produced so far. Spend nothing; read only.

Read and summarise:

- `basin-01/state/taxonomy.json` — the Namer's own system, exactly as it wrote
  it. Note whether it has diverged from a flat list, since that is what the
  falsification checkpoint turns on.
- `basin-01/state/specimen_log.jsonl` — the specimen records, including the
  Namer's full reasoning. That reasoning is the primary research data.
- `basin-01/state/anomaly_log.jsonl` — keep two kinds separate: specimens the
  Namer declined to classify (a finding about the taxonomy) versus harness
  failures logged as unresolved (a finding about the software).
- `basin-01/state/memory.json` — category counters, terrain events, and the
  Archivist and Cartographer annotations if any passes have run.

Present it as observation, not as a verdict. Report what is there, including
dull or null results. Do not describe the terrain as alive, conscious, or
having experience, and do not present its categories as discovered fact — they
are one system's account of itself under the conditions it was given
(DNT-CLS-001 Section 7).

If the steward asks what it means, distinguish clearly between what the record
shows and what would merely be your interpretation of it.
