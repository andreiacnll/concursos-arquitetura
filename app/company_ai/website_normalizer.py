from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from .website_crawler import WebsiteCrawlResult


SECTION_LABELS = {
    "identity": "IDENTIDADE",
    "services": "SERVICOS",
    "competences": "COMPETENCIAS",
    "projects": "PROJETOS",
    "locations": "LOCALIZACOES",
    "awards": "PREMIOS",
    "team": "EQUIPA",
    "research": "INVESTIGACAO",
    "typologies": "TIPOLOGIAS",
}

_NOISE_PATTERNS = (
    r"sorry\s+no posts matched your criteria",
    r"lorem ipsum",
    r"contact us",
    r"may we help you",
    r"back to top",
    r"read more",
    r"find more",
    r"saiba mais",
    r"facebook|instagram|twitter|linkedin|youtube|pinterest",
    r"cookies?|privacy policy|terms and conditions",
    r"newsletter|subscribe|widget|sidebar",
    r"select themes|all rights reserved",
    r"previous|next|older posts|newer posts",
)

_LABEL_NOISE = {
    "home",
    "works",
    "work",
    "news",
    "office",
    "publications",
    "contacts",
    "contact",
    "portfolio",
    "go",
    "en",
    "pt",
    "menu",
    "search",
    "close",
}


@dataclass
class NormalizedBlock:
    section: str
    url: str
    text: str


@dataclass
class NormalizedWebsiteContent:
    combined_text: str
    sections: dict[str, list[NormalizedBlock]] = field(default_factory=dict)
    section_urls: dict[str, str] = field(default_factory=dict)
    section_evidence: dict[str, str] = field(default_factory=dict)
    project_names: list[str] = field(default_factory=list)
    removed_blocks: int = 0
    warnings: list[str] = field(default_factory=list)


def _clean_text(value: Any) -> str:
    text = " ".join(str(value or "").replace("\xa0", " ").split())
    return text.strip(" \t\r\n-–—|")


def _normal_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _is_noise(text: str) -> bool:
    cleaned = _clean_text(text)
    key = _normal_key(cleaned)
    if not cleaned or key in _LABEL_NOISE:
        return True
    if len(cleaned) < 4:
        return True
    if len(cleaned) <= 24 and len(cleaned.split()) <= 3 and cleaned.isupper():
        return True
    return any(re.search(pattern, key, re.I) for pattern in _NOISE_PATTERNS)


def _paragraphs(text: str) -> list[str]:
    candidates = re.split(r"[\r\n]+", text or "")
    return [_clean_text(candidate) for candidate in candidates if _clean_text(candidate)]


def _too_similar(text: str, seen: list[str]) -> bool:
    key = _normal_key(text)
    for previous in seen:
        if key == previous:
            return True
        if SequenceMatcher(None, key, previous).ratio() >= 0.92:
            return True
    return False


def _section_for(text: str, url: str) -> str:
    base = _normal_key(f"{url} {text}")
    if "/portfolio-item/" in url or "project" in base:
        return "projects"
    if any(word in base for word in ("office", "about", "profile", "atelier", "studio")):
        return "identity"
    if any(word in base for word in ("service", "architecture", "urbanism", "landscape", "consulting", "interior design")):
        return "services"
    if any(word in base for word in ("bim", "computational", "engineering", "coordination", "software", "methodology")):
        return "competences"
    if any(word in base for word in ("award", "prize", "winner", "premio", "prémio")):
        return "awards"
    if any(word in base for word in ("team", "nuno", "lacerda", "biography", "founder")):
        return "team"
    if any(word in base for word in ("research", "innovation", "investigation")):
        return "research"
    if any(word in base for word in ("school", "housing", "hospital", "hotel", "heritage", "sports", "retail", "public space")):
        return "typologies"
    if any(word in base for word in ("location", "porto", "lisbon", "rwanda", "ghana", "portugal")):
        return "locations"
    return "identity"


def _dedupe_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _clean_text(value)
        key = _normal_key(text)
        if not text or key in seen or _is_noise(text):
            continue
        seen.add(key)
        result.append(text)
    return result


def normalize_website_content(
    crawl_result: WebsiteCrawlResult,
) -> NormalizedWebsiteContent:
    page_paragraph_counts: dict[str, int] = {}
    page_paragraphs: list[tuple[str, str]] = []

    for page in crawl_result.pages:
        local_seen: set[str] = set()
        for paragraph in _paragraphs(page.text):
            key = _normal_key(paragraph)
            if not key or key in local_seen:
                continue
            local_seen.add(key)
            page_paragraphs.append((page.url, paragraph))
            page_paragraph_counts[key] = page_paragraph_counts.get(key, 0) + 1

    sections: dict[str, list[NormalizedBlock]] = {
        key: [] for key in SECTION_LABELS
    }
    seen_by_section: dict[str, list[str]] = {key: [] for key in SECTION_LABELS}
    removed = 0

    for url, paragraph in page_paragraphs:
        key = _normal_key(paragraph)
        if _is_noise(paragraph) or page_paragraph_counts.get(key, 0) > 2:
            removed += 1
            continue
        section = _section_for(paragraph, url)
        if _too_similar(paragraph, seen_by_section[section]):
            removed += 1
            continue
        seen_by_section[section].append(key)
        sections[section].append(
            NormalizedBlock(section=section, url=url, text=paragraph)
        )

    project_names = _dedupe_list(crawl_result.project_names)
    if project_names:
        for name in project_names:
            sections["projects"].append(
                NormalizedBlock(
                    section="projects",
                    url=crawl_result.final_url,
                    text=name,
                )
            )

    section_urls: dict[str, str] = {}
    section_evidence: dict[str, str] = {}
    text_parts: list[str] = []
    for section, label in SECTION_LABELS.items():
        blocks = sections.get(section, [])
        if not blocks:
            continue
        section_urls[section] = blocks[0].url
        section_evidence[section] = blocks[0].text[:700]
        text_parts.append(label)
        text_parts.extend(block.text for block in blocks[:80])
        text_parts.append("")

    warnings: list[str] = []
    if removed:
        warnings.append(f"normalized_removed_blocks:{removed}")
    if not text_parts:
        warnings.append("normalized_empty_content")

    return NormalizedWebsiteContent(
        combined_text="\n".join(text_parts).strip(),
        sections=sections,
        section_urls=section_urls,
        section_evidence=section_evidence,
        project_names=project_names,
        removed_blocks=removed,
        warnings=warnings,
    )
