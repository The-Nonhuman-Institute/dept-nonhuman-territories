"""
The specimen codex — a field guide drawn from one terrain's own record.

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
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
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


# ---------------------------------------------------------------------------
# The compendium is two documents, not one scroll.
#
# 462 entries in a single page is a page nobody reads. The index says what the
# terrain holds and how to read a measurement; each native category gets its
# own sheet, and that sheet is where the specimens are. Nothing is dropped —
# every specimen is on exactly one category sheet, and the index accounts for
# all of them.
# ---------------------------------------------------------------------------

ROOT = PROJECT_ROOT
import dnt_chrome

TERRAIN_DIR = os.path.basename(config.TERRAIN_ROOT.rstrip(os.sep))
CATEGORY_DIR = os.path.join(config.TERRAIN_ROOT, "codex")


def slug(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(name).lower())


def _band_rows(entry, pools):
    """The measurement table for one card. Value, then where it stands."""
    m = entry.get("measurements") or {}
    st = m.get("structure") or {}
    aff = m.get("affinities") or {}
    rows = []
    if st:
        rows.append(("reach", "%.2f" % st.get("extent", 0),
                     _stands(st.get("extent"), pools.get("extent", []))))
        rows.append(("holds n links", "%d (links)" % (1 + int(st.get("junctions", 0))),
                     _stands(st.get("junctions"), pools.get("junctions", []))))
        rows.append(("carries", "%.2f" % st.get("mass", 0),
                     _stands(st.get("mass"), pools.get("mass", []))))
    if aff:
        strongest = max(("ground", aff.get("cover", 0)), ("remains", aff.get("residue", 0)),
                        ("others", aff.get("links", 0)), key=lambda kv: kv[1])[0]
        rows.append(("makes its living by",
                     "ground %.2f · remains %.2f · others %.2f"
                     % (aff.get("cover", 0), aff.get("residue", 0), aff.get("links", 0)),
                     "leans on the %s" % strongest))
    if m.get("upkeep") is not None:
        rows.append(("upkeep", "%.2f light / shift" % (m.get("upkeep") or 0),
                     _stands(m.get("upkeep"), pools.get("upkeep", []))))
        rows.append(("can hold", "%.1f light" % (m.get("capacity") or 0), ""))
    rows.append(("lasted", "%s shift(s)" % esc(entry.get("shifts_present")),
                 _stands(entry.get("shifts_present"), pools.get("lasted", []))))
    rows.append(("offspring",
                 esc(entry.get("descendants") if entry.get("descendants") is not None else "—"), ""))
    if m.get("substrate"):
        rows.append(("made of", esc(m["substrate"]), ""))
    if m.get("parent_id"):
        rows.append(("child of", esc(m["parent_id"]), ""))
    return rows


def card(entry, pools, port) -> str:
    m = entry.get("measurements") or {}
    alive = bool(entry.get("alive"))
    # A specimen that has ended is not in the field, so there is nothing for a
    # 3D link to open. Saying so is better than a link that lands on nothing.
    corner = ('<a class="v3" href="http://127.0.0.1:%d/index.html#%s">VIEW 3D ↗</a>'
              % (port, esc(entry["id"]))) if alive \
        else '<span class="v3 gone">NOT IN THE FIELD</span>'
    status = ('<span class="st alive">LIVING</span>' if alive
              else '<span class="st">DIED AT SHIFT %s</span>' % esc(entry.get("ended_at_shift")))
    elev = near = None
    try:
        cell = m.get("cell")
        if cell is not None:
            elev = life.cell_elevation(int(cell))
            near = life.cell_position(int(cell))
    except Exception:
        elev = near = None
    prose = describe.describe(entry)
    where = describe.place(entry, elev, near)
    rows = "".join(
        '<tr><td class="k">%s</td><td class="v">%s%s</td></tr>'
        % (esc(k), esc(v), ('  –  <i>%s</i>' % esc(b)) if b else "")
        for k, v, b in _band_rows(entry, pools))
    words = ""
    if entry.get("persistence"):
        words += ('<div class="lbl">how it stays alive, in the Namer’s own words</div>'
                  '<p class="say">%s</p>' % esc(entry["persistence"][:700]))
    if entry.get("reasoning"):
        words += ('<details><summary>why the Namer grouped it here</summary>'
                  '<p>%s</p></details>' % esc(entry["reasoning"][:1600]))
    return (
        '<article class="card" data-alive="%d" data-shift="%s" data-lasted="%s" data-id="%s">'
        '<div class="draw"><div class="dh"><span>SPECIMEN DRAWING</span>%s</div>%s</div>'
        '<div class="body">'
        '<div class="id"><a href="/%s/specimens/%s.html">%s</a>%s</div>'
        '<p class="prose">%s%s</p>'
        '<table class="ms">%s</table>%s</div></article>'
        % (1 if alive else 0, esc(entry.get("ended_at_shift") or 0),
           esc(entry.get("shifts_present") or 0), esc(entry["id"]),
           corner, plate(entry),
           TERRAIN_DIR, esc(entry["id"]), esc(entry["id"]), status,
           esc(prose), (" " + esc(where)) if where else "", rows, words))


# ---------------------------------------------------------------------------

CSS = """
h1{font:400 clamp(30px,4.2vw,44px)/1.05 var(--serif);margin:0 0 10px}
h1.cat{font-family:var(--mono);font-size:clamp(22px,3vw,34px);letter-spacing:.01em;
text-transform:uppercase;margin:0 0 6px}
.eyebrow{font:10px var(--mono);letter-spacing:.16em;text-transform:uppercase;
color:var(--grey);margin:0 0 12px}
.mast{border-bottom:1px solid var(--rule);padding-bottom:20px;margin-bottom:26px;
display:grid;grid-template-columns:1fr auto;gap:30px;align-items:start}
.mast table.doc{border-collapse:collapse;font:11px/1.9 var(--mono);color:var(--grey)}
.mast table.doc td{padding:0 0 0 16px;white-space:nowrap}
.mast table.doc td.k{padding:0}.mast table.doc td.v{color:var(--ink)}
.strip{display:flex;flex-wrap:wrap;gap:6px 30px;font:12px var(--mono);color:var(--grey);
font-variant-numeric:tabular-nums;margin:0 0 4px}
.strip b{color:var(--ink);font-weight:400}
.lede{color:var(--ink);font-size:14.5px;line-height:1.7;max-width:72ch;margin:16px 0 0}
.lede.dim{color:var(--grey)}
h2.sec{font:10px var(--mono);letter-spacing:.15em;text-transform:uppercase;color:var(--grey);
margin:38px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--rule)}

