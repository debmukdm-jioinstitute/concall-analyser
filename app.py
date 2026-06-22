import streamlit as st
import io
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
/* ── Force light background everywhere ── */
.stApp, .main, section[data-testid="stMain"] {
    background-color: #FFFFFF !important;
}

/* ── Layout ── */
.block-container {
    padding: 2rem 3rem 4rem 3rem !important;
    max-width: 1300px !important;
}

/* ── Typography ── */
h1, h2, h3, h4 {
    color: #111827 !important;
    font-weight: 700 !important;
}
h1 { font-size: 1.9rem !important; margin-bottom: 0.3rem !important; }
h2 { font-size: 1.3rem !important; margin: 1.4rem 0 0.6rem 0 !important; }
h3 { font-size: 1.05rem !important; margin: 1rem 0 0.4rem 0 !important; }

p, li, span, label, div {
    color: #374151 !important;
    font-size: 0.95rem !important;
    line-height: 1.7 !important;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: #F9FAFB !important;
    border: 1.5px solid #E5E7EB !important;
    border-radius: 12px !important;
    padding: 1rem 1.1rem !important;
}
[data-testid="stMetricLabel"] p,
[data-testid="metric-container"] label {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    color: #6B7280 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    color: #111827 !important;
    white-space: normal !important;
    word-break: break-word !important;
}

/* ── Tabs ── */
[data-baseweb="tab"] p {
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    color: #4B5563 !important;
}
[aria-selected="true"] p {
    color: #6C63FF !important;
}

/* ── Expander ── */
details summary {
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    color: #1F2937 !important;
    padding: 0.5rem 0 !important;
    white-space: normal !important;
    word-break: break-word !important;
}

/* ── Alert / info boxes ── */
[data-testid="stAlert"] p {
    font-size: 0.9rem !important;
    line-height: 1.65 !important;
    color: inherit !important;
}

/* ── Caption ── */
[data-testid="stCaptionContainer"] p,
small {
    font-size: 0.8rem !important;
    color: #6B7280 !important;
    line-height: 1.5 !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #F9FAFB !important;
    border-right: 1px solid #E5E7EB !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] li {
    font-size: 0.87rem !important;
    color: #374151 !important;
    line-height: 1.75 !important;
}

