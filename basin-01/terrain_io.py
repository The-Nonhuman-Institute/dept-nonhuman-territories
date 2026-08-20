# SPDX-FileCopyrightText: 2026 U3 Labs, LLC
# SPDX-License-Identifier: Apache-2.0
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


def terrain_files() -> Tuple[str, ...]:
    """Every file a terrain must have. Read-only."""
    paths = [
        config.MEMORY_FILE,
        config.TAXONOMY_FILE,
        config.SPECIMEN_LOG,
        config.ANOMALY_LOG,
        config.SHIFT_LOG,
    ]
    field_log = getattr(config, "FIELD_LOG", None)
    if field_log:
        paths.append(field_log)
    return tuple(paths)


def missing_terrain_files() -> List[str]:
    """Which terrain files are absent. Reads only — creates nothing.

    Exists so that --status can report an uninitialised terrain instead of
    quietly seeding one, which is a write, and which on a half-present terrain
    means replacing the Namer's taxonomy with an empty one.
    """
    return [os.path.basename(p) for p in terrain_files() if not os.path.exists(p)]


def initialize_terrain() -> Dict[str, bool]:
    """Create any missing terrain file with a valid empty structure.

    Never overwrites, and refuses to seed a terrain that is only partly there.

    That second rule matters more than it looks. taxonomy.json holds the
    Namer's authored classification — the research data. If it alone goes
    missing (an aborted restore, a stray checkout), seeding it writes {} over
    a system that memory.json still describes as having dozens of nodes, and
    nothing downstream can tell the difference between "the Namer has not
    started" and "the Namer's work was destroyed". A partly-present terrain is
    a finding for the steward, not a gap to fill in.
    """
    present = [p for p in terrain_files() if os.path.exists(p)]
    absent = [p for p in terrain_files() if not os.path.exists(p)]
    if absent and present:
        populated = [
            os.path.basename(p) for p in present if os.path.getsize(p) > 0
        ]
        if populated:
            raise TerrainStateError(
                "this terrain is only partly present: %s missing, while %s "
                "already hold(s) data. Seeding the missing file(s) would write "
                "an empty structure beside a live record — if taxonomy.json is "
                "among them that discards the Namer's classification. Restore "
                "the missing file or start a new terrain; this will not guess."
                % (
                    ", ".join(os.path.basename(p) for p in absent),
                    ", ".join(populated),
                )
            )

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


def _fsync_directory(directory: str) -> None:
    """Flush a directory entry so a rename or creation survives power loss.

    Fsyncing a file guarantees its contents; it says nothing about whether the
    name pointing at it has reached the disk.
    """
    try:
        handle = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)