/* how to read an entry */
.howto{border:1px solid var(--rule);background:var(--panel);padding:22px 24px;margin:30px 0}
.howto h3{font:10px var(--mono);letter-spacing:.15em;text-transform:uppercase;
color:var(--ink);margin:0 0 10px}
.howto .sub{color:var(--grey);font:11.5px/1.7 var(--mono);max-width:88ch;margin:0 0 16px}
.gloss{display:grid;grid-template-columns:150px 1fr;gap:9px 24px;margin:0 0 16px}
.gloss dt{font:11px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--grey)}
.gloss dd{margin:0;color:var(--ink);font-size:13.5px;line-height:1.55}
.howto .tail{font-size:12.5px;color:var(--grey);line-height:1.6;margin:0;
border-top:1px solid var(--rule);padding-top:13px}

/* the category index */
ul.cats{list-style:none;margin:0;padding:0}
ul.cats li{display:grid;grid-template-columns:1fr auto auto;gap:20px;align-items:baseline;
padding:9px 0;border-bottom:1px solid var(--rule)}
ul.cats a{color:var(--ink);text-decoration:none;font:13px var(--mono)}
ul.cats a:hover{color:var(--moss)}
ul.cats a:before{content:"> ";color:var(--grey)}
ul.cats .n{font:11.5px var(--mono);color:var(--grey);font-variant-numeric:tabular-nums}
ul.cats .go{font:10px var(--mono);letter-spacing:.08em;color:var(--moss)}
ul.docs{list-style:none;margin:0;padding:0;columns:2;column-gap:34px}
ul.docs li{padding:7px 0;border-bottom:1px solid var(--rule);break-inside:avoid}
ul.docs a{color:var(--ink);text-decoration:none;font:13px var(--mono)}
ul.docs a:before{content:"> ";color:var(--grey)}
ul.docs a:hover{color:var(--moss)}

