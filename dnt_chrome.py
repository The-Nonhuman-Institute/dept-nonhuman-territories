"""
DNT — the shared frame every page sits in.

Two systems, as the department uses them:

  PAPER    reference documents — the index, the compendium, category records,
           the crosswalk, the structure sheet. Cream, serif, read and cited.
  CONSOLE  operational pages — observation decks, terrain records, shift logs,
           lineage records, checkpoint reports. Near-black, monospace, watched.

Both carry the same mark, the same left navigation, and the same footer, so a
reader moving between them stays inside one institution.

Nothing here invents data. It supplies the frame; every page fills it from its
own terrain's logs.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import dnt_style

MARK = dnt_style.MARK_PATH


def mark(size: int = 30, cls: str = "mk") -> str:
    return ('<svg class="%s" viewBox="0 0 100 120" width="%d" height="%d" aria-hidden="true">'
            '<path d="%s" fill-rule="evenodd"/></svg>' % (cls, size, int(size * 1.2), MARK))


TERRAIN_NAV = [("basin-01", "BASIN-01"), ("basin-02", "BASIN-02"),
               ("basin-03", "BASIN-03"), ("basin-04", "BASIN-04")]

# The paper sidebar lists only the paper documents. The terrain record and the
# shift log are console views of a running terrain, not reference sheets, and
# they are reached through the TERRAINS group above — which leaves paper on
# purpose, the same way the console's top bar leaves the console to get here.
REFERENCE_NAV = [("codex.html", "FIELD COMPENDIUM"),
                 ("structure.html", "CLASSIFICATION STRUCTURE"),
                 ("crosswalk.html", "LINNAEAN CROSSWALK")]


def sidebar(root: str, current_terrain: Optional[str] = None,
            current_page: Optional[str] = None, extra: str = "") -> str:
    """Left navigation. Only links to pages that exist on disk."""
    items = []
    for d, label in TERRAIN_NAV:
        if not os.path.isdir(os.path.join(root, d)):
            continue
        cls = "on" if d == current_terrain else ""
        items.append('<a class="nav %s" href="/%s/terrain.html">%s</a>' % (cls, d, label))
    ref = []
    if current_terrain:
        for f, label in REFERENCE_NAV:
            if os.path.exists(os.path.join(root, current_terrain, f)):
                cls = "on" if f == current_page else ""
                ref.append('<a class="nav %s" href="/%s/%s">%s</a>' % (cls, current_terrain, f, label))
    return (
        '<aside class="side">'
        '<div class="navgroup"><div class="navhead">Terrains</div>%s</div>'
        '%s'
        '%s'
        '<div class="manual">%s<div>DNT FIELD MANUAL<br>VERSION 1.0<br>'
        '<span class="muted">INTERNAL USE ONLY</span></div></div>'
        '</aside>'
        % ("".join(items),
           ('<div class="navgroup"><div class="navhead">Reference</div>%s</div>' % "".join(ref))
           if ref else "",
           extra, mark(22, "mk small")))


def topbar(crumbs: List[str], right: str = "") -> str:
    trail = ' <span class="sep">/</span> '.join(
        ('<span class="crumb on">%s</span>' % c) if i == len(crumbs) - 1
        else ('<span class="crumb">%s</span>' % c) for i, c in enumerate(crumbs))
    return ('<header class="top">'
            '<a class="brand" href="/hub.html">'
            '<span class="glyph">%s<span class="wm">DNT</span></span>'
            '<span class="bt">Department of<br>Nonhuman Territories</span></a>'
            '<nav class="trail">%s</nav><div class="topright">%s</div></header>'
            % (mark(27), trail, right))


def footer(left: str = "") -> str:
    return ('<footer class="foot"><span>%s</span>'
            '<span class="motto">WE OBSERVE. WE DO NOT INTERFERE.</span>'
            '<span class="inst">A BRANCH OF THE NONHUMAN INSTITUTE %s</span></footer>'
            % (left, mark(14, "mk tiny")))


# --- the two skins ---------------------------------------------------------
PAPER = """
:root{--paper:#EFEDE3;--ink:#14170F;--moss:#3B4A2F;--grey:#6B7168;--rule:#B9B5A4;
--panel:#F7F5EC;--amber:#8A6D14;
--serif:Georgia,'Iowan Old Style','Times New Roman',serif;
--sans:ui-sans-serif,system-ui,-apple-system,'Helvetica Neue',sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,'DejaVu Sans Mono',monospace}
"""

CONSOLE = """
:root{--paper:#0A0C09;--ink:#D8E0D4;--moss:#8FC96B;--grey:#6E7A6B;--rule:#1E241C;
--panel:#0F120E;--amber:#C9A227;
--serif:Georgia,'Iowan Old Style',serif;
--sans:ui-sans-serif,system-ui,-apple-system,sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,'DejaVu Sans Mono',monospace}
"""

FRAME = """
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font:14px/1.6 var(--sans);margin:0}
.mk{fill:var(--moss);display:block}
.shell{display:grid;grid-template-columns:212px 1fr;min-height:100vh}
.top{grid-column:1/-1;display:flex;align-items:center;gap:22px;padding:10px 20px;
border-bottom:1px solid var(--rule);background:var(--panel);position:sticky;top:0;z-index:20}
.brand{display:flex;align-items:center;gap:11px;text-decoration:none;color:var(--ink)}
/* The mark is a bracket with a gap in its base. The wordmark belongs in that
   gap — below the frame, tucked between its two feet — not beside it. */
