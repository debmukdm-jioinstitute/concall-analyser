# ConcallAnalyser — India

AI-powered earnings call intelligence for NSE-listed companies.

## Features
- Search 2000+ NSE companies, fetch concall PDFs directly
- Deep AI analysis: financials, guidance, management tone, risks
- AGM & corporate announcement scoring (bullish/bearish)
- Real-time market buzz from ET Markets, Moneycontrol, LiveMint

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add your Groq API key
streamlit run app.py
```

## Environment Variables

Create a `.env` file:
```
GROQ_API_KEY=your_groq_api_key_here
```

Get a free Groq API key at [console.groq.com](https://console.groq.com)

## Powered by
- Groq + Llama 3.3 70B
- NSE Corporate Filings API
- Screener.in (fallback)
