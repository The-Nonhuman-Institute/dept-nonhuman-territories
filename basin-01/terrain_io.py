"""
BASIN-01 — sandboxed state layer.

This module is the ONLY write path in the terrain. No agent role opens a file,
constructs a path, or imports `os`. A role is handed a writer object exposing
exactly the operations its function requires, and nothing else.

That is the mechanism behind physics.md Section 9 and README.md Section 6:

  "Any replication-capable (viral/parasitic) specimen logic must be logically
   incapable of writing to any file/process outside /basin-01/state/. Enforce
   this at the code level (e.g., sandboxed write function all roles must use —
   no raw filesystem access), not by prompt instruction alone."

Containment here is structural, not advisory. There is no path parameter on any
public write method, so there is no path for a specimen to traverse. The five
terrain files are addressed by name through fixed methods; the resolver below
is a second, redundant check that refuses anything landing outside the terrain.

Crash safety (STARTUP_GUIDE.md Section 6): nothing is written during a shift.
A transaction buffers every change in memory and commits at a clean clock-out
by staging temp files and swapping them into place. A machine that dies
mid-shift leaves state/ at its last good checkpoint.

Python 3.9 compatible.
"""

from __future__ import annotations

import datetime
import json
import os
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Tuple

import config


# ---------------------------------------------------------------------------
# 1. CONTAINMENT BOUNDARY
# ---------------------------------------------------------------------------


class ContainmentError(RuntimeError):
    """A write was attempted against a path outside the terrain.

    Reaching this exception is a Section 9 event, not a routine error. It means
    something tried to address storage the terrain does not own. The Stewardship
    Protocol's containment exception (DNT-STW-001 Section 5) applies: intervene
    to restore containment, and log it as a terrain event rather than conceal it.
    """


class TerrainStateError(RuntimeError):
    """State on disk is missing, malformed, or internally inconsistent."""


# The complete set of writable locations in this terrain. Anything not on this
# list cannot be written by any code path in the module.
_WRITABLE_FILES = frozenset(
    (
        config.MEMORY_FILE,
        config.TAXONOMY_FILE,
        config.SPECIMEN_LOG,
        config.ANOMALY_LOG,
        config.SHIFT_LOG,
    )
)

_APPEND_ONLY_FILES = frozenset(
    (config.SPECIMEN_LOG, config.ANOMALY_LOG, config.SHIFT_LOG)
)


def _guard(path: str) -> str:
    """Refuse any path that is not one of the terrain's five own files.

    Resolves symlinks before comparing, so a symlink planted inside state/ that
    points outside the terrain is caught rather than followed.
    """
    resolved = os.path.realpath(path)
    for allowed in _WRITABLE_FILES:
        if resolved == os.path.realpath(allowed):
            return resolved
        # A file that does not exist yet has no realpath of its own to match,
        # so compare the resolved parent directory plus the basename.
        if not os.path.exists(allowed):
            if resolved == os.path.join(
                os.path.realpath(os.path.dirname(allowed)), os.path.basename(allowed)
            ):
                return resolved
    raise ContainmentError(
        "refused write outside terrain storage: %r resolved to %r"
        % (path, resolved)
    )


def _utc_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ---------------------------------------------------------------------------
# 2. SEED STRUCTURES
#
#    physics.md Section 2: flat JSON files, one per category. The structures
#    below are storage containers only.
#
#    taxonomy.json is deliberately near-empty. The Classification Standard
#    (DNT-CLS-001 Section 1) forbids issuing the Namer a structure to fill in,
#    so the file provides one opaque object — `native` — that the Namer owns
#    entirely. Nothing in the seed suggests hierarchy, rank, or relation. Code
#    that needs to count category membership for the promotion rule reads the
#    derived counters in memory.json instead, so no counting requirement leaks
#    a shape back into the Namer's own system.
# ---------------------------------------------------------------------------


