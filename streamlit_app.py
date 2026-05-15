import json
import re
import time as _time
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as _stc
import yfinance as yf
from deep_translator import GoogleTranslator
from plotly.subplots import make_subplots


@st.cache_data(show_spinner=False, ttl=86400)
def translate_to_thai(text: str) -> str:
    try:
        chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
        return " ".join(GoogleTranslator(source="en", target="th").translate(c) for c in chunks)
    except Exception:
        return text


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_stock_news(ticker: str, max_items: int = 6):
    try:
        news_list = yf.Ticker(ticker).news or []
        out = []
        for item in news_list[:max_items]:
            title = (item.get("content", {}).get("title") or item.get("title", "")).strip()
            if not title:
                continue
            link = (item.get("content", {}).get("canonicalUrl", {}).get("url")
                    or item.get("link", "#"))
            publisher = (item.get("content", {}).get("provider", {}).get("displayName")
                         or item.get("publisher", ""))
            pub_ts = (item.get("content", {}).get("pubDate")
                      or item.get("providerPublishTime", 0))
            if isinstance(pub_ts, str):
                try:
                    pub_ts = int(datetime.fromisoformat(pub_ts.replace("Z", "+00:00")).timestamp())
                except Exception:
                    pub_ts = 0
            out.append({"title": title, "publisher": publisher,
                        "link": link, "published": int(pub_ts or 0)})
        return out
    except Exception:
        return []


DEFAULT_FAVORITES = ["NVDA", "AMD", "INTC", "LLY", "UNH", "V", "SCB.BK"]
FAVORITES_FILE = Path("favorites.json")

_TV_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
    "Content-Type": "application/json",
}
_TV_URL = "https://scanner.tradingview.com/america/scan"


@st.cache_data(ttl=120, show_spinner=False)
def fetch_us_gainers():
    pre_payload = {
        "filter": [
            {"left": "premarket_change", "operation": "nempty"},
            {"left": "premarket_change", "operation": "greater", "right": 0},
            {"left": "close", "operation": "greater", "right": 1},
            {"left": "exchange", "operation": "in_range",
             "right": ["NASDAQ", "NYSE", "AMEX"]},
        ],
        "columns": ["name", "description", "close", "premarket_close", "premarket_change"],
        "sort": {"sortBy": "premarket_change", "sortOrder": "desc"},
        "range": [0, 10],
    }
    try:
        r = requests.post(_TV_URL, json=pre_payload, headers=_TV_HEADERS, timeout=14)
        r.raise_for_status()
        rows = r.json().get("data", [])
        if rows:
            gainers = []
            for row in rows:
                d = row.get("d", [])
                if len(d) >= 5 and d[4] is not None:
                    gainers.append({"ticker": d[0] or "", "name": (d[1] or d[0] or "")[:28],
                                    "price": d[3] if d[3] else d[2], "pct": float(d[4])})
            if gainers:
                return gainers, "pre", None
    except Exception:
        pass

    reg_payload = {
        "filter": [
            {"left": "change", "operation": "greater", "right": 0},
            {"left": "close", "operation": "greater", "right": 1},
            {"left": "volume", "operation": "greater", "right": 1000000},
            {"left": "exchange", "operation": "in_range", "right": ["NASDAQ", "NYSE", "AMEX"]},
        ],
        "columns": ["name", "description", "close", "change"],
        "sort": {"sortBy": "change", "sortOrder": "desc"},
        "range": [0, 10],
    }
    try:
        r = requests.post(_TV_URL, json=reg_payload, headers=_TV_HEADERS, timeout=14)
        r.raise_for_status()
        rows = r.json().get("data", [])
        gainers = []
        for row in rows:
            d = row.get("d", [])
            if len(d) >= 4 and d[3] is not None:
                gainers.append({"ticker": d[0] or "", "name": (d[1] or d[0] or "")[:28],
                                "price": d[2] or 0, "pct": float(d[3])})
        return gainers[:10], "regular", None
    except Exception as exc:
        return [], "regular", str(exc)


st.set_page_config(page_title="GEMUDA STATION", page_icon="🌕", layout="wide")

