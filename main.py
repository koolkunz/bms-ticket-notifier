"""
BMS Ticket Checker & Notifier Bot
=================================
Monitors BookMyShow for movie ticket releases, new dates, showtimes, and seat availability.
Runs locally (interactive loop / background bot) or headless in CI (GitHub Actions).

Features:
- Monitors movie ticket releases (alerts when bookings first open)
- Supports date ranges (e.g. 20261110-20261115, today+3, or specific dates)
- Discovers and filters multi-format shows (IMAX, 3D, 2D, 4DX, Hindi, English, etc.)
- Filters by theatre / cinema name (e.g. PVR, INOX, Miraj)
- Filters by time period (morning, afternoon, evening, night)
- Sends rich HTML email alerts via Resend
- Runs as a continuous local monitoring bot or single check
- Reads from .env file or command-line arguments (no export command needed on Windows)
"""

import os
import sys
import re
import json
import time
import argparse
from html import escape
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from urllib.parse import urlparse
import requests

# ──────────────────────────────────────────────────────────────────────
# .ENV FILE LOADER (Built-in, zero dependencies)
# ──────────────────────────────────────────────────────────────────────
def load_dotenv(filepath=".env"):
    """Load key-value pairs from .env into os.environ if not already set."""
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception as e:
        print(f"  ⚠️ Warning reading .env: {e}")

load_dotenv()

# ──────────────────────────────────────────────────────────────────────
# CONSTANTS & MAPS
# ──────────────────────────────────────────────────────────────────────
STATE_FILE = "bms_state.json"
REGIONS_CACHE_FILE = "bms_regions_cache.json"

AVAIL_STATUS_MAP = {
    "0": ("SOLD OUT",    "🔴"),
    "1": ("ALMOST FULL", "🟡"),
    "2": ("FILLING FAST","🟠"),
    "3": ("AVAILABLE",   "🟢"),
}

DATE_STYLE_MAP = {
    "date-selected": "BOOKABLE",
    "date-default":  "AVAILABLE",
    "date-disabled": "NOT_OPEN",
}

TIME_PERIODS = {
    "morning":   (600, 1200),
    "afternoon": (1200, 1600),
    "evening":   (1600, 1900),
    "night":     (1900, 2400),
}

# Major cities default fallback map (code, slug, lat, lon, geohash)
STATIC_REGION_MAP = {
    # Delhi NCR & surrounding cities
    "national-capital-region-ncr": ("NCR",    "national-capital-region-ncr", "28.6139", "77.2090", "ttn"),
    "delhi-ncr":                   ("NCR",    "national-capital-region-ncr", "28.6139", "77.2090", "ttn"),
    "delhi":                       ("NCR",    "national-capital-region-ncr", "28.6139", "77.2090", "ttn"),
    "ncr":                         ("NCR",    "national-capital-region-ncr", "28.6139", "77.2090", "ttn"),
    "nation":                      ("NCR",    "national-capital-region-ncr", "28.6139", "77.2090", "ttn"),
    "new-delhi":                   ("NCR",    "national-capital-region-ncr", "28.6139", "77.2090", "ttn"),
    "noida":                       ("NCR",    "national-capital-region-ncr", "28.6139", "77.2090", "ttn"),
    "greater-noida":               ("NCR",    "national-capital-region-ncr", "28.6139", "77.2090", "ttn"),
    "gurugram":                    ("NCR",    "delhi-ncr",                  "28.6139", "77.2090", "ttn"),
    "gurgaon":                     ("NCR",    "delhi-ncr",                  "28.6139", "77.2090", "ttn"),
    "ghaziabad":                   ("NCR",    "delhi-ncr",                  "28.6139", "77.2090", "ttn"),
    "faridabad":                   ("NCR",    "delhi-ncr",                  "28.6139", "77.2090", "ttn"),

    # Mumbai & MMR
    "mumbai":                      ("MUMBAI", "mumbai",                     "19.0760", "72.8777", "te7"),
    "navi-mumbai":                 ("MUMBAI", "mumbai",                     "19.0760", "72.8777", "te7"),
    "thane":                       ("MUMBAI", "mumbai",                     "19.0760", "72.8777", "te7"),

    # Bengaluru
    "bengaluru":                   ("BANG",   "bengaluru",                  "12.9716", "77.5946", "tdr"),
    "bangalore":                   ("BANG",   "bengaluru",                  "12.9716", "77.5946", "tdr"),
    "bang":                        ("BANG",   "bengaluru",                  "12.9716", "77.5946", "tdr"),
    "blr":                         ("BANG",   "bengaluru",                  "12.9716", "77.5946", "tdr"),

    # Hyderabad
    "hyderabad":                   ("HYD",    "hyderabad",                  "17.3850", "78.4867", "tep"),
    "hyd":                         ("HYD",    "hyderabad",                  "17.3850", "78.4867", "tep"),

    # Chennai
    "chennai":                     ("CHEN",   "chennai",                    "13.0560", "80.2060", "tf3"),
    "chen":                        ("CHEN",   "chennai",                    "13.0560", "80.2060", "tf3"),
    "madras":                      ("CHEN",   "chennai",                    "13.0560", "80.2060", "tf3"),

    # Kolkata
    "kolkata":                     ("KOLK",   "kolkata",                    "22.5726", "88.3639", "tun"),
    "kolk":                        ("KOLK",   "kolkata",                    "22.5726", "88.3639", "tun"),
    "calcutta":                    ("KOLK",   "kolkata",                    "22.5726", "88.3639", "tun"),

    # Pune
    "pune":                        ("PUNE",   "pune",                       "18.5204", "73.8567", "te2"),

    # Ahmedabad
    "ahmedabad":                   ("AHD",    "ahmedabad",                  "23.0396", "72.5660", "ts5"),
    "ahd":                         ("AHD",    "ahmedabad",                  "23.0396", "72.5660", "ts5"),

    # Chandigarh
    "chandigarh":                  ("CHD",    "chandigarh",                 "30.7333", "76.7794", "ttq"),
    "chd":                         ("CHD",    "chandigarh",                 "30.7333", "76.7794", "ttq"),

    # Other major cities
    "kochi":                       ("KOCH",   "kochi",                      "9.9312",  "76.2673", "t9z"),
    "cochin":                      ("KOCH",   "kochi",                      "9.9312",  "76.2673", "t9z"),
    "jaipur":                      ("JAIP",   "jaipur",                     "26.9124", "75.7873", "tsv"),
    "lucknow":                     ("LUCK",   "lucknow",                    "26.8467", "80.9462", "tu8"),
    "surat":                       ("SURT",   "surat",                      "21.1950", "72.8190", "te5"),
    "coimbatore":                  ("COIM",   "coimbatore",                 "11.0168", "76.9558", "t9y"),
    "indore":                      ("IND",    "indore",                     "22.7196", "75.8577", "tsg"),
    "nagpur":                      ("NAGP",   "nagpur",                     "21.1458", "79.0882", "tgc"),
    "goa":                         ("GOA",    "goa",                        "15.2993", "74.1240", "td8"),
    "vadodara":                    ("VAD",    "vadodara",                   "22.3072", "73.1812", "te5"),
    "vizag":                       ("VIZ",    "visakhapatnam",              "17.6868", "83.2185", "tg7"),
    "visakhapatnam":               ("VIZ",    "visakhapatnam",              "17.6868", "83.2185", "tg7"),
}

