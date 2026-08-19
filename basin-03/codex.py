"""
BASIN-02 — the specimen codex. A field guide drawn from the record.

    python3 codex.py            write codex.html
    python3 codex.py --open     write it and open it

WHY THIS EXISTS

  The observation deck shows what is alive right now. Everything else — 3,951
  endings and counting — existed only as sentences. A specimen could be
  classified, reasoned about at length, and then vanish without anyone ever
  having seen its form. That happened to i-01215, the only mobile_opportunist
  this terrain ever produced: named at shift 70, ended at shift 83, and no
  image of it exists anywhere.

  This reads every specimen the Namer classified, living or ended, and draws
  each one from its own measurements as a plate. The plates are SVG rather
  than 3D because a field guide is read, not walked through, and because a
  drawing can hold a specimen still in a way the terrain never does.

WHAT IS DRAWN, AND FROM WHAT

  Exactly the measurements the 3D viewer uses, in a different projection:

    core size          mass
    core shape         substrate (structural / fragment)
    radiating arms     junctions, at length extent x links-affinity
    downward anchors   cover-affinity
    bracing rings      upkeep
    orbit rings        descendants
    ground disc        residue-affinity

  Nothing is styled and no specimen is drawn from imagination. Where a
  measurement is missing from the record, the plate says so rather than
  guessing — endings before shift 140 kept no remains, so those specimens are
  listed with their words and an empty plate. That absence is the honest state
  of the record and is shown as such.

Python 3.9 compatible. Reads only; writes one file.
"""

from __future__ import annotations

import json
import math
import os
import sys
import webbrowser
import dnt_style
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import describe
import life

OUTPUT = os.path.join(config.TERRAIN_ROOT, "codex.html")


def _load(path: str) -> List[Dict[str, Any]]:
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def gather() -> Dict[str, Any]:
    memory = json.load(open(config.MEMORY_FILE, encoding="utf-8"))
    living = memory.get("world", {}).get("individuals", {})
    specimens: Dict[str, Dict[str, Any]] = {}

    # every classification the Namer ever made, newest kept
    for record in _load(config.SPECIMEN_LOG):
        classification = record.get("classification") or {}
        identifier = record.get("specimen_id")
        if not identifier or not classification.get("category"):
            continue
        entry = specimens.setdefault(identifier, {"id": identifier})
        entry["category"] = classification.get("category")
        entry["reasoning"] = classification.get("reasoning") or ""
        entry["persistence"] = classification.get("persistence_native") or ""
        entry["comparison"] = classification.get("comparison") or ""
        entry["named_at_shift"] = record.get("shift")
        entry["record_tier"] = record.get("record_tier")

    # the remains of anything that ended
    for record in _load(config.ANOMALY_LOG):
        if record.get("record_tier") != "ended":
            continue
        identifier = record.get("specimen_id")
        if identifier not in specimens:
            continue
        entry = specimens[identifier]
        entry["ended_at_shift"] = record.get("shift")
        entry["shifts_present"] = record.get("shifts_present")
        entry["descendants"] = record.get("descendants")
        remains = record.get("remains") or {}
        if remains and record.get("position_cell") is not None:
            remains = dict(remains); remains["cell"] = record.get("position_cell")
        if remains:
            entry["measurements"] = remains
            entry["from_remains"] = True

    # anything still alive is measured directly
    for identifier, being in living.items():
        if identifier not in specimens:
            continue
        entry = specimens[identifier]
        entry["alive"] = True
        entry["shifts_present"] = being.get("age")
        entry["descendants"] = being.get("descendants")
        structure = being.get("structure") or {}
        entry["measurements"] = {
            "cell": being.get("cell"),
            "substrate": being.get("substrate"),
            "structure": structure,
            "affinities": being.get("traits") or {},
            "generation": being.get("generation"),
            "parent_id": being.get("parent_id"),
            "origin": being.get("origin"),
            "arose_at_shift": being.get("arose_at_shift"),
            "moves": being.get("moves"),
            "drawn_from_census": being.get("drawn_from_census", 0.0),
            "drawn_from_residue": being.get("drawn_from_residue", 0.0),
            "drawn_from_links": being.get("drawn_from_links", 0.0),
        }
        entry["from_remains"] = False

    return {"specimens": specimens, "shift": memory.get("last_committed_shift"),
            "terrain": memory.get("terrain_name")}


