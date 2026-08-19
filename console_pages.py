"""
The console views — every live-state page of a terrain, in the deck's own chrome.

    python3 console_pages.py --all
    python3 console_pages.py basin-03

WHAT THIS WRITES, PER TERRAIN

    terrain.html              the terrain record
    shiftlog.html             the shift log
    categories/<name>.html    a native category record   (console; the paper
                              compendium writes a sheet of the same name under
                              codex/, and they answer different questions)
    specimens/<id>.html       a specimen record
    lineage/<id>.html         a lineage record

  Every one of them sits in dnt_console's frame and carries "Back to
  observation deck", because every one of them is a way of looking at the same
  running terrain rather than a document about it.

WHAT IS NOT DRAWN

  The mockups these follow carry fields the department does not record —
  a category's "rank" and "confidence in definition", a live RUNNING clock, an
  authority that filed a report. Where a field has no source it is either shown
  as absent, in words, or it is not shown. Nothing on any of these pages is a
  number that was not read from this terrain's own logs.

Python 3.9 compatible. Reads only; writes HTML.
"""

from __future__ import annotations

import json, math, os, sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import dnt_console as C
import dnt_data

TERRAINS = ["basin-01", "basin-02", "basin-03", "basin-04"]

# The same hues the observation deck colours its population with, so a class
# reads the same on the deck and in the record.
LIVELIHOOD = [
    ("taker",     "#d4614a", "draws from others"),
    ("donor",     "#7f6fae", "gives to others"),
    ("scavenger", "#c9a227", "lives on remains"),
    ("grazer",    "#6f9f5f", "grazes the mat"),
    ("nascent",   "#5a6b78", "not yet feeding"),
]


