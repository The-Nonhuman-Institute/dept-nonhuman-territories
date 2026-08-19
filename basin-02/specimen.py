"""
DNT — the specimen field record. One page per specimen.

    python3 specimen.py            write a record for every classified specimen
    python3 specimen.py i-00042    write one

WHAT THIS ADDS THAT THE COMPENDIUM CANNOT

  The compendium shows one card per specimen: a drawing, its measurements, and
  the Namer's latest word on it. That is a catalogue entry.

  A specimen is observed many times. The Namer writes fresh reasoning at every
  observation, and its account develops — it revises, it compares against
  specimens it has seen since, and occasionally it reclassifies outright. A
  card shows only the last of those. This page shows the whole sequence, in
  order, so the reader can watch an opinion form rather than read its
  conclusion.

  It also holds what the card has no room for: parentage and offspring, the
  links this specimen holds, where it has stood, the Archivist's crosswalk for
  its category, and the substrate it was made from.

WHAT IS NOT HERE, AND WILL NOT BE

  No scale in metres, no sound, no temperature, no photograph. The terrain has
  no length unit, no acoustics, no thermodynamics and no camera. A field record
  that invented those would read better and mean less. Where a section has no
  data it says so.

Python 3.9 compatible. Read-only.
"""

from __future__ import annotations

import json
import os
import sys
import webbrowser
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
import dnt_style
import describe
import codex

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(ROOT, "specimens")