# ──────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ──────────────────────────────────────────────────────────────────────
@dataclass
class CatInfo:
    name: str
    price: str
    status: str

@dataclass
class ShowInfo:
    venue_code: str
    venue_name: str
    session_id: str
    date_code: str
    time: str
    time_code: str
    screen_attr: str
    language: str = ""
    format_title: str = ""
    categories: list[CatInfo] = field(default_factory=list)

@dataclass
class DateInfo:
    date_code: str
    status: str

# ──────────────────────────────────────────────────────────────────────
# REGION RESOLVER
# ──────────────────────────────────────────────────────────────────────
def resolve_region(slug_or_code, session=None):
    """Resolve city slug/code to BMS region tuple (code, slug, lat, lon, geohash)."""
    raw = (slug_or_code or "").strip().lower()
    clean = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")

    # 1. Exact match in static region map
    if clean in STATIC_REGION_MAP:
        return STATIC_REGION_MAP[clean]
    if raw in STATIC_REGION_MAP:
        return STATIC_REGION_MAP[raw]

    # 2. Heuristic keyword matches for common regions (resilient in CI without cache/network)
    if any(k in clean for k in ("delhi", "ncr", "nation", "noida", "gurgaon", "gurugram", "ghaziabad", "faridabad")):
        return STATIC_REGION_MAP["national-capital-region-ncr"]
    if any(k in clean for k in ("mumbai", "bombay", "thane", "navi")):
        return STATIC_REGION_MAP["mumbai"]
    if any(k in clean for k in ("bengaluru", "bangalore", "bang", "blr")):
        return STATIC_REGION_MAP["bengaluru"]
    if any(k in clean for k in ("hyderabad", "hyd")):
        return STATIC_REGION_MAP["hyderabad"]
    if any(k in clean for k in ("chennai", "chen", "madras")):
        return STATIC_REGION_MAP["chennai"]
    if any(k in clean for k in ("kolkata", "kolk", "calcutta")):
        return STATIC_REGION_MAP["kolkata"]
    if "pune" in clean:
        return STATIC_REGION_MAP["pune"]
    if any(k in clean for k in ("ahmedabad", "ahd")):
        return STATIC_REGION_MAP["ahmedabad"]
    if any(k in clean for k in ("chandigarh", "chd")):
        return STATIC_REGION_MAP["chandigarh"]
    if "jaipur" in clean:
        return STATIC_REGION_MAP["jaipur"]
    if "lucknow" in clean:
        return STATIC_REGION_MAP["lucknow"]
    if any(k in clean for k in ("kochi", "cochin")):
        return STATIC_REGION_MAP["kochi"]
    if "goa" in clean:
        return STATIC_REGION_MAP["goa"]

    # 3. Check local cache file
    cached_regions = {}
    if os.path.exists(REGIONS_CACHE_FILE):
        try:
            with open(REGIONS_CACHE_FILE, "r") as f:
                cached_regions = json.load(f)
        except Exception:
            pass

    if clean in cached_regions:
        r = cached_regions[clean]
        return (r["code"], r["slug"], r["lat"], r["lon"], r.get("geohash", ""))
    if raw in cached_regions:
        r = cached_regions[raw]
        return (r["code"], r["slug"], r["lat"], r["lon"], r.get("geohash", ""))

    # 4. Query BookMyShow GETREGIONS endpoint (has 2,000+ Indian cities)
    s = session or requests.Session()
    try:
        resp = s.get(
            "https://in.bookmyshow.com/serv/getData?cmd=GETREGIONS",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
                )
            },
            timeout=8
        )
        if resp.status_code == 200 and "var regionlst=" in resp.text:
            idx = resp.text.find("var regionlst=")
            raw_js = resp.text[idx + len("var regionlst="):]
            data, _ = json.JSONDecoder().raw_decode(raw_js)

            for code, items in data.items():
                for item in items:
                    c = item.get("code", "")
                    sl = item.get("slug", "")
                    nm = item.get("name", "").lower()
                    lat = str(item.get("lat", "28.6139"))
                    lon = str(item.get("long", "77.2090"))
                    info = {"code": c, "slug": sl, "lat": lat, "lon": lon, "geohash": ""}
                    cached_regions[c.lower()] = info
                    cached_regions[sl.lower()] = info
                    cached_regions[nm] = info

            try:
                with open(REGIONS_CACHE_FILE, "w") as f:
                    json.dump(cached_regions, f)
            except Exception:
                pass

            if clean in cached_regions:
                r = cached_regions[clean]
                return (r["code"], r["slug"], r["lat"], r["lon"], r.get("geohash", ""))
    except Exception as e:
        print(f"  ⚠️ Warning fetching regions list: {e}")

    # 5. Safe fallback default (never return 0, 0 as coordinates because BMS API rejects it with 403)
    code = clean.upper()[:6] if clean else "NCR"
    slug = clean if clean else "national-capital-region-ncr"
    return (code, slug, "28.6139", "77.2090", "ttn")

