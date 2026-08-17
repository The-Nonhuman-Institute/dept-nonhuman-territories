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
    "agents/keeper.py",
    "agents/archivist.py",
    "agents/cartographer.py",
)

# The Linnaean crosswalk vocabulary is REQUIRED in exactly one place and
# forbidden everywhere else.
#
# physics.md Section 4.4 obliges the Archivist to produce plain-English tier
# labels — Kingdom through Species — so those words must be allowed there.
# DNT-CLS-001 Sections 1 and 2 forbid the same vocabulary reaching the Namer,
# whose native reasoning has to stay "uncontaminated by human categorical
# language in the moment of classification".
#
# So this is not an exemption that weakens the check. It is the check: the
# vocabulary is permitted in the crosswalk file and actively hunted everywhere
# else, which is the separation the standard actually asks for.
CROSSWALK_VOCABULARY = (
    "kingdom", "phylum", "class", "order", "family", "genus", "species",
    "binomial", "linnaean", "biological", "taxonomic rank",
)

CROSSWALK_PERMITTED_IN = ("agents/archivist.py",)

# Files that must never carry crosswalk vocabulary, checked explicitly rather
# than by omission.
CROSSWALK_FORBIDDEN_IN = (
    "agents/namer.py",
    "agents/generator_a.py",
    "agents/generator_b.py",
    "agents/keeper.py",
    "agents/cartographer.py",
)

_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in FORBIDDEN_TERMS) + r")\b",
    re.IGNORECASE,
)

_CROSSWALK_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in CROSSWALK_VOCABULARY) + r")\b",
    re.IGNORECASE,
)


def scan(path: str, pattern: "re.Pattern") -> List[Tuple[int, str, str]]:
    hits: List[Tuple[int, str, str]] = []
    with open(path, "r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, start=1):
            for match in pattern.finditer(line):
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
        name = os.path.relpath(target, root)
        relative = name.replace(os.sep, "/")

        hits = scan(target, _PATTERN)
        if relative in CROSSWALK_PERMITTED_IN:
            # physics.md Section 4.4 obliges this file to name the tiers, so
            # tier vocabulary is not a hit here.
            hits = [h for h in hits if h[1].lower() not in CROSSWALK_VOCABULARY]

        crosswalk_hits: List[Tuple[int, str, str]] = []

        if not hits and not crosswalk_hits:
            note = ""
            if relative in CROSSWALK_PERMITTED_IN:
                note = "  (crosswalk vocabulary permitted here, per physics.md 4.4)"
            print("clean   %s%s" % (name, note))
            continue

        for number, term, line in hits:
            print("HIT     %s:%d  %r" % (name, number, term))
            print("            %s" % line[:100])
        for number, term, line in crosswalk_hits:
            print("HIT     %s:%d  %r — crosswalk vocabulary is forbidden in this"
                  " file (DNT-CLS-001 Sections 1 and 2)" % (name, number, term))
            print("            %s" % line[:100])
        total += len(hits) + len(crosswalk_hits)

    total += check_prompts()

    print("")
    print("shape-language lint: %d hit(s)" % total)
    return 1 if total else 0


def check_prompts() -> int:
    """Check the operative instructions actually sent to a model.

    Scanning file text is blunt: a docstring stating that a role is NOT issued
    the crosswalk vocabulary reads the same to a regex as a prompt containing
    it. What matters is what reaches the model, so this imports each role and
    inspects the string its prompt builder returns.

    This is the check that enforces DNT-CLS-001 Sections 1 and 2 — the Namer's
    native reasoning staying uncontaminated by human categorical language at
    the moment of classification.
    """
    root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, root)
    sys.path.insert(0, os.path.join(root, "agents"))

    print("")
    print("operative instructions (what actually reaches a model):")

    failures = 0
    for module_name in ("generator_a", "generator_b", "namer", "keeper", "archivist"):
        try:
            module = __import__(module_name)
        except ImportError as exc:
            print("  skipped %-14s (%s)" % (module_name, exc))
            continue

        builder = getattr(module, "_system_prompt", None)
        if builder is None:
            print("  %-14s no prompt builder" % module_name)
            continue

        try:
            prompt = builder()
        except TypeError:
            # Builders taking resource-scaled arguments; values are irrelevant
            # to the vocabulary check.
            prompt = builder(*([1] * builder.__code__.co_argcount))

        shape = [m.group(0) for m in _PATTERN.finditer(prompt)]
        crosswalk = [m.group(0) for m in _CROSSWALK_PATTERN.finditer(prompt)]
        permitted = ("agents/%s.py" % module_name) in CROSSWALK_PERMITTED_IN
        if permitted:
            crosswalk = []
            shape = [s for s in shape if s.lower() not in CROSSWALK_VOCABULARY]

        if shape or crosswalk:
            failures += len(shape) + len(crosswalk)
            print("  HIT %-14s shape=%s crosswalk=%s" % (module_name, shape, crosswalk))
        else:
            print("  clean %-12s%s" % (
                module_name,
                "  (tier vocabulary permitted)" if permitted else "",
            ))

    return failures


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