def esc(v: Any) -> str:
    return (str(v if v is not None else "—").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def num(v) -> str:
    if isinstance(v, float):
        return "{:,.3f}".format(v) if abs(v) < 100 else "{:,.1f}".format(v)
    if isinstance(v, int):
        return "{:,}".format(v)
    return esc(v)


def livelihood_of(b: Dict[str, Any]) -> Tuple[str, str, str]:
    drawn = (b.get("drawn_from_census", 0.0) + b.get("drawn_from_residue", 0.0)
             + b.get("drawn_from_links", 0.0))
    if drawn <= 0:
        return LIVELIHOOD[4]
    links = b.get("drawn_from_links", 0.0) / drawn
    residue = b.get("drawn_from_residue", 0.0) / drawn
    if links > 0.20:
        return LIVELIHOOD[0]
    if b.get("given_to_links", 0.0) > 0.8 and links < 0.05:
        return LIVELIHOOD[1]
    if residue > 0.45:
        return LIVELIHOOD[2]
    return LIVELIHOOD[3]


def spark(series: List[float], w: int = 300, h: int = 60,
          colour: str = "var(--moss)") -> str:
    pts = [v for v in series if v is not None]
    if len(pts) < 2:
        return '<p class="absent">not enough shifts recorded to draw a line</p>'
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    step = w / float(len(pts) - 1)
    d = " ".join("%.1f,%.1f" % (i * step, h - (v - lo) / span * (h - 6) - 3)
                 for i, v in enumerate(pts))
    return ('<svg viewBox="0 0 %d %d" preserveAspectRatio="none" class="spark" '
            'role="img" aria-label="%d points, %s to %s">'
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="1.4"/></svg>'
            % (w, h, len(pts), num(lo), num(hi), d, colour))


def link_specimen(d, sid, label=None):
    """A specimen link, but only where that specimen has a page."""
    label = label if label is not None else esc(sid)
    if sid in d.get("_pages", ()):
        return '<a href="/%s/specimens/%s.html">%s</a>' % (d["dir"], esc(sid), label)
    return label


def load(terrain: str) -> Optional[Dict[str, Any]]:
    d = dnt_data.load(terrain)
    if not d:
        return None
    m = d["memory"]
    d["world"] = m.get("world") or {}
    d["individuals"] = d["world"].get("individuals") or {}
    d["shift"] = m.get("last_committed_shift")
    rows = d["shifts"]
    d["committed_at"] = rows[-1].get("end_timestamp") if rows else None
    d["name"] = m.get("terrain_name") or terrain.upper()
    # The Namer's latest word on each specimen it has looked at individually.
    latest: Dict[str, Dict[str, Any]] = {}
    for r in d["specimens"]:
        c = r.get("classification") or {}
        if r.get("specimen_id") and c.get("category"):
            latest[r["specimen_id"]] = dict(c, shift=r.get("shift"),
                                            record_tier=r.get("record_tier"))
    d["named"] = latest
    return d


CSS = """
.spark{width:100%;height:auto;display:block}
.rowlink{display:grid;grid-template-columns:auto 1fr auto;gap:9px;align-items:center;
padding:7px 13px;border-bottom:1px solid var(--rule);text-decoration:none;color:var(--ink);
font:11px var(--mono)}
.rowlink:last-child{border-bottom:none}
.rowlink:hover{background:var(--panel2)}
.rowlink.on{background:var(--rule)}
.rowlink .n{color:var(--dim);font-variant-numeric:tabular-nums}
.rowlink .s{display:block;color:var(--dim);font-size:9.5px}
.say{font:11.5px/1.7 var(--mono);color:var(--ink);margin:0;
border-left:2px solid var(--rule);padding-left:11px}
.searchbox{width:100%;background:var(--bg);border:1px solid var(--rule);color:var(--ink);
font:11px var(--mono);padding:7px 9px;margin-bottom:2px}
.searchbox::placeholder{color:var(--faint)}
.hidden{display:none}
.legend{display:flex;gap:16px;flex-wrap:wrap;font:10px var(--mono);color:var(--dim);
align-items:center}
.legend span{display:flex;gap:6px;align-items:center}
.tree{display:flex;gap:26px;overflow-x:auto;padding-bottom:6px}
.gen{min-width:150px}
.genh{font:9px var(--mono);letter-spacing:.11em;text-transform:uppercase;color:var(--dim);
border-bottom:1px solid var(--rule);padding-bottom:6px;margin-bottom:9px}
.node{border:1px solid var(--rule);background:var(--panel2);padding:8px 10px;margin-bottom:8px;
font:10.5px var(--mono);text-decoration:none;color:var(--ink);display:block}
.node:hover{border-color:var(--moss2)}
.node.root{border-color:var(--moss2)}
.node .c{color:var(--dim);font-size:9.5px;display:block;margin-top:2px}
.hist{display:flex;gap:2px;align-items:flex-end;height:44px}
.hist i{flex:1;background:var(--moss2);display:block;min-height:1px}
"""


# ===========================================================================
# terrain record
# ===========================================================================
def terrain_record(d: Dict[str, Any]) -> str:
    t, m = d["dir"], d["memory"]
    rows, ind = d["shifts"], d["individuals"]
    cells = d["world"].get("cells") or []
    cats = m.get("category_stats") or {}
    cover = sum(1 for c in cells if c.get("census_density", 0) > 0)
    links = len([1 for v in (d["world"].get("links") or {}).values()
                 if v.get("formed_at_shift") is not None])
    kids = sum(1 for b in ind.values() if b.get("parent_id"))
    events = m.get("terrain_events")
    events = events if isinstance(events, list) else ([events] if events else [])
    pop = [r.get("living") for r in rows]

    gov = dnt_data.governing_conditions(t)
    grows = "".join(
        '<tr><td>%s</td><td class="%s">%s</td><td class="dim">%s</td></tr>'
        % (esc(g["label"]), "" if g["present"] else "absent",
           esc(g["value"]) if g["present"] else "no mechanism in this terrain",
           esc(g["governs"]))
        for g in gov)

    div = dnt_data.shannon_diversity([c.get("count", 0) for c in cats.values()])
    stab = dnt_data.coefficient_of_variation(pop[-40:])
    anom = dnt_data.per_hundred_shifts(
        sum(r.get("anomalous", 0) or 0 for r in rows), len(rows))
    derived = "".join(
        '<tr><td>%s</td><td class="num">%s</td><td class="dim">%s · %s</td></tr>'
        % (label, "—" if value is None else "%.4f" % value,
           dnt_data.DEFINITIONS[key][0], dnt_data.DEFINITIONS[key][1])
        for label, value, key in (("classification diversity", div, "diversity"),
                                  ("population stability", stab, "stability"),
                                  ("anomaly rate", anom, "anomaly rate")))

    evrows = "".join(
        '<tr><td class="num">%s</td><td style="color:var(--moss)">%s</td>'
        '<td class="dim">%s</td><td class="dim num">%s</td></tr>'
        % (esc(e.get("shift")), esc(e.get("kind")),
           esc((e.get("detail") or e.get("note") or "")[:150]),
           esc((e.get("logged_at") or "").replace("T", " ").replace("Z", "")))
        for e in reversed(events[-14:])) or \
        '<tr><td colspan="4" class="absent">no terrain events on the record</td></tr>'

    # class breakdown of the living population
    tally: Dict[str, int] = {}
    for b in ind.values():
        tally[livelihood_of(b)[0]] = tally.get(livelihood_of(b)[0], 0) + 1
    total = max(1, len(ind))
    classes = "".join(
        '<div class="mini"><span><i class="sw" style="background:%s"></i> %s</span>'
        '%s<b>%s</b></div>' % (hue, label, C.bar(tally.get(key, 0) / float(total), hue),
                               num(tally.get(key, 0)))
        for key, hue, label in LIVELIHOOD)

    catrows = "".join(
        '<a class="rowlink" href="/%s/categories/%s.html">'
        '<span></span><span>%s<span class="s">first seen shift %s · last shift %s</span></span>'
        '<span class="n">%s</span></a>'
        % (t, slug(name), esc(name), esc(c.get("first_seen_shift")),
           esc(c.get("last_seen_shift")), num(c.get("count", 0)))
        for name, c in sorted(cats.items(), key=lambda kv: -kv[1].get("count", 0))[:14])

    left = C.panel("Terrains", "".join(
        '<a class="rowlink%s" href="/%s/terrain.html"><span></span>'
        '<span>%s<span class="s">shift %s</span></span><span></span></a>'
        % (" on" if x == t else "", x, x.upper(),
           esc((dnt_data.load(x) or {}).get("memory", {}).get("last_committed_shift", "—")))
        for x in TERRAINS if os.path.isdir(os.path.join(ROOT, x))), flush=True) + \
        C.panel("This terrain", C.kv([
            ("shift log", '<a href="/%s/shiftlog.html">open →</a>' % t),
            ("checkpoints", '<a href="/%s/checkpoint.html">open →</a>' % t
             if os.path.exists(os.path.join(ROOT, t, "checkpoint.html")) else "not yet built"),
            ("comparative study", '<a href="/study.html">open →</a>'
             if os.path.exists(os.path.join(ROOT, "study.html")) else "not yet built"),
        ])) + \
        C.panel("About terrains",
                '<p class="note">Terrains are bounded digital environments seeded and '
                'stewarded by DNT under defined governing conditions. Each terrain is an '
                'autonomous system. We do not design. We observe.</p>')

    right = C.panel("Terrain status", C.kv([
        ("current shift", num(d["shift"])),
        ("last committed", esc((d["committed_at"] or "—").replace("T", " ").replace("Z", ""))),
        ("shifts on record", num(len(rows))),
        ("cumulative spend", "$%.4f" % float(m.get("cumulative_cost_usd", 0.0))),
        ("phase", esc(rows[-1].get("phase") if rows else "—")),
        ("model", esc(rows[-1].get("model") if rows else "—")),
    ])) + C.panel("Population over time", spark(pop, 300, 74),
                  "%d shifts" % len(rows)) + \
        C.panel("The living, by how they feed", classes,
                "%s living" % num(len(ind))) + \
        C.panel("Classification summary", C.kv([
            ("native categories", num(len(cats))),
            ("classified specimens", num(len(d["named"]))),
            ("descendant threads", num(kids)),
            ("active links", num(links)),
        ]))

    mid = (
        '<div class="hdr"><div><p class="eyebrow">Terrains · %s</p>'
        '<h1 class="doc">%s</h1>'
        '<p class="sub">%s</p></div>'
        '<table class="doc">'
        '<tr><td class="k">DOCUMENT</td><td class="v">DNT-T%s</td></tr>'
        '<tr><td class="k">SHIFT</td><td class="v">%s</td></tr>'
        '<tr><td class="k">PHYSICS</td><td class="v">%s</td></tr>'
        '<tr><td class="k">STATUS</td><td class="v">ACTIVE</td></tr></table></div>'
        % (esc(d["name"]), esc(d["name"]),
           esc(m.get("physics_document") or "one terrain, as its own logs describe it"),
           esc(str(m.get("terrain_id") or "")[-2:]), esc(d["shift"]),
           esc(m.get("physics_document") or "—")))

    mid += C.stats([
        (num(d["shift"]), "age", "shifts on the record"),
        (num(len(ind)), "living specimens", "counted now"),
        (num(cover), "cover layer", "of %s cells" % num(len(cells))),
        (num(kids), "descendant threads", "with a parent still living"),
        (num(links), "active links", "between specimens"),
        (num(len(cats)), "native categories", "coined by the Namer"),
    ])

    mid += C.panel(
        "Governing conditions",
        '<p class="note" style="margin:0 0 11px">Each row names the quantity it governs. '
        'A condition this terrain does not have is shown as absent rather than given a '
        'value.</p><div class="scroll"><table class="d">'
        '<thead><tr><th>condition</th><th>value</th><th>what it governs</th></tr></thead>'
        '<tbody>%s</tbody></table></div>' % grows)

    mid += ('<div class="cols2">%s%s</div>'
            % (C.panel("Derived quantities",
                       '<div class="scroll"><table class="d"><tbody>%s</tbody></table></div>'
                       '<p class="note">Published definitions only. Each formula is printed '
                       'beside its value so the number can be checked rather than trusted.'
                       '</p>' % derived),
               C.panel("Native categories", catrows or
                       '<p class="absent">none coined yet</p>',
                       '<a href="/%s/codex.html">field compendium →</a>' % t
                       if os.path.exists(os.path.join(ROOT, t, "codex.html")) else "",
                       flush=bool(catrows))))

    mid += C.panel("Terrain events",
                   '<div class="scroll"><table class="d"><thead><tr><th class="num">shift</th>'
                   '<th>kind</th><th>first line of the record</th><th class="num">logged</th>'
                   '</tr></thead><tbody>%s</tbody></table></div>'
                   '<p class="note">%d event(s) on the record. Each is a logged amendment or '
                   'occurrence, never a summary.</p>' % (evrows, len(events)))

    return C.page("%s — Terrain Record" % d["name"], "TERRAIN RECORD", t,
                  [("TERRAINS", C.HUB + "/hub.html"), (d["name"], None)],
                  d["shift"], d["committed_at"], mid, left, right, CSS,
                  current="terrain")


def slug(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(name).lower())


# ===========================================================================
# shift log
# ===========================================================================
def shift_log(d: Dict[str, Any]) -> str:
    t, m, rows = d["dir"], d["memory"], d["shifts"]
    recent = list(reversed(rows))[:120]
    last = rows[-1] if rows else {}
    prev = rows[-2] if len(rows) > 1 else {}

    def delta(key):
        a, b = last.get(key), prev.get(key)
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            return ""
        diff = a - b
        if not diff:
            return '<span class="dim">no change</span>'
        return ('<span class="%s">%+s</span>'
                % ("up" if diff > 0 else "down", num(diff)))

    body = "".join(
        '<tr><td class="num">%s</td><td class="dim">%s</td><td class="num">%s</td>'
        '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
        '<td class="num">%s</td><td class="num">%s</td><td class="dim">%s</td>'
        '<td class="dim">%s</td></tr>'
        % (esc(r.get("shift")),
           esc((r.get("end_timestamp") or "").replace("T", " ").replace("Z", "")),
           num(r.get("living")), num(r.get("arose_this_shift")),
           num(r.get("ended_this_shift")), num(r.get("replicated_this_shift")),
           num(r.get("links_formed")), num(r.get("classified")),
           esc(", ".join(r.get("new_categories") or []) or "—"), esc(r.get("phase")))
        for r in recent)

    # what a shift costs and what it produced, most recent first
    strip = C.stats([
        (num(len(rows)), "shifts", "on the record"),
        (num(last.get("living")), "living", delta("living")),
        (num(len(m.get("category_stats") or {})), "native categories",
         "+%s this shift" % num(len(last.get("new_categories") or []))),
        (num(last.get("arose_this_shift")), "arose", "this shift"),
        (num(last.get("ended_this_shift")), "ended", "this shift"),
        (num(last.get("classified")), "classified", "this shift"),
    ])

    events = m.get("terrain_events")
    events = events if isinstance(events, list) else ([events] if events else [])
    evs = "".join(
        '<div class="rowlink"><span class="sw" style="background:var(--amber)"></span>'
        '<span>%s<span class="s">shift %s · %s</span></span><span></span></div>'
        % (esc(e.get("kind")), esc(e.get("shift")),
           esc((e.get("logged_at") or "").replace("T", " ").replace("Z", "")))
        for e in reversed(events[-10:])) or \
        '<p class="absent">no terrain events</p>'

    left = C.panel("Select terrain", "".join(
        '<a class="rowlink%s" href="/%s/shiftlog.html"><span></span>'
        '<span>%s</span><span></span></a>' % (" on" if x == t else "", x, x.upper())
        for x in TERRAINS if os.path.isdir(os.path.join(ROOT, x))), flush=True) + \
        C.panel("Log navigation", C.kv([
            ("terrain record", '<a href="/%s/terrain.html">open →</a>' % t),
            ("observation deck",
             '<a href="http://127.0.0.1:%d/index.html">open →</a>' % C.PORTS.get(t, 8731)),
        ])) + \
        C.panel("What a column means",
                '<p class="note">Every column is a value the shift itself recorded when it '
                'closed. Nothing on this page is recomputed, averaged, or filled in — a '
                'blank is a field that shift did not write.</p>')

    right = C.panel("Shift context", C.kv([
        ("current shift", num(d["shift"])),
        ("committed", esc((d["committed_at"] or "—").replace("T", " ").replace("Z", ""))),
        ("duration", "%.1fs" % float(last.get("duration_seconds") or 0)),
        ("phase", esc(last.get("phase"))),
        ("model", esc(last.get("model"))),
        ("model calls", num(last.get("model_calls"))),
        ("cost this shift", "$%.6f" % float(last.get("estimated_cost_usd") or 0)),
        ("cumulative", "$%.4f" % float(last.get("cumulative_cost_usd") or 0)),
    ])) + C.panel("Terrain events", evs, "%d on record" % len(events), flush=True) + \
        C.panel("Living, last %d shifts" % min(60, len(rows)),
                spark([r.get("living") for r in rows[-60:]], 290, 64))

    mid = ('<div class="hdr"><div><p class="eyebrow">%s · shift log</p>'
           '<h1 class="doc">Shift Log</h1>'
           '<p class="sub">Chronological record of observed changes and system events.</p>'
           '</div><table class="doc">'
           '<tr><td class="k">DOCUMENT</td><td class="v">DNT-SHL</td></tr>'
           '<tr><td class="k">TERRAIN</td><td class="v">%s</td></tr>'
           '<tr><td class="k">SHIFTS</td><td class="v">%s</td></tr>'
           '<tr><td class="k">THROUGH</td><td class="v">%s</td></tr></table></div>'
           % (esc(d["name"]), esc(d["name"]), num(len(rows)), esc(d["shift"])))
    mid += strip
    mid += C.panel(
        "Shifts, newest first",
        '<div class="scroll"><table class="d"><thead><tr>'
        '<th class="num">shift</th><th>committed</th><th class="num">living</th>'
        '<th class="num">arose</th><th class="num">ended</th><th class="num">replicated</th>'
        '<th class="num">links</th><th class="num">classified</th>'
        '<th>categories coined</th><th>phase</th></tr></thead><tbody>%s</tbody></table></div>'
        '<p class="note">Showing the most recent %d of %d shifts.</p>'
        % (body, len(recent), len(rows)))

    return C.page("%s — Shift Log" % d["name"], "SHIFT LOG", t,
                  [("TERRAINS", C.HUB + "/hub.html"),
                   (d["name"], "/%s/terrain.html" % t), ("SHIFT LOG", None)],
                  d["shift"], d["committed_at"], mid, left, right, CSS,
                  current="shiftlog")


# ===========================================================================
# native category record
# ===========================================================================
def category_record(d: Dict[str, Any], name: str, members: List[str],
                    ever: List[Dict[str, Any]]) -> str:
    """One native category, as the live record describes it.

    `members` are living specimens the Namer has filed here; `ever` is every
    specimen-log entry ever filed here, living or not.
    """
    t, m = d["dir"], d["memory"]
    stat = (m.get("category_stats") or {}).get(name) or {}
    ind = d["individuals"]
    alive = [ind[i] for i in members if i in ind]
    total_ever = len({r.get("specimen_id") for r in ever})

    # class size over time: first sighting per specimen, cumulated
    firsts: Dict[str, int] = {}
    for r in ever:
        sid, s = r.get("specimen_id"), r.get("shift")
        if sid is not None and s is not None:
            firsts[sid] = min(firsts.get(sid, s), s)
    series = []
    if firsts:
        hi = max(firsts.values())
        running = 0
        counts = {}
        for s in firsts.values():
            counts[s] = counts.get(s, 0) + 1
        for s in range(min(firsts.values()), hi + 1):
            running += counts.get(s, 0)
            series.append(running)

    # distribution by elevation band, from the cells the living actually stand in
    bands = [("high", 0.66, 1.01), ("mid", 0.33, 0.66), ("low", -0.01, 0.33)]
    elev: Dict[str, int] = {}
    cellinfo = {c["index"]: c for c in (d["world"].get("cells") or [])}
    positioned = 0
    for b in alive:
        c = cellinfo.get(b.get("cell"))
        if not c:
            continue
        p = float(c.get("position", 0.0))
        positioned += 1
        for label, lo, hi2 in bands:
            if lo <= p < hi2:
                elev[label] = elev.get(label, 0) + 1
                break
    dist = "".join(
        '<div class="mini"><span>%s (%.2f – %.2f)</span>%s<b>%s</b></div>'
        % (label, lo if lo > 0 else 0.0, hi2 if hi2 < 1 else 1.0,
           C.bar(elev.get(label, 0) / float(max(1, positioned))), num(elev.get(label, 0)))
        for label, lo, hi2 in bands) if positioned else \
        '<p class="absent">no living member of this category is currently placed</p>'

    # how the living members of this category make their living
    tally: Dict[str, int] = {}
    for b in alive:
        tally[livelihood_of(b)[0]] = tally.get(livelihood_of(b)[0], 0) + 1
    feeds = "".join(
        '<div class="mini"><span><i class="sw" style="background:%s"></i> %s</span>'
        '%s<b>%s</b></div>'
        % (hue, label, C.bar(tally.get(k, 0) / float(max(1, len(alive))), hue),
           num(tally.get(k, 0)))
        for k, hue, label in LIVELIHOOD if tally.get(k))

    # the Namer's own words, most recent first
    words = [r for r in ever if (r.get("classification") or {}).get("reasoning")]
    basis = ""
    if words:
        c = words[-1]["classification"]
        basis = ('<p class="say">%s</p><p class="note">Filed on %s, for %s. This is the '
                 'most recent reasoning the Namer wrote for a member of this category; it '
                 'is not a definition of the category, because the Namer never wrote one.'
                 '</p>' % (esc(c.get("reasoning", "")[:900]), esc(words[-1].get("shift")),
                           esc(words[-1].get("specimen_id"))))
    else:
        basis = '<p class="absent">no reasoning recorded for any member</p>'

    # measurements across the living members
    def spread(fn):
        vals = [fn(b) for b in alive if fn(b) is not None]
        if not vals:
            return None
        vals.sort()
        return (vals[0], vals[len(vals) // 2], vals[-1],
                sum(vals) / float(len(vals)))
    measures = []
    for label, fn in (("age (shifts)", lambda b: b.get("age")),
                      ("light held", lambda b: b.get("light")),
                      ("mass", lambda b: (b.get("structure") or {}).get("mass")),
                      ("reach", lambda b: (b.get("structure") or {}).get("extent")),
                      ("descendants", lambda b: b.get("descendants")),
                      ("moves", lambda b: b.get("moves"))):
        s = spread(fn)
        measures.append(
            '<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td class="num">%s</td></tr>'
            % (label, num(s[0]), num(s[3]), num(s[1]), num(s[2])) if s else
            '<tr><td>%s</td><td colspan="4" class="absent">not recorded</td></tr>' % label)

    memrows = "".join(
        '<a class="rowlink" href="/%s/specimens/%s.html"><span class="sw" '
        'style="background:%s"></span><span>%s<span class="s">%s · %s shift(s) · '
        'holding %.1f</span></span><span class="n">%s</span></a>'
        % (t, esc(b["id"]), livelihood_of(b)[1], esc(b["id"]), livelihood_of(b)[2],
           num(b.get("age")), float(b.get("light", 0)), num(b.get("descendants")))
        for b in sorted(alive, key=lambda x: -(x.get("age") or 0))[:40])

    cats = m.get("category_stats") or {}
    left = C.panel(
        "Native categories",
        '<div class="pb" style="padding:9px 11px 4px"><input class="searchbox" id="q" '
        'placeholder="search categories…"></div>' +
        "".join(
            '<a class="rowlink%s" data-n="%s" href="/%s/categories/%s.html">'
            '<span class="sw" style="background:%s"></span>'
            '<span>%s<span class="s">first seen shift %s</span></span>'
            '<span class="n">%s</span></a>'
            % (" on" if k == name else "", esc(k.lower()), t, slug(k),
               "var(--moss2)" if k == name else "var(--rule)",
               esc(k), esc(v.get("first_seen_shift")), num(v.get("count", 0)))
            for k, v in sorted(cats.items(), key=lambda kv: -kv[1].get("count", 0))),
        flush=True)

    right = C.panel("Class overview", C.kv([
        ("first seen", "shift %s" % esc(stat.get("first_seen_shift"))),
        ("last seen", "shift %s" % esc(stat.get("last_seen_shift"))),
        ("mean complexity", num(stat.get("mean_complexity"))),
        ("category rank", "not recorded", True),
        ("confidence in definition", "not recorded", True),
        ("revision count", "not recorded", True),
    ])) + \
        '<p class="note" style="padding:0 13px 13px">The last three are fields the mockup ' \
        'carries and the department does not record. The Namer coins a category and files ' \
        'specimens into it; it never rates its own confidence or versions a definition.</p>' + \
        C.panel("Distribution by gradient band", dist,
                "%s placed" % num(positioned)) + \
        (C.panel("How its members feed", feeds) if feeds else "") + \
        C.panel("Elsewhere", C.kv([
            ("field-guide sheet", '<a href="/%s/codex/%s.html">open →</a>'
             % (t, slug(name)) if os.path.exists(
                 os.path.join(ROOT, t, "codex", slug(name) + ".html"))
             else '<a href="/%s/codex.html">compendium →</a>' % t),
            ("crosswalk", '<a href="/%s/crosswalk.html">open →</a>' % t
             if os.path.exists(os.path.join(ROOT, t, "crosswalk.html")) else "no pass yet"),
            ("terrain record", '<a href="/%s/terrain.html">open →</a>' % t),
        ]))

    mid = ('<div class="hdr"><div><p class="eyebrow">Native classification</p>'
           '<h1 class="doc mono">%s</h1>'
           '<p class="sub">A category the Namer coined and files specimens into. '
           'Nothing here defines it — the department has no definition, only the '
           'record of what was filed and why.</p></div>'
           '<table class="doc">'
           '<tr><td class="k">TERRAIN</td><td class="v">%s</td></tr>'
           '<tr><td class="k">SHIFT</td><td class="v">%s</td></tr>'
           '<tr><td class="k">COINED BY</td><td class="v">THE NAMER</td></tr>'
           '<tr><td class="k">FIRST SEEN</td><td class="v">SHIFT %s</td></tr>'
           '</table></div>'
           % (esc(name), esc(d["name"]), esc(d["shift"]),
              esc(stat.get("first_seen_shift"))))

    mid += C.stats([
        (num(total_ever), "classified", "lifetime"),
        (num(len(alive)), "living", "counted now"),
        (num(total_ever - len(alive)), "no longer living", "of the classified"),
        (num(stat.get("count", 0)), "in category_stats", "as the Keeper counts"),
        (num(max([b.get("generation", 0) for b in alive] or [0])), "deepest generation",
         "among the living"),
    ])

    mid += ('<div class="cols2">%s%s</div>'
            % (C.panel("Class size over time",
                       spark(series, 400, 90) if len(series) > 1 else
                       '<p class="absent">too few sightings to draw a line</p>',
                       "cumulative first sightings"),
               C.panel("Measurements across the living",
                       '<div class="scroll"><table class="d"><thead><tr><th></th>'
                       '<th class="num">lowest</th><th class="num">mean</th>'
                       '<th class="num">median</th><th class="num">highest</th></tr></thead>'
                       '<tbody>%s</tbody></table></div>' % "".join(measures))))

    mid += C.panel("The Namer's basis", basis)
    mid += C.panel("Living members", memrows or
                   '<p class="absent">no member of this category is currently living</p>',
                   "showing %d of %s" % (min(40, len(alive)), num(len(alive))),
                   flush=bool(memrows))

    script = ("<script>var q=document.getElementById('q');if(q)q.oninput=function(){"
              "var v=q.value.toLowerCase();"
              "document.querySelectorAll('.rowlink[data-n]').forEach(function(r){"
              "r.classList.toggle('hidden', r.dataset.n.indexOf(v)<0)})};</script>")

    return C.page("%s — %s" % (esc(name), d["name"]), "CATEGORY RECORD", t,
                  [("TERRAINS", C.HUB + "/hub.html"),
                   (d["name"], "/%s/terrain.html" % t),
                   ("NATIVE CLASSIFICATION", None), (esc(name).upper(), None)],
                  d["shift"], d["committed_at"], mid, left, right, CSS,
                  current="category", scripts=script)


# ===========================================================================
# specimen record
# ===========================================================================
def specimen_record(d: Dict[str, Any], sid: str, sightings: List[Dict[str, Any]]) -> str:
    t = d["dir"]
    ind = d["individuals"]
    b = ind.get(sid) or {}
    alive = sid in ind
    named = d["named"].get(sid) or {}
    st = b.get("structure") or {}
    aff = b.get("traits") or {}
    drawn = (b.get("drawn_from_census", 0.0) + b.get("drawn_from_residue", 0.0)
             + b.get("drawn_from_links", 0.0))
    share = (lambda v: v / drawn if drawn else 0.0)
    hue = livelihood_of(b)[1] if b else "var(--faint)"

    cellinfo = {c["index"]: c for c in (d["world"].get("cells") or [])}
    cell = cellinfo.get(b.get("cell")) or {}

    # ---- composition
    comp = "".join(
        '<div class="mini"><span>%s</span>%s<b>%d%%</b></div>'
        % (label, C.bar(share(v), colour), round(share(v) * 100))
        for label, v, colour in (
            ("from the cover layer", b.get("drawn_from_census", 0.0), "var(--moss)"),
            ("from remains", b.get("drawn_from_residue", 0.0), "var(--amber)"),
            ("along links", b.get("drawn_from_links", 0.0), "var(--rose)"))) \
        if drawn else '<p class="absent">nothing recorded as taken in yet</p>'

    # ---- descendants and parent
    kids = sorted([k for k, v in ind.items() if v.get("parent_id") == sid])
    parent = b.get("parent_id")
    lineage_rows = "".join(
        '<%s class="rowlink"%s><span class="sw" style="background:%s"></span>'
        '<span>%s<span class="s">%s shift(s)</span></span>'
        '<span class="n">gen %s</span></%s>'
        % ("a" if k in d.get("_pages", ()) else "div",
           ' href="/%s/specimens/%s.html"' % (t, esc(k))
           if k in d.get("_pages", ()) else "",
           livelihood_of(ind[k])[1], esc(k), num(ind[k].get("age")),
           num(ind[k].get("generation")),
           "a" if k in d.get("_pages", ()) else "div")
        for k in kids[:12]) or '<p class="absent">no living descendants</p>'

    # ---- sighting history: which shifts this specimen was written up on
    shifts_seen = sorted({r.get("shift") for r in sightings if r.get("shift") is not None})
    hist = ""
    if shifts_seen:
        lo, hi = min(shifts_seen), max(shifts_seen)
        seen = set(shifts_seen)
        hist = ('<div class="hist">%s</div>'
                '<p class="note">Shift %s to %s. A bar is a shift on which the Namer wrote '
                'this specimen up; a gap is a shift on which it did not. %d sighting(s) '
                'across %d shifts.</p>'
                % ("".join('<i style="height:%d%%;opacity:%s"></i>'
                           % (100 if s in seen else 8, "1" if s in seen else ".35")
                           for s in range(lo, hi + 1)),
                   lo, hi, len(sightings), hi - lo + 1))
    else:
        hist = '<p class="absent">never written up individually</p>'

    # ---- state history from the specimen log
    state_rows = "".join(
        '<tr><td class="num">%s</td><td class="dim">%s</td><td>%s</td>'
        '<td class="dim">%s</td></tr>'
        % (esc(r.get("shift")),
           esc((r.get("logged_at") or "").replace("T", " ").replace("Z", "")),
           esc((r.get("classification") or {}).get("category") or "—"),
           esc((r.get("classification") or {}).get("decision") or "—"))
        for r in reversed(sightings[-24:])) or \
        '<tr><td colspan="4" class="absent">no entries</td></tr>'

    # ---- reproduction
    repro = C.kv([
        ("generation", num(b.get("generation"))),
        ("descended from", link_specimen(d, parent)
         if parent else "arose from the census, not from a parent"),
        ("descendants recorded", num(b.get("descendants"))),
        ("descendants still living", num(len(kids))),
        ("arose at shift", num(b.get("arose_at_shift"))),
        ("origin", esc((b.get("origin") or "").replace("_", " "))),
    ])

    # ---- tabs
    overview = (
        '<div class="cols2">%s%s</div>%s'
        % (C.panel("Behaviour summary", C.kv([
               ("makes its living by", livelihood_of(b)[2] if b else "—"),
               ("moved", "%s time(s)" % num(b.get("moves"))),
               ("standing in cell", num(b.get("cell"))),
               ("position on the gradient", num(cell.get("position"))),
               ("cover where it stands", num(cell.get("census_density"))),
               ("remains where it stands", num(cell.get("residue"))),
           ])),
           C.panel("Lifetime summary", C.kv([
               ("shifts present", num(b.get("age"))),
               ("sightings", num(b.get("sightings"))),
               ("light held now", num(b.get("light"))),
               ("given away along links", num(b.get("given_to_links"))),
               ("record tier", esc(named.get("record_tier") or "—")),
               ("last seen at shift", num(b.get("last_seen_shift"))),
           ])),
           C.panel("How it is built", C.kv([
               ("reach", num(st.get("extent"))),
               ("junctions", "%s — holds up to %s link(s) at once"
                % (num(st.get("junctions")), num(1 + int(st.get("junctions", 0) or 0)))),
               ("carries", num(st.get("mass"))),
               ("affinity: cover", num(aff.get("cover"))),
               ("affinity: remains", num(aff.get("residue"))),
               ("affinity: links", num(aff.get("links"))),
           ]) + '<p class="note">Six inherited numbers. The first three are what it built '
                'and are charged for every shift; the last three are what it is disposed to '
                'draw on, and they sit on a fixed budget.</p>')))

    sightings_pane = C.panel("Sighting history", hist,
                             "%d recorded" % len(sightings))
    state_pane = C.panel(
        "State history",
        '<div class="scroll"><table class="d"><thead><tr><th class="num">shift</th>'
        '<th>logged</th><th>filed as</th><th>decision</th></tr></thead><tbody>%s</tbody>'
        '</table></div><p class="note">Every entry the Namer wrote about this specimen, '
        'newest first. Where the category changes between rows, the Namer refiled it.</p>'
        % state_rows)
    repro_pane = ('<div class="cols2">%s%s</div>'
                  % (C.panel("Reproduction", repro),
                     C.panel("Living descendants", lineage_rows,
                             "%d of %s" % (min(12, len(kids)), num(b.get("descendants"))),
                             flush=bool(kids))))

    words_pane = ""
    if named.get("persistence"):
        words_pane += C.panel("How it persists — the Namer's words",
                              '<p class="say">%s</p>' % esc(named["persistence"]))
    if named.get("reasoning"):
        words_pane += C.panel("Why it was filed here",
                              '<p class="say">%s</p>' % esc(named["reasoning"]))
    if named.get("comparison"):
        words_pane += C.panel("How it compares",
                              '<p class="say">%s</p>' % esc(named["comparison"]))
    if not words_pane:
        words_pane = C.panel("The Namer's words",
                             '<p class="absent">the Namer has not written about this '
                             'specimen individually</p>')

    tabs = [("overview", "Overview", overview),
            ("sightings", "Sightings", sightings_pane),
            ("state", "State history", state_pane),
            ("repro", "Reproduction", repro_pane),
            ("words", "The Namer's words", words_pane)]
    tabbar = '<div class="tabs">%s</div>' % "".join(
        '<button data-tab="%s"%s>%s</button>' % (k, ' class="on"' if i == 0 else "", label)
        for i, (k, label, _) in enumerate(tabs))
    panes = "".join('<div class="tabpane%s" id="tab-%s">%s</div>'
                    % (" on" if i == 0 else "", k, body)
                    for i, (k, _, body) in enumerate(tabs))

    # ---- rails
    others = sorted((k for k in ind if k in d.get("_pages", ())),
                    key=lambda k: -(ind[k].get("age") or 0))[:40]
    left = C.panel(
        "Specimens",
        '<div class="pb" style="padding:9px 11px 4px"><input class="searchbox" id="q" '
        'placeholder="search specimens…"></div>' + "".join(
            '<a class="rowlink%s" data-n="%s" href="/%s/specimens/%s.html">'
            '<span class="sw" style="background:%s"></span>'
            '<span>%s<span class="s">%s</span></span><span class="n">%s</span></a>'
            % (" on" if k == sid else "", esc(k.lower()), t, esc(k),
               livelihood_of(ind[k])[1], esc(k),
               esc((d["named"].get(k) or {}).get("category") or "not yet named"),
               num(ind[k].get("age")))
            for k in others), flush=True)

    right = C.panel("Native classification",
                    '<div style="font:13px var(--mono);color:var(--moss);margin-bottom:8px">'
                    '%s</div>%s'
                    % (esc(named.get("category") or "not yet named"),
                       C.kv([("record tier", esc(named.get("record_tier") or "—")),
                             ("decision", esc(named.get("decision") or "—")),
                             ("last filed at shift", num(named.get("shift"))),
                             ("category record",
                              '<a href="/%s/categories/%s.html">open →</a>'
                              % (t, slug(named["category"])) if named.get("category") else "—")]))) + \
        C.panel("Composition", comp) + \
        C.panel("Lineage", C.kv([
            ("generation", num(b.get("generation"))),
            ("parent", link_specimen(d, parent)
             if parent else "none — arose from the census"),
            ("descendants", num(b.get("descendants"))),
            ("living descendants", num(len(kids))),
            ("lineage record", '<a href="/%s/lineage/%s.html">open →</a>' % (t, esc(sid))
             if sid in d.get("_lineages", ()) else "no recorded descendants"),
        ])) + \
        C.panel("Where it stands", C.kv([
            ("cell", num(b.get("cell"))),
            ("position", num(cell.get("position"))),
            ("cover here", num(cell.get("census_density"))),
            ("remains here", num(cell.get("residue"))),
            ("in the field",
             '<a href="http://127.0.0.1:%d/index.html#%s">open the deck →</a>'
             % (C.PORTS.get(t, 8731), esc(sid)) if alive else "no longer in the field"),
        ]))

    mid = ('<div class="hdr"><div><p class="eyebrow">Specimen record</p>'
           '<h1 class="doc mono">%s</h1>'
           '<p class="sub"><span class="chip %s">%s</span> '
           '<span class="chip">%s</span> <span class="chip">%s</span></p></div>'
           '<table class="doc">'
           '<tr><td class="k">TERRAIN</td><td class="v">%s</td></tr>'
           '<tr><td class="k">SHIFT</td><td class="v">%s</td></tr>'
           '<tr><td class="k">PRESENT FOR</td><td class="v">%s SHIFT(S)</td></tr>'
           '<tr><td class="k">SIGHTINGS</td><td class="v">%s</td></tr></table></div>'
           % (esc(sid), "on" if alive else "off", "LIVING" if alive else "NO LONGER LIVING",
              esc(b.get("substrate") or "—"), esc(livelihood_of(b)[2] if b else "—"),
              esc(d["name"]), esc(d["shift"]), num(b.get("age")), num(b.get("sightings"))))

    mid += C.stats([
        (num(b.get("age")), "shifts present"),
        (num(b.get("light")), "light held"),
        (num(st.get("mass")), "carries"),
        (num(st.get("extent")), "reach"),
        (num(b.get("descendants")), "descendants"),
        (num(b.get("moves")), "moves"),
    ])
    mid += tabbar + panes

    script = ("<script>"
              "document.querySelectorAll('.tabs button').forEach(function(t){"
              "t.onclick=function(){"
              "document.querySelectorAll('.tabs button').forEach(function(x){"
              "x.classList.remove('on')});t.classList.add('on');"
              "document.querySelectorAll('.tabpane').forEach(function(p){"
              "p.classList.toggle('on', p.id==='tab-'+t.dataset.tab)})}});"
              "var q=document.getElementById('q');if(q)q.oninput=function(){"
              "var v=q.value.toLowerCase();"
              "document.querySelectorAll('.rowlink[data-n]').forEach(function(r){"
              "r.classList.toggle('hidden', r.dataset.n.indexOf(v)<0)})};"
              "</script>")

    return C.page("%s — %s" % (esc(sid), d["name"]), "SPECIMEN RECORD", t,
                  [("TERRAINS", C.HUB + "/hub.html"),
                   (d["name"], "/%s/terrain.html" % t), ("SPECIMEN %s" % esc(sid), None)],
                  d["shift"], d["committed_at"], mid, left, right, CSS,
                  current="specimen", scripts=script)


# ===========================================================================
# lineage record
# ===========================================================================
def lineage_record(d: Dict[str, Any], root: str) -> str:
    t = d["dir"]
    ind = d["individuals"]
    kids_of: Dict[str, List[str]] = {}
    for k, v in ind.items():
        p = v.get("parent_id")
        if p:
            kids_of.setdefault(p, []).append(k)

    # walk the tree from the root, breadth first, recording depth
    gens: Dict[int, List[str]] = {0: [root]}
    seen = {root}
    depth = 0
    while gens.get(depth) and depth < 12:
        nxt = []
        for node in gens[depth]:
            for kid in sorted(kids_of.get(node, [])):
                if kid not in seen:
                    seen.add(kid)
                    nxt.append(kid)
        if not nxt:
            break
        depth += 1
        gens[depth] = nxt

    living = [k for k in seen if k in ind]
    b = ind.get(root) or {}

    # trait drift by generation, against the root
    def trait(k, path):
        v = ind.get(k) or {}
        return (v.get("structure") or {}).get(path) if path in ("extent", "junctions", "mass") \
            else (v.get("traits") or {}).get(path)
    base = {p: trait(root, p) for p in ("extent", "junctions", "mass",
                                        "cover", "residue", "links")}
    drift_rows = []
    for p, label in (("extent", "reach"), ("junctions", "junctions"), ("mass", "mass"),
                     ("cover", "affinity: cover"), ("residue", "affinity: remains"),
                     ("links", "affinity: links")):
        cells = []
        for g in sorted(gens):
            if g == 0:
                continue
            vals = [trait(k, p) for k in gens[g] if trait(k, p) is not None]
            if not vals or base.get(p) is None:
                cells.append('<td class="absent">—</td>')
            else:
                delta = sum(vals) / float(len(vals)) - base[p]
                cells.append('<td class="num %s">%+.3f</td>'
                             % ("up" if delta > 0 else ("down" if delta < 0 else "dim"), delta))
        drift_rows.append('<tr><td>%s</td>%s</tr>' % (label, "".join(cells)))
    genhdr = "".join('<th class="num">gen %d</th>' % g for g in sorted(gens) if g)
    drift = ('<div class="scroll"><table class="d"><thead><tr><th>trait</th>%s</tr></thead>'
             '<tbody>%s</tbody></table></div>'
             '<p class="note">The mean of that generation minus the root\'s own value. '
             'Traits are inherited with variation at replication, so this is drift as it '
             'actually happened, not a model of it.</p>' % (genhdr, "".join(drift_rows))) \
        if genhdr else '<p class="absent">this specimen has no recorded descendants</p>'

    # the tree itself, one column per generation
    tree = '<div class="tree">%s</div>' % "".join(
        '<div class="gen"><div class="genh">gen %d · %d</div>%s</div>'
        % (g, len(gens[g]), "".join(
            '<%s class="node%s"%s>%s'
            '<span class="c">%s<br>%s shift(s) · %s kid(s)</span></%s>'
            % ("a" if k in d.get("_pages", ()) else "div", " root" if g == 0 else "",
               ' href="/%s/specimens/%s.html"' % (t, esc(k))
               if k in d.get("_pages", ()) else "", esc(k),
               esc((d["named"].get(k) or {}).get("category") or "not yet named"),
               num((ind.get(k) or {}).get("age")),
               num((ind.get(k) or {}).get("descendants")),
               "a" if k in d.get("_pages", ()) else "div")
            for k in gens[g][:14]) +
           ('<div class="node" style="border-style:dashed;color:var(--dim)">+ %d more</div>'
            % (len(gens[g]) - 14) if len(gens[g]) > 14 else ""))
        for g in sorted(gens))

    branch_lengths = [g for g in sorted(gens) for _ in gens[g]]
    mean_branch = (sum(branch_lengths) / float(len(branch_lengths))) if branch_lengths else 0

    # A member of this lineage only gets a link if it founded a line of its own
    # and therefore has a page; the rest are listed but not linked.
    left = C.panel("Lineage", "".join(
        '<%s class="rowlink%s"%s><span class="sw" '
        'style="background:%s"></span><span>%s<span class="s">gen %s · %s kid(s)</span>'
        '</span><span class="n">%s</span></%s>'
        % ("a" if k in d.get("_lineages", ()) else "div",
           " on" if k == root else "",
           ' href="/%s/lineage/%s.html"' % (t, esc(k))
           if k in d.get("_lineages", ()) else "",
           livelihood_of(ind[k])[1], esc(k),
           num(ind[k].get("generation")), num(ind[k].get("descendants")),
           num(ind[k].get("age")),
           "a" if k in d.get("_lineages", ()) else "div")
        for k in sorted(seen, key=lambda x: ((ind.get(x) or {}).get("generation", 0),
                                             x))[:40]
        if k in d.get("_pages", ())), flush=True)

    right = C.panel("Lineage summary", C.kv([
        ("root specimen", esc(root)),
        ("depth", "%d generation(s)" % depth),
        ("members traced", num(len(seen))),
        ("living now", num(len(living))),
        ("no longer living", num(len(seen) - len(living))),
        ("mean depth", "%.2f generations" % mean_branch),
        ("root's own descendants", num(b.get("descendants"))),
    ])) + C.panel("Members per generation", "".join(
        '<div class="mini"><span>gen %d</span>%s<b>%d</b></div>'
        % (g, C.bar(len(gens[g]) / float(max(len(v) for v in gens.values()))), len(gens[g]))
        for g in sorted(gens))) + \
        C.panel("Elsewhere", C.kv([
            ("specimen record", '<a href="/%s/specimens/%s.html">open →</a>' % (t, esc(root))),
            ("terrain record", '<a href="/%s/terrain.html">open →</a>' % t),
            ("in the field",
             '<a href="http://127.0.0.1:%d/index.html#%s">open the deck →</a>'
             % (C.PORTS.get(t, 8731), esc(root)) if root in ind else "no longer in the field"),
        ])) + \
        C.panel("What is traced",
                '<p class="note">Only recorded parentage. Every edge on this page is a '
                'parent_id the terrain wrote when a specimen replicated; nothing is '
                'inferred from similarity, position, or category. A specimen whose parent '
                'has ended still appears — the record of descent outlives the parent.</p>')

    mid = ('<div class="hdr"><div><p class="eyebrow">Lineage record</p>'
           '<h1 class="doc mono">%s</h1>'
           '<p class="sub">%s · generation %s%s</p></div>'
           '<table class="doc">'
           '<tr><td class="k">TERRAIN</td><td class="v">%s</td></tr>'
           '<tr><td class="k">SHIFT</td><td class="v">%s</td></tr>'
           '<tr><td class="k">DEPTH</td><td class="v">%d GENERATION(S)</td></tr>'
           '<tr><td class="k">TRACED</td><td class="v">%s</td></tr></table></div>'
           % (esc(root), esc((d["named"].get(root) or {}).get("category") or "not yet named"),
              num(b.get("generation")), " (root)" if not b.get("parent_id") else "",
              esc(d["name"]), esc(d["shift"]), depth, num(len(seen))))

    mid += C.stats([
        (num(len(seen)), "traced", "from parentage"),
        (num(len(living)), "living now"),
        ("%d" % depth, "generations", "below the root"),
        (num(b.get("descendants")), "root's descendants"),
        ("%.1f" % mean_branch, "mean depth", "generations"),
    ])
    mid += C.panel("Lineage tree", tree, "one column per generation")
    mid += C.panel("Trait drift by generation", drift)
    return C.page("%s — Lineage" % esc(root), "LINEAGE RECORD", t,
                  [("TERRAINS", C.HUB + "/hub.html"),
                   (d["name"], "/%s/terrain.html" % t),
                   ("SPECIMEN %s" % esc(root), "/%s/specimens/%s.html" % (t, esc(root))),
                   ("LINEAGE", None)],
                  d["shift"], d["committed_at"], mid, left, right, CSS, current="lineage")


# ===========================================================================
# checkpoint report
# ===========================================================================
def checkpoint_report(d: Dict[str, Any], window: int = 14) -> str:
    """A state comparison between two shifts, computed from the shift log.

    The mockup this follows carries a report AUTHORITY, a CONFIDENCE, and an
    AUTHENTIC RECORD seal. No such thing exists: nobody signs off on a terrain
    and the department has no confidence scale. What it has is two rows of the
    shift log and arithmetic between them, and that is what this shows.
    """
    t, m, rows = d["dir"], d["memory"], d["shifts"]
    if len(rows) < 2:
        return ""
    last = rows[-1]
    earlier = rows[max(0, len(rows) - 1 - window)]
    a, b = earlier.get("shift"), last.get("shift")

    def pair(key, label, fmt=num):
        va, vb = earlier.get(key), last.get(key)
        if not isinstance(va, (int, float)) or not isinstance(vb, (int, float)):
            return (label, None, None, None, None)
        diff = vb - va
        pct = (diff / va * 100.0) if va else None
        return (label, va, vb, diff, pct)

    metrics = [pair("living", "living specimens"),
               pair("classified", "classified this shift"),
               pair("arose_this_shift", "arose this shift"),
               pair("ended_this_shift", "ended this shift"),
               pair("replicated_this_shift", "replicated this shift"),
               pair("links_formed", "links formed this shift"),
               pair("resource_flow", "resource flow"),
               pair("cumulative_cost_usd", "cumulative spend")]

    def row(mt):
        label, va, vb, diff, pct = mt
        if va is None:
            return ('<tr><td>%s</td><td colspan="4" class="absent">not recorded at both '
                    'shifts</td></tr>' % label)
        cls = "up" if (diff or 0) > 0 else ("down" if (diff or 0) < 0 else "dim")
        return ('<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
                '<td class="num %s">%+s</td><td class="num %s">%s</td></tr>'
                % (label, num(va), num(vb), cls, num(diff), cls,
                   ("%+.2f%%" % pct) if pct is not None else "—"))

    cats_now = len(m.get("category_stats") or {})
    coined = sorted({c for r in rows[max(0, len(rows) - 1 - window):]
                     for c in (r.get("new_categories") or [])})
    anomalies = sum(r.get("anomalous", 0) or 0
                    for r in rows[max(0, len(rows) - 1 - window):])
    unresolved = sum(r.get("unresolved", 0) or 0
                     for r in rows[max(0, len(rows) - 1 - window):])
    pop = [r.get("living") for r in rows]
    stab = dnt_data.coefficient_of_variation(pop[-window:])

    # the falsification checkpoint physics.md Section 11 actually names
    canon = [r for r in rows if (r.get("phase") or "") != "ollama"]
    left = C.panel("Checkpoints", "".join(
        '<a class="rowlink%s" href="/%s/checkpoint.html"><span></span>'
        '<span>%s<span class="s">shift %s → %s</span></span><span></span></a>'
        % (" on" if x == t else "", x, x.upper(), a, b) for x in [t]), flush=True) + \
        C.panel("Report sections", C.kv([
            ("terrain record", '<a href="/%s/terrain.html">open →</a>' % t),
            ("shift log", '<a href="/%s/shiftlog.html">open →</a>' % t),
            ("comparative study", '<a href="/study.html">open →</a>'
             if os.path.exists(os.path.join(ROOT, "study.html")) else "not yet built"),
        ])) + \
        C.panel("What a checkpoint is",
                '<p class="note">Two rows of this terrain\'s own shift log and the '
                'arithmetic between them. Nobody signs a checkpoint off, the department '
                'has no confidence scale, and no assessment is recorded — those fields '
                'exist in the design mockups and have no source here.</p>')

    right = C.panel("Window", C.kv([
        ("from shift", num(a)),
        ("to shift", num(b)),
        ("shifts in window", num(b - a if isinstance(a, int) and isinstance(b, int) else "—")),
        ("canonical shifts", num(len(canon))),
        ("falsification checkpoint", "15 canonical shifts"),
        ("checkpoint reached",
         "yes" if len(canon) >= 15 else "no — %d to go" % (15 - len(canon))),
    ])) + C.panel("Population across the window",
                  spark(pop[-window - 1:], 290, 64)) + \
        C.panel("Classification", C.kv([
            ("categories now", num(cats_now)),
            ("coined in window", num(len(coined))),
            ("anomalous in window", num(anomalies)),
            ("unresolved in window", num(unresolved)),
        ]) + ('<p class="note">Coined: %s</p>' % esc(", ".join(coined)) if coined else "")) + \
        C.panel("Stability", C.kv([
            ("coefficient of variation", "—" if stab is None else "%.4f" % stab),
        ]) + '<p class="note">CV = σ / μ of the living population across this window. '
             'Lower is steadier. It is a description, not a grade.</p>')

    mid = ('<div class="hdr"><div><p class="eyebrow">%s · checkpoint</p>'
           '<h1 class="doc">Checkpoint Report</h1>'
           '<p class="sub">Shift %s → shift %s. State comparison computed from the '
           'shift log.</p></div><table class="doc">'
           '<tr><td class="k">DOCUMENT</td><td class="v">DNT-CKP</td></tr>'
           '<tr><td class="k">TERRAIN</td><td class="v">%s</td></tr>'
           '<tr><td class="k">WINDOW</td><td class="v">%s SHIFTS</td></tr>'
           '<tr><td class="k">SOURCE</td><td class="v">SHIFT LOG</td></tr></table></div>'
           % (esc(d["name"]), num(a), num(b), esc(d["name"]),
              num(b - a if isinstance(a, int) and isinstance(b, int) else "—")))

    mid += C.stats([
        (num(b - a if isinstance(a, int) and isinstance(b, int) else "—"), "shifts",
         "%s → %s" % (num(a), num(b))),
        (num(last.get("living")), "living", "at shift %s" % num(b)),
        (num(cats_now), "native categories", "+%d in window" % len(coined)),
        (num(anomalies), "anomalous", "in window"),
        (num(unresolved), "unresolved", "harness failures"),
        (num(len(canon)), "canonical shifts", "of 15 at the checkpoint"),
    ])
    mid += C.panel(
        "What changed between the two shifts",
        '<div class="scroll"><table class="d"><thead><tr><th>metric</th>'
        '<th class="num">shift %s</th><th class="num">shift %s</th>'
        '<th class="num">change</th><th class="num">change %%</th></tr></thead>'
        '<tbody>%s</tbody></table></div>'
        '<p class="note">Every figure is a value the shift itself wrote when it closed. '
        'A metric absent at either end says so rather than being interpolated.</p>'
        % (num(a), num(b), "".join(row(mt) for mt in metrics)))

    mid += C.panel(
        "The falsification checkpoint",
        C.kv([("condition", "physics.md Section 11"),
              ("canonical shifts run", num(len(canon))),
              ("required", "15"),
              ("status", "reached" if len(canon) >= 15 else "not yet reached")]) +
        '<p class="note">Phase 1 shifts on the local model do not count toward it. This '
        'panel reports whether the condition has been reached; it does not evaluate it. '
        'Evaluating it is a separate reading of the record and is not done here.</p>')

    return C.page("%s — Checkpoint" % d["name"], "CHECKPOINT REPORT", t,
                  [("TERRAINS", C.HUB + "/hub.html"),
                   (d["name"], "/%s/terrain.html" % t),
                   ("CHECKPOINT %s → %s" % (num(a), num(b)), None)],
                  d["shift"], d["committed_at"], mid, left, right, CSS,
                  current="checkpoint")


# ===========================================================================
# comparative terrain study
# ===========================================================================
def comparative_study(loaded: List[Dict[str, Any]]) -> str:
    """Every terrain side by side, on quantities all of them actually record."""
    shown = [d for d in loaded if d and d["shifts"]]
    if len(shown) < 2:
        return ""

    def cell(d, key, fn=None):
        rows = d["shifts"]
        v = fn(d) if fn else (rows[-1].get(key) if rows else None)
        return v

    METRICS = [
        ("living specimens", lambda d: d["shifts"][-1].get("living")),
        ("shifts on record", lambda d: len(d["shifts"])),
        ("native categories", lambda d: len(d["memory"].get("category_stats") or {})),
        ("classified specimens", lambda d: len(d["named"])),
        ("cells in the terrain", lambda d: len(d["world"].get("cells") or [])),
        ("cover cells", lambda d: sum(1 for c in (d["world"].get("cells") or [])
                                      if c.get("census_density", 0) > 0)),
        ("active links", lambda d: len([1 for v in (d["world"].get("links") or {}).values()
                                        if v.get("formed_at_shift") is not None])),
        ("descendant threads", lambda d: sum(1 for b in d["individuals"].values()
                                             if b.get("parent_id"))),
        ("classification diversity", lambda d: dnt_data.shannon_diversity(
            [c.get("count", 0) for c in (d["memory"].get("category_stats") or {}).values()])),
        ("population stability", lambda d: dnt_data.coefficient_of_variation(
            [r.get("living") for r in d["shifts"][-40:]])),
        ("cumulative spend", lambda d: float(d["memory"].get("cumulative_cost_usd", 0.0))),
    ]

    head = "".join('<th class="num">%s</th>' % esc(d["name"]) for d in shown)
    body = []
    for label, fn in METRICS:
        vals = []
        for d in shown:
            try:
                vals.append(fn(d))
            except Exception:
                vals.append(None)
        body.append('<tr><td>%s</td>%s</tr>'
                    % (label, "".join('<td class="num">%s</td>'
                                      % ("—" if v is None else num(v)) for v in vals)))

    # governing conditions, terrain by terrain — the actual point of comparison
    labels = []
    for d in shown:
        for g in dnt_data.governing_conditions(d["dir"]):
            if g["label"] not in labels:
                labels.append(g["label"])
    govmap = {d["dir"]: {g["label"]: g for g in dnt_data.governing_conditions(d["dir"])}
              for d in shown}
    govrows = "".join(
        '<tr><td>%s</td>%s</tr>'
        % (esc(label), "".join(
            ('<td class="num">%s</td>' % esc(govmap[d["dir"]][label]["value"]))
            if govmap[d["dir"]].get(label, {}).get("present")
            else '<td class="num absent">absent</td>' for d in shown))
        for label in labels)

    cards = "".join(
        '<section class="p"><div class="ph"><b>%s</b><span class="r">shift %s</span></div>'
        '<div class="pb">%s<p class="note">%s</p>'
        '<p class="note"><a href="/%s/terrain.html">terrain record →</a></p></div></section>'
        % (esc(d["name"]), num(d["shift"]),
           C.kv([("living", num(d["shifts"][-1].get("living"))),
                 ("categories", num(len(d["memory"].get("category_stats") or {}))),
                 ("cells", num(len(d["world"].get("cells") or []))),
                 ("spend", "$%.4f" % float(d["memory"].get("cumulative_cost_usd", 0.0)))]),
           esc(d["memory"].get("physics_document") or ""), d["dir"])
        for d in shown)

    trajectories = "".join(
        '<div><div class="genh">%s · living</div>%s</div>'
        % (esc(d["name"]), spark([r.get("living") for r in d["shifts"]], 300, 70))
        for d in shown)

    left = C.panel("Terrains in study", "".join(
        '<div class="rowlink"><span class="sw" style="background:var(--moss2)"></span>'
        '<span>%s<span class="s">shift %s</span></span><span></span></div>'
        % (esc(d["name"]), num(d["shift"])) for d in shown), flush=True) + \
        C.panel("Study controls",
                '<p class="note">There are none. Every terrain on this page contributes '
                'every shift it has committed; there is no window to choose and no '
                'normalisation applied, because normalising terrains of different ages '
                'against each other would invent a comparison the record does not '
                'support.</p>') + \
        C.panel("What this is not",
                '<p class="note">Not a ranking. Terrains run under different conditions '
                'and different numbers of shifts; a higher figure is a different outcome, '
                'not a better one. DNT does not evaluate terrains. We observe.</p>')

    right = C.panel("Study context",
                    '<p class="note">All terrains are experimental systems. This is an '
                    'observational comparison and implies no preference, success, or '
                    'superiority.</p>') + \
        C.panel("Read with care",
                '<p class="note">BASIN-01 and BASIN-02 differ in exactly one seeded '
                'variable and are a controlled comparison. BASIN-03 and BASIN-04 are not '
                '— each took further amendments, so a difference between them and the '
                'first two has more than one possible cause.</p>') + \
        C.panel("Related", C.kv(
            [("%s record" % d["name"], '<a href="/%s/terrain.html">open →</a>' % d["dir"])
             for d in shown] +
            [("department index", '<a href="%s/hub.html">open →</a>' % C.HUB)]))

    mid = ('<div class="hdr"><div><p class="eyebrow">Studies</p>'
           '<h1 class="doc">Comparative Terrain Study</h1>'
           '<p class="sub">Longitudinal comparison of active terrains under differing '
           'governing conditions.</p></div><table class="doc">'
           '<tr><td class="k">DOCUMENT</td><td class="v">DNT-STUDY</td></tr>'
           '<tr><td class="k">TERRAINS</td><td class="v">%d</td></tr>'
           '<tr><td class="k">SOURCE</td><td class="v">EACH TERRAIN\'S OWN LOGS</td></tr>'
           '</table></div>' % len(shown))
    mid += '<div class="cols3" style="margin-bottom:14px">%s</div>' % cards
    mid += C.panel("Living population over time",
                   '<div class="cols3">%s</div>'
                   '<p class="note">Each line is drawn against its own range, so the shapes '
                   'are comparable and the heights are not. A terrain runs for as long as it '
                   'has run; none of these are normalised to a common age.</p>' % trajectories)
    mid += C.panel("Governing conditions, side by side",
                   '<div class="scroll"><table class="d"><thead><tr><th>condition</th>%s</tr>'
                   '</thead><tbody>%s</tbody></table></div>'
                   '<p class="note">This is the comparison that matters: the terrains differ '
                   'in what governs them, and a condition a terrain does not have is shown as '
                   'absent rather than as a zero.</p>' % (head, govrows))
    mid += C.panel("Aggregate metrics at the latest shift",
                   '<div class="scroll"><table class="d"><thead><tr><th>metric</th>%s</tr>'
                   '</thead><tbody>%s</tbody></table></div>'
                   '<p class="note">Read across a row, not down a column. Each terrain is at '
                   'a different shift and under different conditions.</p>'
                   % (head, "".join(body)))

    return C.page("Comparative Terrain Study", "COMPARATIVE STUDY", shown[-1]["dir"],
                  [("STUDIES", None), ("COMPARATIVE TERRAIN STUDY", None)],
                  shown[-1]["shift"], shown[-1]["committed_at"], mid, left, right, CSS,
                  current="study")


# ===========================================================================
def write(path: str, html: str) -> None:
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(html)


# Which specimens get their own page.
#
# Every LIVING specimen would be 10,589 files on BASIN-03 alone, and most of
# them are counted rather than written up — there would be nothing on the page.
# The set that matters is the one the rest of the site already links to: every
# specimen the Namer has classified individually. The compendium links each of
# them from its category sheet, so each of them must exist.
def specimen_targets(d):
    return set(d["named"])


def build(terrain: str) -> Optional[str]:
    d = load(terrain)
    if not d:
        return None
    base = os.path.join(ROOT, terrain)
    write(os.path.join(base, "terrain.html"), terrain_record(d))
    write(os.path.join(base, "shiftlog.html"), shift_log(d))

    # categories
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for r in d["specimens"]:
        c = (r.get("classification") or {}).get("category")
        if c:
            by_cat.setdefault(c, []).append(r)
    for name in set(list(by_cat) + list((d["memory"].get("category_stats") or {}))):
        members = [sid for sid, c in d["named"].items() if c.get("category") == name]
        write(os.path.join(base, "categories", slug(name) + ".html"),
              category_record(d, name, members, by_cat.get(name, [])))

    # specimens: the longest-standing living, plus anything with descendants
    ind = d["individuals"]
    picked = sorted(specimen_targets(d))
    d["_pages"] = set(picked)
    sight: Dict[str, List[Dict[str, Any]]] = {}
    for r in d["specimens"]:
        if r.get("specimen_id"):
            sight.setdefault(r["specimen_id"], []).append(r)
    # Which lineage pages will exist has to be settled BEFORE the specimen
    # records are written, or every one of them links to a page that is not
    # there yet and may never be.
    roots = sorted((k for k in picked if (ind.get(k) or {}).get("descendants")),
                   key=lambda k: -(ind[k].get("descendants") or 0))[:60]
    d["_lineages"] = set(roots)
    for sid in picked:
        write(os.path.join(base, "specimens", sid + ".html"),
              specimen_record(d, sid, sight.get(sid, [])))

    for sid in roots:
        write(os.path.join(base, "lineage", sid + ".html"), lineage_record(d, sid))

    ck = checkpoint_report(d)
    if ck:
        write(os.path.join(base, "checkpoint.html"), ck)
    return ("%-9s terrain + shift log%s + %d category + %d specimen + %d lineage"
            % (terrain, " + checkpoint" if ck else "", len(by_cat), len(picked), len(roots)))


def main(argv: List[str]) -> int:
    targets = [t for t in TERRAINS
               if ("--all" in argv or t in argv)
               and os.path.exists(os.path.join(ROOT, t, "state", "memory.json"))]
    if not targets:
        print("usage: python3 console_pages.py basin-03 | --all")
        return 1
    for t in targets:
        line = build(t)
        if line:
            print("  " + line)
    # The study is one document for the department, written last so that every
    # terrain it reads has already been rebuilt.
    study = comparative_study([load(t) for t in TERRAINS
                               if os.path.exists(os.path.join(ROOT, t, "state",
                                                              "memory.json"))])
    if study:
        write(os.path.join(ROOT, "study.html"), study)
        print("  study.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