_GLOBAL_CSS = """
<style>
html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"], [data-testid="block-container"],
button, input, select, textarea {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text",
                 "Segoe UI", Roboto, sans-serif !important;
}
body::before {
    content: '';
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background:
        radial-gradient(ellipse 900px 800px at 8%  12%,  rgba(110,231,183,0.55), transparent 65%),
        radial-gradient(ellipse 750px 680px at 92% 30%,  rgba(96,165,250,0.50),  transparent 65%),
        radial-gradient(ellipse 620px 580px at 20% 82%,  rgba(167,139,250,0.45), transparent 65%),
        radial-gradient(ellipse 540px 500px at 82% 86%,  rgba(251,191,36,0.38),  transparent 65%),
        radial-gradient(ellipse 400px 380px at 55% 50%,  rgba(249,168,212,0.30), transparent 65%),
        linear-gradient(135deg, #e0f7ef 0%, #dbeafe 40%, #ede9fe 70%, #fef9ee 100%);
    animation: bg-breathe 18s ease-in-out infinite alternate;
}
@keyframes bg-breathe {
    0%   { opacity: 1;   }
    50%  { opacity: 0.92; }
    100% { opacity: 1;   }
}
html {
    margin: 0 !important; padding: 0 !important;
    width: 100% !important; min-height: 100% !important;
    overflow-x: hidden !important;
    background: #0a0f18 !important;
}
body {
    margin: 0 !important; padding: 0 !important;
    width: 100% !important; min-height: 100% !important;
    overflow-x: hidden !important;
    background: transparent !important;
}
[data-testid="stCustomComponentV1"],
[data-testid="stCustomComponentV1"] > div,
[data-testid="stCustomComponentV1"] iframe {
    height: 0 !important; min-height: 0 !important; max-height: 0 !important;
    overflow: hidden !important; visibility: hidden !important;
    pointer-events: none !important; border: none !important;
    margin: 0 !important; padding: 0 !important; line-height: 0 !important;
}
[data-testid="stAppViewContainer"], [data-testid="stApp"],
[data-testid="stMain"], [data-testid="block-container"], section.main {
    background: transparent !important;
    color: #1C1C1E !important;
    margin: 0 !important; padding: 0 !important;
    max-width: 100% !important; width: 100% !important;
}
.block-container, [data-testid="block-container"] {
    padding: 0.75rem 0.75rem 2rem 0.75rem !important;
    max-width: 100% !important;
}
[data-testid="stHeader"] { display: none !important; height: 0 !important; visibility: hidden !important; }

[data-testid="stMarkdown"]:has(#gm-fav-anchor) + [data-testid="stHorizontalBlock"] button {
    white-space: pre-wrap !important; line-height: 1.35 !important;
    min-height: 60px !important; text-align: center !important;
    font-size: 0.88rem !important; padding: 8px 12px !important;
}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stStatusWidget"] {
    display: none !important; height: 0 !important; overflow: hidden !important;
}
[data-testid="stBottomBlockContainer"], [data-testid="stBottom"] {
    background: #0a0f18 !important; background-color: #0a0f18 !important;
    border: none !important; box-shadow: none !important; outline: none !important;
}
[data-testid="stBottomBlockContainer"] *, [data-testid="stBottom"] * {
    visibility: hidden !important; pointer-events: none !important;
}

[data-testid="stMetric"] {
    background: rgba(255,255,255,0.18) !important;
    backdrop-filter: blur(24px) saturate(220%) !important;
    -webkit-backdrop-filter: blur(24px) saturate(220%) !important;
    border: 1px solid rgba(255,255,255,0.32) !important;
    border-radius: 22px !important; padding: 20px 24px !important;
    box-shadow: 0 8px 32px rgba(31,38,135,0.10), 0 2px 8px rgba(0,0,0,0.06),
                inset 0 1px 0 rgba(255,255,255,0.65), inset 0 -1px 0 rgba(0,0,0,0.03) !important;
    transition: box-shadow 0.22s ease, transform 0.18s ease !important;
}
[data-testid="stMetric"]:hover {
    background: rgba(255,255,255,0.28) !important;
    box-shadow: 0 12px 40px rgba(5,150,105,0.15), 0 4px 12px rgba(0,0,0,0.08),
                inset 0 1px 0 rgba(255,255,255,0.80), 0 0 0 1.5px rgba(5,150,105,0.28) !important;
    transform: translateY(-3px) !important;
}
[data-testid="stMetricLabel"] {
    color: rgba(40,40,60,0.60) !important; font-size: 0.82rem !important;
    font-weight: 700 !important; letter-spacing: 0.07em !important; text-transform: uppercase !important;
}
[data-testid="stMetricValue"] { color: #1C1C1E !important; font-size: 1.75rem !important; font-weight: 700 !important; }
[data-testid="stMetric"]:has([data-testid="stMetricDeltaIcon-Up"])   [data-testid="stMetricValue"] { color: #34D399 !important; }
[data-testid="stMetric"]:has([data-testid="stMetricDeltaIcon-Down"]) [data-testid="stMetricValue"] { color: #F87171 !important; }
[data-testid="stMetricDelta"] { font-size: 1.00rem !important; font-weight: 600 !important; }
[data-testid="stMetricDelta"] svg { display: none !important; }
[data-testid="stMetricDelta"]:has([data-testid*="Up"])   { color: #34D399 !important; font-weight: 700 !important; }
[data-testid="stMetricDelta"]:has([data-testid*="Down"]) { color: #F87171 !important; font-weight: 700 !important; }

.stButton > button {
    background: rgba(255,255,255,0.20) !important;
    backdrop-filter: blur(18px) saturate(200%) !important;
    -webkit-backdrop-filter: blur(18px) saturate(200%) !important;
    color: #065F46 !important; border: 1px solid rgba(255,255,255,0.35) !important;
    border-radius: 14px !important; font-weight: 600 !important; font-size: 0.95rem !important;
    padding: 10px 22px !important; transition: all 0.18s ease !important;
    box-shadow: 0 4px 16px rgba(31,38,135,0.08), inset 0 1px 0 rgba(255,255,255,0.65) !important;
    letter-spacing: 0.02em !important;
}
.stButton > button:hover {
    background: rgba(255,255,255,0.35) !important; border-color: rgba(5,150,105,0.45) !important;
    box-shadow: 0 8px 24px rgba(5,150,105,0.18), inset 0 1px 0 rgba(255,255,255,0.80),
                0 0 0 2px rgba(5,150,105,0.12) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:active { transform: translateY(0) scale(0.98) !important; }
.stButton > button[kind="primary"] {
    background: rgba(5,150,105,0.72) !important;
    backdrop-filter: blur(20px) saturate(200%) !important;
    -webkit-backdrop-filter: blur(20px) saturate(200%) !important;
    color: #FFFFFF !important; border: 1px solid rgba(255,255,255,0.30) !important;
    font-weight: 700 !important; letter-spacing: 0.04em !important;
    box-shadow: 0 6px 24px rgba(5,150,105,0.35), inset 0 1px 0 rgba(255,255,255,0.30) !important;
}
.stButton > button[kind="primary"]:hover {
    background: rgba(4,120,87,0.85) !important;
    box-shadow: 0 8px 32px rgba(5,150,105,0.45), inset 0 1px 0 rgba(255,255,255,0.35) !important;
    transform: translateY(-2px) !important;
}

[data-testid="stTextInput"] > div > div {
    border-radius: 16px !important; background: rgba(255,255,255,0.18) !important;
    backdrop-filter: blur(24px) saturate(200%) !important;
    -webkit-backdrop-filter: blur(24px) saturate(200%) !important;
    border: 1px solid rgba(255,255,255,0.32) !important;
    box-shadow: 0 4px 16px rgba(31,38,135,0.08), inset 0 1px 0 rgba(255,255,255,0.65) !important;
}
[data-testid="stTextInput"] > div > div > input {
    background: transparent !important; color: #1C1C1E !important;
    border: none !important; padding: 12px 18px !important; font-size: 0.98rem !important;
}
[data-testid="stTextInput"] > div > div > input::placeholder { color: rgba(60,60,67,0.35) !important; }

[data-testid="stTabs"] [role="tablist"] {
    background: rgba(255,255,255,0.16) !important;
    backdrop-filter: blur(24px) saturate(200%) !important;
    border-radius: 16px !important; padding: 5px !important;
    border: 1px solid rgba(255,255,255,0.30) !important;
}
[data-testid="stTabs"] button[role="tab"] {
    background: transparent !important; color: rgba(40,40,60,0.60) !important;
    border-radius: 12px !important; font-weight: 600 !important; font-size: 0.93rem !important; border: none !important;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: rgba(5,150,105,0.75) !important; color: #FFFFFF !important;
    box-shadow: 0 4px 14px rgba(5,150,105,0.30), inset 0 1px 0 rgba(255,255,255,0.25) !important;
}
[data-testid="stTabs"] button[role="tab"]:hover:not([aria-selected="true"]) {
    background: rgba(255,255,255,0.35) !important; color: #1C1C1E !important;
}
[data-testid="stTabsContent"] { background: transparent !important; padding-top: 16px !important; }

[data-testid="stExpander"] {
    background: rgba(255,255,255,0.15) !important;
    backdrop-filter: blur(24px) saturate(200%) !important;
    border: 1px solid rgba(255,255,255,0.30) !important;
    border-radius: 20px !important; overflow: hidden !important;
}
[data-testid="stExpander"] summary { color: #1C1C1E !important; font-weight: 600 !important; padding: 14px 18px !important; }

[data-testid="stInfo"]    { background: rgba(219,234,254,0.55) !important; border-left-color: #3B82F6 !important; border-radius: 14px !important; color: #1C1C1E !important; }
[data-testid="stSuccess"] { background: rgba(209,250,229,0.55) !important; border-left-color: #059669 !important; border-radius: 14px !important; color: #1C1C1E !important; }
[data-testid="stError"]   { background: rgba(254,226,226,0.55) !important; border-left-color: #DC2626 !important; border-radius: 14px !important; color: #1C1C1E !important; }
[data-testid="stWarning"] { background: rgba(254,243,199,0.55) !important; border-left-color: #D97706 !important; border-radius: 14px !important; color: #1C1C1E !important; }

[data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,0.18) !important; border: 1px solid rgba(255,255,255,0.32) !important;
    border-radius: 14px !important; color: #1C1C1E !important;
}
[data-testid="stCaption"], small, caption { color: rgba(60,60,67,0.45) !important; }
hr { border-color: rgba(0,0,0,0.08) !important; margin: 18px 0 !important; }
h1 { color: #1C1C1E !important; letter-spacing: -0.03em !important; }
h2, h3 { color: #1C1C1E !important; }
h4 { color: #3A3A3C !important; }
[data-testid="stCheckbox"] label { color: #3A3A3C !important; font-size: 0.84rem !important; }
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); border-radius: 8px; }
::-webkit-scrollbar-thumb:hover { background: rgba(5,150,105,0.45); }

[data-testid="stMarkdown"]:has(#gm-fav-anchor) + [data-testid="stHorizontalBlock"] {
    overflow-x: auto !important; gap: 8px !important; padding: 10px 8px 14px !important;
    scrollbar-width: thin !important; background: rgba(20,20,30,0.55) !important;
    backdrop-filter: blur(20px) !important; border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 18px !important; margin-bottom: 12px !important;
}
[data-testid="stMarkdown"]:has(#gm-fav-anchor) + [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:not(:last-child) button {
    background: rgba(6,78,59,0.55) !important; color: #6EE7B7 !important;
    border: 1px solid rgba(52,211,153,0.30) !important;
    box-shadow: 0 2px 8px rgba(5,150,105,0.15), inset 0 1px 0 rgba(255,255,255,0.12) !important;
    font-weight: 700 !important; letter-spacing: 0.05em !important; min-width: 72px !important;
}
[data-testid="stMarkdown"]:has(#gm-fav-anchor) + [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:not(:last-child) button:hover {
    background: rgba(6,78,59,0.75) !important; color: #A7F3D0 !important;
    transform: translateY(-1px) !important;
}

/* ── FIB LEVEL BOX STYLES — เหมือน SMA/EMA metric cards ────────── */
.fib-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 200px), 1fr));
    gap: 10px;
    margin: 8px 0 16px 0;
}
/* กรอบ Fibonacci แต่ละ level — ใช้ glass morphism เหมือน metric card */
.fib-card {
    background: rgba(255,255,255,0.08);
    backdrop-filter: blur(24px) saturate(220%);
    -webkit-backdrop-filter: blur(24px) saturate(220%);
    border-radius: 20px;
    padding: 14px 16px 12px 16px;
    border: 1px solid rgba(255,255,255,0.13);
    box-shadow: 0 4px 20px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.10);
    position: relative;
    overflow: hidden;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    border-left: 3px solid transparent;
}
.fib-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 28px rgba(0,0,0,0.36), inset 0 1px 0 rgba(255,255,255,0.14);
}
/* แต่ละ level ใช้สีซ้าย border ต่างกัน */
.fib-card.fib-c100  { border-left-color: #CE93D8; }
.fib-card.fib-c786  { border-left-color: #BA68C8; }
.fib-card.fib-c618  { border-left-color: #F48FB1; background: rgba(244,143,177,0.12); }
.fib-card.fib-c500  { border-left-color: #FFB74D; }
.fib-card.fib-c382  { border-left-color: #81C784; }
.fib-card.fib-c236  { border-left-color: #64B5F6; }
.fib-card.fib-c000  { border-left-color: #CE93D8; }
/* ราคาอยู่ใกล้ — highlight เหมือน golden */
.fib-card.fib-near  {
    border-left-color: #fbbf24 !important;
    background: rgba(251,191,36,0.13) !important;
    box-shadow: 0 0 0 1px rgba(251,191,36,0.30), 0 6px 22px rgba(251,191,36,0.12),
                inset 0 1px 0 rgba(255,255,255,0.14) !important;
}
.fib-card-level {
    font-size: 0.70rem; font-weight: 800; letter-spacing: 0.08em;
    text-transform: uppercase; margin-bottom: 6px; opacity: 0.65;
}
.fib-card-price {
    font-size: 1.30rem; font-weight: 900; letter-spacing: -0.02em;
    line-height: 1; font-variant-numeric: tabular-nums;
    color: #F5F5F7; margin-bottom: 4px;
}
.fib-card-dist {
    font-size: 0.84rem; font-weight: 700; margin-bottom: 4px;
}
.fib-card-desc {
    font-size: 0.68rem; color: rgba(235,235,245,0.42); line-height: 1.35;
}
.fib-near-chip {
    display: inline-block;
    font-size: 0.60rem; font-weight: 800; color: #fbbf24;
    background: rgba(251,191,36,0.18); border: 1px solid rgba(251,191,36,0.40);
    border-radius: 6px; padding: 1px 6px; margin-left: 6px;
    vertical-align: middle; white-space: nowrap;
}

/* ══ DARK MODE ═══════════════════════════════════════════════════ */
body {
    background: transparent !important;
}
body::before {
    background:
        radial-gradient(ellipse 900px 800px at 8%  12%,  rgba(52,211,153,0.30),  transparent 65%),
        radial-gradient(ellipse 750px 680px at 92% 30%,  rgba(96,165,250,0.25),  transparent 65%),
        radial-gradient(ellipse 620px 580px at 20% 82%,  rgba(167,139,250,0.25), transparent 65%),
        radial-gradient(ellipse 540px 500px at 82% 86%,  rgba(251,191,36,0.18),  transparent 65%),
        radial-gradient(ellipse 400px 380px at 55% 50%,  rgba(249,168,212,0.15), transparent 65%),
        linear-gradient(135deg, #0a0f18 0%, #0d1525 40%, #120d22 70%, #0e0c0a 100%);
}
[data-testid="stHeader"] { display: none !important; height: 0 !important; }
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.08) !important; border: 1px solid rgba(255,255,255,0.14) !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.40), inset 0 1px 0 rgba(255,255,255,0.14) !important;
}
[data-testid="stMetricLabel"] { color: rgba(235,235,245,0.45) !important; }
[data-testid="stMetricValue"] { color: #F5F5F7 !important; }
[data-testid="stMarkdown"], p, label { color: #E5E5EA !important; }
span:not([style*="color"]) { color: #E5E5EA !important; }
h1, h2, h3 { color: #F5F5F7 !important; }
h4 { color: rgba(235,235,245,0.75) !important; }
hr { border-color: rgba(255,255,255,0.08) !important; }
[data-testid="stCaption"], small { color: rgba(235,235,245,0.38) !important; }
.stButton > button {
    background: rgba(255,255,255,0.08) !important; color: #34D399 !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.12) !important;
}
.stButton > button:hover {
    background: rgba(255,255,255,0.14) !important; border-color: rgba(52,211,153,0.40) !important; color: #6EE7B7 !important;
}
.stButton > button[kind="primary"] {
    background: rgba(5,150,105,0.65) !important; color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.20) !important;
    box-shadow: 0 6px 24px rgba(5,150,105,0.35), inset 0 1px 0 rgba(255,255,255,0.22) !important;
}
[data-testid="stTextInput"] > div > div {
    background: rgba(255,255,255,0.08) !important; border: 1px solid rgba(255,255,255,0.14) !important;
}
[data-testid="stTextInput"] > div > div > input { color: #E5E5EA !important; }
[data-testid="stTextInput"] > div > div > input::placeholder { color: rgba(235,235,245,0.35) !important; }
[data-testid="stTabs"] [role="tablist"] {
    background: rgba(255,255,255,0.07) !important; border: 1px solid rgba(255,255,255,0.12) !important;
}
[data-testid="stTabs"] button[role="tab"] { color: rgba(235,235,245,0.45) !important; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: rgba(5,150,105,0.70) !important; color: #fff !important;
}
[data-testid="stTabs"] button[role="tab"]:hover:not([aria-selected="true"]) {
    background: rgba(255,255,255,0.10) !important; color: #F5F5F7 !important;
}
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.07) !important; border: 1px solid rgba(255,255,255,0.12) !important;
}
[data-testid="stExpander"] summary { color: #F5F5F7 !important; }
[data-testid="stInfo"]    { background: rgba(96,165,250,0.18) !important; border: 1px solid rgba(96,165,250,0.30) !important; color: #93C5FD !important; }
[data-testid="stSuccess"] { background: rgba(52,211,153,0.15) !important; border: 1px solid rgba(52,211,153,0.28) !important; color: #6EE7B7 !important; }
[data-testid="stError"]   { background: rgba(248,113,113,0.15) !important; border: 1px solid rgba(248,113,113,0.28) !important; color: #FCA5A5 !important; }
[data-testid="stWarning"] { background: rgba(251,191,36,0.15) !important; border: 1px solid rgba(251,191,36,0.28) !important; color: #FCD34D !important; }
[data-testid="stSelectbox"] > div > div {
    background: rgba(255,255,255,0.08) !important; border: 1px solid rgba(255,255,255,0.14) !important; color: #F5F5F7 !important;
}
.gm-header-title { color: #F5F5F7 !important; }
.gm-header-sub   { color: rgba(235,235,245,0.45) !important; }
.gm-card-label   { color: #FFFFFF !important; text-shadow: 0 1px 3px rgba(0,0,0,0.45) !important; }

/* ── PORTRAIT MOBILE ─────────────────────────────────────── */
@media (max-width: 768px) and (orientation: portrait) {
    html, body { margin: 0 !important; padding: 0 !important; overflow-x: hidden !important; }
    .block-container, [data-testid="block-container"] {
        padding: 0.4rem 0.4rem 2rem 0.4rem !important; margin: 0 !important;
        max-width: 100vw !important; width: 100vw !important;
    }
    [data-testid="stHorizontalBlock"] {
        flex-direction: column !important; align-items: stretch !important;
        gap: 0.5rem !important; width: 100% !important;
    }
    [data-testid="stColumn"] {
        width: 100% !important; min-width: 100% !important; max-width: 100% !important;
        flex: 0 0 auto !important; box-sizing: border-box !important;
    }
    .gm-header-wrap  { padding: 44px 6px 14px !important; }
    .gm-header-title { font-size: 2.0rem !important; }
    [data-testid="stTabs"] button[role="tab"] { font-size: 0.82rem !important; padding: 8px 10px !important; }
    [data-testid="stMetric"] { padding: 12px 14px !important; }
    [data-testid="stMarkdown"]:has(#gm-fav-anchor) + [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
}
@media (max-width: 480px) and (orientation: portrait) {
    .block-container, [data-testid="block-container"] { padding: 0.25rem 0.35rem 2rem 0.35rem !important; }
    .gm-header-title { font-size: 1.75rem !important; }
    [data-testid="stTabs"] button[role="tab"] { font-size: 0.75rem !important; padding: 7px 8px !important; }
}
/* ── LANDSCAPE MOBILE — แนวนอน ──────────────────────────── */
@media (max-height: 500px) and (orientation: landscape) {
    html, body { overflow-x: hidden !important; overflow-y: auto !important; }
    .block-container, [data-testid="block-container"] {
        padding: 0.3rem 0.6rem 1.5rem 0.6rem !important;
        max-width: 100vw !important; width: 100vw !important;
    }
    /* แนวนอน: columns วางข้างกันได้ ไม่ stack */
    [data-testid="stHorizontalBlock"] {
        flex-direction: row !important; flex-wrap: wrap !important;
        align-items: flex-start !important; gap: 6px !important;
    }
    [data-testid="stColumn"] {
        flex: 1 1 auto !important; min-width: 120px !important;
        max-width: none !important; width: auto !important;
    }
    .gm-header-wrap  { padding: 8px 6px 8px !important; }
    .gm-header-title { font-size: 1.4rem !important; }
    .gm-header-sub   { font-size: 0.72rem !important; }
    /* tabs เล็กลงนิดหน่อย */
    [data-testid="stTabs"] button[role="tab"] { font-size: 0.76rem !important; padding: 6px 9px !important; }
    [data-testid="stMetric"] { padding: 10px 12px !important; }
    /* fib grid 4 col ในแนวนอน */
    .fib-grid { grid-template-columns: repeat(4, 1fr) !important; }
}
</style>
"""
st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)