/* the toolbar on a category sheet */
.bar{display:flex;align-items:center;gap:20px;flex-wrap:wrap;padding:11px 0;
border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);margin-bottom:22px;
font:10.5px var(--mono);letter-spacing:.07em;color:var(--grey);text-transform:uppercase}
.bar .count b{color:var(--ink);font-weight:400}
.bar .grp{display:flex;align-items:center;gap:8px;margin-left:auto}
.bar select{font:10.5px var(--mono);letter-spacing:.06em;background:var(--panel);
color:var(--ink);border:1px solid var(--rule);padding:4px 7px;text-transform:uppercase}
.bar button{font:10.5px var(--mono);letter-spacing:.06em;background:var(--panel);
color:var(--grey);border:1px solid var(--rule);padding:4px 9px;cursor:pointer;
text-transform:uppercase}
.bar button.on{background:var(--moss);border-color:var(--moss);color:var(--paper)}

/* the cards */
.grid{display:grid;gap:16px;grid-template-columns:repeat(4,minmax(0,1fr))}
.grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}
@media(max-width:1500px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:1150px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.grid,.grid.two{grid-template-columns:1fr}}
.card{border:1px solid var(--rule);background:var(--panel);display:flex;flex-direction:column}
.card.hide{display:none}
.draw{position:relative;background:#0B0D0A;border-bottom:1px solid var(--rule)}
.dh{position:absolute;inset:9px 10px auto 10px;display:flex;justify-content:space-between;
font:9px var(--mono);letter-spacing:.1em;color:#6E7A6B;z-index:2}
.dh a.v3{color:#8FC96B;text-decoration:none}
.dh a.v3:hover{text-decoration:underline}
.dh .gone{color:#4A5046}
.plate{width:100%;height:196px;display:block}
.plate .core{fill:rgba(156,181,132,.20);stroke:#9CB584;stroke-width:1.2}
.plate .arm{stroke:#9CB584;stroke-width:1.1;opacity:.75}
.plate .node{fill:#8FC96B;opacity:.9}
.plate .anchor{stroke:#7d8f6e;stroke-width:.9;opacity:.55}
.plate .brace{fill:none;stroke:#9CB584;stroke-width:.6;opacity:.45}
.plate .orbit{fill:none;stroke:#C9A227;stroke-width:.9;opacity:.55}
.plate .disc{fill:#C9A227;opacity:.22}
.plate.empty{background:#0B0D0A}
.plate .none{fill:#4A5046;font:11px ui-monospace,monospace;text-anchor:middle;letter-spacing:.1em}
.body{padding:13px 15px 16px;display:flex;flex-direction:column;gap:10px}
.id{font:12px var(--mono);display:flex;justify-content:space-between;gap:10px;
align-items:baseline;border-bottom:1px solid var(--rule);padding-bottom:8px}
.id a{color:var(--ink);text-decoration:none}
.id a:hover{color:var(--moss)}
.st{font:9.5px var(--mono);letter-spacing:.08em;color:var(--grey);white-space:nowrap}
.st.alive{color:var(--moss)}
.prose{font:14px/1.62 var(--serif);margin:0;color:var(--ink)}
table.ms{border-collapse:collapse;width:100%;font:11px/1.55 var(--mono);
font-variant-numeric:tabular-nums}
table.ms td{padding:2px 0;vertical-align:top}
table.ms td.k{color:var(--grey);padding-right:12px;width:44%}
table.ms td.v i{color:var(--grey);font-style:normal}
.lbl{font:9px var(--mono);letter-spacing:.11em;text-transform:uppercase;color:var(--grey);
border-top:1px solid var(--rule);padding-top:10px}
.say{font:12px/1.6 var(--mono);color:var(--ink);margin:0}
.card details{font-size:11.5px;color:var(--grey)}
.card summary{cursor:pointer;font:10px var(--mono);letter-spacing:.07em;color:var(--moss)}
.card details p{margin:7px 0 0;line-height:1.6;font:11.5px/1.6 var(--mono)}
.none{color:var(--grey);font-style:italic}
.foot-note{margin:36px 0 0;padding-top:14px;border-top:1px solid var(--rule);
color:var(--grey);font:11.5px/1.6 var(--mono)}
"""

SORT_JS = """
<script>
(function(){
  var grid=document.getElementById('grid');
  if(!grid)return;
  var cards=Array.prototype.slice.call(grid.children);
  var num=function(c,k){return Number(c.dataset[k]||0)};
  var sorts={
    shift:function(a,b){return num(b,'shift')-num(a,'shift')},
    lasted:function(a,b){return num(b,'lasted')-num(a,'lasted')},
    id:function(a,b){return a.dataset.id.localeCompare(b.dataset.id)}
  };
  var sel=document.getElementById('sort');
  sel.onchange=function(){
    cards.slice().sort(sorts[sel.value]).forEach(function(c){grid.appendChild(c)});
  };
  sel.onchange();
  var show=function(mode){
    var n=0;
    cards.forEach(function(c){
      var ok = mode==='all' || (mode==='living')===(c.dataset.alive==='1');
      c.classList.toggle('hide',!ok);
      if(ok)n++;
    });
    document.getElementById('shown').textContent=n;
  };
  document.querySelectorAll('[data-filter]').forEach(function(b){
    b.onclick=function(){
      document.querySelectorAll('[data-filter]').forEach(function(x){x.classList.remove('on')});
      b.classList.add('on'); show(b.dataset.filter);
    };
  });
  document.querySelectorAll('[data-cols]').forEach(function(b){
    b.onclick=function(){
      document.querySelectorAll('[data-cols]').forEach(function(x){x.classList.remove('on')});
      b.classList.add('on'); grid.classList.toggle('two', b.dataset.cols==='2');
    };
  });
})();
</script>
"""

HOWTO = """
<section class="howto"><h3>How to read an entry</h3>
<p class="sub">Every figure on a specimen sheet is a measurement the terrain recorded. None of
them have units — they only mean something next to each other, so each one is also
described in plain words against every other specimen on record.</p>
<dl class="gloss">
<dt>reach</dt><dd>How far out it can gather light from the ground around it. A long reach
collects from a wider area but costs more to keep up.</dd>
<dt>holds n links</dt><dd>How many other specimens it can be joined to at once. Light moves
along those joins — sometimes given, sometimes taken.</dd>
<dt>carries</dt><dd>How much substance it has. More lets it store more light and resist having
light pulled off it by others, and costs more every shift to hold together.</dd>
<dt>makes its living by</dt><dd>Where its light actually comes from. <b>ground</b> is the cover
layer growing where it stands; <b>remains</b> is what dead specimens left behind;
<b>others</b> is light drawn along links from other living things.</dd>
<dt>upkeep</dt><dd>What it must spend every shift simply to keep existing. If it cannot cover
this, it dies. Everything else has to be earned on top of it.</dd>
<dt>can hold</dt><dd>The most light it can store at once. Anything beyond this is lost.</dd>
<dt>lasted</dt><dd>How many shifts it was alive. A shift is one tick of the terrain.</dd>
</dl>
<p class="tail">The drawing is built from those same numbers: the core is what it carries, the
spokes are its links, their length is its reach, the rings are offspring, and the disc beneath
is how much it lived off remains.</p></section>
"""

FOOT = ("Generated from state/specimen_log.jsonl, state/anomaly_log.jsonl and state/memory.json. "
        "Read-only: this tool writes HTML and changes no terrain record.")


def _shell(title, crumbs, page_file, body, topright=""):
    return dnt_chrome.page(
        title, dnt_chrome.PAPER, CSS, body + ('<p class="foot-note">%s</p>' % FOOT),
        crumbs, dnt_chrome.sidebar(ROOT, TERRAIN_DIR, page_file), topright,
        "DNT FIELD MANUAL v1.0")


def render_index(data, by_cat, ordered, port) -> str:
    living = sum(1 for e in ordered if e.get("alive"))
    plated = sum(1 for e in ordered if (e.get("measurements") or {}).get("structure"))
    terrain = esc(data.get("terrain") or TERRAIN_DIR.upper())

    cats = "".join(
        '<li><a href="/%s/codex/%s.html">%s</a>'
        '<span class="n">%d living / %d total</span>'
        '<span class="go">VIEW SHEET →</span></li>'
        % (TERRAIN_DIR, slug(c), esc(c),
           sum(1 for e in es if e.get("alive")), len(es))
        for c, es in sorted(by_cat.items(), key=lambda kv: (-len(kv[1]), kv[0])))

    # Only documents that exist. A related-documents list that links to pages
    # nobody has written is worse than a short one.
    related = []
    for filename, label in (("structure.html", "classification structure"),
                            ("crosswalk.html", "Linnaean crosswalk"),
                            ("terrain.html", "terrain record — governing conditions"),
                            ("shiftlog.html", "shift log — every shift committed")):
        if os.path.exists(os.path.join(config.TERRAIN_ROOT, filename)):
            related.append('<li><a href="/%s/%s">%s</a></li>' % (TERRAIN_DIR, filename, label))
    related.append('<li><a href="http://127.0.0.1:%d/index.html">observation deck '
                   '— walk the terrain in 3D</a></li>' % port)

    body = (
        '<div class="mast"><div>'
        '<p class="eyebrow">Department of Nonhuman Territories · %s</p>'
        '<h1>Field Compendium</h1>'
        '<div class="strip"><span>shift <b>%s</b></span><span><b>%d</b> classified</span>'
        '<span><b>%d</b> still living</span><span><b>%d</b> with measurements</span>'
        '<span><b>%d</b> categories</span></div>'
        '<p class="lede">A record of everything that has lived in this terrain and been looked '
        'at closely.</p>'
        '<p class="lede dim">Each drawing is made from that specimen’s own measurements '
        '— how much it carried, how far it reached, how many others it could hold on to, '
        'how long it lasted. Nothing is drawn from imagination, and no two look alike because '
        'no two sets of numbers are alike.</p>'
        '<p class="lede dim">The groupings are not ours either. A classifying agent called the '
        'Namer watches what each specimen does, decides for itself what kinds of thing are here, '
        'and names them. Its words appear on each sheet exactly as it wrote them — they are '
        'the finding, not a summary of one.</p>'
        '<p class="lede dim">Each entry opens with a plain description. Those sentences are '
        'built by fixed rules from the specimen’s own measurements — the same numbers '
        'the drawing uses — so they describe what was recorded and never guess. They say '
        'what a specimen was like and how it made its living; they never say what KIND of thing '
        'it was. That judgement belongs to the Namer, and its word for it is the title of the '
        'sheet.</p>'
        '<p class="lede dim">Where a specimen shows an empty frame, it died before this terrain '
        'began keeping remains, and nothing survives to draw from.</p>'
        '<p class="lede dim">One caution about the counts above: they are counts of '
        '<b>individually classified</b> specimens. The Namer records most of the population '
        'in aggregate and the cover layer as a census, so a terrain holding thousands of '
        'living things may have only dozens of them written up here. The observation deck '
        'reports the whole population; this document reports the part of it that was looked '
        'at one at a time.</p>'
        '</div>'
        '<table class="doc"><tr><td class="k">DOCUMENT</td><td class="v">DNT-TAX-CDX</td></tr>'
        '<tr><td class="k">TERRAIN</td><td class="v">%s</td></tr>'
        '<tr><td class="k">SHIFT</td><td class="v">%s</td></tr>'
        '<tr><td class="k">STATUS</td><td class="v">EXPLORATORY</td></tr>'
        '<tr><td class="k">SCOPE</td><td class="v">INTERNAL</td></tr></table></div>'
        '%s'
        '<h2 class="sec">Native categories in this terrain</h2>'
        '<ul class="cats">%s</ul>'
        '<h2 class="sec">Related documents</h2><ul class="docs">%s</ul>'
        % (terrain, esc(data.get("shift")), len(ordered), living, plated, len(by_cat),
           terrain, esc(data.get("shift")), HOWTO, cats, "".join(related)))

    return _shell("Field Compendium — " + terrain,
                  [terrain, "FIELD COMPENDIUM"], "codex.html", body,
                  '<a href="http://127.0.0.1:%d/index.html">Observation deck</a>' % port)


def render_category(data, category, entries, pools, port) -> str:
    terrain = esc(data.get("terrain") or TERRAIN_DIR.upper())
    living = sum(1 for e in entries if e.get("alive"))
    plated = sum(1 for e in entries if (e.get("measurements") or {}).get("structure"))
    cards = "".join(card(e, pools, port) for e in entries)
    body = (
        '<div class="mast"><div>'
        '<p class="eyebrow"><a style="color:inherit;text-decoration:none" '
        'href="/%s/codex.html">Field compendium</a> · %s · native category</p>'
        '<h1 class="cat">%s</h1>'
        '<div class="strip"><span><b>%d</b> specimens</span><span><b>%d</b> living</span>'
        '<span><b>%d</b> with measurements</span></div></div>'
        '<table class="doc"><tr><td class="k">TERRAIN</td><td class="v">%s</td></tr>'
        '<tr><td class="k">SHIFT</td><td class="v">%s</td></tr>'
        '<tr><td class="k">COINED BY</td><td class="v">THE NAMER</td></tr></table></div>'
        '<div class="bar">'
        '<span class="count"><b id="shown">%d</b> of <b>%d</b> shown in this category</span>'
        '<span class="grp">show'
        '<button data-filter="all" class="on">all</button>'
        '<button data-filter="living">living</button>'
        '<button data-filter="ended">ended</button>'
        '&nbsp;&nbsp;view'
        '<button data-cols="4" class="on">4</button>'
        '<button data-cols="2">2</button>'
        '&nbsp;&nbsp;sort'
        '<select id="sort"><option value="shift">by shift (newest)</option>'
        '<option value="lasted">by shifts lasted</option>'
        '<option value="id">by identifier</option></select></span></div>'
        '<div class="grid" id="grid">%s</div>%s'
        % (TERRAIN_DIR, terrain, esc(category), len(entries), living, plated,
           terrain, esc(data.get("shift")), len(entries), len(entries), cards, SORT_JS))
    return _shell("%s — %s" % (esc(category), terrain),
                  [terrain, "FIELD COMPENDIUM", esc(category).upper()], "codex.html", body,
                  '<a href="/%s/codex.html">All categories</a>' % TERRAIN_DIR)


def main(argv: List[str]) -> int:
    data = gather()
    specimens = data["specimens"]
    ordered = sorted(specimens.values(),
                     key=lambda e: (e.get("category") or "~",
                                    -(e.get("shifts_present") or 0), e["id"]))
    by_cat = {}
    for entry in ordered:
        by_cat.setdefault(entry.get("category") or "unclassified", []).append(entry)
    pools = _percentile_bands(ordered)
    port = {"basin-01": 8731, "basin-02": 8732,
            "basin-03": 8733, "basin-04": 8734}.get(TERRAIN_DIR, 8731)

    with open(OUTPUT, "w", encoding="utf-8") as stream:
        stream.write(render_index(data, by_cat, ordered, port))

    if not os.path.isdir(CATEGORY_DIR):
        os.makedirs(CATEGORY_DIR)
    for category, entries in by_cat.items():
        path = os.path.join(CATEGORY_DIR, slug(category) + ".html")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(render_category(data, category, entries, pools, port))

    plated = sum(1 for e in ordered if (e.get("measurements") or {}).get("structure"))
    print("%d classified specimen(s); %d have measurements to draw from"
          % (len(ordered), plated))
    print("wrote %s and %d category sheet(s)" % (OUTPUT, len(by_cat)))
    if "--open" in argv:
        webbrowser.open("file://" + OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
