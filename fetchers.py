"""
Data fetchers for Crossref, bioRxiv, and medRxiv APIs.
"""
import os
import re
import time
import requests
from datetime import datetime, timezone, timedelta, date

CROSSREF_API = "https://api.crossref.org/works"
BIORXIV_API = "https://api.biorxiv.org/details/biorxiv"
MEDRXIV_API = "https://api.biorxiv.org/details/medrxiv"
HEADERS = {"User-Agent": "weekly-bio-dashboard/3.0 (strict + tech/bio split) (local use)"}
CROSSREF_MAILTO = os.getenv("CROSSREF_MAILTO", "").strip()
CROSSREF_MIN_INTERVAL_S = float(os.getenv("CROSSREF_MIN_INTERVAL_S", "0.15"))
CROSSREF_MAX_RETRIES = int(os.getenv("CROSSREF_MAX_RETRIES", "3"))
PREPRINT_MAX_RETRIES = int(os.getenv("PREPRINT_MAX_RETRIES", "3"))

from config import JOURNAL_ISSN


# ========================
# Normalization helpers
# ========================
def norm_journal(s: str) -> str:
    s = (s or "").strip()
    s = s.replace("&amp;", "&")
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def norm_text(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "")).strip()


def clean_abstract(x: str) -> str:
    s = x or ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_crossref_date(it: dict) -> str:
    for k in ["published-online", "published", "issued"]:
        try:
            parts = (it.get(k, {}).get("date-parts") or [[None]])[0]
            if parts and parts[0]:
                y = int(parts[0])
                m = int(parts[1]) if len(parts) > 1 and parts[1] else 1
                d = int(parts[2]) if len(parts) > 2 and parts[2] else 1
                return str(date(y, m, d))
        except Exception:
            continue
    return ""


# ========================
# Crossref fetcher
# ========================
def crossref_fetch(journal: str, days: int, rows: int = 200) -> tuple[list[dict], str]:
    """
    Fetch recent journal articles from Crossref.
    Returns (items_list, status_string).
    """
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    base_filter = f"from-online-pub-date:{start},until-online-pub-date:{end},type:journal-article"

    issns = JOURNAL_ISSN.get(journal, [])
    queries = issns if issns else [None]

    out: list[dict] = []
    status = "ok"
    for issn in queries:
        flt = base_filter + (f",issn:{issn}" if issn else "")
        params = {
            "filter": flt,
            "rows": rows,
            "sort": "published-online",
            "order": "desc",
            "select": "DOI,title,issued,published,published-online,container-title,URL,abstract",
        }
        if CROSSREF_MAILTO:
            params["mailto"] = CROSSREF_MAILTO
        if issn is None:
            params["query.container-title"] = journal

        time.sleep(CROSSREF_MIN_INTERVAL_S)

        r = None
        for attempt in range(CROSSREF_MAX_RETRIES):
            try:
                r = requests.get(CROSSREF_API, params=params, headers=HEADERS, timeout=30)
                r.raise_for_status()
                break
            except requests.exceptions.RequestException:
                time.sleep(0.6 * (2 ** attempt))

        if r is None or getattr(r, "status_code", 500) >= 400:
            status = f"error (HTTP {getattr(r, 'status_code', '?')})" if r else "error (no response)"
            items = []
        else:
            try:
                items = r.json().get("message", {}).get("items", [])
            except Exception:
                status = "error (JSON parse)"
                items = []

        for it in items:
            title = (it.get("title") or [""])[0]
            container = (it.get("container-title") or [""])[0]
            doi = it.get("DOI") or ""
            url = it.get("URL") or ""
            abstract = clean_abstract(it.get("abstract") or "")
            pub_date = parse_crossref_date(it)
            out.append(
                {
                    "source": "Journal",
                    "journal": container or journal,
                    "query_journal": journal,
                    "date": pub_date,
                    "title": norm_text(title),
                    "doi": doi,
                    "url": url,
                    "abstract": abstract,
                }
            )
    return out, status


# ========================
# bioRxiv fetcher (with retry)
# ========================
def biorxiv_fetch(days: int, cursor: int = 0, max_pages: int = 6) -> tuple[list[dict], str]:
    """
    Fetch recent bioRxiv preprints.
    Returns (items_list, status_string).
    """
    return _preprint_fetch(BIORXIV_API, "bioRxiv", days, cursor, max_pages)


# ========================
# medRxiv fetcher
# ========================
def medrxiv_fetch(days: int, cursor: int = 0, max_pages: int = 6) -> tuple[list[dict], str]:
    """
    Fetch recent medRxiv preprints (same API schema as bioRxiv).
    Returns (items_list, status_string).
    """
    return _preprint_fetch(MEDRXIV_API, "medRxiv", days, cursor, max_pages)


def _preprint_fetch(
    api_base: str, source_label: str, days: int, cursor: int = 0, max_pages: int = 6
) -> tuple[list[dict], str]:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)

    out: list[dict] = []
    status = "ok"
    page = 0
    while page < max_pages:
        url = f"{api_base}/{start}/{end}/{cursor}"

        r = None
        for attempt in range(PREPRINT_MAX_RETRIES):
            try:
                r = requests.get(url, timeout=30)
                r.raise_for_status()
                break
            except requests.exceptions.RequestException:
                time.sleep(0.6 * (2 ** attempt))

        if r is None or getattr(r, "status_code", 500) >= 400:
            status = f"error (HTTP {getattr(r, 'status_code', '?')})" if r else "error (no response)"
            break

        try:
            data = r.json()
        except Exception:
            status = "error (JSON parse)"
            break

        collection = data.get("collection", [])
        if not collection:
            break

        for it in collection:
            doi = it.get("doi", "") or ""
            prefix = "https://www.biorxiv.org" if "biorxiv" in api_base.lower() else "https://www.medrxiv.org"
            out.append(
                {
                    "source": "Preprint",
                    "journal": source_label,
                    "query_journal": source_label,
                    "date": it.get("date", "") or "",
                    "title": norm_text(it.get("title", "") or ""),
                    "doi": doi,
                    "url": f"{prefix}/content/{doi}" if doi else "",
                    "abstract": norm_text(it.get("abstract", "") or ""),
                }
            )
        cursor += len(collection)
        page += 1
        time.sleep(0.15)

    return out, status