.glyph{display:flex;flex-direction:column;align-items:center}
.glyph .mk{display:block}
/* The base of the bracket has a gap across its middle 64%. The wordmark is
   pulled up into that gap and masks the line behind it, so the letters read as
   part of the mark rather than as a caption under it. */
.wm{font:700 7.5px/1 var(--mono);letter-spacing:0;color:var(--ink);
margin-top:-6px;background:var(--panel);padding:0}
.bt{font:600 9px/1.35 var(--sans);letter-spacing:.13em;text-transform:uppercase}
.trail{flex:1;font:11.5px var(--mono);letter-spacing:.05em;color:var(--grey);
display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.crumb.on{color:var(--moss)}
.sep{color:var(--rule)}
.topright{display:flex;gap:8px;font:11px var(--mono)}
.topright a{color:var(--ink);text-decoration:none;border:1px solid var(--rule);
padding:5px 10px;background:var(--paper)}
.topright a:hover{border-color:var(--moss)}
.side{border-right:1px solid var(--rule);padding:16px 0 20px;display:flex;
flex-direction:column;gap:20px;background:var(--panel)}
.navgroup{display:flex;flex-direction:column}
.navhead{font:9px var(--mono);letter-spacing:.15em;text-transform:uppercase;
color:var(--grey);padding:0 16px 7px}
a.nav{display:block;padding:7px 16px;font:11px var(--mono);letter-spacing:.06em;
color:var(--ink);text-decoration:none;border-left:2px solid transparent}
a.nav:hover{background:var(--paper)}
a.nav.on{background:var(--moss);color:var(--paper);border-left-color:var(--moss)}
.manual{margin-top:auto;padding:14px 16px;border-top:1px solid var(--rule);
font:9px/1.7 var(--mono);color:var(--grey);display:flex;gap:10px;align-items:flex-start}
.mk.small{fill:var(--moss);opacity:.8}
.muted{color:var(--rule)}
main{padding:22px clamp(16px,2.4vw,30px) 40px;min-width:0}
.foot{grid-column:1/-1;display:flex;justify-content:space-between;align-items:center;
gap:20px;padding:12px 20px;border-top:1px solid var(--rule);background:var(--panel);
font:9.5px var(--mono);letter-spacing:.09em;color:var(--grey)}
.motto{letter-spacing:.14em}
.inst{display:flex;align-items:center;gap:8px}
.mk.tiny{fill:var(--grey)}
@media(max-width:880px){.shell{grid-template-columns:1fr}.side{display:none}}
"""


def page(title: str, skin: str, css: str, body: str, crumbs: List[str],
         side: str, topright: str = "", footleft: str = "") -> str:
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>%s</title><style>%s%s%s</style></head><body><div class=\"shell\">"
            "%s%s<main>%s</main>%s</div></body></html>"
            % (title, skin, FRAME, css, topbar(crumbs, topright), side, body, footer(footleft)))
