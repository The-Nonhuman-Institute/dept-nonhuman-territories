"""
BASIN-01 — a passive register of what kind of reasoning the Namer is doing.

    python3 reasoning_register.py            write the register, print a summary
    python3 reasoning_register.py --show 6   also print that many worked examples

WHAT THIS IS, AND WHAT IT IS CAREFULLY NOT

  It reads specimen_log.jsonl after the fact and records, per entry, whether
  the Namer's reasoning was purely classificatory or whether it referenced
  something individual about that specimen — its own history, its ancestry,
  other specimens by name, or a revision to a category prompted by watching one
  thing change.

  It does not touch the specimen log. It writes its own derived file,
  state/reasoning_register.jsonl, which can be deleted and rebuilt at any time
  without losing anything. The primary record stays exactly as the Namer wrote
  it (Charter Section 3, DNT-STW-001 Section 4).

  It does not reach the Namer. Nothing here is added to a prompt, shown as
  input, or fed back in any form. The Namer's behaviour, its cadence, and its
  vocabulary are unchanged by the existence of this file. It is a window, not
  a lever — which is the only reason it is allowed to exist at all, because a
  measure that changed what it measured would corrupt the thing being watched.

  It is not a judgment about quality. "Purely classificatory" is not a failure
  and "referenced lineage" is not a success. The question this answers is
  whether the character of the reasoning SHIFTS OVER TIME, and that question
  needs both kinds counted honestly.

WHY THE MATCHES ARE STORED

  Every tag records the phrases that triggered it. A count with no evidence
  behind it is not checkable, and a register that cannot be checked would be a
  worse problem than no register at all — it would look like data.

Python 3.9 compatible.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config

OUTPUT = os.path.join(config.STATE_DIR, "reasoning_register.jsonl")

# Each signal is a set of patterns. They are deliberately narrow: a pattern
# that fires on everything measures nothing.
SIGNALS = {
    # Reasoning about THIS specimen's own past, not just its current state.
    "own_history": [
        r"\bcontinues to\b", r"\bremains\b", r"\bhas (?:progressed|evolved|matured|begun|developed|slowed|grown)\b",
        r"\bpreviously (?:classified|recorded|filed)\b", r"\bprevious classification\b",
        r"\bat last interval\b", r"\bfirst sighting\b", r"\bsince (?:shift|its)\b",
        r"\btrajectory\b", r"\bgrowth rate\b", r"\bno longer\b", r"\bstill\b",
        r"\bover (?:this|the) interval\b", r"\bthis interval vs\b",
    ],
    # Descent, ancestry, and the fact of having come from something.
    "lineage": [
        r"\bdescend(?:ed|ant|s|ing)?\b", r"\bancestr\w+\b", r"\bancestor\w*\b",
        r"\blineage\b", r"\bgeneration[- ]?\d\b", r"\bparent\b", r"\boffspring\b",
        r"\binherit\w+\b",
    ],
    # A category's definition being reconsidered because of one specimen.
    "revises_category": [
        r"\brather than creating a new category\b", r"\brather than coin\w*\b",
        r"\bwidens?\b", r"\bbroadens?\b", r"\bare not entirely\b",
        r"\bshows that (?:organisms|specimens|members)\b",
        r"\bsuggests? (?:the|this) category\b", r"\bexpands? the\b",
    ],
}

OTHER_ID = re.compile(r"i-\d{5}")


def _fields(classification: Dict[str, Any]) -> str:
    return " ".join(
        str(classification.get(key) or "")
        for key in ("reasoning", "comparison", "persistence_native")
    )


def examine(record: Dict[str, Any]) -> Dict[str, Any]:
    """Tag one record. Returns the tags AND what triggered them."""
    classification = record.get("classification") or {}
    text = _fields(classification)
    matched: Dict[str, List[str]] = {}
    for signal, patterns in SIGNALS.items():
        hits = []
        for pattern in patterns:
            found = re.search(pattern, text, re.I)
            if found:
                hits.append(found.group(0).lower())
        if hits:
            matched[signal] = sorted(set(hits))

    others = sorted({i for i in OTHER_ID.findall(text) if i != record.get("specimen_id")})
    if others:
        matched["names_other_specimens"] = others

    return {
        "shift": record.get("shift"),
        "specimen_id": record.get("specimen_id"),
        "category": classification.get("category"),
        "decision": classification.get("decision"),
        "record_tier": record.get("record_tier"),
        "signals": sorted(matched),
        # Purely classificatory: matched against a category on its traits, and
        # said nothing about this specimen as a particular thing.
        "categorical_only": not matched,
        "evidence": matched,
        "reasoning_chars": len(classification.get("reasoning") or ""),
    }


def build() -> List[Dict[str, Any]]:
    if not os.path.exists(config.SPECIMEN_LOG):
        return []
    rows = []
    with open(config.SPECIMEN_LOG, "r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if (record.get("classification") or {}).get("reasoning"):
                rows.append(examine(record))
    return rows


def summarise(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        print("no reasoning entries yet")
        return
    print("%d entries with reasoning\n" % len(rows))
    print("%-8s %-7s %-7s %-8s %-8s %-8s %s"
          % ("shifts", "n", "cat-only", "history", "lineage", "names", "revises"))
    spans = [(0, 49, "0-48"), (49, 96, "49-95"), (96, 10 ** 6, "96+")]
    for lo, hi, label in spans:
        group = [r for r in rows if lo <= (r["shift"] or 0) < hi]
        if not group:
            continue
        pct = lambda key: "%d%%" % round(
            100.0 * sum(1 for r in group if key in r["signals"]) / len(group))
        print("%-8s %-7d %-8s %-8s %-8s %-8s %s"
              % (label, len(group),
                 "%d%%" % round(100.0 * sum(1 for r in group if r["categorical_only"]) / len(group)),
                 pct("own_history"), pct("lineage"),
                 pct("names_other_specimens"), pct("revises_category")))


def main(argv: List[str]) -> int:
    rows = build()
    with open(OUTPUT, "w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    summarise(rows)
    print("\nwrote %s" % OUTPUT)
    print("derived from the specimen log; the log itself is untouched.")

    if "--show" in argv:
        try:
            count = int(argv[argv.index("--show") + 1])
        except (IndexError, ValueError):
            count = 3
        print("\nworked examples — the phrases that triggered each tag:\n")
        for row in [r for r in rows if r["evidence"]][-count:]:
            print("  shift %s  %s  ->  %s" % (row["shift"], row["specimen_id"], row["category"]))
            for signal, hits in sorted(row["evidence"].items()):
                print("      %-22s %s" % (signal, ", ".join(hits[:6])))
            print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