# ──────────────────────────────────────────────────────────────────────
# URL & DATE PARSERS
# ──────────────────────────────────────────────────────────────────────
def parse_bms_url(url):
    """
    Extract event_code, date_code, and region_slug from any BMS URL or code.
    Supports /movies/... /buytickets/... direct event code, etc.
    """
    url = (url or "").strip()
    result = {"event_code": None, "date_code": None, "region_slug": None, "movie_name": None}

    if not url:
        return result

    if re.match(r"^ET\d{8,}$", url, re.I):
        result["event_code"] = url.upper()
        return result

    parsed = urlparse(url)
    path = parsed.path.strip("/")
    parts = [p for p in path.split("/") if p]

    for p in parts:
        m = re.search(r"(ET\d{8,})", p, re.I)
        if m:
            result["event_code"] = m.group(1).upper()
        if re.match(r"^\d{8}$", p):
            result["date_code"] = p

    # Heuristic 1: /movies/{region}/... or /{region}/movies/...
    if "movies" in parts:
        idx = parts.index("movies")
        if idx > 0 and parts[idx - 1] not in ("buytickets", "explore"):
            result["region_slug"] = parts[idx - 1].lower()
        elif idx + 1 < len(parts) and parts[idx + 1] not in ("buytickets", "explore"):
            result["region_slug"] = parts[idx + 1].lower()

    # Heuristic 2: /buytickets/{movie}-{region}/movie-{region}-{code}-MT/...
    if not result["region_slug"]:
        for p in parts:
            m = re.match(r"^movie-([a-zA-Z]+)-ET\d+", p, re.I)
            if m:
                result["region_slug"] = m.group(1).lower()
                break

    # Heuristic 3: Common top-level city path /{region}/...
    if not result["region_slug"] and parts:
        first = parts[0].lower()
        if first in STATIC_REGION_MAP:
            result["region_slug"] = first

    # Movie name heuristic from URL slug
    for p in parts:
        clean_p = p.lower()
        if (
            not re.search(r"ET\d{8,}", p, re.I)
            and not re.match(r"^\d{8}$", p)
            and clean_p not in ("movies", "buytickets", "explore")
            and clean_p != (result.get("region_slug") or "").lower()
            and clean_p not in STATIC_REGION_MAP
        ):
            name_candidate = re.sub(r"^movie-", "", p, flags=re.I)
            result["movie_name"] = name_candidate.replace("-", " ").title()
            break

    return result


def parse_date_range(raw_dates_str):
    """
    Parse date string into a sorted list of YYYYMMDD date codes.
    Supports:
    - 'today' (today only)
    - 'today+3' (today through next 3 days)
    - '20261110-20261115' or '2026-11-10 to 2026-11-15' (date ranges)
    - '20261110,20261112' (comma-separated list)
    """
    if not raw_dates_str:
        return []
    s = raw_dates_str.strip().lower()
    now = datetime.now()

    if s == "today":
        return [now.strftime("%Y%m%d")]

    today_plus = re.match(r"^today\+(\d+)$", s)
    if today_plus:
        days = int(today_plus.group(1))
        return [(now + timedelta(days=i)).strftime("%Y%m%d") for i in range(days + 1)]

    # Range: Start to End
    range_match = re.match(r"^(\d{4}-?\d{2}-?\d{2})\s*(?:to|-)\s*(\d{4}-?\d{2}-?\d{2})$", s, re.I)
    if range_match:
        d1_str = range_match.group(1).replace("-", "")
        d2_str = range_match.group(2).replace("-", "")
        try:
            d1 = datetime.strptime(d1_str, "%Y%m%d")
            d2 = datetime.strptime(d2_str, "%Y%m%d")
            if d1 > d2:
                d1, d2 = d2, d1
            result = []
            curr = d1
            while curr <= d2:
                result.append(curr.strftime("%Y%m%d"))
                curr += timedelta(days=1)
            return result
        except ValueError:
            pass

    # Comma or space separated
    parts = re.split(r"[,;\s]+", s)
    result = []
    for p in parts:
        clean = p.replace("-", "").strip()
        if re.match(r"^\d{8}$", clean):
            try:
                datetime.strptime(clean, "%Y%m%d")
                if clean not in result:
                    result.append(clean)
            except ValueError:
                pass
    return sorted(result)


def format_date_human(date_str):
    """
    Format YYYYMMDD date code into human-friendly string like:
    'Sunday, 15th November 2026'
    """
    if not date_str:
        return ""
    clean = re.sub(r"[^\d]", "", str(date_str))[:8]
    if len(clean) != 8:
        return str(date_str)
    try:
        dt = datetime.strptime(clean, "%Y%m%d")
        day = dt.day
        if 11 <= (day % 100) <= 13:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return f"{dt.strftime('%A')}, {day}{suffix} {dt.strftime('%B %Y')}"
    except Exception:
        return str(date_str)

# ──────────────────────────────────────────────────────────────────────
# BMS API CLIENT
# ──────────────────────────────────────────────────────────────────────
API_URL = "https://in.bookmyshow.com/api/movies-data/v4/showtimes-by-event/primary-dynamic"

