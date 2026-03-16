"""
Scoring, tagging, trend mining, and relevance logic.
"""
import re
from collections import Counter, defaultdict
import pandas as pd

from config import (
    CORE_KEYWORDS,
    BIG_DEAL_HINTS,
    TREND_LEXICON,
    TECH_KEYS,
    BIO_KEYS,
)

# Short acronyms that need word-boundary matching to avoid false positives.
# Everything else uses plain substring matching.
# >>> Update this set if you add short (<=3 char) terms to CORE_KEYWORDS <<<
WORD_BOUNDARY_TERMS = {
    "gwas", "tad", "ipsc",
}


def safe_lower(s: str) -> str:
    return (s or "").lower()


def contains_any(text: str, terms: list[str]) -> int:
    """
    Count how many *distinct* terms match in text.
    Uses word-boundary regex for short acronyms, plain substring for the rest.
    Longer terms are checked first so overlapping shorter terms are skipped
    (e.g. "spatial transcriptomics" won't also count "spatial").
    """
    t = safe_lower(text)
    # Sort terms longest-first to prevent double-counting overlapping substrings
    sorted_terms = sorted(terms, key=len, reverse=True)
    matched_spans: list[tuple[int, int]] = []
    hits = 0

    for term in sorted_terms:
        term_l = safe_lower(term)
        if term_l in WORD_BOUNDARY_TERMS:
            pattern = rf"\b{re.escape(term_l)}\b"
            match = re.search(pattern, t)
            if match:
                start, end = match.start(), match.end()
                if not _overlaps(start, end, matched_spans):
                    matched_spans.append((start, end))
                    hits += 1
        else:
            idx = t.find(term_l)
            if idx >= 0:
                start, end = idx, idx + len(term_l)
                if not _overlaps(start, end, matched_spans):
                    matched_spans.append((start, end))
                    hits += 1
    return hits


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    """Check if [start, end) overlaps with any existing span."""
    for s, e in spans:
        if start < e and end > s:
            return True
    return False


# ========================
# Scoring + tags
# ========================
def score_and_tags(title: str, abstract: str) -> tuple[float, list[str], dict]:
    """
    Score a paper and return (score, tags, hit_counts).
    - Title matches weighted 2x over abstract-only matches
    - Co-occurrence bonus when both TECH and BIO tags fire
    - Word-boundary matching for short acronyms
    - Longest-first matching to avoid double-counting
    """
    title_text = title or ""
    abstract_text = abstract or ""
    full_text = f"{title_text} {abstract_text}"

    tags: list[str] = []
    score = 0.0
    hit_counts: dict = {}

    # Count hits per tag category
    for tag, terms in CORE_KEYWORDS.items():
        hits_full = contains_any(full_text, terms)
        hits_title = contains_any(title_text, terms)
        hit_counts[tag] = hits_full
        if hits_full > 0:
            tags.append(tag)
        # Title bonus: each title hit adds +1 to effective count
        hit_counts[f"{tag}_title"] = hits_title

    # Base scoring by tag category — tech categories get higher weight
    for tag in TECH_KEYS:
        w = 3
        effective = min(6, hit_counts.get(tag, 0))
        title_bonus = min(3, hit_counts.get(f"{tag}_title", 0))
        score += effective * w + title_bonus * 2  # title hits get extra weight

    for tag in BIO_KEYS:
        effective = min(6, hit_counts.get(tag, 0))
        title_bonus = min(3, hit_counts.get(f"{tag}_title", 0))
        score += effective * 2 + title_bonus * 1.5

    # Method/platform bonus
    score += min(
        8,
        contains_any(full_text, ["assay", "platform", "technology", "workflow", "method", "pipeline"]) * 2,
    )

    # Co-occurrence bonus: papers hitting both TECH and BIO tags are more relevant
    has_tech = any(hit_counts.get(k, 0) > 0 for k in TECH_KEYS)
    has_bio = any(hit_counts.get(k, 0) > 0 for k in BIO_KEYS)
    if has_tech and has_bio:
        score += 6  # significant bonus for cross-domain relevance

    return score, tags, hit_counts


def is_core_by_logic(hit_counts: dict) -> bool:
    """Core = has at least one tech OR one bio keyword hit."""
    tech = any(hit_counts.get(k, 0) > 0 for k in TECH_KEYS)
    bio = any(hit_counts.get(k, 0) > 0 for k in BIO_KEYS)
    return tech or bio


def is_big_deal(title: str, abstract: str) -> bool:
    text = safe_lower(f"{title or ''} {abstract or ''}")
    hint_hits = sum(1 for h in BIG_DEAL_HINTS if h in text)
    return hint_hits >= 2


# ========================
# Journal weighting
# ========================
# Lower the multiplier for broad journals to avoid them dominating Must-read.
# Set to 1.0 for no adjustment. Add your own journals here as needed.
JOURNAL_SCORE_MULTIPLIER = {
    "nature communications": 0.5,
    "elife": 0.5,
}


def journal_multiplier(journal_name: str, source: str) -> float:
    if source != "Journal":
        return 1.0
    return float(JOURNAL_SCORE_MULTIPLIER.get(safe_lower(journal_name).strip(), 1.0))


# ========================
# Trend mining
# ========================
def normalize_text_for_trend(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[^a-z0-9\-\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def trend_summary(df: pd.DataFrame, top_k: int = 3):
    pool = df[df["core"] | df["big_deal"]].copy()
    if pool.empty:
        return []
    trend_score = Counter()
    trend_examples = defaultdict(list)
    for idx, r in pool.iterrows():
        text = normalize_text_for_trend(
            (r.get("title", "") or "") + " " + (r.get("abstract", "") or "")
        )
        weight = 2.0 if bool(r.get("core")) else 1.0
        for tname, kws in TREND_LEXICON.items():
            hits = sum(1 for kw in kws if kw in text)
            if hits > 0:
                trend_score[tname] += weight * hits
                trend_examples[tname].append(idx)
    if not trend_score:
        return []
    top_trends = [t for t, _ in trend_score.most_common(top_k)]
    out = []
    for tname in top_trends:
        idxs = trend_examples[tname]
        sub = pool.loc[idxs].copy()
        sub["date_sort"] = pd.to_datetime(sub["date"], errors="coerce")
        sub = sub.sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])
        examples = sub.head(5)[["journal", "date", "title", "url"]].copy()
        n_core = int(sub["core"].sum())
        n_total = int(len(sub))
        tag_counts = Counter()
        for tags in sub["tags"]:
            for t in (tags or []):
                tag_counts[t] += 1
        top_tags = [t for t, _ in tag_counts.most_common(4)]
        tag_str = " · ".join(top_tags) if top_tags else "mixed signals"
        one_liner = f"{tname}: {n_total} papers (core {n_core}); dominant signals: {tag_str}."
        out.append((tname, one_liner, examples))
    return out
