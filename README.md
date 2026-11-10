# BMS Ticket Notifier & Release Monitor Bot

An intelligent, multi-format bot that monitors [BookMyShow](https://in.bookmyshow.com) for movie ticket releases, newly opened booking dates, additional showtimes, and seat availability changes.

Runs locally as a continuous background bot or in CI via GitHub Actions, alerting you via email (Resend) and terminal audio alerts.

---

## Key Features

- 🚨 **Ticket Release Alerts**: Detects when bookings first open for an unreleased movie and immediately alerts you.
- 🎯 **Multi-Format & Language Filter**: Automatically discovers all formats linked to a movie on BookMyShow (`IMAX 3D`, `3D`, `4DX`, `2D`, `Hindi`, `English`, etc.) and monitors the ones you specify (e.g. `hindi, imax`).
- 📅 **Date Range Monitoring**: Supports flexible dates:
  - Date ranges: `20261110-20261115` or `2026-11-10 to 2026-11-15`
  - Relative dates: `today`, `today+3` (today through next 3 days)
  - Comma-separated: `20261110,20261112`
  - Auto-detection: Leave blank to automatically check all dates listed on BMS.
- 🏛️ **Theatre Filter**: Filter by cinema chain or venue name (e.g. `PVR, INOX, Miraj`).
- ⏰ **Time Period Filter**: Filter by time of day (`morning`, `afternoon`, `evening`, `night`).
- 📍 **All-India Region Resolution**: Pre-configured for all major Indian cities with automatic dynamic resolution for 2,000+ BookMyShow cities.
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

# Bot loop interval in seconds (e.g. 60 = check every 1 minute)
CHECK_INTERVAL=60

# Optional: Resend Email setup (get a free API key at resend.com)
RESEND_API_KEY=re_123456789
# Comma-separated list of recipient emails
RESEND_TO_EMAIL=you@example.com, friend@example.com
RESEND_FROM_EMAIL=onboarding@resend.dev
```

### 3. Run the Bot

**Run continuously in monitoring loop (checks every 60s):**
```bash
python main.py --loop --interval 60
```

**Run a single check:**
```bash
python main.py --once
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
| `--region` | Override city / region | `mumbai`, `bengaluru`, `delhi` |
| `--loop` | Run continuously in a monitoring loop | `--loop` |
| `--interval` | Polling interval in seconds | `--interval 60` |
| `--once` | Run a single check and exit | `--once` |
| `--test-email` | Send a test email via Resend | `--test-email` |
| `--reset-state` | Clear cached watch state | `--reset-state` |

---

## GitHub Actions Setup (Headless Cloud Runner)

To run the checker automatically on GitHub Actions every 30 minutes:

1. Fork this repository.
2. In your repo, go to **Settings → Secrets and variables → Actions**.
3. Under **Secrets**, add:
   - `RESEND_API_KEY`: Your Resend API key
   - `RESEND_TO_EMAIL`: Your destination email
   - `RESEND_FROM_EMAIL`: Sender email (`onboarding@resend.dev` or your verified domain)
4. Under **Variables**, add:
   - `BMS_URL`: BookMyShow movie URL
   - `BMS_DATES`: (Optional) Date range or list
   - `BMS_SHOW_TYPE`: (Optional) e.g. `hindi, imax`
   - `BMS_THEATRE`: (Optional) e.g. `PVR, INOX`
   - `BMS_TIME`: (Optional) e.g. `evening,night`
5. Go to **Actions → BMS Ticket Checker → Run workflow**.

---

## How It Works

1. **Movie & Format Discovery**: Queries BookMyShow's API with desktop browser headers. It discovers all languages and screen formats for the title (2D, 3D, IMAX 3D, 4DX, ScreenX, ICE, etc.) and isolates the exact event codes matching your criteria.
2. **Date Range Checking**: Iterates across your requested dates or auto-detects all available booking dates on the schedule.
3. **Filtering**: Matches showtimes against theatre names, time slots, and formats.
4. **State Tracking**: Compares the results against `bms_state.json`:
   - If bookings were not open and now are → **🚨 BOOKINGS OPENED ALERT!**
   - If a new date is announced → **📅 NEW DATE OPENED!**
   - If new showtimes are added → **🆕 NEW SHOWS!**
   - If a sold-out show has seats again → **🟢 TICKETS BACK!**
5. **Notification**: Dispatches an HTML email via Resend and chimes in the local console.