def create_bms_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "x-app-code": "WEB",
        "x-location-selection": "manual",
        "x-lsid": "",
        "sec-ch-ua": '"Chromium";v="145", "Not:A-Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    })
    return s


def fetch_bms(session, event_code, date_code, region_code, region_slug, lat, lon, geohash=""):
    headers = {
        "x-region-code": region_code,
        "x-region-slug": region_slug,
        "x-geohash": geohash or "",
        "x-latitude": lat,
        "x-longitude": lon,
        "x-location-selection": "manual",
        "x-lsid": "",
        "Referer": f"https://in.bookmyshow.com/movies/{region_slug}/buytickets/{event_code}/",
    }
    params = {
        "eventCode": event_code,
        "dateCode": date_code or "",
        "isDesktop": "true",
        "regionCode": region_code,
        "xLocationShared": "false",
        "memberId": "",
        "lsId": "",
        "subCode": "",
        "lat": lat,
        "lon": lon,
    }
    for attempt in range(2):
        try:
            resp = session.get(API_URL, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 403 and attempt == 0:
                time.sleep(1.5)
                # Fallback user agent on 403
                headers["User-Agent"] = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                continue
            print(f"  HTTP {resp.status_code} for {event_code} ({date_code or 'default'})")
        except requests.RequestException as e:
            if attempt == 0:
                time.sleep(1.0)
                continue
            print(f"  Request failed: {e}")
    return None

# ──────────────────────────────────────────────────────────────────────
# DATA PARSERS & FORMAT DISCOVERY
# ──────────────────────────────────────────────────────────────────────
def extract_movie_info(data):
    info = {"name": "Unknown Movie", "language": ""}
    header_title = data.get("data", {}).get("header", {}).get("title", {})
    if header_title.get("text"):
        info["name"] = header_title["text"]

    bs = data.get("data", {}).get("bottomSheetData", {})
    for w in bs.get("format-selector", {}).get("widgets", []):
        if w.get("type") == "vertical-text-list":
            for d in w.get("data", []):
                if d.get("styleId") == "bottomsheet-subtitle":
                    info["name"] = d.get("text", info["name"])

    for w in data.get("data", {}).get("topStickyWidgets", []):
        if w.get("type") == "horizontal-text-list":
            for item in w.get("data", []):
                for row in item.get("leftText", {}).get("data", []):
                    for c in row.get("components", []):
                        if "•" in c.get("text", ""):
                            info["language"] = c["text"].strip()
    return info


def extract_available_formats(data, base_event_code):
    """
    Extract all formats and languages linked to this movie from BookMyShow's format-selector.
    Returns list of dicts: language, format, event_code, display.
    """
    formats = []
    seen = set()
    fs = data.get("data", {}).get("bottomSheetData", {}).get("format-selector", {})
    for w in fs.get("widgets", []):
        if w.get("type") == "chip-list":
            lang = w.get("text", "").strip()
            for chip in w.get("data", []):
                fmt_title = chip.get("title", "").strip()
                addl = chip.get("cta", {}).get("additionalData", {})
                ecode = addl.get("eventCode") or addl.get("refEventCode")
                if ecode and ecode not in seen:
                    seen.add(ecode)
                    formats.append({
                        "language": lang,
                        "format": fmt_title,
                        "event_code": ecode,
                        "display": f"{lang} • {fmt_title}"
                    })
    return formats


def match_target_formats(available_formats, base_event_code, show_type_filter="", format_filter="", lang_filter=""):
    """
    Match available formats based on show_type, format, and lang criteria.
    e.g. show_type="hindi, imax" matches format "Hindi • IMAX 3D".
    """
    if not available_formats:
        return [{"event_code": base_event_code, "language": "", "format": "", "display": "Default"}]

    tokens = []
    if show_type_filter:
        tokens.extend([t.strip().lower() for t in re.split(r"[,;]+", show_type_filter) if t.strip()])
    if format_filter:
        tokens.extend([t.strip().lower() for t in re.split(r"[,;]+", format_filter) if t.strip()])
    if lang_filter:
        tokens.extend([t.strip().lower() for t in re.split(r"[,;]+", lang_filter) if t.strip()])

    if not tokens:
        # If no filter specified, track the base event code format if found, otherwise all
        for f in available_formats:
            if f["event_code"] == base_event_code:
                return [f]
        return available_formats

    matched = []
    for f in available_formats:
        haystack = f"{f['language']} {f['format']}".lower()
        if all(token in haystack for token in tokens):
            matched.append(f)

    if not matched:
        # Partial match if all tokens didn't match simultaneously
        for f in available_formats:
            haystack = f"{f['language']} {f['format']}".lower()
            if any(token in haystack for token in tokens):
                matched.append(f)

    return matched or [{"event_code": base_event_code, "language": "", "format": "", "display": "Default"}]


def parse_dates(data):
    dates = []
    seen = set()
    for w in data.get("data", {}).get("topStickyWidgets", []):
        if w.get("type") != "horizontal-block-list":
            continue
        for item in w.get("data", []):
            texts = item.get("data", [])
            if len(texts) >= 3:
                dc = item.get("id", "")
                if dc and dc not in seen:
                    seen.add(dc)
                    style = item.get("styleId", "")
                    dates.append(DateInfo(
                        date_code=dc,
                        status=DATE_STYLE_MAP.get(style, "UNKNOWN"),
                    ))
    return dates


def parse_shows(data, language="", format_title=""):
    shows = []
    for w in data.get("data", {}).get("showtimeWidgets", []):
        if w.get("type") != "groupList":
            continue
        for g in w.get("data", []):
            if g.get("type") != "venueGroup":
                continue
            for card in g.get("data", []):
                if card.get("type") != "venue-card":
                    continue
                addl = card.get("additionalData", {})
                vname = addl.get("venueName", "Unknown")
                vcode = addl.get("venueCode", "")

                for st in card.get("showtimes", []):
                    sa = st.get("additionalData", {})
                    date_code = str(
                        sa.get("showDateCode", "")
                        or sa.get("dateCode", "")
                    ).strip()
                    if not date_code and re.match(r"^\d{8}", sa.get("cutOffDateTime", "")):
                        date_code = sa["cutOffDateTime"][:8]

                    screen_attr = st.get("screenAttr") or sa.get("attributes") or ""

                    show = ShowInfo(
                        venue_code=vcode,
                        venue_name=vname,
                        session_id=sa.get("sessionId", ""),
                        date_code=date_code,
                        time=st.get("title", ""),
                        time_code=str(sa.get("showTimeCode", "")),
                        screen_attr=screen_attr,
                        language=language,
                        format_title=format_title,
                    )
                    for cat in sa.get("categories", []):
                        ca = str(cat.get("availStatus", ""))
                        show.categories.append(CatInfo(
                            name=cat.get("priceDesc", ""),
                            price=cat.get("curPrice", "0"),
                            status=ca,
                        ))
                    shows.append(show)
    return shows

# ──────────────────────────────────────────────────────────────────────
# FILTERING
# ──────────────────────────────────────────────────────────────────────
def filter_shows(shows, theatre_filter="", time_periods="", allowed_dates=None, show_type_filter=""):
    result = []
    theatre_kws = [k.strip().lower() for k in re.split(r"[,;]+", theatre_filter) if k.strip()]
    periods = [p.strip().lower() for p in re.split(r"[,;]+", time_periods) if p.strip()]
    dates_set = set(allowed_dates) if allowed_dates else set()
    type_tokens = [t.strip().lower() for t in re.split(r"[,;]+", show_type_filter) if t.strip()]

    for s in shows:
        # Theatre filter
        if theatre_kws:
            name_lower = s.venue_name.lower()
            if not any(k in name_lower for k in theatre_kws):
                continue

        # Date filter
        if dates_set and s.date_code and s.date_code not in dates_set:
            continue

        # Time period filter
        if periods:
            try:
                tc = int(s.time_code)
            except ValueError:
                tc = 0
            matched = False
            for p in periods:
                if p in TIME_PERIODS:
                    lo, hi = TIME_PERIODS[p]
                    if lo <= tc < hi:
                        matched = True
                        break
            if not matched:
                continue

        # Show type / Screen attributes check (if applicable)
        if type_tokens:
            haystack = f"{s.language} {s.format_title} {s.screen_attr}".lower()
            if not any(token in haystack for token in type_tokens):
                continue

        result.append(s)
    return result

# ──────────────────────────────────────────────────────────────────────
# STATE PERSISTENCE & CHANGE DETECTION
# ──────────────────────────────────────────────────────────────────────
def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"  ⚠️ Error saving state: {e}")


