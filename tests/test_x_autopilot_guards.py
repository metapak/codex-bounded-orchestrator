from __future__ import annotations

import unittest

from x_autopilot.guards import draft_text_valid, review_claims


def checked_claim(text, kind, *, evidence_ids=(), context_indices=(), evidence_quotes=(), context_quotes=()):
    return {
        "text": text,
        "kind": kind,
        "evidence_ids": list(evidence_ids),
        "verified_context_indices": list(context_indices),
        "evidence_quotes": list(evidence_quotes),
        "context_quotes": list(context_quotes),
        "supported": True,
        "note": "model says supported",
    }


class GuardTests(unittest.TestCase):
    def test_draft_text_format_rejects_empty_overlength_and_emoji(self):
        self.assertFalse(draft_text_valid("  "))
        self.assertFalse(draft_text_valid("a" * 281))
        self.assertFalse(draft_text_valid("iyi fikir 🚀"))
        self.assertTrue(draft_text_valid("kısa ve emojisiz."))

    def test_supported_claim_does_not_hide_an_unreviewed_personal_or_numerical_claim(self):
        text = "Araç 100 kullanıcıya ulaştı. bugün ödeme akışını düzelttim."
        factual = checked_claim(
            "Araç 100 kullanıcıya ulaştı.",
            "numerical",
            evidence_ids=(1,),
            evidence_quotes=({"evidence_id": 1, "quote": "Araç 100 kullanıcıya ulaştı."},),
        )
        _, supported = review_claims(text, [], [factual], {1: "Araç 100 kullanıcıya ulaştı."}, ())
        self.assertFalse(supported)

    def test_personal_wording_cannot_be_labeled_factual_to_bypass_context(self):
        text = "bugün ödeme akışını düzelttim."
        mislabeled = checked_claim(
            text,
            "factual",
            evidence_ids=(1,),
            evidence_quotes=({"evidence_id": 1, "quote": text},),
        )
        claims, supported = review_claims(text, [], [mislabeled], {1: text}, ())
        self.assertFalse(supported)
        self.assertFalse(claims[0]["supported"])

    def test_shared_topic_word_does_not_unlock_a_different_personal_claim(self):
        context = ("domain düşündüm.",)
        claim = checked_claim(
            "domain aldım.",
            "personal",
            context_indices=(0,),
            context_quotes=({"context_index": 0, "quote": context[0]},),
        )
        claims, supported = review_claims("domain aldım.", [], [claim], {}, context)
        self.assertFalse(supported)
        self.assertFalse(claims[0]["supported"])

    def test_exact_verified_personal_claim_and_exact_evidence_claim_can_pass(self):
        personal_context = ("cursor kullanıyorum.",)
        personal = checked_claim(
            "cursor kullanıyorum.",
            "personal",
            context_indices=(0,),
            context_quotes=({"context_index": 0, "quote": personal_context[0]},),
        )
        _, personal_supported = review_claims("cursor kullanıyorum.", [], [personal], {}, personal_context)
        self.assertTrue(personal_supported)

        factual = checked_claim(
            "Araç açık kaynak olarak yayınlandı.",
            "factual",
            evidence_ids=(4,),
            evidence_quotes=({"evidence_id": 4, "quote": "Araç açık kaynak olarak yayınlandı."},),
        )
        _, factual_supported = review_claims(
            "Araç açık kaynak olarak yayınlandı.", [], [factual], {4: "Araç açık kaynak olarak yayınlandı."}, ()
        )
        self.assertTrue(factual_supported)


if __name__ == "__main__":
    unittest.main()