_TANUKI_HTML = r"""
<script>
(function(){
  var d = window.parent.document;
  var w = window.parent;
  var svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' shape-rendering='crispEdges'><rect width='16' height='16' fill='none'/><rect x='4' y='1' width='2' height='2' fill='#6b3f22'/><rect x='10' y='1' width='2' height='2' fill='#6b3f22'/><rect x='3' y='3' width='10' height='8' fill='#b96b2c'/><rect x='4' y='4' width='8' height='6' fill='#d9944a'/><rect x='5' y='5' width='2' height='2' fill='#1b120d'/><rect x='9' y='5' width='2' height='2' fill='#1b120d'/><rect x='7' y='7' width='2' height='1' fill='#1b120d'/><rect x='5' y='8' width='6' height='2' fill='#f5d1a1'/><rect x='6' y='9' width='4' height='1' fill='#7a3f1d'/><rect x='2' y='7' width='2' height='3' fill='#6b3f22'/><rect x='12' y='7' width='2' height='3' fill='#6b3f22'/><rect x='4' y='11' width='3' height='3' fill='#6b3f22'/><rect x='9' y='11' width='3' height='3' fill='#6b3f22'/><rect x='1' y='10' width='4' height='2' fill='#8f5225'/><rect x='0' y='11' width='2' height='2' fill='#f5d1a1'/></svg>";
  var angrySvg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' shape-rendering='crispEdges'><rect width='16' height='16' fill='none'/><rect x='4' y='1' width='2' height='2' fill='#6b3f22'/><rect x='10' y='1' width='2' height='2' fill='#6b3f22'/><rect x='3' y='3' width='10' height='8' fill='#b96b2c'/><rect x='4' y='4' width='8' height='6' fill='#d9944a'/><rect x='4' y='4' width='3' height='1' fill='#7f1d1d'/><rect x='9' y='4' width='3' height='1' fill='#7f1d1d'/><rect x='5' y='5' width='2' height='2' fill='#1b120d'/><rect x='9' y='5' width='2' height='2' fill='#1b120d'/><rect x='7' y='7' width='2' height='1' fill='#1b120d'/><rect x='5' y='8' width='6' height='2' fill='#f5d1a1'/><rect x='6' y='9' width='4' height='1' fill='#7f1d1d'/><rect x='2' y='7' width='2' height='3' fill='#6b3f22'/><rect x='12' y='7' width='2' height='3' fill='#6b3f22'/><rect x='4' y='11' width='3' height='3' fill='#6b3f22'/><rect x='9' y='11' width='3' height='3' fill='#6b3f22'/><rect x='1' y='10' width='4' height='2' fill='#8f5225'/><rect x='0' y='11' width='2' height='2' fill='#f5d1a1'/></svg>";
  var src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  var angrySrc = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(angrySvg);
  var old = d.getElementById('gm-floating-tanuki'); if(old) old.remove();
  var oldBubble = d.getElementById('gm-tanuki-bubble'); if(oldBubble) oldBubble.remove();
  var style = d.getElementById('gm-floating-tanuki-style');
  if(!style){
    style = d.createElement('style'); style.id = 'gm-floating-tanuki-style';
    style.textContent = '@keyframes gmTanukiRun{0%,100%{margin-top:0}50%{margin-top:-5px}} @keyframes gmTanukiFeet{0%,100%{filter:drop-shadow(0 10px 6px rgba(0,0,0,.18))}50%{filter:drop-shadow(0 5px 3px rgba(0,0,0,.14))}} @keyframes gmTanukiStruggle{0%,100%{transform:rotate(0deg);}25%{transform:rotate(15deg);}75%{transform:rotate(-15deg);}} @keyframes gmTanukiHappy{0%,100%{transform:translateY(0) rotate(0deg)}35%{transform:translateY(-10px) rotate(-8deg)}70%{transform:translateY(-3px) rotate(8deg)}} @keyframes gmTanukiSad{0%,100%{transform:translateY(0) rotate(-4deg)}50%{transform:translateY(4px) rotate(4deg)}} @keyframes gmTanukiAlert{0%,100%{transform:translateX(0) rotate(0deg)}20%{transform:translateX(-4px) rotate(-12deg)}40%{transform:translateX(4px) rotate(12deg)}60%{transform:translateX(-3px) rotate(-8deg)}80%{transform:translateX(3px) rotate(8deg)}} @keyframes gmHeartFloat{0%{opacity:0;transform:translateY(0) scale(.7)}20%{opacity:1}100%{opacity:0;transform:translateY(-76px) scale(1.35)}} .gm-tanuki-heart{position:fixed;z-index:2147483646;font-size:18px;pointer-events:none;animation:gmHeartFloat 1.9s ease-out forwards;} #gm-tanuki-bubble{position:fixed;z-index:2147483647;max-width:min(260px,72vw);padding:11px 13px;border-radius:16px 16px 16px 4px;background:rgba(255,255,255,.94);color:#0f172a;border:1px solid rgba(255,255,255,.72);box-shadow:0 12px 36px rgba(15,23,42,.18),inset 0 1px 0 rgba(255,255,255,.9);font:700 13px/1.45 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;opacity:0;transform:translateY(8px) scale(.96);transition:opacity .22s ease,transform .22s ease;pointer-events:none;backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)} #gm-tanuki-bubble.gm-show{opacity:1;transform:translateY(0) scale(1)} #gm-tanuki-bubble.gm-happy{border-color:rgba(16,185,129,.45)} #gm-tanuki-bubble.gm-sad{border-color:rgba(96,165,250,.50)} #gm-tanuki-bubble.gm-alert{border-color:rgba(245,158,11,.62)} #gm-tanuki-bubble.gm-angry{border-color:rgba(220,38,38,.55)}';
    d.head.appendChild(style);
  }
  var el = d.createElement('div'); el.id = 'gm-floating-tanuki';
  el.setAttribute('aria-label','Tanuki');
  el.style.cssText = 'position:fixed;left:0;top:0;width:64px;height:64px;z-index:2147483647;cursor:grab;touch-action:none;user-select:none;-webkit-user-select:none;will-change:transform;pointer-events:auto;animation:gmTanukiFeet .28s steps(2,end) infinite;';
  var img = d.createElement('img'); img.src = src; img.alt = 'nuki'; img.draggable = false;
  img.style.cssText = 'width:100%;height:100%;object-fit:contain;image-rendering:pixelated;image-rendering:crisp-edges;animation:gmTanukiRun .28s steps(2,end) infinite;pointer-events:none;';
  el.appendChild(img); d.body.appendChild(el);
  var bubble = d.createElement('div'); bubble.id = 'gm-tanuki-bubble'; d.body.appendChild(bubble);
  var bubbleTimer = null; var moodTimer = null; var saved = {};
  try{ saved = JSON.parse(w.localStorage.getItem('gmTanukiPos') || '{}'); }catch(e){}
  var size = Math.min(72, Math.max(52, Math.floor(w.innerWidth * 0.15)));
  el.style.width = size + 'px'; el.style.height = size + 'px';
  var x = Number.isFinite(saved.x) ? saved.x : Math.max(16, w.innerWidth - size - 24);
  var y = Number.isFinite(saved.y) ? saved.y : Math.max(80, w.innerHeight * 0.45);
  var vx = 0.8; var vy = 0.6; var dragging = false; var moved = false;
  var holdUntil = 0; var startX = 0; var startY = 0; var downX = 0; var downY = 0; var offX = 0; var offY = 0;
  function clamp(){
    size = Math.min(72, Math.max(52, Math.floor(w.innerWidth * 0.15)));
    el.style.width = size+'px'; el.style.height = size+'px';
    x = Math.min(Math.max(4,x), Math.max(4,w.innerWidth-size-4));
    y = Math.min(Math.max(4,y), Math.max(4,w.innerHeight-size-4));
  }
  function paint(){
    clamp();
    el.style.transform = 'translate3d('+x+'px,'+y+'px,0) scaleX('+(vx>=0?1:-1)+')';
    var bx = Math.min(Math.max(10,x-10), Math.max(10,w.innerWidth-285));
    var by = Math.max(10,y-76);
    bubble.style.left = bx+'px'; bubble.style.top = by+'px';
  }
  function setMood(mood){
    if(dragging) return;
    if(moodTimer) w.clearTimeout(moodTimer);
    img.style.filter = ''; img.src = mood==='angry'?angrySrc:src;
    if(mood==='happy'){ img.style.animation='gmTanukiHappy .52s ease-in-out infinite'; img.style.filter='drop-shadow(0 0 10px rgba(16,185,129,.42))'; }
    else if(mood==='sad'){ img.style.animation='gmTanukiSad .9s ease-in-out infinite'; img.style.filter='saturate(.72) drop-shadow(0 0 10px rgba(59,130,246,.30))'; }
    else if(mood==='alert'){ img.style.animation='gmTanukiAlert .20s ease-in-out infinite'; img.style.filter='saturate(1.25) drop-shadow(0 0 12px rgba(245,158,11,.52))'; }
    else if(mood==='angry'){ img.style.animation='gmTanukiAlert .16s ease-in-out infinite'; img.style.filter='saturate(1.45) drop-shadow(0 0 14px rgba(220,38,38,.55))'; }
    else { img.style.animation='gmTanukiRun .28s steps(2,end) infinite'; }
    moodTimer = w.setTimeout(function(){ if(!dragging){ img.src=src; img.style.animation='gmTanukiRun .28s steps(2,end) infinite'; img.style.filter=''; }}, 5200);
  }
  w.gmTanukiSpeak = function(message, mood){
    if(!message) return;
    bubble.textContent = message; bubble.className = 'gm-show gm-'+(mood||'neutral');
    setMood(mood||'neutral');
    if(bubbleTimer) w.clearTimeout(bubbleTimer);
    bubbleTimer = w.setTimeout(function(){ bubble.className=''; }, 6500);
    holdUntil = Date.now()+1200; paint();
  };
  function randomChoice(items){ return items[Math.floor(Math.random()*items.length)]; }
  function spawnHearts(){
    for(var i=0;i<6;i++){
      var h=d.createElement('div'); h.className='gm-tanuki-heart';
      h.textContent=randomChoice(['♥','❤','💕','✨']);
      h.style.left=(x+size*(0.15+Math.random()*0.75))+'px';
      h.style.top=(y+size*(0.12+Math.random()*0.45))+'px';
      h.style.animationDelay=(i*90)+'ms';
      d.body.appendChild(h);
      w.setTimeout(function(node){ node&&node.remove(); }, 1900+i*90, h);
    }
  }
  if(w.gmTanukiNukiInterval) w.clearInterval(w.gmTanukiNukiInterval);
  w.gmTanukiNukiInterval = w.setInterval(function(){ w.gmTanukiSpeak('nuki nuki nuki ♪','happy'); }, 60000);
  function save(){ try{ w.localStorage.setItem('gmTanukiPos',JSON.stringify({x:x,y:y})); }catch(e){} }
  el.addEventListener('pointerdown', function(ev){
    dragging=true; moved=false; el.style.cursor='grabbing';
    img.style.animation='gmTanukiStruggle .15s infinite';
    w.gmTanukiSpeak(randomChoice(['ปล่อย nuki นะ','อย่ามายุ่ง!','เดียวกัดซะเลย','จับเบาๆ สิ','nuki ไม่ใช่ตุ๊กตานะ']),'alert');
    el.setPointerCapture&&el.setPointerCapture(ev.pointerId);
    startX=ev.clientX; startY=ev.clientY; downX=ev.clientX; downY=ev.clientY;
    offX=ev.clientX-x; offY=ev.clientY-y; ev.preventDefault();
  },{passive:false});
  el.addEventListener('pointermove', function(ev){
    if(!dragging) return;
    if(Math.abs(ev.clientX-downX)+Math.abs(ev.clientY-downY)>8) moved=true;
    vx=Math.max(-2.5,Math.min(2.5,(ev.clientX-startX)*0.15||vx));
    vy=Math.max(-2.5,Math.min(2.5,(ev.clientY-startY)*0.15||vy));
    x=ev.clientX-offX; y=ev.clientY-offY; startX=ev.clientX; startY=ev.clientY;
    paint(); ev.preventDefault();
  },{passive:false});
  function endDrag(ev){
    if(!dragging) return; dragging=false; holdUntil=Date.now()+500;
    el.style.cursor='grab'; img.style.animation='gmTanukiRun .28s steps(2,end) infinite'; img.style.filter='';
    el.releasePointerCapture&&el.releasePointerCapture(ev.pointerId);
    paint(); save();
    if(moved){ w.gmTanukiSpeak(randomChoice(['nuki nuki nuki','แค่นี้เองเหรอ','เกือบหลุดละ!']),'angry'); }
    else { spawnHearts(); w.gmTanukiSpeak('nuki nuki nuki ♪','happy'); }
  }
  el.addEventListener('pointerup', endDrag); el.addEventListener('pointercancel', endDrag);
  w.addEventListener('resize', paint);
  function tick(){
    if(!dragging&&Date.now()>holdUntil){ x+=vx; y+=vy;
      if(x<=4||x>=w.innerWidth-size-4) vx*=-1;
      if(y<=56||y>=w.innerHeight-size-12) vy*=-1;
      if(Math.random()<0.005) vy*=-1; if(Math.random()<0.003) vx*=-1;
    }
    paint(); w.requestAnimationFrame(tick);
  }
  tick();
})();
</script>
"""
_stc.html(_TANUKI_HTML, height=0, scrolling=False)

_stc.html("""
<script>
(function(){
  var d = window.parent.document; var w = window.parent;
  var vp = d.querySelector('meta[name="viewport"]');
  if(vp) vp.setAttribute('content','width=device-width, initial-scale=1.0, user-scalable=yes, viewport-fit=cover');
  else { var m=d.createElement('meta'); m.name='viewport'; m.content='width=device-width, initial-scale=1.0, user-scalable=yes, viewport-fit=cover'; d.head.appendChild(m); }
  if(w.history&&w.history.scrollRestoration){ w.history.scrollRestoration='manual'; }
  d.addEventListener('click',function(ev){ var a=ev.target.closest('a'); if(a){ var h=a.getAttribute('href'); if(h==='#'||h===''||h===null){ ev.preventDefault(); ev.stopPropagation(); } }},true);
  function hideFooter(){
    ['stToolbar','stStatusWidget','stDeployButton','stMainMenu'].forEach(function(id){
      d.querySelectorAll('[data-testid="'+id+'"]').forEach(function(el){ el.style.setProperty('display','none','important'); el.style.setProperty('pointer-events','none','important'); });
    });
    var mm=d.getElementById('MainMenu'); if(mm){ mm.style.setProperty('display','none','important'); }
    d.querySelectorAll('footer').forEach(function(el){ el.style.setProperty('display','none','important'); });
    ['stBottomBlockContainer','stBottom'].forEach(function(id){
      d.querySelectorAll('[data-testid="'+id+'"]').forEach(function(el){
        el.style.setProperty('background','#0a0f18','important');
        el.style.setProperty('background-color','#0a0f18','important');
        el.style.setProperty('border','none','important');
        Array.from(el.children).forEach(function(c){ c.style.setProperty('visibility','hidden','important'); });
      });
    });
  }
  function fixBg(){
    ['[data-testid="stApp"]','[data-testid="stAppViewContainer"]','[data-testid="stMain"]',
     '[data-testid="block-container"]','[data-testid="stVerticalBlock"]','.block-container','section.main'
    ].forEach(function(sel){ d.querySelectorAll(sel).forEach(function(el){ el.style.setProperty('background','transparent','important'); el.style.setProperty('background-color','transparent','important'); }); });
  }
  function stackCols(){
    // แนวนอน (landscape) ไม่ต้อง stack columns
    if(w.innerWidth > 768 || (w.innerHeight < 500 && w.innerWidth > w.innerHeight)) return;
    d.querySelectorAll('[data-testid="stHorizontalBlock"]').forEach(function(blk){
      blk.style.setProperty('display','flex','important'); blk.style.setProperty('flex-direction','column','important');
      blk.style.setProperty('align-items','stretch','important'); blk.style.setProperty('width','100%','important');
      blk.querySelectorAll('[data-testid="stColumn"]').forEach(function(col){
        col.style.setProperty('width','100%','important'); col.style.setProperty('min-width','100%','important');
        col.style.setProperty('max-width','100%','important'); col.style.setProperty('flex','0 0 auto','important');
      });
    });
  }
  function runAll(){ hideFooter(); fixBg(); stackCols(); }
  runAll(); w.addEventListener('resize',runAll);
  new MutationObserver(runAll).observe(d.body,{childList:true,subtree:true});
})();
</script>
""", height=0, scrolling=False)


# ─────────────────────────────────────────────────────────────────
# SCROLL-TO-RESULT: inject ผ่าน st.markdown (ทำงานใน parent window)
# ใช้ window.parent เพราะ Streamlit render ใน iframe
# ─────────────────────────────────────────────────────────────────
_SCROLL_JS = """
<script>
(function(){
  var MAX = 40; var tries = 0;
  function doScroll(){
    try {
      // Streamlit Cloud / local: content อยู่ใน parent window
      var docs = [document, window.parent ? window.parent.document : null];
      for(var i = 0; i < docs.length; i++){
        if(!docs[i]) continue;
        var el = docs[i].getElementById('gm-result-anchor');
        if(el){
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          return;
        }
      }
    } catch(e){}
    if(tries++ < MAX) setTimeout(doScroll, 120);
  }
  // หน่วงให้ Streamlit วาง DOM ก่อน แล้วค่อย scroll
  setTimeout(doScroll, 350);
})();
</script>
"""

def sanitize_ticker(raw: str) -> str:
    return re.sub(r"[^A-Z0-9.\-]", "", str(raw).upper().strip())


def fmt_num(value, prefix="", suffix="", decimals=2):
    if value is None or pd.isna(value): return "N/A"
    if abs(value) >= 1e12: return f"{prefix}{value/1e12:.2f}T{suffix}"
    if abs(value) >= 1e9:  return f"{prefix}{value/1e9:.2f}B{suffix}"
    if abs(value) >= 1e6:  return f"{prefix}{value/1e6:.2f}M{suffix}"
    return f"{prefix}{value:.{decimals}f}{suffix}"


def load_favorites():
    try:
        if FAVORITES_FILE.exists():
            saved = json.loads(FAVORITES_FILE.read_text())
            if isinstance(saved, list):
                favs = []
                for t in saved:
                    n = sanitize_ticker(t)
                    if n and n not in favs: favs.append(n)
                return favs
    except Exception:
        pass
    return DEFAULT_FAVORITES.copy()


def save_favorites(favorites):
    FAVORITES_FILE.write_text(json.dumps(favorites, ensure_ascii=False, indent=2))


@st.cache_data(ttl=300)
def load_favorite_snapshot_data(ticker):
    try:
        df = yf.Ticker(ticker).history(period="5d")
        if df is None or df.empty or len(df) < 2: return None
        price = float(df["Close"].iloc[-1])
        prev  = float(df["Close"].iloc[-2])
        pct   = (price - prev) / prev * 100 if prev else 0.0
        return {"price": price, "pct": pct}
    except Exception:
        return None


