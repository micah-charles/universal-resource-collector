from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse


@dataclass(slots=True)
class ResourceLink:
    url: str
    text: str = ""
    section: str = ""


@dataclass(slots=True)
class DiscoveredPage:
    url: str
    final_url: str
    title: str
    body: bytes
    links: list[str]
    resource_links: list[ResourceLink]


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links: list[str] = []; self.resource_links: list[tuple[str, str, str]] = []; self.title: list[str] = []; self.in_title = False; self.heading: list[str] = []; self.in_heading = False; self.current_link: dict | None = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}: self.in_heading = True; self.heading = []
        if tag == "a" and attrs.get("href"): self.current_link = {"href": attrs["href"], "text": []}
        if tag in {"link", "iframe"} and attrs.get("href"): self.links.append(attrs["href"])
        if tag == "title": self.in_title = True
    def handle_endtag(self, tag):
        if tag == "title": self.in_title = False
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}: self.in_heading = False
        if tag == "a" and self.current_link:
            text = " ".join("".join(self.current_link["text"]).split())
            self.links.append(self.current_link["href"]); self.resource_links.append((self.current_link["href"], text, " ".join(self.heading).strip())); self.current_link = None
    def handle_data(self, data):
        if self.in_title: self.title.append(data)
        if self.in_heading: self.heading.append(data)
        if self.current_link: self.current_link["text"].append(data)


class GenericWebAdapter:
    def __init__(self, allowed_domains: list[str], include_extensions: tuple[str, ...] = (".pdf",), path_prefix: str | None = None):
        self.allowed_domains = {x.lower().rstrip(".") for x in allowed_domains}
        self.include_extensions = tuple(x.lower() for x in include_extensions)
        self.path_prefix = path_prefix

    def canonical(self, base: str, href: str) -> str | None:
        url = urldefrag(urljoin(base, html.unescape(href)))[0]
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower().rstrip(".") not in self.allowed_domains:
            return None
        if self.path_prefix and not parsed.path.startswith(self.path_prefix):
            return None
        return url.replace(" ", "%20")

    def parse(self, url: str, body: bytes, final_url: str | None = None) -> DiscoveredPage:
        parser = LinkParser(); parser.feed(body.decode("utf-8", errors="replace"))
        links = sorted({x for href in parser.links if (x := self.canonical(final_url or url, href))})
        records = []
        for href, text, section in parser.resource_links:
            canonical = self.canonical(final_url or url, href)
            if canonical: records.append(ResourceLink(canonical, text, section))
        return DiscoveredPage(url, final_url or url, " ".join("".join(parser.title).split()), body, links, records)

    def qualifies_resource(self, url: str) -> bool:
        return urlparse(url).path.lower().endswith(self.include_extensions)

