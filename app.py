# Weekly Bio Dashboard v3 — modular, with search, abstracts, focus sections, fetch status
import re
import os
import json
import hashlib
import pandas as pd
import streamlit as st
from datetime import datetime, timezone
from collections import Counter

from config import (
    JOURNALS,
    INCLUDE_BIORXIV_DEFAULT,
    INCLUDE_MEDRXIV_DEFAULT,
    CORE_KEYWORDS,
    FOCUS_AREA_1_KEYS,
    FOCUS_AREA_2_KEYS,
    FOCUS_AI_KEYS,
    MUST_READ_N,
    MAX_PER_JOURNAL_MUST_READ,
    TECH_KEYS,
    BIO_KEYS,
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

# ========================
# STRICT journal whitelist
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
for canon, vars_ in ALIASES.items():
    if norm_journal(canon) in BASE_WHITELIST:
        ALLOWED_JOURNALS.add(norm_journal(canon))
        for v in vars_:
            ALLOWED_JOURNALS.add(norm_journal(v))


# ========================
# Saved papers (bookmarks)
# ========================
SAVED_PAPERS_FILE = os.path.join(os.path.dirname(__file__) or ".", "saved_papers.json")
DEFAULT_CATEGORIES = ["To Read", "For Lab Meeting", "Key Reference", "Methods to Try"]


def _paper_key(row) -> str:
    """Generate a unique key for a paper (DOI preferred, else hash of title+journal)."""
    doi = str(row.get("doi", "") or "").strip()
    if doi and doi != "nan":
        return doi
    raw = f"{row.get('title', '')}|{row.get('journal', '')}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def load_saved_papers() -> dict:
    if "saved_papers" not in st.session_state:
        if os.path.exists(SAVED_PAPERS_FILE):
            try:
                with open(SAVED_PAPERS_FILE, "r") as f:
                    st.session_state["saved_papers"] = json.load(f)
            except (json.JSONDecodeError, IOError):
                st.session_state["saved_papers"] = {"papers": {}, "categories": list(DEFAULT_CATEGORIES)}
        else:
            st.session_state["saved_papers"] = {"papers": {}, "categories": list(DEFAULT_CATEGORIES)}
    return st.session_state["saved_papers"]


def _flush_saved():
    data = st.session_state.get("saved_papers", {"papers": {}, "categories": list(DEFAULT_CATEGORIES)})
    with open(SAVED_PAPERS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_paper(key: str, row, category: str):
    data = load_saved_papers()
    data["papers"][key] = {
        "title": str(row.get("title", "")),
        "journal": str(row.get("journal", "")),
        "date": str(row.get("date", "")),
        "url": str(row.get("url", "")),
        "category": category,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    _flush_saved()


def remove_paper(key: str):
    data = load_saved_papers()
    data["papers"].pop(key, None)
    _flush_saved()


def add_category(name: str):
    data = load_saved_papers()
    name = name.strip()
    if name and name not in data["categories"]:
        data["categories"].append(name)
        _flush_saved()


def get_categories() -> list[str]:
    return load_saved_papers().get("categories", list(DEFAULT_CATEGORIES))


def is_paper_saved(key: str) -> str | None:
    """Return category name if saved, else None."""
    return load_saved_papers()["papers"].get(key, {}).get("category")


# ========================
# Rendering helpers
# ========================
def render_df(d: pd.DataFrame, show_abstract: bool = False, key_prefix: str = ""):
    """Render a dataframe of papers. Optionally show abstracts in expanders.
    key_prefix must be unique per call site to avoid duplicate Streamlit widget keys."""
    if d.empty:
        st.caption("No results.")
        return
    if show_abstract:
        categories = get_categories()
        for _idx, row in d.iterrows():
            title = row.get("title", "Untitled")
            url = row.get("url", "")
            journal = row.get("journal", "")
            date_str = row.get("date", "")
            score_val = row.get("score", 0)
            tags = row.get("tags", [])
            abstract = row.get("abstract", "")
            tag_str = ", ".join(tags) if tags else ""
            pk = _paper_key(row)

            link = f"[{title}]({url})" if url else title
            saved_cat = is_paper_saved(pk)
            label_prefix = f"[{saved_cat}] " if saved_cat else ""

            with st.expander(f"{label_prefix}{title[:120]}..." if len(title) > 120 else f"{label_prefix}{title}", expanded=False):
                st.markdown(f"### {link}")
                st.markdown(f"**{journal}** &nbsp;|&nbsp; {date_str} &nbsp;|&nbsp; score: **{score_val:.0f}**"
                            + (f" &nbsp;|&nbsp; `{tag_str}`" if tag_str else ""))
                if abstract:
                    st.markdown(abstract[:1500])
                else:
                    st.markdown("*(no abstract available)*")

                # Bookmark controls
                if saved_cat:
                    st.success(f"Saved to **{saved_cat}**")
                    if st.button("Remove bookmark", key=f"rm_{key_prefix}_{pk}_{_idx}"):
                        remove_paper(pk)
                        st.rerun()
                else:
                    bcol1, bcol2 = st.columns([3, 1])
                    with bcol1:
                        cat = st.selectbox("Category", categories, key=f"cat_{key_prefix}_{pk}_{_idx}", label_visibility="collapsed")
                    with bcol2:
                        if st.button("Save", key=f"sv_{key_prefix}_{pk}_{_idx}"):
                            save_paper(pk, row, cat)
                            st.rerun()
    else:
        show = d[["source", "journal", "date", "title", "score", "score_raw", "journal_mult", "tags", "url"]].copy()
        show.rename(columns={"score": "score_adj"}, inplace=True)
        st.dataframe(
            show, use_container_width=True,
            column_config={"url": st.column_config.LinkColumn("url")},
        )


def cap_per_journal(df: pd.DataFrame, cap: int) -> pd.DataFrame:
    if cap is None or cap <= 0 or df.empty:
        return df
    return df.groupby("journal", group_keys=False).head(int(cap))


def best_journal_match(df_src: pd.DataFrame, j_display: str) -> pd.DataFrame:
    if "query_journal" in df_src.columns:
        sub = df_src[df_src["query_journal"].str.lower() == j_display.lower()].copy()
        if not sub.empty:
            return sub
    sub = df_src[df_src["journal"].str.lower() == j_display.lower()].copy()
    if sub.empty:
        sub = df_src[df_src["journal"].str.lower().str.contains(j_display.lower())].copy()
    return sub


def to_csv_bytes(d: pd.DataFrame, filename: str):
    export_cols = ["source", "journal", "date", "title", "url", "score", "score_raw", "journal_mult"]
    return d[export_cols].to_csv(index=False), filename


def apply_search_filter(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Filter dataframe by search query across title, abstract, journal, and tags."""
    if not query or not query.strip():
        return df
    q = query.strip().lower()
    mask = (
        df["title"].str.lower().str.contains(q, na=False)
        | df["abstract"].str.lower().str.contains(q, na=False)
        | df["journal"].str.lower().str.contains(q, na=False)
        | df["tags"].apply(lambda tags: any(q in t.lower() for t in (tags or [])))
    )
    return df[mask].copy()


# ========================
# Streamlit UI
# ========================
st.set_page_config(page_title="Weekly Bio Dashboard", layout="wide")
st.title("Weekly Bio Dashboard v3")

# Controls
c1, c2, c3, c4 = st.columns([1.15, 1.15, 1.0, 1.0])
with c1:
    journal_days = st.slider("Journal lookback (days)", 7, 90, 15)
with c2:
    preprint_days = st.slider("Preprint lookback (days)", 3, 21, 7)
with c3:
    include_biorxiv = st.checkbox("Include bioRxiv", value=INCLUDE_BIORXIV_DEFAULT)
    include_medrxiv = st.checkbox("Include medRxiv", value=INCLUDE_MEDRXIV_DEFAULT)
with c4:
    max_rows_per_journal = st.selectbox("Max rows/journal", [200, 300, 500], index=1)

c5, c6, c7, c8 = st.columns([1, 1, 1, 1])
with c5:
    journal_core_thresh = st.slider("Core threshold (journals)", 4, 60, 12)
with c6:
    preprint_core_thresh = st.slider("Core threshold (preprints)", 4, 60, 14)
with c7:
    per_journal_core_view = st.checkbox("Show Journal Core grouped by journal", value=True)
with c8:
    show_abstracts = st.checkbox("Show abstracts (expandable)", value=True)

# Search bar + saved count
_scol1, _scol2 = st.columns([5, 1])
with _scol1:
    search_query = st.text_input(
        "Search papers (title, abstract, journal, tag)",
        placeholder="e.g. stem cell, CRISPR, deep learning, Nature Methods...",
    )
with _scol2:
    _saved_data = load_saved_papers()
    _n_saved = len(_saved_data.get("papers", {}))
    st.metric("Saved", _n_saved)


# ========================
# Data fetch + scoring
# ========================
@st.cache_data(show_spinner=True, ttl=3600)
def refresh(
    journal_days: int, preprint_days: int,
    include_biorxiv: bool, include_medrxiv: bool,
    max_rows_per_journal: int,
) -> tuple[pd.DataFrame, dict, str]:
    """
    Fetch and score all papers. Returns (df, fetch_status_dict, refresh_timestamp).
    """
    all_items: list[dict] = []
    fetch_status: dict = {}

    for j in JOURNALS:
        items, status = crossref_fetch(j, days=journal_days, rows=max_rows_per_journal)
        all_items.extend(items)
        fetch_status[j] = {"count": len(items), "status": status}

    if include_biorxiv:
        items, status = biorxiv_fetch(days=preprint_days)
        all_items.extend(items)
        fetch_status["bioRxiv"] = {"count": len(items), "status": status}

    if include_medrxiv:
        items, status = medrxiv_fetch(days=preprint_days)
        all_items.extend(items)
        fetch_status["medRxiv"] = {"count": len(items), "status": status}

    df = pd.DataFrame(all_items)

    if not df.empty:
        df["journal_norm"] = df["journal"].apply(norm_journal)
        keep = (df["source"] == "Preprint") | (df["journal_norm"].isin(ALLOWED_JOURNALS))
        df = df[keep].copy()
        df = df.drop(columns=["journal_norm"])

    if not df.empty:
        # Deduplication
        df = df.copy()
        df["title_norm"] = df["title"].astype(str).str.lower().str.strip()
        df["journal_norm2"] = df["journal"].astype(str).str.lower().str.strip()
        df["doi_norm"] = (
            df.get("doi", "")
              .astype(str)
              .str.lower()
              .str.strip()
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

    # Score all papers
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
    df["is_bio"]  = df["hits"].apply(lambda h: any((h.get(k, 0) or 0) > 0 for k in BIO_KEYS))
    df["is_ai"]   = df["hits"].apply(lambda h: (h.get("computational", 0) or 0) > 0)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return df, fetch_status, timestamp


df, fetch_status, refresh_ts = refresh(
    journal_days, preprint_days, include_biorxiv, include_medrxiv, max_rows_per_journal,
)
df = df.copy()

# Apply core thresholds (not cached — changes with slider)
df["core"] = False
df.loc[df["source"] == "Journal", "core"] = df["core_by_logic"] & (df["score"] >= float(journal_core_thresh))
df.loc[df["source"] == "Preprint", "core"] = df["core_by_logic"] & (df["score"] >= float(preprint_core_thresh))

# Apply search filter
df = apply_search_filter(df, search_query)

df_j = df[df["source"] == "Journal"].copy()
df_p = df[df["source"] == "Preprint"].copy()
df_j = df_j.sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])
df_p = df_p.sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])


# ========================
# Last refreshed + fetch status
# ========================
st.caption(f"Data last refreshed: **{refresh_ts}** | {len(df)} papers total after filtering")

with st.expander("Fetch status per source", expanded=False):
    status_rows = []
    for src, info in fetch_status.items():
        emoji = "OK" if info["status"] == "ok" else "WARN"
        status_rows.append({"Source": src, "Papers": info["count"], "Status": emoji, "Detail": info["status"]})
    if status_rows:
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True)


# ========================
# Must-read (split Tech vs Bio, plus Preprints)
# ========================
st.subheader("Must-read")
st.caption("Journals are split into Tech vs Bio; Preprints stay separate.")

# Journals — Tech
st.markdown(f"### Must-read — Journals (Tech Top {MUST_READ_N})")
tech_j = df_j[df_j["is_tech"]].copy()
tech_j = tech_j.sort_values(by=["score", "date_sort"], ascending=[False, False])
tech_j = cap_per_journal(tech_j, MAX_PER_JOURNAL_MUST_READ).head(MUST_READ_N)
render_df(tech_j, show_abstract=show_abstracts, key_prefix="mr_tech")
if not tech_j.empty:
    csv, fn = to_csv_bytes(tech_j, "weekly_must_read_journals_tech.csv")
    st.download_button("Download (Tech Journals CSV)", csv, fn, "text/csv")

st.divider()

# Journals — Bio
st.markdown(f"### Must-read — Journals (Bio Top {MUST_READ_N})")
bio_j = df_j[df_j["is_bio"]].copy()
bio_j = bio_j.sort_values(by=["score", "date_sort"], ascending=[False, False])
bio_j = cap_per_journal(bio_j, MAX_PER_JOURNAL_MUST_READ).head(MUST_READ_N)
render_df(bio_j, show_abstract=show_abstracts, key_prefix="mr_bio")
if not bio_j.empty:
    csv, fn = to_csv_bytes(bio_j, "weekly_must_read_journals_bio.csv")
    st.download_button("Download (Bio Journals CSV)", csv, fn, "text/csv")

st.divider()

# Preprints
st.markdown(f"### Must-read — Preprints (Top {MUST_READ_N})")
if include_biorxiv or include_medrxiv:
    must_p = df_p[df_p["core"]].sort_values(by=["score", "date_sort"], ascending=[False, False]).head(MUST_READ_N).copy()
    render_df(must_p, show_abstract=show_abstracts, key_prefix="mr_pre")
    if not must_p.empty:
        csv, fn = to_csv_bytes(must_p, "weekly_must_read_preprints.csv")
        st.download_button("Download (Preprints CSV)", csv, fn, "text/csv")
else:
    st.info("Preprint sources are disabled.")

st.divider()


# ========================
# Focus sections
# ========================
# To customize: change the section title, caption, and the keyword list
# used in the filter function. See config.py for FOCUS_AREA_1_KEYS, etc.

# --- Focus 1: Gene regulation & epigenetics (example) ---
st.subheader("Focus: Gene regulation & epigenetics")
st.caption("Customize this section in config.py by editing FOCUS_AREA_1_KEYS.")

def is_focus_area_1(title: str, abstract: str) -> bool:
    text = (title + " " + abstract).lower()
    return any(k in text for k in FOCUS_AREA_1_KEYS)

focus_1_all = df[df.apply(lambda r: is_focus_area_1(r.get("title", ""), r.get("abstract", "")), axis=1)].copy()
focus_1_j = focus_1_all[focus_1_all["source"] == "Journal"].copy().sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])
focus_1_p = focus_1_all[focus_1_all["source"] == "Preprint"].copy().sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])

f1col1, f1col2 = st.columns(2)
with f1col1:
    st.markdown("### Focus 1 — Journals")
    render_df(focus_1_j, show_abstract=show_abstracts, key_prefix="f1_j")
    if not focus_1_j.empty:
        csv, fn = to_csv_bytes(focus_1_j, "focus_1_journals.csv")
        st.download_button("Download (Focus 1 Journals CSV)", csv, fn, "text/csv")
with f1col2:
    st.markdown("### Focus 1 — Preprints")
    if include_biorxiv or include_medrxiv:
        render_df(focus_1_p, show_abstract=show_abstracts, key_prefix="f1_p")
        if not focus_1_p.empty:
            csv, fn = to_csv_bytes(focus_1_p, "focus_1_preprints.csv")
            st.download_button("Download (Focus 1 Preprints CSV)", csv, fn, "text/csv")
    else:
        st.info("Preprint sources are disabled.")

st.divider()

# --- Focus 2: Stem cells & regenerative medicine (example) ---
st.subheader("Focus: Stem cells & regenerative medicine")
st.caption("Customize this section in config.py by editing FOCUS_AREA_2_KEYS.")

def is_focus_area_2(title: str, abstract: str) -> bool:
    text = (title + " " + abstract).lower()
    return any(k in text for k in FOCUS_AREA_2_KEYS)

focus_2_all = df[df.apply(lambda r: is_focus_area_2(r.get("title", ""), r.get("abstract", "")), axis=1)].copy()
focus_2_j = focus_2_all[focus_2_all["source"] == "Journal"].copy().sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])
focus_2_p = focus_2_all[focus_2_all["source"] == "Preprint"].copy().sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])

f2col1, f2col2 = st.columns(2)
with f2col1:
    st.markdown("### Focus 2 — Journals")
    render_df(focus_2_j, show_abstract=show_abstracts, key_prefix="f2_j")
    if not focus_2_j.empty:
        csv, fn = to_csv_bytes(focus_2_j, "focus_2_journals.csv")
        st.download_button("Download (Focus 2 Journals CSV)", csv, fn, "text/csv")
with f2col2:
    st.markdown("### Focus 2 — Preprints")
    if include_biorxiv or include_medrxiv:
        render_df(focus_2_p, show_abstract=show_abstracts, key_prefix="f2_p")
        if not focus_2_p.empty:
            csv, fn = to_csv_bytes(focus_2_p, "focus_2_preprints.csv")
            st.download_button("Download (Focus 2 Preprints CSV)", csv, fn, "text/csv")
    else:
        st.info("Preprint sources are disabled.")

st.divider()

# --- Focus 3: AI/ML ---
st.subheader("Focus: AI/ML in biological data analysis")
st.caption("Deep learning, foundation models, image analysis, and computational methods applied to bio data.")

def is_ai_focus(title: str, abstract: str) -> bool:
    text = (title + " " + abstract).lower()
    return any(k in text for k in FOCUS_AI_KEYS)

focus_ai = df[df.apply(lambda r: is_ai_focus(r.get("title", ""), r.get("abstract", "")), axis=1)].copy()
focus_ai_j = focus_ai[focus_ai["source"] == "Journal"].copy().sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])
focus_ai_p = focus_ai[focus_ai["source"] == "Preprint"].copy().sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])

aicol1, aicol2 = st.columns(2)
with aicol1:
    st.markdown("### Focus AI/ML — Journals")
    render_df(focus_ai_j, show_abstract=show_abstracts, key_prefix="fai_j")
    if not focus_ai_j.empty:
        csv, fn = to_csv_bytes(focus_ai_j, "ai_ml_focus_journals.csv")
        st.download_button("Download (AI/ML Journals CSV)", csv, fn, "text/csv")
with aicol2:
    st.markdown("### Focus AI/ML — Preprints")
    if include_biorxiv or include_medrxiv:
        render_df(focus_ai_p, show_abstract=show_abstracts, key_prefix="fai_p")
        if not focus_ai_p.empty:
            csv, fn = to_csv_bytes(focus_ai_p, "ai_ml_focus_preprints.csv")
            st.download_button("Download (AI/ML Preprints CSV)", csv, fn, "text/csv")
    else:
        st.info("Preprint sources are disabled.")

st.divider()


# ========================
# Trends
# ========================
st.subheader("Trends")
tcol1, tcol2 = st.columns(2)
with tcol1:
    st.markdown(f"### Journal trends (last {journal_days} days)")
    trends_j = trend_summary(df_j, top_k=3)
    if not trends_j:
        st.info("No clear journal trend clusters in this window.")
    else:
        for i, (tname, one_liner, examples) in enumerate(trends_j, 1):
            with st.expander(f"Journal Trend {i} — {tname}", expanded=(i == 1)):
                st.write(one_liner)
                st.dataframe(examples, use_container_width=True, column_config={"url": st.column_config.LinkColumn("url")})

with tcol2:
    st.markdown(f"### Preprint trends (last {preprint_days} days)")
    if include_biorxiv or include_medrxiv:
        trends_p = trend_summary(df_p, top_k=3)
        if not trends_p:
            st.info("No clear preprint trend clusters in this window.")
        else:
            for i, (tname, one_liner, examples) in enumerate(trends_p, 1):
                with st.expander(f"Preprint Trend {i} — {tname}", expanded=(i == 1)):
                    st.write(one_liner)
                    st.dataframe(examples, use_container_width=True, column_config={"url": st.column_config.LinkColumn("url")})
    else:
        st.info("Preprint sources are disabled.")

st.divider()


# ========================
# Tabs
# ========================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs(
    [
        "Core — Journals",
        "Core — Preprints",
        "Big deals — Journals",
        "Big deals — Preprints",
        "By journal",
        "Focus 1 (tab)",
        "Focus 2 (tab)",
        "AI/ML (tab)",
        "All — Journals",
        f"Saved Papers ({_n_saved})",
    ]
)

with tab1:
    st.subheader(f"Core — Journals (last {journal_days} days)")
    core_j = df_j[df_j["core"]].copy()
    if core_j.empty:
        st.info("No journal core papers above threshold in this window.")
    else:
        if per_journal_core_view:
            for j in JOURNALS:
                sub = best_journal_match(core_j, j)
                if sub.empty:
                    continue
                sub = sub.sort_values(by=["score", "date_sort"], ascending=[False, False])
                st.markdown(f"### {j}  ({len(sub)})")
                render_df(sub, show_abstract=show_abstracts, key_prefix=f"t1cj_{j[:8]}")
        else:
            render_df(core_j.sort_values(by=["score", "date_sort"], ascending=[False, False]), show_abstract=show_abstracts, key_prefix="t1cj_all")

with tab2:
    st.subheader(f"Core — Preprints (last {preprint_days} days)")
    if include_biorxiv or include_medrxiv:
        render_df(df_p[df_p["core"]].copy(), show_abstract=show_abstracts, key_prefix="t2cp")
    else:
        st.info("Preprint sources are disabled.")

with tab3:
    st.subheader(f"Big deals — Journals (last {journal_days} days)")
    bdj = df_j[df_j["big_deal"] & (~df_j["core"])].copy()
    if bdj.empty:
        st.info("No journal big-deal papers in this window.")
    else:
        for j in JOURNALS:
            sub = best_journal_match(bdj, j)
            if sub.empty:
                continue
            sub = sub.sort_values(by=["score", "date_sort"], ascending=[False, False])
            st.markdown(f"### {j}  ({len(sub)})")
            render_df(sub, show_abstract=show_abstracts, key_prefix=f"t3bd_{j[:8]}")

with tab4:
    st.subheader(f"Big deals — Preprints (last {preprint_days} days)")
    if include_biorxiv or include_medrxiv:
        render_df(df_p[df_p["big_deal"] & (~df_p["core"])].copy(), show_abstract=show_abstracts, key_prefix="t4bdp")
    else:
        st.info("Preprint sources are disabled.")

with tab5:
    st.subheader("By journal (selected journals)")
    mode = st.radio("Show papers:", ["Core only", "Core + Big deal", "All"], horizontal=True, index=0)

    if mode == "Core only":
        view_j = df_j[df_j["core"]].copy()
        view_p = df_p[df_p["core"]].copy()
    elif mode == "Core + Big deal":
        view_j = df_j[df_j["core"] | df_j["big_deal"]].copy()
        view_p = df_p[df_p["core"] | df_p["big_deal"]].copy()
    else:
        view_j = df_j.copy()
        view_p = df_p.copy()

    for j in JOURNALS:
        sub = best_journal_match(view_j, j)
        if sub.empty:
            continue
        sub = sub.sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])
        st.markdown(f"### {j}  ({len(sub)})")
        render_df(sub, show_abstract=show_abstracts, key_prefix=f"t5bj_{j[:8]}")

    if (include_biorxiv or include_medrxiv) and not view_p.empty:
        st.markdown(f"### Preprints  ({len(view_p)})")
        view_p = view_p.sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False])
        render_df(view_p, show_abstract=show_abstracts, key_prefix="t5bj_pre")

with tab6:
    st.subheader("Focus 1 (tab)")
    fmode = st.radio("Focus 1 tab view:", ["All focus", "Journals only", "Preprints only"], horizontal=True, index=0)
    if fmode == "Journals only":
        render_df(focus_1_j, show_abstract=show_abstracts, key_prefix="t6f1_j")
    elif fmode == "Preprints only":
        render_df(focus_1_p, show_abstract=show_abstracts, key_prefix="t6f1_p")
    else:
        render_df(focus_1_all.sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False]), show_abstract=show_abstracts, key_prefix="t6f1_a")

with tab7:
    st.subheader("Focus 2 (tab)")
    f2mode = st.radio(
        "Focus 2 tab view:",
        ["All focus", "Journals only", "Preprints only"],
        horizontal=True, index=0, key="f2_focus_mode",
    )
    if f2mode == "Journals only":
        render_df(focus_2_j, show_abstract=show_abstracts, key_prefix="t7f2_j")
    elif f2mode == "Preprints only":
        render_df(focus_2_p, show_abstract=show_abstracts, key_prefix="t7f2_p")
    else:
        render_df(focus_2_all.sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False]), show_abstract=show_abstracts, key_prefix="t7f2_a")

with tab8:
    st.subheader("AI/ML in biological data analysis (tab)")
    aimode = st.radio(
        "AI/ML focus view:",
        ["All focus", "Journals only", "Preprints only"],
        horizontal=True, index=0, key="ai_focus_mode",
    )
    if aimode == "Journals only":
        render_df(focus_ai_j, show_abstract=show_abstracts, key_prefix="t8ai_j")
    elif aimode == "Preprints only":
        render_df(focus_ai_p, show_abstract=show_abstracts, key_prefix="t8ai_p")
    else:
        render_df(focus_ai.sort_values(by=["core", "score", "date_sort"], ascending=[False, False, False]), show_abstract=show_abstracts, key_prefix="t8ai_a")

with tab9:
    st.subheader(f"All — Journals (last {journal_days} days)")
    st.caption("All papers from your selected journals, regardless of relevance. Sorted by date.")
    allj = df_j.sort_values(by=["date_sort"], ascending=False).copy()

    for j in JOURNALS:
        sub = best_journal_match(allj, j)
        if sub.empty:
            continue
        st.markdown(f"### {j}  ({len(sub)})")
        show = sub[["date", "title", "url"]].copy()
        st.dataframe(show, use_container_width=True, column_config={"url": st.column_config.LinkColumn("url")})

        csv = sub[["journal", "query_journal", "date", "title", "url", "doi"]].to_csv(index=False)
        safe_name = re.sub(r"[^A-Za-z0-9_\-]+", "_", j).strip("_") or "journal"
        st.download_button(f"Download {j} (CSV)", csv, f"all_{safe_name}_{journal_days}d.csv", "text/csv")

with tab10:
    st.subheader("Saved Papers")
    saved_data = load_saved_papers()
    saved_papers = saved_data.get("papers", {})
    all_categories = get_categories()

    # Add custom category
    with st.expander("Manage categories", expanded=False):
        new_cat = st.text_input("Add a new category", placeholder="e.g. Thesis References", key="new_cat_input")
        if st.button("Add category", key="add_cat_btn") and new_cat.strip():
            add_category(new_cat.strip())
            st.rerun()
        st.caption(f"Current categories: {', '.join(all_categories)}")

    if not saved_papers:
        st.info("No papers saved yet. Browse papers above, expand one, and click **Save** to bookmark it.")
    else:
        # Filter by category
        filter_options = ["All"] + all_categories
        cat_filter = st.radio("Filter by category:", filter_options, horizontal=True, index=0, key="saved_cat_filter")

        if cat_filter == "All":
            display_papers = saved_papers
        else:
            display_papers = {k: v for k, v in saved_papers.items() if v.get("category") == cat_filter}

        st.caption(f"Showing {len(display_papers)} of {len(saved_papers)} saved papers")

        for pk, info in display_papers.items():
            title = info.get("title", "Untitled")
            url = info.get("url", "")
            journal = info.get("journal", "")
            date_str = info.get("date", "")
            category = info.get("category", "")
            saved_at = info.get("saved_at", "")[:10]

            link = f"[{title}]({url})" if url else title

            with st.expander(f"[{category}] {title[:120]}", expanded=False):
                st.markdown(f"### {link}")
                st.markdown(f"**{journal}** &nbsp;|&nbsp; {date_str} &nbsp;|&nbsp; Category: **{category}** &nbsp;|&nbsp; Saved: {saved_at}")
                if st.button("Remove", key=f"rm_saved_{pk}"):
                    remove_paper(pk)
                    st.rerun()

        # Export
        if display_papers:
            export_rows = []
            for pk, info in display_papers.items():
                export_rows.append({
                    "title": info.get("title", ""),
                    "journal": info.get("journal", ""),
                    "date": info.get("date", ""),
                    "url": info.get("url", ""),
                    "category": info.get("category", ""),
                    "saved_at": info.get("saved_at", ""),
                })
            export_csv = pd.DataFrame(export_rows).to_csv(index=False)
            st.download_button("Export saved papers (CSV)", export_csv, "saved_papers.csv", "text/csv")
