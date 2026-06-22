"""
Event Calendar — NSE Corporate Events
Fetches board meetings, AGMs, concalls, results dates for any month/year.
"""
from __future__ import annotations

import calendar
from datetime import datetime
from collections import defaultdict

import requests
from nsepython import headers as NSE_HEADERS

_session = None

EVENT_COLORS = {
    "Financial Results":         {"bg": "#dcfce7", "border": "#16a34a", "icon": "📊", "tag": "Results"},
    "Dividend":                  {"bg": "#fef3c7", "border": "#d97706", "icon": "💰", "tag": "Dividend"},
    "AGM":                       {"bg": "#dbeafe", "border": "#2563eb", "icon": "🏛️", "tag": "AGM"},
    "EGM":                       {"bg": "#ede9fe", "border": "#7c3aed", "icon": "📋", "tag": "EGM"},
    "Board Meeting Intimation":  {"bg": "#f3f4f6", "border": "#6b7280", "icon": "📅", "tag": "Board"},
    "Concall":                   {"bg": "#ecfdf5", "border": "#059669", "icon": "📞", "tag": "Concall"},
    "Buyback":                   {"bg": "#fce7f3", "border": "#db2777", "icon": "🔁", "tag": "Buyback"},
    "Other":                     {"bg": "#f9fafb", "border": "#d1d5db", "icon": "📌", "tag": "Event"},
}


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(NSE_HEADERS)
        try:
            _session.get("https://www.nseindia.com", timeout=10)
        except Exception:
            pass
    return _session


def _classify_event(purpose: str, desc: str) -> str:
    text = (purpose + " " + desc).lower()
    if any(w in text for w in ["agm", "annual general"]):
        return "AGM"
    if any(w in text for w in ["egm", "extraordinary general"]):
        return "EGM"
    if any(w in text for w in ["dividend", "record date"]):
        return "Dividend"
    if any(w in text for w in ["buyback", "buy back"]):
        return "Buyback"
    if any(w in text for w in ["concall", "con call", "earnings call", "analyst", "investor meet", "transcript"]):
        return "Concall"
    if any(w in text for w in ["financial results", "quarterly results", "q1", "q2", "q3", "q4", "half year", "annual results"]):
        return "Financial Results"
    if any(w in text for w in ["board meeting"]):
        return "Board Meeting Intimation"
    return "Other"


def fetch_events_for_month(year: int, month: int) -> list[dict]:
    """Fetch all NSE corporate events for a given month/year. Returns FIFO (date asc)."""
    s = _get_session()
    # Build date range
    last_day = calendar.monthrange(year, month)[1]
    from_date = f"01-{month:02d}-{year}"
    to_date = f"{last_day:02d}-{month:02d}-{year}"

    url = (
        f"https://www.nseindia.com/api/corporate-board-meetings"
        f"?index=equities&from_date={from_date}&to_date={to_date}"
    )

    try:
        r = s.get(url, timeout=15)
        r.raise_for_status()
        raw = r.json()
    except Exception:
        return []

    events = []
    seen = set()

    for item in raw:
        symbol = item.get("bm_symbol", "")
        company = item.get("sm_name", symbol)
        date_str = item.get("bm_date", "")
        purpose = item.get("bm_purpose", "")
        desc = item.get("bm_desc", "")
        attachment = item.get("attachment", "")
        industry = item.get("sm_indusrty", "")

        # Parse date
        try:
            dt = datetime.strptime(date_str, "%d-%b-%Y")
            date_key = dt.strftime("%Y-%m-%d")
            display_date = dt.strftime("%d %b %Y")
        except Exception:
            continue

        # Deduplicate: same company + same date + same purpose
        uid = f"{symbol}_{date_key}_{purpose[:30]}"
        if uid in seen:
            continue
        seen.add(uid)

        event_type = _classify_event(purpose, desc)
        style = EVENT_COLORS.get(event_type, EVENT_COLORS["Other"])

        events.append({
            "date_key":     date_key,
            "display_date": display_date,
            "day":          dt.day,
            "symbol":       symbol,
            "company":      company[:50],
            "purpose":      purpose,
            "desc":         desc[:300],
            "type":         event_type,
            "industry":     industry,
            "pdf_url":      attachment if attachment and attachment.endswith(".pdf") else "",
            "bg":           style["bg"],
            "border":       style["border"],
            "icon":         style["icon"],
            "tag":          style["tag"],
        })

    # LIFO: sort by date descending — most recent first
    events.sort(key=lambda x: (x["date_key"], x["company"]), reverse=True)
    return events


def group_by_day(events: list[dict]) -> dict[int, list[dict]]:
    """Group events by day-of-month."""
    grouped = defaultdict(list)
    for e in events:
        grouped[e["day"]].append(e)
    return dict(grouped)
