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

import json, math, os, re, sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import dnt_console as C
import dnt_data
import dnt_charts as charts
import dnt_terrains
import snapshot

TERRAINS = dnt_terrains.dirs()

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
.dq{border-bottom:1px solid var(--rule);padding:0 0 14px;margin-bottom:14px}
.dq:last-of-type{border-bottom:none;padding-bottom:0;margin-bottom:0}
.dqh{display:flex;justify-content:space-between;align-items:baseline;gap:14px}
.dqn{font:11px var(--mono);letter-spacing:.09em;text-transform:uppercase;color:var(--dim)}
.dqv{font:400 25px/1 var(--serif);font-variant-numeric:tabular-nums;color:var(--ink)}
.dqp{font:12.5px/1.65 var(--sans);color:var(--ink);margin:9px 0 0;max-width:74ch}
.dqp b{color:var(--moss);font-weight:400;font-family:var(--mono)}
.dqp i{color:var(--dim);font-style:normal;font-family:var(--mono);font-size:11.5px}
.dqf{font:10.5px/1.6 var(--mono);color:var(--faint);margin:7px 0 0}
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
border-bottom:1px solid var(--rule);padding-bottom:6px;margin-bottom:9px;
display:flex;justify-content:space-between;gap:8px}
.genh span{color:var(--ink);letter-spacing:.04em}
.node{border:1px solid var(--rule);background:var(--panel2);padding:8px 10px;margin-bottom:8px;
font:10.5px var(--mono);text-decoration:none;color:var(--ink);display:block}
.node:hover{border-color:var(--moss2)}
.node.root{border-color:var(--moss2)}
.node{position:relative}
.node .nid{font:11px var(--mono);color:var(--ink);display:block}
.node .c{color:var(--dim);font-size:9px;display:block;margin-top:2px;line-height:1.4}
.node.gone{opacity:.55;border-style:dashed}
.node.more{border-style:dashed;color:var(--dim);text-align:center;font-size:9.5px}
.ndot{width:6px;height:6px;border-radius:50%;display:inline-block}
.node .ndot{position:absolute;top:8px;right:8px}
.ndot.live{background:#7FCB8A}
.ndot.dead{background:#4E574C}
.gen{min-width:172px}
.tl{position:relative;height:34px;background:var(--bg);border:1px solid var(--rule)}
.tl i{position:absolute;top:4px;width:2px;height:26px;display:block}
.tlx{display:flex;justify-content:space-between;font:9.5px var(--mono);color:var(--dim);
margin-top:6px}
.ann{border-bottom:1px solid var(--rule);padding:9px 0}
.ann:last-child{border-bottom:none}
.annh{display:flex;justify-content:space-between;gap:10px;font:11px var(--mono);
color:var(--ink)}
.annh span{color:var(--dim);font-size:9.5px;white-space:nowrap}
.annb{font:9.5px var(--mono);color:var(--dim);margin-top:3px}
.filters{display:flex;flex-direction:column;gap:4px}
.filt{display:flex;align-items:center;gap:8px;font:10.5px var(--mono);color:var(--ink);
cursor:pointer}
.filt input{accent-color:var(--moss);margin:0}
.filt .c{margin-left:auto;color:var(--dim);font-variant-numeric:tabular-nums}
.tj{cursor:zoom-in}
.tj .ct{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.tj:hover .ct{color:var(--moss)}
.cmpshots{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.cmpshot{margin:0}
.cmpshot figcaption{font:12px var(--mono);letter-spacing:.05em;margin-bottom:7px}
.cmpshot span{display:block;font:9.5px var(--mono);color:var(--dim);margin-top:6px}
.tcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
gap:14px;margin-bottom:14px}
.tcard{border:1px solid var(--rule);background:var(--panel);
display:flex;flex-direction:column}
.tch{display:flex;justify-content:space-between;align-items:center;padding:11px 13px;
border-bottom:1px solid var(--rule)}
.tch b{font:14px var(--mono);letter-spacing:.05em}
.tcb{padding:12px 13px;display:flex;flex-direction:column;flex:1}
.tcg{font:9px var(--mono);letter-spacing:.13em;text-transform:uppercase;color:var(--dim);
margin:13px 0 7px;border-top:1px solid var(--rule);padding-top:11px}
.tcb .nav{margin-top:auto}
.tcb > dl.kv:last-of-type{margin-bottom:26px}
ul.find{list-style:none;margin:0;padding:0}
ul.find li{font:11.5px/1.65 var(--mono);color:var(--dim);padding:8px 0;
border-bottom:1px solid var(--rule)}
ul.find li:last-child{border-bottom:none;color:var(--faint)}
ul.find b{font-weight:400}
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

    # A number nobody can read is not a published result, it is decoration.
    # Each derived quantity carries three things: the value, a sentence saying
    # what it means FOR THIS TERRAIN in words a reader can check against their
    # own sense of the place, and the formula it came from. The formula stays —
    # it is what makes the number checkable — but it is no longer the only
    # explanation offered.
    div = dnt_data.shannon_diversity([c.get("count", 0) for c in cats.values()])
    stab = dnt_data.coefficient_of_variation(pop[-40:])
    anom_count = sum(r.get("anomalous", 0) or 0 for r in rows)
    anom = dnt_data.per_hundred_shifts(anom_count, len(rows))

    counts = sorted((c.get("count", 0) for c in cats.values()), reverse=True)
    filed = sum(counts)
    if div is not None and counts:
        effective = math.exp(div)
        biggest = (100.0 * counts[0] / filed) if filed else 0.0
        div_plain = (
            "As varied as <b>%.1f</b> evenly-filled categories, though <b>%d</b> have "
            "been coined. The largest holds <b>%.0f%%</b> of everything filed, which is "
            "why the two numbers disagree. A terrain where all %d were equally common "
            "would read %.4f; one where everything sat in a single category would read 0."
            % (effective, len(counts), biggest, len(counts), math.log(len(counts))))
    else:
        div_plain = "Not enough categories have been coined to measure spread."

    window = pop[-40:]
    if stab is not None and window:
        mu = sum(window) / float(len(window))
        div2 = len(window)
        sd = (sum((v - mu) ** 2 for v in window) / div2) ** 0.5
        stab_plain = (
            "Across the last %d shifts the living population ran between <b>%s</b> and "
            "<b>%s</b>, averaging <b>%s</b>. A typical shift sits about <b>%.0f%%</b> away "
            "from that average. Lower is steadier; it is a description, not a grade."
            % (len(window), num(min(window)), num(max(window)), num(int(round(mu))),
               stab * 100.0))
    else:
        stab_plain = "Too few shifts recorded to measure how steady the population is."

    anom_plain = (
        "<b>%s</b> classification(s) the Namer could not fit into any category, across "
        "<b>%s</b> shifts. That is the Namer reporting something it did not recognise — a "
        "finding, not a fault. It is counted apart from <i>unresolved</i>, which is the "
        "model failing to answer at all."
        % (num(anom_count), num(len(rows))))

    derived = "".join(
        '<div class="dq"><div class="dqh"><span class="dqn">%s</span>'
        '<span class="dqv">%s</span></div>'
        '<p class="dqp">%s</p>'
        '<p class="dqf">%s &nbsp;·&nbsp; %s</p></div>'
        % (label, "—" if value is None else "%.4f" % value, plain,
           dnt_data.DEFINITIONS[key][0], dnt_data.DEFINITIONS[key][1])
        for label, value, key, plain in (
            ("classification diversity", div, "diversity", div_plain),
            ("population stability", stab, "stability", stab_plain),
            ("anomaly rate", anom, "anomaly rate", anom_plain)))

    evrows = "".join(
        '<tr><td class="num">%s</td><td style="color:var(--moss)">%s</td>'
        '<td class="dim">%s</td><td class="dim num">%s</td></tr>'
        % (esc(e.get("shift")), esc(e.get("kind")),
           esc((e.get("detail") or e.get("note") or "")[:150]),
           C.stamp(e.get("logged_at")))
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
        C.panel("This terrain", C.nav([
            ("Observation deck", "http://127.0.0.1:%d/index.html" % C.PORTS.get(t, 8731),
             "walk the terrain in 3D"),
            ("Shift log", "/%s/shiftlog.html" % t,
             "every shift committed, and what changed"),
            ("Checkpoint report",
             ("/%s/checkpoint.html" % t)
             if os.path.exists(os.path.join(ROOT, t, "checkpoint.html")) else None,
             "state compared across a window of shifts"),
            ("Comparative study",
             "/study.html" if os.path.exists(os.path.join(ROOT, "study.html")) else None,
             "this terrain beside the others"),
            ("Field compendium",
             ("/%s/codex.html" % t)
             if os.path.exists(os.path.join(ROOT, t, "codex.html")) else None,
             "every specimen ever classified"),
        ])) + \
        C.panel("About terrains",
                '<p class="note">Terrains are bounded digital environments seeded and '
                'stewarded by DNT under defined governing conditions. Each terrain is an '
                'autonomous system. We do not design. We observe.</p>')

    right = C.panel("Terrain status", C.kv([
        ("current shift", num(d["shift"])),
        ("last committed", C.stamp(d["committed_at"])),
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
                       '%s<p class="note">Published definitions only. Each value is said in '
                       'plain words and then in the formula it came from, so it can be read '
                       'and checked rather than trusted.</p>' % derived),
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
IMPACT = [(1, "minimal", "observable but low system effect"),
          (10, "low", "localised or contained change"),
          (100, "moderate", "noticeable terrain-scale effect"),
          (1000, "high", "significant, wide-reaching effect"),
          (10 ** 9, "critical", "system-altering or rare")]


def impact_of(affected: int):
    """A published band, not a judgement — how many things an event touched."""
    for ceiling, name, blurb in IMPACT:
        if affected <= ceiling:
            return name, blurb
    return IMPACT[-1][1], IMPACT[-1][2]


def events_for_shift(d, shift):
    """The real event stream for one shift, assembled from the logs.

    Every row below is a record the terrain already wrote. Classifications
    carry their own UTC timestamp, so those are placed in real time; the rest
    are known to the shift but not to the second, and say so rather than being
    given an invented clock time.
    """
    out = []
    for r in d["specimens"]:
        if r.get("shift") != shift:
            continue
        cl = r.get("classification") or {}
        if not cl.get("category"):
            continue
        out.append({
            "at": r.get("logged_at"), "kind": "classification",
            "colour": "#A8D45C",
            "detail": "%s filed as %s%s" % (
                r.get("specimen_id"), cl.get("category"),
                (" — %s" % cl.get("decision")) if cl.get("decision") else ""),
            "target": r.get("specimen_id"), "affected": 1,
        })
    row = next((r for r in d["shifts"] if r.get("shift") == shift), None) or {}
    for cat in (row.get("new_categories") or []):
        out.append({"at": row.get("end_timestamp"), "kind": "category coined",
                    "colour": "#4FA3E3",
                    "detail": "the Namer coined %s" % cat, "target": cat,
                    "affected": (d["memory"].get("category_stats") or {}
                                 ).get(cat, {}).get("count", 1)})
    for key, kind, colour in (("arose_this_shift", "arrivals", "#7FCB8A"),
                              ("ended_this_shift", "endings", "#D4614A"),
                              ("replicated_this_shift", "replications", "#B37BD6"),
                              ("links_formed", "links formed", "#5FA9A0")):
        n = row.get(key) or 0
        if n:
            out.append({"at": row.get("end_timestamp"), "kind": kind, "colour": colour,
                        "detail": "%s %s recorded in this shift" % (num(n), kind),
                        "target": "", "affected": n})
    events = d["memory"].get("terrain_events")
    events = events if isinstance(events, list) else ([events] if events else [])
    for e in events:
        if e.get("shift") == shift:
            out.append({"at": e.get("logged_at"), "kind": "terrain event",
                        "colour": "#C9A227",
                        "detail": (e.get("detail") or e.get("note") or "")[:180],
                        "target": e.get("kind"), "affected": 0})
    out.sort(key=lambda x: (x.get("at") or ""), reverse=True)
    return out


def _secs(stamp):
    """Seconds into the day, from a UTC stamp, or None."""
    if not stamp or "T" not in stamp:
        return None
    try:
        hh, mm, ss = stamp.split("T")[1].rstrip("Z").split(":")
        return int(hh) * 3600 + int(mm) * 60 + int(float(ss))
    except (ValueError, IndexError):
        return None


def shift_log(d: Dict[str, Any]) -> str:
    t, m, rows = d["dir"], d["memory"], d["shifts"]
    hue = charts.hue(t)
    last = rows[-1] if rows else {}
    prev = rows[-2] if len(rows) > 1 else {}
    shift = last.get("shift")
    evs = events_for_shift(d, shift)

    def delta(key):
        a, b = last.get(key), prev.get(key)
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            return ""
        diff = a - b
        if not diff:
            return '<span class="dim">no change</span>'
        return '<span class="%s">%+s vs previous</span>' % (
            "up" if diff > 0 else "down", num(diff))

    strip = C.stats([
        (num(len(rows)), "shifts",
         ("since %s" % esc((rows[0].get("end_timestamp") or "")[:10])) if rows
         else "none committed yet"),
        (num(last.get("living")), "living", delta("living")),
        (num(len(m.get("category_stats") or {})), "native categories",
         "+%s this shift" % num(len(last.get("new_categories") or []))),
        (num(last.get("arose_this_shift")), "arose", delta("arose_this_shift")),
        (num(last.get("ended_this_shift")), "ended", delta("ended_this_shift")),
        (num(last.get("replicated_this_shift")), "replicated", delta("replicated_this_shift")),
        (num(last.get("links_formed")), "links formed", delta("links_formed")),
    ])

    evrows = "".join(
        '<tr data-kind="%s"><td class="num">%s</td>'
        '<td class="dim">%s</td>'
        '<td><span class="sw" style="background:%s"></span> %s</td>'
        '<td class="dim">%s</td><td class="num"><span class="chip">%s</span></td>'
        '<td class="num dim">%s</td></tr>'
        % (esc(e["kind"]), esc(shift), C.stamp(e.get("at"), "shift only"),
           e["colour"], esc(e["kind"]), esc(e["detail"]),
           impact_of(e.get("affected") or 0)[0],
           num(e.get("affected")) if e.get("affected") else "—")
        for e in evs[:80]) or \
        '<tr><td colspan="6" class="absent">nothing individually logged for this shift</td></tr>'

    # ---- activity across the real elapsed shift --------------------------
    t0, t1 = _secs(last.get("start_timestamp")), _secs(last.get("end_timestamp"))
    ticks = ""
    if t0 is not None and t1 is not None and t1 > t0:
        marks = []
        for e in evs:
            s = _secs(e.get("at"))
            if s is None or not (t0 <= s <= t1):
                continue
            marks.append('<i style="left:%.2f%%;background:%s" title="%s"></i>'
                         % (100.0 * (s - t0) / (t1 - t0), e["colour"], esc(e["kind"])))
        ticks = ('<div class="tl">%s</div>'
                 '<div class="tlx"><span>%s</span><span>%s elapsed</span><span>%s</span></div>'
                 % ("".join(marks),
                    esc((last.get("start_timestamp") or "")[11:19]),
                    "%.0fs" % float(last.get("duration_seconds") or (t1 - t0)),
                    esc((last.get("end_timestamp") or "")[11:19])))
    else:
        ticks = '<p class="absent">this shift recorded no start and end time</p>'

    # ---- summary comparison, with a trend per row ------------------------
    COMPARE = [("living specimens", "living"), ("arose", "arose_this_shift"),
               ("ended", "ended_this_shift"), ("replicated", "replicated_this_shift"),
               ("classified", "classified"), ("links formed", "links_formed"),
               ("anomalous", "anomalous"), ("unresolved", "unresolved"),
               ("resource flow", "resource_flow")]
    last10 = rows[-10:]
    crows = "".join(
        '<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
        '<td class="num %s">%s</td><td>%s</td></tr>'
        % (label,
           num(prev.get(key)) if prev else "—", num(last.get(key)),
           ("up" if (last.get(key) or 0) - (prev.get(key) or 0) > 0 else
            ("down" if (last.get(key) or 0) - (prev.get(key) or 0) < 0 else "dim")),
           ("%+s" % num((last.get(key) or 0) - (prev.get(key) or 0))) if prev else "—",
           charts.trend([r.get(key) for r in last10], colour=hue))
        for label, key in COMPARE)

    kinds = sorted({e["kind"] for e in evs})
    left = C.panel("Select terrain", "".join(
        '<a class="rowlink%s" href="/%s/shiftlog.html"><span class="sw" '
        'style="background:%s"></span><span>%s<span class="s">shift %s</span></span>'
        '<span></span></a>'
        % (" on" if x == t else "", x, charts.hue(x), x.upper(),
           esc((dnt_data.load(x) or {}).get("memory", {}).get("last_committed_shift", "—")))
        for x in TERRAINS if os.path.isdir(os.path.join(ROOT, x))), flush=True) + \
        C.panel("Show", '<div class="filters">%s</div>'
                '<p class="note">Filters hide rows. They change nothing in the record, and '
                'the counts above stay what the shift wrote.</p>' % "".join(
                    '<label class="filt"><input type="checkbox" data-kind="%s" checked>'
                    '<i class="sw" style="background:%s"></i>%s'
                    '<span class="c">%d</span></label>'
                    % (esc(k), next((e["colour"] for e in evs if e["kind"] == k), "#7C8879"),
                       esc(k), sum(1 for e in evs if e["kind"] == k))
                    for k in kinds)) + \
        C.panel("Go to", C.nav([
            ("Terrain record", "/%s/terrain.html" % t,
             "governing conditions and current state"),
            ("Observation deck", "http://127.0.0.1:%d/index.html" % C.PORTS.get(t, 8731),
             "walk the terrain in 3D"),
            ("Checkpoint report",
             ("/%s/checkpoint.html" % t)
             if os.path.exists(os.path.join(ROOT, t, "checkpoint.html")) else None,
             "state compared across a window"),
        ]))

    ann = m.get("annotations") or {}
    annrows = "".join(
        '<div class="ann"><div class="annh">%s<span>%s</span></div>'
        '<div class="annb">recorded by %s at shift %s</div></div>'
        % (esc(k.replace("_", " ")), C.stamp(v.get("at")),
           esc(v.get("by") or "—"), esc(v.get("shift")))
        for k, v in sorted(ann.items(),
                           key=lambda kv: kv[1].get("at") or "", reverse=True)
        if isinstance(v, dict)) or \
        '<p class="absent">no annotations recorded</p>'

    right = C.panel("Shift context", C.kv([
        ("current shift", num(shift)),
        ("started", C.stamp(last.get("start_timestamp"))),
        ("committed", C.stamp(last.get("end_timestamp"))),
        ("took", "%.1fs" % float(last.get("duration_seconds") or 0)),
        ("phase", esc(last.get("phase"))),
        ("model", esc(last.get("model"))),
        ("model calls", num(last.get("model_calls"))),
        ("cost this shift", "$%.6f" % float(last.get("estimated_cost_usd") or 0)),
        ("cumulative", "$%.4f" % float(last.get("cumulative_cost_usd") or 0)),
    ])) + C.panel("Annotations", annrows, "%d on record" % len(ann)) + \
        C.panel("Event impact key", "".join(
            '<div class="mini"><span><span class="chip">%s</span></span>'
            '<span></span><b style="text-align:left;color:var(--dim);font-size:10px">%s</b>'
            '</div>' % (name, blurb) for _, name, blurb in IMPACT) +
            '<p class="note">A band, not a judgement: how many things the record says the '
            'event touched.</p>') + \
        C.panel("Export", C.nav([
            ("Shift log (CSV)", "/%s/exports/shiftlog.csv" % t,
             "every shift, every column the log wrote"),
            ("Shift log (JSON)", "/%s/shifts/shift_log.jsonl" % t,
             "the raw append-only record"),
        ]))

    mid = ('<div class="hdr" id="top"><div><p class="eyebrow">%s · shift log</p>'
           '<h1 class="doc">Shift Log <span style="color:%s">%s</span></h1>'
           '<p class="sub">Chronological record of observed changes and system events.</p>'
           '</div><table class="doc">'
           '<tr><td class="k">DOCUMENT</td><td class="v">DNT-SHL</td></tr>'
           '<tr><td class="k">TERRAIN</td><td class="v">%s</td></tr>'
           '<tr><td class="k">SHIFTS</td><td class="v">%s</td></tr>'
           '<tr><td class="k">THROUGH</td><td class="v">%s</td></tr></table></div>'
           % (esc(d["name"]), hue, esc(d["name"]), esc(d["name"]), num(len(rows)), esc(shift)))
    mid += strip
    mid += C.panel(
        "Shift events, newest first",
        '<div class="scroll"><table class="d" id="evt"><thead><tr><th class="num">shift</th>'
        '<th>time (UTC)</th><th>event</th><th>details</th><th class="num">impact</th>'
        '<th class="num">affected</th></tr></thead><tbody>%s</tbody></table></div>'
        '<p class="note">Classifications carry their own timestamp and are placed in real '
        'time. The others are known to the shift but not to the second, and say so rather '
        'than being given an invented clock time.</p>' % evrows,
        "shift %s · %d event(s)" % (num(shift), len(evs)))
    mid += C.panel("Activity across shift %s" % num(shift), ticks,
                   "%.0f seconds elapsed" % float(last.get("duration_seconds") or 0))
    mid += C.panel(
        "Shift summary comparison",
        '<div class="scroll"><table class="d"><thead><tr><th>metric</th>'
        '<th class="num">shift %s</th><th class="num">shift %s</th><th class="num">Δ</th>'
        '<th>last 10 shifts</th></tr></thead><tbody>%s</tbody></table></div>'
        % (num(prev.get("shift")) if prev else "—", num(shift), crows))
    mid += C.panel(
        "Every shift committed",
        '<div class="scroll"><table class="d"><thead><tr>'
        '<th class="num">shift</th><th>committed</th><th class="num">living</th>'
        '<th class="num">arose</th><th class="num">ended</th><th class="num">replicated</th>'
        '<th class="num">links</th><th class="num">classified</th>'
        '<th>categories coined</th><th>phase</th></tr></thead><tbody>%s</tbody></table></div>'
        '<p class="note">Showing the most recent %d of %d.</p>'
        % ("".join(
            '<tr><td class="num">%s</td><td class="dim">%s</td>'
            '<td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td class="dim">%s</td><td class="dim">%s</td></tr>'
            % (esc(r.get("shift")), C.stamp(r.get("end_timestamp")),
               num(r.get("living")), num(r.get("arose_this_shift")),
               num(r.get("ended_this_shift")), num(r.get("replicated_this_shift")),
               num(r.get("links_formed")), num(r.get("classified")),
               esc(", ".join(r.get("new_categories") or []) or "—"), esc(r.get("phase")))
            for r in reversed(rows[-100:])), min(100, len(rows)), len(rows)))

    script = ("<script>document.querySelectorAll('[data-kind]').forEach(function(b){"
              "if(b.tagName!=='INPUT')return;b.onchange=function(){"
              "var on={};document.querySelectorAll('input[data-kind]').forEach(function(x){"
              "on[x.dataset.kind]=x.checked});"
              "document.querySelectorAll('#evt tbody tr[data-kind]').forEach(function(r){"
              "r.style.display = on[r.dataset.kind]===false ? 'none' : ''})}});</script>")

    return C.page("%s — Shift Log" % d["name"], "SHIFT LOG", t,
                  [("TERRAINS", C.HUB + "/hub.html"),
                   (d["name"], "/%s/terrain.html" % t), ("SHIFT LOG", None)],
                  shift, d["committed_at"], mid, left, right,
                  CSS + charts.CSS, current="shiftlog", scripts=script)


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
        C.panel("Go to", C.nav([
            ("Field-guide sheet",
             ("/%s/codex/%s.html" % (t, slug(name)))
             if os.path.exists(os.path.join(ROOT, t, "codex", slug(name) + ".html"))
             else (("/%s/codex.html" % t)
                   if os.path.exists(os.path.join(ROOT, t, "codex.html")) else None),
             "the same category, drawn and described"),
            ("Linnaean crosswalk",
             ("/%s/crosswalk.html" % t)
             if os.path.exists(os.path.join(ROOT, t, "crosswalk.html")) else None,
             "the Archivist's translation, if it has run"),
            ("Terrain record", "/%s/terrain.html" % t,
             "the terrain this category lives in"),
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
        ])) + \
        C.panel("Go to", C.nav([
            ("See it in the field",
             ("http://127.0.0.1:%d/index.html#%s" % (C.PORTS.get(t, 8731), esc(sid)))
             if alive else None,
             "opens the deck with this one selected" if alive
             else "no longer in the field"),
            ("Lineage record",
             ("/%s/lineage/%s.html" % (t, esc(sid)))
             if sid in d.get("_lineages", ()) else None,
             "its descendants, generation by generation" if sid in d.get("_lineages", ())
             else "no recorded descendants"),
            ("Category record",
             ("/%s/categories/%s.html" % (t, slug(named["category"])))
             if named.get("category") else None,
             "everything else the Namer filed here"),
            ("Terrain record", "/%s/terrain.html" % t, "the terrain it lives in"),
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
    ended = {e.get("id"): e for e in (d["world"].get("ended") or [])}
    hue = charts.hue(t)

    kids_of: Dict[str, List[str]] = {}
    for k, v in list(ind.items()) + list(ended.items()):
        p = v.get("parent_id")
        if p:
            kids_of.setdefault(p, []).append(k)

    gens: Dict[int, List[str]] = {0: [root]}
    seen = {root}
    depth = 0
    while gens.get(depth) and depth < 14:
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

    rec = lambda k: ind.get(k) or ended.get(k) or {}
    living = [k for k in seen if k in ind]
    extinct = [k for k in seen if k not in ind]
    b = rec(root)
    alive = root in ind

    # ---- ancestry, walked upward ----------------------------------------
    chain, node = [], b.get("parent_id")
    guard = 0
    while node and guard < 30:
        chain.append(node)
        node = rec(node).get("parent_id")
        guard += 1

    # ---- the tree, one column per generation ----------------------------
    def node_box(k, g):
        r = rec(k)
        is_live = k in ind
        cat = (d["named"].get(k) or {}).get("category") or "not yet named"
        linkable = k in d.get("_pages", ())
        return ('<%s class="node%s%s"%s><span class="nid">%s</span>'
                '<span class="c">%s</span>'
                '<span class="c">gen %s · %s shift(s) · %s kid(s)</span>'
                '<span class="ndot %s"></span></%s>'
                % ("a" if linkable else "div", " root" if g == 0 else "",
                   "" if is_live else " gone",
                   ' href="/%s/specimens/%s.html"' % (t, esc(k)) if linkable else "",
                   esc(k), esc(cat), num(r.get("generation")), num(r.get("age")),
                   num(r.get("descendants")),
                   "live" if is_live else "dead",
                   "a" if linkable else "div"))

    tree = '<div class="tree">%s</div>' % "".join(
        '<div class="gen"><div class="genh">gen %d<span>%d</span></div>%s</div>'
        % (g, len(gens[g]), "".join(node_box(k, g) for k in gens[g][:12]) +
           ('<div class="node more">+ %d more</div>' % (len(gens[g]) - 12)
            if len(gens[g]) > 12 else ""))
        for g in sorted(gens))

    tree_legend = ('<div class="chartlegend">'
                   '<span class="lg"><i class="ndot live"></i>living</span>'
                   '<span class="lg"><i class="ndot dead"></i>ended</span>'
                   '<span class="lg"><i class="ndot" style="background:%s"></i>root</span>'
                   '<span class="lg">a column is a generation; a box is one recorded '
                   'parent_id away from the column to its left</span></div>' % hue)

    # ---- trait drift ------------------------------------------------------
    def trait(k, path):
        v = rec(k)
        if path in ("extent", "junctions", "mass"):
            return (v.get("structure") or {}).get(path)
        return (v.get("traits") or {}).get(path)
    base = {p: trait(root, p) for p in ("extent", "junctions", "mass",
                                        "cover", "residue", "links")}
    TRAITS = (("extent", "reach"), ("junctions", "junctions"), ("mass", "mass"),
              ("cover", "affinity: cover"), ("residue", "affinity: remains"),
              ("links", "affinity: links"))
    drift_rows, drift_series = [], []
    for p, label in TRAITS:
        cells, pts = [], []
        for g in sorted(gens):
            if g == 0:
                continue
            vals = [trait(k, p) for k in gens[g] if trait(k, p) is not None]
            if not vals or base.get(p) is None:
                cells.append('<td class="num absent">—</td>')
                continue
            delta = sum(vals) / float(len(vals)) - base[p]
            pts.append((g, delta))
            cells.append('<td class="num %s">%+.3f</td>'
                         % ("up" if delta > 0 else ("down" if delta < 0 else "dim"), delta))
        drift_rows.append('<tr><td>%s</td>%s</tr>' % (label, "".join(cells)))
        if len(pts) > 1:
            drift_series.append({"name": label, "colour": charts.SERIES.get(
                list(charts.SERIES)[len(drift_series) % 4]), "points": pts})
    genhdr = "".join('<th class="num">gen %d</th>' % g for g in sorted(gens) if g)
    drift_table = ('<div class="scroll"><table class="d"><thead><tr><th>trait</th>%s</tr>'
                   '</thead><tbody>%s</tbody></table></div>'
                   '<p class="note">The mean of that generation minus the root\'s own '
                   'value. Traits are inherited with variation at replication, so this is '
                   'drift as it actually happened, not a model of it.</p>'
                   % (genhdr, "".join(drift_rows))) if genhdr else \
        '<p class="absent">this specimen has no recorded descendants</p>'
    drift_chart = (charts.line_chart(drift_series, 520, 210, x_label="generation")
                   + charts.legend([(s["name"], s["colour"]) for s in drift_series])) \
        if len(drift_series) > 1 else ""

    # ---- timeline by generation ------------------------------------------
    tl_rows = []
    born = {g: [rec(k).get("arose_at_shift") for k in gens[g]
                if rec(k).get("arose_at_shift") is not None] for g in sorted(gens)}
    cum = 0
    counts, first_shift, live_share = [], [], []
    for g in sorted(gens):
        cum += len(gens[g])
        counts.append(cum)
        first_shift.append(min(born[g]) if born[g] else None)
        live_share.append(sum(1 for k in gens[g] if k in ind))
    tl_rows.append('<tr><td>first appeared at shift</td>%s</tr>'
                   % "".join('<td class="num">%s</td>' % (num(v) if v is not None else "—")
                             for v in first_shift))
    tl_rows.append('<tr><td>members in generation</td>%s</tr>'
                   % "".join('<td class="num">%s</td>' % num(len(gens[g]))
                             for g in sorted(gens)))
    tl_rows.append('<tr><td>still living</td>%s</tr>'
                   % "".join('<td class="num">%s</td>' % num(v) for v in live_share))
    tl_rows.append('<tr><td>cumulative</td>%s</tr>'
                   % "".join('<td class="num">%s</td>' % num(v) for v in counts))
    tl_rows.append('<tr><td></td>%s</tr>'
                   % "".join('<td>%s</td>' % C.bar(len(gens[g]) /
                                                   float(max(len(v) for v in gens.values())),
                                                   hue) for g in sorted(gens)))
    timeline = ('<div class="scroll"><table class="d"><thead><tr><th></th>%s</tr></thead>'
                '<tbody>%s</tbody></table></div>'
                % ("".join('<th class="num">gen %d</th>' % g for g in sorted(gens)),
                   "".join(tl_rows)))

    # ---- notable events, read from the record ----------------------------
    notable = []
    if b.get("arose_at_shift") is not None:
        notable.append((b["arose_at_shift"], "root first recorded"))
    for g in sorted(gens):
        if g and born[g]:
            notable.append((min(born[g]), "generation %d first appears" % g))
    for k in seen:
        r = rec(k)
        if k not in ind and r.get("last_seen_shift") is not None:
            notable.append((r["last_seen_shift"], "%s ended" % k))
    notable.sort()
    nrows = "".join(
        '<div class="mini"><span>shift %s</span><span></span>'
        '<b style="text-align:left;color:var(--dim);font-size:10.5px">%s</b></div>'
        % (num(s), esc(label)) for s, label in notable[:14]) or \
        '<p class="absent">nothing dated on this line yet</p>'

    ancestry = (C.panel("Ancestry", "".join(
        '<div class="rowlink"><span class="sw" style="background:%s"></span>'
        '<span>%s<span class="s">generation %s · %s</span></span>'
        '<span class="n">%s</span></div>'
        % (charts.hue(t) if i == len(chain) - 1 else "var(--rule)", esc(k),
           num(rec(k).get("generation")),
           "living" if k in ind else "ended",
           num(rec(k).get("descendants")))
        for i, k in enumerate(reversed(chain))) or
        '<p class="absent">this specimen arose from the census. It has no parent, and this '
        'line begins with it.</p>', flush=bool(chain)))

    notes = C.panel("What is traced",
                    '<p class="note">Only recorded parentage. Every box on this page is a '
                    'parent_id the terrain wrote when a specimen replicated; nothing is '
                    'inferred from similarity, position, or category. A specimen whose '
                    'parent has ended still appears — the record of descent outlives the '
                    'parent, and ended members are drawn dimmed rather than dropped.</p>'
                    '<p class="note">The mockup this follows carries a NAMER\'S CONCLUSION '
                    'about the line. The Namer writes about specimens, never about lineages, '
                    'so there is nothing to quote and nothing is invented in its place. What '
                    'it wrote about the root is on the root\'s own record.</p>')

    tabs = [("tree", "Lineage tree", C.panel("Lineage tree", tree + tree_legend,
                                             "%d traced, %d generations" % (len(seen), depth))),
            ("anc", "Ancestry", ancestry),
            ("drift", "Traits &amp; drift",
             C.panel("Trait drift by generation", (drift_chart or "") + drift_table)),
            ("time", "Lineage timeline", C.panel("By generation", timeline)),
            ("notes", "Notes", notes)]
    tabbar = '<div class="tabs">%s</div>' % "".join(
        '<button data-tab="%s"%s>%s</button>' % (k, ' class="on"' if i == 0 else "", label)
        for i, (k, label, _) in enumerate(tabs))
    panes = "".join('<div class="tabpane%s" id="tab-%s">%s</div>'
                    % (" on" if i == 0 else "", k, body)
                    for i, (k, _, body) in enumerate(tabs))

    branch_lengths = [g for g in sorted(gens) for _ in gens[g]]
    mean_branch = (sum(branch_lengths) / float(len(branch_lengths))) if branch_lengths else 0

    left = C.panel("Lineage navigation",
        '<div class="pb" style="padding:9px 11px 4px"><input class="searchbox" id="q" '
        'placeholder="search this lineage…"></div>' + "".join(
        '<%s class="rowlink%s" data-n="%s"%s><span class="sw" style="background:%s"></span>'
        '<span>%s<span class="s">gen %s · %s · %s kid(s)</span></span>'
        '<span class="n">%s</span></%s>'
        % ("a" if k in d.get("_lineages", ()) else "div",
           " on" if k == root else "", esc(k.lower()),
           ' href="/%s/lineage/%s.html"' % (t, esc(k))
           if k in d.get("_lineages", ()) else "",
           hue if k in ind else "var(--faint)", esc(k),
           num(rec(k).get("generation")), "living" if k in ind else "ended",
           num(rec(k).get("descendants")), num(rec(k).get("age")),
           "a" if k in d.get("_lineages", ()) else "div")
        for k in sorted(seen, key=lambda x: (rec(x).get("generation", 0), x))[:60]),
        flush=True) + \
        C.panel("Go to", C.nav([
            ("Specimen record", "/%s/specimens/%s.html" % (t, esc(root)),
             "the root of this line, on its own"),
            ("See it in the field",
             ("http://127.0.0.1:%d/index.html#%s" % (C.PORTS.get(t, 8731), esc(root)))
             if alive else None,
             "opens the deck with the root selected" if alive
             else "no longer in the field"),
            ("Terrain record", "/%s/terrain.html" % t, "the terrain this line runs in"),
        ]))

    right = C.panel("Lineage summary", C.kv([
        ("root specimen", esc(root)),
        ("root state", "living" if alive else "ended"),
        ("depth", "%d generation(s)" % depth),
        ("members traced", num(len(seen))),
        ("living now", num(len(living))),
        ("ended", num(len(extinct))),
        ("mean depth", "%.2f generations" % mean_branch),
        ("root's own descendants", num(b.get("descendants"))),
        ("first recorded", "shift %s" % num(b.get("arose_at_shift"))),
    ])) + C.panel("Members per generation", "".join(
        '<div class="mini"><span>gen %d</span>%s<b>%d</b></div>'
        % (g, C.bar(len(gens[g]) / float(max(len(v) for v in gens.values())), hue),
           len(gens[g])) for g in sorted(gens))) + \
        C.panel("Notable events on this line", nrows) + \
        C.panel("Export", C.nav([
            ("Lineage (CSV)", "/%s/exports/lineage-%s.csv" % (t, esc(root)),
             "every traced member, with its measurements"),
        ]))

    mid = ('<div class="hdr"><div><p class="eyebrow">Lineage record</p>'
           '<h1 class="doc mono">%s</h1>'
           '<p class="sub"><span class="chip %s">%s</span> %s · generation %s%s</p></div>'
           '<table class="doc">'
           '<tr><td class="k">TERRAIN</td><td class="v">%s</td></tr>'
           '<tr><td class="k">SHIFT</td><td class="v">%s</td></tr>'
           '<tr><td class="k">DEPTH</td><td class="v">%d GENERATION(S)</td></tr>'
           '<tr><td class="k">TRACED</td><td class="v">%s</td></tr></table></div>'
           % (esc(root), "on" if alive else "off", "LIVING" if alive else "ENDED",
              esc((d["named"].get(root) or {}).get("category") or "not yet named"),
              num(b.get("generation")), " (root)" if not b.get("parent_id") else "",
              esc(d["name"]), esc(d["shift"]), depth, num(len(seen))))
    mid += C.stats([
        (num(len(seen)), "traced", "from parentage"),
        (num(len(living)), "living now"),
        (num(len(extinct)), "ended"),
        ("%d" % depth, "generations", "below the root"),
        (num(b.get("descendants")), "root's descendants"),
        ("%.1f" % mean_branch, "mean depth", "generations"),
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

    return C.page("%s — Lineage" % esc(root), "LINEAGE RECORD", t,
                  [("TERRAINS", C.HUB + "/hub.html"),
                   (d["name"], "/%s/terrain.html" % t),
                   ("SPECIMEN %s" % esc(root), "/%s/specimens/%s.html" % (t, esc(root))),
                   ("LINEAGE", None)],
                  d["shift"], d["committed_at"], mid, left, right,
                  CSS + charts.CSS, current="lineage", scripts=script)


# ===========================================================================
# checkpoint report
# ===========================================================================
CHECKPOINT_EVERY = 14


def checkpoints_for(d):
    """Every window the record supports, at a fixed stride.

    The mockup shows a list of checkpoints a user created. Nobody creates one
    here: a checkpoint is a pair of shifts and the arithmetic between them, so
    every window the log can support already exists and is simply listed.
    """
    rows = d["shifts"]
    if len(rows) < 2:
        return []
    out = []
    i = CHECKPOINT_EVERY
    while i < len(rows):
        out.append((rows[i - CHECKPOINT_EVERY], rows[i]))
        i += CHECKPOINT_EVERY
    if not out or out[-1][1] is not rows[-1]:
        out.append((rows[max(0, len(rows) - 1 - CHECKPOINT_EVERY)], rows[-1]))
    return out


def checkpoint_report(d: Dict[str, Any], window: int = CHECKPOINT_EVERY) -> str:
    t, m, rows = d["dir"], d["memory"], d["shifts"]
    if len(rows) < 2:
        return ""
    hue = charts.hue(t)
    last = rows[-1]
    earlier = rows[max(0, len(rows) - 1 - window)]
    a, b = earlier.get("shift"), last.get("shift")
    span = rows[max(0, len(rows) - 1 - window):]

    def pair(key):
        va, vb = earlier.get(key), last.get(key)
        if not isinstance(va, (int, float)) or not isinstance(vb, (int, float)):
            return None
        return (va, vb, vb - va, ((vb - va) / va * 100.0) if va else None)

    HEAD = [("total shifts", None), ("living specimens", "living"),
            ("native categories", None), ("descendant threads", None),
            ("cover cells", None), ("active links", None),
            ("resource flow", "resource_flow")]

    cats_at = {}
    seen = set()
    for r in rows:
        for cat in (r.get("new_categories") or []):
            seen.add(cat)
        cats_at[r.get("shift")] = len(seen)
    cats_a, cats_b = cats_at.get(a, 0), cats_at.get(b, 0)

    kids = sum(1 for x in d["individuals"].values() if x.get("parent_id"))
    cover_now = sum(1 for c in (d["world"].get("cells") or [])
                    if c.get("census_density", 0) > 0)
    links_now = len([1 for v in (d["world"].get("links") or {}).values()
                     if v.get("formed_at_shift") is not None])

    def stat(value, label, delta=None, pct=None, sub=""):
        s = sub
        if delta is not None:
            cls = "up" if delta > 0 else ("down" if delta < 0 else "dim")
            s = ('<span class="%s">%+s%s</span>'
                 % (cls, num(delta), (" (%+.2f%%)" % pct) if pct is not None else ""))
        return (num(value), label, s)

    liv = pair("living")
    flow = pair("resource_flow")
    strip = C.stats([
        (num(b - a if isinstance(a, int) and isinstance(b, int) else "—"), "shifts in window",
         "%s &rarr; %s" % (num(a), num(b))),
        stat(last.get("living"), "living specimens",
             liv[2] if liv else None, liv[3] if liv else None),
        stat(cats_b, "native categories", cats_b - cats_a,
             ((cats_b - cats_a) / cats_a * 100.0) if cats_a else None),
        (num(kids), "descendant threads", "with a parent still living"),
        (num(cover_now), "cover cells", "of %s" % num(len(d["world"].get("cells") or []))),
        (num(links_now), "active links", "between specimens"),
        stat(last.get("resource_flow"), "resource flow",
             flow[2] if flow else None, flow[3] if flow else None),
    ])

    # ---- charts ---------------------------------------------------------
    xs = [r.get("shift") for r in rows]
    pop_series = [
        {"name": "living specimens", "colour": hue,
         "points": [(r.get("shift"), r.get("living")) for r in rows
                    if r.get("living") is not None]},
    ]
    repl_run, total = [], 0
    for r in rows:
        total += (r.get("replicated_this_shift") or 0)
        repl_run.append((r.get("shift"), total))
    pop_series.append({"name": "replications, cumulative", "colour": "#B37BD6",
                       "points": repl_run})
    pop_chart = charts.line_chart(pop_series, 440, 220, x_label="shift",
                                  markers=[(a, str(a)), (b, str(b))], y_zero=True)

    cls_series = [
        {"name": "native categories", "colour": hue,
         "points": [(r.get("shift"), cats_at.get(r.get("shift"), 0)) for r in rows]},
        {"name": "classified this shift", "colour": "#4FA3E3",
         "points": [(r.get("shift"), r.get("classified") or 0) for r in rows]},
    ]
    cls_chart = charts.line_chart(cls_series, 440, 220, x_label="shift", y_zero=True)

    flow_series = [
        {"name": "resource flow", "colour": "#A8D45C",
         "points": [(r.get("shift"), r.get("resource_flow")) for r in span
                    if r.get("resource_flow") is not None]},
        {"name": "arose", "colour": "#4FA3E3",
         "points": [(r.get("shift"), r.get("arose_this_shift") or 0) for r in span]},
        {"name": "ended", "colour": "#D4614A",
         "points": [(r.get("shift"), r.get("ended_this_shift") or 0) for r in span]},
    ]
    flow_chart = charts.line_chart(flow_series, 440, 220, x_label="shift")

    # ---- comparison tables ----------------------------------------------
    def ctable(items):
        out = []
        for label, va, vb in items:
            if not isinstance(va, (int, float)) or not isinstance(vb, (int, float)):
                out.append('<tr><td>%s</td><td colspan="3" class="absent">not recorded at '
                           'both shifts</td></tr>' % label)
                continue
            diff = vb - va
            cls = "up" if diff > 0 else ("down" if diff < 0 else "dim")
            pct = ("%+.2f%%" % (diff / va * 100.0)) if va else "—"
            out.append('<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
                       '<td class="num %s">%+s</td><td class="num %s">%s</td></tr>'
                       % (label, num(va), num(vb), cls, num(diff), cls, pct))
        return ('<div class="scroll"><table class="d"><thead><tr><th>metric</th>'
                '<th class="num">shift %s</th><th class="num">shift %s</th>'
                '<th class="num">change</th><th class="num">change %%</th></tr></thead>'
                '<tbody>%s</tbody></table></div>' % (num(a), num(b), "".join(out)))

    pop_table = ctable([
        ("living specimens", earlier.get("living"), last.get("living")),
        ("arose this shift", earlier.get("arose_this_shift"), last.get("arose_this_shift")),
        ("ended this shift", earlier.get("ended_this_shift"), last.get("ended_this_shift")),
        ("replicated this shift", earlier.get("replicated_this_shift"),
         last.get("replicated_this_shift")),
        ("links formed this shift", earlier.get("links_formed"), last.get("links_formed")),
    ])
    cls_table = ctable([
        ("native categories", cats_a, cats_b),
        ("classified this shift", earlier.get("classified"), last.get("classified")),
        ("anomalous this shift", earlier.get("anomalous"), last.get("anomalous")),
        ("unresolved this shift", earlier.get("unresolved"), last.get("unresolved")),
    ])
    ce, cl = earlier.get("census") or {}, last.get("census") or {}
    res_table = ctable([
        ("resource flow", earlier.get("resource_flow"), last.get("resource_flow")),
        ("cells occupied", ce.get("cells_occupied"), cl.get("cells_occupied")),
        ("total cover density", ce.get("total_density"), cl.get("total_density")),
        ("residue pool", ce.get("residue_pool"), cl.get("residue_pool")),
    ])

    # ---- spatial distribution -------------------------------------------
    cells = d["world"].get("cells") or []
    width_cells = (m.get("landscape") or {}).get("width") or grid_width_of(d)
    dens = [0.0] * (max((c.get("index", 0) for c in cells), default=-1) + 1)
    for c in cells:
        dens[c.get("index", 0)] = float(c.get("census_density", 0.0) or 0.0)
    dmap = charts.density_map(dens, width_cells, 300, 210)

    # ---- lineage depth distribution --------------------------------------
    depth: Dict[int, int] = {}
    for x in d["individuals"].values():
        g = int(x.get("generation", 0) or 0)
        depth[g] = depth.get(g, 0) + 1
    tot = sum(depth.values()) or 1
    drows = "".join(
        '<tr><td class="num">%d%s</td><td class="num">%s</td><td class="num">%.1f%%</td>'
        '<td>%s</td></tr>'
        % (g, " (root)" if g == 0 else "", num(depth[g]), 100.0 * depth[g] / tot,
           C.bar(depth[g] / float(max(depth.values()))))
        for g in sorted(depth)) or \
        '<tr><td colspan="4" class="absent">no living specimens</td></tr>'

    # ---- what appeared in this window ------------------------------------
    # Deduped on read. BASIN-01 through BASIN-04 record a category as newly
    # coined every time the Namer declares it new, including when it had coined
    # it already — so counting the raw field inflates the figure. Their records
    # stand as written; the count shown here is of DISTINCT categories.
    coined, already = [], set()
    for r in rows[:len(rows) - len(span)]:
        already.update(r.get("new_categories") or [])
    for r in span:
        for cat in (r.get("new_categories") or []):
            if cat not in already:
                already.add(cat)
                coined.append((r.get("shift"), cat))
    stats_map = m.get("category_stats") or {}
    emerg = "".join(
        '<tr><td><a href="/%s/categories/%s.html">%s</a></td>'
        '<td class="num">%s</td><td class="num">%s</td><td class="dim">%s</td></tr>'
        % (t, slug(cat), esc(cat), esc(sh),
           num((stats_map.get(cat) or {}).get("count", 0)),
           "still filed to" if (stats_map.get(cat) or {}).get("last_seen_shift") == b
           else "last filed shift %s" % esc((stats_map.get(cat) or {}).get("last_seen_shift")))
        for sh, cat in reversed(coined)) or \
        '<tr><td colspan="4" class="absent">no category was coined in this window</td></tr>'

    # ---- measured indicators, not grades ---------------------------------
    pop_w = [r.get("living") for r in span if r.get("living") is not None]
    slope = ((pop_w[-1] - pop_w[0]) / float(len(pop_w) - 1)) if len(pop_w) > 1 else 0.0
    peak = max(pop_w) if pop_w else 0
    trough_after = min(pop_w[pop_w.index(peak):]) if pop_w else 0
    drawdown = (100.0 * (peak - trough_after) / peak) if peak else 0.0
    cv = dnt_data.coefficient_of_variation(pop_w)
    anom_w = sum(r.get("anomalous", 0) or 0 for r in span)
    unres_w = sum(r.get("unresolved", 0) or 0 for r in span)
    div = dnt_data.shannon_diversity([c.get("count", 0) for c in stats_map.values()])
    indicators = C.kv([
        ("population slope", "%+.1f living per shift" % slope),
        ("largest drawdown", "%.1f%% from the window's peak" % drawdown),
        ("steadiness (CV)", "—" if cv is None else "%.4f" % cv),
        ("classification diversity", "—" if div is None else "%.4f" % div),
        ("anomalous in window", num(anom_w)),
        ("unresolved in window", num(unres_w)),
    ])

    canon = [r for r in rows if (r.get("phase") or "") != "ollama"]

    findings = []
    if liv:
        findings.append("Living population %s by %s (%s) across the window."
                        % ("rose" if liv[2] > 0 else ("fell" if liv[2] < 0 else "held"),
                           num(abs(liv[2])),
                           ("%+.2f%%" % liv[3]) if liv[3] is not None else "—"))
    findings.append("%s category(ies) coined in this window; %s on the record in total."
                    % (num(len(coined)), num(cats_b)))
    findings.append("Deepest generation among the living is %s."
                    % num(max(depth) if depth else 0))
    findings.append("%s anomalous and %s unresolved. Anomalous is the Namer reporting "
                    "something it could not place; unresolved is the model failing to "
                    "answer." % (num(anom_w), num(unres_w)))
    findings.append("Largest drawdown from the window's peak was %.1f%%." % drawdown)

    ck_list = checkpoints_for(d)
    left = C.panel("Terrain navigation", "".join(
        '<a class="rowlink%s" href="/%s/checkpoint.html"><span class="sw" '
        'style="background:%s"></span><span>%s<span class="s">shift %s</span></span>'
        '<span></span></a>'
        % (" on" if x == t else "", x, charts.hue(x), x.upper(),
           esc((dnt_data.load(x) or {}).get("memory", {}).get("last_committed_shift", "—")))
        for x in TERRAINS if os.path.exists(os.path.join(ROOT, x, "checkpoint.html"))),
        flush=True) + \
        C.panel("Windows the log supports", "".join(
            '<div class="rowlink%s"><span></span><span>shift %s &rarr; %s'
            '<span class="s">%s</span></span><span></span></div>'
            % (" on" if (x[0] is earlier and x[1] is last) else "",
               esc(x[0].get("shift")), esc(x[1].get("shift")),
               esc((x[1].get("end_timestamp") or "")[:10]))
            for x in reversed(ck_list[-8:])), flush=True) + \
        C.panel("Report sections", C.section_nav(
            (("Summary", "top"), ("Population and flow", "pop"),
             ("Spatial and descent", "spatial"))), flush=True) + \
        C.panel("Go to", C.nav([
            ("Terrain record", "/%s/terrain.html" % t, "current state and conditions"),
            ("Shift log", "/%s/shiftlog.html" % t, "the rows this report reads"),
            ("Comparative study",
             "/study.html" if os.path.exists(os.path.join(ROOT, "study.html")) else None,
             "this terrain beside the others"),
        ]))

    right = C.panel("Key findings",
                    '<ul class="find">%s</ul>' % "".join('<li>%s</li>' % f for f in findings)) + \
        C.panel("Comparative snapshot",
                '<div class="scroll"><table class="d"><thead><tr><th></th>'
                '<th class="num">%s</th><th class="num">%s</th><th class="num">Δ</th>'
                '</tr></thead><tbody>%s</tbody></table></div>'
                % (num(a), num(b), "".join(
                    '<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
                    '<td class="num %s">%+s</td></tr>'
                    % (label, num(va), num(vb),
                       "up" if vb - va > 0 else ("down" if vb - va < 0 else "dim"), num(vb - va))
                    for label, va, vb in (
                        ("living", earlier.get("living") or 0, last.get("living") or 0),
                        ("categories", cats_a, cats_b),
                        ("classified", earlier.get("classified") or 0,
                         last.get("classified") or 0),
                        ("links formed", earlier.get("links_formed") or 0,
                         last.get("links_formed") or 0))))) + \
        C.panel("Indicators", indicators +
                '<p class="note">Measured, not graded. The mockup this follows carries an '
                'assessment — trajectory, health, resilience, risk — and an authority who '
                'signed it. DNT does not evaluate terrains and nobody signs a checkpoint '
                'off, so what is reported is the arithmetic and its definitions.</p>') + \
        C.panel("Falsification checkpoint", C.kv([
            ("condition", "physics.md §11"),
            ("canonical shifts run", num(len(canon))),
            ("required", "15"),
            ("status", "reached" if len(canon) >= 15 else
             "not yet — %d to go" % (15 - len(canon))),
        ]) + '<p class="note">Phase 1 shifts on the local model do not count toward it. '
             'This reports whether the condition has been REACHED. Evaluating it is a '
             'separate reading of the record and is not done here.</p>')

    mid = ('<div class="hdr" id="top"><div><p class="eyebrow">%s · checkpoint</p>'
           '<h1 class="doc">Checkpoint Report</h1>'
           '<p class="sub"><b style="color:%s">%s</b> · shift %s &rarr; shift %s · '
           'state comparison computed from the shift log.</p></div>'
           '<table class="doc">'
           '<tr><td class="k">CHECKPOINT</td><td class="v">%s-CKP-%s</td></tr>'
           '<tr><td class="k">COMPUTED FROM</td><td class="v">SHIFT LOG</td></tr>'
           '<tr><td class="k">WINDOW</td><td class="v">%s SHIFTS</td></tr>'
           '<tr><td class="k">PHYSICS</td><td class="v">%s</td></tr></table></div>'
           % (esc(d["name"]), hue, esc(d["name"]), num(a), num(b),
              esc(d["name"]), esc(b),
              num(b - a if isinstance(a, int) and isinstance(b, int) else "—"),
              esc(m.get("physics_document") or "—")))
    mid += strip
    mid += ('<div class="charts3" id="pop">%s%s%s</div>'
            % ('<section class="p"><div class="ph"><b>Population over time</b></div>'
               '<div class="pb">%s%s%s</div></section>'
               % (pop_chart,
                  charts.legend([("living", hue), ("replications, cumulative", "#B37BD6")]),
                  pop_table),
               '<section class="p"><div class="ph"><b>Classification growth</b></div>'
               '<div class="pb">%s%s%s</div></section>'
               % (cls_chart,
                  charts.legend([("native categories", hue),
                                 ("classified this shift", "#4FA3E3")]),
                  cls_table),
               '<section class="p"><div class="ph"><b>Flow, arrivals and endings</b></div>'
               '<div class="pb">%s%s%s</div></section>'
               % (flow_chart,
                  charts.legend([("resource flow", "#A8D45C"), ("arose", "#4FA3E3"),
                                 ("ended", "#D4614A")]),
                  res_table)))
    mid += ('<div class="charts3" id="spatial">%s%s%s</div>'
            % (C.panel("Spatial distribution",
                       dmap + '<p class="note">Cover density per cell at shift %s, drawn '
                       'from the same grid the deck reads. Brighter is denser.</p>' % num(b)),
               C.panel("Lineage depth distribution",
                       '<div class="scroll"><table class="d"><thead><tr>'
                       '<th class="num">generation</th><th class="num">living</th>'
                       '<th class="num">share</th><th></th></tr></thead><tbody>%s</tbody>'
                       '</table></div><p class="note">Generations from a root, walked from '
                       'recorded parentage.</p>' % drows),
               C.panel("Categories coined in this window",
                       '<div class="scroll"><table class="d"><thead><tr><th>category</th>'
                       '<th class="num">coined at</th><th class="num">filed</th>'
                       '<th>since</th></tr></thead><tbody>%s</tbody></table></div>'
                       % emerg)))
    return C.page("%s — Checkpoint %s → %s" % (d["name"], num(a), num(b)),
                  "CHECKPOINT REPORT", t,
                  [("TERRAINS", C.HUB + "/hub.html"),
                   (d["name"], "/%s/terrain.html" % t),
                   ("CHECKPOINT %s → %s" % (num(a), num(b)), None)],
                  d["shift"], d["committed_at"], mid, left, right,
                  CSS + charts.CSS, current="checkpoint", scripts=C.SECTION_JS)


def grid_width_of(d):
    ls = (d["memory"].get("landscape") or {})
    if ls.get("width"):
        return int(ls["width"])
    path = os.path.join(ROOT, d["dir"], "life.py")
    try:
        with open(path, encoding="utf-8") as stream:
            found = re.search(r"^FIELD_WIDTH\s*=\s*(\d+)", stream.read(), re.M)
        if found:
            return int(found.group(1))
    except IOError:
        pass
    return len(d["world"].get("cells") or []) or 1


# ===========================================================================
# comparative terrain study
# ===========================================================================
def _norm(points):
    """Index a series to its own MEAN, so shapes compare and scales do not.

    Indexing to the first value looks reasonable and is not: a terrain that
    began with one living specimen indexes its own population to 10,589, and
    the panel becomes a chart of how small each terrain started. The mean is
    stable, puts every terrain around 1.0, and leaves the shape untouched.
    """
    vals = [v for v in points if v is not None]
    if not vals:
        return []
    base = sum(vals) / float(len(vals))
    if not base:
        return []
    return [(v / base) if v is not None else None for v in points]


def _resample(series, n=26):
    """Put a terrain's whole life on a 0..1 axis, so ages compare."""
    vals = [v for v in series if v is not None]
    if len(vals) < 2:
        return []
    out = []
    for i in range(n):
        f = i / float(n - 1)
        pos = f * (len(vals) - 1)
        a = int(math.floor(pos))
        b = min(len(vals) - 1, a + 1)
        frac = pos - a
        out.append((f * 100.0, vals[a] + (vals[b] - vals[a]) * frac))
    return out


def _lineage_depth(d):
    """Mean generations from a root, walked from recorded parentage."""
    ind = d["individuals"]
    gens = [b.get("generation", 0) or 0 for b in ind.values()]
    return (sum(gens) / float(len(gens))) if gens else 0.0


def _per_hundred(d, key):
    rows = d["shifts"]
    if not rows:
        return 0.0
    return sum(r.get(key, 0) or 0 for r in rows) * 100.0 / len(rows)


def labels_all(shown):
    """Every governing-condition label any terrain in the set declares."""
    out = []
    for d in shown:
        for g in dnt_data.governing_conditions(d["dir"]):
            if g["label"] not in out:
                out.append(g["label"])
    return out


def comparative_study(loaded: List[Dict[str, Any]]) -> str:
    """Every terrain side by side, on quantities all of them actually record."""
    # Every terrain that exists is listed. Only those that have committed a
    # shift can be plotted or compared — but a founded terrain silently missing
    # from the department's own comparison is worse than one shown as unrun.
    everything = [d for d in loaded if d]
    shown = [d for d in everything if d["shifts"]]
    unrun = [d for d in everything if not d["shifts"]]
    if len(shown) < 2:
        return ""
    for d in shown:
        d["_hue"] = charts.hue(d["dir"])

    # ---- trajectories: five panels, each terrain on its own life axis -----
    def track(fn, normalise=True):
        out = []
        for d in shown:
            raw = fn(d)
            pts = _resample(_norm(raw) if normalise else raw)
            if pts:
                out.append({"name": d["name"], "colour": d["_hue"], "points": pts})
        return out

    def cumulative_categories(d):
        seen, run = set(), []
        for r in d["shifts"]:
            for cat in (r.get("new_categories") or []):
                seen.add(cat)
            run.append(len(seen))
        return run

    def net_flow(d):
        return [r.get("resource_flow") for r in d["shifts"]]

    def stability_track(d):
        pop = [r.get("living") for r in d["shifts"]]
        out, win = [], 20
        for i in range(len(pop)):
            w = [v for v in pop[max(0, i - win):i + 1] if v is not None]
            cv = dnt_data.coefficient_of_variation(w)
            out.append(None if cv is None else 1.0 - min(1.0, cv))
        return out

    def lineage_track(d):
        # mean generation among the living, shift by shift, is not logged;
        # what IS logged is how many replicated each shift, cumulatively.
        run, total = [], 0
        for r in d["shifts"]:
            total += (r.get("replicated_this_shift") or 0)
            run.append(total)
        return run

    # The panel titled "classification diversity" was counting CATEGORIES
    # COINED, which is not diversity — diversity is the Shannon figure in the
    # aggregate table, and a terrain can coin many categories while remaining
    # concentrated in one. Renamed to what it actually plots.
    panels = [
        ("Living population", "index",
         track(lambda d: [r.get("living") for r in d["shifts"]]),
         "living",
         [("What this shows",
           ["The count of living specimens each shift recorded when it closed, "
            "for every shift the terrain has committed.",
            "Source: the <code>living</code> field on each row of that terrain's "
            "own shift log. Nothing is smoothed or interpolated."]),
          ("How to read it",
           ["Each line is indexed to <b>that terrain's own mean</b>, so 1.0 is its "
            "own average population and 2.0 is twice it. Heights are NOT comparable "
            "between terrains — BASIN-01 holds 21 living and BASIN-03 holds 10,589.",
            "The x axis is each terrain's own life as a percentage, so a terrain of "
            "128 shifts and one of 218 sit on the same axis. <b>Compare the shapes, "
            "never the heights.</b>"]),
          ("What it does not show",
           ["It is not a population size. A line at 4.0 means four times that "
            "terrain's own average, not four times another terrain's.",
            "A terrain that has run one shift has no shape to draw and is absent "
            "from the panel rather than drawn flat."])]),

        ("Native categories, cumulative", "running count of categories coined",
         track(cumulative_categories), "categories",
         [("What this shows",
           ["The running total of distinct categories the Namer has coined, "
            "accumulated shift by shift and never decreasing.",
            "Source: the <code>new_categories</code> list each shift wrote."]),
          ("How to read it",
           ["A step means the Namer met something it decided needed a new name. "
            "A long flat stretch means it kept filing into names it already had.",
            "Indexed to each terrain's own mean, like the other panels."]),
          ("What it does not show",
           ["This is a <b>count</b>, not diversity. A terrain can coin twelve "
            "categories and still file 82% of everything into one of them — "
            "BASIN-03 does exactly that. The diversity figure that accounts for "
            "how full each category is (Shannon entropy) is in the aggregate "
            "metrics table below, not here."])]),

        ("Replication, cumulative", "running total of replications",
         track(lineage_track), "replication",
         [("What this shows",
           ["Every replication the terrain has recorded, accumulated over its life.",
            "Source: the <code>replicated_this_shift</code> field per shift."]),
          ("How to read it",
           ["Slope is the replication rate. A steepening curve means replication is "
            "accelerating; a straightening one means it has settled.",
            "Replication is how a specimen leaves descendants, so this is the raw "
            "material every lineage record is built from."]),
          ("What it does not show",
           ["Not survival. A replication that ended the next shift still counts "
            "here. What lasted is in the persistence table."])]),

        ("Resource flow", "index", track(net_flow), "flow",
         [("What this shows",
           ["The resource flow logged at each shift — the light entering the "
            "terrain and driving its entire economy.",
            "Source: the <code>resource_flow</code> field per shift."]),
          ("How to read it",
           ["This is an input, not an outcome. It oscillates by design where a "
            "terrain has a light cycle, and the sawtooth on these lines is that "
            "oscillation, not noise.",
            "BASIN-03 and BASIN-04 run a 12-shift light cycle; BASIN-01 and "
            "BASIN-02 have no such mechanism."]),
          ("What it does not show",
           ["Not what the population actually took in. Light that arrives can go "
            "uncollected, and what was collected is in the composition figures on "
            "each specimen record."])]),

        ("Population steadiness", "1 − CV over a trailing 20-shift window",
         track(stability_track, False), "steadiness",
         [("What this shows",
           ["How steady the population has been, measured over the previous 20 "
            "shifts at every point in the terrain's life.",
            "Computed as <b>1 − CV</b>, where CV is the coefficient of variation "
            "(σ / μ) of the living count across that window."]),
          ("How to read it",
           ["Higher is steadier. It is subtracted from 1 so that <b>up means "
            "steadier on this panel as on every other</b> — raw CV runs the other "
            "way and reading a panel backwards is easy to do.",
            "The rise every terrain shows early on is a terrain finding its "
            "footing from a near-empty start, not a trend."]),
          ("What it does not show",
           ["Not health, and not a grade. A steady terrain is not a better one; "
            "DNT does not evaluate terrains.",
            "This panel is NOT indexed to the mean — it is the raw figure, because "
            "it is already a ratio."])]),
    ]
    traj = "".join(
        '<div class="tj mdl-open" data-modal="mdl-%s" data-modal-title="%s" '
        'data-modal-sub="%s"><div class="ct">%s<span class="mdl-hint">enlarge</span></div>'
        '<div class="cs">%s</div>%s</div>'
        % (key, title, sub, title, sub,
           charts.line_chart(sers, 420, 210, x_label="terrain life (%)"))
        for title, sub, sers, key, _ in panels)

    # the enlarged figure and its explanation, held in the page
    store = [("mdl-%s" % key,
              '<div class="mdl-fig">%s%s</div>%s'
              % (charts.line_chart(sers, 1040, 420, x_label="terrain life (%)"),
                 charts.legend([(d["name"], d["_hue"]) for d in shown]),
                 C.readable(read)))
             for title, sub, sers, key, read in panels]

    # ---- terrain cards, with the terrain itself as the picture -----------
    cards = []
    for d in shown:
        gov = {g["label"]: g for g in dnt_data.governing_conditions(d["dir"])}
        rows = d["shifts"]
        first = C.stamp(rows[0].get("end_timestamp")) if rows else "not yet committed"
        conds = []
        for label in ("gravity", "temperature at stream", "light cycle",
                      "wind strength", "subsurface rate"):
            g = gov.get(label)
            conds.append('<dt>%s</dt><dd%s>%s</dd>'
                         % (label, "" if (g and g["present"]) else ' class="na"',
                            esc(g["value"]) if (g and g["present"]) else "no mechanism"))
        cards.append(
            '<section class="tcard" style="border-color:%s">'
            '<div class="tch"><b style="color:%s">%s</b>'
            '<span class="chip on">ACTIVE</span></div>'
            '%s'
            '<div class="tcb"><dl class="kv"><dt>first committed</dt><dd>%s</dd>'
            '<dt>age (shifts)</dt><dd>%s</dd><dt>cells</dt><dd>%s</dd>'
            '<dt>physics</dt><dd>%s</dd></dl>'
            '<div class="tcg">Governing conditions</div><dl class="kv">%s</dl>'
            '<a class="nav" href="/%s/terrain.html"><span class="t">Terrain record'
            '<span class="go">&rarr;</span></span></a></div></section>'
            % (d["_hue"], d["_hue"], esc(d["name"]),
               snapshot.isometric(d["dir"], 330, 132),
               first, num(len(rows)),
               num(len(d["world"].get("cells") or [])),
               esc(d["memory"].get("physics_document") or "—"),
               "".join(conds), d["dir"]))

    # ---- aggregate metrics, with a median column -------------------------
    METRICS = [
        ("living specimens", lambda d: d["shifts"][-1].get("living") if d["shifts"] else 0),
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
        ("mean generation", _lineage_depth),
        ("classification diversity", lambda d: dnt_data.shannon_diversity(
            [c.get("count", 0) for c in (d["memory"].get("category_stats") or {}).values()])),
        ("population stability (CV)", lambda d: dnt_data.coefficient_of_variation(
            [r.get("living") for r in d["shifts"][-40:]])),
        ("cumulative spend", lambda d: float(d["memory"].get("cumulative_cost_usd", 0.0))),
    ]
    head = "".join('<th class="num" style="color:%s">%s</th>' % (d["_hue"], esc(d["name"]))
                   for d in shown)
    agg, medians = [], {}
    for label, fn in METRICS:
        vals = []
        for d in shown:
            try:
                vals.append(fn(d))
            except Exception:
                vals.append(None)
        good = sorted(v for v in vals if isinstance(v, (int, float)))
        med = (good[len(good) // 2] if len(good) % 2 else
               (good[len(good) // 2 - 1] + good[len(good) // 2]) / 2.0) if good else None
        medians[label] = (med, vals)
        agg.append('<tr><td>%s</td>%s<td class="num dim">%s</td></tr>'
                   % (label,
                      "".join('<td class="num">%s</td>' % ("—" if v is None else num(v))
                              for v in vals),
                      "—" if med is None else num(med)))

    # ---- how each terrain sits against the median of its peers -----------
    KEY = ["living specimens", "native categories", "descendant threads",
           "mean generation", "classification diversity", "population stability (CV)"]
    keyrows = []
    for label in KEY:
        med, vals = medians.get(label, (None, []))
        cells = []
        for v in vals:
            if med in (None, 0) or v is None:
                cells.append('<td class="num absent">—</td>')
                continue
            pct = (v - med) / abs(med) * 100.0
            cls = "up" if pct > 0 else ("down" if pct < 0 else "dim")
            # Beyond a few hundred percent a percentage stops being readable.
            # A multiple says the same thing and can be held in the head.
            if abs(pct) >= 200 and med:
                cells.append('<td class="num %s">×%.1f</td>' % (cls, v / float(med)))
            else:
                cells.append('<td class="num %s">%+.0f%%</td>' % (cls, pct))
        keyrows.append('<tr><td>%s</td>%s</tr>' % (label, "".join(cells)))

    # ---- event frequency, per hundred shifts -----------------------------
    EVENTS = [("births / replications", "replicated_this_shift"),
              ("arrivals", "arose_this_shift"),
              ("endings", "ended_this_shift"),
              ("links formed", "links_formed"),
              ("classifications", "classified"),
              ("anomalous", "anomalous"),
              ("unresolved", "unresolved")]
    evrows = "".join(
        '<tr><td>%s</td>%s</tr>'
        % (label, "".join('<td class="num">%.1f</td>' % _per_hundred(d, key)
                          for d in shown))
        for label, key in EVENTS)

    # ---- persistence: how long things last ------------------------------
    def persistence(d):
        ages = [b.get("age", 0) or 0 for b in d["individuals"].values()]
        ended = [e.get("age", 0) or 0 for e in (d["world"].get("ended") or [])]
        both = ages + ended
        if not both:
            return (0.0, 0.0, 0.0)
        both.sort()
        over5 = 100.0 * sum(1 for a in both if a > 5) / len(both)
        over20 = 100.0 * sum(1 for a in both if a > 20) / len(both)
        return (both[len(both) // 2], over5, over20)
    perс = [persistence(d) for d in shown]
    prows = "".join(
        '<tr><td>%s</td>%s</tr>'
        % (label, "".join('<td class="num">%s</td>' % fmt(p[i]) for p in perс))
        for i, (label, fmt) in enumerate((
            ("median lifespan (shifts)", lambda v: num(v)),
            ("lasted more than 5 shifts", lambda v: "%.0f%%" % v),
            ("lasted more than 20 shifts", lambda v: "%.0f%%" % v))))

    # ---- findings, computed rather than asserted -------------------------
    findings = []
    for label in ("living specimens", "native categories", "classification diversity",
                  "population stability (CV)"):
        med, vals = medians.get(label, (None, []))
        pairs = [(v, d) for v, d in zip(vals, shown) if isinstance(v, (int, float))]
        if not pairs:
            continue
        top = max(pairs, key=lambda p: p[0])
        low = min(pairs, key=lambda p: p[0])
        if label == "population stability (CV)":
            findings.append('<li><b style="color:%s">%s</b> holds the steadiest population '
                            '(CV %.4f); <b style="color:%s">%s</b> the least steady '
                            '(%.4f).</li>'
                            % (low[1]["_hue"], esc(low[1]["name"]), low[0],
                               top[1]["_hue"], esc(top[1]["name"]), top[0]))
        else:
            findings.append('<li><b style="color:%s">%s</b> leads on %s (%s), against a '
                            'median of %s across %d terrains.</li>'
                            % (top[1]["_hue"], esc(top[1]["name"]), label, num(top[0]),
                               num(med), len(pairs)))
    findings.append('<li>These are the largest and smallest figures in the set. They are '
                    'not rankings: the terrains run under different conditions and for '
                    'different lengths of time.</li>')

    NAVSECTIONS = [("Study overview", "top"),
                   ("Trajectories", "traj"), ("Aggregate metrics", "agg"),
                   ("Against the median", "key"), ("Event frequency", "ev"),
                   ("Persistence", "pers"), ("Method", "method")]
    unrun_note = "".join(
        '<div class="rowlink"><span class="sw" style="background:%s;opacity:.45"></span>'
        '<span>%s<span class="s">founded, no shift committed</span></span>'
        '<span></span></div>' % (charts.hue(d["dir"]), esc(d["name"])) for d in unrun)

    left = C.panel("Study navigation",
                   C.section_nav(NAVSECTIONS[:1]) +
                   '<a class="rowlink mdl-open" data-modal="mdl-terrains" '
                   'data-modal-title="Terrain comparison" '
                   'data-modal-sub="all four terrains, side by side"><span></span>'
                   '<span>Terrain comparison</span>'
                   '<span class="mdl-hint">open</span></a>' +
                   C.section_nav(NAVSECTIONS[1:]), flush=True) + \
        C.panel("Terrains in study", "".join(
            '<div class="rowlink"><span class="sw" style="background:%s"></span>'
            '<span>%s<span class="s">shift %s · %s cells</span></span><span></span></div>'
            % (d["_hue"], esc(d["name"]), num(d["shift"]),
               num(len(d["world"].get("cells") or []))) for d in shown)
            + unrun_note, flush=True) + \
        C.panel("Study controls",
                '<p class="note">There are none. Every terrain contributes every shift it '
                'has committed. Trajectories are indexed to each terrain\'s own MEAN and '
                'plotted against its own life as a percentage, which is what makes the '
                'SHAPES comparable; the heights are not, and nothing is scaled to a '
                'common age.</p>') + \
        C.panel("What this is not",
                '<p class="note">Not a ranking. A higher figure is a different outcome, not '
                'a better one. DNT does not evaluate terrains. We observe.</p>')

    against = C.panel(
        "Against the median",
        '<div class="scroll"><table class="d"><thead><tr><th>metric</th>%s</tr>'
        '</thead><tbody>%s</tbody></table></div>'
        '<p class="note">Each terrain against the median of all %d. A sign says direction, '
        'not merit; beyond 200%% the figure is shown as a multiple because a percentage '
        'that large cannot be read.</p>'
        % (head, "".join(keyrows), len(shown)), anchor="key")

    right = C.panel("Study findings", '<ul class="find">%s</ul>' % "".join(findings)) + \
        C.panel("Read with care",
                '<p class="note">BASIN-01 and BASIN-02 differ in exactly one seeded '
                'variable and are a controlled comparison. BASIN-03 and BASIN-04 are not — '
                'each took further amendments, so a difference between them and the first '
                'two has more than one possible cause.</p>') + \
        C.panel("Go to", C.nav(
            [("%s" % d["name"], "/%s/terrain.html" % d["dir"],
              "terrain record · shift %s" % num(d["shift"])) for d in shown] +
            [("Department index", C.HUB + "/hub.html", "every terrain and document")]))

    mid = ('<div class="hdr" id="top"><div><p class="eyebrow">Studies</p>'
           '<h1 class="doc">Comparative Terrain Study</h1>'
           '<p class="sub">Longitudinal comparison of active terrains under differing '
           'governing conditions.</p></div><table class="doc">'
           '<tr><td class="k">DOCUMENT</td><td class="v">DNT-STUDY</td></tr>'
           '<tr><td class="k">TERRAINS</td><td class="v">%d</td></tr>'
           '<tr><td class="k">DATA THROUGH</td><td class="v">SHIFT %s</td></tr>'
           '<tr><td class="k">SOURCE</td><td class="v">EACH TERRAIN\'S OWN LOGS</td></tr>'
           '</table></div>' % (len(shown), num(max(d["shift"] or 0 for d in shown))))

    # "Terrain comparison" used to scroll to the cards already on screen. It
    # now opens the comparison those cards cannot make: all four terrains on
    # one row per quantity, including the conditions that differ.
    cmp_head = "".join('<th class="num" style="color:%s">%s</th>' % (d["_hue"], esc(d["name"]))
                       for d in shown)
    cmp_rows = []
    for label, fn in (
            ("first committed", lambda d: C.stamp(d["shifts"][0].get("end_timestamp"))
              if d["shifts"] else "not yet committed"),
            ("shifts committed", lambda d: num(len(d["shifts"]))),
            ("cells in the terrain", lambda d: num(len(d["world"].get("cells") or []))),
            ("living now", lambda d: num(d["shifts"][-1].get("living"))
              if d["shifts"] else "0"),
            ("native categories", lambda d: num(len(d["memory"].get("category_stats") or {}))),
            ("classified specimens", lambda d: num(len(d["named"]))),
            ("physics document", lambda d: esc(d["memory"].get("physics_document") or "—")),
            ("cumulative spend",
             lambda d: "$%.4f" % float(d["memory"].get("cumulative_cost_usd", 0.0)))):
        cmp_rows.append('<tr><td>%s</td>%s</tr>'
                        % (label, "".join('<td class="num">%s</td>' % fn(d) for d in shown)))
    for label in labels_all(shown):
        gm = {d["dir"]: {g["label"]: g for g in dnt_data.governing_conditions(d["dir"])}
              for d in shown}
        cmp_rows.append(
            '<tr><td>%s</td>%s</tr>'
            % (esc(label), "".join(
                ('<td class="num">%s</td>' % esc(gm[d["dir"]][label]["value"]))
                if gm[d["dir"]].get(label, {}).get("present")
                else '<td class="num absent">no mechanism</td>' for d in shown)))
    cmp_shots = "".join(
        '<figure class="cmpshot"><figcaption style="color:%s">%s</figcaption>%s'
        '<span>%s cells · shift %s</span></figure>'
        % (d["_hue"], esc(d["name"]), snapshot.isometric(d["dir"], 300, 130),
           num(len(d["world"].get("cells") or [])), num(d["shift"]))
        for d in shown)
    store.append(("mdl-terrains",
        '<div class="mdl-fig"><div class="cmpshots">%s</div></div>'
        '<div class="scroll"><table class="d"><thead><tr><th></th>%s</tr></thead>'
        '<tbody>%s</tbody></table></div>%s'
        % (cmp_shots, cmp_head, "".join(cmp_rows),
           C.readable([
               ("What this compares",
                ["Every terrain on one row per quantity, which the cards on the page "
                 "cannot do because each card only knows itself.",
                 "Each picture is that terrain's own elevation and cover grid, drawn "
                 "from the same export the observation deck reads. None is an "
                 "illustration and none is a photograph."]),
               ("Why the conditions matter most",
                ["The bottom rows are the reason the terrains differ at all. A "
                 "condition a terrain does not have reads <b>no mechanism</b> rather "
                 "than zero, because absent and zero are not the same claim.",
                 "BASIN-01 and BASIN-02 have none of them and differ from each other "
                 "in exactly one seeded variable."]),
               ("How to read it",
                ["Across a row, not down a column. The terrains are at different "
                 "shifts, under different conditions, and have run for different "
                 "lengths of time.",
                 "Not a ranking. DNT does not evaluate terrains."])]))))

    for d in unrun:
        cards.append(
            '<section class="tcard" style="border-color:%s;opacity:.72">'
            '<div class="tch"><b style="color:%s">%s</b>'
            '<span class="chip">FOUNDED</span></div>%s'
            '<div class="tcb"><dl class="kv"><dt>first committed</dt>'
            '<dd class="na">no shift yet</dd><dt>age (shifts)</dt><dd>0</dd>'
            '<dt>cells</dt><dd>%s</dd><dt>physics</dt><dd>%s</dd></dl>'
            '<p class="note">Founded and seeded. It has ground, and nothing has '
            'lived in it yet, so it carries no trajectory to compare.</p>'
            '<a class="nav" href="/%s/terrain.html"><span class="t">Terrain record'
            '<span class="go">&rarr;</span></span></a></div></section>'
            % (charts.hue(d["dir"]), charts.hue(d["dir"]), esc(d["name"]),
               snapshot.isometric(d["dir"], 330, 132),
               num(len(d["world"].get("cells") or [])),
               esc(d["memory"].get("physics_document") or "—"), d["dir"]))
    mid += '<div id="cards" class="tcards">%s</div>' % "".join(cards)
    mid += C.panel("Trajectory over time",
                   '<div class="charts3">%s</div>%s'
                   '<p class="note">Each terrain is indexed to its own mean and drawn '
                   'against its own life as a percentage, so a terrain of 128 shifts and '
                   'one of 218 can be compared by shape. Indexing to the FIRST value '
                   'looks reasonable and is not: a terrain that began with one living '
                   'specimen would index its population to ten thousand, and the panel '
                   'would become a chart of how small each terrain started. Steadiness '
                   'is plotted as 1 − CV so that up means steadier on every panel.</p>'
                   % (traj, charts.legend([(d["name"], d["_hue"]) for d in shown])),
                   "click any panel to enlarge", anchor="traj")
    mid += C.panel("Aggregate metrics at the latest shift",
                   '<div class="scroll"><table class="d"><thead><tr><th>metric</th>%s'
                   '<th class="num">median</th></tr></thead><tbody>%s</tbody></table></div>'
                   '<p class="note">Read across a row, not down a column. Each terrain is at '
                   'a different shift and under different conditions.</p>'
                   % (head, "".join(agg)), anchor="agg")
    mid += against

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

    mid += ('<div class="cols2">%s%s</div>'
            % (C.panel("Event frequency, per hundred shifts",
                       '<div class="scroll"><table class="d"><thead><tr><th>event</th>%s'
                       '</tr></thead><tbody>%s</tbody></table></div>'
                       '<p class="note">A rate, not a total, so terrains of different ages '
                       'compare. Every figure is summed from the shift log.</p>'
                       % (head, evrows), anchor="ev"),
               C.panel("Persistence",
                       '<div class="scroll"><table class="d"><thead><tr><th>pattern</th>%s'
                       '</tr></thead><tbody>%s</tbody></table></div>'
                       '<p class="note">Across every specimen the terrain has held, living '
                       'and ended alike.</p>' % (head, prows), anchor="pers")))

    mid += C.MODAL_FRAME + C.modal_store(store)
    mid += C.panel("Governing conditions, side by side",
                   '<div class="scroll"><table class="d"><thead><tr><th>condition</th>%s</tr>'
                   '</thead><tbody>%s</tbody></table></div>'
                   '<p class="note">This is the comparison that matters: the terrains differ '
                   'in what governs them, and a condition a terrain does not have is shown as '
                   'absent rather than as a zero.</p>' % (head, govrows), anchor="method")

    return C.page("Comparative Terrain Study", "COMPARATIVE STUDY", shown[-1]["dir"],
                  [("STUDIES", None), ("COMPARATIVE TERRAIN STUDY", None)],
                  shown[-1]["shift"], shown[-1]["committed_at"], mid, left, right,
                  CSS + charts.CSS + snapshot.CSS + C.MODAL_CSS, current="study",
                  scripts=C.SECTION_JS + C.MODAL_JS)


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


def export_csv(d, path) -> None:
    """The shift log as a spreadsheet, from the same rows the page reads."""
    rows = d["shifts"]
    if not rows:
        return
    cols = ["shift", "end_timestamp", "living", "arose_this_shift", "ended_this_shift",
            "replicated_this_shift", "links_formed", "classified", "anomalous",
            "unresolved", "resource_flow", "phase", "model", "duration_seconds",
            "estimated_cost_usd", "cumulative_cost_usd", "new_categories"]
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(",".join(cols) + "\n")
        for r in rows:
            out = []
            for col in cols:
                v = r.get(col)
                if isinstance(v, list):
                    v = " ".join(str(x) for x in v)
                v = "" if v is None else str(v)
                out.append('"%s"' % v.replace('"', '""') if ("," in v or '"' in v) else v)
            stream.write(",".join(out) + "\n")


def export_lineage_csv(d, root, path) -> None:
    """Every traced member of one line, with the measurements the record holds."""
    ind = d["individuals"]
    ended = {e.get("id"): e for e in (d["world"].get("ended") or [])}
    rec = lambda k: ind.get(k) or ended.get(k) or {}
    kids_of: Dict[str, List[str]] = {}
    for k, v in list(ind.items()) + list(ended.items()):
        if v.get("parent_id"):
            kids_of.setdefault(v["parent_id"], []).append(k)
    seen, frontier = {root}, [root]
    while frontier:
        nxt = []
        for node in frontier:
            for kid in kids_of.get(node, []):
                if kid not in seen:
                    seen.add(kid)
                    nxt.append(kid)
        frontier = nxt
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("id,state,generation,parent_id,arose_at_shift,age,descendants,"
                     "light,extent,junctions,mass,cover,residue,links,category\n")
        for k in sorted(seen, key=lambda x: (rec(x).get("generation", 0), x)):
            r = rec(k)
            st, tr = (r.get("structure") or {}), (r.get("traits") or {})
            stream.write(",".join(str(v) for v in [
                k, "living" if k in ind else "ended", r.get("generation", ""),
                r.get("parent_id", ""), r.get("arose_at_shift", ""), r.get("age", ""),
                r.get("descendants", ""), r.get("light", ""),
                st.get("extent", ""), st.get("junctions", ""), st.get("mass", ""),
                tr.get("cover", ""), tr.get("residue", ""), tr.get("links", ""),
                (d["named"].get(k) or {}).get("category", "")]) + "\n")


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

    # A download link that downloads nothing is worse than no link.
    export_csv(d, os.path.join(base, "exports", "shiftlog.csv"))
    for sid in roots:
        export_lineage_csv(d, sid, os.path.join(base, "exports", "lineage-%s.csv" % sid))

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
    study = comparative_study([load(t) for t in dnt_terrains.dirs()
                               if os.path.exists(os.path.join(ROOT, t, "state",
                                                              "memory.json"))])
    if study:
        write(os.path.join(ROOT, "study.html"), study)
        print("  study.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
