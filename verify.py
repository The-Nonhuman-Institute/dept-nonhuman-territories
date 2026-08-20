"""
Physics and record verification. Run before a terrain advances.

WHY THIS EXISTS

  BASIN-04 and BASIN-05 were both founded, seeded and run before anyone checked
  whether their flow router worked. It does not: 252 interior cells in BASIN-05
  have no lower neighbour at all, so water runs into them and stops, and the
  drainage network is fragmented into pieces. That was findable in twenty lines
  and instead it was found by tracing a river that turned out not to exist.

  Separately, two shift processes were run against BASIN-05 at once and both
  committed, duplicating two shifts in its log. Nothing checked for that either.

  Every check here is cheap, deterministic, and makes no model call. The point
  is to fail loudly before a terrain accumulates a record under a defect, not
  to explain the defect afterwards.

WHAT A FAILURE MEANS

  FAIL   a defect. The model or the record is wrong and something should be
         fixed before more shifts are run.
  WARN   a condition worth knowing that is not necessarily wrong — a young
         terrain, a deliberate choice.
  ok     checked and sound.

  A check that cannot run for lack of data says so rather than passing.

    python3 verify.py              every terrain
    python3 verify.py basin-05     one terrain

Python 3.9 compatible. Reads only.
"""

from __future__ import annotations

import json, math, os, sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import dnt_terrains

FAIL, WARN, OK, SKIP = "FAIL", "WARN", "ok", "--"


class Report:
    def __init__(self, terrain: str):
        self.terrain = terrain
        self.rows: List[Tuple[str, str, str]] = []

    def add(self, status: str, name: str, detail: str = "") -> None:
        self.rows.append((status, name, detail))

    def counts(self) -> Dict[str, int]:
        out = {FAIL: 0, WARN: 0, OK: 0, SKIP: 0}
        for status, _, _ in self.rows:
            out[status] = out.get(status, 0) + 1
        return out


def _load(terrain: str) -> Dict[str, Any]:
    base = os.path.join(ROOT, terrain)
    def js(path, default):
        p = os.path.join(base, path)
        if not os.path.exists(p):
            return default
        try:
            with open(p, encoding="utf-8") as s:
                return json.load(s)
        except ValueError:
            return default
    def jl(path):
        p = os.path.join(base, path)
        out = []
        if os.path.exists(p):
            with open(p, encoding="utf-8") as s:
                for line in s:
                    line = line.strip()
                    if line:
                        try:
                            out.append(json.loads(line))
                        except ValueError:
                            pass
        return out
    return {"memory": js("state/memory.json", {}),
            "taxonomy": js("state/taxonomy.json", {}),
            "shifts": jl("shifts/shift_log.jsonl"),
            "specimens": jl("state/specimen_log.jsonl"),
            "anomalies": jl("state/anomaly_log.jsonl")}


