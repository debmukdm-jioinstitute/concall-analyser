"""
Announcement Parser — Weighted Scoring Algorithm v2

Algorithm design:
  final_score = Σ(raw_score × category_weight × recency_weight) / Σ(category_weight × recency_weight)

Three layers:
  1. raw_score    — what the text says (keyword rules, -10 to +10)
  2. category_weight — how important is this type of event (1x to 3x)
  3. recency_weight  — how recent is it (0.2x to 1.0x, decays over time)
"""

import re
import math
from datetime import datetime, timedelta
from nsepython import headers
import requests

_session = None

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1: Text Scoring Rules
# Each rule: (keywords, base_score, label)
# base_score range: -10 to +10
# ─────────────────────────────────────────────────────────────────────────────
SCORING_RULES = [
    # ── Tier A: Structural / Capital events (high signal) ────────────────────
    (["buyback", "buy back", "buy-back"],                            +10, "Share Buyback"),
    (["special dividend", "interim dividend", "final dividend"],     +8,  "Dividend (Special/Final)"),
    (["dividend"],                                                   +6,  "Dividend"),
    (["bonus shares", "bonus issue", "bonus share"],                 +7,  "Bonus Issue"),
    (["stock split", "share split"],                                 +5,  "Stock Split"),
    (["record date"],                                                +3,  "Record Date Set"),
    (["insolvency", "nclt", "winding up", "bankruptcy"],             -10, "Insolvency/NCLT"),
    (["fraud", "scam", "cbi", "ed notice", "enforcement directorate"], -9, "Fraud/Investigation"),
    (["sebi order", "sebi notice", "sebi action", "nse penalty", "bse penalty"], -8, "Regulatory Action"),
    (["loan default", "default on payment", "npa", "non performing"], -8, "Loan Default/NPA"),
    (["pledge creation", "pledged shares", "pledge of shares"],      -7,  "Promoter Pledge Created"),
    (["pledge revocation", "pledge revoked", "pledge released"],     +6,  "Promoter Pledge Released"),
    (["rights issue", "rights offering"],                            -5,  "Rights Issue (Dilution)"),
    (["rating downgrade", "credit downgrade", "downgraded to"],      -7,  "Credit Downgrade"),
    (["rating upgrade", "credit upgrade", "upgraded to"],            +6,  "Credit Upgrade"),

    # ── Tier B: Business events (medium signal) ───────────────────────────────
    (["order win", "order received", "new order", "large order", "major order", "order intake"], +7, "Order Win"),
    (["capex", "capital expenditure", "new plant", "greenfield", "brownfield expansion"],        +5, "Capex/Expansion"),
    (["acquisition", "acquires", "acquire", "takeover"],             +4,  "Acquisition"),
    (["divestment", "stake sale", "divest", "sell stake"],           +4,  "Asset Divestment"),
    (["joint venture", "jv with", "strategic partnership"],          +4,  "JV/Partnership"),
    (["debt repaid", "debt free", "zero debt", "repayment of loan"], +5,  "Debt Reduction"),
    (["debt restructuring", "restructuring of debt"],                -4,  "Debt Restructuring"),
    (["legal proceedings", "litigation", "court order", "fir"],      -5,  "Legal/Litigation Risk"),
    (["related party", "related-party"],                             -2,  "Related Party Transaction"),
    (["net profit", "pat increase", "profit after tax up"],          +4,  "Profit Growth"),
    (["net loss", "pat decline", "revenue decline"],                 -4,  "Loss/Decline"),

    # ── Tier C: Informational (low signal) ────────────────────────────────────
    (["investor presentation", "analyst meet"],                      +2,  "Investor Relations"),
    (["con call", "concall", "earnings call"],                       +2,  "Earnings Call"),
    (["quarterly results", "financial results", "q1", "q2", "q3", "q4"], +1, "Results Filing"),
    (["esop", "esos", "esps", "employee stock"],                     +1,  "ESOP Allotment"),
    (["board meeting"],                                              +1,  "Board Meeting"),
    (["agm", "annual general meeting"],                              0,   "AGM Notice"),
    (["credit rating"],                                              0,   "Credit Rating Update"),
    (["trading window"],                                             0,   "Trading Window"),
]

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2: Category Weight
# How important is this type of event? Multiplier applied to raw score.
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_WEIGHTS = {
    # High importance: capital structure & compliance events
    "Dividend":                                              3.0,
    "Action(s) taken or orders passed":                     3.0,
    "Acquisition":                                          2.5,
    "Sale or disposal":                                     2.5,
    "Other Restructuring":                                  2.0,
    "Outcome of Board Meeting":                             2.0,
    "Credit Rating":                                        2.0,
    "Record Date":                                          1.5,

    # Medium importance: business updates
    "Analysts/Institutional Investor Meet/Con. Call Updates": 1.5,
    "Investor Presentation":                                1.5,
    "Press Release":                                        1.2,
    "Shareholders meeting":                                 1.0,
    "ESOP/ESOS/ESPS":                                       0.8,

    # Low importance: routine filings
    "General Updates":                                      0.6,
    "Updates":                                              0.6,
    "Trading Window":                                       0.3,
    "Copy of Newspaper Publication":                        0.4,
}
DEFAULT_WEIGHT = 1.0

# ─────────────────────────────────────────────────────────────────────────────
# LAYER 3: Recency Decay
# Recent events matter more. Exponential decay over time.
# ─────────────────────────────────────────────────────────────────────────────
RECENCY_HALF_LIFE_DAYS = 45  # score halves every 45 days


