import streamlit as st
import io
import calendar as cal_lib
from datetime import datetime as dt_lib
from collections import Counter
import plotly.graph_objects as go
from streamlit_searchbox import st_searchbox
from analyzer import analyze_concall, extract_text_from_pdf
from bse_fetcher import fetch_concall_documents, fetch_all_recent_announcements, download_pdf_from_url
from nse_symbols import search_companies, _load_nse_equity_list
from announcement_parser import parse_announcements, summarize_announcements
from social_intel import fetch_all_news, extract_mentions, get_trending_themes
from event_calendar import fetch_events_for_month, group_by_day, EVENT_COLORS

st.set_page_config(
    page_title="Concall Analyzer",
    page_icon="📊",
    layout="wide"
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ── */
html,body,[class*="css"]{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif!important}
.stApp,.main,section[data-testid="stMain"]{background:#F9FAFB!important}
.block-container{padding:1.5rem 2rem 3rem 2rem!important;max-width:1400px!important}

/* ── Navbar header ── */
.ca-nav{display:flex;align-items:center;gap:16px;background:#fff;border:1px solid #E5E7EB;
        border-radius:12px;padding:12px 18px;margin-bottom:20px}
.ca-logo{display:flex;align-items:center;gap:8px;font-size:16px;font-weight:700;color:#111827;margin-right:auto}
.ca-logo-icon{width:30px;height:30px;background:#6C63FF;border-radius:8px;display:flex;
              align-items:center;justify-content:center;font-size:16px;line-height:1}
.ca-live{display:flex;align-items:center;gap:5px;font-size:12px;color:#6B7280;
         background:#F0FDF4;border:1px solid #BBF7D0;padding:4px 10px;border-radius:20px}
.ca-live-dot{width:6px;height:6px;background:#10B981;border-radius:50%}

/* ── Cards ── */
.ca-card{background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:16px 18px;margin-bottom:12px}
.ca-card-title{font-size:11px!important;font-weight:700!important;color:#6B7280!important;
               text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}
.ca-verdict{border-radius:10px;padding:12px 16px;margin-bottom:16px;border-left:4px solid}
.ca-verdict.buy{background:#F0FDF4;border-color:#10B981}
.ca-verdict.sell{background:#FEF2F2;border-color:#EF4444}
.ca-verdict.hold{background:#FFFBEB;border-color:#F59E0B}
.ca-verdict-tag{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px}
.ca-verdict-tag.buy{color:#059669}
.ca-verdict-tag.sell{color:#DC2626}
.ca-verdict-tag.hold{color:#D97706}
.ca-verdict-text{font-size:14px;font-weight:600;color:#111827;line-height:1.5}
.ca-metric-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:14px}
.ca-metric{background:#fff;border:1px solid #E5E7EB;border-radius:10px;padding:12px 14px}
.ca-metric-label{font-size:10px;font-weight:700;color:#6B7280;text-transform:uppercase;
                 letter-spacing:.06em;margin-bottom:4px}
.ca-metric-value{font-size:18px;font-weight:700;color:#111827;line-height:1.2}
.ca-metric-sub{font-size:11px;margin-top:3px}
.ca-metric-sub.up{color:#059669}.ca-metric-sub.dn{color:#DC2626}.ca-metric-sub.neu{color:#6B7280}
.ca-two-col{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.ca-fin-row{display:flex;justify-content:space-between;align-items:baseline;
            padding:6px 0;border-bottom:1px solid #F3F4F6;font-size:13px}
.ca-fin-row:last-child{border:none}
.ca-fin-label{color:#6B7280}.ca-fin-val{font-weight:600;color:#111827}
.ca-fin-delta{font-size:11px;margin-left:4px}
.ca-fin-delta.up{color:#059669}.ca-fin-delta.dn{color:#DC2626}
.ca-tag{display:inline-block;font-size:11px;font-weight:600;padding:3px 9px;
        border-radius:20px;margin:2px 3px 2px 0}
.ca-tag.green{background:#DCFCE7;color:#15803D}
.ca-tag.red{background:#FEE2E2;color:#B91C1C}
.ca-tag.yellow{background:#FEF9C3;color:#A16207}
.ca-tag.blue{background:#DBEAFE;color:#1D4ED8}
.ca-tag.purple{background:#EDE9FE;color:#6D28D9}
.ca-tag.gray{background:#F3F4F6;color:#374151}
.ca-qa-item{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-bottom:1px solid #F3F4F6}
.ca-qa-item:last-child{border:none}
.ca-qa-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:4px}
.ca-qa-q{font-size:12px;color:#6B7280;margin-bottom:2px}
.ca-qa-a{font-size:13px;font-weight:500;color:#111827;font-style:italic;line-height:1.5}
.ca-badge{font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;margin-left:auto;
          flex-shrink:0;text-transform:uppercase;letter-spacing:.04em}
.ca-badge.clear{background:#DCFCE7;color:#15803D}
.ca-badge.vague{background:#FEF9C3;color:#A16207}
.ca-badge.deflect{background:#FEE2E2;color:#B91C1C}
.ca-badge.strong{background:#EDE9FE;color:#6D28D9}
.ca-section-head{font-size:12px!important;font-weight:700!important;color:#374151!important;
                 display:flex;align-items:center;gap:6px;margin:14px 0 8px 0;
                 padding-bottom:6px;border-bottom:1px solid #E5E7EB}
.ca-rec{display:inline-block;font-size:18px;font-weight:800;padding:6px 20px;border-radius:10px;margin-top:8px}
.ca-rec.buy{background:#DCFCE7;color:#15803D}
.ca-rec.sell{background:#FEE2E2;color:#B91C1C}
.ca-rec.hold{background:#FEF9C3;color:#A16207}
.ca-rec.accumulate{background:#DBEAFE;color:#1D4ED8}
.ca-rec.reduce{background:#FFEDD5;color:#C2410C}

/* ── Metrics (Streamlit native) ── */
[data-testid="metric-container"]{background:#fff!important;border:1px solid #E5E7EB!important;
    border-radius:10px!important;padding:.85rem 1rem!important}
[data-testid="stMetricLabel"] p{font-size:.7rem!important;font-weight:700!important;
    color:#6B7280!important;text-transform:uppercase!important;letter-spacing:.06em!important}
[data-testid="stMetricValue"]{font-size:1.25rem!important;font-weight:700!important;
    color:#111827!important;word-break:break-word!important}

/* ── Tabs ── */
[data-baseweb="tab"] p{font-size:.9rem!important;font-weight:600!important;color:#6B7280!important}
[aria-selected="true"] p{color:#6C63FF!important}
[data-baseweb="tab-list"]{border-bottom:2px solid #E5E7EB!important}

/* ── Expanders ── */
details summary{font-size:.88rem!important;font-weight:600!important;color:#111827!important;
    white-space:normal!important;word-break:break-word!important}

/* ── Alerts ── */
[data-testid="stAlert"] p{font-size:.88rem!important;line-height:1.6!important;color:inherit!important}

/* ── Captions ── */
[data-testid="stCaptionContainer"] p{font-size:.78rem!important;color:#9CA3AF!important}

/* ── Sidebar ── */
[data-testid="stSidebar"]{background:#fff!important;border-right:1px solid #E5E7EB!important}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] li{font-size:.86rem!important;
    color:#374151!important;line-height:1.7!important}

/* ── Buttons ── */
button[kind="primary"]{background:#6C63FF!important;color:#fff!important;
    border:none!important;border-radius:8px!important;font-weight:600!important}

/* ── Inputs ── */
input,textarea,select{font-size:.9rem!important;color:#111827!important}

/* ── Global ── */
*{overflow-wrap:break-word!important;word-break:break-word!important}
hr{border-color:#E5E7EB!important;margin:1rem 0!important}
</style>
""", unsafe_allow_html=True)

# ── App header ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ca-nav">
  <div class="ca-logo">
    <div class="ca-logo-icon">📊</div>
    ConcallAnalyser
  </div>
  <span style="font-size:12px;color:#9CA3AF;">NSE · BSE · AI-Powered Investment Intelligence</span>
  <div class="ca-live">
    <div class="ca-live-dot"></div>
    NSE Live
  </div>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("""
<div style="text-align:center;padding:12px 0 16px">
  <div style="font-size:24px;font-weight:800;color:#111827">📊</div>
  <div style="font-size:14px;font-weight:700;color:#111827;margin-top:4px">ConcallAnalyser</div>
  <div style="font-size:11px;color:#9CA3AF;margin-top:2px">India's AI Finance Tool</div>
</div>
""", unsafe_allow_html=True)
    st.divider()
    st.markdown("**Navigate**")
    st.markdown("""
- 📊 **Concall Analyzer** — Search NSE or upload PDF
- 🏛️ **Corporate Intelligence** — Announcements + Calendar
- 📡 **Market Buzz** — Live news mentions
""")
    st.divider()
    st.markdown("**Quick tips**")
    st.markdown("""
- Type 2+ letters to search 2000+ companies
- ZOMATO → auto-resolves to ETERNAL
- Analysis takes 15–30 seconds
- Export raw JSON from any analysis
""")
    st.divider()
    st.markdown("""
<div style="font-size:11px;color:#9CA3AF;line-height:1.8;text-align:center">
  Powered by Groq · Llama 3.3 70B<br>
  Data: NSE · Screener.in · ET Markets
</div>
""", unsafe_allow_html=True)


def _val(v, fallback="Not mentioned"):
    if v is None or v == "" or v == []:
        return fallback
    return v


def _tag(text: str, color: str = "gray") -> str:
    return f'<span class="ca-tag {color}">{text}</span>'


def _fin_row(label: str, value: str, delta: str = "", delta_up: bool = True) -> str:
    dc = "up" if delta_up else "dn"
    dhtml = f'<span class="ca-fin-delta {dc}">{delta}</span>' if delta else ""
    return f'<div class="ca-fin-row"><span class="ca-fin-label">{label}</span><span class="ca-fin-val">{value} {dhtml}</span></div>'


def render_analysis(result: dict):
    if "error" in result:
        st.error(f"Analysis error: {result['error']}")
        st.code(result.get("raw", ""))
        return

    hv    = result.get("headline_verdict", result)
    mgmt  = result.get("management_assessment", {}) or {}
    fin   = result.get("financials_reported", {}) or {}
    guid  = result.get("guidance", {}) or {}
    themes = result.get("key_themes", {}) or {}
    segs  = result.get("segment_analysis", []) or []
    qa    = result.get("analyst_qa_highlights", []) or []
    comp  = result.get("competitive_landscape", {}) or {}
    out   = result.get("outlook_summary", {}) or {}
    inv   = result.get("investor_summary", {}) or {}

    signal    = hv.get("intraday_signal", result.get("intraday_signal", "HOLD")) or "HOLD"
    sentiment = hv.get("overall_sentiment", result.get("overall_sentiment", "NEUTRAL")) or "NEUTRAL"
    score     = hv.get("sentiment_score", result.get("sentiment_score", 0)) or 0
    confidence = hv.get("signal_confidence", "MEDIUM") or "MEDIUM"
    verdict   = hv.get("one_line_verdict") or hv.get("signal_reasoning") or result.get("signal_reasoning", "")
    rec       = inv.get("recommendation", signal) or signal
    tone      = mgmt.get("tone", "N/A") or "N/A"
    cred      = mgmt.get("credibility_score", "?")

    sig_cls = {"BUY":"buy","ACCUMULATE":"buy","SELL":"sell","REDUCE":"sell","AVOID":"sell","HOLD":"hold"}.get(signal,"hold")
    rec_cls = {"BUY":"buy","ACCUMULATE":"accumulate","SELL":"sell","REDUCE":"reduce","AVOID":"sell","HOLD":"hold"}.get(rec,"hold")

    # ── VERDICT BANNER ────────────────────────────────────────────────────────
    st.markdown(f"""
<div class="ca-verdict {sig_cls}">
  <div class="ca-verdict-tag {sig_cls}">{sentiment} &nbsp;·&nbsp; {signal} &nbsp;·&nbsp; Confidence: {confidence}</div>
  <div class="ca-verdict-text">{verdict}</div>
</div>""", unsafe_allow_html=True)

    # ── 5 METRIC CARDS ────────────────────────────────────────────────────────
    try: score_f = float(score)
    except: score_f = 0
    score_color = "#059669" if score_f >= 3 else "#DC2626" if score_f <= -2 else "#D97706"
    sent_sub = {"BULLISH":"up","BEARISH":"dn","NEUTRAL":"neu"}.get(sentiment,"neu")

    st.markdown(f"""
<div class="ca-metric-grid">
  <div class="ca-metric">
    <div class="ca-metric-label">Signal</div>
    <div class="ca-metric-value" style="color:{score_color}">{signal}</div>
    <div class="ca-metric-sub {sent_sub}">{sentiment}</div>
  </div>
  <div class="ca-metric">
    <div class="ca-metric-label">Sentiment Score</div>
    <div class="ca-metric-value" style="color:{score_color}">{score_f:+.1f}</div>
    <div class="ca-metric-sub neu">out of ±10</div>
  </div>
  <div class="ca-metric">
    <div class="ca-metric-label">Mgmt Tone</div>
    <div class="ca-metric-value" style="font-size:15px">{tone}</div>
    <div class="ca-metric-sub neu">Credibility: {cred}/10</div>
  </div>
  <div class="ca-metric">
    <div class="ca-metric-label">Revenue</div>
    <div class="ca-metric-value" style="font-size:15px">{_val(fin.get("revenue"),"—")}</div>
    <div class="ca-metric-sub up">{_val(fin.get("revenue_growth_yoy"),"")}</div>
  </div>
  <div class="ca-metric">
    <div class="ca-metric-label">EBITDA Margin</div>
    <div class="ca-metric-value" style="font-size:15px">{_val(fin.get("ebitda_margin"),"—")}</div>
    <div class="ca-metric-sub up">{_val(fin.get("ebitda_margin_change"),"")}</div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── ROW 1: POSITIVES + FINANCIALS ─────────────────────────────────────────
    col_a, col_b = st.columns([1, 1])

    with col_a:
        positives = themes.get("positives", result.get("key_positives", []))
        pos_tags = "".join(_tag(p[:60], "green") for p in positives[:5])
        tailwinds = themes.get("tailwinds", [])
        tw_tags = "".join(_tag(t[:50], "blue") for t in tailwinds[:3])

        risks = themes.get("risks", result.get("key_risks", []))
        risk_tags = "".join(_tag(r[:60], "red") for r in risks[:4])
        headwinds = themes.get("headwinds", [])
        hw_tags = "".join(_tag(h[:50], "yellow") for h in headwinds[:3])

        red_flags = themes.get("red_flags", result.get("red_flags", []))
        rf_html = ""
        if red_flags:
            rf_tags = "".join(_tag(f[:60], "red") for f in red_flags[:3])
            rf_html = f'<div class="ca-section-head">🚩 Red Flags</div>{rf_tags}'

        st.markdown(f"""
<div class="ca-card">
  <div class="ca-section-head">✅ Key Positives {("& Tailwinds" if tailwinds else "")}</div>
  {pos_tags}{tw_tags}
  <div class="ca-section-head" style="margin-top:14px">⚠️ Risks {("& Headwinds" if headwinds else "")}</div>
  {risk_tags}{hw_tags}
  {rf_html}
</div>""", unsafe_allow_html=True)

    with col_b:
        rows = ""
        pairs = [
            ("Revenue", fin.get("revenue"), fin.get("revenue_growth_yoy")),
            ("EBITDA",  fin.get("ebitda"),  fin.get("ebitda_margin")),
            ("PAT",     fin.get("pat"),      fin.get("pat_growth_yoy")),
            ("Debt",    fin.get("debt_level"), fin.get("cash_and_equivalents") and f"Cash: {fin.get('cash_and_equivalents')}"),
            ("Capex",   fin.get("capex"),    fin.get("order_book") and f"OB: {fin.get('order_book')}"),
        ]
        for label, val, delta in pairs:
            if val:
                is_up = delta and any(c in str(delta) for c in ["+", "↑", "up", "Up"])
                rows += _fin_row(label, str(val), str(delta) if delta else "", is_up)

        st.markdown(f"""
<div class="ca-card">
  <div class="ca-section-head">💰 Financials Reported</div>
  {rows if rows else "<p style='color:#9CA3AF;font-size:13px'>No financial data extracted</p>"}
</div>""", unsafe_allow_html=True)

    # ── ROW 2: GUIDANCE + MANAGEMENT ──────────────────────────────────────────
    col_c, col_d = st.columns([1, 1])

    with col_c:
        changed_html = ""
        if guid.get("guidance_changed"):
            changed_html = f'<div class="ca-tag yellow" style="margin-bottom:8px">⚠️ Guidance revised</div><p style="font-size:12px;color:#374151">{_val(guid.get("guidance_change_detail"))}</p>'
        g_rows = ""
        g_pairs = [
            ("Revenue", guid.get("revenue_guidance")),
            ("Margin",  guid.get("margin_guidance")),
            ("Growth",  guid.get("growth_guidance")),
            ("Capex",   guid.get("capex_guidance")),
            ("Hiring",  guid.get("hiring_guidance")),
            ("Dividend",guid.get("dividend_guidance")),
        ]
        for label, val in g_pairs:
            if val:
                g_rows += f'<div class="ca-fin-row"><span class="ca-fin-label">{label}</span><span class="ca-fin-val">{val}</span></div>'

        st.markdown(f"""
<div class="ca-card">
  <div class="ca-section-head">🔭 Management Guidance</div>
  {changed_html}
  {g_rows if g_rows else "<p style='color:#9CA3AF;font-size:13px'>No guidance mentioned</p>"}
</div>""", unsafe_allow_html=True)

    with col_d:
        speakers = "".join(f'<div class="ca-tag gray">{s}</div>' for s in mgmt.get("key_speakers", [])[:4])
        stmts_html = "".join(
            f'<div style="font-size:12px;font-style:italic;color:#374151;padding:5px 0;border-bottom:1px solid #F3F4F6">'
            f'&ldquo;{s[:120]}&rdquo;</div>'
            for s in mgmt.get("strong_statements", [])[:3]
        )
        evasive = "".join(f'<div class="ca-tag yellow">{q[:70]}</div>' for q in mgmt.get("evasive_questions", [])[:3])

        st.markdown(f"""
<div class="ca-card">
  <div class="ca-section-head">🎙️ Management Assessment</div>
  <div style="font-size:13px;margin-bottom:8px">
    <strong>Tone:</strong> {tone} &nbsp;&nbsp; <strong>Credibility:</strong> {cred}/10
  </div>
  <p style="font-size:12px;color:#6B7280;margin-bottom:8px">{_val(mgmt.get("tone_reasoning"))}</p>
  {('<div style="margin-bottom:6px">' + speakers + '</div>') if speakers else ""}
  {stmts_html}
  {('<div class="ca-section-head" style="margin-top:8px">Questions dodged</div>' + evasive) if evasive else ""}
</div>""", unsafe_allow_html=True)

    # ── ANALYST Q&A ───────────────────────────────────────────────────────────
    if qa:
        qa_html = ""
        badge_map = {"Clear":"clear","Strong":"strong","Vague":"vague","Deflected":"deflect"}
        dot_color = {"Clear":"#10B981","Strong":"#6C63FF","Vague":"#F59E0B","Deflected":"#EF4444"}
        for item in qa[:6]:
            quality = item.get("management_answer_quality","")
            firm = item.get("analyst_firm","Analyst") or "Analyst"
            topic = item.get("question_topic","") or ""
            tkaway = item.get("key_takeaway","") or ""
            bc = badge_map.get(quality,"vague")
            dc = dot_color.get(quality,"#9CA3AF")
            qa_html += f"""
<div class="ca-qa-item">
  <div class="ca-qa-dot" style="background:{dc}"></div>
  <div style="flex:1">
    <div class="ca-qa-q">{firm} — {topic[:70]}</div>
    <div class="ca-qa-a">{tkaway[:150]}</div>
  </div>
  <span class="ca-badge {bc}">{quality}</span>
</div>"""
        st.markdown(f'<div class="ca-card"><div class="ca-section-head">❓ Analyst Q&A Highlights</div>{qa_html}</div>', unsafe_allow_html=True)

    # ── SEGMENTS (expanders, less visual weight) ───────────────────────────────
    if segs:
        with st.expander(f"📦 Segment Analysis — {len(segs)} segments"):
            for seg in segs:
                sc1, sc2 = st.columns([1, 2])
                sc1.metric(seg.get("segment_name","Segment"), _val(seg.get("revenue")))
                sc2.write(_val(seg.get("outlook")))

    # ── OUTLOOK ───────────────────────────────────────────────────────────────
    mon_tags = "".join(_tag(m[:60],"blue") for m in out.get("key_monitorables",[])[:4])
    cat_tags = "".join(_tag(c[:60],"green") for c in out.get("catalysts",[])[:3])
    rsk_tags = "".join(_tag(r[:60],"red") for r in out.get("risks_to_watch",[])[:3])
    short_t = _val(out.get("short_term_1q"))
    long_t  = _val(out.get("medium_term_1y"))

    st.markdown(f"""
<div class="ca-card">
  <div class="ca-section-head">🔮 Outlook & Monitorables</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
    <div>
      <div style="font-size:11px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Next Quarter</div>
      <p style="font-size:13px;color:#374151;margin-bottom:10px">{short_t}</p>
      <div style="font-size:11px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">1-Year View</div>
      <p style="font-size:13px;color:#374151">{long_t}</p>
    </div>
    <div>
      <div style="font-size:11px;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">Watch List</div>
      {mon_tags}
      <div style="font-size:11px;font-weight:700;color:#059669;text-transform:uppercase;letter-spacing:.05em;margin:8px 0 4px">Catalysts</div>
      {cat_tags if cat_tags else '<span style="font-size:12px;color:#9CA3AF">None mentioned</span>'}
      <div style="font-size:11px;font-weight:700;color:#DC2626;text-transform:uppercase;letter-spacing:.05em;margin:8px 0 4px">Downside Risks</div>
      {rsk_tags if rsk_tags else '<span style="font-size:12px;color:#9CA3AF">None mentioned</span>'}
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── INVESTOR SUMMARY + RECOMMENDATION ─────────────────────────────────────
    retail_txt  = _val(inv.get("for_retail_investor", result.get("analyst_summary","")))
    bull_txt    = _val(inv.get("buy_case"))
    bear_txt    = _val(inv.get("sell_case"))
    tp_txt      = inv.get("target_price_mentioned","")

    st.markdown(f"""
<div class="ca-card">
  <div class="ca-section-head">📝 Investor Summary</div>
  <p style="font-size:13px;color:#374151;margin-bottom:14px">{retail_txt}</p>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
    <div style="background:#F0FDF4;border-radius:8px;padding:12px">
      <div style="font-size:11px;font-weight:700;color:#059669;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Bull Case</div>
      <p style="font-size:12px;color:#15803D;margin:0">{bull_txt}</p>
    </div>
    <div style="background:#FEF2F2;border-radius:8px;padding:12px">
      <div style="font-size:11px;font-weight:700;color:#DC2626;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Bear Case</div>
      <p style="font-size:12px;color:#B91C1C;margin:0">{bear_txt}</p>
    </div>
  </div>
  {f'<p style="font-size:12px;color:#6B7280;margin-bottom:10px">Analyst target prices: {tp_txt}</p>' if tp_txt else ""}
  <div>
    <span style="font-size:12px;color:#6B7280;margin-right:8px">Final Recommendation</span>
    <span class="ca-rec {rec_cls}">{rec}</span>
  </div>
</div>""", unsafe_allow_html=True)

    with st.expander("🔧 View Raw Analysis JSON"):
        st.json(result)


@st.cache_data(show_spinner="Loading NSE company list...")
def load_all_companies():
    return _load_nse_equity_list()


def search_nse(query: str) -> list[str]:
    """Returns list of 'Company Name (SYMBOL)' strings for searchbox."""
    if not query or len(query.strip()) < 1:
        return []
    results = search_companies(query, max_results=12)
    return [f"{r['name']}  ({r['symbol']})" for r in results]


# ---- TABS ----
tab1, tab2, tab3 = st.tabs(["📊 Concall Analyzer", "🏛️ Corporate Intelligence", "📡 Market Buzz"])


# ======== TAB 1: CONCALL ANALYZER ========
with tab1:
    mode = st.radio(
        "How would you like to load the concall?",
        ["🔎 Search NSE (auto-fetch)", "📤 Upload PDF manually"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.divider()

    if mode == "🔎 Search NSE (auto-fetch)":
        st.caption("Type company name or NSE symbol — live suggestions from 2000+ listed companies")
        load_all_companies()

        selected_label = st_searchbox(
            search_nse,
            placeholder="e.g. Infosys, HDFC Bank, RELIANCE, TCS...",
            key="nse_searchbox",
            label="Search NSE Company",
            clear_on_submit=False,
        )

        if selected_label:
            symbol_part = selected_label.strip().rsplit("(", 1)
            selected_symbol = symbol_part[-1].replace(")", "").strip() if len(symbol_part) > 1 else selected_label.strip()
            company_display = symbol_part[0].strip() if len(symbol_part) > 1 else selected_label.strip()
            st.info(f"Selected: **{company_display}** | Symbol: `{selected_symbol}`")

            if st.button("📂 Fetch Documents", use_container_width=True, type="primary"):
                with st.spinner(f"Fetching documents for {selected_symbol} — trying all sources..."):
                    docs, source_used = fetch_concall_documents(selected_symbol, max_results=30)
                    st.session_state["docs"] = docs
                    st.session_state["doc_source"] = source_used
                    st.session_state["company_display"] = company_display

        if "docs" in st.session_state:
            docs = st.session_state["docs"]
            company_display = st.session_state.get("company_display", "")
            doc_source = st.session_state.get("doc_source", "")

            if not docs:
                st.error(f"""
**No documents found for {company_display} across all sources.**

All 3 sources tried: NSE API → NSE alias → Screener.in

Try uploading the PDF manually using the toggle above, or:
- Google: `{company_display} concall transcript PDF site:nsearchives.nseindia.com`
                """)
            else:
                source_badge = {"NSE": "🟢 NSE API", "Screener.in": "🟡 Screener.in (fallback)"}.get(
                    doc_source.split(" ")[0], f"🔵 {doc_source}")
                st.success(f"Found **{len(docs)} documents** for {company_display} · Source: {source_badge}")

                def _doc_label(d, i):
                    date = d.get("date", "")
                    title = d.get("title", "")
                    desc = d.get("description", "")[:60]
                    label = f"{date} — {title}"
                    if desc and desc.lower() not in title.lower():
                        label += f" · {desc}"
                    return label[:120]

                doc_options = {_doc_label(d, i): i for i, d in enumerate(docs)}
                selected_doc_label = st.selectbox("Select document to analyze", list(doc_options.keys()))
                selected_idx = doc_options[selected_doc_label]
                selected_doc = docs[selected_idx]

                d_col1, d_col2 = st.columns([3, 1])
                with d_col1:
                    st.caption(f"📄 {selected_doc['pdf_url']}")
                with d_col2:
                    if selected_doc.get("size"):
                        st.caption(f"Size: {selected_doc['size']}")

                if st.button("🔍 Download & Analyze", type="primary", use_container_width=True):
                    with st.spinner("Downloading PDF from NSE..."):
                        try:
                            pdf_bytes = download_pdf_from_url(selected_doc["pdf_url"])
                            pdf_file = io.BytesIO(pdf_bytes)
                            text = extract_text_from_pdf(pdf_file)
                            word_count = len(text.split())
                            if word_count < 100:
                                st.warning(f"Only {word_count} words — may be image-based PDF.")
                            else:
                                st.success(f"PDF downloaded: {word_count:,} words extracted")
                        except Exception as e:
                            st.error(f"Download failed: {e}. Switch to upload mode above.")
                            st.stop()
                    with st.spinner("Analyzing with AI (15–30 seconds)..."):
                        result = analyze_concall(text, company_display)
                    render_analysis(result)

    else:  # Upload PDF manually
        st.caption("Upload any concall/AGM/analyst meet PDF from BSE, NSE, or broker research")
        company_name = st.text_input("Company Name", placeholder="e.g. Reliance Industries", key="manual_company")
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"],
                                         help="NSE/BSE concall transcripts, broker research PDFs")
        if uploaded_file and company_name:
            if st.button("🔍 Analyze", type="primary", use_container_width=True):
                with st.spinner("Reading PDF..."):
                    text = extract_text_from_pdf(uploaded_file)
                    st.success(f"PDF read: {len(text.split()):,} words extracted")
                with st.spinner("Analyzing with AI..."):
                    result = analyze_concall(text, company_name)
                render_analysis(result)
        elif uploaded_file and not company_name:
            st.warning("Enter company name first.")
        elif company_name and not uploaded_file:
            st.info("Upload a PDF to begin.")


# ======== TAB 2: CORPORATE INTELLIGENCE ========
with tab2:
    corp_section = st.radio(
        "Section",
        ["📢 Announcement Scorer", "📅 Event Calendar"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.divider()

    if corp_section == "📢 Announcement Scorer":
        st.subheader("📢 AGM & Corporate Announcement Analyser")
        st.caption("Fetch all NSE announcements for any company — scored BULLISH / BEARISH / NEUTRAL automatically")

    load_all_companies()

    ann_selected = st_searchbox(
        search_nse,
        placeholder="Search company — e.g. Infosys, HDFC Bank, TCS...",
        key="ann_searchbox",
        label="Search NSE Company",
        clear_on_submit=False,
    )

    if ann_selected:
        sym_part = ann_selected.strip().rsplit("(", 1)
        ann_symbol = sym_part[-1].replace(")", "").strip() if len(sym_part) > 1 else ann_selected.strip()
        ann_company = sym_part[0].strip() if len(sym_part) > 1 else ann_selected.strip()

        col_l, col_r = st.columns([2, 1])
        with col_l:
            st.info(f"Selected: **{ann_company}** | `{ann_symbol}`")
        with col_r:
            max_ann = st.selectbox("Announcements to fetch", [20, 50, 100], index=1, key="ann_count")

        if st.button("📥 Fetch & Score Announcements", type="primary", use_container_width=True):
            with st.spinner(f"Fetching announcements for {ann_symbol}..."):
                parsed = parse_announcements(ann_symbol, max_ann)
                summary = summarize_announcements(parsed)
                st.session_state["ann_parsed"] = parsed
                st.session_state["ann_summary"] = summary
                st.session_state["ann_company"] = ann_company

    if "ann_parsed" in st.session_state:
        parsed = st.session_state["ann_parsed"]
        summary = st.session_state["ann_summary"]
        company_label = st.session_state.get("ann_company", "")

        if not parsed:
            st.warning("No announcements found.")
        else:
            # ── SUMMARY METRICS ────────────────────────────────────────────────
            st.divider()
            overall = summary.get("overall_signal", "NEUTRAL")
            overall_emoji = summary.get("overall_emoji", "🟡")
            momentum = summary.get("momentum", "→ Stable")
            composite = summary.get("composite_score", 0)

            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Overall Signal", f"{overall_emoji} {overall}")
            c2.metric("Composite Score", f"{composite:+.2f}")
            c3.metric("Momentum (30d)", momentum)
            c4.metric("🟢 Bullish", f"{summary.get('bullish_count',0)} ({summary.get('recent_bullish_30d',0)} recent)")
            c5.metric("🔴 Bearish", f"{summary.get('bearish_count',0)} ({summary.get('recent_bearish_30d',0)} recent)")
            c6.metric("Scanned", summary.get("total", 0))

            with st.expander("ℹ️ How this score is calculated"):
                st.markdown("""
**Algorithm: 3-Layer Weighted Average**

```
Composite = Σ(raw_score × category_weight × recency_weight)
            ─────────────────────────────────────────────────
               Σ(category_weight × recency_weight)
```

| Layer | What it measures | Range |
|-------|-----------------|-------|
| **Raw Score** | Keyword match on announcement text | -10 to +10 |
| **Category Weight** | Dividend/Acquisition = 3×, Routine filings = 0.3× | 0.3× – 3.0× |
| **Recency Decay** | Today = 1.0×, 45 days ago = 0.5×, 90 days = 0.25× | 0.1× – 1.0× |

A buyback from last week scores far higher than an AGM notice from 3 months ago.
                """)

            # ── GAUGE ──────────────────────────────────────────────────────────
            avg = summary.get("avg_score", 0)
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=avg,
                number={"suffix": "/10", "font": {"size": 28}},
                domain={"x": [0, 1], "y": [0, 1]},
                title={"text": f"Announcement Sentiment — {company_label}"},
                gauge={
                    "axis": {"range": [-10, 10]},
                    "bar": {"color": "#6C63FF"},
                    "steps": [
                        {"range": [-10, -3], "color": "#fee2e2"},
                        {"range": [-3, 3], "color": "#fef9c3"},
                        {"range": [3, 10], "color": "#dcfce7"},
                    ],
                }
            ))
            fig.update_layout(height=220, margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)

            # ── CATEGORY BREAKDOWN ─────────────────────────────────────────────
            st.subheader("📊 Announcement Categories")
            cat_data = summary.get("top_categories", [])
            if cat_data:
                cats, counts = zip(*cat_data)
                fig2 = go.Figure(go.Bar(
                    x=list(counts), y=list(cats),
                    orientation="h",
                    marker_color="#6C63FF",
                ))
                fig2.update_layout(height=220, margin=dict(t=10, b=10, l=10, r=10),
                                   xaxis_title="Count", yaxis={"autorange": "reversed"})
                st.plotly_chart(fig2, use_container_width=True)

            # ── HIGHLIGHTS ────────────────────────────────────────────────────
            col_bull, col_bear = st.columns(2)
            with col_bull:
                st.subheader("🟢 Recent Bullish Events")
                for a in summary.get("recent_bullish", []):
                    with st.container(border=True):
                        st.markdown(f"**{a['date']} — {a['category']}** | Score: `{a['score']:+}`")
                        st.caption(a["text"][:200] or "No description")
                        if a["matched_rules"]:
                            st.caption("Triggers: " + " · ".join(a["matched_rules"]))
                        if a["pdf_url"]:
                            st.markdown(f"[📄 Open Source Document ↗]({a['pdf_url']})")

            with col_bear:
                st.subheader("🔴 Recent Bearish Events")
                bearish_list = [a for a in parsed if a["signal"] == "BEARISH"]
                if bearish_list:
                    for a in bearish_list[:3]:
                        with st.container(border=True):
                            st.markdown(f"**{a['date']} — {a['category']}** | Score: `{a['score']:+}`")
                            st.caption(a["text"][:200] or "No description")
                            if a["matched_rules"]:
                                st.caption("Triggers: " + " · ".join(a["matched_rules"]))
                            if a["pdf_url"]:
                                st.markdown(f"[📄 Open Source Document ↗]({a['pdf_url']})")
                else:
                    st.success("No bearish events detected.")

            # ── FULL TABLE ────────────────────────────────────────────────────
            st.divider()
            st.subheader("📋 All Announcements")

            filter_sig = st.multiselect(
                "Filter by signal",
                ["BULLISH", "NEUTRAL", "BEARISH"],
                default=["BULLISH", "NEUTRAL", "BEARISH"],
                key="ann_filter"
            )

            for a in parsed:
                if a["signal"] not in filter_sig:
                    continue
                with st.expander(
                    f"{a['emoji']} {a['date']} — {a['category']} | Weighted Score: {a['score']:+.1f}",
                    expanded=False
                ):
                    st.write(a["text"] or "No description available.")
                    if a["matched_rules"]:
                        st.info("Signal triggers: " + " · ".join(a["matched_rules"]))
                    # Score breakdown
                    sc1, sc2, sc3 = st.columns(3)
                    sc1.caption(f"Raw score: **{a['raw_score']:+.0f}**")
                    sc2.caption(f"Category weight: **{a['cat_weight']}×**")
                    sc3.caption(f"Recency weight: **{a['rec_weight']}×**")
                    if a["pdf_url"]:
                        fc1, fc2 = st.columns([1, 3])
                        with fc1:
                            st.link_button("📄 Open NSE Filing", a["pdf_url"], use_container_width=True)
                        with fc2:
                            st.caption(f"Source: NSE Corporate Announcements · {a['size']}")
    else:
        st.markdown("""
        ### What this tab shows:
        - 📋 All corporate announcements from NSE (up to 100)
        - 🟢 Auto-scored BULLISH events: dividends, buybacks, acquisitions, order wins
        - 🔴 Auto-scored BEARISH events: pledge creation, regulatory action, defaults
        - 📊 Category breakdown chart + sentiment gauge

        **Get started:** Search a company above → Fetch & Score
        """)


# ======== TAB 3: MARKET BUZZ ========
with tab3:
    st.subheader("📡 Market Buzz — Real-Time Stock Intelligence")
    st.caption("Live stock mentions & sentiment from ET Markets, Moneycontrol, LiveMint — refreshes on every page load")

    col_refresh, col_info = st.columns([1, 3])
    with col_refresh:
        do_fetch = st.button("🔄 Refresh Now", type="primary", use_container_width=True)
    with col_info:
        st.info("Sources: Economic Times Markets · ET Stocks · Moneycontrol · LiveMint")

    if do_fetch or "buzz_mentions" not in st.session_state:
        with st.spinner("Fetching live news from 4 sources..."):
            buzz_articles = fetch_all_news()
            buzz_nse = _load_nse_equity_list()
            buzz_mentions = extract_mentions(buzz_articles, buzz_nse)
            buzz_themes = get_trending_themes(buzz_articles)
            st.session_state["buzz_articles"] = buzz_articles
            st.session_state["buzz_mentions"] = buzz_mentions
            st.session_state["buzz_themes"] = buzz_themes

    buzz_articles = st.session_state.get("buzz_articles", [])
    buzz_mentions = st.session_state.get("buzz_mentions", {})
    buzz_themes = st.session_state.get("buzz_themes", {})

    if not buzz_mentions:
        st.warning("No stock mentions found. Try refreshing.")
    else:
        st.success(f"Live: **{len(buzz_articles)} articles** scanned · **{len(buzz_mentions)} stocks** mentioned")

        # ── METRICS ────────────────────────────────────────────────────────────
        bullish_stocks = [s for s, d in buzz_mentions.items() if d["signal"] == "BULLISH"]
        bearish_stocks = [s for s, d in buzz_mentions.items() if d["signal"] == "BEARISH"]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🟢 Bullish Stocks", len(bullish_stocks))
        m2.metric("🔴 Bearish Stocks", len(bearish_stocks))
        m3.metric("📰 Articles Scanned", len(buzz_articles))
        m4.metric("🏢 Stocks Tracked", len(buzz_mentions))

        st.divider()

        # ── TRENDING SECTORS ───────────────────────────────────────────────────
        col_sector, col_stocks = st.columns([1, 2])

        with col_sector:
            st.subheader("🔥 Trending Sectors")
            if buzz_themes:
                themes_list = list(buzz_themes.items())
                sectors, sector_counts = zip(*themes_list)
                fig_sector = go.Figure(go.Bar(
                    x=list(sector_counts),
                    y=list(sectors),
                    orientation="h",
                    marker=dict(
                        color=list(sector_counts),
                        colorscale="Purples",
                        showscale=False,
                    ),
                ))
                fig_sector.update_layout(
                    height=300, margin=dict(t=10, b=10, l=10, r=10),
                    xaxis_title="Article count",
                    yaxis={"autorange": "reversed"},
                )
                st.plotly_chart(fig_sector, use_container_width=True)

        with col_stocks:
            st.subheader("📈 Most Mentioned Stocks")
            top_stocks = list(buzz_mentions.items())[:12]
            if top_stocks:
                syms = [d["symbol"] for _, d in top_stocks]
                names = [f"{d['symbol']} — {d['name'][:20]}" for _, d in top_stocks]
                counts = [d["mentions"] for _, d in top_stocks]
                colors = [
                    "#10b981" if d["signal"] == "BULLISH"
                    else "#ef4444" if d["signal"] == "BEARISH"
                    else "#f59e0b"
                    for _, d in top_stocks
                ]
                fig_stocks = go.Figure(go.Bar(
                    x=counts,
                    y=names,
                    orientation="h",
                    marker_color=colors,
                    text=[f"{d['emoji']} {d['signal']}" for _, d in top_stocks],
                    textposition="outside",
                ))
                fig_stocks.update_layout(
                    height=360, margin=dict(t=10, b=10, l=10, r=80),
                    xaxis_title="Mentions",
                    yaxis={"autorange": "reversed"},
                )
                st.plotly_chart(fig_stocks, use_container_width=True)

        st.divider()

        # ── STOCK CARDS ────────────────────────────────────────────────────────
        st.subheader("🗞️ Stock-wise News Feed")

        signal_filter = st.multiselect(
            "Filter by signal",
            ["BULLISH", "NEUTRAL", "BEARISH"],
            default=["BULLISH", "BEARISH", "NEUTRAL"],
            key="buzz_filter"
        )

        for sym, data in buzz_mentions.items():
            if data["signal"] not in signal_filter:
                continue
            with st.expander(
                f"{data['emoji']} **{sym}** — {data['name']} | {data['mentions']} mentions | {data['signal']} (avg score: {data['avg_score']:+.1f})",
                expanded=False,
            ):
                b1, b2, b3 = st.columns(3)
                b1.metric("🟢 Bullish Articles", data["buy_recs"])
                b2.metric("🔴 Bearish Articles", data["sell_recs"])
                b3.metric("🟡 Neutral Articles", data["hold_recs"])
                st.divider()
                for art in data["articles"]:
                    signal_badge = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(art["signal"], "🟡")
                    st.markdown(f"{signal_badge} **[{art['title']}]({art['link']})** — *{art['source']}*")

        # ── RAW HEADLINES ──────────────────────────────────────────────────────
        st.divider()
        with st.expander("📋 All Raw Headlines"):
            for art in buzz_articles[:40]:
                st.markdown(f"**{art['source']}** — [{art['title']}]({art['link']})")


# ======== EVENT CALENDAR — inside Tab 2 ========
with tab2:
    if corp_section == "📅 Event Calendar":

            st.subheader("📅 NSE Corporate Event Calendar")
            st.caption("Board meetings · AGMs · Results dates · Concalls · Dividends — all in one view")

            # ── Controls ──────────────────────────────────────────────────────────────
            now = dt_lib.now()
            ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([2, 2, 2, 2])
            with ctrl1:
                sel_year = st.selectbox("Year", list(range(2023, 2028)), index=list(range(2023, 2028)).index(now.year))
            with ctrl2:
                months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
                sel_month_name = st.selectbox("Month", months, index=now.month - 1)
                sel_month = months.index(sel_month_name) + 1
            with ctrl3:
                event_types = ["All"] + list(EVENT_COLORS.keys())
                filter_type = st.selectbox("Filter by type", event_types)
            with ctrl4:
                fetch_btn = st.button("📥 Load Events", type="primary", use_container_width=True)

            if fetch_btn or "cal_events" not in st.session_state or \
               st.session_state.get("cal_month") != (sel_year, sel_month):
                with st.spinner(f"Fetching NSE events for {sel_month_name} {sel_year}..."):
                    raw_events = fetch_events_for_month(sel_year, sel_month)
                    st.session_state["cal_events"] = raw_events
                    st.session_state["cal_month"] = (sel_year, sel_month)

            all_events = st.session_state.get("cal_events", [])
            events = [e for e in all_events if filter_type == "All" or e["type"] == filter_type]

            if not all_events:
                st.warning("No events found for this month. Try another month or check your connection.")
            else:
                # ── Summary strip ─────────────────────────────────────────────────────
                type_counts = Counter(e["type"] for e in all_events)
                cols = st.columns(len(EVENT_COLORS))
                for i, (etype, style) in enumerate(EVENT_COLORS.items()):
                    count = type_counts.get(etype, 0)
                    if count:
                        cols[i].markdown(
                            f"<div style='text-align:center; padding:6px 4px; background:{style['bg']}; "
                            f"border:1px solid {style['border']}; border-radius:8px; font-size:0.8rem;'>"
                            f"{style['icon']} <b>{style['tag']}</b><br><span style='font-size:1.1rem;font-weight:700'>{count}</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

                st.markdown(f"**{len(events)} events** shown · {len(all_events)} total for {sel_month_name} {sel_year}")
                st.divider()

                # ── Calendar grid ─────────────────────────────────────────────────────
                days_by_day = group_by_day(events)
                num_days = cal_lib.monthrange(sel_year, sel_month)[1]
                first_weekday = cal_lib.monthrange(sel_year, sel_month)[0]  # 0=Mon
                day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

                # Render calendar as HTML
                cal_html = """
                <style>
                .cal-grid { display: grid; grid-template-columns: repeat(7,1fr); gap: 6px; margin-top: 8px; }
                .cal-header { text-align:center; font-size:0.78rem; font-weight:700; color:#6B7280;
                              padding:6px 0; background:#F9FAFB; border-radius:6px; }
                .cal-cell { min-height:90px; border:1px solid #E5E7EB; border-radius:8px; padding:6px;
                            background:#FFFFFF; vertical-align:top; font-size:0.75rem; }
                .cal-cell.today { border-color:#6C63FF; background:#F5F3FF; }
                .cal-cell.empty { background:#FAFAFA; border:1px dashed #E5E7EB; }
                .cal-day-num { font-size:0.85rem; font-weight:700; color:#374151; margin-bottom:4px; }
                .cal-day-num.today-num { color:#6C63FF; }
                .cal-event { padding:2px 5px; border-radius:4px; margin-bottom:2px; font-size:0.7rem;
                             font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
                             cursor:pointer; border-left:3px solid; }
                .cal-more { font-size:0.68rem; color:#6B7280; margin-top:2px; }
                </style>
                <div class='cal-grid'>
                """

                # Day headers
                for d in day_names:
                    cal_html += f"<div class='cal-header'>{d}</div>"

                # Empty cells before first day
                for _ in range(first_weekday):
                    cal_html += "<div class='cal-cell empty'></div>"

                today = dt_lib.now()
                is_current_month = (sel_year == today.year and sel_month == today.month)

                for day in range(1, num_days + 1):
                    is_today = is_current_month and day == today.day
                    cell_class = "cal-cell today" if is_today else "cal-cell"
                    num_class = "cal-day-num today-num" if is_today else "cal-day-num"
                    cal_html += f"<div class='{cell_class}'><div class='{num_class}'>{day}</div>"

                    day_events = days_by_day.get(day, [])
                    show = day_events[:4]
                    rest = len(day_events) - 4

                    for ev in show:
                        bg = ev["bg"]
                        border = ev["border"]
                        icon = ev["icon"]
                        sym = ev["symbol"]
                        co = ev["company"].replace("'", "")
                        purp = ev["purpose"].replace("'", "")
                        cal_html += (
                            f"<div class='cal-event' "
                            f"style='background:{bg};border-left-color:{border};' "
                            f"title='{co} — {purp}'>"
                            f"{icon} {sym}"
                            f"</div>"
                        )
                    if rest > 0:
                        cal_html += f"<div class='cal-more'>+{rest} more</div>"

                    cal_html += "</div>"

                # Fill remaining cells
                total_cells = first_weekday + num_days
                remainder = (7 - total_cells % 7) % 7
                for _ in range(remainder):
                    cal_html += "<div class='cal-cell empty'></div>"

                cal_html += "</div>"
                st.markdown(cal_html, unsafe_allow_html=True)

                # ── Date detail view ──────────────────────────────────────────────────
                st.divider()
                st.subheader("📋 Events by Date — FIFO Order")
                st.caption("All events sorted earliest first. Click to expand details.")

                # Group and display
                current_date = None
                for ev in events:
                    if ev["date_key"] != current_date:
                        current_date = ev["date_key"]
                        st.markdown(
                            f"<div style='background:#F8F9FF;border-left:4px solid #6C63FF;"
                            f"padding:6px 12px;border-radius:4px;margin:12px 0 4px 0;"
                            f"font-weight:700;color:#1A1B3A;font-size:0.95rem;'>"
                            f"📆 {ev['display_date']}</div>",
                            unsafe_allow_html=True
                        )

                    with st.expander(
                        f"{ev['icon']} **{ev['symbol']}** — {ev['company']} | {ev['tag']} | {ev['purpose'][:60]}",
                        expanded=False
                    ):
                        ec1, ec2 = st.columns([1, 3])
                        with ec1:
                            ev_bg = ev["bg"]; ev_bd = ev["border"]
                            ev_ic = ev["icon"]; ev_tg = ev["tag"]
                            ev_ind = ev["industry"] or "N/A"
                            st.markdown(
                                f"<div style='background:{ev_bg};border:1px solid {ev_bd};"
                                f"border-radius:8px;padding:12px;text-align:center;'>"
                                f"<div style='font-size:1.8rem'>{ev_ic}</div>"
                                f"<div style='font-weight:700;color:#1A1B3A;font-size:0.9rem;'>{ev_tg}</div>"
                                f"<div style='font-size:0.75rem;color:#6B7280;margin-top:4px;'>{ev_ind}</div>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                        with ec2:
                            st.markdown(f"**Company:** {ev['company']}")
                            st.markdown(f"**NSE Symbol:** `{ev['symbol']}`")
                            st.markdown(f"**Date:** {ev['display_date']}")
                            st.markdown(f"**Event:** {ev['purpose']}")
                            st.write(ev['desc'] or "No description available.")
                            if ev["pdf_url"]:
                                st.link_button("📄 Open Filing", ev["pdf_url"])
