"""
The console shell — the frame every live-state view of a terrain sits inside.

WHAT THE CONSOLE IS, AND WHAT IT IS NOT

  The department publishes two kinds of page and they do not look alike.

  REFERENCE DOCUMENTS are printed on paper: the Field Compendium, the
  Classification Structure, the Linnaean Crosswalk. They are read, they are
  cited, and they change only when someone regenerates them.

  CONSOLE VIEWS are the live state of one terrain, and they are dark: the
  observation deck, the terrain record, the shift log, a specimen record, a
  category record, a lineage record, a checkpoint report, a comparative study.
  Every one of them carries "Back to observation deck" in its top bar, because
  every one of them is a way of looking at the same running terrain.

  The split is not decorative. A reader who clicks between two console views is
  still looking at the terrain; a reader who clicks out to the compendium has
  left it for a document about it.

WHAT THE STATUS LINE SAYS

  The mockups this was built to show a status of RUNNING and a wall-clock time.
  A terrain is not a process that runs; it advances when a shift is run against
  it and is otherwise exactly still. The status line therefore reports the last
  shift committed and when it was committed, which is the true state, and says
  HOLDING rather than RUNNING between shifts.

Python 3.9 compatible.
"""

from __future__ import annotations

import os
from typing import List, Optional, Sequence, Tuple

import dnt_style

MARK = dnt_style.MARK_PATH

PORTS = {"basin-01": 8731, "basin-02": 8732, "basin-03": 8733, "basin-04": 8734}
HUB = "http://127.0.0.1:8730"


