from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from x_autopilot.config import AppConfig, ModelRoute
from x_autopilot.domain import EvidenceError, RawResearchItem, VerificationStatus
from x_autopilot.model import FakeModelProvider, ModelGateway
from x_autopilot.pipeline import Pipeline, _review_claims
from x_autopilot.storage import SQLiteRepository


class StaticSource:
    name = "fixture"

    def __init__(self, count: int = 1) -> None:
        self.count = count

    def fetch(self, limit: int):
        return [
            RawResearchItem("fixture", str(i), f"Yeni geliştirici aracı {i}", f"https://example.com/{i}", f"Araç {i + 100} kullanıcıya ulaştı.")
            for i in range(min(limit, self.count))
        ]


class BrokenSource:
    name = "broken"

    def fetch(self, limit):
        raise RuntimeError("temporary source failure")


def config(path: Path, *, max_drafts: int = 4, verified_context: tuple[str, ...] = ()) -> AppConfig:
    routes = {
        "luna": ModelRoute("fake", "cheap-model"),
        "sol": ModelRoute("fake", "editor-model", enabled=False),
        "astra": ModelRoute("fake", "premium-model", enabled=False),
    }
    return AppConfig(path, "127.0.0.1", 0, .65, 8, max_drafts, "tr", ("developer_observation",), routes, {}, verified_user_context=verified_context)


def candidate(item, *, text="küçük bir değişiklik bazen bütün öğleden sonrayı yiyor.", claims=None, accepted=True):
    return {
        "research_item_id": item["research_item_id"], "accepted": accepted, "summary": item["title"],
        "category": "developer_observation", "confidence": .9, "noise": False, "near_duplicate_key": None,
        "draft_text": text, "factual_risk": "low" if not claims else "high", "hook_type": "observation",
        "post_structure": "standalone", "claims": claims or [], "rejection_reason": None if accepted else "zayıf konu",
    }


def generate_all(request):
    return {"candidates": [candidate(item) for item in request.input["items"]]}