def _seed_memory() -> Dict[str, Any]:
    return {
        "terrain_id": config.TERRAIN_ID,
        "terrain_name": config.TERRAIN_NAME,
        "physics_document": "DNT-PHY-001",
        "seeded_at": _utc_now(),
        "last_committed_shift": -1,
        "shifts_completed": 0,
        "cumulative_cost_usd": 0.0,
        "resource": {
            "flow": config.RESOURCE_FLOW_BASELINE,
            "generator_a_position": config.GENERATOR_A_POSITION,
            "generator_b_position": config.GENERATOR_B_POSITION,
        },
        "specimen_counts": {
            "total": 0,
            "individual_records": 0,
            "aggregate_members": 0,
            "anomalous": 0,
        },
        # Derived counters supporting the code-enforced promotion rule
        # (config.py Section 6). Keys are whatever labels the Namer coins; this
        # module never invents one.
        "category_stats": {},
        # Per-specimen state, including the required end-state resolution
        # (physics.md Section 7). Nothing is silently dropped.
        "specimen_index": {},
        # Non-agentive occurrences, logged separately from specimen activity
        # (physics.md Section 7). Containment interventions land here too.
        "terrain_events": [],
        "keeper_summary": None,
        "notes": (
            "Steward may read this file freely. Steward may not edit taxonomy "
            "or specimen records directly (DNT-STW-001 Section 3)."
        ),
    }


def _seed_taxonomy() -> Dict[str, Any]:
    return {
        "authored_by": "namer",
        "seeded_at": _utc_now(),
        "container_note": (
            "The object under 'native' is authored entirely by this terrain's "
            "Namer. It is not issued a template, a structure, or a vocabulary. "
            "Its only obligation is that for any two specimens it can state "
            "whether they are more or less alike, and why (DNT-CLS-001 "
            "Section 1)."
        ),
        "native": {},
        "revisions": [],
    }


def initialize_terrain() -> Dict[str, bool]:
    """Create any missing terrain file with a valid empty structure.

    Never overwrites. Running this against a live terrain is a no-op, which
    makes it safe for clock_in.py to call on every shift.
    """
    created: Dict[str, bool] = {}
    for directory in (config.STATE_DIR, config.SHIFTS_DIR):
        if not os.path.isdir(directory):
            os.makedirs(directory)

    for path, seed in (
        (config.MEMORY_FILE, _seed_memory()),
        (config.TAXONOMY_FILE, _seed_taxonomy()),
    ):
        if not os.path.exists(path):
            _write_json_atomic(path, seed)
            created[os.path.basename(path)] = True
        else:
            created[os.path.basename(path)] = False

    for path in (config.SPECIMEN_LOG, config.ANOMALY_LOG, config.SHIFT_LOG):
        if not os.path.exists(path):
            _guard(path)
            with open(path, "w", encoding="utf-8"):
                pass
            created[os.path.basename(path)] = True
        else:
            created[os.path.basename(path)] = False
    return created


# ---------------------------------------------------------------------------
# 3. ATOMIC PRIMITIVES
#
#    Every write lands via a staged temp file in the same directory, followed
#    by os.replace(), which is atomic on this platform. A crash leaves either
#    the old file or the new one — never a half-written one.
# ---------------------------------------------------------------------------


