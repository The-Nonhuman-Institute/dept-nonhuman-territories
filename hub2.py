"""
DNT — the department index, built to the mockup and filled from the record.

Every figure is read from a terrain's own state and logs. Where the mockup
shows something the department does not measure, this shows what it does
measure instead, or says the thing is absent. Nothing is invented.

The terrain thumbnails are drawn from each terrain's actual cover and
elevation grid — not illustrations, the same data the observation deck renders.
"""

from __future__ import annotations

import json, os, re, sys, datetime
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import dnt_chrome, dnt_data

TERRAINS = [
    ("basin-01", "BASIN-01", 8731, "A line of 21 cells.",
     "Control. Physics frozen at v1.4; not to be amended."),
    ("basin-02", "BASIN-02", 8732, "A field 21 deep x 15 wide, with relief.",
     "Controlled comparison through shift 140; exploratory since."),
    ("basin-03", "BASIN-03", 8733, "An eroded landscape that grows at its margins.",
     "Ground formed by process, not formula."),
    ("basin-04", "BASIN-04", 8734, "An eroded landscape under six governing conditions.",
     "Temperature, wind, gravity, subsurface water, light cycle, shift length."),
]


def esc(v: Any) -> str:
    return (str(v if v is not None else "—").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def num(v) -> str:
    return "{:,}".format(v) if isinstance(v, int) else ("%s" % v)


_WIDTH_CACHE = {}


def grid_width(directory: str, ncells: int) -> int:
    """The terrain's lateral width, read from its own physics module.

    Terrains that form their ground by process carry width in the landscape
    record. The two that do not (a line, and a fixed field) declare it as a
    constant in life.py, so it is read from there rather than guessed. A
    terrain with neither is a line, and its width is its whole length.
    """
    if directory in _WIDTH_CACHE:
        return _WIDTH_CACHE[directory]
    width = ncells
    path = os.path.join(ROOT, directory, "life.py")
    try:
        with open(path, "r", encoding="utf-8") as stream:
            found = re.search(r"^FIELD_WIDTH\s*=\s*(\d+)", stream.read(), re.M)
        if found:
            width = int(found.group(1))
    except IOError:
        pass
    _WIDTH_CACHE[directory] = width
    return width


def thumbnail(d: Dict[str, Any], w: int = 300, h: int = 150) -> str:
    """A real picture of the terrain: its own cover density and water, per cell.

    Not an illustration. The same grid the observation deck reads.
    """
    m = d.get("memory") or {}
    world = m.get("world") or {}
    cells = world.get("cells") or []
    ls = m.get("landscape") or {}
    if not cells:
        return '<div class="thumb none">no terrain state yet</div>'
    fw = int(ls.get("width") or 0) or grid_width(d["dir"], len(cells))
    fd = max(1, len(cells) // max(1, fw))
    step = max(1, fw // 120)
    rects = []
    cw = w / max(1, fw / step)
    ch = h / max(1, fd / step)
    ground = ls.get("ground") or []
    lo = min(ground) if ground else 0.0
    hi = max(ground) if ground else 1.0
    span = max(1e-9, hi - lo)
    for i in range(0, len(cells), step):
        c = cells[i]
        idx = c.get("index", i)
        col, row = idx % fw, idx // fw
        if col % step or row % step:
            continue
        cover = min(1.0, float(c.get("census_density", 0.0)))
        elev = ((ground[idx] - lo) / span) if idx < len(ground) else 0.4
        if cover > 0.02:
            g = 0.18 + cover * 0.5
            col_s = "rgb(%d,%d,%d)" % (int(70 * g), int(190 * g), int(90 * g))
        else:
            s = 0.10 + elev * 0.30
            col_s = "rgb(%d,%d,%d)" % (int(180 * s), int(196 * s), int(176 * s))
        rects.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                     % (col / step * cw, row / step * ch, cw + .6, ch + .6, col_s))
    return ('<svg class="thumb" viewBox="0 0 %d %d" preserveAspectRatio="none" role="img" '
            'aria-label="cover and elevation across the terrain">%s</svg>'
            % (w, h, "".join(rects)))


def gather() -> List[Dict[str, Any]]:
    out = []
    for d, name, port, shape, role in TERRAINS:
        data = dnt_data.load(d)
        if not data:
            continue
        m = data["memory"]; w = m.get("world") or {}
        cats = m.get("category_stats") or {}
        out.append({
            "dir": d, "name": name, "port": port, "shape": shape, "role": role,
            "data": data, "memory": m,
            "shift": m.get("last_committed_shift"),
            "living": len(w.get("individuals") or {}),
            "categories": len(cats),
            "classified": len(data["specimens"]),
            "events": len(m.get("terrain_events") if isinstance(m.get("terrain_events"), list)
                          else ([m["terrain_events"]] if m.get("terrain_events") else [])),
            "spend": m.get("cumulative_cost_usd", 0.0),
            "shifts": data["shifts"],
        })
    return out


def recent_activity(ts: List[Dict[str, Any]], limit: int = 8) -> str:
    """Real events, newest first, with the timestamps they were logged at."""
    rows = []
    for t in ts:
        for r in t["shifts"][-6:]:
            when = r.get("end_timestamp")
            if not when:
                continue
            newcats = r.get("new_categories") or []
            if newcats:
                rows.append((when, t["name"], "category coined",
                             ", ".join(newcats) + " · shift %s" % r.get("shift_id")))
            rows.append((when, t["name"], "shift committed",
                         "%s living recorded · shift %s" % (num(r.get("living") or 0),
                                                            r.get("shift_id"))))
        ev = t["memory"].get("terrain_events")
        ev = ev if isinstance(ev, list) else ([ev] if ev else [])
        for e in ev[-3:]:
            if e and e.get("logged_at"):
                rows.append((e["logged_at"], t["name"], "terrain event",
                             "%s · shift %s" % (e.get("kind"), e.get("shift"))))
    rows.sort(reverse=True)
    return "".join(
        '<li><span class="dot"></span><div><div class="al">%s</div>'
        '<div class="am">%s · %s</div></div><div class="at">%s</div></li>'
        % (esc(kind), esc(who), esc(detail), dnt_chrome.stamp(when))
        for when, who, kind, detail in rows[:limit])


def documents() -> str:
    rows = []
    docs = os.path.join(ROOT, "docs")
    if os.path.isdir(docs):
        for f in sorted(os.listdir(docs)):
            if f.endswith(".docx") and "BACKUP" not in f:
                mt = datetime.datetime.utcfromtimestamp(
                    os.path.getmtime(os.path.join(docs, f))).strftime("%Y-%m-%d")
                rows.append('<li><a href="docs/%s">%s</a><span>%s</span></li>'
                            % (f, esc(f.replace("_", " ").replace(".docx", "")), mt))
    for f in ("physics.md", "physics_basin02.md", "README.md", "STARTUP_GUIDE.md"):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            mt = datetime.datetime.utcfromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")
            rows.append('<li><a href="%s">%s</a><span>%s</span></li>' % (f, esc(f), mt))
    return "".join(rows)


def system_status(ts: List[Dict[str, Any]]) -> str:
    """What is actually true of each terrain, not a health light.

    The mockup shows subsystems reporting "Operational". This reports the two
    things the department can genuinely check: whether a terrain's record is
    internally consistent, and when it last committed.
    """
    rows = []
    for t in ts:
        shifts = t["shifts"]
        last = shifts[-1].get("end_timestamp") if shifts else None
        orphan = bool(shifts and shifts[-1].get("shift_id") is not None
                      and t["shift"] is not None
                      and shifts[-1]["shift_id"] > t["shift"])
        state = "record ahead of last commit" if orphan else "consistent"
        rows.append('<li><span class="dot %s"></span><span class="sk">%s</span>'
                    '<span class="sv">%s</span><span class="st">%s</span></li>'
                    % ("warn" if orphan else "", esc(t["name"]), esc(state),
                       esc((last or "—").replace("T", " ").replace("Z", "")))) 
    return "".join(rows)


def resource_state(ts: List[Dict[str, Any]]) -> str:
    """Each terrain's actual current resource flow, drawn as filled dots.

    The mockup's gauge has no source. Resource flow does: it is logged every
    shift and drives the whole light economy.
    """
    rows = []
    for t in ts:
        flow = (t["shifts"][-1].get("resource_flow") if t["shifts"] else None)
        if flow is None:
            rows.append('<li><span class="sk">%s</span><span class="none">no shift logged</span></li>'
                        % esc(t["name"]))
            continue
        filled = max(0, min(5, int(round(flow * 5))))
        dots = "".join('<i class="%s"></i>' % ("on" if i < filled else "") for i in range(5))
        rows.append('<li><span class="sk">%s</span><span class="dots">%s</span>'
                    '<span class="sv">%.3f</span></li>' % (esc(t["name"]), dots, flow))
    return "".join(rows)


TOOLS = [
    ("codex.html", "Field compendium",
     "Every specimen ever classified — in the Namer's own words."),
    ("structure.html", "Classification structure",
     "Four experimental models for arranging the same observations."),
    ("crosswalk.html", "Linnaean crosswalk",
     "The Archivist's translation, for human readers only."),
    ("terrain.html", "Terrain record",
     "Governing conditions, population over time, terrain events."),
    ("shiftlog.html", "Shift log",
     "Every shift committed, and what changed in each."),
]


CSS = """
h1{font:400 clamp(30px,4vw,44px)/1.06 var(--serif);margin:0 0 12px}
.lede{color:var(--grey);max-width:64ch;margin:0;font-size:14.5px}
.headrow{display:grid;grid-template-columns:1fr auto;gap:34px;align-items:start;
border-bottom:1px solid var(--rule);padding-bottom:22px}
.eyebrow{font:10px var(--mono);letter-spacing:.16em;text-transform:uppercase;
color:var(--grey);margin:0 0 12px}
table.doc{border-collapse:collapse;font:11px/1.9 var(--mono);color:var(--grey)}
table.doc td{padding:0 0 0 16px;white-space:nowrap}
table.doc td.k{padding:0}table.doc td.v{color:var(--ink)}
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
border:1px solid var(--rule);border-left:none;margin:24px 0 30px}
.strip .cell{border-left:1px solid var(--rule);padding:16px 18px}
.strip .n{font:400 30px/1 var(--serif);font-variant-numeric:tabular-nums}
.strip .l{font:9.5px var(--mono);letter-spacing:.12em;text-transform:uppercase;
color:var(--grey);margin-top:8px}
h2.sec{font:10px var(--mono);letter-spacing:.15em;text-transform:uppercase;
color:var(--grey);margin:0 0 14px;display:flex;justify-content:space-between}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:18px}
.card{border:1px solid var(--rule);background:var(--panel);display:flex;flex-direction:column}
.card h3{font:400 21px/1.1 var(--serif);margin:0}
.chead{display:flex;justify-content:space-between;align-items:baseline;
padding:15px 17px 12px;border-bottom:1px solid var(--rule)}
.badge{font:9px var(--mono);letter-spacing:.1em;color:var(--moss);border:1px solid var(--moss);
padding:2px 7px}
.thumb{width:100%;height:132px;display:block;background:#0d0f0c}
.thumb.none{display:grid;place-items:center;color:var(--grey);font:11px var(--mono);
border-bottom:1px solid var(--rule)}
.cbody{padding:14px 17px;display:flex;flex-direction:column;gap:10px;flex:1}
.cbody dl.st{margin-top:auto}
.cdesc{font-size:12.5px;color:var(--grey);margin:0;line-height:1.55}
dl.st{display:grid;grid-template-columns:auto 1fr;gap:1px 14px;margin:0;
font:11.5px/1.75 var(--mono);font-variant-numeric:tabular-nums;
border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:9px 0}
dl.st dt{color:var(--grey);text-transform:uppercase;letter-spacing:.06em;font-size:10px}
dl.st dd{margin:0;text-align:right}
a.deck{display:flex;justify-content:space-between;align-items:center;
padding:11px 14px;border:1px solid var(--rule);color:var(--ink);text-decoration:none;
font-size:13px;margin:0 17px 15px}
a.deck span{color:var(--grey);font-size:11px;display:block}
a.deck:hover{border-color:var(--moss)}
.twocol{display:grid;grid-template-columns:1.15fr 1fr;gap:26px;margin-top:34px}
.tools{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:start}
.tool{border:1px solid var(--rule);background:var(--panel);padding:14px 15px;
text-decoration:none;color:var(--ink);display:block}
.tool:hover{border-color:var(--moss)}
.tool{padding:0}
.tool>a{display:block;padding:14px 15px 10px;text-decoration:none;color:inherit}
.tool b{display:block;font:10px var(--mono);letter-spacing:.1em;text-transform:uppercase;
margin-bottom:5px}
.alts{font:10px var(--mono);color:var(--grey);letter-spacing:.08em;padding:0 15px 11px}
.alts a.alt{color:var(--grey);text-decoration:none;border-bottom:1px solid var(--rule);
margin-left:7px}
.alts a.alt:hover{color:var(--moss);border-color:var(--moss)}
.tool span{font-size:12px;color:var(--grey);line-height:1.5}
ul.feed{list-style:none;margin:0;padding:0;border-top:1px solid var(--rule)}
ul.feed li{display:grid;grid-template-columns:auto 1fr auto;gap:11px;align-items:baseline;
padding:10px 0;border-bottom:1px solid var(--rule)}
.dot{width:6px;height:6px;border-radius:50%;background:var(--moss);display:block}
.dot.warn{background:var(--amber)}
.al{font-size:12.5px}
.am{font:10.5px var(--mono);color:var(--grey);margin-top:2px}
.at{font:10px var(--mono);color:var(--grey);white-space:nowrap}
.threecol{display:grid;grid-template-columns:1fr 1fr 1fr;gap:26px;margin-top:34px;
border-top:1px solid var(--rule);padding-top:24px}
ul.docs{list-style:none;margin:0;padding:0;font-size:12.5px}
ul.docs li{display:flex;justify-content:space-between;gap:14px;padding:5px 0;
border-bottom:1px solid var(--rule)}
ul.docs a{color:var(--ink);text-decoration:none}
ul.docs a:hover{color:var(--moss)}
ul.docs span{font:10px var(--mono);color:var(--grey)}
ul.status{list-style:none;margin:0;padding:0;font:11px var(--mono)}
ul.status li{display:grid;grid-template-columns:auto 80px 1fr auto;gap:10px;
align-items:center;padding:7px 0;border-bottom:1px solid var(--rule)}
.sk{color:var(--ink)}.sv{color:var(--grey)}.st{color:var(--grey);font-size:10px}
.dots{display:flex;gap:4px}
.dots i{width:7px;height:7px;border:1px solid var(--grey);display:block}
.dots i.on{background:var(--moss);border-color:var(--moss)}
.note{font-size:11.5px;color:var(--grey);margin:10px 0 0;line-height:1.55}
.none{color:var(--grey);font-style:italic}
@media(max-width:1000px){.twocol,.threecol{grid-template-columns:1fr}}
"""


def render() -> str:
    ts = gather()
    tot_shifts = sum((t["shift"] or 0) + 1 for t in ts)
    tot_class = sum(t["classified"] for t in ts)
    tot_living = sum(t["living"] for t in ts)
    tot_cats = sum(t["categories"] for t in ts)
    tot_spend = sum(t["spend"] for t in ts)

    strip = "".join('<div class="cell"><div class="n">%s</div><div class="l">%s</div></div>'
                    % (num(v), k) for k, v in (
                        ("total shifts", tot_shifts), ("specimens classified", tot_class),
                        ("living specimens", tot_living), ("native categories", tot_cats),
                        ("terrains", len(ts))))

    cards = []
    for t in ts:
        cards.append(
            '<article class="card"><div class="chead"><h3>%s</h3>'
            '<span class="badge">ACTIVE</span></div>%s'
            '<div class="cbody"><p class="cdesc">%s<br>%s</p>'
            '<dl class="st"><dt>shift</dt><dd>%s</dd><dt>living</dt><dd>%s</dd>'
            '<dt>categories</dt><dd>%s</dd><dt>classified</dt><dd>%s</dd>'
            '<dt>terrain events</dt><dd>%s</dd><dt>spend</dt><dd>$%.4f</dd></dl></div>'
            '<a class="deck" href="http://127.0.0.1:%d/index.html">Observation deck'
            '<span>walk the terrain in 3D</span></a></article>'
            % (esc(t["name"]), thumbnail(t["data"]), esc(t["shape"]), esc(t["role"]),
               num(t["shift"]), num(t["living"]), num(t["categories"]),
               num(t["classified"]), num(t["events"]), t["spend"], t["port"]))

    tools = []
    for filename, label, blurb in TOOLS:
        holders = [t for t in ts
                   if os.path.exists(os.path.join(ROOT, t["dir"], filename))]
        if not holders:
            continue
        # Deepest record first — the terrain with the most to show.
        holders.sort(key=lambda t: t["classified"], reverse=True)
        others = "".join(
            ' <a class="alt" href="/%s/%s">%s</a>' % (t["dir"], filename, t["name"][-2:])
            for t in holders[1:])
        tools.append(
            '<div class="tool"><a href="/%s/%s"><b>%s</b><span>%s</span></a>'
            '<div class="alts">%s%s</div></div>'
            % (holders[0]["dir"], filename, label, blurb,
               esc(holders[0]["name"]), others))
    tools = "".join(tools)

    body = (
        '<div class="headrow"><div><p class="eyebrow">Department of Nonhuman Territories</p>'
        '<h1>Department of<br>Nonhuman Territories</h1>'
        '<p class="lede">Bounded digital environments seeded with fixed mechanical rules, in '
        'which autonomous roles run over time. What emerges is recorded and classified, never '
        'authored, corrected, or steered.</p></div>'
        '<table class="doc"><tr><td class="k">TERRAINS</td><td class="v">%d</td></tr>'
        '<tr><td class="k">COMBINED SPEND</td><td class="v">$%.4f</td></tr>'
        '<tr><td class="k">STATUS</td><td class="v">ACTIVE</td></tr></table></div>'
        '<div class="strip">%s</div>'
        '<section><h2 class="sec"><span>Terrains overview</span></h2>'
        '<div class="cards">%s</div>'
        '<p class="note">Each thumbnail is drawn from that terrain\'s own cover density and '
        'elevation grid — the same data the observation deck reads. None is an illustration.</p>'
        '</section>'
        '<div class="twocol"><section><h2 class="sec"><span>Tools &amp; resources</span></h2>'
        '<div class="tools">%s</div></section>'
        '<section><h2 class="sec"><span>Recent activity</span></h2>'
        '<ul class="feed">%s</ul>'
        '<p class="note">Read from shift logs and terrain events, newest first, at the times '
        'they were committed.</p></section></div>'
        '<div class="threecol">'
        '<section><h2 class="sec"><span>Governing documents</span></h2><ul class="docs">%s</ul></section>'
        '<section><h2 class="sec"><span>Record consistency</span></h2><ul class="status">%s</ul>'
        '<p class="note">The department cannot report a subsystem as "operational" — it has no '
        'such check. What it can verify is whether each terrain\'s logs agree with its last '
        'commit, and when that commit was.</p></section>'
        '<section><h2 class="sec"><span>Resource flow</span></h2><ul class="status">%s</ul>'
        '<p class="note">The flow logged at each terrain\'s most recent shift. This drives the '
        'entire light economy; it is not a health gauge.</p></section></div>'
        % (len(ts), tot_spend, strip, "".join(cards), tools,
           recent_activity(ts), documents(), system_status(ts), resource_state(ts)))

    return dnt_chrome.page(
        "Department of Nonhuman Territories", dnt_chrome.PAPER, CSS, body,
        ["DEPARTMENT INDEX"],
        dnt_chrome.sidebar(ROOT, None, None),
        '<a href="/basin-03/terrain.html">Terrain records</a>',
        "DNT FIELD MANUAL v1.0")


def main(argv: List[str]) -> int:
    html = render()
    with open(os.path.join(ROOT, "hub.html"), "w", encoding="utf-8") as s:
        s.write(html)
    print("wrote hub.html (%.0f KB)" % (len(html) / 1024.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