def _append_lines_atomic(path: str, records: Iterable[Dict[str, Any]]) -> int:
    """Append records to an append-only log.

    The file is opened O_APPEND, so the kernel positions every write at the
    current end of the file as one indivisible step. A second process
    committing at the same moment lands its records *after* these; it cannot
    overwrite them. The whole payload goes out in a single write() call, so a
    record can never be split in half by another writer.

    This deliberately does not copy the file. An earlier version staged a
    rewritten copy and renamed it over the top, which is a read-modify-write:
    two overlapping commits each read N lines and each replaced the file, so
    whichever landed second silently deleted the other's records while
    reporting success. Append-only has to be enforced by the write itself.
    """
    resolved = _guard(path)
    if resolved not in {os.path.realpath(p) for p in _APPEND_ONLY_FILES}:
        raise ContainmentError("not an append-only log: %r" % (path,))

    records = list(records)
    if not records:
        return 0

    payload = "".join(
        json.dumps(record, sort_keys=False) + "\n" for record in records
    ).encode("utf-8")

    handle = os.open(resolved, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        written = os.write(handle, payload)
        if written != len(payload):
            raise TerrainStateError(
                "short write appending to %s: %d of %d bytes reached the disk. "
                "The log may end in a torn record; do not run another shift "
                "until it has been inspected."
                % (os.path.basename(resolved), written, len(payload))
            )
        os.fsync(handle)
    finally:
        os.close(handle)

    _fsync_directory(os.path.dirname(resolved))
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


def read_recent_specimens(limit: Optional[int] = None):
    """The capped window the Namer is shown.

    Never the full history. Unbounded context growth is the largest named risk
    to the budget (STARTUP_GUIDE.md Section 3.3), so the cap lives here rather
    than in the Namer's own judgment.
    """
    if limit is None:
        limit = config.namer_window()
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

    def commit(self, mark_shift: bool = True) -> Dict[str, int]:
        """Write the shift's changes. The only moment this terrain touches disk.

        mark_shift=False records state without advancing the shift counter. It
        exists for one case: a shift that failed before it could close still
        needs its failure on the record (the Charter forbids omitting an
        outcome because it is inconvenient), but it did not produce a shift of
        terrain history and must not claim a shift number.

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

        if mark_shift:
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


def integrity_findings() -> List[Tuple[str, str]]:
    """Every integrity finding, each tagged "blocking" or "standing".

    The distinction is what a finding means for the *next* shift, not how
    serious it is:

      blocking  the next shift number is ambiguous, or a commit is in flight.
                Running would write over an open question.
      standing  a fact about what has already happened to this record. It is
                reported every time and never quietly dropped, but it does not
                make the next shift ambiguous, so it does not stop one.

    Duplicate shifts are the case that forced the split. They are permanent
    scars from a past concurrency incident — already logged as terrain events —
    and treating them as blocking would wedge three terrains for good.

    Findings are reported, never auto-repaired: silently rewriting terrain
    records is exactly what DNT-STW-001 Section 3 forbids.
    """
    findings: List[Tuple[str, str]] = []

    def note(severity: str, message: str) -> None:
        findings.append((severity, message))

    try:
        memory = read_memory()
        read_taxonomy()
    except TerrainStateError as exc:
        return [("blocking", str(exc))]

    committed = int(memory.get("last_committed_shift", -1))

    logs = [config.SPECIMEN_LOG, config.ANOMALY_LOG, config.SHIFT_LOG]
    field_log = getattr(config, "FIELD_LOG", None)
    if field_log:
        logs.append(field_log)

    for path in logs:
        try:
            records = read_log(path)
        except TerrainStateError as exc:
            findings.append(str(exc))
            continue
        orphans = [r for r in records if int(r.get("shift", -1)) > committed]
        if orphans:
            note('blocking',
                "%s holds %d record(s) from a shift beyond the last committed "
                "shift (%d) — an interrupted commit, not corruption. The "
                "records stand; the shift did not close."
                % (os.path.basename(path), len(orphans), committed)
            )

    # The three checks below all read the shift log, which is the one file with
    # exactly one record per shift. Everything above asks whether the logs have
    # run ahead of memory; these ask the other three questions that can be asked
    # of the same pair, and that an earlier version of this function could not
    # see at all.
    try:
        shift_rows = read_log(config.SHIFT_LOG)
    except TerrainStateError:
        shift_rows = None

    if shift_rows is not None:
        numbers = [int(r.get("shift", -1)) for r in shift_rows if r.get("shift") is not None]
        distinct = sorted(set(numbers))

        # (a) memory ahead of the record. The orphan test above only looks the
        # other way, so a shift log that has lost records to a bad commit reads
        # as clean while its history silently disappears.
        if distinct and committed > distinct[-1]:
            note('blocking',
                "memory.json says shift %d was committed, but the shift log ends "
                "at %d — %d shift(s) are missing from the record. Do not run "
                "another shift; the next one would be numbered over the gap."
                % (committed, distinct[-1], committed - distinct[-1])
            )

        # (b) the same shift committed twice. This is the exact condition two
        # concurrent shifts produce, and it was invisible here until now.
        repeats = sorted(n for n in distinct if numbers.count(n) > 1)
        if repeats:
            note('standing',
                "%d shift number(s) appear more than once in the shift log: %s. "
                "Two shifts ran at the same time and both committed. The "
                "duplicate records stand — they are part of the record — but "
                "every count taken over this log is inflated."
                % (len(repeats), ", ".join(str(n) for n in repeats))
            )

        # (c) the counter and the record disagreeing. shifts_completed is
        # incremented once per commit, so it should equal the number of distinct
        # shifts. Where it does not, memory.json lost a write.
        completed = memory.get("shifts_completed")
        if completed is not None and numbers and int(completed) != len(numbers):
            note('standing',
                "memory.json counts %d shift(s) completed but the shift log "
                "holds %d record(s). The counter is incremented once per commit "
                "and each commit appends exactly one record, so these cannot "
                "legitimately differ. The counter travels in the same snapshot "
                "as the rest of memory, so this is the visible edge of a lost "
                "update — other fields were overwritten the same way."
                % (int(completed), len(numbers))
            )

    # Staged temp files are left in the directory of the file being written, so
    # looking only in state/ misses every interrupted shift-log commit.
    stage_dirs = [config.STATE_DIR]
    shifts_dir = os.path.dirname(config.SHIFT_LOG)
    if os.path.realpath(shifts_dir) != os.path.realpath(config.STATE_DIR):
        stage_dirs.append(shifts_dir)

    stale = []
    for directory in stage_dirs:
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if name.startswith(".stage-") and name.endswith(".tmp"):
                stale.append(os.path.join(os.path.basename(directory), name))
    if stale:
        note('blocking',
            "%d staged temp file(s) left behind by an interrupted commit: %s"
            % (len(stale), ", ".join(sorted(stale)))
        )

    return findings


def verify_integrity() -> Tuple[bool, List[str]]:
    """Returns (clean, findings) over every finding, blocking or standing."""
    findings = integrity_findings()
    return (not findings), [message for _, message in findings]


def blockingintegrity_findings() -> List[str]:
    """Only the findings that make the next shift unsafe to run."""
    return [message for severity, message in integrity_findings()
            if severity == "blocking"]


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
