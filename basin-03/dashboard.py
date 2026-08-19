"""
BASIN-01 — local dashboard generator.

    python3 dashboard.py            write dashboard.html
    python3 dashboard.py --open     write it and open it in the browser

README.md Section 7 allows "a simple local dashboard (reads the same JSON
files, no live socket needed)" as a Phase 2 addition. This is that.

It reads the terrain's own state files and writes a single self-contained HTML
page — no server, no network, no external fonts or scripts. The research record
never leaves the machine. Re-run it after any shift to refresh.

It is a VIEW. It reads state and writes one file outside the terrain's storage;
it never writes to state/ or shifts/, and it makes no model call, so it costs
nothing and cannot alter the record it displays.

Python 3.9 compatible.
"""

from __future__ import annotations

import html
import json
import os
import sys
import webbrowser
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config

OUTPUT = os.path.join(config.TERRAIN_ROOT, "dashboard.html")

# Categorical slots 1-4 from the validated reference palette, light / dark.
# Assigned in fixed order and never cycled.
SERIES = ("--series-1", "--series-2", "--series-3", "--series-4")


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as stream:
            return json.load(stream)
    except (IOError, ValueError):
        return default


def read_lines(path: str) -> List[Dict[str, Any]]:
    records = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except ValueError:
                    pass
    return records


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def stat(label: str, value: Any, note: str = "") -> str:
    return (
        '<div class="stat"><div class="stat-label">%s</div>'
        '<div class="stat-value">%s</div>'
        '<div class="stat-note">%s</div></div>'
        % (esc(label), esc(value), esc(note))
    )


def meter(label: str, value: float, maximum: float, display: str, slot: str) -> str:
    """A labelled bar. The value is always written out, never colour alone."""
    width = 0.0 if not maximum else max(0.0, min(100.0, (value / maximum) * 100.0))
    return (
        '<div class="meter-row">'
        '<div class="meter-label">%s</div>'
        '<div class="meter-track"><div class="meter-fill" style="width:%.2f%%;'
        'background:var(%s)"></div></div>'
        '<div class="meter-value">%s</div>'
        "</div>" % (esc(label), width, slot, esc(display))
    )


def taxonomy_tree(node: Any, depth: int = 0) -> str:
    """Render whatever shape the Namer authored, without assuming one."""
    if isinstance(node, dict):
        name = node.get("category") or node.get("subcategory")
        if name:
            parts = ['<div class="cat" style="--depth:%d">' % depth]
            parts.append('<div class="cat-name">%s</div>' % esc(name))
            if node.get("description"):
                parts.append('<div class="cat-desc">%s</div>' % esc(node["description"]))
            bits = []
            if node.get("members"):
                bits.append("%d member(s)" % len(node["members"]))
            if node.get("complexity_range"):
                bits.append("complexity %s–%s" % tuple(node["complexity_range"][:2]))
            if node.get("substrate"):
                bits.append(esc(node["substrate"]))
            if bits:
                parts.append('<div class="cat-meta">%s</div>' % " · ".join(bits))
            if node.get("members"):
                parts.append(
                    '<div class="cat-members">%s</div>'
                    % " ".join('<span class="chip">%s</span>' % esc(m)
                               for m in node["members"])
                )
            for key in ("subcategories", "children"):
                for child in node.get(key, []) or []:
                    parts.append(taxonomy_tree(child, depth + 1))
            parts.append("</div>")
            return "".join(parts)
        return "".join(
            '<div class="cat" style="--depth:%d"><div class="cat-name">%s</div>%s</div>'
            % (depth, esc(key), taxonomy_tree(value, depth + 1))
            for key, value in node.items()
        )
    if isinstance(node, list):
        return "".join(taxonomy_tree(item, depth) for item in node)
    return '<div class="cat-desc">%s</div>' % esc(node)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