def plate(entry: Dict[str, Any], size: int = 168) -> str:
    """Draw one specimen from its measurements. Returns SVG."""
    m = entry.get("measurements")
    if not m or not (m.get("structure") or {}):
        return ('<svg viewBox="0 0 %d %d" class="plate empty" role="img" '
                'aria-label="no measurements survive for this specimen">'
                '<text x="%d" y="%d" class="none">nothing survives</text></svg>'
                % (size, size, size // 2, size // 2))

    st = m["structure"]
    aff = m.get("affinities") or {}
    mass = max(0.2, float(st.get("mass", 1.0)))
    extent = float(st.get("extent", 1.0))
    junctions = float(st.get("junctions", 1.0))
    cover = float(aff.get("cover", 0.0))
    residue = float(aff.get("residue", 0.0))
    links = float(aff.get("links", 0.0))
    upkeep = float(m.get("upkeep") or 0.0)
    generation = int(m.get("generation") or 0)
    descendants = int(entry.get("descendants") or 0)
    age = int(entry.get("shifts_present") or 0)
    fragment = m.get("substrate") == "fragment"

    cx = cy = size / 2.0
    r = 8.0 + mass * 13.0
    parts = []

    # ground disc — residue-affinity
    if residue > 0.15:
        parts.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" class="disc"/>'
                     % (cx, cy + r * 1.5, r * (1.0 + residue * 1.3), r * 0.30))

    # downward anchors — cover-affinity
    anchors = int(round(cover * 4))
    for i in range(anchors):
        a = (i / float(max(1, anchors))) * math.pi + math.pi * 0.15
        reach = r * (0.9 + cover * 0.9)
        parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="anchor"/>'
                     % (cx, cy + r * 0.3, cx + math.cos(a) * reach, cy + r * 1.45))

    # radiating arms — junctions, length extent x links-affinity
    arms = 1 + int(round(junctions))
    reach = r * (1.5 + extent * 1.1) * (0.7 + links * 0.5)
    for i in range(arms):
        a = (i / float(arms)) * 2 * math.pi - math.pi / 2
        x2, y2 = cx + math.cos(a) * reach, cy + math.sin(a) * reach * 0.8
        parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="arm"/>'
                     % (cx, cy, x2, y2))
        parts.append('<circle cx="%.1f" cy="%.1f" r="%.1f" class="node"/>' % (x2, y2, r * 0.16))

    # bracing rings — what the build costs every shift
    for i in range(min(5, int(round(upkeep * 3)))):
        parts.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" class="brace"/>'
                     % (cx, cy, r * (0.55 + i * 0.16), r * (0.20 + i * 0.06)))

    # core — segments accumulate with shifts survived; shape is substrate
    segments = 1 + min(4, age // 7)
    for i in range(segments):
        rr = r * (1 - i * 0.15)
        yy = cy - i * rr * 0.55
        if fragment:
            pts = " ".join("%.1f,%.1f" % (cx + math.cos(math.pi / 2 + k * math.pi / 2) * rr,
                                          yy + math.sin(math.pi / 2 + k * math.pi / 2) * rr)
                           for k in range(4))
            parts.append('<polygon points="%s" class="core"/>' % pts)
        else:
            sides = 6 if generation < 1 else (8 if generation < 2 else 12)
            pts = " ".join("%.1f,%.1f" % (cx + math.cos(2 * math.pi * k / sides - math.pi / 2) * rr,
                                          yy + math.sin(2 * math.pi * k / sides - math.pi / 2) * rr)
                           for k in range(sides))
            parts.append('<polygon points="%s" class="core"/>' % pts)

    # orbit rings — descendants left
    for i in range(min(3, descendants)):
        parts.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" class="orbit"/>'
                     % (cx, cy, r * (1.7 + i * 0.45), r * (0.5 + i * 0.14)))

    return ('<svg viewBox="0 0 %d %d" class="plate" role="img" aria-label="%s">%s</svg>'
            % (size, size, entry["id"], "".join(parts)))


