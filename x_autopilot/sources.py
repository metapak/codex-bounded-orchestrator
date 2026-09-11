"""Small, reliable Phase 1 research source adapters."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from .domain import RawResearchItem, XAutopilotError

MAX_RESPONSE_BYTES = 2_000_000


class SourceError(XAutopilotError):
    pass


def _read(opener: Callable[..., Any], request: urllib.request.Request | str, timeout: float) -> bytes:
    try:
        with opener(request, timeout=timeout) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except Exception as exc:
        raise SourceError(str(exc)) from exc
    if len(data) > MAX_RESPONSE_BYTES:
        raise SourceError("Source response exceeds the Phase 1 size limit.")
    return data


class HackerNewsSource:
    name = "hacker_news"

    def __init__(self, feed: str = "topstories", timeout: float = 15, opener: Callable[..., Any] | None = None, base_url: str = "https://hacker-news.firebaseio.com/v0") -> None:
        if feed not in {"topstories", "newstories", "beststories"}:
            raise ValueError("Unsupported Hacker News feed.")
        self.feed = feed; self.timeout = timeout; self.opener = opener or urllib.request.urlopen; self.base_url = base_url.rstrip("/")

    def fetch(self, limit: int) -> list[RawResearchItem]:
        ids = json.loads(_read(self.opener, f"{self.base_url}/{self.feed}.json", self.timeout))
        result = []
        for story_id in ids[:limit]:
            item = json.loads(_read(self.opener, f"{self.base_url}/item/{int(story_id)}.json", self.timeout))
            if not item or item.get("type") != "story" or not item.get("title"):
                continue
            url = item.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            result.append(RawResearchItem(source=self.name,external_id=str(story_id),title=str(item["title"]),url=str(url),excerpt=str(item.get("text") or item["title"]),author=item.get("by"),published_at=datetime.fromtimestamp(item["time"],timezone.utc).isoformat() if item.get("time") else None,metadata={"score":item.get("score"),"comments":item.get("descendants")}))
        return result


class FeedSource:
    name = "feeds"

    def __init__(self, urls: list[str], timeout: float = 15, opener: Callable[..., Any] | None = None) -> None:
        self.urls = urls; self.timeout = timeout; self.opener = opener or urllib.request.urlopen

    @staticmethod
    def _local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].lower()

    @classmethod
    def _child_text(cls, node: ET.Element, names: set[str]) -> str | None:
        for child in node:
            if cls._local(child.tag) in names:
                if cls._local(child.tag) == "link" and child.attrib.get("href"):
                    return child.attrib["href"].strip()
                text = "".join(child.itertext()).strip()
                if text:
                    return text
        return None

    def fetch(self, limit: int) -> list[RawResearchItem]:
        result: list[RawResearchItem] = []
        per_feed = max(1, limit // max(1, len(self.urls)))
        for url in self.urls:
            try:
                root = ET.fromstring(_read(self.opener, url, self.timeout))
            except ET.ParseError as exc:
                raise SourceError(f"Invalid XML from {url}: {exc}") from exc
            entries = [node for node in root.iter() if self._local(node.tag) in {"item", "entry"}]
            for node in entries[:per_feed]:
                title = self._child_text(node, {"title"})
                link = self._child_text(node, {"link"})
                if not title or not link:
                    continue
                external_id = self._child_text(node, {"guid", "id"}) or link
                result.append(RawResearchItem(source=self.name,external_id=external_id,title=title,url=link,excerpt=self._child_text(node,{"summary","description","content"}) or title,author=self._child_text(node,{"author","creator","name"}),published_at=self._child_text(node,{"published","updated","pubdate"}),metadata={"feed_url":url}))
                if len(result) >= limit:
                    return result
        return result


class GitHubSource:
    name = "github"

    def __init__(self, queries: list[str], token_env: str = "GITHUB_TOKEN", timeout: float = 15, opener: Callable[..., Any] | None = None, endpoint: str = "https://api.github.com/search/repositories") -> None:
        import os
        self.queries=queries; self.token=os.environ.get(token_env); self.timeout=timeout; self.opener=opener or urllib.request.urlopen; self.endpoint=endpoint

    def fetch(self, limit: int) -> list[RawResearchItem]:
        if not self.queries:
            return []
        result=[]; per_query=max(1,limit//len(self.queries))
        for query in self.queries:
            url=f"{self.endpoint}?{urllib.parse.urlencode({'q':query,'sort':'updated','order':'desc','per_page':per_query})}"
            headers={"Accept":"application/vnd.github+json","User-Agent":"x-autopilot-phase1"}
            if self.token: headers["Authorization"]=f"Bearer {self.token}"
            payload=json.loads(_read(self.opener,urllib.request.Request(url,headers=headers),self.timeout))
            for repo in payload.get("items",[])[:per_query]:
                result.append(RawResearchItem(source=self.name,external_id=str(repo["id"]),title=str(repo["full_name"]),url=str(repo["html_url"]),excerpt=str(repo.get("description") or repo["full_name"]),author=str(repo.get("owner",{}).get("login") or "") or None,published_at=repo.get("updated_at"),metadata={"stars":repo.get("stargazers_count"),"language":repo.get("language")}))
        return result[:limit]
