"""
Weekly Bio Dashboard — Email Digest

Fetches papers using the same pipeline as app.py, builds an HTML email,
and sends it via SMTP. Designed to be run by launchd/cron weekly.

Usage:
    python send_digest.py            # send email
    python send_digest.py --dry-run  # save to digest_preview.html instead

Environment variables (set in .env.digest):
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, EMAIL_TO, EMAIL_FROM
"""
import os
import re
import sys
import logging
import smtplib
import argparse
import webbrowser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
import pandas as pd

from config import (
    JOURNALS,
    MUST_READ_N,
    MAX_PER_JOURNAL_MUST_READ,
    TECH_KEYS,
    BIO_KEYS,
    FOCUS_AI_KEYS,
    FOCUS_AREA_1_KEYS,
    FOCUS_AREA_2_KEYS,
)
from fetchers import (
    norm_journal,
    crossref_fetch,
    biorxiv_fetch,
    medrxiv_fetch,
)
from scoring import (
    score_and_tags,
    is_core_by_logic,
    is_big_deal,
    journal_multiplier,
    trend_summary,
)

log = logging.getLogger("digest")

# ========================
# SMTP config (env vars)
# ========================
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")        # <-- set your email in .env.digest
EMAIL_FROM = os.environ.get("EMAIL_FROM", "") or SMTP_USER

# ========================
# Digest parameters
# ========================
JOURNAL_DAYS = 15
PREPRINT_DAYS = 7
MAX_ROWS = 300
JOURNAL_CORE_THRESH = 12
PREPRINT_CORE_THRESH = 14

# ========================
# Journal whitelist (same as app.py)
# ========================
BASE_WHITELIST = {norm_journal(j) for j in JOURNALS}

ALIASES = {
    "cell": {"cell (cambridge, mass.)"},
    "nature": {"nature (london)"},
    "science": {"science (new york, n.y.)"},
    "science advances": {"sci adv", "science adv"},
    "nature communications": {"nat commun", "nature comm", "nat communications"},
    "nature biotechnology": {"nat biotechnol", "nature biotech"},
    "nature methods": {"nat methods"},
    "nature immunology": {"nat immunol"},
    "cancer cell": set(),
    "immunity": set(),
}

ALLOWED_JOURNALS = set(BASE_WHITELIST)
for _canon, _vars in ALIASES.items():
    if norm_journal(_canon) in BASE_WHITELIST:
        ALLOWED_JOURNALS.add(norm_journal(_canon))
        for v in _vars:
            ALLOWED_JOURNALS.add(norm_journal(v))


