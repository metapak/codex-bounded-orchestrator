"""SQLite repository adapter with revision-guarded editorial and publish transitions."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .domain import Draft, DraftStatus, EvidenceError, EvidenceRecord, InvalidTransitionError, RawResearchItem, ResearchItem, StaleRevisionError, VerificationStatus, utc_now
from .ports import ModelResponse

_LOCKED_STATUSES = {DraftStatus.PUBLISHING.value, DraftStatus.PUBLISHED.value, DraftStatus.PUBLISH_FAILED.value, DraftStatus.PUBLISH_UNKNOWN.value}
_DUPLICATE_PUBLISH_ERROR = "Duplicate content has already been claimed for publishing."


def _utc_timestamp(value: str, *, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an offset-aware ISO timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be an offset-aware ISO timestamp.")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


class SQLiteRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._db() as db:
            migrations = sorted((Path(__file__).with_name("migrations")).glob("[0-9][0-9][0-9]_*.sql"))
            try:
                row = db.execute("SELECT MAX(version) AS version FROM schema_version").fetchone()
                current = int(row["version"] or 0)
            except sqlite3.OperationalError:
                current = 0
            for migration in migrations:
                version = int(migration.name.split("_", 1)[0])
                if version > current:
                    db.executescript(migration.read_text(encoding="utf-8"))
                    current = version

    def add_research(self, item: RawResearchItem, canonical_url: str, fingerprint: str) -> tuple[int, bool]:
        with self._write() as db:
            existing = db.execute("SELECT id FROM research_items WHERE fingerprint=? OR (source=? AND external_id=?)", (fingerprint, item.source, item.external_id)).fetchone()
            if existing:
                return int(existing["id"]), False
            cursor = db.execute("INSERT INTO research_items(source,external_id,title,canonical_url,excerpt,fingerprint,author,published_at,discovered_at) VALUES(?,?,?,?,?,?,?,?,?)", (item.source, item.external_id, item.title, canonical_url, item.excerpt, fingerprint, item.author, item.published_at, utc_now()))
            return int(cursor.lastrowid), True

    def add_evidence(self, research_item_id: int, source_url: str, excerpt: str, evidence_type: str = "source_excerpt") -> int:
        digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        with self._write() as db:
            cursor = db.execute("INSERT INTO evidence_records(research_item_id,source_url,excerpt,content_hash,captured_at,evidence_type) VALUES(?,?,?,?,?,?)", (research_item_id, source_url, excerpt, digest, utc_now(), evidence_type))
            return int(cursor.lastrowid)

    def get_evidence(self, evidence_id: int) -> EvidenceRecord | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM evidence_records WHERE id=?", (evidence_id,)).fetchone()
        return EvidenceRecord(**dict(row)) if row else None

    def list_evidence(self, research_item_id: int) -> list[EvidenceRecord]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM evidence_records WHERE research_item_id=? ORDER BY id", (research_item_id,)).fetchall()
        return [EvidenceRecord(**dict(row)) for row in rows]

    @staticmethod
    def _research(row: sqlite3.Row) -> ResearchItem:
        return ResearchItem(**dict(row))

    def list_research(self, status: str | None = None) -> list[ResearchItem]:
        query, params = ("SELECT * FROM research_items ORDER BY id DESC", ()) if status is None else ("SELECT * FROM research_items WHERE status=? ORDER BY id", (status,))
        with self._db() as db:
            rows = db.execute(query, params).fetchall()
        return [self._research(row) for row in rows]

    def get_research(self, research_item_id: int) -> ResearchItem | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM research_items WHERE id=?", (research_item_id,)).fetchone()
        return self._research(row) if row else None

    def update_research_analysis(self, research_item_id: int, *, summary: str, category: str, confidence: float, status: str, near_duplicate_key: str | None = None) -> None:
        with self._write() as db:
            db.execute("UPDATE research_items SET summary=?,category=?,confidence=?,status=?,near_duplicate_key=? WHERE id=?", (summary, category, confidence, status, near_duplicate_key, research_item_id))

    def replace_research_claims(self, research_item_id: int, claims: list[dict[str, Any]]) -> None:
        with self._write() as db:
            db.execute("DELETE FROM research_claims WHERE research_item_id=?", (research_item_id,))
            for index, claim in enumerate(claims):
                db.execute("INSERT INTO research_claims(research_item_id,claim_index,text,kind,evidence_ids) VALUES(?,?,?,?,?)", (research_item_id, index, str(claim["text"]), str(claim["kind"]), json.dumps(claim["evidence_ids"])))

    def list_research_claims(self, research_item_id: int) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM research_claims WHERE research_item_id=? ORDER BY claim_index", (research_item_id,)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["evidence_ids"] = json.loads(item["evidence_ids"])
            result.append(item)
        return result

    def create_draft(self, *, text: str, category: str, confidence: float, factual_risk: str, verification_status: str, research_item_id: int, provider: str, model: str, prompt_version: str, claims: list[dict[str, Any]], rejection_reason: str | None = None, hook_type: str | None = None, post_structure: str | None = None, source_type: str | None = None) -> int:
        now = utc_now()
        status = DraftStatus.PENDING.value if verification_status == VerificationStatus.SUPPORTED.value else DraftStatus.REJECTED.value
        with self._write() as db:
            cursor = db.execute("INSERT INTO drafts(text,category,status,confidence,factual_risk,verification_status,research_item_id,provider,model,prompt_version,created_at,updated_at,rejection_reason,hook_type,post_structure,source_type) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (text, category, status, confidence, factual_risk, verification_status, research_item_id, provider, model, prompt_version, now, now, rejection_reason, hook_type, post_structure, source_type))
            draft_id = int(cursor.lastrowid)
            self._replace_claims(db, draft_id, claims)
            db.execute("INSERT INTO draft_revisions(draft_id,revision,text,verification_status,changed_at) VALUES(?,?,?,?,?)", (draft_id, 1, text, verification_status, now))
        return draft_id

    @staticmethod
    def _replace_claims(db: sqlite3.Connection, draft_id: int, claims: list[dict[str, Any]]) -> None:
        db.execute("DELETE FROM claims WHERE draft_id=?", (draft_id,))
        for index, claim in enumerate(claims):
            supported = None if claim.get("supported") is None else int(bool(claim["supported"]))
            db.execute("INSERT INTO claims(draft_id,claim_index,text,kind,evidence_ids,supported,note) VALUES(?,?,?,?,?,?,?)", (draft_id, index, str(claim["text"]), str(claim.get("kind", "factual")), json.dumps(claim.get("evidence_ids", [])), supported, claim.get("note")))

    @staticmethod
    def _draft(row: sqlite3.Row) -> Draft:
        data = dict(row)
        data["status"] = DraftStatus(data["status"])
        data["verification_status"] = VerificationStatus(data["verification_status"])
        return Draft(**data)

    @staticmethod
    def _check_revision(row: sqlite3.Row, expected_revision: int) -> None:
        if int(row["revision"]) != expected_revision:
            raise StaleRevisionError("Draft was changed by another request.")

    @staticmethod
    def _check_mutable(row: sqlite3.Row) -> None:
        if row["status"] in _LOCKED_STATUSES or row["publish_attempted_at"] is not None:
            raise InvalidTransitionError("Draft cannot be changed after publishing has been claimed.")

    @staticmethod
    def _record_revision(db: sqlite3.Connection, draft_id: int, revision: int, changed_at: str) -> None:
        db.execute("INSERT INTO draft_revisions(draft_id,revision,text,verification_status,changed_at) SELECT id,revision,text,verification_status,? FROM drafts WHERE id=? AND revision=?", (changed_at, draft_id, revision))

    def get_draft(self, draft_id: int) -> Draft | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        return self._draft(row) if row else None

    def list_drafts(self) -> list[Draft]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM drafts ORDER BY id DESC").fetchall()
        return [self._draft(row) for row in rows]

    def list_claims(self, draft_id: int) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM claims WHERE draft_id=? ORDER BY claim_index", (draft_id,)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["evidence_ids"] = json.loads(item["evidence_ids"])
            item["supported"] = None if item["supported"] is None else bool(item["supported"])
            result.append(item)
        return result

    def edit_draft(self, draft_id: int, text: str, expected_revision: int) -> Draft:
        clean = text.strip()
        if not clean:
            raise ValueError("Draft text cannot be empty.")
        with self._write() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            self._check_revision(row, expected_revision)
            self._check_mutable(row)
            revision = expected_revision + 1
            verification = row["verification_status"] if clean == row["text"] else VerificationStatus.UNVERIFIED.value
            now = utc_now()
            cursor = db.execute("UPDATE drafts SET text=?,revision=?,status=?,verification_status=?,updated_at=?,rejection_reason=NULL,approved_at=NULL,rejected_at=NULL,scheduled_at=NULL,publish_error=NULL WHERE id=? AND revision=?", (clean, revision, DraftStatus.PENDING.value, verification, now, draft_id, expected_revision))
            if cursor.rowcount != 1:
                raise StaleRevisionError("Draft was changed by another request.")
            self._record_revision(db, draft_id, revision, now)
        return self.get_draft(draft_id)  # type: ignore[return-value]

    def replace_claims_and_verification(self, draft_id: int, claims: list[dict[str, Any]], verification_status: str, expected_revision: int) -> Draft:
        verification = VerificationStatus(verification_status)
        with self._write() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            self._check_revision(row, expected_revision)
            self._check_mutable(row)
            self._replace_claims(db, draft_id, claims)
            revision = expected_revision + 1
            now = utc_now()
            status = DraftStatus.PENDING.value if verification is VerificationStatus.SUPPORTED else DraftStatus.REJECTED.value
            rejection = None if status == DraftStatus.PENDING.value else "Evidence verification failed."
            cursor = db.execute("UPDATE drafts SET verification_status=?,status=?,revision=?,updated_at=?,rejection_reason=?,approved_at=NULL,rejected_at=?,scheduled_at=NULL,publish_error=NULL WHERE id=? AND revision=?", (verification.value, status, revision, now, rejection, now if status == DraftStatus.REJECTED.value else None, draft_id, expected_revision))
            if cursor.rowcount != 1:
                raise StaleRevisionError("Draft was changed by another request.")
            self._record_revision(db, draft_id, revision, now)
        return self.get_draft(draft_id)  # type: ignore[return-value]

    def set_draft_status(self, draft_id: int, status: str, expected_revision: int, reason: str | None = None) -> Draft:
        target = DraftStatus(status)
        if target not in {DraftStatus.APPROVED, DraftStatus.REJECTED}:
            raise InvalidTransitionError(f"Unsupported editorial state {target.value}.")
        with self._write() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            self._check_revision(row, expected_revision)
            self._check_mutable(row)
            if target is DraftStatus.APPROVED and row["verification_status"] != VerificationStatus.SUPPORTED.value:
                raise EvidenceError("Draft cannot be approved until evidence verification passes.")
            if row["status"] == target.value:
                raise InvalidTransitionError(f"Draft is already {target.value}.")
            revision = expected_revision + 1
            now = utc_now()
            cursor = db.execute("UPDATE drafts SET status=?,revision=?,rejection_reason=?,updated_at=?,approved_at=?,rejected_at=?,scheduled_at=NULL,publish_error=NULL WHERE id=? AND revision=?", (target.value, revision, reason if target is DraftStatus.REJECTED else None, now, now if target is DraftStatus.APPROVED else None, now if target is DraftStatus.REJECTED else None, draft_id, expected_revision))
            if cursor.rowcount != 1:
                raise StaleRevisionError("Draft was changed by another request.")
            self._record_revision(db, draft_id, revision, now)
        return self.get_draft(draft_id)  # type: ignore[return-value]

    def schedule_draft(self, draft_id: int, scheduled_at: str, expected_revision: int) -> Draft:
        scheduled = _utc_timestamp(scheduled_at, field="scheduled_at")
        with self._write() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            self._check_revision(row, expected_revision)
            self._check_mutable(row)
            if row["status"] != DraftStatus.APPROVED.value or row["verification_status"] != VerificationStatus.SUPPORTED.value or row["approved_at"] is None:
                raise InvalidTransitionError("Only a supported, human-approved draft can be scheduled.")
            revision = expected_revision + 1
            now = utc_now()
            cursor = db.execute("UPDATE drafts SET status=?,revision=?,scheduled_at=?,updated_at=? WHERE id=? AND revision=?", (DraftStatus.SCHEDULED.value, revision, scheduled, now, draft_id, expected_revision))
            if cursor.rowcount != 1:
                raise StaleRevisionError("Draft was changed by another request.")
            self._record_revision(db, draft_id, revision, now)
        return self.get_draft(draft_id)  # type: ignore[return-value]

    def list_due_drafts(self, now: str) -> list[Draft]:
        due = _utc_timestamp(now, field="now")
        with self._db() as db:
            rows = db.execute("SELECT * FROM drafts WHERE status=? AND scheduled_at<=? AND publish_attempted_at IS NULL ORDER BY scheduled_at,id", (DraftStatus.SCHEDULED.value, due)).fetchall()
        return [self._draft(row) for row in rows]

    def claim_publish(self, draft_id: int, expected_revision: int, *, scheduled_only: bool = False, now: str | None = None) -> Draft | None:
        attempted_at = _utc_timestamp(now, field="now") if now is not None else utc_now()
        with self._write() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            self._check_revision(row, expected_revision)
            if row["publish_attempted_at"] is not None or row["status"] in _LOCKED_STATUSES:
                return None
            eligible = {DraftStatus.SCHEDULED.value} if scheduled_only else {DraftStatus.APPROVED.value}
            if row["status"] not in eligible:
                return None
            if scheduled_only and (row["scheduled_at"] is None or row["scheduled_at"] > attempted_at):
                return None
            if row["verification_status"] != VerificationStatus.SUPPORTED.value or row["approved_at"] is None:
                return None
            digest = hashlib.sha256(str(row["text"]).encode("utf-8")).hexdigest()
            claim = db.execute("INSERT OR IGNORE INTO publish_claims(content_hash,draft_id,claimed_at) VALUES(?,?,?)", (digest, draft_id, attempted_at))
            revision = expected_revision + 1
            if claim.rowcount != 1:
                db.execute("UPDATE drafts SET status=?,revision=?,publish_attempted_at=?,publish_error=?,updated_at=? WHERE id=? AND revision=?", (DraftStatus.PUBLISH_FAILED.value, revision, attempted_at, _DUPLICATE_PUBLISH_ERROR, attempted_at, draft_id, expected_revision))
                self._record_revision(db, draft_id, revision, attempted_at)
                return None
            cursor = db.execute("UPDATE drafts SET status=?,revision=?,publish_attempted_at=?,publish_error=NULL,updated_at=? WHERE id=? AND revision=?", (DraftStatus.PUBLISHING.value, revision, attempted_at, attempted_at, draft_id, expected_revision))
            if cursor.rowcount != 1:
                raise StaleRevisionError("Draft was changed by another request.")
            self._record_revision(db, draft_id, revision, attempted_at)
        return self.get_draft(draft_id)

    def finish_publish(self, draft_id: int, *, post_id: str | None = None, error: str | None = None, ambiguous: bool = False) -> Draft:
        clean_post_id = post_id.strip() if post_id else None
        if clean_post_id and (error or ambiguous):
            raise ValueError("A publish result cannot contain both success and failure fields.")
        if not clean_post_id and not error:
            raise ValueError("A publish result requires a post id or an error.")
        with self._write() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            if row["status"] != DraftStatus.PUBLISHING.value or row["publish_attempted_at"] is None:
                raise InvalidTransitionError("Only a claimed publishing draft can be finished.")
            now = utc_now()
            revision = int(row["revision"]) + 1
            if clean_post_id:
                status, publish_error, published_at = DraftStatus.PUBLISHED.value, None, now
            else:
                status = DraftStatus.PUBLISH_UNKNOWN.value if ambiguous else DraftStatus.PUBLISH_FAILED.value
                publish_error, published_at = str(error)[:240], None
            cursor = db.execute("UPDATE drafts SET status=?,revision=?,published_at=?,x_post_id=?,publish_error=?,updated_at=? WHERE id=? AND status=? AND revision=?", (status, revision, published_at, clean_post_id, publish_error, now, draft_id, DraftStatus.PUBLISHING.value, row["revision"]))
            if cursor.rowcount != 1:
                raise InvalidTransitionError("Publish result was already recorded.")
            self._record_revision(db, draft_id, revision, now)
        return self.get_draft(draft_id)  # type: ignore[return-value]

    def create_run(self, kind: str) -> int:
        with self._write() as db:
            cursor = db.execute("INSERT INTO pipeline_runs(kind,status,started_at) VALUES(?,?,?)", (kind, "running", utc_now()))
            return int(cursor.lastrowid)

    def finish_run(self, run_id: int, status: str, detail: dict[str, Any]) -> None:
        with self._write() as db:
            db.execute("UPDATE pipeline_runs SET status=?,finished_at=?,detail=? WHERE id=?", (status, utc_now(), json.dumps(detail, sort_keys=True), run_id))

    def record_model_call(self, run_id: int | None, role: str, response: ModelResponse, prompt_version: str) -> None:
        with self._write() as db:
            db.execute("INSERT INTO model_calls(run_id,role,provider,model,response_id,input_tokens,output_tokens,cached_input_tokens,cache_write_tokens,estimated_cost_usd,cost_provenance,prompt_version,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (run_id, role, response.provider, response.model, response.response_id, response.input_tokens, response.output_tokens, response.cached_input_tokens, response.cache_write_tokens, response.estimated_cost_usd, response.cost_provenance, prompt_version, utc_now()))

    def list_model_calls(self, run_id: int | None = None) -> list[dict[str, Any]]:
        query, params = ("SELECT * FROM model_calls ORDER BY id", ()) if run_id is None else ("SELECT * FROM model_calls WHERE run_id=? ORDER BY id", (run_id,))
        with self._db() as db:
            return [dict(row) for row in db.execute(query, params).fetchall()]

    def claim_job_slot(self, job_name: str, slot: str) -> bool:
        with self._write() as db:
            cursor = db.execute("INSERT OR IGNORE INTO job_slots(job_name,slot,status,claimed_at) VALUES(?,?,?,?)", (job_name, slot, "running", utc_now()))
            return cursor.rowcount == 1

    def finish_job_slot(self, job_name: str, slot: str, status: str) -> None:
        with self._write() as db:
            cursor = db.execute("UPDATE job_slots SET status=?,finished_at=? WHERE job_name=? AND slot=?", (status, utc_now(), job_name, slot))
            if cursor.rowcount != 1:
                raise KeyError((job_name, slot))

    def healthcheck(self) -> bool:
        try:
            with self._db() as db:
                return db.execute("SELECT 1").fetchone()[0] == 1
        except Exception:
            return False
