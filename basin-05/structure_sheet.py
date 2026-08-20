# SPDX-FileCopyrightText: 2026 U3 Labs, LLC
# SPDX-License-Identifier: Apache-2.0
"""
DNT — classification structure, hypotheses under review.

    python3 structure_sheet.py [--open]

Four ways of arranging the same observations, drawn from the record:

  A  HIERARCHY   the Namer's own nesting, as it authored it
  B  NETWORK     specimens joined by links, weighted by light actually moved
  C  SPECTRUM    position by degree — persistence against connectivity
  D  SEQUENCE    ordered by first emergence, with descent drawn through time

WHY FOUR

  DNT-CLS-001 Section 1 is explicit that Linnaean taxonomy is one historical
  solution shaped by human morphological perception, and is not assumed to be
  the structure a nonhuman classifier would reach for. A hierarchy is therefore
  a hypothesis, not a given — so it is shown as one arrangement among several
  rather than as the arrangement.

  None of these is adopted. Nothing here feeds back into the native system, and
  the Namer never sees any of it. They are ways of looking, offered together so
  that no single one passes for the truth of the thing.

EVERYTHING IS MEASURED

  Node positions in B and C are computed from recorded values, not arranged by
  eye. Edge weights are light that actually moved. Order in D is the shift each
  specimen first appeared. No layout is hand-adjusted to look better.

Python 3.9 compatible. Read-only; writes one file.
"""

from __future__ import annotations

import json
import math
import os
import sys
import webbrowser
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
import config
import dnt_chrome

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "structure.html")


OBSERVATION_SET = 14      # specimens presented on one sheet


def observation_set(data) -> List[Dict[str, Any]]:
    """The specimens this sheet presents, chosen mechanically.

    A field document shows an OBSERVATION SET, not a census — rendering all
    1,400 living specimens produced panels nobody could read.

    The set is now chosen by DESCENT: the largest living lineages, taken whole,
    until the sheet is full. That is what makes a tree panel possible at all —
    a set picked by tenure alone is a bag of unrelated specimens with no
    parent-child edges between them, which is why the tree rendered as two
    floating nodes.

    The rule is fixed so it cannot become a way of showing the interesting
    ones: lineages ordered by how many living members they have, ties broken on
    the root's identifier, taken whole and in order until the sheet is full.
    The full population is printed beside the sample on every panel.
    """
    world = data["world"]
    living = world.get("individuals") or {}
    kids: Dict[str, List[str]] = {}
    for i, b in living.items():
        p = b.get("parent_id")
        if p in living:
            kids.setdefault(p, []).append(i)
    roots = [i for i, b in living.items()
             if not b.get("parent_id") or b.get("parent_id") not in living]

    def line(root: str) -> List[str]:
        out, stack, seen = [], [root], set()
        while stack:
            n = stack.pop(0)
            if n in seen:
                continue
            seen.add(n)
            out.append(n)
            stack.extend(sorted(kids.get(n, [])))
        return out

    lines = sorted(((len(line(r)), r) for r in roots), key=lambda t: (-t[0], t[1]))
    chosen_ids: List[str] = []
    for count, root in lines:
        if count < 2 and chosen_ids:
            break
        members = line(root)
        if len(chosen_ids) + len(members) > OBSERVATION_SET and chosen_ids:
            continue
        chosen_ids.extend(members)
        if len(chosen_ids) >= OBSERVATION_SET:
            break
    if not chosen_ids:
        chosen_ids = sorted(living, key=lambda i: (-int(living[i].get("age", 0)), i))[:OBSERVATION_SET]

    links = world.get("links") or {}
    held: Dict[str, int] = {}
    for k, v in links.items():
        if v.get("formed_at_shift") is None:
            continue
        for p in k.split("|"):
            held[p] = held.get(p, 0) + 1

    chosen = [living[i] for i in chosen_ids[:OBSERVATION_SET]]
    # Label by position in the lineage, the way a field sheet numbers a family:
    # a root is A, B, C...; its children A-1, A-2; their children A-1-1.
    label: Dict[str, str] = {}
    letters = "ABCDEFGHIJKLMN"
    r_i = 0
    for count, root in lines:
        if root not in chosen_ids:
            continue
        if r_i >= len(letters):
            break
        label[root] = letters[r_i]
        r_i += 1
        stack = [root]
        while stack:
            n = stack.pop(0)
            for j, c in enumerate(sorted(kids.get(n, []))):
                if c in chosen_ids:
                    label[c] = "%s-%d" % (label[n], j + 1)
                    stack.append(c)
    for b in chosen:
        b["_label"] = label.get(b["id"], b["id"][-4:])
        b["_links"] = held.get(b["id"], 0)
        b["_kids"] = [c for c in kids.get(b["id"], []) if c in chosen_ids]
    data["_kids"] = kids
    return chosen