def build() -> str:
    memory = read_json(config.MEMORY_FILE, {})
    taxonomy = read_json(config.TAXONOMY_FILE, {})
    specimens = read_lines(config.SPECIMEN_LOG)
    anomalies = read_lines(config.ANOMALY_LOG)
    shifts = read_lines(config.SHIFT_LOG)

    native = taxonomy.get("native", {})
    stats = memory.get("category_stats", {}) or {}
    structure = memory.get("taxonomy_structure", {}) or {}
    annotations = memory.get("annotations", {}) or {}
    spend = float(memory.get("cumulative_cost_usd", 0.0))

    canonical = [s for s in shifts if s.get("phase") == "claude"]
    flagged = [a for a in anomalies if a.get("record_tier") == "anomalous"]
    unresolved = [a for a in anomalies if a.get("record_tier") == "unresolved"]
    promoted = [s for s in specimens if s.get("promotion_triggers")]

    # --- falsification checkpoint, computed the same way /checkpoint does ---
    criteria = [
        ("Groupings / relational structure",
         bool(structure.get("diverged_from_flat_list")),
         "depth %s, %s nodes" % (structure.get("max_depth"), structure.get("total_nodes"))),
        ("Anomalies flagged", bool(flagged), "%d specimen(s)" % len(flagged)),
        ("Aggregate → individual promotion", bool(promoted), "%d specimen(s)" % len(promoted)),
    ]
    null_result = not any(present for _, present, _ in criteria)
    due = len(canonical) >= 15

    out: List[str] = []
    add = out.append

    add('<div class="wrap">')
    add('<header><h1>BASIN-01</h1>'
        '<p class="sub">Department of Nonhuman Territories · terrain %s · '
        'physics DNT-PHY-001 v1.1</p></header>' % esc(config.TERRAIN_ID))

    # -- stat row ----------------------------------------------------------
    add('<section class="stats">')
    add(stat("Canonical shifts", len(canonical), "checkpoint at 15"))
    add(stat("Specimen records", len(specimens),
             "%d individual · %d aggregate"
             % (sum(1 for s in specimens if s.get("record_tier") == "individual"),
                sum(1 for s in specimens if s.get("record_tier") == "aggregate"))))
    add(stat("Categories coined", len(stats), "by the Namer, unprompted"))
    add(stat("Anomalies", len(flagged), "%d unresolved (harness)" % len(unresolved)))
    add(stat("Spent", "$%.4f" % spend, "of $%.2f (%.1f%%)"
             % (config.TOTAL_USD_CEILING, spend / config.TOTAL_USD_CEILING * 100)))
    add("</section>")

    # -- checkpoint --------------------------------------------------------
    add('<section class="panel %s">' % ("verdict-null" if null_result else "verdict-structure"))
    add("<h2>Falsification checkpoint <span class=\"tag\">physics.md §11</span></h2>")
    add('<p class="lede">%s</p>'
        % ("Checkpoint is due. A null result requires all three to be absent."
           if due else
           "Not yet due — %d of 15 canonical shifts. Shown for reference."
           % len(canonical)))
    add('<table class="grid"><thead><tr><th>Criterion</th><th>State</th>'
        "<th>Evidence</th></tr></thead><tbody>")
    for label, present, evidence in criteria:
        add('<tr><td>%s</td><td><span class="pill %s">%s</span></td><td>%s</td></tr>'
            % (esc(label), "on" if present else "off",
               "present" if present else "absent", esc(evidence)))
    add("</tbody></table>")
    add('<p class="verdict">%s</p>'
        % ("NULL RESULT for this seed configuration"
           if null_result else "NOT a null result"))
    add("</section>")

    # -- the Namer's system ------------------------------------------------
    add('<section class="panel"><h2>The Namer\'s own system '
        '<span class="tag">taxonomy.json</span></h2>')
    add('<p class="lede">Authored entirely by the Namer. It was issued no template, '
        "no ranks and no vocabulary — only the rule that for any two specimens it "
        "must be able to say whether they are more or less alike, and why.</p>")
    add('<div class="tree">%s</div>' % (taxonomy_tree(native) or "<em>empty</em>"))
    add("</section>")

    # -- category sizes ----------------------------------------------------
    if stats:
        biggest = max(int(v.get("count", 0)) for v in stats.values()) or 1
        add('<section class="panel"><h2>Category membership</h2><div class="meters">')
        for index, (label, entry) in enumerate(
            sorted(stats.items(), key=lambda kv: -int(kv[1].get("count", 0)))
        ):
            add(meter(label, int(entry.get("count", 0)), biggest,
                      "%d · mean complexity %.1f"
                      % (int(entry.get("count", 0)), float(entry.get("mean_complexity", 0))),
                      SERIES[index % len(SERIES)]))
        add("</div></section>")

    # -- anomalies ---------------------------------------------------------
    add('<section class="panel"><h2>Anomalies <span class="tag">the Namer declined '
        "to classify these</span></h2>")
    add('<p class="lede">Flagging a specimen anomalous is a valid and expected '
        "outcome (DNT-CLS-001 §5). Nothing here was force-fitted. Harness failures "
        "are logged separately as <em>unresolved</em> and are never counted as "
        "anomalies.</p>")
    for record in flagged:
        reasoning = (record.get("classification") or {}).get("reasoning", "")
        add('<details class="item"><summary><code>%s</code> %s '
            '<span class="muted">complexity %s</span></summary>'
            '<blockquote>%s</blockquote><p class="why">%s</p></details>'
            % (esc(record.get("specimen_id")), esc(record.get("source_role")),
               esc(record.get("complexity")), esc(record.get("content")), esc(reasoning)))
    if unresolved:
        add('<h3>Unresolved — harness failures, not taxonomy findings</h3><ul>')
        for record in unresolved:
            add("<li><code>%s</code> — %s</li>"
                % (esc(record.get("specimen_id")), esc(record.get("mechanism_failure"))))
        add("</ul>")
    add("</section>")

    # -- specimens ---------------------------------------------------------
    add('<section class="panel"><h2>Specimens <span class="tag">%d records</span></h2>'
        % len(specimens))
    add('<p class="lede">The Namer\'s reasoning is logged in full and is the primary '
        "research data (README §5). Click a specimen to read it.</p>")
    for record in reversed(specimens):
        classification = record.get("classification") or {}
        triggers = ", ".join(record.get("promotion_triggers") or []) or "—"
        add('<details class="item"><summary><code>%s</code> '
            '<span class="badge">%s</span> %s '
            '<span class="muted">%s · complexity %s</span></summary>'
            '<blockquote>%s</blockquote>'
            '<dl><dt>Filed as</dt><dd>%s (%s)</dd>'
            "<dt>Comparison</dt><dd>%s</dd>"
            "<dt>Reasoning</dt><dd>%s</dd>"
            "<dt>Tier</dt><dd>%s — triggers: %s</dd></dl></details>"
            % (esc(record.get("specimen_id")), esc(record.get("record_tier")),
               esc(classification.get("category")), esc(record.get("source_role")),
               esc(record.get("complexity")), esc(record.get("content")),
               esc(classification.get("category")), esc(classification.get("decision")),
               esc(classification.get("comparison")), esc(classification.get("reasoning")),
               esc(record.get("record_tier")), esc(triggers)))
    add("</section>")

    # -- archivist ---------------------------------------------------------
    archivist = (annotations.get("linnaean_crosswalk") or {})
    payload = archivist.get("payload") or {}
    if payload:
        add('<section class="panel"><h2>Archivist <span class="tag">pass at shift %s'
            "</span></h2>" % esc(archivist.get("shift")))
        add('<p class="lede">The crosswalk is for human legibility only. It carries no '
            "authority over the native system and does not feed back into it "
            "(DNT-CLS-001 §2). “No reliable equivalent” is a valid answer.</p>")
        rows = payload.get("crosswalk") or []
        if rows:
            add('<table class="grid"><thead><tr><th>Category</th><th>Tier</th>'
                "<th>Confidence</th><th>Note</th></tr></thead><tbody>")
            for row in rows:
                add("<tr><td><code>%s</code></td><td>%s</td>"
                    '<td><span class="pill %s">%s</span></td><td>%s</td></tr>'
                    % (esc(row.get("category")), esc(row.get("tier") or "—"),
                       "off" if row.get("confidence") == "none" else "on",
                       esc(row.get("confidence")), esc(row.get("note"))))
            add("</tbody></table>")
        if payload.get("consistency_notes"):
            add("<h3>Consistency notes</h3><blockquote>%s</blockquote>"
                % esc(payload["consistency_notes"]))
        drift = payload.get("drift") or {}
        add("<h3>Drift</h3><p>Detected: <strong>%s</strong></p>" % esc(drift.get("drift_detected")))
        if drift.get("coined_then_dropped_from_system"):
            add("<p>Filed under, but no longer present in its own system: %s</p>"
                % ", ".join("<code>%s</code>" % esc(c)
                            for c in drift["coined_then_dropped_from_system"]))
        add("</section>")

    # -- cartographer ------------------------------------------------------
    carto = (annotations.get("relational_record") or {})
    cpayload = carto.get("payload") or {}
    if cpayload:
        add('<section class="panel"><h2>Cartographer <span class="tag">pass at shift %s · '
            "no model call</span></h2>" % esc(carto.get("shift")))
        add('<p class="lede">Positional and relational only, computed from the record. '
            "It does not classify or interpret (physics §4.5).</p>")
        zones = cpayload.get("zones") or {}
        total = cpayload.get("specimens_placed") or 1
        add('<div class="meters">')
        for index, (name, zone) in enumerate(zones.items()):
            if not zone.get("specimen_count"):
                continue
            add(meter(name.replace("_", " "), zone["specimen_count"], total,
                      "%d specimens · mean complexity %s"
                      % (zone["specimen_count"], zone.get("mean_complexity")),
                      SERIES[index % len(SERIES)]))
        add("</div>")
        co = cpayload.get("category_co_occurrence_within_a_shift") or {}
        if co:
            add("<h3>Categories appearing in the same shift</h3>"
                '<table class="grid"><thead><tr><th>Pair</th><th>Shifts</th></tr>'
                "</thead><tbody>")
            for pair, count in sorted(co.items(), key=lambda kv: -kv[1])[:12]:
                add("<tr><td>%s</td><td>%d</td></tr>" % (esc(pair), count))
            add("</tbody></table>")
        add("</section>")

    # -- shift log ---------------------------------------------------------
    add('<section class="panel"><h2>Shift log <span class="tag">DNT-SLP-001</span></h2>')
    if shifts:
        peak = max(float(s.get("estimated_cost_usd", 0)) for s in shifts) or 1.0
        add('<table class="grid"><thead><tr><th>Shift</th><th>Phase</th><th>Flow</th>'
            "<th>Classified</th><th>Anom.</th><th>Cost</th><th>Cumulative</th>"
            "</tr></thead><tbody>")
        for record in reversed(shifts):
            cost = float(record.get("estimated_cost_usd", 0))
            width = (cost / peak) * 100
            add("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                '<td><div class="inline-bar"><span style="width:%.1f%%"></span></div>'
                "$%.4f</td><td>$%.4f</td></tr>"
                % (esc(record.get("shift_id")), esc(record.get("phase")),
                   esc(record.get("resource_flow")), esc(record.get("classified")),
                   esc(record.get("anomalies_logged")), width, cost,
                   float(record.get("cumulative_cost_usd", 0))))
        add("</tbody></table>")
    add("</section>")

    # -- terrain events ----------------------------------------------------
    events = memory.get("terrain_events") or []
    if events:
        add('<section class="panel"><h2>Terrain events <span class="tag">non-agentive'
            "</span></h2>")
        for event in events:
            add('<details class="item"><summary><code>%s</code> shift %s</summary>'
                "<p>%s</p></details>"
                % (esc(event.get("kind")), esc(event.get("shift")), esc(event.get("detail"))))
        add("</section>")

    add('<footer><p>Generated from the terrain\'s own state files. This page is a '
        "view: it never writes to state, and makes no model call. A terrain's "
        "taxonomy is that terrain's account of itself, not a verified natural "
        "history (DNT-CLS-001 §7).</p>"
        "<p>Department of Nonhuman Territories — The Nonhuman Institute</p></footer>")
    add("</div>")
    return "\n".join(out)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BASIN-01</title>
