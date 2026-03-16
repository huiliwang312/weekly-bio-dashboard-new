# Weekly Bio Dashboard

A Streamlit dashboard that automatically fetches, scores, and curates recent papers from top biology journals and preprints (bioRxiv / medRxiv).

## Features

- Fetches from **20+ journals** via Crossref API + bioRxiv/medRxiv API (no API key needed)
- **Keyword-based scoring** with Tech vs Bio split
- **Must-read rankings**, Focus sections, Trend detection
- Full-text search, paper bookmarks, CSV export
- Optional **weekly email digest** via SMTP
- Scheduled runs via macOS launchd or cron

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/huiliwang312/weekly-bio-dashboard-new.git
cd weekly-bio-dashboard-new

# 2. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Set up auto-start (macOS)
#    Edit the plist file to match your project path, then:
cp com.huiliw.weekly-bio-dashboard.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.huiliw.weekly-bio-dashboard.plist
```

Opens at http://localhost:8501 — and auto-starts every time you log in. No need to run anything manually after setup.

## Customize for YOUR Research

**You only need to edit one file: `config.py`**

| What to edit | What it does |
|---|---|
| `JOURNALS` / `JOURNAL_ISSN` | Add or remove journals you want to track |
| `CORE_KEYWORDS` | Define keyword categories — each becomes a tag and feeds into scoring |
| `TECH_KEYS` / `BIO_KEYS` | Assign categories into Tech vs Bio buckets for the Must-read split |
| `FOCUS_AREA_1_KEYS` / `FOCUS_AREA_2_KEYS` | Keywords for your dedicated Focus sections (replace with your niche) |
| `FOCUS_AI_KEYS` | Keywords for the AI/ML focus section |
| `TREND_LEXICON` | Groups of keywords for trend detection |

### Example: switching to your own field

Say you study **gut microbiome**. In `config.py`, you would:

1. Add microbiome-related journals to `JOURNALS`
2. Replace a `CORE_KEYWORDS` category:
   ```python
   "microbiome": [
       "microbiome", "gut microbiota", "16s rrna",
       "metagenomics", "gnotobiotic", "dysbiosis",
   ],
   ```
3. Add `"microbiome"` to `BIO_KEYS`
4. Replace `FOCUS_AREA_1_KEYS` with your niche keywords

That's it — the scoring, dashboard, and email digest all update automatically.

## Email Digest (Optional)

Get a weekly summary email with your top papers.

1. Create a `.env.digest` file:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=you@gmail.com
   SMTP_PASSWORD=your-app-password
   EMAIL_TO=you@example.com
   ```

2. Test it:
   ```bash
   python send_digest.py --dry-run
   ```

3. Schedule weekly with macOS launchd:
   - Edit the `.plist` file — replace `/path/to/...` with your actual paths
   - Copy to `~/Library/LaunchAgents/`
   - Load: `launchctl load ~/Library/LaunchAgents/com.yourname.weekly-bio-digest.plist`

## Auto-Start on Login (macOS)

Instead of running `streamlit run app.py` manually each time, you can have the dashboard start automatically when you log in:

1. Edit `com.huiliw.weekly-bio-dashboard.plist` — replace paths with your actual project location
2. Copy to LaunchAgents:
   ```bash
   cp com.huiliw.weekly-bio-dashboard.plist ~/Library/LaunchAgents/
   ```
3. Load it:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.huiliw.weekly-bio-dashboard.plist
   ```

Now just open **http://localhost:8501** anytime — the server is always running in the background. macOS will auto-restart it if it crashes.

To stop: `launchctl unload ~/Library/LaunchAgents/com.huiliw.weekly-bio-dashboard.plist`

## Project Structure

```
config.py          ← All your keywords & settings (edit this!)
app.py             ← Streamlit dashboard UI
scoring.py         ← Scoring, tagging, trend logic
fetchers.py        ← Crossref / bioRxiv / medRxiv API fetchers
send_digest.py     ← Email digest builder & sender
run.sh             ← Launch the dashboard
run_digest.sh      ← Wrapper for scheduled digest runs
com.huiliw.weekly-bio-dashboard.plist  ← LaunchAgent for auto-start on login
requirements.txt   ← Python dependencies
```

## No API Keys Needed

This project uses free, open APIs:
- **Crossref API** — free, no registration required
- **bioRxiv / medRxiv API** — free, no registration required
