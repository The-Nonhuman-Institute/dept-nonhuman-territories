"""
The one place that knows which terrains exist.

WHY THIS EXISTS

  The terrain list was declared in seven files — the hub, the console pages,
  both chrome modules, the chart palette, the server, and a retired page
  generator. Founding a terrain meant editing all seven, and missing one meant
  the terrain simply did not appear in that surface, silently.

  Terrains are now DISCOVERED: any basin-NN directory carrying a committed
  state/memory.json is a terrain, and everything downstream reads from here. A
  new terrain shows up in the hub, the sidebars, the study, the charts and the
  server the moment it has a state file, without anyone remembering to add it.

WHAT IS DERIVED AND WHAT IS READ

  Read from the terrain's own memory.json: its name and its terrain id.
  Derived from the directory number: its port (8730 + N) and its colour.

  Colour is assigned by NUMBER, not by position in a sorted list, so adding a
  terrain never repaints an existing one. Identity is never carried by colour
  alone anywhere it is used — every series is also named in a legend and
  labelled at its own line end — because these hues are not all separable under
  colour vision deficiency.

Python 3.9 compatible.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
HUB_PORT = 8730

# Assigned by terrain number and never reordered.
HUES = ["#4FA3E3",   # 1  blue
        "#B37BD6",   # 2  violet
        "#A8D45C",   # 3  lime
        "#E0A44C",   # 4  amber
        "#4FC9B0",   # 5  teal
        "#E0708A",   # 6  rose
        "#C9C05C",   # 7  ochre
        "#8FA5D6"]   # 8  periwinkle

_CACHE: Optional[List[Dict[str, Any]]] = None


def number_of(directory: str) -> int:
    found = re.search(r"(\d+)$", directory)
    return int(found.group(1)) if found else 0


def port_of(directory: str) -> int:
    return HUB_PORT + number_of(directory)


def hue_of(directory: str) -> str:
    n = number_of(directory)
    return HUES[(n - 1) % len(HUES)] if n else "#7C8879"


def all_terrains(refresh: bool = False) -> List[Dict[str, Any]]:
    """Every terrain with a committed state file, in directory order."""
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    out = []
    for entry in sorted(os.listdir(ROOT)):
        if not re.match(r"^basin-\d+$", entry):
            continue
        mem = os.path.join(ROOT, entry, "state", "memory.json")
        if not os.path.exists(mem):
            continue
        name, tid = entry.upper(), ""
        try:
            with open(mem, encoding="utf-8") as stream:
                m = json.load(stream)
            name = m.get("terrain_name") or name
            tid = m.get("terrain_id") or ""
        except (ValueError, IOError):
            pass
        out.append({"dir": entry, "name": name, "id": tid,
                    "port": port_of(entry), "hue": hue_of(entry),
                    "number": number_of(entry)})
    _CACHE = out
    return out


def dirs() -> List[str]:
    return [t["dir"] for t in all_terrains()]


def nav() -> List[tuple]:
    """(directory, label) pairs for a sidebar."""
    return [(t["dir"], t["name"]) for t in all_terrains()]


def ports() -> Dict[str, int]:
    return {t["dir"]: t["port"] for t in all_terrains()}


def hues() -> Dict[str, str]:
    return {t["dir"]: t["hue"] for t in all_terrains()}