def favorite_button_label(ticker):
    snap = load_favorite_snapshot_data(ticker)
    if not snap: return ticker
    price = snap["price"]
    pct   = snap["pct"]
    price_str = (f"{price:,.0f}" if price >= 1000
                 else f"{price:,.2f}" if price >= 10
                 else f"{price:.4f}")
    dot  = "🟢" if pct >= 0 else "🔴"
    sign = "+" if pct >= 0 else ""
    return f"{ticker}\n{dot} {price_str}  {sign}{pct:.1f}%"


@st.cache_data(ttl=300)
def load_stock_history(ticker):
    return yf.Ticker(ticker).history(period="2y")


@st.cache_data(ttl=300)
def load_stock_info(ticker):
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


def calc_pivot_points(df: pd.DataFrame) -> dict:
    prev  = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
    high  = prev["High"]; low = prev["Low"]; close = prev["Close"]
    pivot = (high + low + close) / 3
    return {
        "PP": pivot,
        "R1": 2 * pivot - low,
        "R2": pivot + (high - low),
        "R3": high + 2 * (pivot - low),
        "S1": 2 * pivot - high,
        "S2": pivot - (high - low),
        "S3": low - 2 * (high - pivot),
    }


def calc_fibonacci(df: pd.DataFrame, lookback: int = 60) -> dict:
    window = df.tail(lookback)
    high = window["High"].max(); low = window["Low"].min()
    dist = high - low
    return {
        "Fib 100%":  high,
        "Fib 78.6%": high - 0.786 * dist,
        "Fib 61.8%": high - 0.618 * dist,
        "Fib 50.0%": high - 0.500 * dist,
        "Fib 38.2%": high - 0.382 * dist,
        "Fib 23.6%": high - 0.236 * dist,
        "Fib 0%":    low,
    }


FIB_DESCRIPTIONS = {
    "Fib 100%":  ("🏔️ จุดสูงสุด (Swing High)",       "แนวต้านสูงสุด — ถ้าทะลุได้ Momentum แรงมาก ให้ Buy Breakout"),
    "Fib 78.6%": ("🛡️ แนวป้องกันสุดท้าย",            "ถ้าหลุดเตรียมคัต — ย่อลึกมากแสดงว่า Buyer อ่อนแรงแล้ว"),
    "Fib 61.8%": ("🥇 โซนสะสมไม้หลัก (Golden Ratio)", "Risk/Reward คุ้มที่สุด — สถาบันนิยมรอซื้อโซนนี้ เหมาะสะสมระยะกลาง-ยาว"),
    "Fib 50.0%": ("🥈 จุดกลาง Swing",                "แนวรับปานกลาง — ซื้อได้ แต่ Stop Loss ใกล้กว่าโซน 61.8%"),
    "Fib 38.2%": ("🥉 แนวรับตื้น",                   "เหมาะเล่นสั้นเด้งไว — ถ้าหลุดรอโซน 50% หรือ 61.8% แทน"),
    "Fib 23.6%": ("⚡ Shallow Pullback",              "ย่อน้อยมาก แสดงว่า Momentum แรง — ซื้อ Dip แต่ Stop แน่น"),
    "Fib 0%":    ("⚠️ จุดต่ำสุด (Swing Low)",         "ถ้าหลุดนี้ Breakdown — เตรียมคัทสถานะทันที อย่ารีบ Average Down"),
}

# สี gradient สำหรับแต่ละ Fibonacci level
FIB_COLORS = {
    "Fib 100%":  {"border": "#CE93D8", "text": "#CE93D8", "bg": "rgba(206,147,216,0.12)"},
    "Fib 78.6%": {"border": "#BA68C8", "text": "#BA68C8", "bg": "rgba(186,104,200,0.10)"},
    "Fib 61.8%": {"border": "#F48FB1", "text": "#F48FB1", "bg": "rgba(244,143,177,0.15)"},  # golden
    "Fib 50.0%": {"border": "#FFB74D", "text": "#FFB74D", "bg": "rgba(255,183,77,0.12)"},
    "Fib 38.2%": {"border": "#81C784", "text": "#81C784", "bg": "rgba(129,199,132,0.10)"},
    "Fib 23.6%": {"border": "#64B5F6", "text": "#64B5F6", "bg": "rgba(100,181,246,0.10)"},
    "Fib 0%":    {"border": "#CE93D8", "text": "#CE93D8", "bg": "rgba(206,147,216,0.08)"},
}


def calculate_indicators(df: pd.DataFrame):
    close = df["Close"]
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=13, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(com=13, min_periods=14, adjust=False).mean()
    rsi = 100 - (100 / (1 + (avg_gain / avg_loss)))
    sma21  = close.rolling(21).mean()
    sma50  = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    ema21  = close.ewm(span=21,  adjust=False).mean()
    ema50  = close.ewm(span=50,  adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    true_range = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - close.shift()).abs(),
        (df["Low"]  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr14 = true_range.ewm(com=13, min_periods=14, adjust=False).mean()
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line   = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist   = macd_line - signal_line
    return {
        "rsi": rsi, "sma21": sma21, "sma50": sma50, "sma200": sma200,
        "ema21": ema21, "ema50": ema50, "ema200": ema200,
        "atr14": atr14, "macd_line": macd_line, "signal_line": signal_line, "macd_hist": macd_hist,
    }


def render_custom_sr_chart(ticker, df, current_price, r2, r1, s1, s2, rsi_value):
    """กราฟเส้นสีม่วงพร้อมแนวรับ-ต้าน (Rocket Style)"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df['Close'], mode='lines', name='ราคาปิด',
        line=dict(color='#8b5cf6', width=2.5),
        fill='tozeroy', fillcolor='rgba(139,92,246,0.12)'
    ))
    n = len(df)
    x_positions = [
        df.index[int(n * 0.88)],
        df.index[int(n * 0.70)],
        df.index[int(n * 0.30)],
        df.index[int(n * 0.12)],
    ]

    def add_sr_line(fig, price_level, label, color, x_pos, yshift_val):
        if price_level is None or pd.isna(price_level): return
        fig.add_hline(y=price_level, line_dash="dash", line_color=color, line_width=1.5, opacity=0.80)
        fig.add_annotation(
            x=x_pos, y=price_level,
            text=f"<b>{label}  {price_level:.2f}</b>",
            showarrow=False,
            font=dict(color="white", size=11, family="monospace"),
            bgcolor=color, bordercolor="rgba(255,255,255,0.3)",
            borderwidth=1, borderpad=5, yshift=yshift_val, xanchor="center",
        )

    add_sr_line(fig, r2, "🔺 แนวต้าน 2", "rgba(34,197,94,0.85)",  x_positions[0], +14)
    add_sr_line(fig, r1, "🟢 แนวต้าน 1", "rgba(74,222,128,0.85)", x_positions[1], +14)
    add_sr_line(fig, s1, "🟠 แนวรับ 1",  "rgba(239,68,68,0.85)",  x_positions[2], -14)
    add_sr_line(fig, s2, "🔻 แนวรับ 2",  "rgba(220,38,38,0.85)",  x_positions[3], -14)
    fig.add_hline(
        y=current_price, line_dash="solid", line_color="rgba(168,85,247,0.9)", line_width=2,
        annotation_text=f"  ราคา {current_price:.2f}", annotation_position="right",
        annotation_font_color="#a855f7", annotation_font_size=12,
    )
    fig.update_layout(
        title=f"<span style='color:#a855f7'>●</span> ราคาปิด {ticker}  |  RSI: {rsi_value:.2f}",
        template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,15,24,0.6)',
        font=dict(color='#E5E5EA'), margin=dict(l=0, r=90, t=44, b=10),
        xaxis=dict(showgrid=False, showline=False, zeroline=False, color='#6b7280'),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', side='right', color='#9ca3af'),
        showlegend=False, height=420,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "📐 **แนวรับ-ต้าน คำนวณจาก Pivot Points (Floor Trader)**  |  "
        "PP = (High + Low + Close) ÷ 3 ของแท่งเทียนก่อนหน้า  |  "
        "R1 = 2×PP − Low  |  R2 = PP + (High − Low)  |  "
        "S1 = 2×PP − High  |  S2 = PP − (High − Low)"
    )


def ma_metric(col, label, ma_value, price):
    if ma_value is None or pd.isna(ma_value):
        col.metric(label, "ข้อมูลน้อย", "—"); return
    pct = ((price - ma_value) / ma_value) * 100
    is_up = price > ma_value
    num_color = "#34D399" if is_up else "#F87171"
    direction = "ขาขึ้น ↑" if is_up else "ขาลง ↓"
    sub_label  = f"{'สูง' if is_up else 'ต่ำ'}กว่า {abs(pct):.1f}%"
    col.markdown(f"""
<div style="background:rgba(255,255,255,0.08);backdrop-filter:blur(24px) saturate(220%);
     -webkit-backdrop-filter:blur(24px) saturate(220%);
     border:1px solid rgba(255,255,255,0.14);border-radius:22px;padding:20px 24px;
     box-shadow:0 8px 32px rgba(0,0,0,0.30),inset 0 1px 0 rgba(255,255,255,0.10);">
  <div class="gm-card-label" style="font-size:0.82rem;font-weight:700;letter-spacing:.07em;
              text-transform:uppercase;margin-bottom:8px;">{label}</div>
  <div style="font-size:1.40rem;font-weight:700;letter-spacing:-0.01em;color:{num_color}">{direction}</div>
  <div style="font-size:0.92rem;font-weight:600;color:{num_color};opacity:0.85;margin-top:5px">{sub_label}</div>
</div>""", unsafe_allow_html=True)


def render_ma_levels(ma_items, price, atr, side):
    valid = [(n, v) for n, v in ma_items
             if v is not None and not pd.isna(v)
             and (v <= price if side == "support" else v >= price)]
    if not valid:
        msg = ("ไม่มีแนวรับจากเส้นนี้ในตอนนี้" if side == "support"
               else "ไม่มีแนวต้านจากเส้นนี้ในตอนนี้")
        st.info(msg + " เพราะราคาอยู่ต่ำ/สูงกว่าเส้นค่าเฉลี่ยทั้งหมด หรือข้อมูลยังไม่ครบ 200 วัน")
        return
    cols = st.columns(len(valid))
    for col, (ma_name, ma_value) in zip(cols, valid):
        pct = ((price - ma_value) / ma_value) * 100
        if side == "support":
            col.markdown(f"#### 🟢 {ma_name}")
            col.caption(f"ราคาอยู่เหนือเส้น {abs(pct):.1f}%")
            col.metric("แนวรับที่ 1", f"{ma_value:.2f}", f"เส้น MA เอง (ห่าง {abs(price-ma_value):.2f})")
            col.metric("แนวรับที่ 2", f"{ma_value-atr:.2f}", f"MA − 1×ATR ({atr:.2f})")
            col.metric("แนวรับแข็งแกร่ง", f"{ma_value-2*atr:.2f}", "MA − 2×ATR")
        else:
            col.markdown(f"#### 🔴 {ma_name}")
            col.caption(f"ราคาอยู่ใต้เส้น {abs(pct):.1f}%")
            col.metric("แนวต้านที่ 1", f"{ma_value:.2f}", f"เส้น MA เอง (ห่าง {abs(price-ma_value):.2f})")
            col.metric("แนวต้านที่ 2", f"{ma_value+atr:.2f}", f"MA + 1×ATR ({atr:.2f})")
            col.metric("แนวต้านแข็งแกร่ง", f"{ma_value+2*atr:.2f}", "MA + 2×ATR")


def get_trend_text(current_price, sma50_value, sma200_value):
    if sma200_value is not None and not pd.isna(sma200_value):
        if current_price > sma200_value and sma50_value > sma200_value: return "ขาขึ้น (Golden Zone) 🟢"
        if current_price > sma50_value: return "ขาขึ้น 🟢"
        if current_price < sma200_value and sma50_value < sma200_value: return "ขาลง (Death Zone) 🔴"
        return "ขาลง 🔴"
    return "ขาขึ้น 🟢" if current_price > sma50_value else "ขาลง 🔴"


def _style_signal_html(label: str, color: str, bg: str) -> str:
    return (f'<span style="background:{bg};color:{color};border-radius:8px;'
            f'padding:3px 12px;font-weight:700;font-size:0.92rem;">{label}</span>')


def render_fib_table(fibs: dict, current_price: float, atr: float):
    """
    แสดง Fibonacci 7 ระดับด้วยกรอบ glass-morphism เหมือน SMA/EMA metric cards
    แต่ละระดับมีกรอบแยก สีต่างกัน แสดงราคา / ระยะห่าง / คำอธิบาย
    """
    FIB_ORDER = ["Fib 100%", "Fib 78.6%", "Fib 61.8%", "Fib 50.0%", "Fib 38.2%", "Fib 23.6%", "Fib 0%"]
    # สี border / accent สำหรับแต่ละ level
    FIB_ACCENT = {
        "Fib 100%":  {"border": "#CE93D8", "glow": "rgba(206,147,216,0.25)", "bg": "rgba(206,147,216,0.08)"},
        "Fib 78.6%": {"border": "#BA68C8", "glow": "rgba(186,104,200,0.22)", "bg": "rgba(186,104,200,0.07)"},
        "Fib 61.8%": {"border": "#F48FB1", "glow": "rgba(244,143,177,0.30)", "bg": "rgba(244,143,177,0.13)"},
        "Fib 50.0%": {"border": "#FFB74D", "glow": "rgba(255,183,77,0.25)",  "bg": "rgba(255,183,77,0.09)"},
        "Fib 38.2%": {"border": "#81C784", "glow": "rgba(129,199,132,0.22)", "bg": "rgba(129,199,132,0.08)"},
        "Fib 23.6%": {"border": "#64B5F6", "glow": "rgba(100,181,246,0.22)", "bg": "rgba(100,181,246,0.08)"},
        "Fib 0%":    {"border": "#9575CD", "glow": "rgba(149,117,205,0.22)", "bg": "rgba(149,117,205,0.08)"},
    }
    FIB_EMOJI = {
        "Fib 100%":  "🏔️", "Fib 78.6%": "🛡️", "Fib 61.8%": "🥇",
        "Fib 50.0%": "🥈", "Fib 38.2%": "🥉", "Fib 23.6%": "⚡", "Fib 0%": "⚠️",
    }
    FIB_ROLE = {
        "Fib 100%":  "Swing High", "Fib 78.6%": "แนวป้องกัน",
        "Fib 61.8%": "Golden Zone ★", "Fib 50.0%": "จุดกลาง",
        "Fib 38.2%": "แนวรับตื้น", "Fib 23.6%": "Shallow Dip", "Fib 0%": "Swing Low",
    }

    valid = [(k, fibs[k]) for k in FIB_ORDER if k in fibs and fibs[k] is not None and not pd.isna(fibs[k])]
    if not valid:
        st.warning("ไม่มีข้อมูล Fibonacci"); return

    cards_html = ""
    for key, val in valid:
        ac = FIB_ACCENT.get(key, {"border":"#a78bfa","glow":"rgba(167,139,250,0.20)","bg":"rgba(167,139,250,0.08)"})
        dist_pct  = (current_price - val) / val * 100
        dist_abs  = current_price - val
        is_near   = abs(dist_abs) <= atr * 0.55
        is_golden = key == "Fib 61.8%"
        dist_color = "#34D399" if dist_pct >= 0 else "#F87171"
        sign = "+" if dist_pct >= 0 else ""
        above_below = "เหนือ ↑" if dist_pct >= 0 else "ใต้ ↓"
        emoji = FIB_EMOJI.get(key, "📌")
        role  = FIB_ROLE.get(key, "")
        label = key.replace("Fib ", "")

        # กรอบพิเศษเมื่อราคาอยู่ใกล้
        if is_near:
            border_style = f"border:1.5px solid {ac['border']};box-shadow:0 0 0 2px {ac['glow']},0 6px 24px rgba(0,0,0,0.32),inset 0 1px 0 rgba(255,255,255,0.12);"
            near_chip = f'<span style="display:inline-block;font-size:0.58rem;font-weight:800;color:#fbbf24;background:rgba(251,191,36,0.18);border:1px solid rgba(251,191,36,0.45);border-radius:5px;padding:1px 6px;margin-left:5px;vertical-align:middle;">📍 ใกล้</span>'
        else:
            border_style = f"border:1px solid rgba(255,255,255,0.11);"
            near_chip = ""

        # Golden Zone label พิเศษ
        if is_golden:
            role_display = f'<span style="color:#F48FB1;font-weight:800;">{role}</span>'
        else:
            role_display = role

        # ราคา format
        if val >= 10000:   price_fmt = f"{val:,.0f}"
        elif val >= 100:   price_fmt = f"{val:,.2f}"
        elif val >= 1:     price_fmt = f"{val:.4f}"
        else:              price_fmt = f"{val:.6f}"

        cards_html += f"""
<div style="background:{ac['bg']};backdrop-filter:blur(22px) saturate(200%);
     -webkit-backdrop-filter:blur(22px) saturate(200%);
     border-radius:18px;padding:14px 16px 12px;
     {border_style}
     transition:transform 0.18s ease,box-shadow 0.18s ease;
     border-left:3px solid {ac['border']};">
  <!-- header row -->
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
    <span style="font-size:0.68rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;
          color:{ac['border']};opacity:0.9;">{label}</span>
    <span style="font-size:0.80rem;">{emoji}</span>
  </div>
  <!-- ราคา -->
  <div style="font-size:1.28rem;font-weight:900;color:#F5F5F7;letter-spacing:-0.02em;
       line-height:1;font-variant-numeric:tabular-nums;margin-bottom:5px;">
    {price_fmt}{near_chip}
  </div>
  <!-- ระยะห่างจากราคาปัจจุบัน -->
  <div style="font-size:0.82rem;font-weight:700;color:{dist_color};margin-bottom:5px;">
    {above_below}&nbsp;{sign}{abs(dist_pct):.1f}%
    <span style="font-size:0.70rem;font-weight:500;color:rgba(235,235,245,0.35);margin-left:4px;">
      ({sign}{abs(dist_abs):.2f})
    </span>
  </div>
  <!-- role label -->
  <div style="font-size:0.70rem;color:rgba(235,235,245,0.45);line-height:1.3;">{role_display}</div>
</div>"""

    # 7 cards ใน responsive grid
    st.markdown(f"""
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,155px),1fr));
     gap:10px;margin:8px 0 14px;">
  {cards_html}
