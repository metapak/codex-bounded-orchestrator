from __future__ import annotations

import http.client
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

from x_autopilot.domain import RawResearchItem
from x_autopilot.normalize import canonicalize_url, fingerprint
from x_autopilot.review import local_datetime_to_iso
from x_autopilot.storage import SQLiteRepository
from x_autopilot.web import create_server


class FakePublisher:
    def __init__(self, repository):
        self.repository = repository
        self.calls = []

    def publish_now(self, draft_id, revision):
        self.calls.append((draft_id, revision))
        claimed = self.repository.claim_publish(draft_id, revision)
        if claimed is None:
            return None
        return self.repository.finish_publish(draft_id, post_id=f"1000{draft_id}")


class ReviewUITests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(); self.repo=SQLiteRepository(Path(self.temporary.name)/"db.sqlite3"); self.repo.initialize()
        raw=RawResearchItem("fixture","1","<Research>","https://example.com","<script>alert(1)</script>"); url=canonicalize_url(raw.url); item_id,_=self.repo.add_research(raw,url,fingerprint(raw,url)); self.repo.add_evidence(item_id,url,raw.excerpt)
        self.draft_id=self.repo.create_draft(text="Taslak",category="tools",confidence=.8,factual_risk="low",verification_status="supported",research_item_id=item_id,provider="fake",model="m",prompt_version="v1",claims=[])
        self.publisher=FakePublisher(self.repo)
        def verify_callback(draft_id,revision):
            self.repo.replace_claims_and_verification(draft_id,[],"supported",revision)
            return {"verification_status":"supported"}
        self.server=create_server(self.repo,"127.0.0.1",0,csrf_token="test-token",publisher=self.publisher,verify_callback=verify_callback); self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start(); self.port=self.server.server_port
    def tearDown(self): self.server.shutdown(); self.server.server_close(); self.thread.join(2); self.temporary.cleanup()

    def request(self,method,path,body=None,headers=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.port,timeout=3); conn.request(method,path,body,headers or {}); response=conn.getresponse(); data=response.read().decode(); result=(response.status,dict(response.getheaders()),data); conn.close(); return result

    def test_lists_escaped_research_and_draft_detail(self):
        status,headers,body=self.request("GET","/"); self.assertEqual(status,200); self.assertIn("&lt;Research&gt;",body); self.assertNotIn("<script>",body); self.assertIn("Content-Security-Policy",headers); self.assertEqual(headers["Referrer-Policy"],"strict-origin-when-cross-origin")
        self.repo.add_evidence(self.repo.get_draft(self.draft_id).research_item_id,"javascript:alert(1)","unsafe")
        status,_,body=self.request("GET",f"/draft/{self.draft_id}"); self.assertEqual(status,200); self.assertIn("Taslak",body); self.assertIn("Evidence",body)
        self.assertIn('name="viewport"',body); self.assertIn("@media(max-width:600px)",body)
        self.assertIn("Sağlayıcı",body); self.assertIn("Prompt",body)
        self.assertNotIn('href="javascript:',body)

    def test_csrf_edit_and_approve_flow(self):
        body=urlencode({"csrf":"bad","revision":"1","text":"Yeni"}); status,_,_=self.request("POST",f"/draft/{self.draft_id}/edit",body,{"Content-Type":"application/x-www-form-urlencoded","Cookie":"xap_csrf=test-token"}); self.assertEqual(status,403)
        body=urlencode({"csrf":"test-token","revision":"1","text":"Yeni olgusal metin"}); status,headers,_=self.request("POST",f"/draft/{self.draft_id}/edit",body,{"Content-Type":"application/x-www-form-urlencoded","Cookie":"xap_csrf=test-token"}); self.assertEqual(status,303)
        draft=self.repo.get_draft(self.draft_id); self.assertEqual(draft.revision,2); self.assertEqual(draft.verification_status.value,"unverified")
        body=urlencode({"csrf":"test-token","revision":"2"}); status,_,_=self.request("POST",f"/draft/{self.draft_id}/approve",body,{"Content-Type":"application/x-www-form-urlencoded","Cookie":"xap_csrf=test-token"}); self.assertEqual(status,409)

        status,_,page=self.request("GET",f"/draft/{self.draft_id}"); self.assertEqual(status,200); self.assertIn("Yeniden doğrula",page)
        body=urlencode({"csrf":"test-token","revision":"2"}); status,_,_=self.request("POST",f"/draft/{self.draft_id}/verify",body,{"Content-Type":"application/x-www-form-urlencoded","Cookie":"xap_csrf=test-token"}); self.assertEqual(status,303)
        body=urlencode({"csrf":"test-token","revision":"3"}); status,_,_=self.request("POST",f"/draft/{self.draft_id}/approve",body,{"Content-Type":"application/x-www-form-urlencoded","Cookie":"xap_csrf=test-token"}); self.assertEqual(status,303)

    def test_approve_schedule_and_publish_now(self):
        headers={"Content-Type":"application/x-www-form-urlencoded","Cookie":"xap_csrf=test-token"}
        body=urlencode({"csrf":"test-token","revision":"1"}); status,_,_=self.request("POST",f"/draft/{self.draft_id}/approve",body,headers); self.assertEqual(status,303)
        status,_,page=self.request("GET",f"/draft/{self.draft_id}"); self.assertEqual(status,200); self.assertIn("Şimdi yayınla",page); self.assertIn('type="datetime-local"',page)
        body=urlencode({"csrf":"test-token","revision":"2","scheduled_at":"2030-01-02T12:00"}); status,_,_=self.request("POST",f"/draft/{self.draft_id}/schedule",body,headers); self.assertEqual(status,303)
        scheduled=self.repo.get_draft(self.draft_id); self.assertEqual(scheduled.status.value,"scheduled"); self.assertEqual(scheduled.scheduled_at,"2030-01-02T09:00:00+00:00")

        second=self.repo.create_draft(text="İkinci taslak",category="tools",confidence=.8,factual_risk="low",verification_status="supported",research_item_id=scheduled.research_item_id,provider="fake",model="m",prompt_version="v1",claims=[])
        body=urlencode({"csrf":"test-token","revision":"1"}); status,_,_=self.request("POST",f"/draft/{second}/approve",body,headers); self.assertEqual(status,303)
        body=urlencode({"csrf":"test-token","revision":"2"}); status,_,_=self.request("POST",f"/draft/{second}/publish",body,headers); self.assertEqual(status,303)
        published=self.repo.get_draft(second); self.assertEqual(published.status.value,"published"); self.assertEqual(published.x_post_id,f"1000{second}"); self.assertEqual(self.publisher.calls,[(second,2)])
        status,_,page=self.request("GET",f"/draft/{second}"); self.assertNotIn("Şimdi yayınla",page); self.assertIn("Draft metni",page); self.assertIn("İkinci taslak",page); self.assertIn(f'href="https://x.com/i/web/status/1000{second}"',page)

    def test_datetime_local_rejects_dst_gap_and_fold(self):
        self.assertEqual(local_datetime_to_iso("2030-01-02T12:00","Europe/Istanbul"),"2030-01-02T12:00:00+03:00")
        with self.assertRaisesRegex(ValueError,"mevcut değil"):
            local_datetime_to_iso("2026-03-29T02:30","Europe/Berlin")
        with self.assertRaisesRegex(ValueError,"belirsiz"):
            local_datetime_to_iso("2026-10-25T02:30","Europe/Berlin")


if __name__ == "__main__": unittest.main()
