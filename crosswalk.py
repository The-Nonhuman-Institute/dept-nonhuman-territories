"""
DNT — the Linnaean crosswalk, made readable.

    python3 crosswalk.py basin-03            write basin-03/crosswalk.html
    python3 crosswalk.py basin-03 --open     ...and open it

WHY THIS EXISTS

  DNT-CLS-001 Section 2 requires the Archivist to maintain a best-effort
  translation of each terrain's native taxonomy into Linnaean terms, for human
  readers. That has been produced on every Archivist pass since each terrain
  was seeded, and it has been sitting in memory.json where nobody could read
  it. The requirement was met and the point of it was not.

  This renders it. It reads the record and writes one file.

WHAT THE CROSSWALK IS, AND IS NOT

  It is a translation layer for human readers. It carries NO authority over the
  native taxonomy and does not feed back into it. The Namer never sees it. A
  clean mapping is not required and "no clear Linnaean equivalent" is a valid
  and expected answer — the Archivist says so itself, in its own confidence
  ratings, and those are shown here rather than smoothed away.

  Reading this page as "what the specimens really are" would invert the whole
  method. The native system is the finding. This is the footnote.

Python 3.9 compatible. Read-only.
"""

from __future__ import annotations

import json
import os
import sys
import webbrowser
import dnt_style
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.abspath(__file__))
TIER_ORDER = ["Domain", "Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species"]


