"""
BASIN-01 — world export for the observation deck.

    python3 world_export.py            write viewer/world.json from current state
    python3 world_export.py --serve    write it, serve it locally, open the viewer

A browser will not load JavaScript modules straight off the filesystem — it
refuses them as cross-origin, which is why opening index.html directly leaves
the terrain on "loading". --serve starts a small local web server on this
machine, opens the viewer against it, and stops when you press Ctrl+C. Nothing
is exposed beyond this machine and no data leaves it.

Turns the terrain's own state into the shape a renderer needs. It reads
memory.json and writes one file. It changes nothing, spends nothing, and makes
no model call.

WHAT THIS EXPORTS, AND WHY THAT MATTERS

  Only measurements. Cell position, cover density, residue, and for each living
  thing: where it is, how much light it holds, how long it has been present,
  what it draws on, what it is linked to.

  Nothing here decides what anything looks like. There is no shape, no model,
  no species, no form. The viewer draws position, brightness, scale and
  connection from these numbers and nothing else — so what appears on screen is
  the record, not an illustration of it.

  That restraint is the point. The Department's own principle is
  non-authorship: what grows here was not written by us. A renderer that gave
  things legs, or made the light-takers look predatory, would be authoring the
  terrain in the one place nobody would think to audit.

THE ONE PRESENTATION CHOICE

  The terrain's physics is a single gradient — 21 cells from the far margin to
  the data-stream. To be walked through, that is presented as a valley: cells
  become bands across the ground, and specimens are spread laterally within
  their band so they can be told apart.

  The lateral position is DISPLAY ONLY. It is derived from the specimen's own
  identifier so it stays put between shifts, and it means nothing. The terrain
  has no second dimension; this is a way of looking at one that does not.

Python 3.9 compatible.
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import socketserver
import sys
import threading
import webbrowser
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents"))

import config
import life

VIEWER_DIR = os.path.join(config.TERRAIN_ROOT, "viewer")
OUTPUT = os.path.join(VIEWER_DIR, "world.json")


def _lateral(identifier: str) -> float:
    """A stable across-valley offset for display. Carries no meaning."""
    total = 0
    for position, character in enumerate(identifier):
        total = (total * 131 + ord(character) + position) % 100003
    return round((total % 2001) / 1000.0 - 1.0, 4)   # -1.0 .. 1.0


def build(memory: Dict[str, Any]) -> Dict[str, Any]:
    world = memory.get("world") or {}
    cells = world.get("cells") or []
    individuals = world.get("individuals") or {}
    links = world.get("links") or {}
    traces = memory.get("traces") or {}

    shift = int(memory.get("last_committed_shift", -1))
    flow = config.resource_flow_for_shift(max(0, shift))

    exported_cells: List[Dict[str, Any]] = []
    for cell in cells:
        exported_cells.append({
            "index": cell["index"],
            "position": cell["position"],
            "cover": round(float(cell.get("census_density", 0.0)), 4),
            "cover_light": round(float(cell.get("census_light", 0.0)), 3),
            "residue": round(float(cell.get("residue", 0.0)), 3),
            "substrate": cell.get("census_substrate"),
            "influx": life.influx(cell["index"], flow),
        })

    exported_beings: List[Dict[str, Any]] = []
    for identifier in sorted(individuals):
        being = individuals[identifier]
        drawn = (being.get("drawn_from_census", 0.0)
                 + being.get("drawn_from_residue", 0.0)
                 + being.get("drawn_from_links", 0.0))
        share = lambda v: round(v / drawn, 4) if drawn > 0 else 0.0
        exported_beings.append({
            "id": identifier,
            "cell": being.get("cell"),
            "position": life.cell_position(int(being.get("cell", 0))),
            "lateral": _lateral(identifier),
            "light": round(float(being.get("light", 0.0)), 3),
            "age": int(being.get("age", 0)),
            "sightings": int(being.get("sightings", 0)),
            "substrate": being.get("substrate"),
            "generation": int(being.get("generation", 0) or 0),
            "parent_id": being.get("parent_id"),
            "descendants": int(being.get("descendants", 0)),
            "origin": being.get("origin"),
            "affinities": being.get("traits", {}),
            "from_cover": share(being.get("drawn_from_census", 0.0)),
            "from_residue": share(being.get("drawn_from_residue", 0.0)),
            "from_links": share(being.get("drawn_from_links", 0.0)),
            "given_to_links": round(float(being.get("given_to_links", 0.0)), 3),
            "moves": int(being.get("moves", 0)),
            "trace": (traces.get(identifier) or "")[:600],
        })

    exported_links: List[Dict[str, Any]] = []
    for key, link in sorted(links.items()):
        if link.get("formed_at_shift") is None:
            continue
        a, b = key.split("|")
        if a in individuals and b in individuals:
            exported_links.append({
                "a": a, "b": b,
                "light_moved": round(float(link.get("light_moved", 0.0)), 3),
                "formed_at_shift": link.get("formed_at_shift"),
            })

    ended = [
        {"id": e.get("id"), "cell": e.get("cell"), "ended_at_shift": e.get("ended_at_shift"),
         "age": e.get("age"), "descendants": e.get("descendants", 0)}
        for e in (world.get("ended") or [])[-40:]
    ]

    return {
        "terrain": config.TERRAIN_NAME,
        "terrain_id": config.TERRAIN_ID,
        "shift": shift,
        "flow": flow,
        "cell_count": life.CELL_COUNT,
        "cells": exported_cells,
        "beings": exported_beings,
        "links": exported_links,
        "recently_ended": ended,
        "totals": {
            "living": len(exported_beings),
            "ever_ended": len(world.get("ended") or []),
            "cover_cells": sum(1 for c in exported_cells if c["cover"] > 0.0),
            "cumulative_cost_usd": round(float(memory.get("cumulative_cost_usd", 0.0)), 4),
        },
        "note": (
            "Positions, light, age and links are measured. Lateral placement is "
            "display only and carries no meaning — the terrain is one gradient."
        ),
    }


def main(argv: List[str]) -> int:
    if not os.path.isdir(VIEWER_DIR):
        os.makedirs(VIEWER_DIR)
    try:
        with open(config.MEMORY_FILE, "r", encoding="utf-8") as stream:
            memory = json.load(stream)
    except (IOError, ValueError) as exc:
        print("could not read terrain state: %s" % exc)
        return 1

    payload = build(memory)
    with open(OUTPUT, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=1)

    print("shift %s — %d living, cover in %d of %d cells, %d link(s)"
          % (payload["shift"], payload["totals"]["living"],
             payload["totals"]["cover_cells"], payload["cell_count"],
             len(payload["links"])))
    print("wrote %s" % OUTPUT)

    if "--serve" in argv or "--open" in argv:
        return serve()
    print("")
    print("to walk through it:  python3 world_export.py --serve")
    return 0


def serve(port: int = 8731) -> int:
    """Serve the viewer on this machine only, and open it.

    Bound to the loopback address, so it is reachable from this computer and
    from nowhere else. The terrain's record is not published by doing this.
    """
    viewer = os.path.join(VIEWER_DIR, "index.html")
    if not os.path.exists(viewer):
        print("viewer/index.html not built yet")
        return 1

    handler = functools.partial(QuietHandler, directory=VIEWER_DIR)
    for attempt in range(20):
        try:
            server = socketserver.TCPServer(("127.0.0.1", port + attempt), handler)
            break
        except OSError:
            continue
    else:
        print("could not find a free port")
        return 1

    url = "http://127.0.0.1:%d/index.html" % server.server_address[1]
    print("")
    print("observation deck: %s" % url)
    print("visible only on this machine. press Ctrl+C to close it.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nclosed.")
    finally:
        server.server_close()
    return 0


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the viewer directory without narrating every request."""

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