# ========================
# Data pipeline
# ========================
def fetch_and_score() -> tuple[pd.DataFrame, dict, str]:
    all_items: list[dict] = []
    fetch_status: dict = {}

    for j in JOURNALS:
        items, status = crossref_fetch(j, days=JOURNAL_DAYS, rows=MAX_ROWS)
        all_items.extend(items)
        fetch_status[j] = {"count": len(items), "status": status}

    items, status = biorxiv_fetch(days=PREPRINT_DAYS)
    all_items.extend(items)
    fetch_status["bioRxiv"] = {"count": len(items), "status": status}

    items, status = medrxiv_fetch(days=PREPRINT_DAYS)
    all_items.extend(items)
    fetch_status["medRxiv"] = {"count": len(items), "status": status}

    df = pd.DataFrame(all_items)

    # Journal whitelist filter
    if not df.empty:
        df["journal_norm"] = df["journal"].apply(norm_journal)
        keep = (df["source"] == "Preprint") | (df["journal_norm"].isin(ALLOWED_JOURNALS))
        df = df[keep].copy()
        df = df.drop(columns=["journal_norm"])

    # Deduplication
    if not df.empty:
        df = df.copy()
        df["title_norm"] = df["title"].astype(str).str.lower().str.strip()
        df["journal_norm2"] = df["journal"].astype(str).str.lower().str.strip()
        df["doi_norm"] = (
            df.get("doi", "")
              .astype(str).str.lower().str.strip()
              .str.replace(r"^https?://(dx\.)?doi\.org/", "", regex=True)
        )
        df["_has_doi"] = df["doi_norm"].ne("") & df["doi_norm"].ne("nan")
        df = df.sort_values(by=["source"], ascending=[True])
        df_with_doi = df[df["_has_doi"]].drop_duplicates(subset=["doi_norm"], keep="first")
        df_no_doi = df[~df["_has_doi"]]
        df = pd.concat([df_with_doi, df_no_doi], ignore_index=True)
        df["_has_doi"] = df["doi_norm"].ne("") & df["doi_norm"].ne("nan")
        df = df.sort_values(by=["_has_doi", "date"], ascending=[False, False])
        df = df.drop_duplicates(subset=["journal_norm2", "title_norm"], keep="first")
        df = df.drop(columns=["title_norm", "journal_norm2", "doi_norm", "_has_doi"])

    # Scoring
    scores_raw, scores_adj, tags_list, hit_list = [], [], [], []
    core_logic_list, big_list, mult_list = [], [], []
    for _, r in df.iterrows():
        s_raw, tags, hits = score_and_tags(r.get("title", ""), r.get("abstract", ""))
        mult = journal_multiplier(r.get("query_journal", r.get("journal", "")), r.get("source", ""))
        s_adj = float(s_raw) * mult
        scores_raw.append(float(s_raw))
        scores_adj.append(float(s_adj))
        mult_list.append(float(mult))
        tags_list.append(tags)
        hit_list.append(hits)
        core_logic_list.append(is_core_by_logic(hits))
        big_list.append(is_big_deal(r.get("title", ""), r.get("abstract", "")))

    df["score_raw"] = scores_raw
    df["score"] = scores_adj
    df["journal_mult"] = mult_list
    df["tags"] = tags_list
    df["hits"] = hit_list
    df["core_by_logic"] = core_logic_list
    df["big_deal"] = big_list
    df["date_sort"] = pd.to_datetime(df["date"], errors="coerce")
    df["is_tech"] = df["hits"].apply(lambda h: any((h.get(k, 0) or 0) > 0 for k in TECH_KEYS))
    df["is_bio"] = df["hits"].apply(lambda h: any((h.get(k, 0) or 0) > 0 for k in BIO_KEYS))
    df["is_ai"] = df["hits"].apply(lambda h: (h.get("computational", 0) or 0) > 0)

    # Core thresholds
    df["core"] = False
    df.loc[df["source"] == "Journal", "core"] = df["core_by_logic"] & (df["score"] >= JOURNAL_CORE_THRESH)
    df.loc[df["source"] == "Preprint", "core"] = df["core_by_logic"] & (df["score"] >= PREPRINT_CORE_THRESH)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return df, fetch_status, timestamp


# ========================
# Section builders
# ========================
def cap_per_journal(df: pd.DataFrame, cap: int) -> pd.DataFrame:
    if cap is None or cap <= 0 or df.empty:
        return df
    return df.groupby("journal", group_keys=False).head(int(cap))


def must_read_tech(df_j: pd.DataFrame) -> pd.DataFrame:
    tech = df_j[df_j["is_tech"]].copy()
    tech = tech.sort_values(by=["score", "date_sort"], ascending=[False, False])
    return cap_per_journal(tech, MAX_PER_JOURNAL_MUST_READ).head(MUST_READ_N)


def must_read_bio(df_j: pd.DataFrame) -> pd.DataFrame:
    bio = df_j[df_j["is_bio"]].copy()
    bio = bio.sort_values(by=["score", "date_sort"], ascending=[False, False])
    return cap_per_journal(bio, MAX_PER_JOURNAL_MUST_READ).head(MUST_READ_N)


def must_read_preprints(df_p: pd.DataFrame) -> pd.DataFrame:
    return df_p[df_p["core"]].sort_values(
        by=["score", "date_sort"], ascending=[False, False]
    ).head(MUST_READ_N)


def focus_ai(df: pd.DataFrame) -> pd.DataFrame:
    mask = df.apply(
        lambda r: any(
            k in ((r.get("title", "") or "") + " " + (r.get("abstract", "") or "")).lower()
            for k in FOCUS_AI_KEYS
        ),
        axis=1,
    )
    return df[mask].sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False]).head(15)


def focus_area_1(df: pd.DataFrame) -> pd.DataFrame:
    mask = df.apply(
        lambda r: any(
            k in ((r.get("title", "") or "") + " " + (r.get("abstract", "") or "")).lower()
            for k in FOCUS_AREA_1_KEYS
        ),
        axis=1,
    )
    return df[mask].sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False]).head(15)


def focus_area_2(df: pd.DataFrame) -> pd.DataFrame:
    mask = df.apply(
        lambda r: any(
            k in ((r.get("title", "") or "") + " " + (r.get("abstract", "") or "")).lower()
            for k in FOCUS_AREA_2_KEYS
        ),
        axis=1,
    )
    return df[mask].sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False]).head(15)