# ---------------------------------------------------------------- landscape
def check_landscape(d, r) -> None:
    ls = (d["memory"].get("landscape") or {})
    g, W = ls.get("ground") or [], int(ls.get("width") or 0)
    if not g or not W:
        r.add(SKIP, "landscape", "this terrain forms no landscape")
        return
    H = len(g) // W
    N = len(g)

    bad = [v for v in g if v != v or v in (float("inf"), float("-inf"))]
    r.add(FAIL if bad else OK, "elevation is finite",
          "%d non-finite value(s)" % len(bad) if bad else "%d cells" % N)

    def nb(i):
        row, col = i // W, i % W
        out = []
        if row > 0: out.append(i - W)
        if row < H - 1: out.append(i + W)
        if col > 0: out.append(i - 1)
        if col < W - 1: out.append(i + 1)
        return out

    edge = lambda i: (i // W in (0, H - 1)) or (i % W in (0, W - 1))
    pits = [i for i in range(N) if not edge(i) and all(g[j] >= g[i] for j in nb(i))]
    share = 100.0 * len(pits) / N
    r.add(FAIL if pits else OK, "flow can leave every cell",
          ("%d interior cell(s), %.1f%%, have no lower neighbour — water runs in "
           "and stops, so the drainage network is broken into pieces"
           % (len(pits), share)) if pits else "no closed depressions")

    inner = sorted(g[i] for i in range(N) if 2 <= i // W < H - 2 and 2 <= i % W < W - 2)
    if len(inner) > 20:
        relief = inner[int(len(inner) * .95)] - inner[int(len(inner) * .05)]
        med = inner[len(inner) // 2]
        r.add(WARN if relief < med * 0.25 else OK, "the interior has relief",
              "p95-p5 is %.2f against a median height of %.2f%s"
              % (relief, med, " — this is a tableland, not country"
                 if relief < med * 0.25 else ""))

    flow = ls.get("flow") or []
    if flow and len(flow) == N:
        peak = max(flow)
        r.add(FAIL if peak < N * 0.05 else (WARN if peak < N * 0.25 else OK),
              "flow gathers toward a mouth",
              "peak flow %.0f across %d cells (%.1f%%) — a connected network "
              "gathers most of them" % (peak, N, 100.0 * peak / N))
    else:
        r.add(SKIP, "flow gathers toward a mouth", "no flow field recorded")


# ------------------------------------------------------------------- record
def check_record(d, r) -> None:
    rows, m = d["shifts"], d["memory"]
    if not rows:
        r.add(SKIP, "shift log", "no shift has been committed")
        return

    seen: Dict[Any, int] = {}
    for row in rows:
        s = row.get("shift")
        seen[s] = seen.get(s, 0) + 1
    dupes = {s: n for s, n in seen.items() if n > 1}
    r.add(FAIL if dupes else OK, "each shift committed once",
          ("shift(s) %s recorded more than once — two shift processes ran at the "
           "same time and both committed"
           % ", ".join("%s x%d" % (s, n) for s, n in sorted(dupes.items())))
          if dupes else "%d shift(s), all distinct" % len(rows))

    pair: Dict[Tuple, int] = {}
    for rec in d["specimens"]:
        key = (rec.get("specimen_id"), rec.get("shift"))
        if key[0] is not None:
            pair[key] = pair.get(key, 0) + 1
    sd = {k: v for k, v in pair.items() if v > 1}
    r.add(FAIL if sd else OK, "each specimen classified once per shift",
          "%d duplicated (specimen, shift) record(s), e.g. %s"
          % (len(sd), ", ".join("%s@%s" % k for k in list(sd)[:3])) if sd
          else "%d classification record(s)" % len(d["specimens"]))

    last = m.get("last_committed_shift")
    highest = max((row.get("shift") for row in rows
                   if isinstance(row.get("shift"), int)), default=None)
    r.add(OK if last == highest else FAIL, "memory agrees with the shift log",
          "memory says %s, the log's highest is %s" % (last, highest))

    world = m.get("world") or {}
    ind = world.get("individuals") or {}
    nxt = world.get("next_individual_number")
    if isinstance(nxt, int) and ind:
        highest_id = max((int(k.split("-")[-1]) for k in ind if "-" in k), default=-1)
        r.add(OK if nxt > highest_id else FAIL, "identifiers cannot collide",
              "next is %d, highest in use is %d" % (nxt, highest_id))

    cells = {c.get("index") for c in (world.get("cells") or [])}
    if cells:
        stray = [k for k, v in ind.items() if v.get("cell") not in cells]
        r.add(FAIL if stray else OK, "every specimen stands on a real cell",
              "%d standing nowhere: %s" % (len(stray), ", ".join(stray[:4]))
              if stray else "%d individual(s)" % len(ind))

    known = set(ind) | {e.get("id") for e in (world.get("ended") or [])}
    orphans = [k for k, v in ind.items()
               if v.get("parent_id") and v["parent_id"] not in known]
    r.add(WARN if orphans else OK, "recorded parents are known specimens",
          "%d specimen(s) name a parent no longer on the record: %s"
          % (len(orphans), ", ".join(orphans[:4])) if orphans else "descent is closed")


# ------------------------------------------------------------- classification
def check_classification(d, r) -> None:
    rows = d["shifts"]
    if not rows:
        r.add(SKIP, "classification", "no shift has been committed")
        return
    classified = sum(row.get("classified", 0) or 0 for row in rows)
    unresolved = sum(row.get("unresolved", 0) or 0 for row in rows)
    attempts = classified + unresolved
    rate = (100.0 * unresolved / attempts) if attempts else 0.0
    r.add(FAIL if rate > 50 else (WARN if rate > 15 else OK),
          "the classifier answers usably",
          "%d of %d attempt(s) returned nothing readable (%.0f%%) — harness "
          "failure, not the Namer declining" % (unresolved, attempts, rate)
          if attempts else "nothing classified yet")

    stats = d["memory"].get("category_stats") or {}
    native = (d["taxonomy"].get("native") or {})
    def count(node):
        if isinstance(node, dict):
            return 1 + sum(count(v) for v in node.values())
        if isinstance(node, list):
            return sum(count(v) for v in node)
        return 0
    nodes = count(native)
    if stats:
        r.add(WARN if nodes < len(stats) else OK, "the taxonomy holds its categories",
              "%d node(s) in the Namer's own structure against %d categories it "
              "files into%s" % (nodes, len(stats),
                                " — the structure is emitted last and is the first "
                                "thing lost to a truncated response" if nodes < len(stats) else ""))

    seen, redeclared = set(), 0
    for row in rows:
        for c in (row.get("new_categories") or []):
            if c in seen:
                redeclared += 1
            seen.add(c)
    r.add(WARN if redeclared else OK, "a category is coined once",
          "%d coinage event(s) re-declare a category already coined" % redeclared
          if redeclared else "%d distinct categor(ies)" % len(seen))


# ------------------------------------------------------------------ economy
def check_economy(d, r) -> None:
    world = d["memory"].get("world") or {}
    ind = world.get("individuals") or {}
    if not ind:
        r.add(SKIP, "light economy", "nothing living")
        return
    negative = [k for k, v in ind.items() if (v.get("light") or 0) < 0]
    r.add(WARN if negative else OK, "no living specimen holds negative light",
          "%d do: %s" % (len(negative), ", ".join(negative[:4])) if negative
          else "%d individual(s)" % len(ind))
    cells = world.get("cells") or []
    bad = [c.get("index") for c in cells if (c.get("residue") or 0) < 0
           or (c.get("census_density") or 0) < 0]
    r.add(FAIL if bad else OK, "cover and residue are never negative",
          "%d cell(s) below zero" % len(bad) if bad else "%d cell(s)" % len(cells))


CHECKS = [("landscape", check_landscape), ("record", check_record),
          ("classification", check_classification), ("economy", check_economy)]


def verify(terrain: str) -> Report:
    d = _load(terrain)
    r = Report(terrain)
    for _, fn in CHECKS:
        try:
            fn(d, r)
        except Exception as exc:
            r.add(FAIL, "%s checks ran" % fn.__name__, "raised %s" % exc)
    return r


def main(argv: List[str]) -> int:
    wanted = [a for a in argv[1:] if not a.startswith("-")]
    terrains = wanted or dnt_terrains.dirs()
    worst = 0
    for t in terrains:
        r = verify(t)
        c = r.counts()
        print("\n%s  —  %d ok, %d warn, %d FAIL"
              % (t.upper(), c[OK], c[WARN], c[FAIL]))
        print("-" * 78)
        for status, name, detail in r.rows:
            mark = {FAIL: "FAIL", WARN: "warn", OK: "  ok", SKIP: "  --"}[status]
            print("  %s  %-36s %s" % (mark, name, detail))
        if c[FAIL]:
            worst = 2
        elif c[WARN] and worst < 1:
            worst = 1
    print("")
    return worst


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
