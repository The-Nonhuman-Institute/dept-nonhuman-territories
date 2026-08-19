"""
DNT — the terrain record and the shift log.

    python3 pages.py basin-03            write both for one terrain
    python3 pages.py --all               write both for every terrain

Every figure is read from that terrain's own state and logs. A governing
condition the terrain does not have renders as "no mechanism in this terrain",
never as a value. A derived quantity renders with its definition beside it.
"""

from __future__ import annotations

import json, math, os, re, sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import dnt_style, dnt_data, dnt_chrome

TERRAINS = [("basin-01", 8731), ("basin-02", 8732), ("basin-03", 8733), ("basin-04", 8734)]


def esc(v: Any) -> str:
    return (str(v if v is not None else "—").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def num(v: Any) -> str:
    if isinstance(v, float):
        return "{:,.4f}".format(v) if abs(v) < 100 else "{:,.0f}".format(v)
    if isinstance(v, int):
        return "{:,}".format(v)
    return esc(v)


def sparkline(series: List[float], w: int = 240, h: int = 44) -> str:
    vals = [v for v in series if isinstance(v, (int, float))]
    if len(vals) < 2:
        return '<span class="none">not enough shifts yet</span>'
    lo, hi = min(vals), max(vals)
    span = max(1e-9, hi - lo)
    pts = " ".join("%.1f,%.1f" % (i / (len(vals) - 1.0) * w, h - (v - lo) / span * (h - 4) - 2)
                   for i, v in enumerate(vals))
    return ('<svg class="spark" viewBox="0 0 %d %d" preserveAspectRatio="none" role="img" '
            'aria-label="%d shifts, %s to %s"><polyline points="%s"/></svg>'
            % (w, h, len(vals), num(lo), num(hi), pts))


def kv(pairs) -> str:
    return ('<table class="kv">%s</table>'
            % "".join('<tr><td class="k">%s</td><td class="v">%s</td></tr>' % (k, v)
                      for k, v in pairs if v is not None))


# --------------------------------------------------------------------------
def terrain_record(t: str, port: int) -> str:
    d = dnt_data.load(t)
    if not d:
        return ""
    m = d["memory"]; w = m.get("world") or {}
    rows = d["shifts"]
    living = len(w.get("individuals") or {})
    cells = w.get("cells") or []
    cover = sum(1 for c in cells if c.get("census_density", 0) > 0)
    links = len([1 for v in (w.get("links") or {}).values() if v.get("formed_at_shift") is not None])
    kids = sum(1 for b in (w.get("individuals") or {}).values() if b.get("parent_id"))
    cats = m.get("category_stats") or {}
    events = m.get("terrain_events")
    events = events if isinstance(events, list) else ([events] if events else [])

    pop = [r.get("living") for r in rows]
    div = dnt_data.shannon_diversity([c.get("count", 0) for c in cats.values()])
    stab = dnt_data.coefficient_of_variation(pop[-40:])
    anom = dnt_data.per_hundred_shifts(sum(r.get("anomalous", 0) or 0 for r in rows), len(rows))

    stat = "".join(
        '<div class="stat"><div class="sv">%s</div><div class="sl">%s</div>'
        '<div class="sn">%s</div></div>' % (num(v), k, n)
        for k, v, n in (
            ("age", m.get("last_committed_shift"), "shifts on the record"),
            ("living specimens", living, "counted now"),
            ("cover layer", cover, "of %s cells" % num(len(cells))),
            ("descendant threads", kids, "with a parent still living"),
            ("active links", links, "between specimens"),
            ("native categories", len(cats), "coined by the Namer"),
        ))

    gc = dnt_data.governing_conditions(t)
    gcrows = "".join(
        '<tr class="%s"><td class="gl">%s</td><td class="gv">%s</td><td class="gg">%s</td></tr>'
        % ("" if r["present"] else "absent", esc(r["label"]),
           esc(r["value"]) if r["present"] else '<span class="none">no mechanism in this terrain</span>',
           esc(r["governs"])) for r in gc)

    evrows = "".join(
        '<tr><td class="ev-s">%s</td><td class="ev-k">%s</td><td class="ev-d">%s</td>'
        '<td class="ev-t">%s</td></tr>'
        % (esc(e.get("shift")), esc(e.get("kind")),
           esc((e.get("detail") or "").split("\n")[0][:150]), esc(e.get("logged_at")))
        for e in reversed(events[-8:]))

    derived = kv([
        ("classification diversity",
         '%s <span class="def">Shannon entropy · H = -Σ pᵢ ln pᵢ over category shares</span>'
         % (num(div) if div is not None else '<span class="none">needs 2+ categories</span>')),
        ("population stability",
         '%s <span class="def">coefficient of variation · σ/μ over the last 40 shifts. lower is steadier</span>'
         % (num(stab) if stab is not None else '<span class="none">needs 3+ shifts</span>')),
        ("anomaly rate",
         '%s <span class="def">anomalous classifications × 100 / shifts</span>'
         % (num(anom) if anom is not None else '<span class="none">—</span>')),
    ])

    body = [
        '<section><h2>%s</h2><p class="lede">%s</p>' % (esc(m.get("terrain_name")),
            esc(m.get("physics_document") or "")),
        '<div class="stats">%s</div></section>' % stat,
        '<section><h3>Governing conditions</h3>'
        '<p class="lede">Each row names the quantity it governs. A condition this terrain '
        'does not have is shown as absent rather than given a value.</p>'
        '<div class="scroll"><table class="data gov">'
        '<thead><tr><th>condition</th><th>value</th><th>what it governs</th></tr></thead>'
        '<tbody>%s</tbody></table></div></section>' % gcrows,
        '<section><h3>Population over time</h3>%s'
        '<p class="cap">%d shifts recorded. Every point is the living count logged at that '
        'shift.</p></section>' % (sparkline(pop, 700, 90), len(rows)),
        '<section><h3>Derived quantities</h3>'
        '<p class="lede">Published definitions only. Each formula is printed beside its '
        'value so the number can be checked rather than trusted.</p>%s</section>' % derived,
        '<section><h3>Terrain events</h3><div class="scroll"><table class="data">'
        '<thead><tr><th>shift</th><th>kind</th><th>first line of the record</th>'
        '<th>logged</th></tr></thead><tbody>%s</tbody></table></div>'
        '<p class="cap">%d event(s) on the record. Each is a logged amendment or occurrence, '
        'never a summary.</p></section>' % (evrows, len(events)),
        '<section><h3>Elsewhere</h3><div class="links">'
        '<a class="go" href="http://127.0.0.1:%d/index.html">Observation deck</a>'
        '<a class="go" href="/%s/codex.html">Field compendium</a>'
        '<a class="go" href="/%s/structure.html">Classification structure</a>'
        '<a class="go" href="/%s/crosswalk.html">Linnaean crosswalk</a>'
        '<a class="go" href="/%s/shiftlog.html">Shift log</a>'
        '</div></section>' % (port, t, t, t, t),
    ]
    return frame(
        esc(m.get("terrain_name")) + " \u2014 Terrain Record", t, "terrain.html",
        [esc(m.get("terrain_name")), "TERRAIN RECORD"],
        masthead("Terrain Record", "One terrain, as its own logs describe it.",
                 [("TERRAIN", esc(m.get("terrain_name"))),
                  ("ID", esc(m.get("terrain_id"))),
                  ("SHIFT", esc(m.get("last_committed_shift"))),
                  ("STATUS", "ACTIVE")]),
        body,
        '<a href="http://127.0.0.1:%d/index.html">Observation deck</a>' % port)


# --------------------------------------------------------------------------
def shift_log(t: str, port: int) -> str:
    d = dnt_data.load(t)
    if not d:
        return ""
    m = d["memory"]; rows = d["shifts"]
    recent = list(reversed(rows[-60:]))

    def delta(cur, prev, key):
        a, b = cur.get(key), (prev or {}).get(key)
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            return ""
        diff = a - b
        if diff == 0:
            return '<span class="d0">0</span>'
        return '<span class="%s">%+d</span>' % ("dup" if diff > 0 else "ddn", diff)

    body_rows = []
    for i, r in enumerate(recent):
        prev = recent[i + 1] if i + 1 < len(recent) else None
        newcats = r.get("new_categories") or []
        body_rows.append(
            '<tr><td class="num">%s</td><td class="ts">%s</td>'
            '<td class="num">%s %s</td><td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
            '<td class="cats">%s</td><td class="ts">%s</td></tr>'
            % (esc(r.get("shift_id")), esc((r.get("end_timestamp") or "")[11:19]),
               num(r.get("living")), delta(r, prev, "living"),
               num(r.get("arose_this_shift")), num(r.get("ended_this_shift")),
               num(r.get("replicated_this_shift")), num(r.get("links_formed")),
               num(r.get("classified")),
               " ".join('<code>%s</code>' % esc(c) for c in newcats) or "",
               esc(r.get("phase"))))

    tot = {
        "shifts": len(rows),
        "arose": sum(r.get("arose_this_shift", 0) or 0 for r in rows),
        "ended": sum(r.get("ended_this_shift", 0) or 0 for r in rows),
        "classified": sum(r.get("classified", 0) or 0 for r in rows),
        "categories": len(m.get("category_stats") or {}),
        "spend": m.get("cumulative_cost_usd", 0.0),
    }
    stat = "".join(
        '<div class="stat"><div class="sv">%s</div><div class="sl">%s</div></div>' % (num(v), k)
        for k, v in (("shifts logged", tot["shifts"]), ("arose", tot["arose"]),
                     ("ended", tot["ended"]), ("classified", tot["classified"]),
                     ("categories", tot["categories"]),
                     ("spend", "$%.4f" % tot["spend"])))

    charts = "".join(
        '<div class="chart"><div class="ct">%s</div>%s</div>' % (label, sparkline(
            [r.get(key) for r in rows], 300, 60))
        for label, key in (("living", "living"), ("arose", "arose_this_shift"),
                           ("ended", "ended_this_shift"), ("links formed", "links_formed"),
                           ("resource flow", "resource_flow"), ("classified", "classified")))

    body = [
        '<section><h2>Shift log — %s</h2>'
        '<p class="lede">Every shift this terrain has committed. A shift is one tick; the '
        'terrain does not change between them.</p><div class="stats">%s</div></section>'
        % (esc(m.get("terrain_name")), stat),
        '<section><h3>Across every shift</h3><div class="charts">%s</div></section>' % charts,
        '<section><h3>The last %d shifts</h3><div class="scroll"><table class="data">'
        '<thead><tr><th class="num">shift</th><th>ended (UTC)</th><th class="num">living</th>'
        '<th class="num">arose</th><th class="num">ended</th><th class="num">replicated</th>'
        '<th class="num">links</th><th class="num">classified</th>'
        '<th>categories coined</th><th>phase</th></tr></thead><tbody>%s</tbody></table></div>'
        '<p class="cap">Newest first. Every column is a value the shift recorded when it '
        'closed — nothing is recomputed here.</p></section>' % (len(recent), "".join(body_rows)),
    ]
    return frame(
        esc(m.get("terrain_name")) + " \u2014 Shift Log", t, "shiftlog.html",
        [esc(m.get("terrain_name")), "SHIFT LOG"],
        masthead("Shift Log", "The chronological record of one terrain.",
                 [("TERRAIN", esc(m.get("terrain_name"))),
                  ("SHIFTS", esc(len(rows))),
                  ("THROUGH", esc(m.get("last_committed_shift"))),
                  ("STATUS", "ACTIVE")]),
        body,
        '<a href="/%s/terrain.html">Terrain record</a>' % t)


EXTRA = """
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;
background:var(--rule);border:1px solid var(--rule);margin:18px 0}
.stat{background:var(--panel);padding:14px 16px}
.sv{font:400 26px/1.1 var(--serif);font-variant-numeric:tabular-nums}
.sl{font:10px var(--mono);letter-spacing:.09em;text-transform:uppercase;color:var(--grey);margin-top:5px}
.sn{font:10.5px var(--mono);color:var(--grey);margin-top:3px}
table.kv{border-collapse:collapse;font:12.5px/1.9 var(--mono);width:100%}
table.kv td{padding:4px 0;vertical-align:top;border-bottom:1px solid var(--rule)}
table.kv td.k{color:var(--grey);padding-right:24px;white-space:nowrap;width:1%}
.def{display:block;color:var(--grey);font-size:11px;margin-top:2px}
.none{color:var(--grey);font-style:italic}
table.gov tr.absent .gl,table.gov tr.absent .gg{color:var(--grey)}
.gl{font:12px var(--mono)}
.gv{font:12.5px var(--mono);white-space:nowrap}
.gg{color:var(--grey);font-size:12px}
.spark{width:100%;height:auto;display:block}
.spark polyline{fill:none;stroke:var(--moss);stroke-width:1.4}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.chart{border:1px solid var(--rule);background:var(--panel);padding:10px 12px}
.ct{font:10px var(--mono);letter-spacing:.09em;text-transform:uppercase;color:var(--grey);margin-bottom:6px}
.cap{color:var(--grey);font-size:11.5px;margin:10px 0 0}
.ts{font:11px var(--mono);color:var(--grey)}
.cats code{font-size:11px;margin-right:4px}
.dup{color:var(--moss)}.ddn{color:var(--amber)}.d0{color:var(--grey)}
.ev-s{font:11.5px var(--mono);width:1%}
.ev-k{font:11.5px var(--mono);color:var(--moss);white-space:nowrap}
.ev-d{font-size:12.5px;color:var(--grey)}
.ev-t{font:10.5px var(--mono);color:var(--grey);white-space:nowrap}
.links{display:flex;flex-wrap:wrap;gap:10px}
a.go{display:block;padding:10px 14px;border:1px solid var(--rule);color:var(--ink);
text-decoration:none;font-size:13.5px;background:var(--panel)}
a.go:hover{border-color:var(--moss)}
"""

# The house style is written entirely against tokens, so the same rules set a
# printed sheet or a console. Only the token block is dropped here; the console
# skin from dnt_chrome supplies the replacement, and the frame supplies the
# sidebar, the top bar, and the footer these pages previously drew themselves.
_ROOT_BLOCK = re.compile(r":root\{[^}]*\}\s*", re.S)
BODY_CSS = _ROOT_BLOCK.sub("", dnt_style.CSS, count=1)

FOOT = ("Every figure is read from this terrain\u2019s own state and logs. Derived "
        "quantities carry their definitions. A condition the terrain does not have is "
        "shown as absent, never as a value.")


def frame(title, terrain, page_file, crumbs, masthead, body, topright=""):
    return dnt_chrome.page(
        title, dnt_chrome.CONSOLE, BODY_CSS + EXTRA + FRAME_CSS,
        masthead + "".join(body) + ('<p class="foot-note">%s</p>' % FOOT),
        crumbs, dnt_chrome.sidebar(ROOT, terrain, page_file), topright,
        "DNT FIELD MANUAL v1.0")


FRAME_CSS = """
.mast{border-bottom:1px solid var(--rule);padding:0 0 20px;margin-bottom:24px;
display:grid;grid-template-columns:1fr auto;gap:30px;align-items:end}
.mast h1{font:400 clamp(26px,3.4vw,38px)/1.08 var(--serif);margin:0 0 8px}
.mast .lede{color:var(--grey);margin:0;max-width:62ch;font-size:14px}
.mast table.doc{border-collapse:collapse;font:11px/1.9 var(--mono);color:var(--grey)}
.mast table.doc td{padding:0 0 0 16px;white-space:nowrap}
.mast table.doc td.k{padding:0}
.mast table.doc td.v{color:var(--ink)}
.foot-note{margin:36px 0 0;padding-top:14px;border-top:1px solid var(--rule);
color:var(--grey);font-size:11.5px;line-height:1.6}
"""


def masthead(title, lede, pairs):
    doc = "".join('<tr><td class="k">%s</td><td class="v">%s</td></tr>' % (k, v)
                  for k, v in pairs)
    return ('<div class="mast"><div><h1>%s</h1><p class="lede">%s</p></div>'
            '<table class="doc">%s</table></div>' % (title, lede, doc))


def main(argv: List[str]) -> int:
    targets = [(t, p) for t, p in TERRAINS
               if ("--all" in argv or t in argv)
               and os.path.exists(os.path.join(ROOT, t, "state", "memory.json"))]
    if not targets:
        print("usage: python3 pages.py basin-03 | --all")
        return 1
    for t, port in targets:
        for name, fn in (("terrain.html", terrain_record), ("shiftlog.html", shift_log)):
            html = fn(t, port)
            if not html:
                continue
            with open(os.path.join(ROOT, t, name), "w", encoding="utf-8") as s:
                s.write(html)
        print("  %-9s terrain.html + shiftlog.html" % t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