def esc(v: Any) -> str:
    return (str(v if v is not None else "—").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def load() -> Dict[str, Any]:
    memory = json.load(open(config.MEMORY_FILE, encoding="utf-8"))
    recs: List[Dict[str, Any]] = []
    with open(config.SPECIMEN_LOG, encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except ValueError:
                    pass
    ends: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(config.ANOMALY_LOG):
        with open(config.ANOMALY_LOG, encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("record_tier") == "ended":
                    ends[r.get("specimen_id")] = r
    cw = ((memory.get("annotations") or {}).get("linnaean_crosswalk") or {}).get("payload") or {}
    return {"memory": memory, "recs": recs, "ends": ends, "crosswalk": cw,
            "world": memory.get("world") or {}}


def history(data, ident: str) -> List[Dict[str, Any]]:
    return [r for r in data["recs"] if r.get("specimen_id") == ident
            and (r.get("classification") or {}).get("category")]


def entry_for(data, ident: str) -> Dict[str, Any]:
    """Assemble everything the record knows about one specimen."""
    world = data["world"]
    living = world.get("individuals") or {}
    hist = history(data, ident)
    e: Dict[str, Any] = {"id": ident, "history": hist}
    if hist:
        c = hist[-1]["classification"]
        e.update({"category": c.get("category"), "record_tier": hist[-1].get("record_tier"),
                  "first_observed": hist[0].get("shift"), "last_observed": hist[-1].get("shift")})
    being = living.get(ident)
    if being:
        st = being.get("structure") or {}
        e["alive"] = True
        e["shifts_present"] = being.get("age")
        e["descendants"] = being.get("descendants")
        e["measurements"] = {
            "cell": being.get("cell"), "substrate": being.get("substrate"),
            "structure": st, "affinities": being.get("traits") or {},
            "generation": being.get("generation"), "parent_id": being.get("parent_id"),
            "origin": being.get("origin"), "arose_at_shift": being.get("arose_at_shift"),
            "moves": being.get("moves"), "sightings": being.get("sightings"),
            "drawn_from_census": being.get("drawn_from_census", 0.0),
            "drawn_from_residue": being.get("drawn_from_residue", 0.0),
            "drawn_from_links": being.get("drawn_from_links", 0.0),
            "given_to_links": being.get("given_to_links", 0.0),
            "light": being.get("light"),
        }
        e["offspring"] = sorted(i for i, b in living.items() if b.get("parent_id") == ident)
        e["links"] = sorted(k for k, v in (world.get("links") or {}).items()
                            if ident in k.split("|") and v.get("formed_at_shift") is not None)
    else:
        end = data["ends"].get(ident)
        if end:
            e["alive"] = False
            e["ended_at_shift"] = end.get("shift")
            e["shifts_present"] = end.get("shifts_present")
            e["descendants"] = end.get("descendants")
            rem = end.get("remains") or {}
            if rem:
                rem = dict(rem)
                rem["cell"] = end.get("position_cell")
                e["measurements"] = rem
    e["trace"] = (data["memory"].get("traces") or {}).get(ident)
    return e


def crosswalk_for(data, category: Optional[str]) -> Optional[Dict[str, Any]]:
    for row in (data["crosswalk"].get("crosswalk") or []):
        if isinstance(row, dict) and row.get("category") == category:
            return row
    return None


def render(data, e: Dict[str, Any]) -> str:
    m = e.get("measurements") or {}
    st = m.get("structure") or {}
    aff = m.get("affinities") or {}
    cw = crosswalk_for(data, e.get("category"))
    status = ('<span class="status alive">Active</span>' if e.get("alive")
              else '<span class="status ended">Ended shift %s</span>' % esc(e.get("ended_at_shift")))

    def section(num, title, body):
        return ('<section class="rec"><h3><span class="num">%s</span> %s</h3>%s</section>'
                % (num, title, body))

    def rows(pairs):
        return ('<table class="kv">%s</table>'
                % "".join('<tr><td class="k">%s</td><td class="v">%s</td></tr>' % (k, v)
                          for k, v in pairs if v not in (None, "")))

    # 01 native classification
    native = ('<div class="native"><div class="nname">%s</div>'
              '<div class="nsub">the Namer\'s own category · %s tier record</div></div>'
              % (esc(e.get("category")), esc(e.get("record_tier"))))

    # 02 crosswalk
    if cw:
        conf = (cw.get("confidence") or "none").lower()
        cwb = (rows([("Tier", '<b>%s</b>' % esc(cw.get("tier")) if cw.get("tier")
                      else '<i>no clear equivalent</i>'),
                     ("Confidence", '<span class="conf %s">%s</span>' % (conf, conf))])
               + '<p class="note">%s</p>' % esc(cw.get("note"))
               + '<p class="fine">For human legibility only. Carries no authority over the '
                 'native system and does not feed back into it (DNT-CLS-001 §2).</p>')
    else:
        cwb = ('<p class="none">The Archivist has not crosswalked this category yet. It runs '
               'on a cadence; categories coined since its last pass wait for the next one.</p>')

    # 03 observation data
    obs = rows([
        ("First observed", "shift %s" % esc(e.get("first_observed"))),
        ("Last observed", "shift %s" % esc(e.get("last_observed"))),
        ("Observations", str(len(e.get("history") or []))),
        ("Shifts present", esc(e.get("shifts_present"))),
        ("Sightings", esc(m.get("sightings"))),
        ("Arose by", esc(m.get("origin"))),
        ("Substrate", esc(m.get("substrate"))),
        ("Generation", esc(m.get("generation"))),
        ("Times moved", esc(m.get("moves"))),
        ("Status", status),
    ])

    # 04 the Namer's reasoning, in sequence
    seq = []
    for r in (e.get("history") or []):
        c = r["classification"]
        seq.append('<div class="obs"><div class="oh">Shift %s · filed as <code>%s</code>'
                   ' · %s</div>%s%s%s</div>'
                   % (esc(r.get("shift")), esc(c.get("category")), esc(r.get("record_tier")),
                      '<p class="ot">%s</p>' % esc(c.get("reasoning")) if c.get("reasoning") else "",
                      '<p class="op"><span class="lb">how it persists</span>%s</p>'
                      % esc(c.get("persistence_native")) if c.get("persistence_native") else "",
                      '<p class="oc"><span class="lb">compared against</span>%s</p>'
                      % esc(c.get("comparison")) if c.get("comparison") else ""))
    changes = len({(r["classification"] or {}).get("category") for r in (e.get("history") or [])})
    seqhead = ('<p class="lede">%d observations across %s shifts. %s</p>'
               % (len(e.get("history") or []),
                  esc(e.get("last_observed", 0) - (e.get("first_observed") or 0) + 1),
                  "The Namer changed its filing during this sequence."
                  if changes > 1 else "The Namer's filing did not change."))

    # 05 form, drawn from measurements
    if st:
        form = ('<div class="formrow"><div class="plate">%s</div><div class="fm">%s'
                '<p class="prose">%s</p></div></div>'
                % (codex.plate(e, 200),
                   rows([("Reach", "%.2f" % st.get("extent", 0)),
                         ("Links it can hold", "%d" % (1 + int(st.get("junctions", 0)))),
                         ("Carries", "%.2f" % st.get("mass", 0)),
                         ("Upkeep", "%.2f light per shift" % (m.get("upkeep") or 0)),
                         ("Can hold", "%.1f light" % (m.get("capacity") or 0)),
                         ("Lives on", "ground %.2f · remains %.2f · others %.2f"
                          % (aff.get("cover", 0), aff.get("residue", 0), aff.get("links", 0)))]),
                   esc(describe.describe(e))))
    else:
        form = ('<p class="none">Nothing survives of this specimen\'s build. It ended before '
                'the terrain began keeping remains, and its form cannot be recovered.</p>')

    # 06 relations
    rel = rows([
        ("Parent", ('<a href="%s.html">%s</a>' % (esc(m.get("parent_id")), esc(m.get("parent_id"))))
                   if m.get("parent_id") else "arose from the cover layer"),
        ("Offspring", " ".join('<a href="%s.html">%s</a>' % (esc(o), esc(o))
                               for o in (e.get("offspring") or [])) or "none living"),
        ("Links held", str(len(e.get("links") or []))),
    ])

    trace = ('<pre class="trace">%s</pre>' % esc(e["trace"][:1400])) if e.get("trace") else \
            '<p class="none">No substrate trace was drawn for this specimen.</p>'

    body = (section("01", "Native classification", native)
            + section("02", "Linnaean crosswalk", cwb)
            + section("03", "Observation data", obs)
            + section("04", "Form, drawn from measurements", form)
            + section("05", "Relations", rel)
            + section("06", "The Namer's reasoning, in sequence", seqhead + "".join(seq))
            + section("07", "Substrate as recorded", trace))

    return (PAGE.replace("__CSS__", dnt_style.CSS)
                .replace("__BACK__", '<div class="backbar">'
                         '<a href="http://127.0.0.1:8730/hub.html">&larr; Department index</a>'
                         ' &nbsp;·&nbsp; <a href="../codex.html">&larr; Field compendium</a></div>')
                .replace("__MASTHEAD__", dnt_style.masthead(
                    "Specimen Field Record",
                    "One specimen, and everything the terrain has recorded of it.",
                    [("SPECIMEN", esc(e["id"])),
                     ("TERRAIN", esc(data["memory"].get("terrain_name"))),
                     ("CATEGORY", esc(e.get("category"))),
                     ("STATUS", "ACTIVE" if e.get("alive") else "ENDED")]))
                .replace("__BODY__", body)
                .replace("__ID__", esc(e["id"])))


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Specimen __ID__</title><style>__CSS__
.rec{border-top:1px solid var(--rule);padding-top:16px;margin:24px 0 0}
.rec h3{font:600 10px/1.5 var(--mono);letter-spacing:.13em;text-transform:uppercase;
color:var(--grey);margin:0 0 12px;display:flex;gap:10px;align-items:baseline}
.rec h3 .num{color:var(--moss);font-weight:400}
.native .nname{font:400 clamp(26px,3.4vw,40px)/1.1 var(--serif)}
.native .nsub{font:11px var(--mono);color:var(--grey);letter-spacing:.05em;margin-top:6px}
table.kv{border-collapse:collapse;font:12.5px/1.75 var(--mono);
font-variant-numeric:tabular-nums}
table.kv td{padding:1px 0;vertical-align:top}
table.kv td.k{color:var(--grey);padding-right:26px;white-space:nowrap}
table.kv td.v a{color:var(--moss)}
.conf{font:9.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;
border:1px solid}
.conf.partial{color:var(--amber);border-color:var(--amber)}
.conf.none{color:var(--grey);border-color:var(--rule)}
.status{font:9.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;padding:2px 8px;
border:1px solid}
.status.alive{color:var(--moss);border-color:var(--moss)}
.status.ended{color:var(--grey);border-color:var(--rule)}
.note{font-size:13px;color:var(--ink);max-width:74ch;margin:12px 0 0}
.fine{font:11px/1.6 var(--mono);color:var(--grey);margin:8px 0 0;max-width:74ch}
.none{color:var(--grey);font-style:italic;font-size:13px;max-width:70ch}
.formrow{display:grid;grid-template-columns:220px 1fr;gap:26px;align-items:start}
.plate{border:1px solid var(--rule);background:var(--panel);padding:6px}
.plate svg{width:100%;height:auto;display:block}
.plate .core{fill:rgba(59,74,47,.10);stroke:var(--moss);stroke-width:1.2}
.plate .arm{stroke:var(--ink);stroke-width:1.1;opacity:.7}
.plate .node{fill:var(--moss);opacity:.9}
.plate .anchor{stroke:var(--ink);stroke-width:.9;opacity:.45}
.plate .brace{fill:none;stroke:var(--moss);stroke-width:.6;opacity:.5}
.plate .orbit{fill:none;stroke:var(--amber);stroke-width:.9;opacity:.6}
.plate .disc{fill:var(--amber);opacity:.22}
.plate .none{fill:var(--grey);font:11px var(--mono);text-anchor:middle}
.prose{font:15px/1.65 var(--serif);margin:14px 0 0;max-width:66ch}
.obs{border-left:2px solid var(--rule);padding:2px 0 2px 16px;margin:0 0 18px;max-width:80ch}
.oh{font:10.5px var(--mono);color:var(--grey);letter-spacing:.04em;margin-bottom:6px}
.oh code{font-size:10.5px}
.ot{font:13.5px/1.62 var(--sans);margin:0 0 8px}
.op,.oc{font:italic 13px/1.6 var(--serif);color:var(--ink);margin:0 0 8px}
.lb{display:block;font:9px var(--mono);font-style:normal;letter-spacing:.1em;
text-transform:uppercase;color:var(--grey);margin-bottom:3px}
.trace{font:11px/1.5 var(--mono);background:var(--panel);border:1px solid var(--rule);
padding:12px 14px;overflow-x:auto;white-space:pre;max-width:100%}
@media(max-width:720px){.formrow{grid-template-columns:1fr}}
</style></head><body><div class="sheet">
__BACK__
__MASTHEAD__
__BODY__
<footer>Generated from state/specimen_log.jsonl, state/anomaly_log.jsonl and state/memory.json.
Read-only. The Namer's words are reproduced exactly as written; everything else on this page is
a measurement or a rendering of one.</footer>
</div></body></html>"""


def main(argv: List[str]) -> int:
    data = load()
    if not os.path.isdir(OUTDIR):
        os.makedirs(OUTDIR)
    wanted = [a for a in argv[1:] if not a.startswith("--")]
    ids = wanted or sorted({r["specimen_id"] for r in data["recs"]
                            if (r.get("classification") or {}).get("category")})
    written = 0
    for ident in ids:
        e = entry_for(data, ident)
        if not e.get("history"):
            continue
        with open(os.path.join(OUTDIR, "%s.html" % ident), "w", encoding="utf-8") as stream:
            stream.write(render(data, e))
        written += 1
    print("%d specimen record(s) -> %s" % (written, OUTDIR))
    if "--open" in argv and ids:
        webbrowser.open("file://" + os.path.join(OUTDIR, "%s.html" % ids[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