def portrait(being: Dict[str, Any], r: float = 15.0) -> str:
    """A small drawing of one specimen, from its own measurements.

    The same values the compendium plate uses: core from what it carries,
    spokes from its links, spoke length from its reach, a ring per offspring.
    """
    st = being.get("structure") or {}
    if not st:
        return '<circle r="%.1f" class="pbg"/><circle r="2" class="pnode"/>' % r
    mass = max(0.25, float(st.get("mass", 1)))
    reach = float(st.get("extent", 1))
    joints = 1 + int(st.get("junctions", 0) or 0)
    kids = int(being.get("descendants", 0) or 0)
    core = r * min(0.72, 0.26 + mass * 0.20)
    out = ['<circle r="%.1f" class="pbg"/>' % r]
    for i in range(joints):
        a = (i / float(joints)) * 2 * math.pi - math.pi / 2
        L = core + (r - core) * min(1.0, 0.35 + reach * 0.38)
        out.append('<line x1="0" y1="0" x2="%.1f" y2="%.1f" class="pspoke"/>'
                   % (math.cos(a) * L, math.sin(a) * L))
        out.append('<circle cx="%.1f" cy="%.1f" r="1.3" class="pnode"/>'
                   % (math.cos(a) * L, math.sin(a) * L))
    for k in range(min(2, kids)):
        out.append('<ellipse rx="%.1f" ry="%.1f" class="pring"/>'
                   % (core * (1.45 + k * 0.4), core * (0.5 + k * 0.16)))
    sides = 6 if mass < 1.2 else 8
    pts = " ".join("%.1f,%.1f" % (math.cos(2 * math.pi * j / sides - math.pi / 2) * core,
                                  math.sin(2 * math.pi * j / sides - math.pi / 2) * core)
                   for j in range(sides))
    out.append('<polygon points="%s" class="pcore"/>' % pts)
    return "".join(out)


