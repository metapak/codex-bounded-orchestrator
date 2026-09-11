from __future__ import annotations

import json
import unittest

from x_autopilot.sources import FeedSource, GitHubSource, HackerNewsSource


class Response:
    def __init__(self,data): self.data=data if isinstance(data,bytes) else json.dumps(data).encode()
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,*args): return self.data


class SourceTests(unittest.TestCase):
    def test_hacker_news_official_shape(self):
        def opener(request,timeout):
            url=request if isinstance(request,str) else request.full_url
            return Response([7] if "topstories" in url else {"id":7,"type":"story","title":"Tool","url":"https://example.com/tool","by":"met","time":100})
        items=HackerNewsSource(opener=opener).fetch(1); self.assertEqual(items[0].external_id,"7"); self.assertEqual(items[0].source,"hacker_news")

    def test_rss_and_atom_normalize(self):
        rss=b'<rss><channel><item><title>One</title><link>https://example.com/1</link><description>Body</description><guid>x1</guid></item></channel></rss>'
        atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Two</title><link href="https://example.com/2"/><summary>Body 2</summary><id>x2</id></entry></feed>'
        values=iter([Response(rss),Response(atom)])
        items=FeedSource(["https://a/feed","https://b/feed"],opener=lambda *a,**k:next(values)).fetch(2)
        self.assertEqual([item.title for item in items],["One","Two"])

    def test_github_public_api_shape_and_no_required_token(self):
        payload={"items":[{"id":3,"full_name":"acme/tool","html_url":"https://github.com/acme/tool","description":"Useful","owner":{"login":"acme"},"updated_at":"2026-01-01T00:00:00Z","stargazers_count":10}]}
        source=GitHubSource(["topic:tools"],opener=lambda *a,**k:Response(payload)); items=source.fetch(1)
        self.assertEqual(items[0].title,"acme/tool")


if __name__ == "__main__": unittest.main()