</div>""", unsafe_allow_html=True)
    st.caption("📐 Swing High/Low ย้อนหลัง 60 วัน  ·  📍 ราคาอยู่ใกล้ (< ½ ATR)  ·  🥇 Golden Ratio 61.8% = โซนที่ดีที่สุด")


def render_trading_style(price, atr, pivots, fibs, values):
    st.markdown("### 🧠 สไตล์การเล่นหุ้น — เลือกให้ตรงนิสัย")
    sma50  = values.get("sma50");  sma200 = values.get("sma200")
    ema21  = values.get("ema21");  ema50  = values.get("ema50");  ema200 = values.get("ema200")
    rsi    = values.get("rsi");    macd   = values.get("macd");   signal = values.get("signal")
    hist   = values.get("macd_hist")

    with st.expander("⚡ Day Trade — เล่นสั้นมาก จบในวัน (ใช้ Pivot)", expanded=False):
        st.markdown('<p style="color:#888;font-size:0.92rem;margin-top:-6px;">เกาะระดับ Pivot เปิดเช้า ปิดก่อนเย็น ไม่ค้างคืน</p>', unsafe_allow_html=True)
        pp = pivots.get("PP"); r1 = pivots.get("R1"); r2 = pivots.get("R2"); r3 = pivots.get("R3")
        s1 = pivots.get("S1"); s2 = pivots.get("S2"); s3 = pivots.get("S3")
        if pp:
            above_pp = price >= pp
            bias_html = (_style_signal_html("▲ BULLISH BIAS","#22c55e","rgba(34,197,94,0.15)") if above_pp
                         else _style_signal_html("▼ BEARISH BIAS","#ef4444","rgba(239,68,68,0.15)"))
            st.markdown(f"**Bias วันนี้:** {bias_html}", unsafe_allow_html=True)
            st.markdown("")
            if above_pp:
                st.markdown("| ระดับ | ราคา | บทบาท |")
                st.markdown("|---|---|---|")
                for lvl, val, role in [("R3",r3,"🔴 แนวต้านแข็ง"),("R2",r2,"🔴 Target 2"),
                                        ("R1",r1,"🎯 Target 1 — ขายบางส่วน"),("PP",pp,"⭐ แนวกลาง"),
                                        ("S1",s1,"🟢 จุดรับหากถูกย่อ"),("S2",s2,"🛑 Stop Loss")]:
                    if val is not None:
                        mark = f"**← ราคาปัจจุบัน {price:.2f}**" if abs(price-val)<atr*0.3 else ""
                        st.markdown(f"| {lvl} | {val:.2f} | {role} {mark} |")
            else:
                st.markdown("| ระดับ | ราคา | บทบาท |"); st.markdown("|---|---|---|")
                for lvl, val, role in [("R1",r1,"🛑 Stop Loss"),("PP",pp,"⭐ แนวกลาง"),
                                        ("S1",s1,"🎯 Target 1"),("S2",s2,"🔵 Target 2"),("S3",s3,"🔵 Target 3")]:
                    if val is not None:
                        mark = f"**← ราคาปัจจุบัน {price:.2f}**" if abs(price-val)<atr*0.3 else ""
                        st.markdown(f"| {lvl} | {val:.2f} | {role} {mark} |")
            st.caption(f"ATR 14 = {atr:.2f} | ราคา {'เหนือ' if above_pp else 'ใต้'} PP {abs(price-pp):.2f}")
        else:
            st.warning("ไม่มีข้อมูล Pivot Points")

    with st.expander("🌊 Swing Trade — เล่นเป็นรอบ ย่อซื้อ-เด้งขาย (ใช้ Fibo)", expanded=False):
        st.markdown('<p style="color:#888;font-size:0.92rem;margin-top:-6px;">ซื้อตอนราคาย่อลงมาหา Fibo แล้วรอ Bounce ขึ้น</p>', unsafe_allow_html=True)
        if fibs:
            # FIX: ใช้ render_fib_table แทน markdown table เดิม
            render_fib_table(fibs, price, atr)

            # หาโซนที่ใกล้ที่สุดแล้ว show signal
            found_zone = None
            fib_strengths = {"Fib 61.8%": 3, "Fib 50.0%": 2, "Fib 38.2%": 2,
                             "Fib 78.6%": 1, "Fib 23.6%": 1, "Fib 100%": 0, "Fib 0%": 0}
            for fkey, fval in fibs.items():
                if fval is not None and abs(price - fval) <= atr * 0.5:
                    found_zone = (fkey, fval, fib_strengths.get(fkey, 0))
                    break

            if found_zone:
                fkey, fval, strength = found_zone
                if strength >= 3:
                    sig = _style_signal_html("🥇 Golden Zone — โซนซื้อที่ดีที่สุด!","#22c55e","rgba(34,197,94,0.18)")
                elif strength >= 2:
                    sig = _style_signal_html("📍 โซนรับ Fibo — รอสัญญาณ Buy","#22c55e","rgba(34,197,94,0.12)")
                elif fkey == "Fib 0%":
                    sig = _style_signal_html("⚠️ ใกล้จุดต่ำสุด — ระวัง Breakdown","#f59e0b","rgba(245,158,11,0.15)")
                else:
                    sig = _style_signal_html("📌 ใกล้แนวรับตื้น — รอยืนยันก่อน","#94a3b8","rgba(148,163,184,0.15)")
                st.markdown(f"**สัญญาณ:** {sig}", unsafe_allow_html=True)
        else:
            st.warning("ข้อมูล Fibonacci ไม่เพียงพอ")

    with st.expander("🏔️ Trend Follow — ถือยาวๆ กินคำโต (ใช้ SMA 21/50/200)", expanded=False):
        st.markdown('<p style="color:#888;font-size:0.92rem;margin-top:-6px;">ซื้อตอน Golden Cross ถือตราบที่เส้นยังเรียงลำดับ ขายตอน Death Cross</p>', unsafe_allow_html=True)
        sma21_ = values.get("sma21")
        sma_ok = sma50 is not None and not pd.isna(sma50)
        sma200_ok = sma200 is not None and not pd.isna(sma200)
        if sma_ok and sma200_ok:
            golden_zone = price > sma200 and sma50 > sma200
            death_zone  = price < sma200 and sma50 < sma200
            if golden_zone:
                zone_html = _style_signal_html("🌟 GOLDEN ZONE","#22c55e","rgba(34,197,94,0.15)")
                action = "**ถือต่อ** — ไม่ขาย ตราบที่ราคาอยู่เหนือ SMA200"
                stop_txt = f"Stop: หลุด SMA200 ({sma200:.2f}) → ออก"
            elif death_zone:
                zone_html = _style_signal_html("💀 DEATH ZONE","#ef4444","rgba(239,68,68,0.15)")
                action = "**ออกจากตลาด** — รอ Golden Cross"
                stop_txt = "ไม่ควรซื้อจนกว่า SMA50 จะข้าม SMA200"
            elif price > sma50:
                zone_html = _style_signal_html("🟢 ขาขึ้น — แต่ยังไม่ Golden","#86efac","rgba(134,239,172,0.15)")
                action = "**ถือได้** — แต่ระวัง SMA50 ยังไม่ข้าม SMA200"
                stop_txt = f"Stop: หลุด SMA50 ({sma50:.2f}) → ลดสัดส่วน"
            else:
                zone_html = _style_signal_html("🔴 ขาลง","#ef4444","rgba(239,68,68,0.15)")
                action = "**หลีกเลี่ยง** — รอราคากลับมาเหนือ SMA50"
                stop_txt = f"ไม่ซื้อจนกว่าราคาจะกลับมาเหนือ {sma50:.2f}"
            st.markdown(f"**โซนเทรนด์:** {zone_html}", unsafe_allow_html=True)
            st.markdown(f"**การกระทำ:** {action}")
            st.markdown(f"**จุดตัดสินใจ:** {stop_txt}")
            c1, c2, c3 = st.columns(3)
            c1.metric("SMA 50",  f"{sma50:.2f}",  f"{'เหนือ' if price>sma50 else 'ใต้'} {abs(price-sma50):.2f}")
            c2.metric("SMA 200", f"{sma200:.2f}", f"{'เหนือ' if price>sma200 else 'ใต้'} {abs(price-sma200):.2f}")
            cross = sma50 - sma200
            c3.metric("ห่างระหว่างเส้น", f"{abs(cross):.2f}", "Golden ✅" if cross>0 else "Death ❌")
        else:
            st.warning("ข้อมูลไม่เพียงพอ")

    with st.expander("🚀 Momentum — เกาะรถซิ่ง (ใช้ EMA 21/50/200 + MACD + RSI)", expanded=False):
        st.markdown('<p style="color:#888;font-size:0.92rem;margin-top:-6px;">เข้าตอน EMA เรียงตัว + MACD บวก + RSI เกิน 50</p>', unsafe_allow_html=True)
        ema_ok  = ema21 is not None and not pd.isna(ema21) and ema50 is not None and not pd.isna(ema50)
        ema200_ok = ema200 is not None and not pd.isna(ema200)
        rsi_ok  = rsi is not None and not pd.isna(rsi)
        macd_ok = macd is not None and not pd.isna(macd) and signal is not None and not pd.isna(signal)
        score = 0; checks = []
        if ema_ok:
            if price > ema21: score+=1; checks.append(("✅","ราคา > EMA21 — Short-term momentum บวก"))
            else: checks.append(("❌","ราคา < EMA21 — Short-term momentum ลบ"))
            if ema21 > ema50: score+=1; checks.append(("✅","EMA21 > EMA50 — Mid-term momentum บวก"))
            else: checks.append(("❌","EMA21 < EMA50 — Mid-term momentum ลบ"))
        if ema200_ok:
            if ema50 is not None and not pd.isna(ema50) and ema50 > ema200: score+=1; checks.append(("✅","EMA50 > EMA200 — Long-term momentum บวก"))
            else: checks.append(("❌","EMA50 < EMA200 — Long-term momentum ลบ"))
        if macd_ok:
            if macd > signal: score+=1; checks.append(("✅",f"MACD ({macd:.3f}) > Signal ({signal:.3f})"))
            else: checks.append(("❌",f"MACD ({macd:.3f}) < Signal ({signal:.3f})"))
            if hist is not None and not pd.isna(hist) and hist > 0: score+=1; checks.append(("✅",f"Histogram บวก ({hist:.3f}) — Momentum เร่ง"))
            else: checks.append(("❌","Histogram ลบ — Momentum ชะลอ"))
        if rsi_ok:
            if rsi >= 50: score+=1; checks.append(("✅",f"RSI {rsi:.1f} ≥ 50 — Momentum Zone"))
            else: checks.append(("❌",f"RSI {rsi:.1f} < 50 — ยังไม่เข้า Momentum Zone"))
        total = max(len(checks), 1); pct = score/total*100
        if pct>=80: sig_html=_style_signal_html(f"🚀 FULL MOMENTUM ({score}/{total}) — โดดขึ้นรถได้!","#22c55e","rgba(34,197,94,0.18)")
        elif pct>=60: sig_html=_style_signal_html(f"⚡ MOMENTUM กำลังสะสม ({score}/{total})","#f59e0b","rgba(245,158,11,0.15)")
        elif pct>=40: sig_html=_style_signal_html(f"⚖️ MIXED SIGNALS ({score}/{total})","#94a3b8","rgba(148,163,184,0.15)")
        else: sig_html=_style_signal_html(f"🛑 ไม่มี Momentum ({score}/{total}) — รอก่อน","#ef4444","rgba(239,68,68,0.15)")
        st.markdown(f"**สัญญาณ Momentum:** {sig_html}", unsafe_allow_html=True)
        st.markdown("")
        for icon, txt in checks: st.markdown(f"{icon} {txt}")
        if ema_ok and ema200_ok:
            st.markdown("")
            ce1, ce2, ce3 = st.columns(3)
            ce1.metric("EMA 21",  f"{ema21:.2f}",  f"{'↑' if price>ema21 else '↓'} {abs(price-ema21):.2f}")
            ce2.metric("EMA 50",  f"{ema50:.2f}",  f"{'↑' if price>ema50 else '↓'} {abs(price-ema50):.2f}")
            ce3.metric("EMA 200", f"{ema200:.2f}", f"{'↑' if price>ema200 else '↓'} {abs(price-ema200):.2f}")


def render_chart(df, indicators, pivots, fibs):
    st.caption("🎛️ เลือกชั้นที่ต้องการแสดง:")
    gc1, gc2, gc3, gc4, gc5, gc6 = st.columns(6)
    show_sma21  = gc1.checkbox("🟠 SMA 21",       value=True,  key="ch_sma21")
    show_ma_mid = gc2.checkbox("🔵🔴 SMA 50/200", value=True,  key="ch_sma_mid")
    show_ema21  = gc3.checkbox("🟡 EMA 21",       value=True,  key="ch_ema21")
    show_ema    = gc4.checkbox("🟢🟣 EMA 50/200", value=True,  key="ch_ema")
    show_pivot  = gc5.checkbox("📌 Pivot Points", value=True,  key="ch_pivot")
    show_fib    = gc6.checkbox("🌀 Fibonacci",    value=False, key="ch_fib")

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.2, 0.25], vertical_spacing=0.04,
        subplot_titles=("ราคา + Pivot + Fibonacci", "Volume", "MACD (12,26,9)"),
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="ราคา",
        increasing_line_color="#00897B", increasing_fillcolor="#26a69a",
        decreasing_line_color="#C62828", decreasing_fillcolor="#ef5350",
    ), row=1, col=1)
    if show_sma21:
        fig.add_trace(go.Scatter(x=df.index, y=indicators["sma21"],  name="SMA 21",  line=dict(color="#FFA726", width=1.2)), row=1, col=1)
    if show_ma_mid:
        fig.add_trace(go.Scatter(x=df.index, y=indicators["sma50"],  name="SMA 50",  line=dict(color="#29B6F6", width=2.2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=indicators["sma200"], name="SMA 200", line=dict(color="#FF5252", width=3.0)), row=1, col=1)
    if show_ema21:
        fig.add_trace(go.Scatter(x=df.index, y=indicators["ema21"],  name="EMA 21",  line=dict(color="#FFD740", width=1.5, dash="dot")), row=1, col=1)
    if show_ema:
        fig.add_trace(go.Scatter(x=df.index, y=indicators["ema50"],  name="EMA 50",  line=dict(color="#69F0AE", width=1.8, dash="dash")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=indicators["ema200"], name="EMA 200", line=dict(color="#CE93D8", width=2.8, dash="dashdot")), row=1, col=1)
    if show_pivot:
        pivot_styles = {
            "PP": ("white", 2, "dash"),
            "R1": ("#ef5350",1.2,"dot"),"R2": ("#ef5350",1.2,"dot"),"R3": ("#ef5350",1,"dot"),
            "S1": ("#26a69a",1.2,"dot"),"S2": ("#26a69a",1.2,"dot"),"S3": ("#26a69a",1,"dot"),
        }
        for name, value in pivots.items():
            color, width, dash = pivot_styles[name]
            fig.add_hline(y=value, line_dash=dash, line_color=color, line_width=width,
                          annotation_text=f"  {name} {value:.2f}", annotation_font_color=color,
                          annotation_position="right", row=1, col=1)
    if show_fib:
        fib_colors = {"Fib 100%":"#CE93D8","Fib 78.6%":"#BA68C8","Fib 61.8%":"#F48FB1",
                      "Fib 50.0%":"#FFB74D","Fib 38.2%":"#81C784","Fib 23.6%":"#64B5F6","Fib 0%":"#CE93D8"}
        for name, value in fibs.items():
            fig.add_hline(y=value, line_dash="longdash", line_color=fib_colors[name], line_width=0.8,
                          annotation_text=f"  {name} {value:.2f}", annotation_font_color=fib_colors[name],
                          annotation_position="left", row=1, col=1)
    vol_colors = ["#26a69a" if c >= o else "#ef5350" for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=vol_colors, showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=indicators["macd_line"],   name="MACD",   line=dict(color="#42A5F5", width=1.5)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=indicators["signal_line"], name="Signal", line=dict(color="#FFA726", width=1.5)), row=3, col=1)
    hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in indicators["macd_hist"]]
    fig.add_trace(go.Bar(x=df.index, y=indicators["macd_hist"], marker_color=hist_colors, showlegend=False), row=3, col=1)
    fig.add_hline(y=0, line_color="rgba(255,255,255,0.12)", line_width=1, row=3, col=1)
    fig.update_layout(
        height=700, template="plotly_dark",
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(10,15,24,0.6)",
        font=dict(color="#E5E5EA", family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"),
        legend=dict(orientation="h", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(20,20,30,0.80)", bordercolor="rgba(255,255,255,0.12)", borderwidth=1),
        margin=dict(l=60, r=130, t=50, b=10),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                     tickfont=dict(color="#9ca3af"), title_font=dict(color="#9ca3af"))
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                     tickfont=dict(color="#9ca3af"), title_font=dict(color="#9ca3af"))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("คำอธิบายเส้น:")
    lg1, lg2, lg3, lg4, lg5, lg6 = st.columns(6)
    lg1.markdown("🟠 **SMA 21** — ส้ม ทึบบาง\n21 วัน ระยะสั้น")
    lg2.markdown("🔵 **SMA 50** — ฟ้า ทึบ\n50 วัน ระยะกลาง")
    lg3.markdown("🔴 **SMA 200** — แดง ทึบหนา\n200 วัน ระยะยาว")
    lg4.markdown("🟡 **EMA 21** — เหลือง จุด\n21 วัน ถ่วงน้ำหนัก")
    lg5.markdown("🟢 **EMA 50** — เขียว ประ\n50 วัน ถ่วงน้ำหนัก")
    lg6.markdown("🟣 **EMA 200** — ม่วง ประยาว\n200 วัน ถ่วงน้ำหนัก")


def render_financials(info, current_price):
    sector   = info.get("sector", "N/A"); industry = info.get("industry", "N/A")
    target_price = info.get("targetMeanPrice"); recommendation_mean = info.get("recommendationMean")
    recommendation_key = info.get("recommendationKey") or "N/A"
    analyst_count = info.get("numberOfAnalystOpinions")
    business_summary = info.get("longBusinessSummary", "")
    currency = info.get("currency", "USD")
    currency_prefix = "฿" if currency == "THB" else "$"

    def _fmt_val(val, prefix="", decimals=2):
        if val is None or (isinstance(val, float) and pd.isna(val)): return "N/A"
        return f"{prefix}{val:.{decimals}f}"

    if business_summary:
        st.markdown("#### 🏢 เกี่ยวกับบริษัท")
        with st.spinner("กำลังแปลภาษา..."):
            thai_summary = translate_to_thai(business_summary)
        st.markdown(f"""