def build_state(shows, dates, movie_name="", event_code="", waiting=False):
    show_state = {}
    for s in shows:
        fmt = s.format_title or s.screen_attr
        for c in s.categories:
            key = f"{s.venue_code}|{s.session_id}|{s.date_code}|{c.name}"
            show_state[key] = {
                "venue": s.venue_name,
                "time": s.time,
                "date": s.date_code,
                "format": fmt,
                "cat": c.name,
                "price": c.price,
                "status": c.status,
            }

    date_state = {d.date_code: d.status for d in dates}
    return {
        "event_code": event_code,
        "movie": movie_name,
        "waiting_for_release": waiting,
        "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "shows": show_state,
        "dates": date_state,
    }


def detect_changes(old_state, new_state, current_event_code=""):
    changes = []
    # If state is from an entirely different movie or legacy state without event_code, treat as fresh baseline
    if not old_state or old_state.get("event_code") != current_event_code:
        return changes

    old_shows = old_state.get("shows", {})
    new_shows = new_state.get("shows", {})
    was_waiting = old_state.get("waiting_for_release", False) or len(old_shows) == 0

    # 1. TICKET RELEASE EVENT (First time tickets become bookable!)
    if was_waiting and len(new_shows) > 0:
        changes.append("🚨 BOOKINGS OPENED! Tickets have just been released on BookMyShow!")

    # 2. Date opening event
    old_dates = old_state.get("dates", {})
    new_dates = new_state.get("dates", {})
    for dc, status in new_dates.items():
        old_status = old_dates.get(dc)
        if old_status == "NOT_OPEN" and status in ("BOOKABLE", "AVAILABLE"):
            changes.append(f"📅 NEW DATE OPENED FOR BOOKING: {format_date_human(dc)}")

    # 3. New showtimes added
    for key in set(new_shows) - set(old_shows):
        s = new_shows[key]
        fmt_str = f" [{s.get('format')}]" if s.get("format") else ""
        changes.append(
            f"🆕 NEW SHOW: {s['venue']} {s['time']}{fmt_str} on {format_date_human(s['date'])} "
            f"— {s['cat']} ₹{s['price']}"
        )

    # 4. Sold out → Available again
    for key, new_s in new_shows.items():
        old_s = old_shows.get(key)
        if old_s and old_s.get("status") == "0" and new_s.get("status") != "0":
            lbl, ico = AVAIL_STATUS_MAP.get(new_s["status"], ("AVAILABLE", "🟢"))
            fmt_str = f" [{new_s.get('format')}]" if new_s.get("format") else ""
            changes.append(
                f"{ico} TICKETS BACK: {new_s['venue']} {new_s['time']}{fmt_str} "
                f"[{format_date_human(new_s['date'])}] — {new_s['cat']} → {lbl}"
            )

    return changes