SKIN = """
:root{--ink:#D6DED2;--dim:#7C8879;--faint:#4E574C;--rule:#1D231B;--rule2:#2A322704;
--bg:#080A07;--panel:#0D100C;--panel2:#111510;--moss:#8FC96B;--moss2:#5F8F45;
--amber:#C9A227;--rose:#D4614A;--violet:#8F7FBE;--cyan:#5FA9A0;--slate:#5A6B78;
--serif:Georgia,'Iowan Old Style',serif;
--sans:ui-sans-serif,system-ui,-apple-system,sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,'DejaVu Sans Mono',monospace}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);
font:13px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--moss)}
::selection{background:var(--moss2);color:var(--bg)}

/* ---- shell ---- */
.app{display:grid;min-height:100vh;
grid-template-columns:var(--lw,236px) minmax(0,1fr) var(--rw,318px);
grid-template-rows:auto minmax(0,1fr) auto;
grid-template-areas:"top top top" "left mid right" "bot bot bot"}
.app.norail{--rw:0px;grid-template-areas:"top top top" "left mid mid" "bot bot bot"}
.app.noleft{--lw:0px;grid-template-areas:"top top top" "mid mid right" "bot bot bot"}

/* ---- top bar ---- */
.top{grid-area:top;display:flex;align-items:center;gap:18px;padding:9px 16px;
background:var(--panel);border-bottom:1px solid var(--rule);flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:11px;text-decoration:none;color:var(--ink);
flex:0 0 auto}
/* The mark is a bracket with a gap in its base. The wordmark belongs in that
   gap — below the frame, tucked between its two feet — not beside it. */
.glyph{display:flex;flex-direction:column;align-items:center;flex:0 0 auto}
.glyph svg{fill:var(--moss);display:block}
/* The base of the bracket has a gap across its middle 64%. The wordmark is
   pulled up into that gap and masks the line behind it, so the letters read as
   part of the mark rather than as a caption under it. */
.glyph .w{font:700 9.5px/1 var(--mono);letter-spacing:.13em;color:var(--ink);
margin-top:-8px;background:var(--panel);padding:1px 2px 0}
.brand .d{font:600 8px/1.4 var(--sans);letter-spacing:.13em;text-transform:uppercase;
color:var(--dim)}
.crumbs{display:flex;align-items:center;gap:7px;font:11px var(--mono);letter-spacing:.06em;
flex-wrap:wrap}
.crumbs a{color:var(--moss);text-decoration:none}
.crumbs a:hover{text-decoration:underline}
.crumbs .cur{color:var(--moss)}
.crumbs .arrow{color:var(--faint)}
.state{display:flex;align-items:center;gap:9px;font:11px var(--mono);color:var(--dim);
margin-left:8px;white-space:nowrap}
.state b{color:var(--ink);font-weight:400}
.state .dot{width:6px;height:6px;border-radius:50%;background:var(--moss);display:block}
.acts{margin-left:auto;display:flex;gap:7px;flex-wrap:wrap}
.acts a{font:10.5px var(--mono);letter-spacing:.03em;color:var(--ink);text-decoration:none;
border:1px solid var(--rule);background:var(--bg);padding:6px 11px;white-space:nowrap}
.acts a:hover{border-color:var(--moss2);color:var(--moss)}
.acts a.pri{border-color:var(--moss2)}

/* ---- rails ---- */
.left{grid-area:left;background:var(--panel);border-right:1px solid var(--rule)}
.right{grid-area:right;background:var(--panel);border-left:1px solid var(--rule)}
.mid{grid-area:mid;min-width:0;padding:16px}
.left,.right{overflow-y:auto;min-height:0}
.app.norail .right{display:none}
.app.noleft .left{display:none}

/* ---- panels ---- */
.p{border:1px solid var(--rule);background:var(--panel);margin-bottom:14px}
.mid>.p:last-child,.rail .p:last-child{margin-bottom:0}
.rail{padding:13px}
.ph{display:flex;align-items:baseline;gap:9px;padding:10px 13px;
border-bottom:1px solid var(--rule);font:9.5px var(--mono);letter-spacing:.13em;
text-transform:uppercase;color:var(--dim)}
.ph b{color:var(--ink);font-weight:400;letter-spacing:.06em}
.ph .r{margin-left:auto;color:var(--faint);text-transform:none;letter-spacing:.04em}
.ph a{color:var(--moss);text-decoration:none;font-size:9.5px}
.pb{padding:13px}
.pb.flush{padding:0}

/* ---- key/value ---- */
dl.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;margin:0;
font:11.5px/1.6 var(--mono);font-variant-numeric:tabular-nums}
dl.kv dt{color:var(--dim)}
dl.kv dd{margin:0;text-align:right;color:var(--ink);word-break:break-word}
dl.kv dd.na{color:var(--faint);font-style:italic}

/* ---- stat strip ---- */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));
border:1px solid var(--rule);border-left:none;background:var(--panel);margin-bottom:14px}
.stat{border-left:1px solid var(--rule);padding:13px 15px}
.stat .v{font:400 26px/1.05 var(--serif);font-variant-numeric:tabular-nums}
.stat .l{font:9px var(--mono);letter-spacing:.11em;text-transform:uppercase;
color:var(--dim);margin-top:7px}
.stat .s{font:10px var(--mono);color:var(--faint);margin-top:3px}
.up{color:var(--moss)}.down{color:var(--rose)}

/* ---- tables ---- */
table.d{border-collapse:collapse;width:100%;font:11.5px/1.5 var(--mono);
font-variant-numeric:tabular-nums}
table.d th{text-align:left;font:9px var(--mono);letter-spacing:.11em;text-transform:uppercase;
color:var(--dim);border-bottom:1px solid var(--rule);padding:0 12px 8px 0;font-weight:400}
table.d td{padding:7px 12px 7px 0;border-bottom:1px solid var(--rule);vertical-align:top;
color:var(--ink)}
table.d td.dim{color:var(--dim)}
table.d td.num,table.d th.num{text-align:right;padding-right:14px}
table.d tr:last-child td{border-bottom:none}
.scroll{overflow-x:auto}

/* ---- bars ---- */
.bar{height:5px;background:var(--rule);position:relative;min-width:52px}
.bar span{display:block;height:5px;background:var(--moss)}
.mini{display:grid;grid-template-columns:1fr 54px auto;gap:9px;align-items:center;
font:11px var(--mono);color:var(--dim);padding:4px 0}
.mini b{color:var(--ink);font-weight:400;text-align:right;font-variant-numeric:tabular-nums}

/* ---- chips ---- */
.chip{display:inline-block;font:9px var(--mono);letter-spacing:.09em;text-transform:uppercase;
padding:2px 7px;border:1px solid var(--rule);color:var(--dim)}
.chip.on{color:var(--moss);border-color:var(--moss2)}
.chip.warn{color:var(--amber);border-color:var(--amber)}
.chip.off{color:var(--faint)}
.sw{width:9px;height:9px;border-radius:2px;display:inline-block;flex:0 0 auto;
vertical-align:middle}

/* ---- tabs ---- */
.tabs{display:flex;gap:0;border-bottom:1px solid var(--rule);margin-bottom:14px;
flex-wrap:wrap}
.tabs button{font:9.5px var(--mono);letter-spacing:.11em;text-transform:uppercase;
background:none;border:none;border-bottom:2px solid transparent;color:var(--dim);
padding:9px 14px;cursor:pointer}
.tabs button:hover{color:var(--ink)}
.tabs button.on{color:var(--moss);border-bottom-color:var(--moss)}
.tabpane{display:none}
.tabpane.on{display:block}

/* ---- navigation ---- */
.nav{display:block;border:1px solid var(--rule);background:var(--bg);text-decoration:none;
color:var(--ink);padding:11px 13px;margin-bottom:8px}
.nav:last-child{margin-bottom:0}
.nav:hover{border-color:var(--moss2);background:var(--panel2)}
.nav .t{font:11.5px var(--mono);letter-spacing:.04em;display:flex;
justify-content:space-between;align-items:center;gap:10px}
.nav .t .go{color:var(--moss)}
.nav .s{display:block;font:9.5px/1.5 var(--mono);color:var(--dim);margin-top:4px}
.nav.dead{border-style:dashed;background:none;cursor:default}
.nav.dead .t,.nav.dead .t .go{color:var(--faint)}
.nav.dead:hover{border-color:var(--rule);background:none}

/* ---- misc ---- */
.note{font:10.5px/1.6 var(--mono);color:var(--dim);margin:9px 0 0}
.note:first-child{margin-top:0}
.absent{color:var(--faint);font-style:italic}
.cols2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.cols3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
@media(max-width:1250px){.cols3{grid-template-columns:1fr 1fr}}
@media(max-width:900px){.cols2,.cols3{grid-template-columns:1fr}
.app,.app.norail,.app.noleft{grid-template-columns:1fr;
grid-template-areas:"top" "mid" "left" "right" "bot"}}
h1.doc{font:400 clamp(23px,2.6vw,32px)/1.1 var(--serif);margin:0 0 6px;letter-spacing:.01em}
h1.doc.mono{font-family:var(--mono);text-transform:uppercase;letter-spacing:.02em;
font-size:clamp(19px,2.2vw,26px)}
.sub{color:var(--dim);font:11.5px/1.6 var(--mono);margin:0}
.hdr{border-bottom:1px solid var(--rule);padding-bottom:14px;margin-bottom:16px;
display:grid;grid-template-columns:1fr auto;gap:26px;align-items:start}
.hdr table.doc{border-collapse:collapse;font:10.5px/1.75 var(--mono);color:var(--dim)}
.hdr table.doc td{padding:0 0 0 16px;white-space:nowrap;border:none}
.hdr table.doc td.k{padding:0}
.hdr table.doc td.v{color:var(--ink)}
.eyebrow{font:9.5px var(--mono);letter-spacing:.14em;text-transform:uppercase;
color:var(--dim);margin:0 0 9px}

/* ---- foot ---- */
.bot{grid-area:bot;display:flex;align-items:center;justify-content:space-between;gap:20px;
padding:11px 16px;background:var(--panel);border-top:1px solid var(--rule);
font:9.5px var(--mono);letter-spacing:.1em;color:var(--faint);text-transform:uppercase}
.bot svg{fill:var(--faint);display:block}
.bot .mid_{letter-spacing:.16em;color:var(--dim)}
"""