<div style="background:rgba(139,92,246,0.10);border-left:4px solid #8b5cf6;
            border-radius:12px;padding:16px 20px;margin:4px 0;
            font-size:1.02rem;line-height:1.75;color:#E5E5EA;">
  {thai_summary}
</div>""", unsafe_allow_html=True)

    st.markdown(f"**กลุ่มธุรกิจ:** {sector}  |  **อุตสาหกรรม:** {industry}")
    st.markdown("---")
    st.markdown("#### 🎯 เป้าหมายนักวิเคราะห์")
    a1, a2, a3 = st.columns(3)
    upside = ((target_price - current_price) / current_price * 100) if target_price is not None else None
    a1.metric("เป้าราคาเฉลี่ย", _fmt_val(target_price, prefix=currency_prefix, decimals=2),
              f"{upside:+.1f}% upside" if upside is not None else None)
    a2.metric("คำแนะนำ", recommendation_key.upper() if recommendation_key != "N/A" else "N/A",
              f"score {recommendation_mean:.1f}/5" if recommendation_mean is not None else None)
    a3.metric("จำนวนนักวิเคราะห์", str(analyst_count) if analyst_count is not None else "N/A")


def render_support_resistance(current_price, current_atr, pivots, fibs, values):
    st.caption("หมายเหตุ: แนวรับจาก SMA/EMA จะแสดงเฉพาะเส้นที่อยู่ใต้ราคา ส่วนแนวต้านจะแสดงเฉพาะเส้นที่อยู่เหนือราคาปัจจุบัน")
    sr_t1, sr_t2, sr_t3, sr_t4, sr_t5, sr_t6 = st.tabs([
        "📌 Pivot Points", "🌀 Fibonacci",
        "🟢 SMA แนวรับ", "🔴 SMA แนวต้าน",
        "🟢 EMA แนวรับ", "🔴 EMA แนวต้าน",
    ])
    with sr_t1:
        st.markdown('<span style="background:rgba(99,102,241,0.15);color:#6366F1;border-radius:8px;padding:3px 12px;font-weight:700;font-size:0.88rem;">⚡ เหมาะ Day Trade — เล่นสั้นจบในวัน</span>', unsafe_allow_html=True)
        st.caption("คำนวณจาก: PP = (High + Low + Close) ÷ 3 ของวันก่อนหน้า  |  R/S = สูตร Floor Trader Pivot มาตรฐาน")
        pc1, pc2, pc3 = st.columns(3)
        pc1.markdown("### 🟢 แนวรับ")
        pc1.metric("แนวรับที่ 1 (S1)", f"{pivots['S1']:.2f}", f"{((current_price-pivots['S1'])/current_price*100):+.1f}%")
        pc1.metric("แนวรับที่ 2 (S2)", f"{pivots['S2']:.2f}", f"{((current_price-pivots['S2'])/current_price*100):+.1f}%")
        pc1.metric("แนวรับแข็งแกร่ง (S3)", f"{pivots['S3']:.2f}", f"{((current_price-pivots['S3'])/current_price*100):+.1f}%")
        pc2.markdown("### ⚪ จุดหมุน")
        pc2.metric("Pivot Point (PP)", f"{pivots['PP']:.2f}", f"{((current_price-pivots['PP'])/current_price*100):+.1f}%")
        pc3.markdown("### 🔴 แนวต้าน")
        pc3.metric("แนวต้านที่ 1 (R1)", f"{pivots['R1']:.2f}", f"{((current_price-pivots['R1'])/current_price*100):+.1f}%")
        pc3.metric("แนวต้านที่ 2 (R2)", f"{pivots['R2']:.2f}", f"{((current_price-pivots['R2'])/current_price*100):+.1f}%")
        pc3.metric("แนวต้านแข็งแกร่ง (R3)", f"{pivots['R3']:.2f}", f"{((current_price-pivots['R3'])/current_price*100):+.1f}%")

    with sr_t2:
        # FIX: ใช้ render_fib_table แทน markdown ธรรมดา
        st.markdown('<span style="background:rgba(34,197,94,0.15);color:#16a34a;border-radius:8px;padding:3px 12px;font-weight:700;font-size:0.88rem;">🌊 เหมาะ Swing Trade — ย่อซื้อ เด้งขาย</span>', unsafe_allow_html=True)
        st.caption("คำนวณจาก: Swing High และ Swing Low ของราคาย้อนหลัง 60 วัน  |  ระดับ 0% / 23.6% / 38.2% / 50% / 61.8% / 78.6% / 100%")
        render_fib_table(fibs, current_price, current_atr)

    with sr_t3:
        st.markdown('<span style="background:rgba(59,130,246,0.15);color:#2563eb;border-radius:8px;padding:3px 12px;font-weight:700;font-size:0.88rem;">🏔️ เหมาะ Trend Follow — ถือยาว ไม่หลุดเทรนด์ไม่ขาย</span>', unsafe_allow_html=True)
        st.caption(f"คำนวณจาก: ค่าเฉลี่ยราคาปิดย้อนหลัง 21 / 50 / 200 วัน  |  แสดงเฉพาะเส้นใต้ราคา {current_price:.2f}")
        render_ma_levels([("SMA 21",values["sma21"]),("SMA 50",values["sma50"]),("SMA 200",values["sma200"])], current_price, current_atr, "support")
    with sr_t4:
        st.markdown('<span style="background:rgba(59,130,246,0.15);color:#2563eb;border-radius:8px;padding:3px 12px;font-weight:700;font-size:0.88rem;">🏔️ เหมาะ Trend Follow — รู้แนวต้านก่อนเพิ่มสถานะ</span>', unsafe_allow_html=True)
        st.caption(f"คำนวณจาก: ค่าเฉลี่ยราคาปิดย้อนหลัง 21 / 50 / 200 วัน  |  แสดงเฉพาะเส้นเหนือราคา {current_price:.2f}")
        render_ma_levels([("SMA 21",values["sma21"]),("SMA 50",values["sma50"]),("SMA 200",values["sma200"])], current_price, current_atr, "resistance")
    with sr_t5:
        st.markdown('<span style="background:rgba(245,158,11,0.15);color:#d97706;border-radius:8px;padding:3px 12px;font-weight:700;font-size:0.88rem;">🚀 เหมาะ Momentum — เกาะรถซิ่ง ซื้อตอนวิ่งแรง</span>', unsafe_allow_html=True)
        st.caption(f"คำนวณจาก: EMA ถ่วงน้ำหนัก 21 / 50 / 200 วัน  |  แสดงเฉพาะเส้นใต้ราคา {current_price:.2f}")
        render_ma_levels([("EMA 21",values["ema21"]),("EMA 50",values["ema50"]),("EMA 200",values["ema200"])], current_price, current_atr, "support")
    with sr_t6:
        st.markdown('<span style="background:rgba(245,158,11,0.15);color:#d97706;border-radius:8px;padding:3px 12px;font-weight:700;font-size:0.88rem;">🚀 เหมาะ Momentum — รู้แนวต้าน EMA ก่อนโดดขึ้นรถ</span>', unsafe_allow_html=True)
        st.caption(f"คำนวณจาก: EMA ถ่วงน้ำหนัก 21 / 50 / 200 วัน  |  แสดงเฉพาะเส้นเหนือราคา {current_price:.2f}")
        render_ma_levels([("EMA 21",values["ema21"]),("EMA 50",values["ema50"]),("EMA 200",values["ema200"])], current_price, current_atr, "resistance")


# ══════════════════════════════════════════════════════════════════
# SESSION STATE INIT
# ══════════════════════════════════════════════════════════════════
if "favorites"       not in st.session_state: st.session_state.favorites     = load_favorites()
if "show_manage"     not in st.session_state: st.session_state.show_manage   = False
if "search_box"      not in st.session_state: st.session_state.search_box    = ""
if "auto_scan"       not in st.session_state: st.session_state.auto_scan     = False
if "current_stock"   not in st.session_state: st.session_state.current_stock = ""
if "market"          not in st.session_state: st.session_state.market        = "foreign"
if "quick_pick"      not in st.session_state: st.session_state.quick_pick    = ""
if "show_gainers"    not in st.session_state: st.session_state.show_gainers  = False
# FIX: เพิ่ม flag สำหรับ scroll หลัง rerun
if "should_scroll"   not in st.session_state: st.session_state.should_scroll = False

# ══════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div class="gm-header-wrap" style="padding:36px 4px 12px;">
  <div class="gm-header-title" style="font-size:2.2rem;font-weight:800;color:#F5F5F7;letter-spacing:-0.03em;
              line-height:1.1;font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display',sans-serif;">
    GEMUDA STATION
  </div>
  <div class="gm-header-sub" style="font-size:0.88rem;color:rgba(235,235,245,0.45);letter-spacing:0.03em;margin-top:7px;">
    เครื่องมือสแกนหุ้น &nbsp;·&nbsp; สัญญาณเทคนิค &nbsp;·&nbsp; แนวรับ-แนวต้าน
  </div>
</div>
""", unsafe_allow_html=True)