<style>
:root {
  color-scheme: light;
  --surface-0:#f4f3ef; --surface-1:#fcfcfb; --surface-2:#eeede8;
  --border:#dbdad3; --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#78766f;
  --series-1:#2a78d6; --series-2:#eb6834; --series-3:#1baf7a; --series-4:#eda100;
  --good:#1baf7a; --off:#78766f;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface-0:#131312; --surface-1:#1a1a19; --surface-2:#232322;
    --border:#333330; --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#8d8b82;
    --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70; --series-4:#c98500;
    --good:#199e70; --off:#8d8b82;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-0:#131312; --surface-1:#1a1a19; --surface-2:#232322;
  --border:#333330; --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#8d8b82;
  --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70; --series-4:#c98500;
  --good:#199e70; --off:#8d8b82;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--surface-0); color:var(--text-primary);
  font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
.wrap { max-width:1080px; margin:0 auto; padding:32px 20px 64px; }
header h1 { font-size:28px; margin:0 0 4px; letter-spacing:-0.01em; }
.sub { color:var(--muted); margin:0 0 28px; font-size:13px; }
h2 { font-size:17px; margin:0 0 4px; display:flex; align-items:baseline;
  gap:10px; flex-wrap:wrap; }
h3 { font-size:14px; margin:22px 0 8px; color:var(--text-secondary); }
.tag { font-size:11px; font-weight:400; color:var(--muted); }
.lede { color:var(--text-secondary); font-size:13.5px; margin:6px 0 16px; }
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:12px; margin-bottom:22px; }
.stat { background:var(--surface-1); border:1px solid var(--border);
  border-radius:10px; padding:14px 16px; }