# ========================
# HTML email builder
# ========================
def _esc(s: str) -> str:
    """Escape HTML entities."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_paper_table(df: pd.DataFrame, title: str) -> str:
    if df.empty:
        return (
            f'<div style="margin:24px 0;">'
            f'<h2 style="color:#1a365d;border-bottom:2px solid #e2e8f0;padding-bottom:6px;">{_esc(title)}</h2>'
            f'<p style="color:#a0aec0;font-size:14px;">No papers found.</p></div>'
        )
    rows = []
    for _, row in df.iterrows():
        tags_str = ", ".join(row.get("tags", []) or [])
        score_val = row.get("score", 0)
        score_color = "#38a169" if score_val >= 20 else "#718096"
        url = _esc(row.get("url", ""))
        paper_title = _esc(row.get("title", "Untitled"))
        journal = _esc(row.get("journal", ""))
        date_str = _esc(str(row.get("date", "")))

        link = f'<a href="{url}" style="color:#2b6cb0;text-decoration:none;font-weight:600;">{paper_title}</a>' if url else paper_title

        rows.append(
            f'<tr style="border-bottom:1px solid #edf2f7;">'
            f'<td style="padding:10px 4px;">'
            f'{link}<br/>'
            f'<span style="color:#718096;font-size:13px;">'
            f'{journal} | {date_str}'
            f' | <span style="color:{score_color};font-weight:600;">score: {score_val:.0f}</span>'
            f'{(" | " + _esc(tags_str)) if tags_str else ""}'
            f'</span></td></tr>'
        )

    return (
        f'<div style="margin:24px 0;">'
        f'<h2 style="color:#1a365d;border-bottom:2px solid #e2e8f0;padding-bottom:6px;">{_esc(title)}</h2>'
        f'<table style="width:100%;border-collapse:collapse;">{"".join(rows)}</table></div>'
    )


def render_trends(trends: list, title: str) -> str:
    if not trends:
        return ""
    items = []
    for tname, one_liner, _examples in trends:
        items.append(f'<li style="margin:6px 0;"><strong>{_esc(tname)}</strong>: {_esc(one_liner)}</li>')
    return (
        f'<div style="margin:24px 0;">'
        f'<h2 style="color:#1a365d;border-bottom:2px solid #e2e8f0;padding-bottom:6px;">{_esc(title)}</h2>'
        f'<ul style="padding-left:20px;">{"".join(items)}</ul></div>'
    )


def render_fetch_status(fetch_status: dict) -> str:
    rows = []
    for src, info in fetch_status.items():
        status_emoji = "OK" if info["status"] == "ok" else "WARN"
        color = "#38a169" if info["status"] == "ok" else "#e53e3e"
        rows.append(
            f'<tr style="border-bottom:1px solid #edf2f7;">'
            f'<td style="padding:4px 8px;font-size:13px;">{_esc(src)}</td>'
            f'<td style="padding:4px 8px;font-size:13px;text-align:center;">{info["count"]}</td>'
            f'<td style="padding:4px 8px;font-size:13px;color:{color};text-align:center;">{status_emoji}</td>'
            f'</tr>'
        )
    return (
        f'<div style="margin:24px 0;">'
        f'<h2 style="color:#1a365d;border-bottom:2px solid #e2e8f0;padding-bottom:6px;">Fetch Status</h2>'
        f'<table style="width:100%;border-collapse:collapse;max-width:400px;">'
        f'<tr style="background:#f7fafc;"><th style="padding:4px 8px;text-align:left;font-size:13px;">Source</th>'
        f'<th style="padding:4px 8px;text-align:center;font-size:13px;">Papers</th>'
        f'<th style="padding:4px 8px;text-align:center;font-size:13px;">Status</th></tr>'
        f'{"".join(rows)}</table></div>'
    )


def build_email_html(
    tech: pd.DataFrame,
    bio: pd.DataFrame,
    preprints: pd.DataFrame,
    ai: pd.DataFrame,
    area1: pd.DataFrame,
    area2: pd.DataFrame,
    trends_j: list,
    trends_p: list,
    fetch_status: dict,
    timestamp: str,
    total_papers: int,
) -> str:
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=JOURNAL_DAYS)).strftime("%b %d")
    end_date = now.strftime("%b %d, %Y")
    n_core = int(tech.get("core", pd.Series(dtype=bool)).sum()
                 + bio.get("core", pd.Series(dtype=bool)).sum()
                 + preprints.get("core", pd.Series(dtype=bool)).sum())

    header = (
        f'<div style="background:#1a365d;color:white;padding:24px 20px;border-radius:8px 8px 0 0;">'
        f'<h1 style="margin:0;font-size:22px;">Weekly Bio Dashboard Digest</h1>'
        f'<p style="margin:6px 0 0;opacity:0.85;font-size:14px;">'
        f'{start_date} &ndash; {end_date} | {total_papers} papers scanned</p></div>'
    )

    sections = [
        render_paper_table(tech, f"Must-Read — Tech (Top {len(tech)})"),
        render_paper_table(bio, f"Must-Read — Bio (Top {len(bio)})"),
        render_paper_table(preprints, f"Must-Read — Preprints (Top {len(preprints)})"),
        render_paper_table(ai, f"Focus: AI/ML ({len(ai)} papers)"),
        render_paper_table(area1, f"Focus 1 ({len(area1)} papers)"),
        render_paper_table(area2, f"Focus 2 ({len(area2)} papers)"),
        render_trends(trends_j, "Journal Trends"),
        render_trends(trends_p, "Preprint Trends"),
        render_fetch_status(fetch_status),
    ]

    footer = (
        f'<div style="color:#a0aec0;font-size:12px;padding:16px 0;border-top:1px solid #e2e8f0;margin-top:24px;">'
        f'Generated by Weekly Bio Dashboard | {_esc(timestamp)}<br/>'
        f'Dashboard: <a href="http://localhost:8501" style="color:#a0aec0;">http://localhost:8501</a>'
        f'</div>'
    )

    body = (
        f'<html><body style="font-family:-apple-system,Helvetica,Arial,sans-serif;'
        f'max-width:700px;margin:0 auto;padding:0;background:#ffffff;color:#1a202c;">'
        f'{header}'
        f'<div style="padding:0 20px;">'
        f'{"".join(sections)}'
        f'{footer}'
        f'</div></body></html>'
    )
    return body


# ========================
# Plain-text fallback
# ========================
def html_to_plain(html: str) -> str:
    text = re.sub(r'<a\s+href="([^"]*)"[^>]*>([^<]*)</a>', r'\2 (\1)', html)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</tr>', '\n', text)
    text = re.sub(r'</li>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&ndash;', '-', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ========================
# Email sender
# ========================
def send_email(subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    plain = html_to_plain(html_body)
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        if SMTP_PORT != 25:
            server.starttls()
        if SMTP_USER and SMTP_PASSWORD:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())


# ========================
# Main
# ========================
def main():
    parser = argparse.ArgumentParser(description="Weekly Bio Dashboard email digest")
    parser.add_argument("--dry-run", action="store_true", help="Save HTML to file instead of sending email")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    try:
        log.info("Starting weekly digest...")
        df, fetch_status, ts = fetch_and_score()
        log.info(f"Fetched {len(df)} papers total")

        df_j = df[df["source"] == "Journal"].copy()
        df_p = df[df["source"] == "Preprint"].copy()
        df_j = df_j.sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])
        df_p = df_p.sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])

        # Build sections
        tech = must_read_tech(df_j)
        bio = must_read_bio(df_j)
        preprints = must_read_preprints(df_p)
        ai = focus_ai(df)
        area1 = focus_area_1(df)
        area2 = focus_area_2(df)
        trends_j = trend_summary(df_j, top_k=3)
        trends_p = trend_summary(df_p, top_k=3)

        log.info(f"Sections: tech={len(tech)}, bio={len(bio)}, preprints={len(preprints)}, ai={len(ai)}, focus1={len(area1)}, focus2={len(area2)}")

        # Build HTML
        html = build_email_html(
            tech, bio, preprints, ai, area1, area2,
            trends_j, trends_p,
            fetch_status, ts, len(df),
        )

        today = datetime.now().strftime("%b %d, %Y")
        subject = f"Weekly Bio Dashboard Digest - {today}"

        if args.dry_run:
            preview_path = os.path.join(os.path.dirname(__file__) or ".", "digest_preview.html")
            with open(preview_path, "w") as f:
                f.write(html)
            log.info(f"Dry run: saved to {preview_path}")
            webbrowser.open(f"file://{os.path.abspath(preview_path)}")
        else:
            if not SMTP_USER or not SMTP_PASSWORD:
                log.error("SMTP_USER and SMTP_PASSWORD must be set in environment (see .env.digest)")
                sys.exit(1)
            if not EMAIL_TO:
                log.error("EMAIL_TO must be set in environment (see .env.digest)")
                sys.exit(1)
            send_email(subject, html)
            log.info(f"Digest sent to {EMAIL_TO}")

    except Exception:
        log.exception("Digest failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