def esc(v: Any) -> str:
    return (str(v if v is not None else "—").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def load() -> Dict[str, Any]:
    memory = json.load(open(config.MEMORY_FILE, encoding="utf-8"))
    taxonomy = json.load(open(config.TAXONOMY_FILE, encoding="utf-8")).get("native") or {}
    recs = []
    with open(config.SPECIMEN_LOG, encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except ValueError:
                    pass
    named: Dict[str, Dict[str, Any]] = {}
    for r in recs:
        c = r.get("classification") or {}
        if c.get("category"):
            named[r["specimen_id"]] = {"category": c["category"], "shift": r.get("shift")}
    return {"memory": memory, "taxonomy": taxonomy, "named": named,
            "world": memory.get("world") or {}}


# --- A. hierarchy ----------------------------------------------------------
def tree_rows(node: Any, depth: int = 0, out: Optional[List] = None,
              known: Optional[set] = None) -> List[Tuple[int, str, Any]]:
    """Walk the Namer's system exactly as authored, whatever shape it has."""
    if out is None:
        out = []
    if isinstance(node, dict):
        for k, v in node.items():
            # The Namer writes prose fields alongside its categories. Those are
            # how it documents a category, not categories themselves, and
            # rendering them as nodes made its system look four times deeper
            # than it is. Anything whose value is prose or a plain list is
            # documentation; only keys that contain further structure, or that
            # the counters recognise as a filed category, are nodes.
            if k in ("description", "defining_traits", "defining_condition", "exemplars",
                     "members", "member_count", "persistence_mode", "note", "notes",
                     "status", "definition", "examples", "key_traits", "criteria",
                     "observed_states_note", "rationale"):
                continue
            nests = isinstance(v, dict) and any(
                isinstance(vv, (dict, list)) for vv in v.values())
            if not (nests or (known and str(k) in known)):
                continue                      # documentation, not a category
            out.append((depth, str(k), v))
            tree_rows(v, depth + 1, out, known)
    elif isinstance(node, list):
        for e in node:
            if isinstance(e, dict) and e.get("category"):
                out.append((depth, str(e["category"]), e))
                tree_rows({k: v for k, v in e.items() if k != "category"}, depth + 1, out, known)
    return out


def panel_hierarchy(data, w=470, h=390) -> str:
    """Descent, drawn as a tree: a root, its offspring, and theirs.

    This panel used to tree the Namer's CATEGORIES. With two categories
    authored, it rendered as two floating nodes in an empty box — and the
    portraits were all identical because a single hardcoded build was passed
    for every one of them.

    It now trees the thing the record is actually deep in: parentage. Every
    node is that specimen's own portrait, and every edge is a recorded
    parent_id, not an inferred relation.
    """
    chosen = data["_set"]
    if not chosen:
        return ('<p class="empty">Nothing living to tree.</p>', [], "")
    by_id = {b["id"]: b for b in chosen}
    gen = {}
    for b in chosen:
        d = b["_label"].count("-")
        gen.setdefault(d, []).append(b)
    depth = max(gen) + 1
    rows = sorted(gen)
    r = 22.0
    top, gap = 38.0, (h - 104.0) / max(1, len(rows) - 1 or 1)
    pos = {}
    for ri, d in enumerate(rows):
        band = sorted(gen[d], key=lambda b: b["_label"])
        for i, b in enumerate(band):
            x = (w / (len(band) + 1.0)) * (i + 1)
            y = top + ri * gap
            pos[b["id"]] = (x, y)

    parts = []
    # elbow connectors first, so nodes sit on top of them
    for b in chosen:
        p_id = b.get("parent_id")
        if p_id in pos and b["id"] in pos:
            (px, py), (cx, cy) = pos[p_id], pos[b["id"]]
            # The elbow leaves below the parent's LABEL BLOCK, not below the
            # node — it was previously drawn from the node edge and ran
            # straight through the label and the shift count beneath it.
            leave = py + r + 30
            mid = leave + (cy - r - leave) / 2.0
            parts.append('<path d="M%.1f %.1f V%.1f H%.1f V%.1f" class="tedge"/>'
                         % (px, leave, mid, cx, cy - r - 4))
    for b in chosen:
        x, y = pos[b["id"]]
        parts.append('<g transform="translate(%.1f,%.1f)">%s</g>' % (x, y, portrait(b, r)))
        parts.append('<text x="%.1f" y="%.1f" class="tl">%s</text>' % (x, y + r + 13, esc(b["_label"])))
        # Eight nodes across 470px leaves 58px a label, and "7 shift(s)" is
        # wider than that — the counts ran into each other. A crowded row keeps
        # the figure and drops the word.
        crowded = len(gen[b["_label"].count("-")]) > 5
        parts.append('<text x="%.1f" y="%.1f" class="tn">%d%s</text>'
                     % (x, y + r + 24, int(b.get("age", 0)),
                        "" if crowded else " shift(s)"))
    return ('<svg viewBox="0 0 %d %d" class="tree" role="img" aria-label="descent">%s</svg>'
            % (w, h, "".join(parts)),
            [('<i class="lline"></i>', 'parent &rarr; offspring (recorded parentage)'),
             ('<i class="lportrait"></i>', 'each node drawn from its own measurements')],
            'Descent, not classification. Every edge is a recorded parent_id; nothing here '
            'is inferred. Roots are lettered A, B, C in order of how many living members '
            'their line has — %d lines across %d generations on this sheet.'
            % (len(gen.get(0, [])), depth))


# --- B. network ------------------------------------------------------------
def panel_network(data, w=470, h=400) -> str:
    """The observation set, joined by links, drawn where each specimen stands."""
    import life
    world = data["world"]
    links = world.get("links") or {}
    chosen = {b["id"]: b for b in data["_set"]}
    formed = [(k, v) for k, v in links.items()
              if v.get("formed_at_shift") is not None
              and all(p in chosen for p in k.split("|"))]
    try:
        life.load_landscape(config.LANDSCAPE_FILE)
        saved = data["memory"].get("landscape")
        if saved and saved.get("ground"):
            life.FIELD_WIDTH = int(saved["width"]); life.FIELD_DEPTH = int(saved["height"])
    except Exception:
        pass
    FW = getattr(life, "FIELD_WIDTH", 1) or 1
    FD = getattr(life, "FIELD_DEPTH", 1) or 1
    # Positions are the specimens' real relative arrangement, normalised to
    # THEIR OWN bounding box rather than the whole terrain. Placing a set that
    # occupies 30 cells of a 132x72 field against the full extent squeezed
    # every node into one corner and stacked the labels on top of each other —
    # geographic truth rendered illegibly. Relative arrangement is preserved;
    # the scale is the set's own.
    cells = [(int(b.get("cell", 0)) % FW, int(b.get("cell", 0)) // FW)
             for b in chosen.values()]
    xs = [c[0] for c in cells] or [0]
    ys = [c[1] for c in cells] or [0]
    spanx = max(1, max(xs) - min(xs))
    spany = max(1, max(ys) - min(ys))
    pos = {}
    for i, b in chosen.items():
        cx = int(b.get("cell", 0)) % FW
        cy = int(b.get("cell", 0)) // FW
        pos[i] = (48 + (cx - min(xs)) / float(spanx) * (w - 106),
                  46 + (cy - min(ys)) / float(spany) * (h - 132))
    parts = ['<rect x="30" y="24" width="%d" height="%d" class="frame"/>' % (w - 60, h - 84),
             '<defs><marker id="ah" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" '
             'markerHeight="5" orient="auto"><path d="M0 0 L8 4 L0 8 z" class="ahd"/>'
             '</marker></defs>']
    mx = max([float(v.get("light_moved", 0)) for _, v in formed] or [1]) or 1
    for k, v in sorted(formed, key=lambda kv: float(kv[1].get("light_moved", 0))):
        a, b = k.split("|")
        lw = float(v.get("light_moved", 0)) / mx
        cls = "strong" if lw > 0.6 else ("moderate" if lw > 0.25 else "weak")
        parts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="e %s"/>'
                     % (pos[a][0], pos[a][1], pos[b][0], pos[b][1], cls))
    # Each label takes the first of four candidate positions that does not
    # collide with one already placed. Alternating above/below was not enough:
    # where three specimens sit close together, two labels still landed on the
    # same spot and rendered as overlapping text.
    placed = sorted(pos.items(), key=lambda kv: (kv[1][1], kv[1][0]))
    taken: List[Tuple[float, float]] = []
    for i, (x, y) in placed:
        b = chosen[i]
        parts.append('<g transform="translate(%.1f,%.1f)">%s</g>' % (x, y, portrait(b, 17)))
        for dx, dy in ((0, 32), (0, -24), (34, 5), (-34, 5), (0, 44), (0, -36)):
            lx, ly = x + dx, y + dy
            if all(abs(lx - tx) > 32 or abs(ly - ty) > 12 for tx, ty in taken):
                break
        taken.append((lx, ly))
        parts.append('<text x="%.1f" y="%.1f" class="nlbl">%s</text>'
                     % (lx, ly, esc(b["_label"])))
    return ('<svg viewBox="0 0 %d %d" class="net" role="img" aria-label="relational web">%s</svg>'
            % (w, h, "".join(parts)),
            [('<i class="ls strong"></i>', 'strong'),
             ('<i class="ls moderate"></i>', 'moderate'),
             ('<i class="ls weak"></i>', 'weak')],
            'Edges are light that actually moved between two specimens — not containment '
            'and not similarity. Each specimen is drawn where it stands in the terrain, so a '
            'short edge is neighbours trading and a long one is light crossing open ground. '
            '%d links among these %d.' % (len(formed), len(chosen)))


# --- C. spectrum -----------------------------------------------------------
def panel_spectrum(data, w=470, h=400) -> str:
    chosen = data["_set"]
    if not chosen:
        return ('<p class="empty">Nothing living to place.</p>', [],
                'No specimen is alive in this terrain at this shift, so there is nothing '
                'to position. The panel is empty rather than illustrative.')
    mx = max(b.get("_links", 0) for b in chosen) or 1
    my = max(int(b.get("age", 0)) for b in chosen) or 1
    parts = ['<rect x="52" y="24" width="%d" height="%d" class="frame"/>' % (w - 82, h - 96),
             '<line x1="%d" y1="24" x2="%d" y2="%d" class="mid"/>' % (w/2+11, w/2+11, h-72),
             '<line x1="52" y1="%d" x2="%d" y2="%d" class="mid"/>' % ((h-48)/2, w-30, (h-48)/2)]
    for b in chosen:
        x = 52 + (b.get("_links", 0) / mx) * (w - 96)
        y = (h - 72) - (int(b.get("age", 0)) / my) * (h - 110)
        parts.append('<g transform="translate(%.1f,%.1f)">%s</g>' % (x, y, portrait(b, 16)))
        parts.append('<text x="%.1f" y="%.1f" class="nlbl">%s</text>' % (x, y + 27, esc(b["_label"])))
    parts.append('<text x="52" y="%d" class="axl">fewer relations</text>' % (h - 52))
    parts.append('<text x="%d" y="%d" class="axl" text-anchor="end">more relations &rarr;</text>'
                 % (w - 30, h - 52))
    parts.append('<text x="46" y="34" class="axl" text-anchor="end" '
                 'transform="rotate(-90 46 34)">longer standing &rarr;</text>')
    return ('<svg viewBox="0 0 %d %d" class="spec" role="img" aria-label="spectrum">%s</svg>'
            % (w, h, "".join(parts)),
            [('Y', 'shifts stood — temporal continuity of presence'),
             ('X', 'links held — degree of interaction with others'),
             ('&#183;', 'quadrant lines mark the midpoint of each axis')],
            'Position by degree, not kind. Both axes are measurements and the space between '
            'specimens is continuous — nothing here is grouped or bounded.')


# --- D. sequence -----------------------------------------------------------
def panel_sequence(data, w=470) -> str:
    chosen = sorted(data["_set"], key=lambda b: (b.get("arose_at_shift", 0), b["id"]))
    if not chosen:
        return ('<p class="empty">Nothing to order yet.</p>', [],
                'No specimen has emerged in this terrain yet, so there is no order of '
                'emergence to draw.')
    rowh = 30
    h = len(chosen) * rowh + 54
    idx = {b["id"]: n for n, b in enumerate(chosen)}
    parts = ['<text x="6" y="20" class="hd">ORDER</text>',
             '<text x="52" y="20" class="hd">SHIFT</text>',
             '<text x="120" y="20" class="hd">SPECIMEN</text>']
    for n, b in enumerate(chosen):
        y = 42 + n * rowh
        parts.append('<text x="10" y="%d" class="seql">%02d</text>' % (y + 4, n + 1))
        parts.append('<text x="56" y="%d" class="seql">%s</text>' % (y + 4, esc(b.get("arose_at_shift"))))
        parts.append('<g transform="translate(116,%.1f)">%s</g>' % (y, portrait(b, 11)))
        parts.append('<text x="136" y="%d" class="seqid" text-anchor="start">%s</text>'
                     % (y + 4, esc(b["_label"])))
        parent = b.get("parent_id")
        if parent in idx:
            py = 42 + idx[parent] * rowh
            parts.append('<path d="M%d %d C %d %d, %d %d, %d %d" class="desc"/>'
                         % (190, py, 300, py, 300, y, 190, y))
    return ('<svg viewBox="0 0 %d %d" class="seq" role="img" aria-label="order of emergence">'
            '%s</svg>'
            % (w, h, "".join(parts)),
            [('<i class="lcurve"></i>', 'descent — parent to offspring'),
             ('&darr;', 'time runs downward')],
            'Ordered by the shift each specimen first appeared. Descent is drawn only where '
            'both parent and offspring are on this sheet; a specimen whose parent is not in '
            'the set shows no curve.')


SHEET_CSS = """
.masthead{display:grid;grid-template-columns:1fr auto;gap:30px;align-items:start;
border-bottom:3px double var(--ink);padding:22px 0 16px}
.mark{width:52px;height:52px;border:2.5px solid var(--moss);position:relative}
.mark:after{content:"";position:absolute;left:9px;right:9px;top:9px;bottom:-2px;
background:var(--paper);border-left:2.5px solid var(--moss);border-right:2.5px solid var(--moss)}
.dept{font:600 10.5px/1.45 var(--sans);letter-spacing:.13em;text-transform:uppercase;
color:var(--ink);margin-top:6px}
.title h1{font:400 clamp(19px,2.3vw,27px)/1.18 var(--serif);margin:0;text-transform:uppercase}
.title .sub{color:var(--grey);font:11px/1.6 var(--mono);margin-top:8px;max-width:62ch}
table.doc{border-collapse:collapse;font:10.5px/1.7 var(--mono);color:var(--grey);
width:auto;min-width:0}
table.doc td{padding:0 0 0 10px;white-space:nowrap}
table.doc td.k{padding:0;color:var(--grey)}
table.doc td.v{color:var(--ink)}
table.doc td.k:after{content:":";padding-left:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:30px;
margin-top:26px}
.unit{display:flex;flex-direction:column}
.panel{border:1px solid var(--ink);background:var(--panel);padding:16px 18px 14px}
.panel h2{font:600 11.5px/1.4 var(--mono);letter-spacing:.1em;text-transform:uppercase;
margin:0 0 2px}
.pl{color:var(--moss)}
.pq{color:var(--grey);font-weight:400;text-transform:none;letter-spacing:.03em}
.lede{color:var(--grey);font-size:12px;margin:0 0 12px}
.figure{border:1px solid var(--rule);background:var(--paper);padding:8px}
.boxrow{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
.box{border:1px solid var(--rule);padding:8px 10px}
.box.notes{margin-top:10px}
.bh{font:600 9px/1.5 var(--mono);letter-spacing:.12em;text-transform:uppercase;
color:var(--grey);margin-bottom:5px}
table.lg,table.mt{border-collapse:collapse;font:10px/1.6 var(--mono);width:100%}
table.lg td,table.mt td{padding:1px 0;vertical-align:middle}
table.lg td.sym{width:34px;color:var(--ink)}
table.mt td.mk{color:var(--grey);white-space:nowrap;padding-right:10px}
table.mt td.mv{color:var(--ink);text-align:right}
.box.notes p{margin:0;font:10.5px/1.6 var(--sans);color:var(--grey)}
.pcap{font:10.5px/1.6 var(--mono);color:var(--grey);margin:9px 2px 0}
.foot{margin-top:34px;border-top:3px double var(--ink);padding-top:18px;
display:grid;grid-template-columns:1.2fr 1fr .9fr;gap:26px;align-items:start}
.foot h3{font:600 9.5px/1.5 var(--mono);letter-spacing:.12em;text-transform:uppercase;
color:var(--grey);margin:0 0 7px}
.foot p{color:var(--grey);font-size:11.5px;line-height:1.6;margin:0 0 8px}
.stamp{border:1px solid var(--moss);color:var(--ink);padding:12px 14px;
font:10.5px/1.65 var(--mono);display:flex;gap:11px;align-items:flex-start}
.stamp .mark{width:26px;height:26px;border-width:2px;flex:0 0 auto}
.stamp .mark:after{left:5px;right:5px;top:5px;border-width:2px}
.grid svg{width:100%;height:auto;display:block}
.pbg{fill:var(--ink);opacity:.055}
.pcore{fill:none;stroke:var(--ink);stroke-width:1.1}
.pspoke{stroke:var(--ink);stroke-width:.7;opacity:.7}
.pnode{fill:var(--ink);opacity:.8}
.pring{fill:none;stroke:var(--moss);stroke-width:.8;opacity:.75}
.nlbl{fill:var(--ink);font:9px var(--mono);text-anchor:middle}
.frame{fill:none;stroke:var(--rule);stroke-width:1}
.net .e{stroke:var(--ink)}
.net .e.strong{stroke-width:2.4;opacity:.85}
.net .e.moderate{stroke-width:1.3;opacity:.6}
.net .e.weak{stroke-width:.7;opacity:.34}
.tree .tedge{fill:none;stroke:var(--ink);stroke-width:.9;opacity:.65}
.tree .tl{fill:var(--ink);font:10.5px var(--mono);text-anchor:middle;font-weight:600}
.tree .tn{fill:var(--grey);font:9px var(--mono);text-anchor:middle}
.spec .mid{stroke:var(--rule);stroke-dasharray:2 3}
.spec .axl{fill:var(--grey);font:9.5px var(--mono)}
.seq .hd{fill:var(--grey);font:9px var(--mono);letter-spacing:.09em}
.seq .seql{fill:var(--grey);font:9.5px var(--mono)}
.seq .seqid{fill:var(--ink);font:10px var(--mono)}
.ahd{fill:var(--ink);opacity:.7}
.seq .desc{fill:none;stroke:var(--moss);stroke-width:.9;opacity:.6}
.lline{display:inline-block;width:22px;border-top:1px solid var(--ink);vertical-align:middle}
.lcurve{display:inline-block;width:22px;border-top:1px solid var(--moss);
border-radius:60%;vertical-align:middle}
.lportrait{display:inline-block;width:9px;height:9px;border:1px solid var(--ink);
transform:rotate(45deg);vertical-align:middle}
.ls{display:inline-block;width:24px;vertical-align:middle}
.ls.strong{border-top:2.6px solid var(--ink)}
.ls.moderate{border-top:1.4px solid var(--ink);opacity:.75}
.ls.weak{border-top:.8px solid var(--ink);opacity:.45}
"""


SHEET_BODY = """<div class="masthead">
  <div class="title"><h1>DNT — Classification Structure,<br>Hypotheses Under Review</h1>
    <p class="sub">Exploratory models for organising synthform observations.<br>
    The Namer does not follow human systems. These are hypotheses, not prescriptions.</p></div>
  <table class="doc">
    <tr><td class="k">DOCUMENT</td><td class="v">DNT-TAX-STR</td></tr>
    <tr><td class="k">TERRAIN</td><td class="v">__TERRAIN__</td></tr>
    <tr><td class="k">SHIFT</td><td class="v">__SHIFT__</td></tr>
    <tr><td class="k">STATUS</td><td class="v">EXPLORATORY</td></tr>
    <tr><td class="k">SCOPE</td><td class="v">INTERNAL</td></tr>
  </table>
</div>
<div class="grid">__A____B____C____D__</div>
<div class="foot">
  <div><h3>About these models</h3>
    <p>These are provisional frameworks for analysis and pattern testing. They do not
    prescribe ontology. The Namer's system is not assumed to be stable, human-readable,
    or reducible to any of them.</p>
    <p>DNT-CLS-001 Section 1 holds that Linnaean taxonomy is one historical solution shaped
    by human morphological perception. A hierarchy is therefore shown as one arrangement
    among several rather than as the arrangement.</p></div>
  <div class="stamp"><div class="mark"></div>
    <div>NO STRUCTURE HAS BEEN ADOPTED.<br>The native taxonomy remains whatever the Namer
    has made of it. Nothing on this sheet feeds back into it, and no agent has seen it.</div></div>
  <div><h3>Reference</h3>
    <p>A living document. Every position is computed from a recorded value — node placement,
    edge weight and ordering alike. No layout was adjusted by hand.</p>
    <p>Revisions expected as the Namer continues to observe.</p></div>
</div>
"""


PANELS = [
    ("A", "Lineage tree", "(descent, the human-default baseline)",
     "Nested descent. One parent, many offspring."),
    ("B", "Relational web", "(network graph)",
     "Multiple relations. No single hierarchy."),
    ("C", "Spectrum", "(gradient field)",
     "Position by degree, not kind. Continuous space."),
    ("D", "Sequence", "(temporal structure)",
     "Ordered by first emergence. Relations through time."),
]


def meta_rows(pairs) -> str:
    return "".join('<tr><td class="mk">%s</td><td class="mv">%s</td></tr>' % (k, v)
                   for k, v in pairs)


def meta_get(html_rows: str, key: str) -> str:
    import re as _re
    m = _re.search(r'<td class="mk">%s</td><td class="mv">([^<]*)</td>' % key, html_rows)
    return m.group(1) if m else "\u2014"


def compose(letter, title, qualifier, lede, figure, legend, notes, meta) -> str:
    """One panel as a field sheet builds it: a framed figure, then a legend box
    and a meta box side by side, then a notes box, then a caption OUTSIDE the
    frame. The reference sheet separates those four jobs and the earlier build
    ran them together into one undifferentiated column."""
    rows = "".join('<tr><td class="sym">%s</td><td>%s</td></tr>' % (sym, txt)
                   for sym, txt in legend)
    return (
        '<div class="unit">'
        '<section class="panel">'
        '  <h2><span class="pl">%s.</span> %s <span class="pq">%s</span></h2>'
        '  <p class="lede">%s</p>'
        '  <div class="figure">%s</div>'
        '  <div class="boxrow">'
        '    <div class="box"><div class="bh">Legend</div><table class="lg">%s</table></div>'
        '    <div class="box"><div class="bh">Observation set</div>'
        '      <table class="mt">%s</table></div>'
        '  </div>'
        '  <div class="box notes"><div class="bh">Notes</div><p>%s</p></div>'
        '</section>'
        '<p class="pcap">Panel %s — tested against %s logged specimens of %s living, '
        'terrain %s, shift %s. Confidence: exploratory.</p>'
        '</div>'
        % (letter, title, qualifier, lede, figure, rows, meta, notes,
           letter, meta_get(meta, "TOTAL NODES"), meta_get(meta, "POPULATION"),
           meta_get(meta, "TERRAIN"), meta_get(meta, "SHIFT")))


def main(argv: List[str]) -> int:
    data = load()
    data["_set"] = observation_set(data)
    terrain = esc(data["memory"].get("terrain_name"))
    shift = esc(data["memory"].get("last_committed_shift"))
    pop = len(data["world"].get("individuals") or {})
    nset = len(data["_set"])
    first = min([b.get("arose_at_shift", 0) for b in data["_set"]] or [0])
    meta = meta_rows([("TOTAL NODES", str(nset)), ("POPULATION", str(pop)),
                      ("TERRAIN", terrain), ("SHIFT", "%s–%s" % (first, shift)),
                      ("SELECTED BY", "largest living lineages, taken whole")])
    built = []
    for (letter, title, qual, lede), fn in zip(
            PANELS, (panel_hierarchy, panel_network, panel_spectrum, panel_sequence)):
        fig, legend, notes = fn(data)
        built.append(compose(letter, title, qual, lede, fig, legend, notes, meta))
    sheet = (SHEET_BODY.replace("__A__", built[0])
                 .replace("__B__", built[1])
                 .replace("__C__", built[2])
                 .replace("__D__", built[3])
                 .replace("__TERRAIN__", terrain)
                 .replace("__SHIFT__", shift)
                 .replace("__COUNT__", esc(nset))
                 .replace("__POP__", esc(pop)))
    terrain_dir = os.path.basename(config.TERRAIN_ROOT.rstrip(os.sep))
    page = dnt_chrome.page(
        "Classification Structure — " + terrain, dnt_chrome.PAPER, SHEET_CSS, sheet,
        [terrain, "FIELD COMPENDIUM", "CLASSIFICATION STRUCTURE"],
        dnt_chrome.sidebar(PROJECT_ROOT, terrain_dir, "structure.html"),
        '<a href="/%s/codex.html">Field compendium</a>' % terrain_dir,
        "DNT FIELD MANUAL v1.0")
    with open(OUT, "w", encoding="utf-8") as stream:
        stream.write(page)
    print("wrote %s" % OUT)
    if "--open" in argv:
        webbrowser.open("file://" + OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
