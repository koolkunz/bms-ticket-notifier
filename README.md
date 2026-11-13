# BMS Ticket Notifier & Release Monitor Bot

An intelligent, multi-format bot that monitors [BookMyShow](https://in.bookmyshow.com) for movie ticket releases, newly opened booking dates, additional showtimes, and seat availability changes.

Runs locally as a continuous background bot or in CI via GitHub Actions, alerting you via email (Resend) and terminal audio alerts.

---

## Key Features

- 🚨 **Ticket Release Alerts**: Detects when bookings first open for an unreleased movie and immediately alerts you.
- 🎯 **Multi-Format & Language Filter**: Automatically discovers all formats linked to a movie on BookMyShow (`IMAX 3D`, `3D`, `4DX`, `2D`, `Hindi`, `English`, etc.) and monitors the ones you specify (e.g. `hindi, imax`).
- 📅 **Date Range Monitoring & Human Dates**:
  - Readable dates in all alerts: e.g. **`Sunday, 15th November 2026`**
  - Date ranges: `20261110-20261115` or `2026-11-10 to 2026-11-15`
  - Relative dates: `today`, `today+3` (today through next 3 days)
  - Comma-separated: `20261110,20261112`
  - Auto-detection: Leave blank to automatically check all dates listed on BMS.
- 🏛️ **Theatre Filter**: Filter by cinema chain or venue name (e.g. `PVR, INOX, Miraj, Vegas`).
- ⏰ **Time Period Filter**: Filter by time of day (`morning`, `afternoon`, `evening`, `night`).
- 📍 **All-India Region Resolution**: Pre-configured for major Indian cities with automatic dynamic lookup for 2,000+ BookMyShow cities.
- 👥 **Multiple Email Recipients**: Send alerts to multiple emails separated by commas.
- 🤖 **Local Bot Loop**: Run continuously in the background on your machine (`--loop` with custom interval).
- 📧 **Rich HTML Email Alerts**: Grouped by theatre, with seat categories, ticket prices, availability indicators, and direct 1-click booking link.

---

## Quick Start (Local Setup)

### 1. Install Dependencies

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

### 2. Configure Settings

Create a `.env` file from the provided template:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# BookMyShow movie page URL or event code
BMS_URL=https://in.bookmyshow.com/movies/mumbai/ramayana/ET00451914

# Dates to monitor (e.g. 20261110-20261115, today+3, or leave blank for all)
BMS_DATES=20261110-20261115

# Optional theatre filter (comma-separated substrings)
BMS_THEATRE=PVR,INOX

# Optional show type / format filter (e.g. 'hindi, imax', 'imax', '3d', '4dx')
BMS_SHOW_TYPE=hindi, imax

# Optional time period (morning, afternoon, evening, night)
BMS_TIME=evening,night

# Optional city / region override (e.g. delhi-ncr, mumbai, bengaluru)
BMS_REGION=

# Bot loop interval in seconds (e.g. 60 = check every 1 minute)
CHECK_INTERVAL=60

# Send email with current showtimes on startup/first check (true/false)
NOTIFY_ON_START=true

# Always send email on every check, even if nothing changed (true/false)
FORCE_EMAIL=false

# Resend Email Configuration (Optional - get free API key at resend.com)
RESEND_API_KEY=re_123456789
# Comma-separated list of recipient emails
RESEND_TO_EMAIL=you@example.com, friend@example.com
RESEND_FROM_EMAIL=onboarding@resend.dev
```

> **Note on Resend Sender (`RESEND_FROM_EMAIL`)**:
> With Resend's free default sandbox sender (`onboarding@resend.dev`), emails can only be delivered to your own registered account email. To send alerts to other recipients, verify your custom domain at [resend.com/domains](https://resend.com/domains) and set `RESEND_FROM_EMAIL=alerts@yourdomain.com`.

### 3. Run the Bot

**Run continuously in monitoring loop (checks every 60s):**
```bash
python main.py --loop --interval 60
```

**Run a single check:**
```bash
python main.py --once
```

**Run a single check and force an email immediately:**
```bash
python main.py --once --force-email
```

**Test your email setup:**
```bash
python main.py --test-email
```

---

## Command-Line Usage

You can also pass all options directly via CLI flags, overriding any `.env` settings:

```bash
python main.py \
  --url "https://in.bookmyshow.com/movies/mumbai/ramayana/ET00451914" \
  --show-type "hindi, imax" \
  --theatre "PVR, INOX" \
  --dates "today+4" \
  --loop \
  --interval 60
```

### Available CLI Flags

| Flag | Description | Example |
|------|-------------|---------|
| `--url` | BookMyShow movie URL or Event Code | `https://in.bookmyshow.com/.../ET00451914` |
| `--dates` | Date range or comma list | `20261110-20261115` or `today+3` |
| `--show-type` | Filter by show type/format/language | `hindi, imax` or `imax` or `4dx` |
| `--theatre` | Filter by cinema name | `PVR, INOX, Miraj` |
| `--time` | Filter by time period | `evening,night` |
| `--region` | Override city / region | `mumbai`, `delhi-ncr`, `bengaluru` |
| `--loop` | Run continuously in a monitoring loop | `--loop` |
| `--interval` | Polling interval in seconds | `--interval 60` |
| `--once` | Run a single check and exit | `--once` |
| `--force-email` | Send email with current shows even if no changes | `--force-email` |
| `--notify-initial` | Send email notification on first baseline run | `--notify-initial` |
| `--test-email` | Send a test email via Resend and exit | `--test-email` |
| `--reset-state` | Clear cached watch state | `--reset-state` |

---

## GitHub Actions Setup (Headless Cloud Runner)

To run the checker automatically on GitHub Actions every 30 minutes:

### 1. Push your code to GitHub
```bash
git add .
git commit -m "feat: setup ticket notifier"
git push origin main
```

### 2. Enable Workflow Write Permissions
GitHub Actions needs permission to commit updated state back to the repository:
1. In your GitHub repo, go to **Settings → Actions → General**.
2. Scroll to **Workflow permissions**.
3. Select **"Read and write permissions"**.
4. Click **Save**.

### 3. Add GitHub Secrets
Go to **Settings → Secrets and variables → Actions → Secrets tab**:

| Secret Name | Value |
|-------------|-------|
| `RESEND_API_KEY` | Your Resend API key (`re_...`) |
| `RESEND_TO_EMAIL` | Recipient email(s) (comma-separated if multiple) |
| `RESEND_FROM_EMAIL` | `onboarding@resend.dev` (or verified custom domain) |

### 4. Add GitHub Variables
Go to **Settings → Secrets and variables → Actions → Variables tab**:

| Variable Name | Description | Example |
|---------------|-------------|---------|
| `BMS_URL` | BookMyShow ticket page URL | `https://in.bookmyshow.com/.../ET00523158` |
| `BMS_DATES` | (Optional) Date range or relative | `today+4` or `20261111-20261115` |
| `BMS_SHOW_TYPE` | (Optional) Show type / format | `hindi, imax` |
| `BMS_THEATRE` | (Optional) Cinema name filter | `PVR, INOX, Vegas` |
| `BMS_TIME` | (Optional) Time slot | `evening,night` |
| `BMS_REGION` | (Optional) City / region | `delhi-ncr`, `mumbai` |

> [!TIP]
> In GitHub Actions, if you want to leave an optional variable blank (e.g. to monitor **all dates**, **all formats**, or **all theatres**), you can set its value to `NULL` (or `none`), or simply delete the variable. The bot automatically treats `NULL` as empty.

### 5. Trigger the Workflow
Go to **Actions → BMS Ticket Checker → Run workflow**, or wait for it to run automatically on schedule.

### 6. Adjust Schedule Frequency (Optional)
Edit [`.github/workflows/bms-checker.yml`](.github/workflows/bms-checker.yml):
- Every 30 minutes (jittered): `- cron: '13,43 * * * *'` *(default — shifts by a few minutes to avoid global GitHub runner queue spikes)*
- Every 15 minutes: `- cron: '7,22,37,52 * * * *'`
- Every hour: `- cron: '17 * * * *'`

---

## How It Works

1. **Movie & Format Discovery**: Queries BookMyShow's API with desktop browser headers. It discovers all languages and screen formats for the title (2D, 3D, IMAX 3D, 4DX, ScreenX, ICE, etc.) and isolates the exact event codes matching your criteria.
2. **Date Range Checking**: Iterates across your requested dates, resolving relative dates (`today`, `today+3`) into human-readable dates (`Sunday, 15th November 2026`).
3. **Filtering**: Matches showtimes against theatre names, time slots, and formats.
4. **State Tracking**: Compares the results against `bms_state.json`:
   - If bookings were not open and now are → **🚨 BOOKINGS OPENED ALERT!**
   - If a new date is announced → **📅 NEW DATE OPENED!**
   - If new showtimes are added → **🆕 NEW SHOWS!**
   - If a sold-out show has seats again → **🟢 TICKETS BACK!**
5. **Notification**: Dispatches an HTML email via Resend and chimes in the local console.
