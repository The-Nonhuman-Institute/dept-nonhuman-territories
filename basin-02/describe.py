# SPDX-FileCopyrightText: 2026 U3 Labs, LLC
# SPDX-License-Identifier: Apache-2.0
"""
DNT — a human-legible description of a specimen. Human side only.

WHAT THIS IS

  DNT-CLS-001 Section 2 makes human legibility a separate concern from native
  classification, and puts it downstream: the Archivist translates for human
  readers after the Namer has classified, and that translation carries no
  authority over the native system.

  This is the same principle applied to form. The Namer describes what a
  specimen DOES, analytically, because that is its job. Nobody in the system
  was describing what a specimen IS in the way an encyclopedia entry would —
  so a reader was handed arithmetic and asked to picture a creature from it.

  This turns the measurements into a sentence, exactly as the plate turns the
  same measurements into a drawing. Both are deterministic renderings of
  recorded numbers.

WHAT MAKES THIS SAFE

  1. It is written in code, not by a model. Every word below is produced by a
     threshold on a recorded value, and the whole table is in this file where
     it can be checked. Run it twice on the same specimen and it says the same
     thing.

  2. It reaches no agent. Nothing here is shown to a Generator, the Namer, the
     Keeper, the Archivist or the Cartographer. It is a rendering of the
     record for a person reading it afterwards.

  3. It describes form and behaviour, never role or kind. It will say a
     specimen is compact, far-reaching, many-jointed, that it fed on the mat or
     drew on its neighbours. It will not say it is a grazer, a predator, a
     parasite or a tree. What KIND of thing it is remains the Namer's to
     decide, and the Namer's word for it appears beside this, unaltered.

  4. It states the numbers it drew from, so a reader can disagree with the
     wording and still see the measurement.

WHY DESCRIBING FORM IS NOT AUTHORING IT

  The form is already fully determined by the record — mass, reach, joints,
  age and offspring are what the drawing is built from. Saying "compact and
  heavy-set" where mass is high and reach is low adds nothing that was not
  measured; it renames it in English. The failure this project guards against
  is deciding what a specimen should be like. This decides nothing.

Python 3.9 compatible.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Every threshold that produces a word, in one place, so the vocabulary can be
# audited against the measurement rather than trusted.
BUILD_MASS = ((0.55, "slight"), (1.10, "modestly built"),
              (1.90, "solidly built"), (99.0, "heavy-set"))
BUILD_REACH = ((0.60, "close-held"), (1.15, "moderately spread"),
               (1.90, "far-reaching"), (99.0, "sprawling"))
JOINTS = ((1, "single-jointed"), (2, "two-jointed"),
          (4, "several-jointed"), (99, "many-jointed"))
UPKEEP = ((0.70, "cheap to keep going"), (1.20, "ordinary to keep going"),
          (2.00, "costly to keep going"), (99.0, "very costly to keep going"))


def _band(value: Optional[float], table) -> str:
    if not isinstance(value, (int, float)):
        return ""
    for edge, word in table:
        if value < edge:
            return word
    return table[-1][1]


def describe(entry: Dict[str, Any]) -> str:
    """One paragraph about a specimen, built only from what was recorded."""
    m = entry.get("measurements") or {}
    st = m.get("structure") or {}
    aff = m.get("affinities") or {}
    if not st:
        return ("Nothing survives of this one but the Namer's account of it. It died "
                "before the terrain began keeping remains, so its build was never "
                "written down and cannot be recovered.")

    mass = st.get("mass")
    reach = st.get("extent")
    joints = 1 + int(st.get("junctions", 0) or 0)
    age = entry.get("shifts_present") or 0
    kids = entry.get("descendants") or 0

    # --- what it was like ---------------------------------------------------
    sentence = ["A %s, %s form" % (_band(mass, BUILD_MASS), _band(reach, BUILD_REACH))]
    sentence.append(", %s" % _band(st.get("junctions"), JOINTS).replace("-", "-"))
    if age >= 21:
        sentence.append(", visibly stacked from long standing")
    elif age >= 7:
        sentence.append(", beginning to stack with age")
    sentence.append(".")
    body = "".join(sentence)

    # --- how it made its living --------------------------------------------
    total = sum(v for v in (aff.get("cover"), aff.get("residue"), aff.get("links"))
                if isinstance(v, (int, float))) or 1.0
    share = {k: (aff.get(k) or 0) / total for k in ("cover", "residue", "links")}
    lead = max(share, key=share.get)
    how = {
        "cover": "It fed on the mat growing where it stood",
        "residue": "It lived off what dead specimens left behind",
        "links": "It drew its living along its joins to other specimens",
    }[lead]
    second = sorted(share, key=share.get, reverse=True)[1]
    if share[second] > 0.30:
        how += ", and took a real share %s as well" % {
            "cover": "from the mat", "residue": "from remains",
            "links": "from its neighbours"}[second]
    body += " " + how + "."

    # --- what that cost it --------------------------------------------------
    upkeep = m.get("upkeep")
    if isinstance(upkeep, (int, float)):
        body += (" It was %s, spending %.2f light every shift simply to hold together."
                 % (_band(upkeep, UPKEEP), upkeep))

    # --- how it ended -------------------------------------------------------
    if entry.get("alive"):
        fate = "It is still standing after %d shift%s" % (age, "" if age == 1 else "s")
    else:
        fate = "It lasted %d shift%s" % (age, "" if age == 1 else "s")
        if entry.get("ended_at_shift") is not None:
            fate += " and ended at shift %s" % entry["ended_at_shift"]
    if kids:
        fate += ", leaving %d offspring" % kids
    else:
        fate += ", leaving none"
    body += " " + fate + "."
    return body


def place(entry: Dict[str, Any], elevation: Optional[float],
          nearness: Optional[float]) -> str:
    """Where it stood, if the terrain records elevation and stream distance."""
    if elevation is None and nearness is None:
        return ""
    bits = []
    if isinstance(elevation, (int, float)):
        bits.append("on high ground" if elevation > 0.66 else
                    ("in low ground" if elevation < 0.34 else "on the middle slopes"))
    if isinstance(nearness, (int, float)):
        bits.append("close to a watercourse" if nearness > 0.66 else
                    ("far back from any watercourse" if nearness < 0.34
                     else "a moderate way from a watercourse"))
    return "It stood " + " and ".join(bits) + "." if bits else ""