# ── FAVORITES ─────────────────────────────────────────────────────
st.markdown("📌 **NUKI ปักหมุด:**")
st.markdown('<span id="gm-fav-anchor"></span>', unsafe_allow_html=True)
favorites = st.session_state.favorites
fav_cols = st.columns(max(len(favorites), 1) + 1)
if favorites:
    for index, favorite in enumerate(favorites):
        if fav_cols[index].button(favorite_button_label(favorite), key=f"fav_{favorite}"):
            st.session_state.search_box    = favorite
            st.session_state.auto_scan     = True
            st.session_state.show_gainers  = False
            st.session_state.should_scroll = True   # FIX
            st.rerun()
else:
    fav_cols[0].info("ยังไม่มีหุ้นปักหมุด")
manage_label = "✏️ จัดการ" if not st.session_state.show_manage else "✖️ ปิด"
if fav_cols[-1].button(manage_label, key="manage_btn"):
    st.session_state.show_manage = not st.session_state.show_manage
    st.rerun()

if st.session_state.show_manage:
    with st.expander("📌 จัดการ NUKI ปักหมุด", expanded=True):
        col_add, col_list = st.columns([1, 2])
        with col_add:
            st.markdown("**เพิ่มหุ้นใหม่**")
            new_ticker = sanitize_ticker(st.text_input("ชื่อย่อหุ้น (เช่น AAPL, PTT.BK)", key="new_ticker_input"))
            add_col, reset_col = st.columns(2)
            if add_col.button("➕ เพิ่ม", key="add_fav_btn"):
                if not new_ticker: st.warning("กรุณาพิมพ์ชื่อหุ้นก่อนเพิ่ม")
                elif new_ticker in st.session_state.favorites: st.warning(f"{new_ticker} มีอยู่แล้ว")
                else:
                    st.session_state.favorites.append(new_ticker)
                    save_favorites(st.session_state.favorites)
                    st.success(f"เพิ่ม {new_ticker} แล้ว"); st.rerun()
            if reset_col.button("↩️ รีเซ็ต", key="reset_fav_btn"):
                st.session_state.favorites = DEFAULT_FAVORITES.copy()
                save_favorites(st.session_state.favorites); st.rerun()
        with col_list:
            st.markdown("**ลบออกจากรายการปักหมุด**")
            if st.session_state.favorites:
                for fav in list(st.session_state.favorites):
                    r1_c, r2_c = st.columns([3, 1])
                    r1_c.markdown(f"**{fav}**")
                    if r2_c.button("🗑️ ลบ", key=f"del_{fav}"):
                        st.session_state.favorites = [t for t in st.session_state.favorites if t != fav]
                        save_favorites(st.session_state.favorites); st.rerun()
            else:
                st.info("ยังไม่มีหุ้นปักหมุด")

st.markdown("---")

# ── MARKET SELECTOR + กระดานซิ่ง ─────────────────────────────────
_mb1, _mb2, _mb3 = st.columns([1, 1, 1])
if _mb1.button("🌍 หุ้นนอก", use_container_width=True,
               type="primary" if st.session_state.market == "foreign" else "secondary"):
    st.session_state.market = "foreign"
    st.session_state.quick_pick = ""; st.session_state.show_gainers = False; st.rerun()
if _mb2.button("🇹🇭 หุ้นไทย", use_container_width=True,
               type="primary" if st.session_state.market == "thai" else "secondary"):
    st.session_state.market = "thai"
    st.session_state.quick_pick = ""; st.session_state.show_gainers = False; st.rerun()
_gainer_label = "🔥 กระดานซิ่ง ✕" if st.session_state.show_gainers else "🔥 กระดานซิ่ง"
if _mb3.button(_gainer_label, use_container_width=True):
    st.session_state.show_gainers = not st.session_state.show_gainers; st.rerun()

# ── กระดานซิ่ง PANEL ─────────────────────────────────────────────
if st.session_state.show_gainers:
    _gr_col1, _gr_col2 = st.columns([5, 1])
    with _gr_col2:
        if st.button("🔄 รีเฟรช", key="refresh_gainers", use_container_width=True):
            fetch_us_gainers.clear(); st.rerun()
    with st.spinner("กำลังดึงข้อมูลหุ้นซิ่ง..."):
        _gainers, _mode, _err = fetch_us_gainers()
    _fetched_at = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%H:%M:%S")
    if _err:
        st.error(f"ดึงข้อมูลไม่สำเร็จ: {_err}")
    elif not _gainers:
        st.info("ไม่พบข้อมูล Gainers ในขณะนี้")
    else:
        _mode_label = ("📈 Pre-market Gainers (สหรัฐฯ) · ดีเลย์ ~15 นาทีจาก TradingView" if _mode == "pre"
                       else "📈 Today's Top Gainers (สหรัฐฯ) · ดีเลย์ ~15 นาทีจาก TradingView")
        st.markdown(f"**{_mode_label}**")
        st.caption(f"{'Pre-market ล่าสุด' if _mode=='pre' else 'ตลาดเปิดแล้ว'} — ดึงเมื่อ {_fetched_at} (GMT+7)")
        for _row_start in range(0, len(_gainers), 2):
            _gc1, _gc2 = st.columns(2)
            for _gcol, _g in zip([_gc1, _gc2], _gainers[_row_start:_row_start+2]):
                _rank     = _gainers.index(_g) + 1
                _pct      = _g["pct"]; _price = _g["price"]
                _gcol_hex = "#10b981" if _pct >= 0 else "#ef4444"
                _gcol_bg  = "rgba(16,185,129,0.15)" if _pct >= 0 else "rgba(239,68,68,0.15)"
                _gcol_bdr = "rgba(16,185,129,0.40)" if _pct >= 0 else "rgba(239,68,68,0.38)"
                _sign     = "+" if _pct >= 0 else ""
                _price_fmt= (f"{_price:,.0f}" if _price >= 1000
                             else f"{_price:,.2f}" if _price >= 10
                             else f"{_price:.4f}")
                _name_short = (_g['name'][:22] + "…") if len(_g['name']) > 22 else _g['name']
                with _gcol:
                    st.markdown(f"""
<div style="background:rgba(255,255,255,0.07);backdrop-filter:blur(22px) saturate(210%);
     -webkit-backdrop-filter:blur(22px) saturate(210%);
     border:1px solid rgba(255,255,255,0.13);border-radius:20px;
     padding:14px 16px 6px 16px;margin-bottom:2px;
     box-shadow:0 4px 18px rgba(0,0,0,0.30),inset 0 1px 0 rgba(255,255,255,0.08);">
  <div style="font-size:1.9rem;font-weight:900;color:rgba(235,235,245,0.25);
       letter-spacing:-0.04em;line-height:1;margin-bottom:2px;">{_rank}</div>
  <div style="font-size:1.55rem;font-weight:900;color:{_gcol_hex};
       letter-spacing:-0.02em;line-height:1.1;margin-bottom:3px;">{_g['ticker']}</div>
  <div style="font-size:0.72rem;font-weight:600;color:rgba(235,235,245,0.45);
       margin-bottom:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_name_short}</div>
  <div style="display:flex;justify-content:space-between;align-items:center;
       background:{_gcol_bg};border:1px solid {_gcol_bdr};border-radius:10px;padding:5px 10px;">
    <span style="font-size:0.80rem;font-weight:700;color:rgba(235,235,245,0.60);">${_price_fmt}</span>
    <span style="font-size:1.1rem;font-weight:900;color:{_gcol_hex};">{_sign}{_pct:.2f}%</span>
  </div>
</div>""", unsafe_allow_html=True)
                    if _gcol.button(f"📊 ดูกราฟ {_g['ticker']}", key=f"gainer_scan_{_g['ticker']}_{_rank}", use_container_width=True):
                        st.session_state.search_box    = _g["ticker"]
                        st.session_state.auto_scan     = True
                        st.session_state.show_gainers  = False
                        st.session_state.should_scroll = True   # FIX
                        st.rerun()

is_thai = st.session_state.market == "thai"

# ── Quick-pick popular tickers ────────────────────────────────────
if is_thai:
    quick_tickers = ["PTT", "KBANK", "AOT", "SCB", "DELTA", "CPALL", "ADVANC", "BBL", "GULF"]
    placeholder   = "พิมพ์ชื่อย่อหุ้น SET เช่น PTT, KBANK, AOT"
    st.caption("กดเลือกหุ้นยอดนิยม หรือพิมพ์ชื่อย่อ — ระบบเติม .BK ให้อัตโนมัติ")
else:
    quick_tickers = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "META", "AMZN", "BRK-B", "SPY"]
    placeholder   = "พิมพ์ ticker เช่น AAPL, TSLA, 9988.HK"
    st.caption("กดเลือกหุ้นยอดนิยม หรือพิมพ์ ticker โดยตรง — รองรับ US, HK, JP และอื่นๆ")

_qcols = st.columns(len(quick_tickers))
for _qcol, _qt in zip(_qcols, quick_tickers):
    if _qcol.button(_qt, key=f"qpick_{_qt}", use_container_width=True):
        st.session_state.search_box    = _qt
        st.session_state.quick_pick    = _qt
        st.session_state.auto_scan     = True
        st.session_state.show_gainers  = False
        st.session_state.should_scroll = True   # FIX
        st.rerun()

# ── Search input + scan button ────────────────────────────────────
_sc1, _sc2 = st.columns([4, 1])
_sc1.text_input("🔍", placeholder=placeholder, key="search_box", label_visibility="collapsed")
scan_btn = _sc2.button("🚀 สแกน", use_container_width=True, type="primary")

auto_scan = st.session_state.auto_scan
if auto_scan:
    st.session_state.auto_scan = False

_typed  = sanitize_ticker(st.session_state.search_box)
_picked = st.session_state.quick_pick
_raw    = _picked if _picked else _typed
st.session_state.quick_pick = ""

if is_thai and _raw and not _raw.upper().endswith(".BK"):
    target_stock = _raw + ".BK"
else:
    target_stock = _raw

if (scan_btn or auto_scan) and target_stock:
    st.session_state.current_stock = target_stock
    st.session_state.should_scroll = True   # FIX: set scroll flag เมื่อ scan button กด

show_analysis = bool(target_stock) and (
    scan_btn or auto_scan or st.session_state.current_stock == target_stock
)

