"""
Fetcher — 3-tier fallback system

Tier 1: NSE corporate-announcements API (primary, ~85% coverage)
Tier 2: NSE with symbol alias (handles renames like ZOMATO→ETERNAL)
Tier 3: Screener.in company page scraping (PDF links, ~60% additional coverage)
"""

import re
import time
import requests
from nsepython import headers as NSE_HEADERS
from nse_symbols import search_companies

# ── Known NSE symbol aliases / renames ────────────────────────────────────────
# Format: old/popular symbol → current NSE symbol
SYMBOL_ALIASES = {
    "ZOMATO":       "ETERNAL",       # Zomato rebranded to Eternal Ltd
    "TATAMTRDVR":   "TATAMTRDVR",
    "M&M":          "M%26M",         # URL-encode & for API
    "BAJAJ-AUTO":   "BAJAJ-AUTO",
    "HDFCAMC":      "HDFCAMC",
}

CONCALL_KEYWORDS = [
    "concall", "con call", "earnings call", "analyst call",
    "investor call", "conference call", "analyst meet",
    "investor meet", "analyst day", "transcript",
    "q1", "q2", "q3", "q4", "quarterly", "earnings",
    "results", "financial results", "press conference",
    "investor presentation", "analyst presentation",
]

CONCALL_CATEGORIES = {
    "Analysts/Institutional Investor Meet/Con. Call Updates",
    "Investor Presentation",
    "Outcome of Board Meeting",
    "Updates",
}

_nse_session = None


# ── Session helpers ────────────────────────────────────────────────────────────

def _fresh_nse_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(NSE_HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=10)
        time.sleep(0.4)
    except Exception:
        pass
    return s


def _get_nse_session(force: bool = False) -> requests.Session:
    global _nse_session
    if _nse_session is None or force:
        _nse_session = _fresh_nse_session()
    return _nse_session


def _screener_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://www.screener.in",
    })
    return s


# ── Tier 1 + 2: NSE API ───────────────────────────────────────────────────────

def _nse_fetch_raw(symbol: str, retries: int = 2) -> tuple[list, str]:
    """
    Fetch raw NSE announcements. Tries symbol + alias. Returns (data, symbol_used).
    """
    symbols_to_try = [symbol]
    alias = SYMBOL_ALIASES.get(symbol.upper())
    if alias and alias != symbol:
        symbols_to_try.append(alias)

    for sym in symbols_to_try:
        url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={sym}"
        for attempt in range(retries + 1):
            s = _get_nse_session(force=(attempt > 0))
            try:
                r = s.get(url, timeout=15)
                r.raise_for_status()
                data = r.json()
                if data:
                    return data, sym
                if attempt < retries:
                    time.sleep(1.2)
            except Exception:
                if attempt < retries:
                    time.sleep(1)

    return [], symbol


def _parse_nse_doc(ann: dict) -> dict | None:
    """Convert raw NSE announcement → standardised doc dict. Returns None if no PDF."""
    if not ann.get("attchmntFile"):
        return None
    raw_dt = ann.get("an_dt", "")
    return {
        "date": raw_dt[:11].strip() if raw_dt else "",
        "title": ann.get("desc", "Document")[:120],
        "description": ann.get("attchmntText", "")[:250],
        "pdf_url": ann.get("attchmntFile", ""),
        "size": ann.get("attFileSize", ""),
        "source": "NSE",
    }


def _is_concall(ann: dict) -> bool:
    category = ann.get("desc", "")
    text = (category + " " + ann.get("attchmntText", "")).lower()
    return (category in CONCALL_CATEGORIES) or any(kw in text for kw in CONCALL_KEYWORDS)


# ── Tier 3: Screener.in ────────────────────────────────────────────────────────

def _screener_find_slug(symbol: str) -> str | None:
    """Search Screener.in for company slug by NSE symbol or name."""
    s = _screener_session()
    for query in [symbol, symbol.replace("-", " ")]:
        try:
            r = s.get(f"https://www.screener.in/api/company/search/?q={query}", timeout=8)
            results = r.json()
            if results:
                return results[0].get("url", "")
        except Exception:
            continue
    return None