def mark(size: int = 20) -> str:
    return ('<svg viewBox="0 0 100 120" width="%d" height="%d" aria-hidden="true">'
            '<path d="%s" fill-rule="evenodd"/></svg>'
            % (size, int(size * 1.2), MARK))


def crumbs(items: Sequence) -> str:
    """items: (label, href_or_None). The last one is the current page."""
    out = []
    for i, (label, href) in enumerate(items):
        if i:
            out.append('<span class="arrow">&rsaquo;</span>')
        if href:
            out.append('<a href="%s">%s</a>' % (href, label))
        else:
            out.append('<span class="cur">%s</span>' % label)
    return '<div class="crumbs">%s</div>' % "".join(out)


def status(shift, committed_at: Optional[str]) -> str:
    """The true state of a terrain: a shift number and when it was committed.

    A terrain does not run continuously. It advances when a shift is run and is
    otherwise exactly still, so this says HOLDING rather than RUNNING.
    """
    when = (committed_at or "").replace("T", " ").replace("Z", " UTC")
    return ('<div class="state"><span class="dot"></span>SHIFT <b>%s</b>'
            '<span class="arrow">·</span>%s<span class="arrow">·</span>HOLDING</div>'
            % (shift, when or "never committed"))


def actions(terrain_dir: str, current: str = "") -> str:
    """The top-bar links. The deck first, then the three paper documents."""
    port = PORTS.get(terrain_dir, 8731)
    out = []
    if current != "deck":
        out.append('<a class="pri" href="http://127.0.0.1:%d/index.html">'
                   'Back to observation deck</a>' % port)
    for filename, label in (("codex.html", "Field compendium"),
                            ("structure.html", "Classification structure"),
                            ("crosswalk.html", "Linnaean crosswalk")):
        # Only what exists. The Archivist has not run on every terrain.
        if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       terrain_dir, filename)):
            out.append('<a href="/%s/%s">%s</a>' % (terrain_dir, filename, label))
    return '<div class="acts">%s</div>' % "".join(out)