# ──────────────────────────────────────────────────────────────────────
# EMAIL NOTIFICATIONS (Resend)
# ──────────────────────────────────────────────────────────────────────
def send_email(subject, changes, shows, movie_info, config, is_release=False):
    api_key = config.get("resend_api_key", "").strip()
    raw_to = config.get("resend_to_email", "").strip()
    frm = config.get("resend_from_email", "").strip() or "onboarding@resend.dev"

    # Support multiple comma-separated email addresses
    recipients = [e.strip() for e in re.split(r"[,;]+", raw_to) if e.strip()]

    if not api_key or not recipients:
        print("  ⚠️ Email skipped — RESEND_API_KEY or RESEND_TO_EMAIL not configured.")
        return

    now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
    movie_name = movie_info.get("name", "Movie")
    bms_url = config.get("url", "https://in.bookmyshow.com")

    banner_color = "#EB4E62" if is_release else "#2D3748"
    banner_title = "🚨 TICKETS RELEASED!" if is_release else "🎟️ BMS Ticket Alert"

    # Build changes HTML
    changes_html = ""
    if changes:
        rows = "".join(
            f'<li style="padding:4px 0;font-size:14px;color:#222;">{escape(c)}</li>'
            for c in changes
        )
        changes_html = f"""
        <div style="background:#FFF5F5;border-left:4px solid #EB4E62;padding:12px 16px;margin-bottom:20px;border-radius:4px;">
            <h3 style="margin:0 0 8px 0;font-size:15px;color:#C53030;">Updates Detected</h3>
            <ul style="margin:0;padding-left:20px;line-height:1.6;">{rows}</ul>
        </div>"""

    # Group shows by venue
    venue_groups = {}
    for s in shows:
        venue_groups.setdefault(s.venue_name, []).append(s)

    shows_html = ""
    for vname, vshows in venue_groups.items():
        show_rows = ""
        for s in vshows:
            cats = " | ".join(
                f"{escape(c.name)} ₹{escape(c.price)} ({AVAIL_STATUS_MAP.get(c.status, ('?', ''))[0]})"
                for c in s.categories
            )
            fmt = f" [{escape(s.format_title or s.screen_attr)}]" if (s.format_title or s.screen_attr) else ""
            formatted_date = format_date_human(s.date_code)
            show_rows += (
                f'<tr>'
                f'<td style="padding:8px 10px;border-bottom:1px solid #edf2f7;font-size:13px;font-weight:600;">'
                f'{escape(s.time)}{fmt}<br><span style="font-size:12px;color:#718096;font-weight:normal;">{escape(formatted_date)}</span></td>'
                f'<td style="padding:8px 10px;border-bottom:1px solid #edf2f7;font-size:13px;color:#4a5568;">{cats}</td>'
                f'</tr>'
            )

        shows_html += f"""
        <div style="margin-top:16px;background:#f7fafc;padding:12px;border-radius:6px;border:1px solid #e2e8f0;">
            <h4 style="margin:0 0 8px 0;font-size:14px;color:#2d3748;">📍 {escape(vname)}</h4>
            <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:4px;overflow:hidden;">
                <thead>
                    <tr style="background:#edf2f7;color:#4a5568;font-size:12px;">
                        <th style="padding:6px 10px;text-align:left;">Time / Date</th>
                        <th style="padding:6px 10px;text-align:left;">Categories & Pricing</th>
                    </tr>
                </thead>
                <tbody>{show_rows}</tbody>
            </table>
        </div>"""

    html = f"""<!doctype html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:20px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#2d3748;background:#f4f5f7;">
    <div style="max-width:640px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);padding:24px;">
        <div style="background:{banner_color};color:#fff;padding:14px 18px;border-radius:6px;margin-bottom:20px;">
            <h1 style="margin:0;font-size:18px;font-weight:bold;">{banner_title}</h1>
            <p style="margin:4px 0 0 0;font-size:13px;opacity:0.9;">{escape(movie_name)} — {escape(now_str)}</p>
        </div>

        {changes_html}

        <div style="text-align:center;margin:20px 0;">
            <a href="{escape(bms_url)}" style="background:#EB4E62;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:6px;font-weight:bold;font-size:15px;display:inline-block;">
                🎟️ Book Tickets on BookMyShow
            </a>
        </div>

        <h3 style="margin:20px 0 10px 0;font-size:15px;color:#1a202c;border-bottom:2px solid #edf2f7;padding-bottom:6px;">
            Available Showtimes ({len(shows)})
        </h3>
        {shows_html or '<p style="color:#718096;font-size:13px;">No active showtimes currently listed.</p>'}

        <hr style="border:none;border-top:1px solid #edf2f7;margin:24px 0 12px 0;">
        <p style="font-size:12px;color:#a0aec0;text-align:center;margin:0;">
            BMS Ticket Notifier Bot • Automated Alert
        </p>
    </div>
</body>
</html>"""

    plain = f"{subject}\n\nChecked at: {now_str}\nBook: {bms_url}\n\n"
    if changes:
        plain += "Changes:\n" + "\n".join(f" - {c}" for c in changes) + "\n\n"
    plain += f"Current shows ({len(shows)}):\n"
    for vname, vshows in venue_groups.items():
        plain += f"\n{vname}:\n"
        for s in vshows:
            cats = " | ".join(f"{c.name} Rs.{c.price}" for c in s.categories)
            fmt = f" [{s.format_title or s.screen_attr}]" if (s.format_title or s.screen_attr) else ""
            plain += f"  {s.time}{fmt} [{format_date_human(s.date_code)}] - {cats}\n"

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": frm,
                "to": recipients,
                "subject": subject,
                "text": plain,
                "html": html,
            },
            timeout=15,
        )
        recipients_str = ", ".join(recipients)
        if resp.status_code in (200, 201):
            print(f"  📧 Alert email successfully sent to {recipients_str}!")
        else:
            print(f"  ❌ Resend API error ({resp.status_code}): {resp.text}")
            if "testing emails to your own email address" in resp.text:
                print("  💡 Tip: With Resend's free default sender (onboarding@resend.dev), you can only send to your own registered email.")
                print("     To send alerts to multiple different email addresses, add and verify your custom domain at https://resend.com/domains")
    except requests.RequestException as e:
        print(f"  ❌ Failed to send email: {e}")