def _screener_fetch_pdfs(slug: str) -> list[dict]:
    """Scrape Screener.in company page for concall/investor-day PDF links."""
    s = _screener_session()
    docs = []
    try:
        r = s.get(f"https://www.screener.in{slug}", timeout=12)
        if r.status_code != 200:
            return []

        # Extract all PDF links
        pdf_links = re.findall(
            r'href=["\']([^"\']*\.pdf[^"\']*)["\']',
            r.text, re.IGNORECASE
        )

        # Also find links near concall/transcript keywords
        all_links = re.findall(r'href=["\']([^"\']+)["\']', r.text)
        concall_links = [
            l for l in all_links
            if any(kw in l.lower() for kw in [
                "concall", "transcript", "earnings-call", "earnings_call",
                "investor-meet", "analyst-day", "quarterly-results",
                "q1", "q2", "q3", "q4"
            ])
        ]

        seen = set()
        for url in pdf_links + concall_links:
            if not url.startswith("http"):
                url = "https://www.screener.in" + url
            if url in seen:
                continue
            seen.add(url)

            # Only include if looks like a relevant document
            url_lower = url.lower()
            if any(kw in url_lower for kw in CONCALL_KEYWORDS + ["investor", "results", "annual"]):
                # Try to extract quarter/date from URL
                date_match = re.search(
                    r'(q[1-4][\s\-_]?fy\d{2,4}|fy\d{4}|\d{4}[-_]\d{2}[-_]\d{2})',
                    url_lower
                )
                date_label = date_match.group(0).upper() if date_match else "Recent"

                docs.append({
                    "date": date_label,
                    "title": "Investor Document (via Screener.in)",
                    "description": url.split("/")[-1][:100],
                    "pdf_url": url,
                    "size": "",
                    "source": "Screener.in",
                })

        return docs[:10]
    except Exception:
        return []


# ── Public API ─────────────────────────────────────────────────────────────────

def search_company_symbol(query: str) -> list[dict]:
    return search_companies(query)


def fetch_concall_documents(symbol: str, max_results: int = 25) -> tuple[list[dict], str]:
    """
    3-tier fetch. Returns (docs, source_used).
    source_used: 'NSE' | 'NSE (alias)' | 'Screener.in' | 'none'
    """
    # ── Tier 1 & 2: NSE ──
    raw, sym_used = _nse_fetch_raw(symbol)
    if raw:
        docs = []
        for ann in raw:
            if _is_concall(ann):
                doc = _parse_nse_doc(ann)
                if doc:
                    docs.append(doc)
            if len(docs) >= max_results:
                break

        source = "NSE" if sym_used == symbol else f"NSE (symbol: {sym_used})"
        if docs:
            return docs, source

        # NSE has data but no concall filter match → return all filings
        all_docs = [_parse_nse_doc(a) for a in raw[:max_results] if a.get("attchmntFile")]
        all_docs = [d for d in all_docs if d]
        if all_docs:
            return all_docs, f"{source} (all filings)"

    # ── Tier 3: Screener.in ──
    slug = _screener_find_slug(symbol)
    if slug:
        screener_docs = _screener_fetch_pdfs(slug)
        if screener_docs:
            return screener_docs, "Screener.in"

    return [], "none"


def fetch_all_recent_announcements(symbol: str, max_results: int = 50) -> list[dict]:
    """All NSE announcements with PDF, no concall filter."""
    raw, _ = _nse_fetch_raw(symbol, retries=1)
    docs = []
    for ann in raw[:max_results]:
        doc = _parse_nse_doc(ann)
        if doc:
            docs.append(doc)
    return docs


def download_pdf_from_url(pdf_url: str) -> bytes:
    s = _get_nse_session()
    r = s.get(pdf_url, timeout=30)
    r.raise_for_status()
    return r.content