def _recency_weight(date_str: str) -> float:
    """Returns 1.0 for today, decays to ~0.2 at 90 days, ~0.1 at 135 days."""
    try:
        # "20-Jun-2026 18:47:50" or "20-Jun-2026"
        dt = datetime.strptime(date_str.strip()[:11], "%d-%b-%Y")
        days_old = max(0, (datetime.now() - dt).days)
        return round(math.exp(-0.693 * days_old / RECENCY_HALF_LIFE_DAYS), 3)
    except Exception:
        return 0.5  # unknown date → moderate weight


def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(headers)
        try:
            _session.get("https://www.nseindia.com", timeout=10)
        except Exception:
            pass
    return _session


def fetch_announcements(symbol: str, max_results: int = 50) -> list[dict]:
    s = _get_session()
    try:
        url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={symbol}"
        r = s.get(url, timeout=15)
        r.raise_for_status()
        return r.json()[:max_results]
    except Exception:
        return []


def score_text(text: str) -> tuple[float, list[str]]:
    """Score announcement text. Returns (raw_score, [matched_labels])."""
    text_lower = text.lower()
    total = 0.0
    matched = []
    for keywords, score, label in SCORING_RULES:
        for kw in keywords:
            if kw in text_lower:
                total += score
                matched.append(f"{label} ({'+' if score > 0 else ''}{score})")
                break
    return total, matched


def parse_announcements(symbol: str, max_results: int = 30) -> list[dict]:
    """Fetch + score announcements using weighted algorithm."""
    raw = fetch_announcements(symbol, max_results)
    parsed = []

    for ann in raw:
        category = ann.get("desc", "Other")
        text = ann.get("attchmntText", "") + " " + ann.get("desc", "")
        raw_dt = ann.get("an_dt", "")
        date = raw_dt[:11].strip() if raw_dt else ""
        pdf_url = ann.get("attchmntFile", "")
        size = ann.get("attFileSize", "")

        raw_score, matched_rules = score_text(text)
        cat_weight = CATEGORY_WEIGHTS.get(category, DEFAULT_WEIGHT)
        rec_weight = _recency_weight(date)

        # Weighted score = raw × category_importance × recency_decay
        weighted = raw_score * cat_weight * rec_weight

        # Normalise to -10..+10 display scale
        display_score = round(max(-10, min(10, weighted / 3)), 1)

        # Signal thresholds
        if display_score >= 3:
            signal, emoji = "BULLISH", "🟢"
        elif display_score <= -2:
            signal, emoji = "BEARISH", "🔴"
        else:
            signal, emoji = "NEUTRAL", "🟡"

        parsed.append({
            "date": date,
            "category": category,
            "text": ann.get("attchmntText", "")[:300],
            "raw_score": round(raw_score, 1),
            "cat_weight": round(cat_weight, 2),
            "rec_weight": round(rec_weight, 3),
            "score": display_score,         # final weighted display score
            "signal": signal,
            "emoji": emoji,
            "matched_rules": matched_rules,
            "pdf_url": pdf_url,
            "size": size,
        })

    return parsed


def summarize_announcements(parsed: list[dict]) -> dict:
    """
    Composite score = weighted average using category_weight × recency_weight as importance.
    High-impact recent events dominate; old routine filings barely move the needle.
    """
    if not parsed:
        return {}

    # Weighted average
    weight_sum = sum(a["cat_weight"] * a["rec_weight"] for a in parsed)
    if weight_sum > 0:
        composite = sum(a["score"] * a["cat_weight"] * a["rec_weight"] for a in parsed) / weight_sum
    else:
        composite = 0.0
    composite = round(composite, 2)

    bullish = [a for a in parsed if a["signal"] == "BULLISH"]
    bearish = [a for a in parsed if a["signal"] == "BEARISH"]
    neutral = [a for a in parsed if a["signal"] == "NEUTRAL"]

    # Momentum: bullish/bearish events in last 30 days vs older
    recent_cutoff = datetime.now() - timedelta(days=30)
    recent_bull = sum(1 for a in bullish if _recency_weight(a["date"]) > 0.63)
    recent_bear = sum(1 for a in bearish if _recency_weight(a["date"]) > 0.63)
    momentum = "↑ Accelerating" if recent_bull > recent_bear + 1 \
               else "↓ Deteriorating" if recent_bear > recent_bull + 1 \
               else "→ Stable"

    # Signal thresholds (tighter than per-event)
    if composite >= 2.5:
        overall_signal = "STRONG BULLISH"
        overall_emoji = "🟢🟢"
    elif composite >= 1.0:
        overall_signal = "BULLISH"
        overall_emoji = "🟢"
    elif composite <= -2.0:
        overall_signal = "STRONG BEARISH"
        overall_emoji = "🔴🔴"
    elif composite <= -0.8:
        overall_signal = "BEARISH"
        overall_emoji = "🔴"
    else:
        overall_signal = "NEUTRAL"
        overall_emoji = "🟡"

    categories = {}
    for a in parsed:
        categories[a["category"]] = categories.get(a["category"], 0) + 1

    return {
        "total": len(parsed),
        "bullish_count": len(bullish),
        "bearish_count": len(bearish),
        "neutral_count": len(neutral),
        "composite_score": composite,
        "avg_score": composite,          # kept for backward compat with app.py gauge
        "overall_signal": overall_signal,
        "overall_emoji": overall_emoji,
        "momentum": momentum,
        "recent_bullish_30d": recent_bull,
        "recent_bearish_30d": recent_bear,
        "top_categories": sorted(categories.items(), key=lambda x: -x[1])[:6],
        "recent_bullish": sorted(bullish, key=lambda x: -x["score"])[:3],
        "recent_bearish": sorted(bearish, key=lambda x: x["score"])[:3],
    }
