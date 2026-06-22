from __future__ import annotations

import requests
import csv
import io

_nse_companies: dict[str, str] = {}  # symbol -> name


def _load_nse_equity_list() -> dict[str, str]:
    """Download full NSE equity list (~2300 companies). Cache in memory."""
    global _nse_companies
    if _nse_companies:
        return _nse_companies

    try:
        from nsepython import headers
        s = requests.Session()
        s.headers.update(headers)
        s.get("https://www.nseindia.com", timeout=10)
        r = s.get(
            "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
            timeout=15
        )
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.text))
        for row in reader:
            symbol = row.get("SYMBOL", "").strip()
            name = row.get("NAME OF COMPANY", "").strip()
            series = row.get(" SERIES", "").strip()
            if symbol and name and series == "EQ":
                _nse_companies[symbol] = name
    except Exception:
        _nse_companies = _get_fallback()

    return _nse_companies


def _get_fallback() -> dict[str, str]:
    return {
        "RELIANCE": "Reliance Industries", "TCS": "Tata Consultancy Services",
        "HDFCBANK": "HDFC Bank", "INFY": "Infosys", "ICICIBANK": "ICICI Bank",
        "HINDUNILVR": "Hindustan Unilever", "SBIN": "State Bank of India",
        "BHARTIARTL": "Bharti Airtel", "ITC": "ITC Limited",
        "KOTAKBANK": "Kotak Mahindra Bank", "LT": "Larsen & Toubro",
        "AXISBANK": "Axis Bank", "ASIANPAINT": "Asian Paints",
        "MARUTI": "Maruti Suzuki", "SUNPHARMA": "Sun Pharmaceutical",
        "TITAN": "Titan Company", "WIPRO": "Wipro",
        "ULTRACEMCO": "UltraTech Cement", "ONGC": "ONGC",
        "BAJFINANCE": "Bajaj Finance", "NTPC": "NTPC",
        "HCLTECH": "HCL Technologies", "TATAMOTORS": "Tata Motors",
        "ZOMATO": "Zomato", "NAUKRI": "Info Edge", "IRCTC": "IRCTC",
        "HAL": "Hindustan Aeronautics", "DLF": "DLF",
        "ADANIENT": "Adani Enterprises", "ADANIPORTS": "Adani Ports",
        "COALINDIA": "Coal India", "DRREDDY": "Dr. Reddy's",
        "CIPLA": "Cipla", "LUPIN": "Lupin", "DIVISLAB": "Divi's Labs",
        "TECHM": "Tech Mahindra", "NESTLEIND": "Nestle India",
        "BAJAJFINSV": "Bajaj Finserv", "EICHERMOT": "Eicher Motors",
        "TATASTEEL": "Tata Steel", "JSWSTEEL": "JSW Steel",
        "HINDALCO": "Hindalco", "DMART": "Avenue Supermarts",
        "TRENT": "Trent", "PERSISTENT": "Persistent Systems",
        "MPHASIS": "Mphasis", "COFORGE": "Coforge", "LTIM": "LTIMindtree",
        "TATAELXSI": "Tata Elxsi", "ANGELONE": "Angel One",
        "PAYTM": "One 97 Communications", "NYKAA": "FSN E-Commerce",
        "LICI": "LIC India", "RVNL": "Rail Vikas Nigam",
        "BEL": "Bharat Electronics", "BHEL": "Bharat Heavy Electricals",
        "SAIL": "Steel Authority of India", "GAIL": "GAIL India",
        "IOC": "Indian Oil", "HPCL": "Hindustan Petroleum",
        "BPCL": "Bharat Petroleum", "TATAPOWER": "Tata Power",
        "GODREJPROP": "Godrej Properties", "OBEROIRLTY": "Oberoi Realty",
        "POLYCAB": "Polycab India", "DIXON": "Dixon Technologies",
        "HAVELLS": "Havells India", "VOLTAS": "Voltas",
        "CROMPTON": "Crompton Greaves", "BLUESTARCO": "Blue Star",
        "CEAT": "CEAT", "MRF": "MRF", "APOLLOTYRE": "Apollo Tyres",
        "ESCORTS": "Escorts Kubota", "ASHOKLEY": "Ashok Leyland",
        "TVSMOTOR": "TVS Motor", "BAJAJ-AUTO": "Bajaj Auto",
        "HEROMOTOCO": "Hero MotoCorp", "M&M": "Mahindra & Mahindra",
    }


def search_companies(query: str, max_results: int = 10) -> list[dict]:
    """Search NSE companies by name or symbol. Returns list of {symbol, name}."""
    if not query or len(query.strip()) < 1:
        return []

    companies = _load_nse_equity_list()
    q_upper = query.upper().strip()
    q_lower = query.lower().strip()
    results = []
    seen = set()

    def add(sym, name):
        if sym not in seen:
            seen.add(sym)
            results.append({"symbol": sym, "name": name})

    # 1. Exact symbol
    if q_upper in companies:
        add(q_upper, companies[q_upper])

    # 2. Symbol starts with query
    for sym, name in companies.items():
        if sym.startswith(q_upper) and sym != q_upper:
            add(sym, name)
        if len(results) >= max_results:
            return results

    # 3. Name starts with query word
    for sym, name in companies.items():
        if name.lower().startswith(q_lower):
            add(sym, name)
        if len(results) >= max_results:
            return results

    # 4. Name contains query anywhere
    for sym, name in companies.items():
        if q_lower in name.lower():
            add(sym, name)
        if len(results) >= max_results:
            return results

    return results[:max_results]


def get_all_display_names() -> list[str]:
    """Return all companies as 'NAME (SYMBOL)' strings for selectbox."""
    companies = _load_nse_equity_list()
    return [f"{name} ({sym})" for sym, name in sorted(companies.items(), key=lambda x: x[1])]
