"""Anti-detection: structural randomization, deploy staggering, content quality checks."""

import hashlib
import random
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# --- Structural randomization ---

def _seed_from_url(domain: str, path: str, doorway_id: int) -> int:
    """Deterministic seed for this page. Same page = same layout."""
    s = f"{domain}|{path}|{doorway_id}"
    return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16)


def get_layout_variant(domain: str, path: str, doorway_id: int, num_variants: int = 3) -> int:
    """Layout variant 0..num_variants-1. Deterministic per page."""
    seed = _seed_from_url(domain, path, doorway_id)
    rng = random.Random(seed)
    return rng.randint(0, num_variants - 1)


def shuffle_block_order(
    domain: str,
    path: str,
    doorway_id: int,
    block_names: List[str],
) -> List[str]:
    """Return blocks in randomized order. Same page = same order."""
    seed = _seed_from_url(domain, path, doorway_id)
    order = block_names.copy()
    random.Random(seed).shuffle(order)
    return order


def get_schema_variant(domain: str, path: str, doorway_id: int) -> str:
    """'article' | 'webpage' | 'both' — varies schema type per page."""
    seed = _seed_from_url(domain, path, doorway_id)
    variants = ["article", "webpage", "both"]
    return variants[seed % len(variants)]


# --- Deploy staggering ---

@dataclass
class StaggerConfig:
    min_delay_sec: float = 30
    max_delay_sec: float = 180
    jitter_sec: float = 10


def compute_deploy_delay(
    index: int,
    total: int,
    config: Optional[StaggerConfig] = None,
) -> float:
    """Delay in seconds before deploy at index. Adds jitter."""
    cfg = config or StaggerConfig()
    if total <= 1:
        return 0
    base = cfg.min_delay_sec + (index / max(1, total - 1)) * (cfg.max_delay_sec - cfg.min_delay_sec)
    jitter = random.uniform(-cfg.jitter_sec, cfg.jitter_sec)
    return max(0, base + jitter)


def sleep_for_stagger(index: int, total: int, config: Optional[StaggerConfig] = None) -> None:
    """Block for the computed delay. Call between batch deploys."""
    delay = compute_deploy_delay(index, total, config)
    if delay > 0:
        time.sleep(delay)


# --- Content quality checks ---

TEMPLATE_PHRASE_BLACKLIST = [
    r"\b(данная статья|этот материал|наш сайт)\b",
    r"\bв данной статье\b",
    r"\bкак вы знаете\b",
    r"\bв заключение\b",
    r"\bподводя итоги\b",
    r"\bв этой статье мы рассмотрим\b",
    r"\bздесь вы найдёте\b",
    r"\bмы расскажем\b",
    r"\bвы узнаете\b",
    r"^(заголовок|введение|заключение)$",
]

MIN_CONTENT_LENGTH = 400
MIN_TITLE_LENGTH = 20
MIN_DESCRIPTION_LENGTH = 80


@dataclass
class ContentQualityResult:
    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def check_content_quality(
    title: str,
    meta_description: str,
    content: str,
    keyword: Optional[str] = None,
) -> ContentQualityResult:
    """
    Pre-deploy quality checks. Returns ok=False if critical issues.
    """
    errors: List[str] = []
    warnings: List[str] = []

    title = (title or "").strip()
    meta = (meta_description or "").strip()
    content = (content or "").strip()

    # Length
    if len(content) < MIN_CONTENT_LENGTH:
        errors.append(f"Content too short: {len(content)} chars (min {MIN_CONTENT_LENGTH})")
    elif len(content) < 600:
        warnings.append(f"Content may be too short for depth: {len(content)} chars")

    if len(title) < MIN_TITLE_LENGTH:
        errors.append(f"Title too short: {len(title)} chars (min {MIN_TITLE_LENGTH})")

    if len(meta) < MIN_DESCRIPTION_LENGTH:
        warnings.append(f"Meta description short: {len(meta)} chars (recommended {MIN_DESCRIPTION_LENGTH}+)")

    # Keyword alignment
    if keyword:
        kw_lower = keyword.lower()
        if kw_lower not in title.lower():
            warnings.append(f"Keyword '{keyword}' not in title")
        if kw_lower not in content.lower():
            warnings.append(f"Keyword '{keyword}' not in content")

    # Template phrases
    text = f"{title} {meta} {content}"
    for pat in TEMPLATE_PHRASE_BLACKLIST:
        if re.search(pat, text, re.IGNORECASE):
            warnings.append(f"Template phrase detected: {pat}")

    return ContentQualityResult(
        ok=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
