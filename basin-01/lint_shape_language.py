"""
BASIN-01 — shape-language lint.

physics.md Section 3 and README.md Section 3 forbid seeding anything toward a
predetermined form or organic analog. README.md Section 3 extends that to code:
no shape language anywhere in the Generator files, "including comments and
variable names".

This check is mechanical so the constraint does not depend on anyone
remembering it. Run it after editing any agent module.

Matching is on whole words, so mechanism vocabulary that merely contains a
forbidden substring is not a hit: "nested structures" is README Section 4's own
approved wording for Generator A's substrate, and "system" is not "stem".

Usage:  python3 lint_shape_language.py [path ...]
Exit:   0 clean, 1 one or more hits.
"""

from __future__ import annotations

import os
import re
import sys
from typing import List, Tuple

# Organic analogs named in physics.md Section 3, plus the wider set of terms
# that would imply a visual outcome or a target silhouette.
FORBIDDEN_TERMS = (
    "tree", "trees", "animal", "animals", "insect", "insects", "mushroom",
    "mushrooms", "flora", "fauna", "plant", "plants", "creature", "creatures",
    "organism", "organisms", "body", "bodies", "limb", "limbs", "leaf",
    "leaves", "root", "roots", "branch", "branches", "cell", "cells", "spore",
    "spores", "colony", "bloom", "petal", "stem", "stems", "trunk", "wing",
    "wings", "eye", "eyes", "skin", "bone", "bones", "blood", "grow", "grows",
    "growing", "growth", "alive", "living", "species", "breed", "hatch",
    "nest", "nests", "swarm", "herd", "predator", "prey", "river", "forest",
    "garden", "organic", "biological", "biology", "anatomy", "anatomical",
    "morphology", "silhouette", "resemble", "resembles", "resembling",
    "creature-like", "lifeform", "lifeforms", "seedling", "sprout",
)

# README.md Section 3 binds the Generator files specifically; README.md
# Section 9 extends the principle to the whole build — "mechanism only,
# everywhere, including in code comments and internal naming" — so every agent
# module is checked.
DEFAULT_TARGETS = (
    "agents/generator_a.py",
    "agents/generator_b.py",
    "agents/namer.py",
)

_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in FORBIDDEN_TERMS) + r")\b",
    re.IGNORECASE,
)


def scan(path: str) -> List[Tuple[int, str, str]]:
    hits: List[Tuple[int, str, str]] = []
    with open(path, "r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, start=1):
            for match in _PATTERN.finditer(line):
                hits.append((number, match.group(0), line.strip()))
    return hits


def main(argv: List[str]) -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    targets = argv[1:] or [os.path.join(root, t) for t in DEFAULT_TARGETS]

    total = 0
    for target in targets:
        if not os.path.exists(target):
            print("missing: %s" % target)
            total += 1
            continue
        hits = scan(target)
        name = os.path.relpath(target, root)
        if not hits:
            print("clean   %s" % name)
            continue
        for number, term, line in hits:
            print("HIT     %s:%d  %r" % (name, number, term))
            print("            %s" % line[:100])
        total += len(hits)

    print("")
    print("shape-language lint: %d hit(s)" % total)
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