# ──────────────────────────────────────────────────────────────────────
# CHECK RUNNER (One cycle)
# ──────────────────────────────────────────────────────────────────────
def run_check(config, session, is_loop=False):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"[{now_str}] 🎬 BMS Ticket Check")
    print(f"{'='*60}")

    parsed = parse_bms_url(config["url"])
    event_code = parsed["event_code"]
    region_slug = config.get("region") or parsed.get("region_slug")
    url_date = parsed.get("date_code", "")

    if not event_code:
        print("  ❌ Could not determine event code from URL.")
        print("  Please provide a valid BookMyShow movie URL or Event Code (e.g. ET00xxxxxx).")
        return False

    if not region_slug:
        region_slug = "mumbai"
        print(f"  ℹ️ Region not detected in URL, defaulting to '{region_slug}' (override with --region or BMS_REGION)")

    region_code, region_slug_r, lat, lon, geohash = resolve_region(region_slug, session)
    print(f"  📍 Region: {region_code} ({region_slug_r}) | Event: {event_code}")

    # Step 1: Initial fetch to discover movie info, formats, and available dates
    initial_data = fetch_bms(session, event_code, "", region_code, region_slug_r, lat, lon, geohash)
    if not initial_data:
        print(f"  ⚠️ Could not reach BookMyShow for event {event_code}. Will retry next interval.")
        return False

    movie_info = extract_movie_info(initial_data)
    if movie_info.get("name") in ("Unknown Movie", "Unknown", "") and parsed.get("movie_name"):
        movie_info["name"] = parsed["movie_name"]

    available_formats = extract_available_formats(initial_data, event_code)
    available_dates_info = parse_dates(initial_data)

    print(f"  🎥 Movie: {movie_info['name']}")
    if available_formats:
        fmt_names = [f["display"] for f in available_formats]
        print(f"  🎞️ Available Formats on BMS: {', '.join(fmt_names)}")

    # Step 2: Match target formats based on user's filters
    target_formats = match_target_formats(
        available_formats,
        event_code,
        show_type_filter=config.get("show_type", ""),
        format_filter=config.get("format", ""),
        lang_filter=config.get("lang", ""),
    )
    target_names = [f["display"] for f in target_formats]
    print(f"  🎯 Monitoring Formats ({len(target_formats)}): {', '.join(target_names)}")

    # Step 3: Determine target dates
    target_dates = parse_date_range(config.get("dates", ""))
    if not target_dates and url_date:
        target_dates = [url_date]
    if not target_dates and available_dates_info:
        # Auto-detect all dates from BookMyShow
        target_dates = [d.date_code for d in available_dates_info if d.date_code]

    if not target_dates:
        target_dates = [""]  # Default/today

    dates_display = ', '.join(format_date_human(d) for d in target_dates) if target_dates != [''] else '(Default/Today)'
    print(f"  📅 Monitoring Dates ({len(target_dates)}): {dates_display}")
    if config.get("theatre"):
        print(f"  🏛️ Theatre Filter: '{config['theatre']}'")
    if config.get("time_period"):
        print(f"  ⏰ Time Filter: '{config['time_period']}'")

    # Step 4: Fetch showtimes for each format and date
    all_shows = []
    all_dates = list(available_dates_info)

    for tf in target_formats:
        f_code = tf["event_code"]
        f_lang = tf.get("language", "")
        f_fmt = tf.get("format", "")

        for dc in target_dates:
            data = fetch_bms(session, f_code, dc, region_code, region_slug_r, lat, lon, geohash)
            if not data:
                continue

            date_objs = parse_dates(data)
            existing_dc = {d.date_code for d in all_dates}
            for d in date_objs:
                if d.date_code not in existing_dc:
                    all_dates.append(d)
                    existing_dc.add(d.date_code)

            shows = parse_shows(data, language=f_lang, format_title=f_fmt)
            all_shows.extend(shows)

    # Step 5: Filter shows
    filtered_shows = filter_shows(
        all_shows,
        theatre_filter=config.get("theatre", ""),
        time_periods=config.get("time_period", ""),
        allowed_dates=target_dates if target_dates != [""] else None,
        show_type_filter=config.get("show_type", ""),
    )

    # Step 6: State & Change Detection
    old_state = load_state()
    is_release = False

    if not filtered_shows:
        print(f"\n  ⏳ Status: No showtimes currently match your criteria.")
        if not all_shows:
            print(f"     Bookings have not opened yet for '{movie_info['name']}'. Monitoring continues...")
        new_state = build_state([], all_dates, movie_info["name"], event_code, waiting=True)
    else:
        num_venues = len(set(s.venue_name for s in filtered_shows))
        print(f"\n  📊 Status: Found {len(filtered_shows)} matching showtime(s) across {num_venues} venue(s)!")
        new_state = build_state(filtered_shows, all_dates, movie_info["name"], event_code, waiting=False)

    changes = []
    if old_state:
        changes = detect_changes(old_state, new_state, current_event_code=event_code)
        if any("BOOKINGS OPENED" in c for c in changes):
            is_release = True
    else:
        print("  📝 Baseline state saved. Watching for new releases, added shows, and seat availability changes...")

    save_state(new_state)

    # Step 7: Notification Dispatch
    if changes:
        print(f"\n  ⚡ {len(changes)} CHANGE(S) DETECTED:")
        for c in changes:
            print(f"     {c}")
        # Audio chime in terminal
        sys.stdout.write("\a")
        sys.stdout.flush()

        subject_prefix = "🚨 TICKETS RELEASED:" if is_release else f"🎟️ BMS Alert ({len(changes)} changes):"
        subject = f"{subject_prefix} {movie_info['name']}"
        send_email(subject, changes, filtered_shows, movie_info, config, is_release=is_release)
    elif config.get("force_email") or (not old_state and config.get("notify_initial")):
        print(f"\n  📧 Sending current showtimes email ({len(filtered_shows)} shows)...")
        subject = f"🎟️ BMS Current Showtimes: {movie_info['name']} ({len(filtered_shows)} shows)"
        initial_summary = [f"📋 Initial status: {len(filtered_shows)} matching showtimes currently available."]
        send_email(subject, initial_summary, filtered_shows, movie_info, config, is_release=False)
    else:
        if old_state:
            print("  ✅ No new changes since last check (email alert sent only when changes/releases occur).")

    # Print summary of matches
    if filtered_shows:
        print("\n  Current Matches:")
        for s in filtered_shows[:8]:
            cats = ", ".join(f"{c.name}=₹{c.price}({AVAIL_STATUS_MAP.get(c.status, ('?',''))[0]})" for c in s.categories[:3])
            fmt = f" | {s.format_title or s.screen_attr}" if (s.format_title or s.screen_attr) else ""
            print(f"    • {s.venue_name} — {s.time}{fmt} [{format_date_human(s.date_code)}] → {cats}")
        if len(filtered_shows) > 8:
            print(f"    ... and {len(filtered_shows) - 8} more shows.")

    return True