def _percentile_bands(specimens: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """Sorted values per measure, so any one specimen can be placed among the rest.

    A bare number tells a reader nothing. 0.72 is only meaningful against what
    every other specimen managed, so each measure is compared to the whole
    recorded population and described in words.
    """
    import bisect
    pools: Dict[str, List[float]] = {}
    for e in specimens:
        m = e.get("measurements") or {}
        st = m.get("structure") or {}
        aff = m.get("affinities") or {}
        for key, val in (("extent", st.get("extent")), ("junctions", st.get("junctions")),
                         ("mass", st.get("mass")), ("upkeep", m.get("upkeep")),
                         ("cover", aff.get("cover")), ("residue", aff.get("residue")),
                         ("links", aff.get("links")),
                         ("lasted", e.get("shifts_present"))):
            if isinstance(val, (int, float)):
                pools.setdefault(key, []).append(float(val))
    for k in pools:
        pools[k].sort()
    return pools


def _stands(value: Any, pool: List[float]) -> str:
    """Where one value sits among all of them, in words rather than a number."""
    if not isinstance(value, (int, float)) or not pool:
        return ""
    import bisect
    pct = bisect.bisect_left(pool, float(value)) / float(len(pool)) * 100.0
    if pct < 10: return "lower than almost all"
    if pct < 30: return "on the low side"
    if pct < 70: return "about typical"
    if pct < 90: return "on the high side"
    return "higher than almost all"


def esc(text: Any) -> str:
    return (str(text or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def render(data: Dict[str, Any]) -> str:
    specimens = data["specimens"]
    # Order: by category, then longest-lived first. Not by interest.
    ordered = sorted(specimens.values(),
                     key=lambda e: (e.get("category") or "~",
                                    -(e.get("shifts_present") or 0), e["id"]))
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for entry in ordered:
        by_cat.setdefault(entry.get("category") or "unclassified", []).append(entry)

    pools = _percentile_bands(ordered)
    living = sum(1 for e in ordered if e.get("alive"))
    with_plate = sum(1 for e in ordered if (e.get("measurements") or {}).get("structure"))

    out = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           '<title>Field Compendium</title>', '<style>', CSS, '</style></head><body>',
           '<div class="backbar"><a href="http://127.0.0.1:8730/hub.html">'
           '&larr; Department index</a></div>',
           '<header><p class="eyebrow">Department of Nonhuman Territories · %s</p>'
           % esc(data.get("terrain") or "BASIN-02"),
           '<h1>Field Compendium</h1>',
           '<div class="meta"><span>shift <b>%s</b></span><span><b>%d</b> classified</span>'
           '<span><b>%d</b> still living</span><span><b>%d</b> with measurements</span>'
           '<span><b>%d</b> categories</span></div>'
           % (esc(data.get("shift")), len(ordered), living, with_plate, len(by_cat)),
           '<p class="note">A record of everything that has lived in this terrain and been '
           'looked at closely.</p>'
           '<p class="note">Each drawing is made from that specimen\'s own measurements — how '
           'much it carried, how far it reached, how many others it could hold on to, how long '
           'it lasted. Nothing is drawn from imagination, and no two look alike because no two '
           'sets of numbers are alike.</p>'
           '<p class="note">The groupings are not ours either. A classifying agent called the '
           'Namer watches what each specimen does, decides for itself what kinds of thing are '
           'here, and names them. Its words appear below exactly as it wrote them — they are '
           'the finding, not a summary of one.</p>'
           '<p class="note">Each entry opens with a plain description. Those sentences are built '
           'by fixed rules from the specimen\'s own measurements — the same numbers the '
           'drawing uses — so they describe what was recorded and never guess. They say what '
           'a specimen was like and how it made its living; they never say what KIND of thing '
           'it was. That judgement belongs to the Namer, and its word for it is the heading '
           'above each group.</p>'
           '<p class="note">Where a specimen shows an empty frame, it died before this terrain '
           'began keeping remains, and nothing survives to draw from.</p></header>',
           HOWTO]

    for category, entries in sorted(by_cat.items()):
        # A compendium with 460 entries is unreadable as one scroll. Each
        # group folds, and the largest ones start closed, so a reader chooses
        # what to open rather than being handed everything at once.
        out.append('<details class="group"%s><summary><span class="gname">%s</span>'
                   '<span class="count">%d specimen%s</span></summary><div class="grid">'
                   % ("" if len(entries) <= 12 else "", esc(category), len(entries),
                      "" if len(entries) == 1 else "s"))
        for e in entries:
            m = e.get("measurements") or {}
            st = m.get("structure") or {}
            aff = m.get("affinities") or {}
            status = ('<span class="tag alive">living</span>' if e.get("alive")
                      else '<span class="tag ended">died at shift %s</span>' % esc(e.get("ended_at_shift")))
            rows = []
            band = _stands
            if st:
                rows.append(("reach", "%.2f" % st.get("extent", 0),
                             band(st.get("extent"), pools.get("extent", []))))
                rows.append(("holds", "%d link(s) at once" % (1 + int(st.get("junctions", 0))),
                             band(st.get("junctions"), pools.get("junctions", []))))
                rows.append(("carries", "%.2f" % st.get("mass", 0),
                             band(st.get("mass"), pools.get("mass", []))))
            if aff:
                strongest = max(("ground", aff.get("cover", 0)), ("remains", aff.get("residue", 0)),
                                ("others", aff.get("links", 0)), key=lambda kv: kv[1])[0]
                rows.append(("makes its living by",
                             "ground %.2f · remains %.2f · others %.2f"
                             % (aff.get("cover", 0), aff.get("residue", 0), aff.get("links", 0)),
                             "leans on the %s" % strongest))
            if m.get("upkeep") is not None:
                rows.append(("upkeep", "%.2f light every shift" % (m.get("upkeep") or 0),
                             band(m.get("upkeep"), pools.get("upkeep", []))))
                rows.append(("can hold", "%.1f light" % (m.get("capacity") or 0), ""))
            rows.append(("lasted", "%s shift(s)" % esc(e.get("shifts_present")),
                         band(e.get("shifts_present"), pools.get("lasted", []))))
            rows.append(("offspring",
                         esc(e.get("descendants") if e.get("descendants") is not None else "—"), ""))
            if m.get("substrate"):
                rows.append(("made of", esc(m["substrate"]), ""))
            if m.get("parent_id"):
                rows.append(("child of", esc(m["parent_id"]), ""))
            # The description a person can actually read. Deterministic, built
            # in code from the same numbers the plate is drawn from, shown to no
            # agent, and carrying no authority over what the Namer called it.
            elev = near = None
            m2 = e.get("measurements") or {}
            try:
                cell = m2.get("cell")
                if cell is not None:
                    elev = life.cell_elevation(int(cell))
                    near = life.cell_position(int(cell))
            except Exception:
                elev = near = None
            prose = describe.describe(e)
            where = describe.place(e, elev, near)
            out.append('<article class="card">%s<div class="body"><div class="id">'
                       '<a class="rec" href="specimens/%s.html">%s</a> %s</div>'
                       '<p class="prose">%s%s</p>'
                       % (plate(e), esc(e["id"]), esc(e["id"]), status, esc(prose),
                          (" " + esc(where)) if where else ""))
            out.append('<dl>%s</dl>' % "".join(
                "<dt>%s</dt><dd>%s%s</dd>"
                % (esc(k), esc(v),
                   (' <span class="stands">— %s</span>' % esc(b)) if b else "")
                for k, v, b in rows))
            if e.get("persistence"):
                out.append('<div class="quote"><span class="lbl">how it stays alive, in the Namer\'s own words</span>%s</div>'
                           % esc(e["persistence"][:600]))
            if e.get("reasoning"):
                out.append('<details><summary>why the Namer grouped it here</summary><p>%s</p></details>'
                           % esc(e["reasoning"][:1400]))
            out.append('</div></article>')
        out.append('</div></details>')

    out.append('<footer>Generated from state/specimen_log.jsonl, state/anomaly_log.jsonl and '
               'state/memory.json. Read-only: this tool writes one HTML file and changes no '
               'terrain record.</footer></body></html>')
    return "\n".join(out)


HOWTO = """
<section class="howto"><h2>How to read an entry</h2>
<p class="sub">Every figure below is a measurement the terrain recorded. None of them have
units — they only mean something next to each other, so each one is also described in
plain words against every other specimen on record.</p>
<dl class="gloss">
<dt>reach</dt><dd>How far out it can gather light from the ground around it. A long reach
collects from a wider area but costs more to keep up.</dd>
<dt>holds N links</dt><dd>How many other specimens it can be joined to at once. Light moves
along those joins — sometimes given, sometimes taken.</dd>
<dt>carries</dt><dd>How much substance it has. More lets it store more light and resist
having light pulled off it by others, and costs more every shift to hold together.</dd>
<dt>makes its living by</dt><dd>Where its light actually comes from. <b>ground</b> is the
cover layer growing where it stands; <b>remains</b> is what dead specimens left behind;
<b>others</b> is light drawn along links from other living things.</dd>
<dt>upkeep</dt><dd>What it must spend every shift simply to keep existing. If it cannot
cover this, it dies. Everything else has to be earned on top of it.</dd>
<dt>can hold</dt><dd>The most light it can store at once. Anything beyond this is lost.</dd>
<dt>lasted</dt><dd>How many shifts it was alive. A shift is one tick of the terrain.</dd>
</dl>
<p class="sub">The <b>drawing</b> is built from those same numbers: the core is what it
carries, the spokes are its links, their length is its reach, the rings are offspring, and
the disc beneath is how much it lived off remains.</p></section>
"""

CSS = dnt_style.CSS + """



.backbar{position:sticky;top:0;background:var(--paper);border-bottom:1px solid var(--rule);
padding:12px 0;margin-bottom:22px;z-index:5;max-width:1180px;margin:0 auto}
.backbar a{color:var(--moss);text-decoration:none;font:12px var(--mono);letter-spacing:.06em}
.backbar a:hover{text-decoration:underline}
header{max-width:70ch;margin:0 auto 40px;border-bottom:1px solid var(--rule);padding-bottom:22px}
.eyebrow{font:500 11px/1.5 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--grey);margin:0}
h1{font:400 clamp(28px,4vw,42px)/1.1 var(--serif);margin:10px 0 14px}
.meta{display:flex;flex-wrap:wrap;gap:6px 26px;font:12px/1.5 var(--mono);color:var(--grey)}
.meta b{color:var(--ink);font-weight:400;font-variant-numeric:tabular-nums}
.note{color:var(--grey);font-size:13.5px;margin:16px 0 0;max-width:70ch}
section{max-width:1180px;margin:0 auto 46px}
h2{font:400 22px/1.2 var(--serif);color:var(--moss);margin:0 0 4px;
border-bottom:1px solid var(--rule);padding-bottom:8px}
h2 .count{font:11px var(--mono);color:var(--grey);letter-spacing:.1em}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));margin-top:18px}
.card{background:var(--panel);border:1px solid var(--rule);display:flex;flex-direction:column}
.plate{width:100%;height:168px;display:block;background:#0E100C;border-bottom:1px solid var(--rule)}
.plate .core{fill:rgba(156,181,132,.20);stroke:#9CB584;stroke-width:1.2}
.plate .arm{stroke:#9CB584;stroke-width:1.1;opacity:.75}
.plate .node{fill:var(--moss);opacity:.9}
.plate .anchor{stroke:#7d8f6e;stroke-width:.9;opacity:.55}
.plate .brace{fill:none;stroke:#9CB584;stroke-width:.6;opacity:.45}
.plate .orbit{fill:none;stroke:#C9A227;stroke-width:.9;opacity:.55}
.plate .disc{fill:var(--amber);opacity:.22}
.plate.empty{background:#0C0D0B}
.plate .none{fill:#4A5046;font:11px ui-monospace,monospace;text-anchor:middle;letter-spacing:.1em}
.body{padding:14px 16px 16px;display:flex;flex-direction:column;gap:9px}
.prose{font:15px/1.62 var(--serif);margin:0 0 4px;color:var(--ink)}
.howto{max-width:1180px;margin:0 auto 44px;background:var(--panel);border:1px solid var(--rule);
padding:22px 24px}
.howto h2{color:var(--moss);border:none;padding:0;margin:0 0 8px}
.howto .sub{color:var(--grey);font-size:13.5px;max-width:76ch;margin:0 0 14px}
.gloss{display:grid;grid-template-columns:130px 1fr;gap:7px 20px;margin:0 0 16px;font-size:13.5px}
.gloss dt{font:12px var(--mono);color:var(--moss)}
.gloss dd{margin:0;color:var(--ink)}
.stands{color:var(--grey);font-style:italic;font-size:11.5px}
.id{font:13px var(--mono);color:var(--ink);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.tag{font:10px var(--mono);letter-spacing:.08em;text-transform:uppercase;padding:2px 6px;border:1px solid}
.tag.alive{color:var(--moss);border-color:#3B4A2F}
.tag.ended{color:var(--grey);border-color:var(--rule)}
dl{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;margin:0;font:12px/1.5 var(--mono);
font-variant-numeric:tabular-nums}
dt{color:var(--grey)}dd{margin:0}
.quote{border-left:2px solid var(--rule);padding:4px 0 4px 12px;font:italic 13px/1.55 var(--serif);color:var(--ink)}
.lbl{display:block;font:10px var(--mono);font-style:normal;letter-spacing:.09em;
text-transform:uppercase;color:var(--grey);margin-bottom:4px}
details{font-size:12.5px;color:var(--grey)}
summary{cursor:pointer;font:11px var(--mono);letter-spacing:.06em;color:var(--moss)}
details p{margin:8px 0 0;line-height:1.55}
footer{max-width:70ch;margin:40px auto 0;padding-top:18px;border-top:1px solid var(--rule);
font:11.5px/1.6 var(--mono);color:var(--grey)}
"""


def main(argv: List[str]) -> int:
    data = gather()
    html = render(data)
    with open(OUTPUT, "w", encoding="utf-8") as stream:
        stream.write(html)
    total = len(data["specimens"])
    plated = sum(1 for e in data["specimens"].values()
                 if (e.get("measurements") or {}).get("structure"))
    print("%d classified specimen(s); %d have measurements to draw from" % (total, plated))
    print("wrote %s" % OUTPUT)
    if "--open" in argv:
        webbrowser.open("file://" + OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