def page(title: str, doc_name: str, terrain_dir: str, crumb_items: Sequence,
         shift, committed_at: Optional[str], mid: str,
         left: str = "", right: str = "", css: str = "",
         current: str = "", scripts: str = "") -> str:
    cls = "app"
    if not right:
        cls += " norail"
    if not left:
        cls += " noleft"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>%s</title><style>%s%s</style></head><body><div class="%s">'
        '<header class="top">'
        '<a class="brand" href="%s/hub.html">'
        '<span class="glyph">%s<span class="w">DNT</span></span>'
        '<span class="d">Department of<br>Nonhuman Territories</span></a>'
        '%s%s%s</header>'
        '%s<main class="mid">%s</main>%s'
        '<footer class="bot"><span>DNT %s v1.0</span>'
        '<span class="mid_">We observe. We do not interfere.</span>'
        '<span>A branch of the Nonhuman Institute %s</span></footer>'
        '</div>%s</body></html>'
        % (title, SKIN, css, cls,
           HUB, mark(27),
           crumbs(crumb_items), status(shift, committed_at), actions(terrain_dir, current),
           ('<aside class="left rail">%s</aside>' % left) if left else "",
           mid,
           ('<aside class="right rail">%s</aside>' % right) if right else "",
           doc_name, mark(13), scripts))


def panel(head: str, body: str, right_note: str = "", flush: bool = False) -> str:
    return ('<section class="p"><div class="ph"><b>%s</b>%s</div>'
            '<div class="pb%s">%s</div></section>'
            % (head, ('<span class="r">%s</span>' % right_note) if right_note else "",
               " flush" if flush else "", body))


def kv(pairs: Sequence[Tuple]) -> str:
    """pairs: (label, value) or (label, value, absent_bool)."""
    out = []
    for row in pairs:
        label, value = row[0], row[1]
        absent = row[2] if len(row) > 2 else False
        out.append('<dt>%s</dt><dd%s>%s</dd>'
                   % (label, ' class="na"' if absent else "", value))
    return '<dl class="kv">%s</dl>' % "".join(out)


def stats(items: Sequence[Tuple]) -> str:
    """items: (value, label) or (value, label, sub)."""
    out = []
    for row in items:
        sub = row[2] if len(row) > 2 else ""
        out.append('<div class="stat"><div class="v">%s</div><div class="l">%s</div>%s</div>'
                   % (row[0], row[1], ('<div class="s">%s</div>' % sub) if sub else ""))
    return '<div class="stats">%s</div>' % "".join(out)


def nav(items) -> str:
    """A list of places to go, sized to be clicked rather than found.

    items: (label, href_or_None, sub). A destination that does not exist yet is
    still listed, greyed and unclickable, so the reader learns it is coming
    rather than that it is missing.
    """
    out = []
    for label, href, sub in items:
        if href:
            out.append('<a class="nav" href="%s"><span class="t">%s'
                       '<span class="go">&rarr;</span></span>'
                       '<span class="s">%s</span></a>' % (href, label, sub))
        else:
            out.append('<div class="nav dead"><span class="t">%s'
                       '<span class="go">&mdash;</span></span>'
                       '<span class="s">%s</span></div>' % (label, sub))
    return "".join(out)


def bar(fraction: float, colour: str = "var(--moss)") -> str:
    f = max(0.0, min(1.0, fraction))
    return ('<div class="bar"><span style="width:%.1f%%;background:%s"></span></div>'
            % (f * 100.0, colour))