.stat-label { font-size:11px; text-transform:uppercase; letter-spacing:.06em;
  color:var(--muted); }
.stat-value { font-size:26px; font-weight:600; margin:4px 0 2px;
  font-variant-numeric:tabular-nums; }
.stat-note { font-size:12px; color:var(--text-secondary); }
.panel { background:var(--surface-1); border:1px solid var(--border);
  border-radius:12px; padding:20px 22px; margin-bottom:18px; }
.verdict-structure { border-left:3px solid var(--series-3); }
.verdict-null { border-left:3px solid var(--series-2); }
.verdict { font-size:16px; font-weight:600; margin:14px 0 0; }
table.grid { width:100%; border-collapse:collapse; font-size:13px; display:block;
  overflow-x:auto; }
table.grid th { text-align:left; font-weight:600; color:var(--text-secondary);
  border-bottom:1px solid var(--border); padding:8px 10px; white-space:nowrap; }
table.grid td { border-bottom:1px solid var(--border); padding:8px 10px;
  vertical-align:top; }
table.grid tr:last-child td { border-bottom:0; }
.pill { display:inline-block; padding:1px 8px; border-radius:999px; font-size:11px;
  border:1px solid var(--border); }
.pill.on { color:var(--good); border-color:var(--good); }
.pill.off { color:var(--off); }
.badge { display:inline-block; padding:1px 7px; border-radius:5px; font-size:11px;
  background:var(--surface-2); color:var(--text-secondary); }
