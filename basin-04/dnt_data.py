"""
DNT — one reader for every page. Real values only.

Every function here returns something computed from a terrain's own logs and
state. Where a quantity does not exist for a terrain, it returns None and the
page renders "no mechanism in this terrain" rather than a number.

Derived quantities use PUBLISHED definitions, never ones invented here, and
every page that shows one prints its formula. Shannon entropy for diversity,
coefficient of variation for stability, counts per hundred shifts for rates.
A derived figure whose definition is hidden is an assertion wearing the
clothes of a measurement.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def load(terrain: str) -> Dict[str, Any]:
    base = os.path.join(ROOT, terrain)
    mem_path = os.path.join(base, "state", "memory.json")
    if not os.path.exists(mem_path):
        return {}
    memory = json.load(open(mem_path, encoding="utf-8"))
    taxonomy = {}
    tpath = os.path.join(base, "state", "taxonomy.json")
    if os.path.exists(tpath):
        taxonomy = json.load(open(tpath, encoding="utf-8"))
    return {
        "dir": terrain,
        "memory": memory,
        "taxonomy": taxonomy,
        "shifts": _read_jsonl(os.path.join(base, "shifts", "shift_log.jsonl")),
        "specimens": _read_jsonl(os.path.join(base, "state", "specimen_log.jsonl")),
        "anomalies": _read_jsonl(os.path.join(base, "state", "anomaly_log.jsonl")),
    }


# --- governing conditions: real, or explicitly absent ---------------------
def governing_conditions(terrain: str) -> List[Dict[str, Any]]:
    """What actually governs this terrain. Absent conditions say so."""
    import importlib, sys
    base = os.path.join(ROOT, terrain)
    if base not in sys.path:
        sys.path.insert(0, base)
    try:
        cfg = importlib.import_module("config")
        importlib.reload(cfg)
    except Exception:
        return []
    rows = []
    def row(label, attr, fmt, governs):
        val = getattr(cfg, attr, None)
        rows.append({"label": label, "value": (fmt % val) if val is not None else None,
                     "governs": governs, "present": val is not None})
    row("light cycle", "LIGHT_CYCLE_PERIOD", "%d shifts", "period of the resource oscillation")
    row("temperature at stream", "TEMPERATURE_AT_STREAM", "%.1f", "warmest point, at cycle peak")
    row("lapse rate", "TEMPERATURE_LAPSE", "%.1f across full elevation",
        "how fast it cools with height")
    row("gravity", "GRAVITY", "%.2f", "drainage, cost of moving, upkeep per unit mass")
    row("wind strength", "WIND_STRENGTH", "%.2f of residue per shift", "lateral transport")
    row("subsurface rate", "SUBSURFACE_RATE", "%.2f per shift", "residue that sinks")
    row("spring threshold", "SPRING_THRESHOLD", "%.1f", "hidden load at which a cell surfaces")
    row("shift length", "SHIFT_LENGTH", "%.2f", "rate multiplier per tick")
    row("light at stream", "LIGHT_INFLUX_AT_STREAM", "%.1f", "influx at a watercourse")
    return rows


# --- derived quantities, with their definitions ---------------------------
def shannon_diversity(counts: List[int]) -> Optional[float]:
    """Shannon entropy H = -sum(p * ln p) over category shares."""
    total = sum(counts)
    if total <= 0 or len(counts) < 2:
        return None
    return round(-sum((c / total) * math.log(c / total) for c in counts if c > 0), 4)


def coefficient_of_variation(series: List[float]) -> Optional[float]:
    """CV = standard deviation / mean. Lower is steadier."""
    vals = [v for v in series if isinstance(v, (int, float))]
    if len(vals) < 3:
        return None
    mean = sum(vals) / len(vals)
    if mean == 0:
        return None
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    return round(math.sqrt(var) / mean, 4)


def per_hundred_shifts(count: int, shifts: int) -> Optional[float]:
    if not shifts:
        return None
    return round(count * 100.0 / shifts, 2)


DEFINITIONS = {
    "diversity": ("Shannon entropy", "H = -Σ pᵢ ln pᵢ over native category shares"),
    "stability": ("coefficient of variation", "CV = σ / μ of living population over the window"),
    "anomaly rate": ("count per hundred shifts", "anomalous classifications × 100 / shifts"),
    "lineage depth": ("mean generations from root", "computed by walking recorded parent_id"),
}
