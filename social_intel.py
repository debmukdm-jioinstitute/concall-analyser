"""
Market Buzz / Social Intelligence
Fetches real-time mentions of NSE stocks across Indian financial news RSS feeds.
Sources: ET Markets, ET Stocks, Moneycontrol, LiveMint
"""

import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from collections import defaultdict

RSS_FEEDS = {
    "ET Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "ET Stocks": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "Moneycontrol": "https://www.moneycontrol.com/rss/latestnews.xml",
    "LiveMint": "https://www.livemint.com/rss/markets",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Auto-generated/templated headline patterns to skip — no real signal
NOISE_PATTERNS = [
    "share price live updates",
    "share price live update",
    "current price and trends",
    "live updates:",
    "price movement today",
    "stock price today",
    "intraday price",
    "live market updates",
    "top gainers & losers",
    "top gainers and losers",
    "market wrap",
    "closing bell",
    "trading session",
    "52-week high/low",
    "delivery percentage",
    "volume leaders",
    "most active stocks",
]


def _is_noise(title: str) -> bool:
    t = title.lower()
    return any(p in t for p in NOISE_PATTERNS)

# Analyst recommendation keywords → sentiment
BUY_SIGNALS = ["buy", "strong buy", "outperform", "overweight", "accumulate", "add", "target price", "upgrade"]
SELL_SIGNALS = ["sell", "reduce", "underperform", "underweight", "downgrade", "exit", "avoid"]
HOLD_SIGNALS = ["hold", "neutral", "market perform", "equal weight", "in-line"]

# NSE symbols that are also common English words → cause false positives
SYMBOL_BLOCKLIST = {
    "OIL", "GLOBAL", "FOCUS", "DOLLAR", "PRIME", "DEEP", "STAR", "POWER",
    "CAPITAL", "ENERGY", "MEDIA", "LINK", "TECH", "NET", "GOLD", "SILVER",
    "BLUE", "GREEN", "RED", "BLACK", "WHITE", "FIRST", "NEXT", "NEW",
    "MAX", "OPEN", "CORE", "BASE", "ACE", "ONE", "TEN", "APEX", "ALPHA",
    "BETA", "WAVE", "FLEX", "ARC", "ION", "ERA", "AGE", "AXIS",  # Axis is valid
    "FUTURE", "CLOUD", "SMART", "PLUS", "PRO", "GO", "UP", "ON", "IN",
    "EMKAY", "LENSKART",  # not pure NSE-listed
}

BULLISH_WORDS = ["gains", "surges", "rallies", "jumps", "rises", "soars", "beats", "outperforms",
                 "record high", "52-week high", "profit up", "revenue up", "order win", "expansion",
                 "dividend", "buyback", "acquisition", "upgrade"]
BEARISH_WORDS = ["falls", "drops", "tumbles", "slumps", "declines", "crashes", "misses", "disappoints",
                 "loss", "downgrade", "sebi", "probe", "fraud", "debt", "default", "weak", "cuts guidance"]


def _fetch_feed(name: str, url: str) -> list[dict]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            desc_el = item.find("description")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
            # Clean HTML tags from description
            desc = re.sub(r"<[^>]+>", "", desc)
            if _is_noise(title):
                continue
            items.append({
                "source": name,
                "title": title,
                "description": desc[:300],
                "link": link_el.text.strip() if link_el is not None and link_el.text else "",
                "published": pub_el.text.strip() if pub_el is not None and pub_el.text else "",
                "full_text": (title + " " + desc).lower(),
            })
        return items
    except Exception as e:
        return []


def fetch_all_news() -> list[dict]:
    """Fetch all RSS feeds and return combined article list."""
    all_items = []
    for name, url in RSS_FEEDS.items():
        items = _fetch_feed(name, url)
        all_items.extend(items)
    return all_items


def _score_headline(text: str) -> tuple[int, str]:
    """Score a headline -3 to +3. Returns (score, signal)."""
    text_l = text.lower()
    score = 0

    for w in BULLISH_WORDS:
        if w in text_l:
            score += 1
    for w in BEARISH_WORDS:
        if w in text_l:
            score -= 1

    for w in BUY_SIGNALS:
        if w in text_l:
            score += 2
    for w in SELL_SIGNALS:
        if w in text_l:
            score -= 2

    score = max(-3, min(3, score))
    if score >= 1:
        signal = "BULLISH"
    elif score <= -1:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"
    return score, signal


def extract_mentions(articles: list[dict], nse_companies: dict) -> dict:
    """
    For each article, find which NSE stocks are mentioned.
    Returns dict: symbol -> {name, count, articles, score_sum, signal}
    """
    mentions = defaultdict(lambda: {
        "name": "",
        "count": 0,
        "articles": [],
        "score_sum": 0,
        "buy_recs": 0,
        "sell_recs": 0,
        "hold_recs": 0,
    })

    # Build lookup: lower-case name → symbol
    name_to_sym = {name.lower(): sym for sym, name in nse_companies.items()}
    # Also short-name lookup (first word of company name)
    short_to_sym = {}
    for sym, name in nse_companies.items():
        first_word = name.split()[0].lower()
        if len(first_word) > 3:  # skip short words like "The", "of"
            if first_word not in short_to_sym:
                short_to_sym[first_word] = sym

    for art in articles:
        text = art["full_text"]
        score, signal = _score_headline(art["title"])
        matched_syms = set()

        # Match by NSE symbol — require UPPERCASE in original text to avoid false positives
        raw_text = art["title"] + " " + art["description"]
        for sym in nse_companies:
            if sym in SYMBOL_BLOCKLIST:
                continue
            if len(sym) < 3:  # skip very short symbols
                continue
            # Require symbol appears as uppercase word in original text
            pattern = r'\b' + re.escape(sym) + r'\b'
            if re.search(pattern, raw_text):  # case-sensitive match
                matched_syms.add(sym)

        # Match by company name
        for name_lower, sym in name_to_sym.items():
            # Only match names > 4 chars to avoid false positives
            if len(name_lower) > 4 and name_lower in text:
                matched_syms.add(sym)

        for sym in matched_syms:
            m = mentions[sym]
            m["name"] = nse_companies.get(sym, sym)
            m["count"] += 1
            m["score_sum"] += score
            m["articles"].append({
                "source": art["source"],
                "title": art["title"],
                "link": art["link"],
                "signal": signal,
                "score": score,
                "published": art["published"],
            })
            if signal == "BULLISH":
                m["buy_recs"] += 1
            elif signal == "BEARISH":
                m["sell_recs"] += 1
            else:
                m["hold_recs"] += 1

    # Compute final signal per stock
    result = {}
    for sym, m in mentions.items():
        if m["count"] == 0:
            continue
        avg_score = m["score_sum"] / m["count"]
        if avg_score >= 0.5:
            final_signal = "BULLISH"
            emoji = "🟢"
        elif avg_score <= -0.5:
            final_signal = "BEARISH"
            emoji = "🔴"
        else:
            final_signal = "NEUTRAL"
            emoji = "🟡"

        result[sym] = {
            "name": m["name"],
            "symbol": sym,
            "mentions": m["count"],
            "avg_score": round(avg_score, 1),
            "signal": final_signal,
            "emoji": emoji,
            "buy_recs": m["buy_recs"],
            "sell_recs": m["sell_recs"],
            "hold_recs": m["hold_recs"],
            "articles": m["articles"][:5],  # top 5 articles
        }

    # Sort by mention count
    return dict(sorted(result.items(), key=lambda x: -x[1]["mentions"]))


def get_trending_themes(articles: list[dict]) -> dict:
    """Extract trending themes/sectors from all headlines."""
    themes = {
        "IT / Tech": ["infosys", "tcs", "wipro", "hcltech", "tech mahindra", "mphasis", "coforge", "persistent"],
        "Banking": ["hdfc bank", "icici bank", "sbi", "axis bank", "kotak", "federal bank", "rbl", "indusind"],
        "Pharma": ["sun pharma", "cipla", "lupin", "divi", "dr reddy", "biocon", "alkem", "aurobindo"],
        "Auto": ["maruti", "tata motors", "m&m", "hero moto", "bajaj auto", "eicher", "tvs motor", "ashok leyland"],
        "Infra / Energy": ["reliance", "ongc", "ntpc", "power grid", "adani", "tata power", "gail", "coal india"],
        "FMCG": ["hindustan unilever", "itc", "nestle", "dabur", "marico", "colgate", "britannia", "godrej"],
        "Metals / Mining": ["tata steel", "jsw steel", "hindalco", "vedanta", "nmdc", "sail", "jindal"],
        "Real Estate": ["dlf", "godrej properties", "oberoi", "prestige", "brigade", "sobha"],
    }

    theme_counts = {}
    for theme, keywords in themes.items():
        count = sum(
            1 for art in articles
            if any(kw in art["full_text"] for kw in keywords)
        )
        if count > 0:
            theme_counts[theme] = count

    return dict(sorted(theme_counts.items(), key=lambda x: -x[1]))