def approve_claims(request):
    reviews = []
    for item in request.input["candidates"]:
        evidence = {record["id"]: record["excerpt"] for record in item["evidence"]}
        claims = [
            {
                **claim,
                "evidence_quotes": [{"evidence_id": ref, "quote": evidence.get(ref, "")} for ref in claim["evidence_ids"]],
                "context_quotes": [],
                "supported": True,
                "note": "fixture support",
            }
            for claim in item["proposed_claims"]
        ]
        reviews.append({"research_item_id": item["research_item_id"], "supported": True, "claims": claims})
    return {"reviews": reviews}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "db.sqlite3"
        self.repo = SQLiteRepository(self.path)
        self.repo.initialize()

    def tearDown(self):
        self.temporary.cleanup()

    def pipeline(self, fake, *, count=1, max_drafts=4, verified_context=()):
        selected = config(self.path, max_drafts=max_drafts, verified_context=verified_context)
        return Pipeline(selected, self.repo, ModelGateway(selected, {"fake": fake}), [StaticSource(count)])

    def test_luna_only_batch_flow_creates_pending_drafts_attached_to_sources(self):
        fake = FakeModelProvider({"luna_batch_generate": generate_all, "luna_batch_review": approve_claims})
        result = self.pipeline(fake, count=4).run()
        drafts = self.repo.list_drafts()
        self.assertEqual(result["generate"]["candidates"], 4)
        self.assertEqual(result["generate"]["drafted"], 4)
        self.assertEqual({draft.research_item_id for draft in drafts}, {item.id for item in self.repo.list_research()})
        self.assertTrue(all(draft.status.value == "pending" for draft in drafts))
        self.assertEqual([purpose for purpose, _ in fake.calls], ["luna_batch_generate", "luna_batch_review"])
        self.assertEqual({model for _, model in fake.calls}, {"cheap-model"})

    def test_total_candidate_limit_counts_rejections(self):
        def reject_all(request):
            return {"candidates": [candidate(item, accepted=False) for item in request.input["items"]]}

        fake = FakeModelProvider({"luna_batch_generate": reject_all})
        result = self.pipeline(fake, count=6, max_drafts=4).run()
        self.assertEqual(result["generate"]["candidates"], 4)
        self.assertEqual(result["generate"]["rejected"], 4)
        self.assertEqual(len(self.repo.list_research("new")), 2)
        self.assertEqual(len(fake.calls), 1)

    def test_invalid_generated_text_is_rejected_before_review(self):
        for invalid in ("", "x" * 281, "iyi fikir 🚀"):
            with self.subTest(invalid=invalid[:12]):
                def generate(request):
                    return {"candidates": [candidate(request.input["items"][0], text=invalid)]}

                fake = FakeModelProvider({"luna_batch_generate": generate})
                result = self.pipeline(fake).run()
                self.assertEqual(result["generate"]["rejected"], 1)
                self.assertEqual(self.repo.list_drafts(), [])
                self.repo = SQLiteRepository(Path(self.temporary.name) / f"next-{len(invalid)}.sqlite3")
                self.repo.initialize()

    def test_six_candidates_use_two_balanced_two_call_batches(self):
        generated_sizes, reviewed_sizes = [], []

        def generate(request):
            generated_sizes.append(len(request.input["items"]))
            return generate_all(request)

        def review(request):
            reviewed_sizes.append(len(request.input["candidates"]))
            return approve_claims(request)

        fake = FakeModelProvider({"luna_batch_generate": generate, "luna_batch_review": review})
        result = self.pipeline(fake, count=6, max_drafts=6).run()
        self.assertEqual(result["generate"]["drafted"], 6)
        self.assertEqual(generated_sizes, [3, 3])
        self.assertEqual(reviewed_sizes, [3, 3])

    def test_duplicate_or_foreign_candidate_id_fails_closed(self):
        def malformed(request):
            first = candidate(request.input["items"][0])
            foreign = {**first, "research_item_id": 999}
            return {"candidates": [first, foreign]}

        fake = FakeModelProvider({"luna_batch_generate": malformed})
        result = self.pipeline(fake, count=2, max_drafts=2).run()
        self.assertEqual(result["generate"]["drafted"], 0)
        self.assertEqual(len(result["generate"]["failures"]), 2)
        self.assertEqual(self.repo.list_drafts(), [])

    def test_partial_source_failure_preserves_successful_research(self):
        selected = config(self.path)
        pipeline = Pipeline(selected, self.repo, ModelGateway(selected, {"fake": FakeModelProvider()}), [BrokenSource(), StaticSource()])
        result = pipeline.research()
        self.assertEqual(result["added"], 1)
        self.assertEqual(result["failures"][0]["source"], "broken")

    def test_omitted_numerical_claim_cannot_be_approved(self):
        def generate(request):
            item = request.input["items"][0]
            ref = item["evidence"][0]["id"]
            claim = {"text": "Araç 100 kullanıcıya ulaştı.", "kind": "numerical", "evidence_ids": [ref], "verified_context_indices": []}
            return {"candidates": [candidate(item, text="Araç 100 kullanıcıya ulaştı.", claims=[claim])]}

        def omit(request):
            item = request.input["candidates"][0]
            return {"reviews": [{"research_item_id": item["research_item_id"], "supported": True, "claims": []}]}

        fake = FakeModelProvider({"luna_batch_generate": generate, "luna_batch_review": omit})
        self.pipeline(fake).run()
        draft = self.repo.list_drafts()[0]
        self.assertEqual(draft.status.value, "rejected")
        self.assertEqual(draft.verification_status, VerificationStatus.UNSUPPORTED)
        self.assertFalse(self.repo.list_claims(draft.id)[0]["supported"])

    def test_cross_source_reference_and_non_covering_quote_are_blocked(self):
        fake = FakeModelProvider()
        pipeline = self.pipeline(fake, count=2, max_drafts=2)
        pipeline.research()
        items = self.repo.list_research("new")
        evidence = {item.id: self.repo.list_evidence(item.id)[0] for item in items}

        def generate(request):
            result = []
            for item in request.input["items"]:
                other = next(record.id for owner, record in evidence.items() if owner != item["research_item_id"])
                claim = {"text": "Araç 100 kullanıcıya ulaştı.", "kind": "numerical", "evidence_ids": [other], "verified_context_indices": []}
                result.append(candidate(item, text="Araç 100 kullanıcıya ulaştı.", claims=[claim]))
            return {"candidates": result}

        def review(request):
            reviews = []
            for item in request.input["candidates"]:
                claim = item["proposed_claims"][0]
                checked = {**claim, "evidence_quotes": [{"evidence_id": claim["evidence_ids"][0], "quote": "Araç"}], "context_quotes": [], "supported": True, "note": "wrong source"}
                reviews.append({"research_item_id": item["research_item_id"], "supported": True, "claims": [checked]})
            return {"reviews": reviews}

        fake.handlers.update({"luna_batch_generate": generate, "luna_batch_review": review})
        result = pipeline.generate()
        self.assertEqual((result["drafted"], result["rejected"]), (0, 2))

    def test_context_cannot_unlock_unrelated_personal_claim(self):
        context = ("cursor kullanıyorum.",)

        def generate(request):
            item = request.input["items"][0]
            claims = [
                {"text": "cursor kullanıyorum", "kind": "personal", "evidence_ids": [], "verified_context_indices": [0]},
                {"text": "bugün ödeme akışını düzelttim", "kind": "personal", "evidence_ids": [], "verified_context_indices": [0]},
            ]
            return {"candidates": [candidate(item, text="cursor kullanıyorum. bugün ödeme akışını düzelttim.", claims=claims)]}

        def review(request):
            item = request.input["candidates"][0]
            claims = [{**claim, "evidence_quotes": [], "context_quotes": [{"context_index": 0, "quote": context[0]}], "supported": True, "note": "context"} for claim in item["proposed_claims"]]
            return {"reviews": [{"research_item_id": item["research_item_id"], "supported": True, "claims": claims}]}

        fake = FakeModelProvider({"luna_batch_generate": generate, "luna_batch_review": review})
        self.pipeline(fake, verified_context=context).run()
        draft = self.repo.list_drafts()[0]
        self.assertEqual([claim["supported"] for claim in self.repo.list_claims(draft.id)], [True, False])
        self.assertEqual(draft.verification_status, VerificationStatus.UNSUPPORTED)

    def test_edit_reverification_uses_luna_and_new_revision(self):
        fake = FakeModelProvider({"luna_batch_generate": generate_all, "luna_batch_review": approve_claims, "luna_draft_review": approve_claims})
        pipeline = self.pipeline(fake)
        pipeline.run()
        draft = self.repo.list_drafts()[0]
        edited = self.repo.edit_draft(draft.id, "bu yaklaşım gereksiz karmaşık geliyor.", draft.revision)
        result = pipeline.verify_draft(edited.id, edited.revision)
        refreshed = self.repo.get_draft(edited.id)
        self.assertEqual(result["verification_status"], "supported")
        self.assertEqual(refreshed.revision, result["revision"])
        approved = self.repo.set_draft_status(refreshed.id, "approved", refreshed.revision)
        self.assertEqual(approved.status.value, "approved")
        self.assertIn("luna_draft_review", [purpose for purpose, _ in fake.calls])

    def test_empty_review_blocks_edited_numerical_and_personal_drafts(self):
        empty_review = lambda request: {"reviews": [{"research_item_id": request.input["candidates"][0]["research_item_id"], "supported": True, "claims": []}]}
        fake = FakeModelProvider({"luna_batch_generate": generate_all, "luna_batch_review": approve_claims, "luna_draft_review": empty_review})
        pipeline = self.pipeline(fake)
        pipeline.run()
        draft_id = self.repo.list_drafts()[0].id
        for text in ("Bu ürünün 999 müşterisi var.", "bugün ödeme akışını düzelttim."):
            current = self.repo.get_draft(draft_id)
            edited = self.repo.edit_draft(draft_id, text, current.revision)
            result = pipeline.verify_draft(draft_id, edited.revision)
            self.assertEqual(result["verification_status"], "unsupported")
            refreshed = self.repo.get_draft(draft_id)
            with self.assertRaises(EvidenceError):
                self.repo.set_draft_status(draft_id, "approved", refreshed.revision)

    def test_edited_overlength_or_emoji_text_cannot_pass_review(self):
        fake = FakeModelProvider({"luna_batch_generate": generate_all, "luna_batch_review": approve_claims, "luna_draft_review": approve_claims})
        pipeline = self.pipeline(fake)
        pipeline.run()
        draft_id = self.repo.list_drafts()[0].id
        for text in ("x" * 281, "iyi fikir 🚀"):
            current = self.repo.get_draft(draft_id)
            edited = self.repo.edit_draft(draft_id, text, current.revision)
            result = pipeline.verify_draft(draft_id, edited.revision)
            self.assertEqual(result["verification_status"], "unsupported")

    def test_legacy_review_merge_still_rejects_duplicates_and_invalid_refs(self):
        proposed = {"text": "100 kullanıcı", "kind": "numerical", "evidence_ids": [1]}
        reviewed = {**proposed, "supported": True, "note": "ok"}
        merged, supported = _review_claims("Araç 100 kullanıcıya ulaştı.", [proposed], [reviewed, reviewed], {1})
        self.assertFalse(supported)
        self.assertFalse(merged[0]["supported"])
        _, supported = _review_claims("Araç 100 kullanıcıya ulaştı.", [], [{**reviewed, "evidence_ids": [999]}], {1})
        self.assertFalse(supported)


if __name__ == "__main__":
    unittest.main()
