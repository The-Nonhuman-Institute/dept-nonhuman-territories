"""
DNT — the department index. One page that ties the terrains together.

    python3 hub.py            write hub.html
    python3 hub.py --open     write it and open it

Reads both terrains' state and writes a single index linking the observation
decks, the specimen codices, the checkpoint reports and the governance
documents. Read-only: it changes no terrain record.

Everything it links to is local. Nothing here publishes anything.
"""

from __future__ import annotations

import json
import os
import sys
import webbrowser
import dnt_style
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(ROOT, "hub.html")

TERRAINS = [
    {"dir": "basin-01", "name": "BASIN-01", "id": "DNT-T01", "port": 8731,
     "shape": "a line of 21 cells",
     "role": "Control. Physics frozen at v1.4; not to be amended."},
    {"dir": "basin-02", "name": "BASIN-02", "id": "DNT-T02", "port": 8732,
     "shape": "a field 21 deep x 15 wide, with relief",
     "role": "Controlled comparison through shift 140; exploratory since."},
    {"dir": "basin-04", "name": "BASIN-04", "id": "DNT-T04", "port": 8734,
     "shape": "an eroded landscape under six governing conditions",
     "role": "Exploratory. Temperature, wind, gravity, subsurface water, a declared "
             "light cycle and shift length — all real mechanics, present from seeding."},
    {"dir": "basin-03", "name": "BASIN-03", "id": "DNT-T03", "port": 8733,
     "shape": "an eroded landscape that grows at its margins",
     "role": "Ground formed by process, not formula. Watercourses cut by flow; "
             "an irregular shore; the terrain extends where something reaches it."},
]


def read(terrain: Dict[str, Any]) -> Dict[str, Any]:
    path = os.path.join(ROOT, terrain["dir"], "state", "memory.json")
    out = dict(terrain)
    out.update({"shift": None, "living": None, "spend": None, "categories": None,
                "events": None, "specimens": None})
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as stream:
        memory = json.load(stream)
    out["shift"] = memory.get("last_committed_shift")
    out["living"] = len((memory.get("world") or {}).get("individuals") or {})
    out["spend"] = memory.get("cumulative_cost_usd", 0.0)
    out["categories"] = len(memory.get("category_stats") or {})
    out["events"] = len(memory.get("terrain_events") or [])
    log = os.path.join(ROOT, terrain["dir"], "state", "specimen_log.jsonl")
    if os.path.exists(log):
        with open(log, encoding="utf-8") as stream:
            out["specimens"] = sum(1 for line in stream if line.strip())
    out["has_codex"] = os.path.exists(os.path.join(ROOT, terrain["dir"], "codex.html"))
    reports = [f for f in os.listdir(os.path.join(ROOT, terrain["dir"]))
               if f.startswith("checkpoint") and f.endswith(".html")] \
        if os.path.isdir(os.path.join(ROOT, terrain["dir"])) else []
    out["reports"] = sorted(reports)
    return out


