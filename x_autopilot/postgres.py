"""PostgreSQL repository adapter with the same domain contract as SQLite."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from .domain import Draft, DraftStatus, EvidenceError, EvidenceRecord, InvalidTransitionError, RawResearchItem, ResearchItem, StaleRevisionError, VerificationStatus, utc_now
from .ports import ModelResponse
from .storage import _DUPLICATE_PUBLISH_ERROR, _LOCKED_STATUSES, _utc_timestamp


class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def _connect(self) -> Connection[dict[str, Any]]:
        return psycopg.connect(self._database_url, row_factory=dict_row, connect_timeout=10)

    @contextmanager
    def _db(self) -> Iterator[Connection[dict[str, Any]]]:
        with self._connect() as connection:
            connection.execute("SET LOCAL statement_timeout = '30s'")
            yield connection

    def initialize(self) -> None:
        migrations = sorted((Path(__file__).with_name("postgres_migrations")).glob("[0-9][0-9][0-9]_*.sql"))
        with self._db() as db:
            db.execute("SELECT pg_advisory_xact_lock(869733042118)")
            exists = db.execute("SELECT to_regclass('schema_version') IS NOT NULL AS present").fetchone()["present"]
            current = int(db.execute("SELECT COALESCE(MAX(version),0) AS version FROM schema_version").fetchone()["version"]) if exists else 0
            for migration in migrations:
                version = int(migration.name.split("_", 1)[0])
                if version > current:
                    db.execute(migration.read_text(encoding="utf-8"))
                    current = version

    @staticmethod
    def _draft(row: dict[str, Any]) -> Draft:
        data = dict(row)
        data["status"] = DraftStatus(data["status"])
        data["verification_status"] = VerificationStatus(data["verification_status"])
        return Draft(**data)

    @staticmethod
    def _research(row: dict[str, Any]) -> ResearchItem:
        return ResearchItem(**dict(row))

    @staticmethod
    def _check_revision(row: dict[str, Any], expected_revision: int) -> None:
        if int(row["revision"]) != expected_revision:
            raise StaleRevisionError("Draft was changed by another request.")

    @staticmethod
    def _check_mutable(row: dict[str, Any]) -> None:
        if row["status"] in _LOCKED_STATUSES or row["publish_attempted_at"] is not None:
            raise InvalidTransitionError("Draft cannot be changed after publishing has been claimed.")

    @staticmethod
    def _record_revision(db: Connection[dict[str, Any]], draft_id: int, revision: int, changed_at: str) -> None:
        db.execute("INSERT INTO draft_revisions(draft_id,revision,text,verification_status,changed_at) SELECT id,revision,text,verification_status,%s FROM drafts WHERE id=%s AND revision=%s", (changed_at, draft_id, revision))

    @staticmethod
    def _replace_claims(db: Connection[dict[str, Any]], draft_id: int, claims: list[dict[str, Any]]) -> None:
        db.execute("DELETE FROM claims WHERE draft_id=%s", (draft_id,))
        for index, claim in enumerate(claims):
            supported = None if claim.get("supported") is None else bool(claim["supported"])
            db.execute("INSERT INTO claims(draft_id,claim_index,text,kind,evidence_ids,supported,note) VALUES(%s,%s,%s,%s,%s,%s,%s)", (draft_id, index, str(claim["text"]), str(claim.get("kind", "factual")), json.dumps(claim.get("evidence_ids", [])), supported, claim.get("note")))

    def add_research(self, item: RawResearchItem, canonical_url: str, fingerprint: str) -> tuple[int, bool]:
        with self._db() as db:
            row = db.execute("INSERT INTO research_items(source,external_id,title,canonical_url,excerpt,fingerprint,author,published_at,discovered_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id", (item.source, item.external_id, item.title, canonical_url, item.excerpt, fingerprint, item.author, item.published_at, utc_now())).fetchone()
            if row:
                return int(row["id"]), True
            existing = db.execute("SELECT id FROM research_items WHERE fingerprint=%s OR (source=%s AND external_id=%s)", (fingerprint, item.source, item.external_id)).fetchone()
            if not existing:
                raise RuntimeError("Research deduplication conflict could not be resolved.")
            return int(existing["id"]), False

    def add_evidence(self, research_item_id: int, source_url: str, excerpt: str, evidence_type: str = "source_excerpt") -> int:
        digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        with self._db() as db:
            row = db.execute("INSERT INTO evidence_records(research_item_id,source_url,excerpt,content_hash,captured_at,evidence_type) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id", (research_item_id, source_url, excerpt, digest, utc_now(), evidence_type)).fetchone()
            return int(row["id"])

    def get_evidence(self, evidence_id: int) -> EvidenceRecord | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM evidence_records WHERE id=%s", (evidence_id,)).fetchone()
        return EvidenceRecord(**row) if row else None

    def list_evidence(self, research_item_id: int) -> list[EvidenceRecord]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM evidence_records WHERE research_item_id=%s ORDER BY id", (research_item_id,)).fetchall()
        return [EvidenceRecord(**row) for row in rows]

    def list_research(self, status: str | None = None) -> list[ResearchItem]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM research_items ORDER BY id DESC").fetchall() if status is None else db.execute("SELECT * FROM research_items WHERE status=%s ORDER BY id", (status,)).fetchall()
        return [self._research(row) for row in rows]

    def get_research(self, research_item_id: int) -> ResearchItem | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM research_items WHERE id=%s", (research_item_id,)).fetchone()
        return self._research(row) if row else None

    def update_research_analysis(self, research_item_id: int, *, summary: str, category: str, confidence: float, status: str, near_duplicate_key: str | None = None) -> None:
        with self._db() as db:
            db.execute("UPDATE research_items SET summary=%s,category=%s,confidence=%s,status=%s,near_duplicate_key=%s WHERE id=%s", (summary, category, confidence, status, near_duplicate_key, research_item_id))

    def replace_research_claims(self, research_item_id: int, claims: list[dict[str, Any]]) -> None:
        with self._db() as db:
            db.execute("DELETE FROM research_claims WHERE research_item_id=%s", (research_item_id,))
            for index, claim in enumerate(claims):
                db.execute("INSERT INTO research_claims(research_item_id,claim_index,text,kind,evidence_ids) VALUES(%s,%s,%s,%s,%s)", (research_item_id, index, str(claim["text"]), str(claim["kind"]), json.dumps(claim["evidence_ids"])))

    def list_research_claims(self, research_item_id: int) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM research_claims WHERE research_item_id=%s ORDER BY claim_index", (research_item_id,)).fetchall()
        for item in rows:
            item["evidence_ids"] = json.loads(item["evidence_ids"])
        return rows

    def create_draft(self, *, text: str, category: str, confidence: float, factual_risk: str, verification_status: str, research_item_id: int, provider: str, model: str, prompt_version: str, claims: list[dict[str, Any]], rejection_reason: str | None = None, hook_type: str | None = None, post_structure: str | None = None, source_type: str | None = None) -> int:
        now = utc_now()
        status = DraftStatus.PENDING.value if verification_status == VerificationStatus.SUPPORTED.value else DraftStatus.REJECTED.value
        with self._db() as db:
            row = db.execute("INSERT INTO drafts(text,category,status,confidence,factual_risk,verification_status,research_item_id,provider,model,prompt_version,created_at,updated_at,rejection_reason,hook_type,post_structure,source_type) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id", (text, category, status, confidence, factual_risk, verification_status, research_item_id, provider, model, prompt_version, now, now, rejection_reason, hook_type, post_structure, source_type)).fetchone()
            draft_id = int(row["id"])
            self._replace_claims(db, draft_id, claims)
            db.execute("INSERT INTO draft_revisions(draft_id,revision,text,verification_status,changed_at) VALUES(%s,%s,%s,%s,%s)", (draft_id, 1, text, verification_status, now))
            return draft_id

    def get_draft(self, draft_id: int) -> Draft | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=%s", (draft_id,)).fetchone()
        return self._draft(row) if row else None

    def list_drafts(self) -> list[Draft]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM drafts ORDER BY id DESC").fetchall()
        return [self._draft(row) for row in rows]

    def list_claims(self, draft_id: int) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM claims WHERE draft_id=%s ORDER BY claim_index", (draft_id,)).fetchall()
        for item in rows:
            item["evidence_ids"] = json.loads(item["evidence_ids"])
        return rows

    def edit_draft(self, draft_id: int, text: str, expected_revision: int) -> Draft:
        clean = text.strip()
        if not clean:
            raise ValueError("Draft text cannot be empty.")
        with self._db() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=%s FOR UPDATE", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            self._check_revision(row, expected_revision); self._check_mutable(row)
            revision, now = expected_revision + 1, utc_now()
            verification = row["verification_status"] if clean == row["text"] else VerificationStatus.UNVERIFIED.value
            db.execute("UPDATE drafts SET text=%s,revision=%s,status=%s,verification_status=%s,updated_at=%s,rejection_reason=NULL,approved_at=NULL,rejected_at=NULL,scheduled_at=NULL,publish_error=NULL WHERE id=%s", (clean, revision, DraftStatus.PENDING.value, verification, now, draft_id))
            self._record_revision(db, draft_id, revision, now)
        return self.get_draft(draft_id)  # type: ignore[return-value]

    def replace_claims_and_verification(self, draft_id: int, claims: list[dict[str, Any]], verification_status: str, expected_revision: int) -> Draft:
        verification = VerificationStatus(verification_status)
        with self._db() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=%s FOR UPDATE", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            self._check_revision(row, expected_revision); self._check_mutable(row)
            self._replace_claims(db, draft_id, claims)
            revision, now = expected_revision + 1, utc_now()
            status = DraftStatus.PENDING.value if verification is VerificationStatus.SUPPORTED else DraftStatus.REJECTED.value
            rejection = None if status == DraftStatus.PENDING.value else "Evidence verification failed."
            db.execute("UPDATE drafts SET verification_status=%s,status=%s,revision=%s,updated_at=%s,rejection_reason=%s,approved_at=NULL,rejected_at=%s,scheduled_at=NULL,publish_error=NULL WHERE id=%s", (verification.value, status, revision, now, rejection, now if status == DraftStatus.REJECTED.value else None, draft_id))
            self._record_revision(db, draft_id, revision, now)
        return self.get_draft(draft_id)  # type: ignore[return-value]

    def set_draft_status(self, draft_id: int, status: str, expected_revision: int, reason: str | None = None) -> Draft:
        target = DraftStatus(status)
        if target not in {DraftStatus.APPROVED, DraftStatus.REJECTED}:
            raise InvalidTransitionError(f"Unsupported editorial state {target.value}.")
        with self._db() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=%s FOR UPDATE", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            self._check_revision(row, expected_revision); self._check_mutable(row)
            if target is DraftStatus.APPROVED and row["verification_status"] != VerificationStatus.SUPPORTED.value:
                raise EvidenceError("Draft cannot be approved until evidence verification passes.")
            if row["status"] == target.value:
                raise InvalidTransitionError(f"Draft is already {target.value}.")
            revision, now = expected_revision + 1, utc_now()
            db.execute("UPDATE drafts SET status=%s,revision=%s,rejection_reason=%s,updated_at=%s,approved_at=%s,rejected_at=%s,scheduled_at=NULL,publish_error=NULL WHERE id=%s", (target.value, revision, reason if target is DraftStatus.REJECTED else None, now, now if target is DraftStatus.APPROVED else None, now if target is DraftStatus.REJECTED else None, draft_id))
            self._record_revision(db, draft_id, revision, now)
        return self.get_draft(draft_id)  # type: ignore[return-value]

    def schedule_draft(self, draft_id: int, scheduled_at: str, expected_revision: int) -> Draft:
        scheduled = _utc_timestamp(scheduled_at, field="scheduled_at")
        with self._db() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=%s FOR UPDATE", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            self._check_revision(row, expected_revision); self._check_mutable(row)
            if row["status"] != DraftStatus.APPROVED.value or row["verification_status"] != VerificationStatus.SUPPORTED.value or row["approved_at"] is None:
                raise InvalidTransitionError("Only a supported, human-approved draft can be scheduled.")
            revision, now = expected_revision + 1, utc_now()
            db.execute("UPDATE drafts SET status=%s,revision=%s,scheduled_at=%s,updated_at=%s WHERE id=%s", (DraftStatus.SCHEDULED.value, revision, scheduled, now, draft_id))
            self._record_revision(db, draft_id, revision, now)
        return self.get_draft(draft_id)  # type: ignore[return-value]

    def list_due_drafts(self, now: str) -> list[Draft]:
        due = _utc_timestamp(now, field="now")
        with self._db() as db:
            rows = db.execute("SELECT * FROM drafts WHERE status=%s AND scheduled_at<=%s AND publish_attempted_at IS NULL ORDER BY scheduled_at,id", (DraftStatus.SCHEDULED.value, due)).fetchall()
        return [self._draft(row) for row in rows]

    def claim_publish(self, draft_id: int, expected_revision: int, *, scheduled_only: bool = False, now: str | None = None) -> Draft | None:
        attempted_at = _utc_timestamp(now, field="now") if now is not None else utc_now()
        with self._db() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=%s FOR UPDATE", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            self._check_revision(row, expected_revision)
            if row["publish_attempted_at"] is not None or row["status"] in _LOCKED_STATUSES:
                return None
            eligible = {DraftStatus.SCHEDULED.value} if scheduled_only else {DraftStatus.APPROVED.value}
            if row["status"] not in eligible or (scheduled_only and (row["scheduled_at"] is None or row["scheduled_at"] > attempted_at)):
                return None
            if row["verification_status"] != VerificationStatus.SUPPORTED.value or row["approved_at"] is None:
                return None
            digest = hashlib.sha256(str(row["text"]).encode("utf-8")).hexdigest()
            claim = db.execute("INSERT INTO publish_claims(content_hash,draft_id,claimed_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING RETURNING content_hash", (digest, draft_id, attempted_at)).fetchone()
            revision = expected_revision + 1
            if not claim:
                db.execute("UPDATE drafts SET status=%s,revision=%s,publish_attempted_at=%s,publish_error=%s,updated_at=%s WHERE id=%s", (DraftStatus.PUBLISH_FAILED.value, revision, attempted_at, _DUPLICATE_PUBLISH_ERROR, attempted_at, draft_id))
                self._record_revision(db, draft_id, revision, attempted_at)
                return None
            db.execute("UPDATE drafts SET status=%s,revision=%s,publish_attempted_at=%s,publish_error=NULL,updated_at=%s WHERE id=%s", (DraftStatus.PUBLISHING.value, revision, attempted_at, attempted_at, draft_id))
            self._record_revision(db, draft_id, revision, attempted_at)
        return self.get_draft(draft_id)

    def finish_publish(self, draft_id: int, *, post_id: str | None = None, error: str | None = None, ambiguous: bool = False) -> Draft:
        clean_post_id = post_id.strip() if post_id else None
        if clean_post_id and (error or ambiguous):
            raise ValueError("A publish result cannot contain both success and failure fields.")
        if not clean_post_id and not error:
            raise ValueError("A publish result requires a post id or an error.")
        with self._db() as db:
            row = db.execute("SELECT * FROM drafts WHERE id=%s FOR UPDATE", (draft_id,)).fetchone()
            if not row:
                raise KeyError(draft_id)
            if row["status"] != DraftStatus.PUBLISHING.value or row["publish_attempted_at"] is None:
                raise InvalidTransitionError("Only a claimed publishing draft can be finished.")
            now, revision = utc_now(), int(row["revision"]) + 1
            if clean_post_id:
                status, publish_error, published_at = DraftStatus.PUBLISHED.value, None, now
            else:
                status = DraftStatus.PUBLISH_UNKNOWN.value if ambiguous else DraftStatus.PUBLISH_FAILED.value
                publish_error, published_at = str(error)[:240], None
            db.execute("UPDATE drafts SET status=%s,revision=%s,published_at=%s,x_post_id=%s,publish_error=%s,updated_at=%s WHERE id=%s", (status, revision, published_at, clean_post_id, publish_error, now, draft_id))
            self._record_revision(db, draft_id, revision, now)
        return self.get_draft(draft_id)  # type: ignore[return-value]

    def create_run(self, kind: str) -> int:
        with self._db() as db:
            row = db.execute("INSERT INTO pipeline_runs(kind,status,started_at) VALUES(%s,%s,%s) RETURNING id", (kind, "running", utc_now())).fetchone()
            return int(row["id"])

    def finish_run(self, run_id: int, status: str, detail: dict[str, Any]) -> None:
        with self._db() as db:
            db.execute("UPDATE pipeline_runs SET status=%s,finished_at=%s,detail=%s WHERE id=%s", (status, utc_now(), json.dumps(detail, sort_keys=True), run_id))

    def record_model_call(self, run_id: int | None, role: str, response: ModelResponse, prompt_version: str) -> None:
        with self._db() as db:
            db.execute("INSERT INTO model_calls(run_id,role,provider,model,response_id,input_tokens,output_tokens,cached_input_tokens,cache_write_tokens,estimated_cost_usd,cost_provenance,prompt_version,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (run_id, role, response.provider, response.model, response.response_id, response.input_tokens, response.output_tokens, response.cached_input_tokens, response.cache_write_tokens, response.estimated_cost_usd, response.cost_provenance, prompt_version, utc_now()))

    def list_model_calls(self, run_id: int | None = None) -> list[dict[str, Any]]:
        with self._db() as db:
            return db.execute("SELECT * FROM model_calls ORDER BY id").fetchall() if run_id is None else db.execute("SELECT * FROM model_calls WHERE run_id=%s ORDER BY id", (run_id,)).fetchall()

    def claim_job_slot(self, job_name: str, slot: str) -> bool:
        with self._db() as db:
            row = db.execute("INSERT INTO job_slots(job_name,slot,status,claimed_at) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING job_name", (job_name, slot, "running", utc_now())).fetchone()
            return row is not None

    def finish_job_slot(self, job_name: str, slot: str, status: str) -> None:
        with self._db() as db:
            cursor = db.execute("UPDATE job_slots SET status=%s,finished_at=%s WHERE job_name=%s AND slot=%s", (status, utc_now(), job_name, slot))
            if cursor.rowcount != 1:
                raise KeyError((job_name, slot))

    def healthcheck(self) -> bool:
        try:
            with self._db() as db:
                return db.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
        except Exception:
            return False