.meters { display:flex; flex-direction:column; gap:8px; }
.meter-row { display:grid; grid-template-columns:minmax(120px,220px) 1fr auto;
  gap:12px; align-items:center; font-size:13px; }
.meter-label { color:var(--text-secondary); overflow-wrap:anywhere; }
.meter-track { background:var(--surface-2); border-radius:4px; height:10px; }
.meter-fill { height:10px; border-radius:0 4px 4px 0; }
.meter-value { color:var(--muted); font-size:12px; white-space:nowrap;
  font-variant-numeric:tabular-nums; }
.inline-bar { display:inline-block; width:60px; height:6px; background:var(--surface-2);
  border-radius:3px; margin-right:8px; vertical-align:middle; }
.inline-bar span { display:block; height:6px; border-radius:0 3px 3px 0;
  background:var(--series-1); }
.tree { display:flex; flex-direction:column; gap:10px; }
.cat { margin-left:calc(var(--depth,0) * 20px);
  border-left:2px solid var(--border); padding:6px 0 6px 14px; }
.cat-name { font-weight:600; font-size:14px; }
.cat-desc { color:var(--text-secondary); font-size:13px; margin-top:3px; }
.cat-meta { color:var(--muted); font-size:12px; margin-top:4px; }
.cat-members { margin-top:6px; display:flex; flex-wrap:wrap; gap:4px; }
.chip { font:11px ui-monospace,SFMono-Regular,Menlo,monospace;
  background:var(--surface-2); border-radius:4px; padding:1px 5px; color:var(--muted); }
details.item { border-top:1px solid var(--border); padding:9px 0; }
details.item summary { cursor:pointer; font-size:13.5px; display:flex; gap:8px;
  align-items:baseline; flex-wrap:wrap; }
blockquote { margin:10px 0; padding:10px 14px; background:var(--surface-2);
  border-radius:8px; font-size:13.5px; white-space:pre-wrap; overflow-wrap:anywhere; }
dl { margin:8px 0 0; font-size:13px; }
dt { font-weight:600; color:var(--text-secondary); margin-top:8px; font-size:12px;
  text-transform:uppercase; letter-spacing:.04em; }
dd { margin:2px 0 0; }
code { font:12px ui-monospace,SFMono-Regular,Menlo,monospace; }
.muted { color:var(--muted); font-size:12px; }
ul { font-size:13px; }
footer { color:var(--muted); font-size:12px; margin-top:28px;
  border-top:1px solid var(--border); padding-top:16px; }
</style></head><body>
__BODY__
</body></html>
"""


def main(argv: List[str]) -> int:
    page = PAGE.replace("__BODY__", build())
    with open(OUTPUT, "w", encoding="utf-8") as stream:
        stream.write(page)
    print("wrote %s (%.0f KB)" % (OUTPUT, len(page) / 1024.0))
    if "--open" in argv:
        webbrowser.open("file://" + OUTPUT)
        print("opened in your browser")
    else:
        print("open it with:  open %s" % OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