def esc(v: Any) -> str:
    return (str(v if v is not None else "—").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def render(terrains: List[Dict[str, Any]]) -> str:
    total = sum(t["spend"] or 0.0 for t in terrains)
    cards = []
    for t in terrains:
        links = ['<a class="go" href="http://127.0.0.1:%d/index.html">Observation deck '
                 '<span>walk the terrain in 3D</span></a>' % t["port"]]
        # Every document this terrain has produced. These were dropping off the
        # index whenever the template was rewritten, because they were added by
        # patching this list rather than derived from what exists on disk. They
        # are now discovered from the directory, so a document cannot be
        # generated and then quietly go unlinked.
        for filename, label, blurb in (
                ("terrain.html", "Terrain record",
                 "the terrain as its own logs describe it — governing conditions, "
                 "population over time, events"),
                ("shiftlog.html", "Shift log",
                 "every shift committed, with what changed in each"),
                ("codex.html", "Field compendium",
                 "every specimen ever classified — a plain description, a drawing built "
                 "from its own measurements, and the Namer's words"),
                ("structure.html", "Classification structure",
                 "four ways of arranging the same observations: lineage, network, "
                 "spectrum, sequence"),
                ("crosswalk.html", "Linnaean crosswalk",
                 "the Archivist's translation of the native taxonomy into human terms "
                 "(DNT-CLS-001 §2)")):
            if os.path.exists(os.path.join(ROOT, t["dir"], filename)):
                links.append('<a class="go" href="%s/%s">%s <span>%s</span></a>'
                             % (t["dir"], filename, label, blurb))
        for report in t.get("reports") or []:
            links.append('<a class="go" href="%s/%s">%s <span>checkpoint report</span></a>'
                         % (t["dir"], report,
                            report.replace("_", " ").replace(".html", "").title()))
        cards.append(
            '<article class="terrain">'
            '<header><h2>%s</h2><p class="tid">%s · %s</p></header>'
            '<p class="role">%s</p>'
            '<dl class="stat"><dt>shift</dt><dd>%s</dd><dt>living</dt><dd>%s</dd>'
            '<dt>categories</dt><dd>%s</dd><dt>classified</dt><dd>%s</dd>'
            '<dt>terrain events</dt><dd>%s</dd><dt>spend</dt><dd>$%s</dd></dl>'
            '<div class="links">%s</div></article>'
            % (esc(t["name"]), esc(t["id"]), esc(t["shape"]), esc(t["role"]),
               esc(t["shift"]), esc(t["living"]), esc(t["categories"]),
               esc(t["specimens"]), esc(t["events"]),
               ("%.4f" % t["spend"]) if t["spend"] is not None else "—",
               "".join(links)))

    docs = []
    docs_dir = os.path.join(ROOT, "docs")
    if os.path.isdir(docs_dir):
        for name in sorted(os.listdir(docs_dir)):
            if name.endswith(".docx") and "BACKUP" not in name:
                docs.append('<li><a href="docs/%s">%s</a></li>'
                            % (name, esc(name.replace("_", " ").replace(".docx", ""))))
    for name in ("physics.md", "physics_basin02.md", "README.md", "STARTUP_GUIDE.md"):
        if os.path.exists(os.path.join(ROOT, name)):
            docs.append('<li><a href="%s">%s</a></li>' % (name, esc(name)))

    page = TEMPLATE % {"cards": "".join(cards), "docs": "".join(docs)}
    return (page.replace("__CSS__", dnt_style.CSS)
                .replace("__MASTHEAD__", dnt_style.backbar() + dnt_style.masthead(
                    "Department of Nonhuman Territories",
                    "Bounded digital environments seeded with fixed mechanical rules, in "
                    "which autonomous roles run over time.<br>What emerges is recorded and "
                    "classified, never authored, corrected, or steered.",
                    [("TERRAINS", str(len(terrains))),
                     ("COMBINED SPEND", "$%.4f" % total),
                     ("STATUS", "ACTIVE")])))


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Department Index</title><style>__CSS__
.grid{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(330px,1fr))}
.terrain{border:1px solid var(--ink);background:var(--panel);padding:18px 20px;
display:flex;flex-direction:column;gap:11px}
.terrain h2{font:400 23px/1.1 var(--serif);margin:0;color:var(--ink)}
.tid{font:10.5px var(--mono);letter-spacing:.08em;color:var(--grey);margin:2px 0 0}
.role{font-size:12.5px;color:var(--grey);margin:0}
dl.stat{display:grid;grid-template-columns:auto 1fr;gap:2px 14px;margin:0;
font:11.5px/1.7 var(--mono);font-variant-numeric:tabular-nums;
border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:8px 0}
dl.stat dt{color:var(--grey)}
dl.stat dd{margin:0;text-align:right}
.links{display:flex;flex-direction:column;gap:6px}
a.go{display:block;padding:9px 12px;border:1px solid var(--rule);color:var(--ink);
text-decoration:none;font-size:13.5px;background:var(--paper)}
a.go span{display:block;font-size:11px;color:var(--grey);margin-top:2px;line-height:1.5}
a.go:hover{border-color:var(--moss)}
a.go:focus-visible{outline:2px solid var(--moss);outline-offset:2px}
ul.docs{margin:0;padding-left:18px;columns:2;column-gap:30px;font-size:13px}
ul.docs li{margin-bottom:5px;break-inside:avoid}
ul.docs a{color:var(--moss)}
</style></head><body><div class="sheet">
__MASTHEAD__
<section><h3>Terrains</h3><div class="grid">%(cards)s</div></section>
<section><h3>Governing documents</h3><ul class="docs">%(docs)s</ul></section>
<footer>Generated from each terrain's own state. Read-only — this index changes no record.
The observation decks require the local server: <code>python3 serve_terrains.py</code></footer>
</div></body></html>"""


def main(argv: List[str]) -> int:
    terrains = [read(t) for t in TERRAINS]
    with open(OUTPUT, "w", encoding="utf-8") as stream:
        stream.write(render(terrains))
    for t in terrains:
        print("  %-9s shift %-5s %4s living  $%s"
              % (t["name"], t["shift"], t["living"],
                 ("%.4f" % t["spend"]) if t["spend"] is not None else "—"))
    print("wrote %s" % OUTPUT)
    if "--open" in argv:
        webbrowser.open("file://" + OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