# ──────────────────────────────────────────────────────────────────────
# CLI & ENTRYPOINT
# ──────────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="BookMyShow Ticket Notifier Bot — Monitors ticket releases, shows, and availability."
    )
    parser.add_argument("--url", default=os.getenv("BMS_URL"), help="BookMyShow movie URL or Event Code")
    parser.add_argument("--dates", default=os.getenv("BMS_DATES", ""), help="Dates or range (e.g. 20261110-20261115, today+3)")
    parser.add_argument("--theatre", default=os.getenv("BMS_THEATRE", ""), help="Theatre name filter (e.g. PVR, INOX)")
    parser.add_argument("--show-type", default=os.getenv("BMS_SHOW_TYPE", ""), help="Show type filter (e.g. 'hindi, imax', 'imax')")
    parser.add_argument("--format", default=os.getenv("BMS_FORMAT", ""), help="Format filter (e.g. imax, 3d, 4dx)")
    parser.add_argument("--lang", default=os.getenv("BMS_LANG", ""), help="Language filter (e.g. hindi, english)")
    parser.add_argument("--time", default=os.getenv("BMS_TIME", ""), help="Time period (morning, afternoon, evening, night)")
    parser.add_argument("--region", default=os.getenv("BMS_REGION", ""), help="City/region override (e.g. mumbai, bengaluru)")
    parser.add_argument("--interval", type=int, default=int(os.getenv("CHECK_INTERVAL", "0")), help="Polling interval in seconds")
    parser.add_argument("--loop", action="store_true", help="Run continuously in a loop")
    parser.add_argument("--once", action="store_true", help="Run once and exit (default if interval=0)")
    parser.add_argument("--force-email", action="store_true", help="Send email notification with current showtimes even if no changes occurred")
    parser.add_argument("--notify-initial", action="store_true", help="Send email notification on initial baseline run")
    parser.add_argument("--test-email", action="store_true", help="Send a test notification email and exit")
    parser.add_argument("--reset-state", action="store_true", help="Reset state file and exit")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.reset_state:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            print(f"  🗑️ Deleted {STATE_FILE}.")
        print("  State reset.")
        return

    url = args.url or os.getenv("BMS_URL")
    config = {
        "url": url,
        "dates": args.dates,
        "theatre": args.theatre,
        "show_type": args.show_type,
        "format": args.format,
        "lang": args.lang,
        "time_period": args.time,
        "region": args.region,
        "force_email": args.force_email or os.getenv("FORCE_EMAIL", "").lower() in ("true", "1", "yes"),
        "notify_initial": args.notify_initial or os.getenv("NOTIFY_ON_START", "true").lower() in ("true", "1", "yes"),
        "resend_api_key": os.getenv("RESEND_API_KEY", ""),
        "resend_to_email": os.getenv("RESEND_TO_EMAIL", ""),
        "resend_from_email": os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev"),
    }

    if args.test_email:
        print("  📧 Sending test email via Resend...")
        test_info = {"name": "Test Movie (BMS Notifier)"}
        test_changes = ["✅ Test alert: Resend email configuration is working!"]
        send_email("🧪 BMS Notifier Test Email", test_changes, [], test_info, config)
        return

    if not config["url"]:
        print("\n❌ Error: No BookMyShow URL or Event Code provided.")
        print("You can provide it via:")
        print("  1. CLI argument:   python main.py --url 'https://in.bookmyshow.com/movies/mumbai/.../ET00xxxxxx'")
        print("  2. In .env file:   BMS_URL=https://in.bookmyshow.com/movies/mumbai/.../ET00xxxxxx")
        print("\nSee .env.example or README.md for complete details.")
        sys.exit(1)

    interval = args.interval
    is_loop = args.loop or interval > 0

    session = create_bms_session()

    if not is_loop or args.once:
        run_check(config, session, is_loop=False)
        print("\n  Check complete.")
        return

    poll_sec = interval if interval > 0 else 60
    print(f"\n🤖 BMS Ticket Notifier Bot started in continuous monitoring mode (Interval: {poll_sec}s).")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            run_check(config, session, is_loop=True)
            print(f"\n  💤 Sleeping for {poll_sec} seconds before next check...")
            time.sleep(poll_sec)
    except KeyboardInterrupt:
        print("\n\n👋 BMS Ticket Notifier Bot stopped by user.")


if __name__ == "__main__":
    main()
