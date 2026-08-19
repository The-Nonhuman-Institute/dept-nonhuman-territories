"""
DNT — one house style for the Department's documents.

The console had grown four looks: a light hub, two dark reading pages, and a
paper field sheet. That is not a preference problem — a reader moving between
them cannot tell whether they are still inside the same institution, and the
seams make an assembled record look like assembled tooling.

WHAT SHARES THIS STYLE, AND WHAT DELIBERATELY DOES NOT

  Documents share it: the index, the compendium, the crosswalk, the structure
  sheet. They are printed matter — read, cited, handed to someone.

  The observation decks do NOT. They are instruments, not documents: a
  luminous terrain rendered on cream paper is unreadable, and the deck's job is
  to show a dark field with light moving through it. They keep the mark, the
  typography and the department's vocabulary, so they read as the same
  institution's equipment rather than the same institution's paperwork.

Python 3.9 compatible.
"""

from __future__ import annotations

CSS = """
:root{--paper:#EFEDE3;--ink:#14170F;--moss:#3B4A2F;--grey:#6B7168;--rule:#B9B5A4;
--panel:#F7F5EC;--amber:#8A6D14;
--serif:Georgia,'Iowan Old Style','Times New Roman',serif;
--sans:ui-sans-serif,system-ui,-apple-system,'Helvetica Neue',sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,'DejaVu Sans Mono',monospace}
/* A printed record commits to paper on either host theme. */
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font:14.5px/1.65 var(--sans);margin:0;
padding:0 clamp(14px,3vw,30px) 60px;-webkit-font-smoothing:antialiased}
.sheet{max-width:1180px;margin:14px auto 0;border:1px solid var(--ink);background:var(--paper);
padding:0 clamp(16px,3vw,32px) 30px}
.backbar{padding:10px 0;border-bottom:1px solid var(--rule)}
.backbar a{color:var(--moss);text-decoration:none;font:11.5px var(--mono);letter-spacing:.06em}
.backbar a:hover{text-decoration:underline}
.backbar a:focus-visible{outline:2px solid var(--moss);outline-offset:2px}
.masthead{display:grid;grid-template-columns:auto 1fr auto;gap:26px;align-items:start;
border-bottom:3px double var(--ink);padding:22px 0 16px}
.mark{display:block;fill:var(--moss)}
.dept{font:600 10.5px/1.45 var(--sans);letter-spacing:.13em;text-transform:uppercase;margin-top:6px}
.title h1{font:400 clamp(19px,2.3vw,27px)/1.18 var(--serif);margin:0;text-transform:uppercase}
.title .sub{color:var(--grey);font:11px/1.6 var(--mono);margin-top:8px;max-width:64ch}
table.doc{border-collapse:collapse;font:10.5px/1.7 var(--mono);color:var(--grey)}
table.doc td{padding:0 0 0 10px;white-space:nowrap}
table.doc td.k{padding:0}
table.doc td.k:after{content:":";padding-left:10px}
table.doc td.v{color:var(--ink)}
h2{font:400 22px/1.2 var(--serif);color:var(--moss);margin:0 0 6px}
h3{font:600 9.5px/1.5 var(--mono);letter-spacing:.12em;text-transform:uppercase;
color:var(--grey);margin:0 0 7px}
section{margin:30px 0}
.lede{color:var(--grey);font-size:13px;max-width:74ch;margin:0 0 14px}
.box{border:1px solid var(--rule);padding:10px 13px;background:var(--panel)}
.bh{font:600 9px/1.5 var(--mono);letter-spacing:.12em;text-transform:uppercase;
color:var(--grey);margin-bottom:5px}
code{font:12px var(--mono);background:var(--panel);padding:1px 5px;border:1px solid var(--rule)}
.scroll{overflow-x:auto}
table.data{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
table.data th{text-align:left;font:600 9.5px/1.4 var(--mono);letter-spacing:.11em;
text-transform:uppercase;color:var(--grey);border-bottom:1px solid var(--ink);
padding:0 14px 7px 0;vertical-align:bottom}
table.data td{border-bottom:1px solid var(--rule);padding:10px 14px 10px 0;vertical-align:top}
table.data td.num,table.data th.num{text-align:right;padding-right:20px;font-family:var(--mono)}
.quote{border-left:2px solid var(--rule);padding:4px 0 4px 18px;font:italic 14px/1.6 var(--serif);
max-width:74ch}
footer{margin-top:34px;border-top:3px double var(--ink);padding-top:16px;
font:10.5px/1.7 var(--mono);color:var(--grey)}
"""


def masthead(title: str, sub: str, rows) -> str:
    meta = "".join('<tr><td class="k">%s</td><td class="v">%s</td></tr>' % (k, v)
                   for k, v in rows)
    return (
        '<div class="masthead">'
        '<div><div class="mark"></div>'
        '<div class="dept">Department of<br>Nonhuman<br>Territories</div></div>'
        '<div class="title"><h1>%s</h1><p class="sub">%s</p></div>'
        '<table class="doc">%s</table></div>' % (title, sub, meta))


def backbar(here: str = "") -> str:
    return ('<div class="backbar"><a href="http://127.0.0.1:8730/hub.html">'
            '&larr; Department index</a></div>')

# ---------------------------------------------------------------------------
# THE MARK
#
# Traced from the supplied logo rather than approximated with borders: a tall
# rectangle, open at the foot, with two short returns at the bottom corners —
# a bracket that encloses without closing. Proportions are measured off the
# original (890 wide by 1065 tall, 65 wall, 160 feet), normalised to a 100x120
# box, and drawn as one path with an even-odd fill so it scales cleanly at any
# size and needs no image file.
# ---------------------------------------------------------------------------

MARK_PATH = ("M0,0 H100 V120 H0 Z "
             "M7.3,7.3 H92.7 V111.2 H7.3 Z "
             "M18,111.2 H82 V120 H18 Z")


def mark(size: int = 52, cls: str = "mark") -> str:
    return ('<svg class="%s" viewBox="0 0 100 120" width="%d" height="%d" '
            'aria-hidden="true" focusable="false">'
            '<path d="%s" fill-rule="evenodd"/></svg>'
            % (cls, size, int(size * 1.2), MARK_PATH))