# ══════════════════════════════════════════════════════════════════
# STOCK RESULT SECTION
# ══════════════════════════════════════════════════════════════════
if show_analysis:
    # วาง anchor ก่อน render ผล
    st.markdown('<div id="gm-result-anchor" style="scroll-margin-top:16px;"></div>', unsafe_allow_html=True)

    # SCROLL FIX: ใช้ _stc.html เพราะสร้าง iframe จริงทุกครั้ง ไม่ถูก deduplicate
    # JS ใน iframe เข้าถึง window.parent ได้เสมอ
    if st.session_state.should_scroll:
        st.session_state.should_scroll = False
        _stc.html("""
<script>
(function(){
  var tries = 0;
  function go(){
    try {
      var docs = [];
      if(window.parent && window.parent.document) docs.push(window.parent.document);
      docs.push(document);
      for(var i=0;i<docs.length;i++){
        var el = docs[i].getElementById('gm-result-anchor');
        if(el){ el.scrollIntoView({behavior:'smooth', block:'start'}); return; }
      }
    } catch(e){}
    if(tries++ < 40) setTimeout(go, 100);
  }
  setTimeout(go, 300);
})();
</script>""", height=0, scrolling=False)

    with st.spinner(f"กำลังดึงข้อมูลของ {target_stock}..."):
        try:
            stock = yf.Ticker(target_stock)
            df    = load_stock_history(target_stock)
            info  = load_stock_info(target_stock)

            if df.empty or len(df) < 20:
                st.error("❌ ไม่พบข้อมูลหุ้นนี้ หรือข้อมูลน้อยเกินไป — ตรวจสอบชื่อย่อหุ้นอีกครั้ง")
                _stc.html(f"""<script>(function(){{
  var tries=0;
  function say(){{ if(window.parent&&window.parent.gmTanukiSpeak) window.parent.gmTanukiSpeak('ไม่พบข้อมูลหุ้นนี้ ลองตรวจชื่อย่ออีกครั้งนะ','alert');
    else if(tries++<20) setTimeout(say,120); }}
  setTimeout(say,450);
}})();</script>""", height=0, scrolling=False)
            else:
                indicators    = calculate_indicators(df)
                current_price = float(df["Close"].iloc[-1])
                prev_price    = float(df["Close"].iloc[-2])
                price_change  = current_price - prev_price
                price_pct     = (price_change / prev_price) * 100
                current_rsi   = float(indicators["rsi"].iloc[-1])
                current_atr   = float(indicators["atr14"].iloc[-1])
                current_macd  = float(indicators["macd_line"].iloc[-1])
                current_signal= float(indicators["signal_line"].iloc[-1])
                pivots = calc_pivot_points(df)
                fibs   = calc_fibonacci(df, lookback=60)
                values = {
                    "sma21":     indicators["sma21"].iloc[-1],
                    "sma50":     indicators["sma50"].iloc[-1],
                    "sma200":    indicators["sma200"].iloc[-1] if not pd.isna(indicators["sma200"].iloc[-1]) else None,
                    "ema21":     indicators["ema21"].iloc[-1],
                    "ema50":     indicators["ema50"].iloc[-1],
                    "ema200":    indicators["ema200"].iloc[-1],
                    "rsi":       current_rsi,
                    "macd":      current_macd,
                    "signal":    current_signal,
                    "macd_hist": float(indicators["macd_hist"].iloc[-1]),
                }
                trend_text = get_trend_text(current_price, values["sma50"], values["sma200"])

                if current_rsi < 30:
                    idea, idea_color = "💡 RSI ต่ำ (Oversold): มีโอกาสรีบาวด์", "success"
                elif current_rsi > 70:
                    idea, idea_color = "⚠️ RSI สูง (Overbought): ระวังแรงขายทำกำไร", "error"
                elif current_price > pivots["R1"]:
                    idea, idea_color = "🚀 ราคาทะลุ Pivot R1: โมเมนตัมบวก", "success"
                elif current_price < pivots["S1"]:
                    idea, idea_color = "📉 ราคาหลุด Pivot S1: ระวัง S2", "error"
                else:
                    idea, idea_color = f"⚖️ ราคาอยู่ในกรอบ S1–R1 ({pivots['S1']:.2f} – {pivots['R1']:.2f}): ไซด์เวย์", "info"

                # Tanuki speech
                _rsi_v = current_rsi; _pct_v = price_pct
                if _rsi_v > 70:       _tnk_mood, _tnk_msg = "alert",   f"RSI {_rsi_v:.1f} สูงมาก ระวังแรงขายทำกำไร"
                elif current_price < pivots["S1"]: _tnk_mood, _tnk_msg = "alert", "ราคาหลุด S1 ระวังไหลต่อถึง S2"
                elif current_price > pivots["R1"]: _tnk_mood, _tnk_msg = "happy", "ราคาทะลุ R1 โมเมนตัมบวกกำลังมา"
                elif _rsi_v < 30:     _tnk_mood, _tnk_msg = "happy",   f"RSI {_rsi_v:.1f} ต่ำ มีโอกาสรีบาวด์"
                elif _pct_v <= -2:    _tnk_mood, _tnk_msg = "sad",     f"วันนี้ลง {_pct_v:.2f}% ระวังแรงขายต่อ"
                elif _pct_v >= 2:     _tnk_mood, _tnk_msg = "happy",   f"วันนี้บวก {_pct_v:.2f}% แนวโน้มดูแข็งแรง"
                else:                 _tnk_mood, _tnk_msg = "neutral", "ราคาอยู่ในกรอบ ยังไม่มีสัญญาณแรงมาก"
                _stc.html(f"""<script>(function(){{
  var msg={json.dumps(_tnk_msg,ensure_ascii=False)},mood={json.dumps(_tnk_mood)},tries=0;
  function say(){{ if(window.parent&&window.parent.gmTanukiSpeak) window.parent.gmTanukiSpeak(msg,mood);
    else if(tries++<20) setTimeout(say,120); }}
  setTimeout(say,550);
}})();</script>""", height=0, scrolling=False)

                company_name = info.get("longName", "") or info.get("shortName", "")
                currency     = info.get("currency", "USD")
                _pct_color   = "#34D399" if price_pct >= 0 else "#F87171"
                _arrow       = "▲" if price_pct >= 0 else "▼"
                _co_line     = f"{target_stock}  ·  {company_name}" if company_name else target_stock
                _updated_at  = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%d/%m/%Y  %H:%M:%S")

                # Pre/Post market price
                post_price  = info.get("postMarketPrice") or info.get("preMarketPrice") or 0
                post_pct    = ((post_price - current_price) / current_price * 100) if post_price and current_price else 0
                post_color  = "#34D399" if post_pct >= 0 else "#F87171"
                post_sign   = "+" if post_pct >= 0 else ""
                post_label  = "หลังตลาดปิด" if info.get("postMarketPrice") else "ก่อนตลาดเปิด"
                has_post    = bool(post_price and post_price != current_price)

                _post_html = ""
                if has_post:
                    _post_html = f"""
  <div style="margin-top:12px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.10);">
    <div style="font-size:0.75rem;color:rgba(235,235,245,0.50);font-weight:600;margin-bottom:4px;">💡 {post_label}</div>
    <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;">
      <span style="font-size:1.5rem;font-weight:800;color:#F5F5F7;">{post_price:.2f}</span>
      <span style="font-size:0.95rem;font-weight:700;color:{post_color};">{post_sign}{post_pct:.2f}%</span>
      <span style="font-size:0.75rem;color:rgba(235,235,245,0.45);">({currency})</span>
    </div>
  </div>"""

                st.markdown(f"""
<div style="background:rgba(255,255,255,0.08);backdrop-filter:blur(28px) saturate(220%);
     -webkit-backdrop-filter:blur(28px) saturate(220%);
     border:1px solid rgba(255,255,255,0.14);border-radius:26px;
     padding:22px 28px 18px 28px;margin-bottom:12px;
     box-shadow:0 8px 32px rgba(0,0,0,0.35),inset 0 1px 0 rgba(255,255,255,0.10);">
  <div style="font-size:1.05rem;font-weight:700;color:rgba(235,235,245,0.70);margin-bottom:10px;line-height:1.3;">
    {_co_line}
  </div>
  <div style="display:flex;align-items:baseline;gap:18px;flex-wrap:wrap;">
    <span style="font-size:2.75rem;font-weight:800;color:#ffffff;letter-spacing:-0.04em;line-height:1;
         font-variant-numeric:tabular-nums;">{current_price:.2f}</span>
    <span style="font-size:1.2rem;font-weight:700;color:{_pct_color};">
      {_arrow}&nbsp;{price_change:+.2f}&nbsp;&nbsp;{price_pct:+.2f}%
    </span>
    <span style="font-size:0.78rem;color:rgba(235,235,245,0.40);font-weight:500;">{currency}</span>
  </div>
  <div style="font-size:0.72rem;color:rgba(235,235,245,0.35);margin-top:8px;letter-spacing:0.02em;">
    ⏱ ดึงข้อมูลเมื่อ {_updated_at} (GMT+7)
  </div>
  {_post_html}
</div>""", unsafe_allow_html=True)

                _alert_cfg = {
                    "success": ("rgba(52,211,153,0.15)",  "#34D399", "#6EE7B7"),
                    "error":   ("rgba(248,113,113,0.15)", "#F87171", "#FCA5A5"),
                    "info":    ("rgba(96,165,250,0.15)",  "#60A5FA", "#93C5FD"),
                }
                _abg, _aborder, _atxt = _alert_cfg.get(idea_color, _alert_cfg["info"])
                st.markdown(f"""
<div style="background:{_abg};border-left:4px solid {_aborder};border-radius:14px;
     padding:14px 18px;margin-bottom:14px;font-size:1.05rem;font-weight:700;color:{_atxt};line-height:1.4;">
  {idea}
</div>""", unsafe_allow_html=True)

                if current_rsi >= 70:   _rsi_col, _rsi_sub = "#F87171", "Overbought 🔴"
                elif current_rsi >= 60: _rsi_col, _rsi_sub = "#FCD34D", "Bullish 🟡"
                elif current_rsi >= 31: _rsi_col, _rsi_sub = "#34D399", "Neutral 🟢"
                else:                   _rsi_col, _rsi_sub = "#67E8F9", "Oversold 💎"
                _vol_str = fmt_num(float(df["Volume"].iloc[-1]))

                def _kcard(col, label, value, sub, val_color="#F5F5F7"):
                    col.markdown(f"""
<div style="background:rgba(255,255,255,0.08);backdrop-filter:blur(24px) saturate(220%);
     -webkit-backdrop-filter:blur(24px) saturate(220%);
     border:1px solid rgba(255,255,255,0.13);border-radius:20px;padding:16px 18px;
     box-shadow:0 4px 20px rgba(0,0,0,0.28),inset 0 1px 0 rgba(255,255,255,0.10);
     height:100%;box-sizing:border-box;">
  <div style="font-size:0.72rem;font-weight:700;color:rgba(235,235,245,0.45);
       letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px;">{label}</div>
  <div style="font-size:1.55rem;font-weight:800;color:{val_color};
       letter-spacing:-0.02em;line-height:1;">{value}</div>
  <div style="font-size:0.82rem;font-weight:600;color:{val_color};
       opacity:0.82;margin-top:6px;">{sub}</div>
</div>""", unsafe_allow_html=True)

                _kc1, _kc2, _kc3, _kc4 = st.columns(4)
                _kcard(_kc1, "RSI (14)", f"{current_rsi:.1f}", _rsi_sub, _rsi_col)
                _kcard(_kc2, "MACD", "กำลังขึ้น ▲" if current_macd > current_signal else "กำลังลง ▼",
                       f"MACD {current_macd:.3f}",
                       "#34D399" if current_macd > current_signal else "#F87171")
                _trend_color = "#34D399" if "ขาขึ้น" in trend_text else "#F87171"
                _kcard(_kc3, "แนวโน้ม", trend_text,
                       f"vs SMA50: {((current_price-values['sma50'])/values['sma50']*100):+.1f}%" if values['sma50'] else "—",
                       _trend_color)
                _kcard(_kc4, "Volume", _vol_str, f"ATR {current_atr:.2f}", "#a78bfa")

                def _ma_badge(label, ma_val):
                    if ma_val is None or pd.isna(ma_val):
                        return (f'<span style="background:rgba(148,163,184,0.12);border:1px solid rgba(148,163,184,0.25);'
                                f'border-radius:20px;padding:5px 12px;font-size:0.78rem;font-weight:700;'
                                f'color:#64748b;white-space:nowrap;">{label} —</span>')
                    pct = (current_price - ma_val) / ma_val * 100
                    if pct >= 0:
                        bg, bdr, txt = "rgba(52,211,153,0.13)", "rgba(52,211,153,0.35)", "#6EE7B7"
                        sym, trend = "▲", "ขาขึ้น"
                    else:
                        bg, bdr, txt = "rgba(248,113,113,0.12)", "rgba(248,113,113,0.32)", "#FCA5A5"
                        sym, trend = "▼", "ขาลง"
                    return (f'<span style="background:{bg};border:1px solid {bdr};'
                            f'border-radius:22px;padding:8px 16px;font-weight:700;'
                            f'color:{txt};white-space:nowrap;display:inline-flex;align-items:center;gap:6px;">'
                            f'<span style="font-size:0.88rem;opacity:0.80;">{label}</span>'
                            f'<span style="font-size:1.05rem;font-weight:900;">{sym}{abs(pct):.1f}%</span>'
                            f'<span style="font-size:0.82rem;font-weight:800;">{trend}</span>'
                            f'</span>')

                _badges = "".join([
                    _ma_badge("SMA 21",  values["sma21"]),
                    _ma_badge("SMA 50",  values["sma50"]),
                    _ma_badge("SMA 200", values["sma200"]),
                    _ma_badge("EMA 21",  values["ema21"]),
                    _ma_badge("EMA 50",  values["ema50"]),
                    _ma_badge("EMA 200", values["ema200"]),
                ])
                st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:7px;margin:14px 0 4px 0;">{_badges}</div>',
                            unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                tab_chart, tab_company, tab_sr, tab_style, tab_news = st.tabs([
                    "📈 กราฟ", "🏢 บริษัท", "🎯 แนวรับ-ต้าน", "🧠 สไตล์", "📰 กล่องข่าว"
                ])

                with tab_chart:
                    try:
                        _cm_key = f"chart_mode_{target_stock}"
                        if _cm_key not in st.session_state:
                            st.session_state[_cm_key] = "rocket"
                        _cm1, _cm2 = st.columns(2)
                        if _cm1.button("💜 กราฟแนวรับ-ต้าน (Rocket)",
                                       use_container_width=True,
                                       type="primary" if st.session_state[_cm_key] == "rocket" else "secondary",
                                       key=f"cm_rocket_{target_stock}"):
                            st.session_state[_cm_key] = "rocket"
                        if _cm2.button("📊 กราฟเชิงลึก (Advanced)",
                                       use_container_width=True,
                                       type="primary" if st.session_state[_cm_key] == "advanced" else "secondary",
                                       key=f"cm_advanced_{target_stock}"):
                            st.session_state[_cm_key] = "advanced"
                        st.markdown("")
                        if st.session_state[_cm_key] == "rocket":
                            render_custom_sr_chart(
                                target_stock, df.tail(120), current_price,
                                pivots.get('R2'), pivots.get('R1'),
                                pivots.get('S1'), pivots.get('S2'), current_rsi
                            )
                        else:
                            render_chart(df, indicators, pivots, fibs)
                    except Exception as exc:
                        print(traceback.format_exc())
                        st.error("กราฟแสดงผลไม่ได้ชั่วคราว")
                        st.caption(str(exc))

                with tab_company:
                    try:
                        render_financials(info, current_price)
                    except Exception as exc:
                        print(traceback.format_exc())
                        st.error("ข้อมูลบริษัทแสดงผลไม่ได้ชั่วคราว")
                        st.caption(str(exc))

                with tab_sr:
                    try:
                        render_support_resistance(current_price, current_atr, pivots, fibs, values)
                    except Exception as exc:
                        print(traceback.format_exc())
                        st.error("แนวรับ-แนวต้านแสดงผลไม่ได้ชั่วคราว")
                        st.caption(str(exc))

                with tab_style:
                    try:
                        render_trading_style(current_price, current_atr, pivots, fibs, values)
                    except Exception as exc:
                        print(traceback.format_exc())
                        st.error("สไตล์การเล่นแสดงผลไม่ได้ชั่วคราว")
                        st.caption(str(exc))

                with tab_news:
                    try:
                        st.markdown("### 📰 ข่าวล่าสุด")
                        st.caption("แปลหัวข่าวเป็นภาษาไทยอัตโนมัติ — กดการ์ดเพื่อเปิดข่าวต้นฉบับ")
                        with st.spinner("กำลังดึงข่าวล่าสุด..."):
                            _news_items = fetch_stock_news(target_stock, max_items=8)
                        if not _news_items:
                            st.info("ไม่พบข่าวสำหรับหุ้นตัวนี้ในขณะนี้")
                        else:
                            for _ni in _news_items:
                                try:
                                    _title_th = translate_to_thai(_ni["title"])
                                except Exception:
                                    _title_th = _ni["title"]
                                _pub_str = ""
                                if _ni["published"]:
                                    try:
                                        _pub_str = datetime.fromtimestamp(
                                            _ni["published"], tz=ZoneInfo("Asia/Bangkok")
                                        ).strftime("%d/%m %H:%M")
                                    except Exception:
                                        pass
                                _meta = "  ".join(filter(None, [_ni.get("publisher",""), _pub_str]))
                                st.markdown(f"""
<a href="{_ni['link']}" target="_blank" style="text-decoration:none;">
<div style="border:1px solid rgba(255,255,255,0.10);
     border-radius:14px;padding:12px 16px;margin:8px 0;cursor:pointer;">
  <div style="font-size:0.70rem;color:rgba(235,235,245,0.38);margin-bottom:5px;">{_meta}</div>
  <div style="font-size:0.95rem;font-weight:700;color:#E5E5EA;line-height:1.45;">{_title_th}</div>
  <div style="font-size:0.72rem;color:rgba(235,235,245,0.30);margin-top:5px;font-style:italic;">{_ni['title']}</div>
</div>
</a>""", unsafe_allow_html=True)
                    except Exception as exc:
                        print(traceback.format_exc())
                        st.error("ดึงข่าวไม่ได้ชั่วคราว")
                        st.caption(str(exc))

        except Exception as exc:
            print(traceback.format_exc())
            st.error("เกิดข้อผิดพลาดในการดึงข้อมูล กรุณาลองใหม่อีกครั้ง")
            st.caption(str(exc))

st.markdown("---")
st.caption("⚠️ แอปพลิเคชันนี้ใช้คำนวณสัญญาณทางคณิตศาสตร์เบื้องต้น ไม่ใช่คำแนะนำการลงทุน")