/* ── Buttons ── */
button[kind="primary"] {
    background: #6C63FF !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
button[kind="secondary"] {
    border-radius: 8px !important;
    font-weight: 600 !important;
}

/* ── Text inputs ── */
input, textarea, select {
    font-size: 0.9rem !important;
    color: #111827 !important;
}

/* ── No text cut anywhere ── */
* { overflow-wrap: break-word !important; word-break: break-word !important; }

/* ── Divider ── */
hr { border-color: #E5E7EB !important; margin: 1.2rem 0 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="margin-bottom: 1.5rem;">
  <h1 style="margin-bottom:4px;">📊 ConcallAnalyser — India</h1>
  <p style="color:#6B7280; font-size:1rem; margin:0;">
    Search any NSE company · Pull concall PDFs · Corporate announcements · Market buzz · AI investment signals
  </p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### 📖 How to use")
    st.markdown("""
**Tab 1 — Search & Analyze**
1. Type company name or NSE symbol
2. Select from dropdown
3. Fetch concall documents
4. Click Analyze

**Tab 2 — Upload PDF**
Upload any concall/AGM PDF manually

**Tab 3 — Announcements**
Fetch & score all NSE filings for a company

**Tab 4 — Market Buzz**
Real-time stock mentions from financial news
    """)
    st.divider()
    st.markdown("""
<div style="font-size:0.8rem; color:#9CA3AF; line-height:1.8;">
  🤖 Powered by Groq + Llama 3.3 70B<br>
  📡 Data: NSE Corporate Filings<br>
  📰 News: ET Markets · Moneycontrol · LiveMint
</div>
""", unsafe_allow_html=True)


def _val(v, fallback="Not mentioned"):
    if v is None or v == "" or v == []:
        return fallback
    return v


def render_analysis(result: dict):
    if "error" in result:
        st.error(f"Analysis error: {result['error']}")
        st.code(result.get("raw", ""))
        return

    # Support both old flat structure and new nested structure
    hv = result.get("headline_verdict", result)
    mgmt = result.get("management_assessment", {})
    fin = result.get("financials_reported", {})
    guid = result.get("guidance", {})
    themes = result.get("key_themes", {})
    segments = result.get("segment_analysis", [])
    qa = result.get("analyst_qa_highlights", [])
    comp = result.get("competitive_landscape", {})
    outlook = result.get("outlook_summary", {})
    inv = result.get("investor_summary", {})

    signal = hv.get("intraday_signal", result.get("intraday_signal", "HOLD"))
    sentiment = hv.get("overall_sentiment", result.get("overall_sentiment", "NEUTRAL"))
    score = hv.get("sentiment_score", result.get("sentiment_score", 0)) or 0
    confidence = hv.get("signal_confidence", "MEDIUM")
    verdict = hv.get("one_line_verdict", "")
    rec = inv.get("recommendation", signal)

    # ── VERDICT BANNER ────────────────────────────────────────────────────────
    sig_color = {"BUY": "#10b981", "SELL": "#ef4444", "HOLD": "#f59e0b",
                 "ACCUMULATE": "#10b981", "REDUCE": "#ef4444", "AVOID": "#ef4444"}.get(signal, "#6b7280")
    st.markdown(f"""
    <div style="background:{sig_color}15; border-left: 4px solid {sig_color};
                padding: 1rem 1.25rem; border-radius: 8px; margin-bottom: 1rem;">
        <div style="font-size:0.75rem; font-weight:700; color:{sig_color};
                    text-transform:uppercase; letter-spacing:0.08em;">
            {sentiment} · {signal} · Confidence: {confidence}
        </div>
        <div style="font-size:1.05rem; font-weight:600; color:#111827; margin-top:4px;">
            {verdict or hv.get("signal_reasoning", result.get("signal_reasoning", ""))}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── TOP METRICS ───────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    sig_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "ACCUMULATE": "🟢", "REDUCE": "🔴", "AVOID": "🔴"}
    m1.metric("Signal", f"{sig_emoji.get(signal,'🟡')} {signal}")
    m2.metric("Sentiment Score", f"{score:+}/10")
    sent_e = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(sentiment, "🟡")
    m3.metric("Sentiment", f"{sent_e} {sentiment}")
    m4.metric("Mgmt Tone", _val(mgmt.get("tone"), "N/A"))
    m5.metric("Credibility", f"{_val(mgmt.get('credibility_score'), '?')}/10")

    # ── GAUGE ─────────────────────────────────────────────────────────────────
    try:
        score_num = float(score)
    except (TypeError, ValueError):
        score_num = 0
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score_num,
        number={"suffix": "/10"},
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Sentiment Score"},
        gauge={
            "axis": {"range": [-10, 10]},
            "bar": {"color": "#6C63FF"},
            "steps": [
                {"range": [-10, -3], "color": "#fee2e2"},
                {"range": [-3, 3],   "color": "#fef9c3"},
                {"range": [3, 10],   "color": "#dcfce7"},
            ],
        }
    ))
    fig.update_layout(height=220, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.divider()

    # ── SECTION 1: FINANCIALS ─────────────────────────────────────────────────
    st.subheader("💰 Financials Reported")
    f1, f2, f3 = st.columns(3)
    with f1:
        st.markdown("**Revenue**")
        st.write(_val(fin.get("revenue")))
        st.caption(f"YoY: {_val(fin.get('revenue_growth_yoy'))} | QoQ: {_val(fin.get('revenue_growth_qoq'))}")

        st.markdown("**EBITDA**")
        st.write(_val(fin.get("ebitda")))
        st.caption(f"Margin: {_val(fin.get('ebitda_margin'))} ({_val(fin.get('ebitda_margin_change'))})")

    with f2:
        st.markdown("**PAT (Net Profit)**")
        st.write(_val(fin.get("pat")))
        st.caption(f"Growth: {_val(fin.get('pat_growth_yoy'))}")

        st.markdown("**Gross Margin**")
        st.write(_val(fin.get("gross_margin")))
        st.caption(f"EPS: {_val(fin.get('eps'))}")

    with f3:
        st.markdown("**Debt**")
        st.write(_val(fin.get("debt_level")))
        st.caption(f"Cash: {_val(fin.get('cash_and_equivalents'))}")

        st.markdown("**Capex**")
        st.write(_val(fin.get("capex")))
        if fin.get("order_book"):
            st.caption(f"Order book: {fin['order_book']}")
        if fin.get("deal_wins_tcv"):
            st.caption(f"Deal TCV: {fin['deal_wins_tcv']}")

    st.divider()

    # ── SECTION 2: GUIDANCE ───────────────────────────────────────────────────
    st.subheader("🔭 Management Guidance")
    if guid.get("guidance_changed"):
        st.warning(f"⚠️ Guidance revised: {_val(guid.get('guidance_change_detail'))}")

    g1, g2 = st.columns(2)
    with g1:
        st.markdown(f"**Revenue Guidance:** {_val(guid.get('revenue_guidance'))}")
        st.markdown(f"**Margin Guidance:** {_val(guid.get('margin_guidance'))}")
        st.markdown(f"**Growth Guidance:** {_val(guid.get('growth_guidance'))}")
    with g2:
        st.markdown(f"**Capex Plan:** {_val(guid.get('capex_guidance'))}")
        st.markdown(f"**Hiring Plan:** {_val(guid.get('hiring_guidance'))}")
        st.markdown(f"**Dividend Policy:** {_val(guid.get('dividend_guidance'))}")
    st.divider()

    # ── SECTION 3: KEY THEMES ─────────────────────────────────────────────────
    st.subheader("📊 Key Themes")
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("**✅ Positives**")
        for p in themes.get("positives", result.get("key_positives", [])):
            st.success(p)
        st.markdown("**🌬️ Tailwinds**")
        for tw in themes.get("tailwinds", []):
            st.info(tw)
    with t2:
        st.markdown("**⚠️ Risks**")
        for r in themes.get("risks", result.get("key_risks", [])):
            st.error(r)
        st.markdown("**🌧️ Headwinds**")
        for hw in themes.get("headwinds", []):
            st.warning(hw)

    red_flags = themes.get("red_flags", result.get("red_flags", []))
    if red_flags:
        st.markdown("**🚩 Red Flags**")
        for f in red_flags:
            st.error(f"🚩 {f}")
    st.divider()

    # ── SECTION 4: MANAGEMENT ASSESSMENT ─────────────────────────────────────
    st.subheader("🎙️ Management Assessment")
    ma1, ma2 = st.columns(2)
    with ma1:
        st.markdown(f"**Tone:** `{_val(mgmt.get('tone'))}`")
        st.write(_val(mgmt.get("tone_reasoning")))
        st.markdown("**Key Speakers:**")
        for spk in mgmt.get("key_speakers", []):
            st.caption(f"• {spk}")
    with ma2:
        st.markdown("**Strong Statements:**")
        for stmt in mgmt.get("strong_statements", []):
            st.info(f"💬 *\"{stmt}\"*")
        if mgmt.get("evasive_questions"):
            st.markdown("**Questions Dodged:**")
            for q in mgmt.get("evasive_questions", []):
                st.warning(f"🔍 {q}")
    st.divider()

    # ── SECTION 5: SEGMENT ANALYSIS ───────────────────────────────────────────
    if segments:
        st.subheader("📦 Segment Analysis")
        for seg in segments:
            with st.expander(f"**{seg.get('segment_name', 'Segment')}** — {_val(seg.get('revenue'))} | Growth: {_val(seg.get('growth'))}"):
                sc1, sc2 = st.columns(2)
                sc1.metric("Revenue", _val(seg.get("revenue")))
                sc2.metric("Growth", _val(seg.get("growth")))
                if seg.get("margin"):
                    st.caption(f"Margin: {seg['margin']}")
                st.write(_val(seg.get("outlook")))
        st.divider()

    # ── SECTION 6: ANALYST Q&A ────────────────────────────────────────────────
    if qa:
        st.subheader("❓ Analyst Q&A Highlights")
        for item in qa:
            quality = item.get("management_answer_quality", "")
            q_color = {"Clear": "✅", "Strong": "✅", "Vague": "🟡", "Deflected": "🔴"}.get(quality, "🟡")
            with st.expander(f"{q_color} {_val(item.get('question_topic'))} — *{_val(item.get('analyst_firm', 'Analyst'))}* · Answer: {quality}"):
                st.write(_val(item.get("key_takeaway")))
        st.divider()

    # ── SECTION 7: COMPETITIVE LANDSCAPE ─────────────────────────────────────
    if comp and any(comp.values()):
        st.subheader("🏆 Competitive Landscape")
        cp1, cp2 = st.columns(2)
        with cp1:
            if comp.get("competitors_mentioned"):
                st.markdown("**Competitors Mentioned:**")
                st.write(", ".join(comp["competitors_mentioned"]))
            st.markdown(f"**Market Share:** {_val(comp.get('market_share_commentary'))}")
            st.markdown(f"**Pricing Power:** {_val(comp.get('pricing_power'))}")
        with cp2:
            if comp.get("competitive_advantages_cited"):
                st.markdown("**Moats Cited:**")
                for adv in comp["competitive_advantages_cited"]:
                    st.success(adv)
        st.divider()

    # ── SECTION 8: OUTLOOK ────────────────────────────────────────────────────
    st.subheader("🔮 Outlook & Monitorables")
    o1, o2 = st.columns(2)
    with o1:
        st.markdown(f"**Next Quarter:** {_val(outlook.get('short_term_1q'))}")
        st.markdown(f"**1-Year View:** {_val(outlook.get('medium_term_1y'))}")
        if outlook.get("catalysts"):
            st.markdown("**Catalysts to Watch:**")
            for c in outlook["catalysts"]:
                st.success(c)
    with o2:
        if outlook.get("key_monitorables"):
            st.markdown("**Key Monitorables:**")
            for m in outlook["key_monitorables"]:
                st.info(f"👁 {m}")
        if outlook.get("risks_to_watch"):
            st.markdown("**Risks to Watch:**")
            for r in outlook["risks_to_watch"]:
                st.error(r)
    st.divider()

    # ── SECTION 9: INVESTOR SUMMARY ───────────────────────────────────────────
    st.subheader("📝 Investor Summary")
    st.info(f"**For Retail Investors:** {_val(inv.get('for_retail_investor', result.get('analyst_summary', '')))}")

    bc1, bc2 = st.columns(2)
    with bc1:
        st.markdown("**🐂 Bull Case:**")
        st.success(_val(inv.get("buy_case")))
    with bc2:
        st.markdown("**🐻 Bear Case:**")
        st.error(_val(inv.get("sell_case")))

    if inv.get("target_price_mentioned"):
        st.caption(f"Analyst target prices mentioned: {inv['target_price_mentioned']}")

    rec_color = {"BUY": "🟢", "ACCUMULATE": "🟢", "HOLD": "🟡",
                 "REDUCE": "🔴", "SELL": "🔴", "AVOID": "🔴"}.get(rec, "🟡")
    st.markdown(f"### Final Recommendation: {rec_color} **{rec}**")

    with st.expander("🔧 Raw Analysis JSON"):
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
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔎 Search NSE & Analyze", "📤 Upload PDF Manually", "📢 AGM / Announcements", "📡 Market Buzz", "📅 Event Calendar"])


# ======== TAB 1: SEARCH ========
with tab1:
    st.subheader("Search Company on NSE")
    st.caption("Type company name or NSE symbol — live suggestions from 2000+ listed companies")

    # Load all companies into cache on first run
    load_all_companies()

    selected_label = st_searchbox(
        search_nse,
        placeholder="e.g. Infosys, HDFC Bank, RELIANCE, TCS...",
        key="nse_searchbox",
        label="Search NSE Company",
        clear_on_submit=False,
    )

    if selected_label:
        # Parse symbol from "Company Name  (SYMBOL)"
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

All 3 sources tried: NSE API → NSE alias lookup → Screener.in

Possible reasons:
- Company files through BSE only
- NSE symbol may differ (e.g. Zomato → ETERNAL)
- Screener.in doesn't have this company indexed

**Manual options:**
1. Download PDF from [NSE filings](https://www.nseindia.com/companies-listing/corporate-filings-announcements) and use **Tab 2 → Upload PDF**
2. Google: `{company_display} concall transcript PDF site:nsearchives.nseindia.com`
            """)
        else:
            source_badge = {"NSE": "🟢 NSE API", "Screener.in": "🟡 Screener.in (fallback)"}.get(
                doc_source.split(" ")[0], f"🔵 {doc_source}")
            st.success(f"Found **{len(docs)} documents** for {company_display} · Source: {source_badge}")

            # Better display: show date + description, not just category title
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
                            st.warning(f"PDF has only {word_count} words — may be an image-based PDF. Analysis may be limited.")
                        else:
                            st.success(f"PDF downloaded: {word_count:,} words extracted")
                    except Exception as e:
                        st.error(f"Failed to download PDF: {e}. Try a different document or upload manually in Tab 2.")
                        st.stop()

                with st.spinner("Analyzing with AI (this takes 15–30 seconds)..."):
                    result = analyze_concall(text, company_display)

                render_analysis(result)


# ======== TAB 2: MANUAL UPLOAD ========
with tab2:
    st.subheader("Upload Concall PDF Manually")
    company_name = st.text_input("Company Name", placeholder="e.g. Reliance Industries", key="manual_company")
    uploaded_file = st.file_uploader(
        "Upload Concall Transcript (PDF)",
        type=["pdf"],
        help="BSE/NSE concall transcripts, broker research PDFs"
    )

    if uploaded_file and company_name:
        if st.button("🔍 Analyze Concall", type="primary", use_container_width=True):
            with st.spinner("Reading PDF..."):
                text = extract_text_from_pdf(uploaded_file)
                word_count = len(text.split())
                st.success(f"PDF read: {word_count} words extracted")

            with st.spinner("Analyzing with AI..."):
                result = analyze_concall(text, company_name)

            render_analysis(result)

    elif uploaded_file and not company_name:
        st.warning("Enter company name first.")
    elif company_name and not uploaded_file:
        st.info("Upload a PDF to begin.")


# ======== TAB 3: AGM / ANNOUNCEMENTS ========
with tab3:
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


# ======== TAB 4: MARKET BUZZ ========
with tab4:
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


# ======== TAB 5: EVENT CALENDAR ========
with tab5:
    import calendar as cal_lib
    from datetime import datetime as dt_lib

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
        from collections import Counter
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