def esc(v: Any) -> str:
    return (str(v if v is not None else "—").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def gather(terrain: str) -> Dict[str, Any]:
    path = os.path.join(ROOT, terrain, "state", "memory.json")
    with open(path, encoding="utf-8") as stream:
        memory = json.load(stream)
    ann = (memory.get("annotations") or {}).get("linnaean_crosswalk") or {}
    payload = ann.get("payload") or {}
    return {
        "terrain": memory.get("terrain_name") or terrain.upper(),
        "shift": memory.get("last_committed_shift"),
        "pass_at": ann.get("shift"),
        "at": ann.get("at"),
        "payload": payload,
        "categories": memory.get("category_stats") or {},
    }


def render(data: Dict[str, Any]) -> str:
    p = data["payload"]
    rows = p.get("crosswalk") or []
    stats = data["categories"]

    mapped = {r.get("category") for r in rows if isinstance(r, dict)}
    unmapped = sorted(set(stats) - mapped)

    body = []
    body.append('<header><p class="eyebrow">%s · DNT-CLS-001 Section 2</p>'
                '<h1>The Linnaean Crosswalk</h1>'
                '<p class="lede">A best-effort translation of this terrain\'s native taxonomy '
                'into Linnaean terms, produced by the Archivist <em>after</em> classification. '
                'It carries no authority over the native system and does not feed back into '
                'it. The Namer has never seen it.</p>'
                '<div class="meta"><span>terrain at shift <b>%s</b></span>'
                '<span>last crosswalk pass <b>shift %s</b></span>'
                '<span><b>%d</b> categories in use</span></div></header>'
                % (esc(data["terrain"]), esc(data["shift"]), esc(data["pass_at"]), len(stats)))

    if p.get("crosswalk_note"):
        body.append('<div class="note">%s</div>' % esc(p["crosswalk_note"]))

    body.append('<section><h2>What maps to what</h2><div class="scroll"><table>'
                '<thead><tr><th>Native category</th><th class="num">Specimens</th>'
                '<th>Linnaean tier</th><th>Confidence</th>'
                '<th>The Archivist\'s note</th></tr></thead><tbody>')
    for r in rows:
        if not isinstance(r, dict):
            continue
        conf = (r.get("confidence") or "none").lower()
        tier = r.get("tier")
        body.append('<tr><td><code>%s</code></td><td class="num">%s</td>'
                    '<td>%s</td><td><span class="conf %s">%s</span></td>'
                    '<td class="note-cell">%s</td></tr>'
                    % (esc(r.get("category")),
                       esc((stats.get(r.get("category")) or {}).get("count", "—")),
                       ('<b>%s</b>' % esc(tier)) if tier else
                       '<span class="none">no equivalent</span>',
                       esc(conf), esc(conf), esc(r.get("note"))))
    body.append('</tbody></table></div>')

    if unmapped:
        body.append('<div class="gap"><h3>Not yet crosswalked</h3>'
                    '<p>%d categories are in active use but have no entry in the latest pass. '
                    'The Archivist runs on a cadence, so categories coined since its last pass '
                    'wait for the next one. This gap is shown rather than hidden:</p><p>%s</p></div>'
                    % (len(unmapped),
                       " ".join('<code>%s</code>' % esc(c) for c in unmapped)))
    body.append('</section>')

    if p.get("consistency_notes"):
        body.append('<section><h2>Is the native system self-consistent?</h2>'
                    '<div class="quote">%s</div></section>' % esc(p["consistency_notes"]))

    pc = p.get("persistence_crosswalk") or []
    if pc:
        body.append('<section><h2>How specimens persist, in both vocabularies</h2>'
                    '<p class="sub">The Namer describes persistence in its own words. The '
                    'Archivist assigns a reference state alongside it — never instead of it.</p>')
        for e in pc[:14]:
            if not isinstance(e, dict):
                continue
            body.append('<div class="pair"><div class="native">%s</div>'
                        '<div class="ref"><span class="lbl">reference state</span>'
                        '<code>%s</code>%s</div></div>'
                        % (esc(e.get("native_wording")), esc(e.get("reference_state")),
                           ('<p class="pn">%s</p>' % esc(e["note"])) if e.get("note") else ""))
        body.append('</section>')

    lin = p.get("lineages") or {}
    if lin.get("lineages_found") is not None:
        body.append('<section><h2>Lineages</h2><p class="sub">%s</p>'
                    '<p><b>%s</b> lineages traced from parentage. No model was consulted.</p>'
                    '</section>' % (esc(lin.get("note")), esc(lin.get("lineages_found"))))

    # Literal replacement, not %-formatting: the stylesheet is full of percent
    # signs (max-width:100%) and every one of them is a format specifier to
    # Python.
    return (TEMPLATE.replace("__HOUSE__", dnt_style.CSS)
                    .replace("%(body)s", "".join(body))
                    .replace("%(terrain)s", esc(data["terrain"])))


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Linnaean Crosswalk</title><style>__HOUSE__





.wrap{max-width:1000px;margin:0 auto}
.backbar{position:sticky;top:0;background:var(--paper);border-bottom:1px solid var(--rule);
padding:12px 0;margin-bottom:26px;z-index:5}
.backbar a{color:var(--moss);text-decoration:none;font:12px var(--mono);letter-spacing:.06em}
.backbar a:hover{text-decoration:underline}
.eyebrow{font:500 11px/1.5 var(--mono);letter-spacing:.16em;text-transform:uppercase;
color:var(--grey);margin:0}
h1{font:400 clamp(28px,4vw,42px)/1.1 var(--serif);margin:10px 0 12px}
h2{font:400 23px/1.2 var(--serif);margin:0 0 6px;color:var(--moss)}
h3{font:600 12px/1.4 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--grey);margin:0 0 6px}
.lede{color:var(--grey);max-width:70ch;margin:0}
.meta{display:flex;flex-wrap:wrap;gap:6px 26px;margin-top:14px;font:12px var(--mono);color:var(--grey)}
.meta b{color:var(--ink);font-weight:400}
header{border-bottom:2px solid var(--ink);padding-bottom:20px;margin-bottom:30px}
.note{background:var(--panel);border-left:3px solid var(--amber);padding:12px 16px;
font-size:13.5px;color:var(--grey);margin-bottom:30px;max-width:74ch}
section{margin-bottom:38px}
.sub{color:var(--grey);font-size:13.5px;max-width:72ch;margin:0 0 14px}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:720px;font-size:13.5px;
font-variant-numeric:tabular-nums;margin-top:12px}
th{text-align:left;font:600 10.5px/1.4 var(--mono);letter-spacing:.1em;text-transform:uppercase;
color:var(--grey);border-bottom:1px solid var(--ink);padding:0 14px 8px 0;vertical-align:bottom}
td{border-bottom:1px solid var(--rule);padding:11px 14px 11px 0;vertical-align:top}
td.num,th.num{text-align:right;padding-right:20px;font-family:var(--mono)}
.note-cell{color:var(--grey);font-size:12.5px;max-width:40ch}
code{font:12.5px var(--mono);background:var(--panel);padding:1px 5px;border:1px solid var(--rule)}
.none{color:var(--grey);font-style:italic}
.conf{font:10px var(--mono);letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border:1px solid}
.conf.partial{color:var(--amber);border-color:var(--amber)}
.conf.none{color:var(--grey);border-color:var(--rule)}
.conf.full,.conf.high{color:var(--moss);border-color:var(--moss)}
.gap{background:var(--panel);border:1px solid var(--rule);padding:16px 18px;margin-top:20px;
font-size:13.5px;color:var(--grey);max-width:74ch}
.gap code{margin-right:5px;display:inline-block;margin-bottom:4px}
.quote{border-left:2px solid var(--rule);padding:4px 0 4px 18px;font:italic 14.5px/1.6 var(--serif);
max-width:74ch}
.pair{display:grid;grid-template-columns:1fr 260px;gap:18px;padding:14px 0;
border-bottom:1px solid var(--rule)}
.native{font:italic 13.5px/1.6 var(--serif)}
.ref .lbl{display:block;font:10px var(--mono);letter-spacing:.09em;text-transform:uppercase;
color:var(--grey);margin-bottom:4px}
.pn{color:var(--grey);font-size:12px;margin:6px 0 0}
@media(max-width:720px){.pair{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<div class="backbar"><a href="http://127.0.0.1:8730/hub.html">&larr; Department index</a></div>
%(body)s
</div></body></html>"""


def main(argv: List[str]) -> int:
    terrain = None
    for a in argv[1:]:
        if not a.startswith("--"):
            terrain = a
    if not terrain:
        print("usage: python3 crosswalk.py <terrain-dir> [--open]")
        return 1
    data = gather(terrain)
    if not data["payload"]:
        print("%s has no crosswalk yet — the Archivist runs on a cadence." % terrain)
        return 1
    out = os.path.join(ROOT, terrain, "crosswalk.html")
    with open(out, "w", encoding="utf-8") as stream:
        stream.write(render(data))
    rows = data["payload"].get("crosswalk") or []
    print("%s: %d category mapping(s) from the pass at shift %s"
          % (data["terrain"], len(rows), data["pass_at"]))
    print("wrote %s" % out)
    if "--open" in argv:
        webbrowser.open("file://" + out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
