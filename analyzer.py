import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_api_key = os.getenv("GROQ_API_KEY")
if not _api_key:
    raise RuntimeError(
        "GROQ_API_KEY not set. Add it to your .env file or Streamlit secrets."
    )
client = Groq(api_key=_api_key)

SYSTEM_PROMPT = """You are a senior equity research analyst at a bulge-bracket investment bank covering Indian equities.
You have 15 years of experience analysing NSE/BSE listed companies across sectors.
Extract every financial metric, management statement, and forward signal from the transcript.
Be precise. Use exact numbers from the transcript where available. Never hallucinate numbers.
Return ONLY valid JSON. No markdown fences. No text outside the JSON object."""


def analyze_concall(text: str, company_name: str) -> dict:
    # Use up to 14000 chars — leaves room for output tokens
    transcript_chunk = text[:14000]

    prompt = f"""
Perform a DEEP analysis of this earnings call transcript for {company_name}.

TRANSCRIPT:
{transcript_chunk}

Return EXACTLY this JSON structure. Use null for fields not mentioned in the transcript.
Do NOT invent numbers. If a metric is not stated, use null.

{{
  "company": "{company_name}",

  "headline_verdict": {{
    "overall_sentiment": "BULLISH | BEARISH | NEUTRAL",
    "sentiment_score": <integer -10 to +10>,
    "intraday_signal": "BUY | SELL | HOLD",
    "signal_confidence": "HIGH | MEDIUM | LOW",
    "signal_reasoning": "<2 sentence reason with specific data points from transcript>",
    "one_line_verdict": "<single sentence verdict a fund manager would say>"
  }},

  "management_assessment": {{
    "tone": "Confident | Cautious | Defensive | Optimistic | Evasive | Mixed",
    "tone_reasoning": "<why you assessed this tone>",
    "credibility_score": <1-10, how credible management seems>,
    "evasive_questions": ["<analyst question they dodged or gave vague answer to>"],
    "strong_statements": ["<exact or near-exact quotes of strong forward-looking statements>"],
    "key_speakers": ["<names and roles of people who spoke>"]
  }},

  "financials_reported": {{
    "revenue": "<exact figure with units e.g. ₹12,400 Cr>",
    "revenue_growth_yoy": "<e.g. +8.2% YoY>",
    "revenue_growth_qoq": "<e.g. +2.1% QoQ>",
    "ebitda": "<figure>",
    "ebitda_margin": "<e.g. 24.5%>",
    "ebitda_margin_change": "<e.g. +120 bps YoY>",
    "pat": "<Profit After Tax figure>",
    "pat_growth_yoy": "<e.g. +15% YoY>",
    "eps": "<earnings per share if mentioned>",
    "gross_margin": "<if mentioned>",
    "debt_level": "<total debt figure>",
    "cash_and_equivalents": "<cash on books>",
    "capex": "<capex spent this quarter/year>",
    "working_capital_days": "<if mentioned>",
    "order_book": "<outstanding order book value if applicable>",
    "deal_wins_tcv": "<Total Contract Value of new deals if IT/services company>"
  }},

  "guidance": {{
    "revenue_guidance": "<exact guidance given for next quarter/year>",
    "margin_guidance": "<exact margin guidance>",
    "growth_guidance": "<growth rate guidance>",
    "capex_guidance": "<planned capex>",
    "hiring_guidance": "<headcount/hiring plans>",
    "dividend_guidance": "<dividend or payout policy mentioned>",
    "guidance_changed": true | false,
    "guidance_change_detail": "<what changed vs previous guidance, if applicable>"
  }},

  "segment_analysis": [
    {{
      "segment_name": "<e.g. Retail, B2B, North America, Pharma>",
      "revenue": "<segment revenue>",
      "growth": "<segment growth>",
      "margin": "<segment margin if given>",
      "outlook": "<management commentary on segment>"
    }}
  ],

  "key_themes": {{
    "positives": [
      "<specific positive point with data e.g. EBITDA margins expanded 150bps driven by cost efficiencies>",
      "<positive 2>",
      "<positive 3>",
      "<positive 4>"
    ],
    "risks": [
      "<specific risk with context e.g. Demand slowdown in US market — management flagged macro uncertainty>",
      "<risk 2>",
      "<risk 3>"
    ],
    "red_flags": [
      "<any concerning signals e.g. management avoided answering debt repayment timeline twice>"
    ],
    "tailwinds": ["<industry/macro tailwinds mentioned>"],
    "headwinds": ["<industry/macro headwinds mentioned>"]
  }},

  "analyst_qa_highlights": [
    {{
      "analyst_firm": "<firm name if mentioned>",
      "question_topic": "<what the analyst asked about>",
      "management_answer_quality": "Clear | Vague | Deflected | Strong",
      "key_takeaway": "<what we learned from this Q&A exchange>"
    }}
  ],

  "competitive_landscape": {{
    "competitors_mentioned": ["<competitor names mentioned>"],
    "market_share_commentary": "<any market share gains/losses mentioned>",
    "pricing_power": "<commentary on pricing ability>",
    "competitive_advantages_cited": ["<moats or differentiators management highlighted>"]
  }},

  "outlook_summary": {{
    "short_term_1q": "<outlook for next quarter>",
    "medium_term_1y": "<1 year outlook>",
    "key_monitorables": ["<metrics/events to watch e.g. Q3 margin trajectory, US client ramp-up>"],
    "catalysts": ["<potential positive catalysts e.g. large deal announcement, margin recovery>"],
    "risks_to_watch": ["<downside risks e.g. rupee depreciation, client budget cuts>"]
  }},

  "investor_summary": {{
    "for_retail_investor": "<4-5 line plain English summary — what does this mean for someone holding or considering this stock>",
    "buy_case": "<2-3 line bull case after this concall>",
    "sell_case": "<2-3 line bear case after this concall>",
    "target_price_mentioned": "<any analyst target prices mentioned during call>",
    "recommendation": "ACCUMULATE | HOLD | REDUCE | AVOID | BUY | SELL"
  }}
}}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.15,
        max_tokens=4000
    )

    raw = response.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
        return {"error": "Failed to parse response", "raw": raw[:500]}


def extract_text_from_pdf(pdf_file) -> str:
    from pypdf import PdfReader
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text
