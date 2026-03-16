Weekly Bio Dashboard
====================
A Streamlit dashboard that automatically fetches, scores, and curates
recent papers from top biology journals and preprints (bioRxiv / medRxiv).

Features:
  - Fetches from 20+ journals via Crossref API + bioRxiv/medRxiv API
  - Keyword-based scoring with Tech vs Bio split
  - Must-read rankings, Focus sections, Trend detection
  - Full-text search, paper bookmarks, CSV export
  - Optional weekly email digest (via SMTP)
  - Scheduled runs via macOS launchd (or cron)


1) Install
----------
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt


2) Run
------
    streamlit run app.py

    Opens http://localhost:8501


3) Customize for YOUR research
-------------------------------
    Edit config.py — it's the ONLY file you need to change.

    a) JOURNALS / JOURNAL_ISSN
       Add or remove journals you want to track.

    b) CORE_KEYWORDS
       Define keyword categories (each becomes a tag + feeds scoring).
       Example categories: "genomics", "imaging", "neuroscience", etc.

    c) TECH_KEYS / BIO_KEYS
       Assign your CORE_KEYWORDS categories into Tech vs Bio buckets.
       This controls the Must-read Tech / Must-read Bio split.

    d) FOCUS_AREA_1_KEYS / FOCUS_AREA_2_KEYS / FOCUS_AI_KEYS
       These power the dedicated Focus sections. Replace the example
       keywords with terms from your own niche.

    e) TREND_LEXICON
       Groups of keywords for trend detection. Customize to match
       the research themes you want to track.


4) Email digest (optional)
--------------------------
    a) Create .env.digest with:
         SMTP_HOST=smtp.gmail.com
         SMTP_PORT=587
         SMTP_USER=you@gmail.com
         SMTP_PASSWORD=your-app-password
         EMAIL_TO=you@example.com

    b) Test: python send_digest.py --dry-run

    c) Schedule with launchd (macOS):
       - Edit the .plist file: replace /path/to/... with your actual paths
       - Copy to ~/Library/LaunchAgents/
       - launchctl load ~/Library/LaunchAgents/com.yourname.weekly-bio-digest.plist