def _write_json_atomic(path: str, payload: Any) -> None:
    resolved = _guard(path)
    directory = os.path.dirname(resolved)
    handle, temp_path = tempfile.mkstemp(dir=directory, prefix=".stage-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, resolved)
    except BaseException:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def _append_lines_atomic(path: str, records: Iterable[Dict[str, Any]]) -> int:
    """Append records to an append-only log without risking a torn line.

    The existing content is copied into a staged file, the new records are
    appended to the copy, and the copy is swapped in. Append-only is a property
    of the content — no line is ever rewritten or removed — while the swap
    keeps a crash from leaving a partial record behind.
    """
    resolved = _guard(path)
    if resolved not in {os.path.realpath(p) for p in _APPEND_ONLY_FILES}:
        raise ContainmentError("not an append-only log: %r" % (path,))

    records = list(records)
    if not records:
        return 0

    directory = os.path.dirname(resolved)
    handle, temp_path = tempfile.mkstemp(dir=directory, prefix=".stage-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            if os.path.exists(resolved):
                with open(resolved, "r", encoding="utf-8") as existing:
                    for line in existing:
                        if line.strip():
                            stream.write(line if line.endswith("\n") else line + "\n")
            for record in records:
                stream.write(json.dumps(record, sort_keys=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, resolved)
    except BaseException:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
    return len(records)


# ---------------------------------------------------------------------------
# 4. READS
#
#    Reads are unrestricted for the steward (DNT-STW-001 Section 2: "Read all
#    logs, state files, taxonomy records, and shift records, in full, at any
#    time"). Roles receive only the slices their spec allows.
# ---------------------------------------------------------------------------


def read_memory() -> Dict[str, Any]:
    return _read_json(config.MEMORY_FILE)


def read_taxonomy() -> Dict[str, Any]:
    return _read_json(config.TAXONOMY_FILE)


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise TerrainStateError(
            "%s is missing — run initialize_terrain() before a shift"
            % os.path.basename(path)
        )
    try:
        with open(path, "r", encoding="utf-8") as stream:
            return json.load(stream)
    except json.JSONDecodeError as exc:
        raise TerrainStateError("%s is malformed: %s" % (os.path.basename(path), exc))


def read_log(path: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return log records, newest last. `limit` returns only the most recent N."""
    if not os.path.exists(path):
        return []
    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                raise TerrainStateError(
                    "%s line %d is not valid JSON — a record may have been "
                    "truncated by an interrupted commit"
                    % (os.path.basename(path), line_number)
                )
    if limit is not None and limit >= 0:
        return records[-limit:]
    return records


def read_recent_specimens(limit: int = config.NAMER_RECENT_SPECIMEN_WINDOW):
    """The capped window the Namer is shown.

    Never the full history. Unbounded context growth is the largest named risk
    to the budget (STARTUP_GUIDE.md Section 3.3), so the cap lives here rather
    than in the Namer's own judgment.
    """
    return read_log(config.SPECIMEN_LOG, limit=limit)


def read_anomalies(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    return read_log(config.ANOMALY_LOG, limit=limit)


def read_shift_log(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    return read_log(config.SHIFT_LOG, limit=limit)


# ---------------------------------------------------------------------------
# 5. TRANSACTION
#
#    Nothing touches disk until commit(). A shift that crashes, is interrupted,
#    or hits a budget ceiling mid-way simply never commits, and state/ is left
#    exactly as the last clean clock-out left it.
# ---------------------------------------------------------------------------


class Transaction(object):
    """Buffered, all-or-nothing changes to terrain state for one shift."""

    def __init__(self, shift_number: int) -> None:
        self.shift_number = shift_number
        self.memory: Dict[str, Any] = read_memory()
        self.taxonomy: Dict[str, Any] = read_taxonomy()
        self._specimen_records: List[Dict[str, Any]] = []
        self._anomaly_records: List[Dict[str, Any]] = []
        self._shift_records: List[Dict[str, Any]] = []
        self._committed = False
        self._aborted = False

    # -- buffered writes ----------------------------------------------------

    def append_specimen(self, record: Dict[str, Any]) -> None:
        self._require_open()
        self._specimen_records.append(self._stamp(record))

    def append_anomaly(self, record: Dict[str, Any]) -> None:
        self._require_open()
        self._anomaly_records.append(self._stamp(record))

    def append_shift_record(self, record: Dict[str, Any]) -> None:
        self._require_open()
        self._shift_records.append(self._stamp(record))

    def record_terrain_event(self, kind: str, detail: str) -> None:
        """Log a non-agentive occurrence, or a containment intervention.

        physics.md Section 7 keeps terrain events separate from specimen
        activity; DNT-STW-001 Section 5 requires any exercise of the containment
        exception to be logged in full rather than concealed.
        """
        self._require_open()
        self.memory.setdefault("terrain_events", []).append(
            {
                "shift": self.shift_number,
                "logged_at": _utc_now(),
                "kind": kind,
                "detail": detail,
            }
        )

    def _stamp(self, record: Dict[str, Any]) -> Dict[str, Any]:
        stamped = dict(record)
        stamped.setdefault("shift", self.shift_number)
        stamped.setdefault("logged_at", _utc_now())
        return stamped

    def _require_open(self) -> None:
        if self._committed:
            raise TerrainStateError("transaction already committed")
        if self._aborted:
            raise TerrainStateError("transaction was aborted")

    # -- introspection ------------------------------------------------------

    @property
    def pending(self) -> Dict[str, int]:
        return {
            "specimen_records": len(self._specimen_records),
            "anomaly_records": len(self._anomaly_records),
            "shift_records": len(self._shift_records),
        }

    # -- resolution ---------------------------------------------------------

    def abort(self) -> None:
        """Discard everything buffered. Disk is untouched."""
        self._aborted = True
        self._specimen_records = []
        self._anomaly_records = []
        self._shift_records = []

    def commit(self) -> Dict[str, int]:
        """Write the shift's changes. The only moment this terrain touches disk.

        Order matters. The append-only logs are written first, then taxonomy,
        then memory.json last. memory.json carries `last_committed_shift`, so it
        acts as the commit marker: if a machine dies between swaps, the logs may
        carry records from a shift memory.json has not yet acknowledged, and
        verify_integrity() reports exactly that rather than leaving it silent.
        """
        self._require_open()

        written = {
            "specimen_records": _append_lines_atomic(
                config.SPECIMEN_LOG, self._specimen_records
            ),
            "anomaly_records": _append_lines_atomic(
                config.ANOMALY_LOG, self._anomaly_records
            ),
            "shift_records": _append_lines_atomic(
                config.SHIFT_LOG, self._shift_records
            ),
        }

        _write_json_atomic(config.TAXONOMY_FILE, self.taxonomy)

        self.memory["last_committed_shift"] = self.shift_number
        self.memory["shifts_completed"] = int(
            self.memory.get("shifts_completed", 0)
        ) + 1
        _write_json_atomic(config.MEMORY_FILE, self.memory)

        self._committed = True
        return written


# ---------------------------------------------------------------------------
# 6. ROLE-SCOPED WRITERS
#
#    A role never receives the Transaction itself. It receives a view carrying
#    only the operations its spec permits. Generators cannot write at all —
#    they return substrate output and the shift loop records it — so a
#    replication-capable form arising in Generator output has no write
#    capability to hijack in the first place.
# ---------------------------------------------------------------------------


class _NoWriteAccess(object):
    """Handed to roles that produce output but never persist it."""

    __slots__ = ("role",)

    def __init__(self, role: str) -> None:
        self.role = role

    def __repr__(self) -> str:
        return "<no write access: %s>" % (self.role,)


class _ClassifierWriter(object):
    """The Namer's view: specimen records, anomaly records, its own taxonomy.

    It cannot write the shift log, cannot alter another role's records, and
    cannot address a path.
    """

    __slots__ = ("_txn", "role")

    def __init__(self, transaction: Transaction, role: str) -> None:
        self._txn = transaction
        self.role = role

    def append_specimen(self, record: Dict[str, Any]) -> None:
        record = dict(record)
        record["source_role"] = record.get("source_role") or self.role
        self._txn.append_specimen(record)

    def append_anomaly(self, record: Dict[str, Any]) -> None:
        record = dict(record)
        record["flagged_by"] = self.role
        self._txn.append_anomaly(record)

    @property
    def taxonomy_native(self) -> Dict[str, Any]:
        """The Namer's own system. Mutable by the Namer, by nothing else."""
        return self._txn.taxonomy.setdefault("native", {})

    def replace_taxonomy_native(self, structure: Dict[str, Any]) -> None:
        """Overwrite the native system with the Namer's own current version.

        Wholesale replacement rather than a merge, because a merge would impose
        a shape: it would require this module to decide what a category, a
        member, or a relation is. The Namer's system is stored exactly as the
        Namer authored it, whatever form that takes. That is what keeps the
        falsification condition (physics.md Section 11) genuinely testable —
        the terrain can only observe divergence from a flat list if the code
        never hardcoded a flat list to begin with.
        """
        self._txn.taxonomy["native"] = structure

    def note_revision(self, note: str) -> None:
        self._txn.taxonomy.setdefault("revisions", []).append(
            {"shift": self._txn.shift_number, "at": _utc_now(), "note": note}
        )


class _SummaryWriter(object):
    """The Keeper's view: the continuity summary, and nothing else."""

    __slots__ = ("_txn", "role")

    def __init__(self, transaction: Transaction, role: str) -> None:
        self._txn = transaction
        self.role = role

    def set_summary(self, summary: str) -> None:
        self._txn.memory["keeper_summary"] = {
            "shift": self._txn.shift_number,
            "at": _utc_now(),
            "text": summary,
        }


class _AnnotationWriter(object):
    """Archivist / Cartographer view: annotations only.

    Neither role may generate or reclassify (physics.md Sections 4.4, 4.5).
    The Archivist maintains the crosswalk and drift record; the Cartographer
    maintains the relational record. Neither can touch `native`.
    """

    __slots__ = ("_txn", "role", "_slot")

    def __init__(self, transaction: Transaction, role: str, slot: str) -> None:
        self._txn = transaction
        self.role = role
        self._slot = slot

    def write_annotation(self, payload: Dict[str, Any]) -> None:
        self._txn.memory.setdefault("annotations", {})[self._slot] = {
            "shift": self._txn.shift_number,
            "at": _utc_now(),
            "by": self.role,
            "payload": payload,
        }

    def read_taxonomy_native(self) -> Dict[str, Any]:
        """Read-only copy. The crosswalk never feeds back into the native system
        (DNT-CLS-001 Section 2)."""
        return json.loads(json.dumps(self._txn.taxonomy.get("native", {})))


def writer_for_role(transaction: Transaction, role: str):
    """Hand a role the narrowest write capability its function requires."""
    if role in ("generator_a", "generator_b"):
        return _NoWriteAccess(role)
    if role == "namer":
        return _ClassifierWriter(transaction, role)
    if role == "keeper":
        return _SummaryWriter(transaction, role)
    if role == "archivist":
        return _AnnotationWriter(transaction, role, "linnaean_crosswalk")
    if role == "cartographer":
        return _AnnotationWriter(transaction, role, "relational_record")
    raise ValueError("unknown role: %r" % (role,))


# ---------------------------------------------------------------------------
# 7. INTEGRITY
# ---------------------------------------------------------------------------


def verify_integrity() -> Tuple[bool, List[str]]:
    """Check state/ for the signature of an interrupted commit.

    Returns (clean, findings). Findings are reported, never auto-repaired —
    silently rewriting terrain records is exactly what DNT-STW-001 Section 3
    forbids.
    """
    findings: List[str] = []
    try:
        memory = read_memory()
        read_taxonomy()
    except TerrainStateError as exc:
        return False, [str(exc)]

    committed = int(memory.get("last_committed_shift", -1))
    for path in (config.SPECIMEN_LOG, config.ANOMALY_LOG, config.SHIFT_LOG):
        try:
            records = read_log(path)
        except TerrainStateError as exc:
            findings.append(str(exc))
            continue
        orphans = [r for r in records if int(r.get("shift", -1)) > committed]
        if orphans:
            findings.append(
                "%s holds %d record(s) from a shift beyond the last committed "
                "shift (%d) — an interrupted commit, not corruption. The "
                "records stand; the shift did not close."
                % (os.path.basename(path), len(orphans), committed)
            )

    stale = [
        name
        for name in os.listdir(config.STATE_DIR)
        if name.startswith(".stage-") and name.endswith(".tmp")
    ]
    if stale:
        findings.append(
            "%d staged temp file(s) left behind by an interrupted commit: %s"
            % (len(stale), ", ".join(sorted(stale)))
        )

    return (not findings), findings


# ---------------------------------------------------------------------------
# 8. STEWARD CONVENIENCE
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    created = initialize_terrain()
    for name in sorted(created):
        print("%-22s %s" % (name, "created" if created[name] else "present"))

    clean, findings = verify_integrity()
    print("")
    print("integrity: %s" % ("clean" if clean else "SEE FINDINGS"))
    for finding in findings:
        print("  - %s" % finding)

    memory = read_memory()
    print("")
    print("last committed shift : %s" % memory.get("last_committed_shift"))
    print("shifts completed     : %s" % memory.get("shifts_completed"))
    print("cumulative cost      : $%.4f" % float(memory.get("cumulative_cost_usd", 0.0)))
    print("specimen log entries : %d" % len(read_log(config.SPECIMEN_LOG)))
    print("anomaly log entries  : %d" % len(read_anomalies()))
