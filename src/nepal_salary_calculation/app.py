"""Streamlit UI: Nepal salary, TDS and pay-slip calculator (FY 2083/84)."""

from __future__ import annotations

import html
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import altair as alt
import nepali_datetime
import pandas as pd
import streamlit as st

from nepal_salary_calculation import dashboard
from nepal_salary_calculation import tax as t
from nepal_salary_calculation.tax import format_npr


def npr(value: float, decimals: int | None = None) -> str:
    """Lakh/crore formatted amount. Decimals appear only when the amount has them, unless `decimals` is given."""
    if decimals is None:
        decimals = 0 if round(value, 2) == round(value) else 2
    return format_npr(value, decimals)


npr_card = npr


SOURCES = [
    (
        "IRD Nepal - Inland Revenue Department (official)",
        "https://ird.gov.np/",
        "Administers the Income Tax Act, 2058 and publishes the annual natural-person tax rates. "
        "Always the final reference.",
    ),
    (
        "Tax rate applicable for Natural Person FY 2083-84 (RSA, chartered accountants)",
        "https://www.rsa.com.np/wp-content/uploads/2026/06/Natural-Person-Taxation-2083-84.pdf",
        "Summary of the IRD slabs and the list of allowed deductions.",
    ),
    (
        "Nepal Income Tax Slabs 2083/84 guide",
        "https://bipinsharma.info.np/research/nepal-income-tax-guide/",
        "Explains the common slab structure, deductions vs. rebates and how TDS works.",
    ),
]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Mukta:wght@400;500;600;700&family=Yatra+One&display=swap');
html, body, [class*="css"], .stApp, button, input, textarea { font-family: 'Mukta', sans-serif !important; }
h1, h2, h3, .np-display { font-family: 'Yatra One', 'Mukta', serif !important; letter-spacing: .2px; }
h2, h3 { color: #003893 !important; }
.stApp { background:
  radial-gradient(circle at 100% 0%, rgba(232,163,23,.12), transparent 35%),
  radial-gradient(circle at 0% 100%, rgba(200,16,46,.07), transparent 40%), #FFF8EC; }
.block-container { padding-top: 5.2rem; max-width: 1180px; }
header[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"], [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
[data-testid="stMain"] { scroll-behavior: smooth; }
.np-anchor { scroll-margin-top: 80px; height: 0; }

.np-nav { position: fixed; top: 0; left: 0; right: 0; z-index: 1000; height: 58px; display: flex;
  align-items: center; justify-content: space-between; padding: 0 max(20px, calc((100vw - 1180px) / 2));
  background: rgba(255,248,236,.93); backdrop-filter: blur(10px); border-bottom: 3px solid #C8102E;
  box-shadow: 0 4px 18px rgba(42,26,20,.08); }
.np-nav a { text-decoration: none; }
.np-nav .brand { font-family: 'Yatra One', serif; font-size: 1.25rem; color: #C8102E; display: flex; gap: 8px; align-items: center; }
.np-nav .brand .flag { height: 30px; width: auto; }
.np-nav .brand small { font-family: 'Mukta', sans-serif; color: #003893; font-size: .8rem; font-weight: 600; }
.np-nav .links { display: flex; gap: 4px; }
.np-nav .links a { color: #2A1A14; font-weight: 600; padding: 7px 14px; border-radius: 999px; font-size: .97rem; transition: all .15s; }
.np-nav .links a:hover { background: #C8102E; color: #fff; }
.np-nav .links a.cta { background: #003893; color: #fff; }
.np-nav .links a.cta:hover { background: #C8102E; }
@media (max-width: 820px) { .np-nav .links a:not(.cta) { display: none; } .np-nav .brand small { display: none; } }

.np-hero { position: relative; overflow: hidden; border-radius: 22px; padding: 46px 40px 50px;
  background: linear-gradient(120deg, #8E0C20 0%, #C8102E 45%, #003893 120%); color: #fff;
  box-shadow: 0 14px 34px rgba(142,12,32,.3); margin-bottom: 18px; }
.np-hero h1 { color: #fff !important; font-size: 2.9rem; margin: 0; line-height: 1.1; padding: 0; }
[data-testid="stHeaderActionElements"] { display: none !important; }
.np-hero .ne { font-family: 'Yatra One', serif; font-size: 1.45rem; color: #FFD77A; margin-top: 8px; }
.np-hero p { margin: 12px 0 0; opacity: .94; font-size: 1.1rem; max-width: 560px; }
.np-hero .chip { display: inline-block; margin: 16px 8px 0 0; padding: 3px 12px; border-radius: 999px;
  background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.3); font-size: .85rem; }
.np-hero .go { display: inline-block; margin-top: 22px; padding: 11px 26px; border-radius: 999px; background: #FFD77A;
  color: #5b0a17 !important; font-weight: 700; text-decoration: none; box-shadow: 0 6px 16px rgba(0,0,0,.25); }
.np-hero .go:hover { background: #fff; }
.np-hero svg { position: absolute; right: 0; bottom: 0; height: 100%; width: 50%; opacity: .75; pointer-events: none; z-index: 0; }
.np-hero > :not(svg) { position: relative; z-index: 1; }
.np-border { height: 12px; border-radius: 4px; margin: 0 0 8px;
  background-image: linear-gradient(135deg, #C8102E 25%, transparent 25%),
    linear-gradient(225deg, #C8102E 25%, transparent 25%),
    linear-gradient(45deg, #E8A317 25%, transparent 25%),
    linear-gradient(315deg, #E8A317 25%, #003893 25%);
  background-size: 24px 24px; background-position: 12px 0, 12px 0, 0 0, 0 0; opacity: .85; }

.sec { display: flex; gap: 16px; align-items: center; margin: 38px 0 14px; }
.sec .num { flex: none; width: 46px; height: 46px; border-radius: 50%; display: grid; place-items: center;
  background: #C8102E; color: #fff; font-family: 'Yatra One', serif; font-size: 1.3rem;
  box-shadow: 0 0 0 5px rgba(200,16,46,.15); }
.sec h2 { margin: 0; padding: 0; font-size: 1.7rem; }
.sec h2 em { font-style: normal; color: #E8A317; font-size: 1.1rem; margin-left: 6px; }
.sec p { margin: 2px 0 0; color: #6b5148; }

[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] .card-t) {
  background: #fff; border: 1px solid #ecd9b8; border-radius: 16px; box-shadow: 0 4px 16px rgba(42,26,20,.07); }
.card-t { display: flex; gap: 12px; align-items: center; margin-bottom: 6px; }
.card-t .ic { font-size: 1.5rem; width: 42px; height: 42px; display: grid; place-items: center; border-radius: 12px; background: #FFF3D6; }
.card-t b { display: block; font-family: 'Yatra One', serif; font-weight: 400; color: #8E0C20; font-size: 1.15rem; line-height: 1.2; }
.card-t small { color: #6b5148; font-size: .85rem; }
div[data-testid="stButton"] button { border-radius: 999px; border: 1.5px solid #C8102E; color: #C8102E; font-weight: 600; background: #fff; }
div[data-testid="stButton"] button:hover { background: #C8102E; color: #fff; border-color: #C8102E; }
div[data-testid="stDownloadButton"] button { border-radius: 999px; background: #003893; color: #fff; border: none; font-weight: 600; }

.np-foot { margin: 46px 0 10px; padding: 22px 26px; border-radius: 16px; background: #2A1A14; color: #f3e3c6; text-align: center; }
.np-foot a { color: #FFD77A; }
.np-foot .ne { font-family: 'Yatra One', serif; font-size: 1.2rem; color: #FFD77A; }

[data-testid="stMetric"] { background: #fff; border-radius: 14px; padding: 14px 16px;
  border-left: 5px solid #C8102E; box-shadow: 0 3px 12px rgba(42,26,20,.08); }
[data-testid="stMetricLabel"] p { color: #6b5148; font-weight: 600; }
[data-testid="stMetricValue"] { color: #2A1A14; font-weight: 700; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] > div { overflow: visible !important; text-overflow: clip !important;
  white-space: normal !important; overflow-wrap: anywhere; font-size: clamp(1.4rem, 2.2vw, 2.25rem); }
/* Cards three-across inside a half-width column (What if…): keep each number on one line */
[data-testid="stColumn"] [data-testid="stColumn"] [data-testid="stMetric"] { padding: 10px 10px 10px 12px; }
[data-testid="stColumn"] [data-testid="stColumn"] [data-testid="stMetricValue"],
[data-testid="stColumn"] [data-testid="stColumn"] [data-testid="stMetricValue"] > div {
  white-space: nowrap !important; overflow-wrap: normal; font-size: clamp(1rem, 1.55vw, 1.6rem); }
[data-testid="stColumn"] [data-testid="stColumn"] [data-testid="stMetricLabel"] p { font-size: .82rem; }
[data-testid="stColumn"] [data-testid="stColumn"] [data-testid="stMetricDelta"] { font-size: .78rem; }

button[data-baseweb="tab"] { font-weight: 600; font-size: 1.02rem; }
button[data-baseweb="tab"][aria-selected="true"] { color: #C8102E; }
div[data-baseweb="tab-highlight"] { background-color: #C8102E !important; height: 3px; }

.slip { background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 6px 22px rgba(42,26,20,.12);
  border: 1px solid #ecd9b8; margin: 6px 0 14px; }
.slip-head { background: linear-gradient(90deg, #003893, #1a56c4); color: #fff; padding: 14px 20px; }
.slip-head .t { font-family: 'Yatra One', serif; font-size: 1.25rem; }
.slip-head .s { opacity: .85; font-size: .9rem; }
.slip-body { display: grid; grid-template-columns: 1fr 1fr; }
.slip-col { padding: 14px 20px 8px; }
.slip-col + .slip-col { border-left: 2px dashed #e6cf9f; }
.slip-col h4 { margin: 0 0 8px; color: #C8102E; font-family: 'Yatra One', serif; font-weight: 400; font-size: 1.1rem; }
.slip table { width: 100%; border-collapse: collapse; }
.slip td { padding: 7px 0; border-bottom: 1px solid #f3e8d2; font-size: .98rem; }
.slip td.a { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }
.slip tr.tot td { border-top: 2px solid #2A1A14; border-bottom: none; font-weight: 700; padding-top: 10px; }
.slip tr.hi td { color: #C8102E; }
.slip-net { background: linear-gradient(90deg, #C8102E, #8E0C20); color: #fff; padding: 14px 20px;
  display: flex; justify-content: space-between; align-items: center; }
.slip-net .l { font-family: 'Yatra One', serif; font-size: 1.15rem; }
.slip-net .v { font-size: 1.7rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.slip-foot { padding: 9px 20px; background: #FFF3D6; color: #6b5148; font-size: .88rem; }
@media (max-width: 760px) { .slip-body { grid-template-columns: 1fr; } .np-hero svg { display: none; } }

.formula { background: #FFF3D6; border-left: 5px solid #E8A317; padding: 10px 14px; border-radius: 8px; margin: 6px 0 10px; }

.sheet-wrap { overflow-x: auto; border-radius: 14px; border: 1px solid #ecd9b8; background: #fff;
  box-shadow: 0 4px 16px rgba(42,26,20,.08); margin: 8px 0 14px; }
.sheet { border-collapse: separate; border-spacing: 0; width: 100%; font-size: .88rem; font-variant-numeric: tabular-nums; }
.sheet th, .sheet td { padding: 6px 10px; border-bottom: 1px solid #f3e8d2; border-right: 1px solid #f7efdf;
  text-align: right; white-space: nowrap; }
.sheet th:first-child, .sheet td:first-child { position: sticky; left: 0; z-index: 2; text-align: left; background: #fff;
  min-width: 250px; border-right: 2px solid #e6cf9f; }
.sheet td.ty { text-align: left; color: #6b5148; font-size: .78rem; min-width: 90px; }
.sheet thead th { background: #003893; color: #fff; font-weight: 600; position: sticky; top: 0; }
.sheet thead th:first-child { background: #003893; }
.sheet thead tr.st th { background: #f3e8d2; color: #2A1A14; font-size: .75rem; padding: 3px 10px; }
.sheet thead tr.st th.act { background: #d7e4ff; color: #003893; }
.sheet thead tr.st th.fc { background: #FFE9B8; color: #8a5a00; }
.sheet td.fc { background: #FFFBF1; }
.sheet tr.grp td { background: #8E0C20; color: #fff; font-family: 'Yatra One', serif; letter-spacing: .3px; text-align: left; }
.sheet tr.sum td { font-weight: 700; background: #FFF3D6; }
.sheet tr.sum td:first-child { background: #FFF3D6; }
.sheet tr.key td { font-weight: 700; color: #C8102E; background: #fff5f6; }
.sheet tr.key td:first-child { background: #fff5f6; }
.sheet td.na { color: #c9b99c; }
.sheet th.cur { background: #C8102E; }
.sheet td.cur { background: #FFF0F2; }
.pchips { margin: 2px 0 10px; }
.pchip { display: inline-block; margin: 0 8px 6px 0; padding: 3px 14px; border-radius: 999px; background: #FFF3D6;
  border: 1px solid #e6cf9f; color: #6b3a00; font-size: .88rem; font-weight: 600; }

/* Glass theme: translucent, blurred surfaces over a colourful fixed backdrop */
.stApp { background:
  radial-gradient(520px circle at 8% 12%, rgba(200,16,46,.28), transparent 70%),
  radial-gradient(620px circle at 92% 8%, rgba(0,56,147,.26), transparent 70%),
  radial-gradient(560px circle at 78% 88%, rgba(232,163,23,.30), transparent 70%),
  radial-gradient(480px circle at 12% 90%, rgba(0,56,147,.18), transparent 70%),
  linear-gradient(135deg, #FFF4E0 0%, #FBE7EC 50%, #E6EEFF 100%); background-attachment: fixed; }
.np-nav { background: rgba(255,255,255,.55); backdrop-filter: blur(18px) saturate(180%);
  -webkit-backdrop-filter: blur(18px) saturate(180%); border-bottom: 1px solid rgba(255,255,255,.7);
  box-shadow: 0 8px 32px rgba(31,38,135,.12), inset 0 -2px 0 rgba(200,16,46,.55); }
.np-nav .links a { background: transparent; }
.np-nav .links a.cta { background: rgba(0,56,147,.9); box-shadow: 0 4px 14px rgba(0,56,147,.35); }
.np-hero { background: linear-gradient(120deg, rgba(142,12,32,.88) 0%, rgba(200,16,46,.8) 45%, rgba(0,56,147,.85) 120%);
  border: 1px solid rgba(255,255,255,.45); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 16px 40px rgba(142,12,32,.28), inset 0 1px 0 rgba(255,255,255,.5); }
.np-hero .chip { background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.4);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); }
.np-hero .go { background: rgba(255,215,122,.92); backdrop-filter: blur(8px); }
.sec .num { background: rgba(200,16,46,.88); border: 1px solid rgba(255,255,255,.6);
  box-shadow: 0 6px 18px rgba(200,16,46,.35), inset 0 1px 0 rgba(255,255,255,.5); }
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] .card-t),
[data-testid="stMetric"], .slip, .sheet-wrap {
  background: rgba(255,255,255,.45) !important; border: 1px solid rgba(255,255,255,.7);
  backdrop-filter: blur(16px) saturate(160%); -webkit-backdrop-filter: blur(16px) saturate(160%);
  box-shadow: 0 8px 32px rgba(31,38,135,.12), inset 0 1px 0 rgba(255,255,255,.8); }
[data-testid="stMetric"] { border-left: 5px solid rgba(200,16,46,.85); }
.card-t .ic { background: rgba(255,255,255,.6); border: 1px solid rgba(255,255,255,.8); }
div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="select"] > div, textarea,
div:has(> input[type="text"]), div:has(> input[type="number"]), [data-testid="stNumberInputContainer"] {
  background: rgba(255,255,255,.5) !important; border-radius: 10px; }
div:has(> input[type="text"]), div:has(> input[type="number"]), div[data-baseweb="select"] > div {
  border: 1px solid rgba(255,255,255,.8) !important; box-shadow: inset 0 1px 3px rgba(31,38,135,.08); }
div[data-baseweb="select"] > div > div { background: transparent !important; }
div[data-testid="stButton"] button { background: rgba(255,255,255,.55); backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px); box-shadow: 0 4px 14px rgba(200,16,46,.12); }
div[data-testid="stButton"] button:hover { background: rgba(200,16,46,.9); }
div[data-testid="stDownloadButton"] button { background: rgba(0,56,147,.9); box-shadow: 0 4px 14px rgba(0,56,147,.3); }
[data-testid="stExpander"] details { background: rgba(255,255,255,.45); border: 1px solid rgba(255,255,255,.7);
  border-radius: 14px; backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  box-shadow: 0 6px 24px rgba(31,38,135,.10); }
.slip-foot, .formula { background: rgba(255,243,214,.6); }
.slip td, .sheet th, .sheet td { border-bottom-color: rgba(230,207,159,.45); }
.sheet th:first-child, .sheet td:first-child { background: rgba(255,255,255,.9); }
.sheet thead th, .sheet thead th:first-child { background: rgba(0,56,147,.92); }
.sheet tr.grp td { background: rgba(142,12,32,.9); }
.sheet tr.sum td, .sheet tr.sum td:first-child { background: rgba(255,243,214,.85); }
.sheet tr.key td, .sheet tr.key td:first-child { background: rgba(255,245,246,.85); }
.sheet td.fc { background: rgba(255,226,160,.28); color: #5b4630; font-style: italic; }
.sheet td.fc1, .sheet thead th.fc1 { border-left: 2px dashed #E8A317; }
.sheet tr.sum td.fc, .sheet tr.key td.fc { background: rgba(255,226,160,.5); }
.pchip { background: rgba(255,255,255,.55); border: 1px solid rgba(255,255,255,.8);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); }
.np-foot { background: rgba(42,26,20,.78); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,.2); }
</style>
"""

HERO = """
<div id="top" class="np-anchor"></div>
<nav class="np-nav">
<a class="brand" href="#top" target="_self"><svg class="flag" viewBox="0 0 26 32" role="img" aria-label="Flag of Nepal"><polygon points="1.5,1.5 23.5,15 11.5,15 23.5,30.5 1.5,30.5" fill="#DC143C" stroke="#003893" stroke-width="2" stroke-linejoin="round"/><circle cx="7" cy="10" r="2" fill="#fff"/><circle cx="7" cy="23.5" r="2.6" fill="#fff"/></svg> तलब गणक <small>Nepal Salary &amp; TDS</small></a>
<div class="links">
<a href="#calculator" target="_self">Calculator</a>
<a href="#payslip" target="_self">Pay slip</a>
<a href="#forecast" target="_self">Forecast</a>
<a href="#tds" target="_self">TDS</a>
<a href="#insights" target="_self">Dashboard</a>
<a href="#rules" target="_self">Rules &amp; sources</a>
<a class="cta" href="#calculator" target="_self">Start</a>
</div>
</nav>
<div class="np-hero">
<svg viewBox="0 0 600 200" preserveAspectRatio="xMaxYMax slice" aria-hidden="true">
<polygon points="0,200 120,90 190,140 300,30 420,150 480,100 600,190 600,200" fill="rgba(255,255,255,.14)"/>
<polygon points="300,30 270,72 292,66 306,84 322,64 340,74" fill="rgba(255,255,255,.55)"/>
<polygon points="120,90 100,118 118,112 130,124 146,108" fill="rgba(255,255,255,.4)"/>
<polygon points="80,200 230,110 330,200" fill="rgba(0,56,147,.55)"/>
<polygon points="330,200 470,95 600,200" fill="rgba(0,40,110,.6)"/>
<polygon points="470,95 452,122 468,118 480,130 494,114" fill="rgba(255,255,255,.5)"/>
</svg>
<h1>Know exactly what lands<br>in your account.</h1>
<div class="ne">नेपाल तलब तथा आयकर (टीडीएस) गणक</div>
<p>Pay slip, annual income forecast and a step-by-step income-tax (TDS) breakdown for the fiscal year 2083/84, built on the IRD slabs.</p>
<span class="chip">FY 2083/84 (2026/27)</span><span class="chip">SSF-aware</span><span class="chip">Monthly TDS</span><br>
<a class="go" href="#calculator" target="_self">Calculate my salary ↓</a>
</div>
<div class="np-border"></div>
"""

FOOTER = """
<div class="np-foot">
<div class="ne">नेपाल तलब गणक</div>
<div>Estimates for planning only. Rates from <a href="https://ird.gov.np/" target="_blank">IRD Nepal</a>. Nothing you enter leaves this page.</div>
</div>
"""

PAYMENT_KEYS = ("incentive", "festival", "encash")
PaymentRows = list[tuple[float, list[int]]]

DEFAULTS = {
    **{f"{k}_ids": [0] for k in PAYMENT_KEYS},
    "basic": None,
    "allowance": None,
    "incentive": None,
    "incentive_every": True,
    "incentive_months": [],
    "festival": None,
    "festival_every": False,
    "festival_months": [2],
    "encash": None,
    "encash_every": False,
    "encash_months": [],
    "ssf_enrolled": True,
    "ssf_full": True,
    "rf": None,
    "cit": None,
    "life": None,
    "health": None,
    "female": True,
    "name": "",
    "gender": "Male",
    "tax_as": "Single",
    "handicapped": False,
    "tds_method": t.TDS_PAYROLL,
}

SAMPLE = {
    **{f"{k}_ids": [0] for k in PAYMENT_KEYS},
    "basic": 60_000.0,
    "allowance": 40_000.0,
    "incentive": 50_000.0,
    "incentive_every": True,
    "festival": 60_000.0,  # one basic salary, paid in Ashwin (Dashain)
    "festival_every": False,
    "festival_months": [2],
    "encash": None,
    "encash_every": False,
    "encash_months": [],
    "rf": None,
    "cit": 23_067.0,  # smallest monthly CIT that fills the NPR 5,00,000 retirement deduction cap
    "ssf_enrolled": True,
    "ssf_full": True,
    "tds_method": t.TDS_PAYROLL,
}


def load_sample() -> None:
    st.session_state.update(SAMPLE)


def reset_inputs() -> None:
    st.session_state.update(DEFAULTS)


def auto_cit() -> None:
    """Set CIT to the smallest monthly amount that fills the retirement deduction cap."""
    ss = st.session_state

    entries = [
        t.MonthEntry(
            basic_salary=ss["basic"] or 0.0,
            allowance=ss["allowance"] or 0.0,
            project_incentive=amount_in_month(payment_rows("incentive"), m),
            festival_allowance=amount_in_month(payment_rows("festival"), m),
            leave_encashment=amount_in_month(payment_rows("encash"), m),
            retirement_fund=ss["rf"] or 0.0,
        )
        for m in range(12)
    ]
    settings = t.Settings(
        ssf_enrolled=ss["ssf_enrolled"],
        ssf_basis=t.SSF_BASIS_FULL if ss.get("ssf_full") else t.SSF_BASIS_EMPLOYEE,
    )
    ss["cit"] = t.min_monthly_cit(entries, settings)


def card_title(icon: str, title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="card-t"><span class="ic">{icon}</span><div><b>{title}</b>'
        f"<small>{subtitle}</small></div></div>",
        unsafe_allow_html=True,
    )


def section(anchor: str, num: int, title: str, ne: str, blurb: str) -> None:
    st.markdown(
        f'<div id="{anchor}" class="np-anchor"></div>'
        f'<div class="sec"><span class="num">{num}</span><div><h2>{title} <em>{ne}</em></h2>'
        f"<p>{blurb}</p></div></div>",
        unsafe_allow_html=True,
    )


def month_name(m: int) -> str:
    return f"{t.MONTHS[m]} ({t.MONTHS_NE[m]})"


def money_input(label: str, key: str, help_text: str | None = None) -> float:
    """Blank by default (None) and returned as 0.0 so the maths never sees None."""
    value = st.number_input(
        label, min_value=0.0, step=1000.0, format="%.10g", value=None, placeholder="0", key=key, help=help_text
    )
    return float(value or 0.0)


def payment_field(key: str, row_id: int) -> str:
    """Session-state key of a payment row; row 0 keeps the original key."""
    return key if row_id == 0 else f"{key}_{row_id}"


def payment_rows(key: str) -> PaymentRows:
    """(amount, months) of every row of a payment, read back from the widgets' session state."""
    ss = st.session_state
    rows = []
    for row_id in ss.get(f"{key}_ids", [0]):
        field = payment_field(key, row_id)
        months = list(range(12)) if ss.get(f"{field}_every") else list(ss.get(f"{field}_months") or [])
        rows.append((float(ss.get(field) or 0.0), months))
    return rows


def amount_in_month(rows: PaymentRows, month: int) -> float:
    return sum(amount for amount, months in rows if month in months)


def add_payment_row(key: str) -> None:
    ids = st.session_state[f"{key}_ids"]
    st.session_state[f"{key}_ids"] = [*ids, max(ids) + 1]


def remove_payment_row(key: str, row_id: int) -> None:
    st.session_state[f"{key}_ids"] = [i for i in st.session_state[f"{key}_ids"] if i != row_id]


def payment(label: str, key: str) -> PaymentRows:
    """A payment with one or more rows, each with its own amount and the months it is paid in."""
    ids = st.session_state[f"{key}_ids"]
    for pos, row_id in enumerate(ids):
        field = payment_field(key, row_id)
        with st.container(border=bool(pos)):
            if pos:
                head, remove = st.columns([3, 2], vertical_alignment="center")
                head.markdown(f"**Amount #{pos + 1}**")
                remove.button("✕ Remove", key=f"{field}_remove", on_click=remove_payment_row, args=(key, row_id), width="stretch")
            title = f"{label} (per payment)" if len(ids) == 1 else f"{label} #{pos + 1} (per payment)"
            money_input(title if not pos else "Amount (per payment)", field)
            every = st.checkbox("Paid every month", key=f"{field}_every")
            if not every:
                st.multiselect(
                    "Paid in month(s)",
                    range(12),
                    format_func=month_name,
                    key=f"{field}_months",
                    placeholder="Choose months",
                )
    st.button(
        "＋ Add another amount",
        key=f"{key}_add",
        on_click=add_payment_row,
        args=(key,),
        help=f"Use this when {label.lower()} differs between months, e.g. 20,000 in Mangsir and 35,000 in Magh.",
        width="stretch",
    )
    return payment_rows(key)


def collect_inputs() -> tuple[dict, t.Settings]:
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)

    actions = st.columns([1, 1, 3])
    actions[0].button("✨ Load sample payslip", on_click=load_sample, width="stretch")
    actions[1].button("↺ Reset", on_click=reset_inputs, width="stretch")
    actions[2].caption("All amounts are in NPR. Basic salary, allowance, CIT and retirement fund are monthly.")

    with st.container(border=True):
        card_title("👤", "Taxpayer profile", "Used on the pay slip and for rebates")
        pf1, pf2, pf3, pf4 = st.columns(4)
        with pf1:
            st.text_input("Name", key="name", placeholder="Your name")
        with pf2:
            gender = st.radio("Gender", ["Male", "Female"], horizontal=True, key="gender")
        with pf3:
            tax_as = st.selectbox(
                "Tax paid as",
                ["Single", "Couple"],
                key="tax_as",
                help="FY 2083/84 uses one common slab table, so this does not change the tax.",
            )
        with pf4:
            handicapped = st.checkbox(
                "Person with disability",
                key="handicapped",
                help="Extra deduction of 50% of the exemption limit (NPR 5,00,000).",
            )
        female = False
        if gender == "Female":
            female = st.checkbox(
                "Apply 10% rebate (income is remuneration only)",
                key="female",
                help="10% reduction of tax for a resident woman whose income is remuneration only.",
            )

    with st.container(border=True):
        card_title("💼", "Monthly pay", "Your regular monthly salary and retirement deductions")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            basic = money_input("Basic salary", "basic")
        with c2:
            allowance = money_input("Allowance", "allowance")
        with c3:
            cit = money_input(
                "CIT deduction",
                "cit",
                "Retirement deductions (SSF + CIT + fund) stop saving tax at NPR 5,00,000 a year or ⅓ of income, "
                "whichever is lower. The button sets the smallest CIT that reaches that limit.",
            )
            st.button("⚡ Minimum for max tax saving", on_click=auto_cit, key="auto_cit_btn", width="stretch")
        with c4:
            rf = money_input("Retirement fund / EPF", "rf")

    with st.container(border=True):
        card_title("🎁", "Incentives & one-offs", "Pick the months each payment is received, or tick “every month”")
        p1, p2, p3 = st.columns(3)
        with p1:
            incentive = payment("Project incentive", "incentive")
        with p2:
            festival = payment("Festival allowance", "festival")
        with p3:
            encash = payment("Leave/Extra Encashment", "encash")

    s1, s2, s3 = st.columns(3)
    with s1, st.container(border=True):
        card_title("🛡️", "Social Security Fund", "11% employee + 20% employer on basic")
        ssf_enrolled = st.checkbox(
            "Enrolled in SSF",
            key="ssf_enrolled",
            help="SSF contributors do not pay the 1% Social Security Tax on the first slab.",
        )
        ssf_full = False
        if ssf_enrolled:
            ssf_full = st.checkbox(
                "Payslip shows employer 20% as income and deducts the full 31%",
                key="ssf_full",
                help="How most payrolls print it: 'SSF Contribution' (20%) is added to gross income and "
                "'SSF Deduction' (31%) is deducted. Untick if your payslip only deducts the 11% employee share.",
            )
    with s2, st.container(border=True):
        card_title("🧾", "Other deductions", "Optional, used for tax")
        life = money_input("Life insurance premium (annual)", "life", "Deduction capped at NPR 40,000.")
        health = money_input("Health insurance premium (annual)", "health", "Deduction capped at NPR 20,000.")
    with s3, st.container(border=True):
        card_title("🧮", "Monthly TDS method", "How tax is spread across the year")
        method = st.radio(
            "Monthly TDS method",
            [t.TDS_PAYROLL, t.TDS_EVEN],
            format_func={
                t.TDS_PAYROLL: "Payroll style: remaining tax ÷ remaining months",
                t.TDS_EVEN: "Simple: annual tax ÷ 12",
            }.get,
            key="tds_method",
            label_visibility="collapsed",
        )

    base = {
        "basic": basic,
        "allowance": allowance,
        "incentive": incentive,
        "festival": festival,
        "encash": encash,
        "rf": rf,
        "cit": cit,
    }
    settings = t.Settings(
        ssf_enrolled=ssf_enrolled,
        ssf_basis=t.SSF_BASIS_FULL if ssf_full else t.SSF_BASIS_EMPLOYEE,
        female_rebate=female,
        handicapped=handicapped,
        couple=tax_as == "Couple",
        name=st.session_state.get("name", "").strip(),
        gender=gender,
        life_insurance=life,
        health_insurance=health,
        tds_method=method,
        standard_cit=cit,
        standard_retirement_fund=rf,
    )
    return base, settings


COLS = {
    "basic_salary": "Basic Salary",
    "allowance": "Allowance",
    "project_incentive": "Project Incentive",
    "festival_allowance": "Festival Allowance",
    "leave_encashment": "Leave/Extra Encashment",
    "cit": "CIT",
    "retirement_fund": "Retirement Fund",
}


def default_table(base: dict) -> pd.DataFrame:
    rows = []
    for m in range(12):
        rows.append(
            {
                "Month": t.MONTHS[m],
                COLS["basic_salary"]: base["basic"],
                COLS["allowance"]: base["allowance"],
                COLS["project_incentive"]: amount_in_month(base["incentive"], m),
                COLS["festival_allowance"]: amount_in_month(base["festival"], m),
                COLS["leave_encashment"]: amount_in_month(base["encash"], m),
                COLS["cit"]: base["cit"],
                COLS["retirement_fund"]: base["rf"],
            }
        )
    return pd.DataFrame(rows)


def month_editor(base: dict) -> list[t.MonthEntry]:
    df = default_table(base)
    signature = abs(hash(tuple(df.itertuples(index=False, name=None))))
    with st.expander("✏️ Month-by-month amounts (edit any cell, e.g. a CIT catch-up or a mid-year increment)"):
        st.caption(
            "Pre-filled from the inputs above. Changing them regenerates this table. "
            "Payroll-style TDS only 'knows' about months up to the one being processed."
        )
        edited = st.data_editor(
            df,
            key=f"month_table_{signature}",
            hide_index=True,
            disabled=["Month"],
            width="stretch",
            column_config={
                c: st.column_config.NumberColumn(c, min_value=0.0, step=500.0, format="%.10g")
                for c in df.columns
                if c != "Month"
            },
        )
    edited = edited.fillna(0.0)
    return [
        t.MonthEntry(**{field: float(row[label]) for field, label in COLS.items()})
        for _, row in edited.iterrows()
    ]


def slip_rows(items: list[tuple[str, float, str]]) -> str:
    return "".join(
        f'<tr class="{cls}"><td>{label}</td><td class="a">{npr(v)}</td></tr>' for label, v, cls in items
    )


def slip_html(slip: t.MonthlySlip, settings: t.Settings) -> str:
    e = slip.entry
    earn = [("Basic Salary", e.basic_salary, "")]
    for label, v in [
        ("Allowance", e.allowance),
        ("Project Incentive", e.project_incentive),
        ("SSF Contribution (employer 20%)", slip.ssf_income),
        ("Festival Allowance", e.festival_allowance),
        ("Leave/Extra Encashment", e.leave_encashment),
    ]:
        if v:
            earn.append((label, v, ""))
    earn.append(("Gross Income", slip.gross_income, "tot"))

    ssf_label = "SSF Deduction (31%)" if settings.ssf_basis == t.SSF_BASIS_FULL else "SSF Deduction (11%)"
    ded = []
    for label, v in [
        ("CIT", e.cit),
        ("Retirement Fund / EPF", e.retirement_fund),
        (ssf_label, slip.ssf_deduction),
    ]:
        if v:
            ded.append((label, v, ""))
    ded.append(("TDS (income tax)", slip.tds, "hi"))
    ded.append(("Total Deduction", slip.total_deductions, "tot"))

    foot = ""
    if slip.ssf_employer:
        foot = (
            f'<div class="slip-foot">Total deposited to your SSF account this month: '
            f"<b>NPR {npr(slip.ssf_employer + slip.ssf_employee)}</b> "
            f"(employer {npr(slip.ssf_employer)} + employee {npr(slip.ssf_employee)}).</div>"
        )
    idx = slip.index
    return (
        '<div class="slip">'
        f'<div class="slip-head"><div class="t">Pay slip · {t.MONTHS[idx]} {t.MONTHS_NE[idx]}</div>'
        f'<div class="s">{t.month_title(idx)} · FY {t.FISCAL_YEAR}'
        + (f" · {html.escape(settings.name)}" if settings.name else "")
        + "</div></div>"
        '<div class="slip-body">'
        f'<div class="slip-col"><h4>Earnings</h4><table>{slip_rows(earn)}</table></div>'
        f'<div class="slip-col"><h4>Deductions</h4><table>{slip_rows(ded)}</table></div>'
        "</div>"
        f'<div class="slip-net"><span class="l">Net Paid</span><span class="v">NPR {npr(slip.net_pay)}</span></div>'
        f"{foot}</div>"
    )


def schedule_frame(result: t.SalaryResult) -> pd.DataFrame:
    rows = []
    for s in result.slips:
        e = s.entry
        rows.append(
            {
                "Month": s.month,
                "Basic": e.basic_salary,
                "Allowance": e.allowance,
                "Incentive": e.project_incentive,
                "SSF contribution": s.ssf_income,
                "Festival": e.festival_allowance,
                "Leave/Extra Encashment": e.leave_encashment,
                "Gross": s.gross_income,
                "CIT": e.cit,
                "Retirement fund": e.retirement_fund,
                "SSF deduction": s.ssf_deduction,
                "TDS": s.tds,
                "Total deduction": s.total_deductions,
                "Net paid": s.net_pay,
            }
        )
    df = pd.DataFrame(rows)
    total = df.drop(columns="Month").sum()
    df.loc[len(df)] = ["Total", *total.tolist()]
    return df


def schedule_html(result: t.SalaryResult, selected: int) -> str:
    """The 12-month pay schedule, laid out like the tax sheet (items down, months across)."""
    slips = result.slips

    def row(label: str, vals: list[float], cls: str = "") -> str:
        cells = "".join(
            f'<td class="{"cur" if j == selected else ""}">{npr(v, 0) if v else ""}</td>' for j, v in enumerate(vals)
        )
        total = sum(vals)
        return f'<tr class="{cls}"><td>{label}</td><td>{npr(total, 0) if total else ""}</td>{cells}</tr>'

    def group(title: str) -> str:
        return f'<tr class="grp"><td colspan="14">{title}</td></tr>'

    head = (
        "<tr><th>Particulars</th><th>Total</th>"
        + "".join(f'<th class="{"cur" if j == selected else ""}">{m}</th>' for j, m in enumerate(t.MONTHS))
        + "</tr>"
    )
    body = [group("Earnings")]
    earnings = [
        ("Basic Salary", [s.entry.basic_salary for s in slips]),
        ("Allowance", [s.entry.allowance for s in slips]),
        ("Project Incentive", [s.entry.project_incentive for s in slips]),
        ("SSF Contribution (employer)", [s.ssf_income for s in slips]),
        ("Festival Allowance", [s.entry.festival_allowance for s in slips]),
        ("Leave/Extra Encashment", [s.entry.leave_encashment for s in slips]),
    ]
    for label, vals in earnings:
        if sum(vals) or label == "Basic Salary":
            body.append(row(label, vals))
    body.append(row("Gross Income", [s.gross_income for s in slips], "sum"))

    body.append(group("Deductions"))
    deductions = [
        ("CIT", [s.entry.cit for s in slips]),
        ("Retirement Fund / EPF", [s.entry.retirement_fund for s in slips]),
        ("SSF Deduction", [s.ssf_deduction for s in slips]),
        ("TDS (income tax)", [s.tds for s in slips]),
    ]
    for label, vals in deductions:
        if sum(vals):
            body.append(row(label, vals))
    body.append(row("Total Deduction", [s.total_deductions for s in slips], "sum"))
    body.append(row("Net Paid", [s.net_pay for s in slips], "key"))

    return (
        f'<div class="sheet-wrap"><table class="sheet"><thead>{head}</thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )


NEPAL_TZ = timezone(timedelta(hours=5, minutes=45))


def current_month_index() -> int:
    """Index into `t.MONTHS` (Shrawan = 0) for today's Nepali (BS) month in Nepal time."""
    today = nepali_datetime.date.from_datetime_date(datetime.now(NEPAL_TZ).date())
    return (today.month - 4) % 12  # Baisakh is BS month 1, Shrawan is 4


def month_picker(label: str, key: str, default: int | None = None) -> int:
    default = current_month_index() if default is None else default
    choice = st.pills(label, t.MONTHS, selection_mode="single", default=t.MONTHS[default], key=key)
    return t.MONTHS.index(choice) if choice else default


def sheet_html(result: t.SalaryResult, sel: int) -> str:
    """Rigo-HR style tax sheet: incomes, deductions and the TDS working per month."""
    s = result.settings
    fe = t.forecast_entries(result.entries, sel, s)
    # Every month is shown: actual months use real pay, later months use the projected pay.
    slips = t.calculate_salary(fe, replace(s, tds_method=t.TDS_PAYROLL)).slips
    at = slips[sel].forecast

    def fmt(v: float, blank_zero: bool = True) -> str:
        return "" if blank_zero and not v else npr(v, 0)

    def row(label: str, kind: str, annual: float | None, months: list[float | None], cls: str = "", blank_zero: bool = True) -> str:
        out = [f'<tr class="{cls}"><td>{label}</td><td class="ty">{kind}</td>']
        out.append(f"<td>{fmt(annual, blank_zero)}</td>" if annual is not None else '<td class="na">–</td>')
        for j, v in enumerate(months):
            fc = (" fc fc1" if j == sel + 1 else " fc") if j > sel else ""
            if v is None:
                out.append(f'<td class="na{fc}">–</td>')
            else:
                out.append(f'<td class="{fc.strip()}">{fmt(v, blank_zero)}</td>')
        return "".join(out) + "</tr>"

    def group(title: str) -> str:
        return f'<tr class="grp"><td colspan="15">{title}</td></tr>'

    def per_month(fn) -> list[float]:
        return [fn(fe[j]) for j in range(12)]

    def calc(fn, blank_zero: bool = False) -> list[float | None]:
        return [fn(slips[j].forecast) for j in range(12)]

    head = (
        '<tr><th>Particulars</th><th>Type</th><th>Annual</th>'
        + "".join(f"<th>{m}</th>" for m in t.MONTHS)
        + "</tr>"
        '<tr class="st"><th></th><th></th>'
        f"<th>as of {t.MONTHS[sel]}</th>"
        + "".join(
            f'<th class="{"act" if j <= sel else "fc fc1" if j == sel + 1 else "fc"}">{"Actual" if j <= sel else "Forecast"}</th>' for j in range(12)
        )
        + "</tr>"
    )

    body = [group("Incomes")]
    incentive_months = sum(1 for e in fe if e.project_incentive)
    income_rows = [
        ("Basic Salary", "Fixed Income", per_month(lambda e: e.basic_salary)),
        ("Allowance", "Fixed Income", per_month(lambda e: e.allowance)),
        ("Festival Allowance", "One Time", per_month(lambda e: e.festival_allowance)),
        ("SSF Contribution (employer)", "Fixed Income", per_month(lambda e: t.monthly_ssf(e, s)[0])),
        ("Project Incentive", "Fixed Income" if incentive_months > 1 else "One Time", per_month(lambda e: e.project_incentive)),
        ("Leave/Extra Encashment", "Variable", per_month(lambda e: e.leave_encashment)),
    ]
    for label, kind, vals in income_rows:
        if sum(vals) or label == "Basic Salary":
            body.append(row(label, kind, sum(vals), vals))
    body.append(
        row("Annual Income Forecast", "", at.gross_income, per_month(lambda e: e.cash_income + t.monthly_ssf(e, s)[0]), "sum")
    )

    body.append(group("Retirement fund & deductions"))
    ded_rows = [
        ("Retirement Fund", per_month(lambda e: e.retirement_fund)),
        ("CIT Deduction", per_month(lambda e: e.cit)),
        ("SSF Deduction", per_month(lambda e: t.monthly_ssf(e, s)[1])),
    ]
    for label, vals in ded_rows:
        if sum(vals):
            body.append(row(label, "Deduction", sum(vals), vals))

    body.append(group("Tax working (forecast as of each month; later months are projected)"))
    body.append(row("a) Eligible retirement fund + SSF", "", at.retirement_actual, calc(lambda f: f.retirement_actual), blank_zero=False))
    body.append(row("b) Allowable limit", "", t.RETIREMENT_CAP_ABSOLUTE, calc(lambda f: t.RETIREMENT_CAP_ABSOLUTE), blank_zero=False))
    body.append(row("c) 1/3 of taxable income", "", at.gross_income / 3, calc(lambda f: f.gross_income / 3), blank_zero=False))
    body.append(row("Min of a, b or c", "", at.retirement_deduction, calc(lambda f: f.retirement_deduction), "sum", blank_zero=False))
    for label, attr in [
        ("Life insurance deduction", "life_insurance_deduction"),
        ("Health insurance deduction", "health_insurance_deduction"),
        ("Disability deduction", "handicap_deduction"),
    ]:
        if getattr(at, attr):
            body.append(row(label, "", getattr(at, attr), calc(lambda f, a=attr: getattr(f, a))))
    body.append(row("Annual Adjusted Taxable Amount", "", at.taxable_income, calc(lambda f: f.taxable_income), "sum", blank_zero=False))

    for k, (lower, upper, rate) in enumerate(t.SLABS):
        if k and not at.slabs[k].taxable_in_slab:
            continue
        waived = at.slabs[k].waived
        label = f"{'SST' if k == 0 else 'TDS'} {0 if waived else rate * 100:g}%"
        kind = "income in slab → tax"
        body.append(row(label, kind, at.slabs[k].taxable_in_slab, calc(lambda f, k=k: f.slabs[k].tax), blank_zero=False))
    if at.female_rebate:
        body.append(row("Female rebate (10%)", "", -at.female_rebate, calc(lambda f: -f.female_rebate)))

    def sst_part(f: t.AnnualTax) -> float:
        return f.slabs[0].tax * (f.annual_tax / f.tax_before_rebate if f.tax_before_rebate else 1)

    body.append(row("Total SST for the Year", "", sst_part(at), calc(sst_part), blank_zero=False))
    body.append(row("Total TDS for the Year", "", at.annual_tax - sst_part(at), calc(lambda f: f.annual_tax - sst_part(f)), blank_zero=False))

    body.append(group("Monthly TDS"))
    body.append(row("TDS paid in past months", "", slips[sel].tds_paid_before, [s_.tds_paid_before for s_ in slips], blank_zero=False))
    body.append(row("Remaining tax to deduct", "", at.annual_tax - slips[sel].tds_paid_before, [s_.forecast.annual_tax - s_.tds_paid_before for s_ in slips], blank_zero=False))
    body.append(row("Remaining months", "", slips[sel].months_remaining, [s_.months_remaining for s_ in slips], blank_zero=False))
    body.append(row("TDS this month", "", slips[sel].tds, [s_.tds for s_ in slips], "key", blank_zero=False))

    return f'<div class="sheet-wrap"><table class="sheet"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>'


COMPACT_NPR = (
    "datum.value >= 10000000 ? format(datum.value / 10000000, '.2~f') + ' Cr' : "
    "datum.value >= 100000 ? format(datum.value / 100000, '.2~f') + ' L' : "
    "datum.value >= 1000 ? format(datum.value / 1000, '.0~f') + 'k' : datum.value"
)


def monthly_chart(df: pd.DataFrame, selected: str) -> alt.LayerChart:
    """Stacked bars per month (net pay, other deductions, TDS) with value labels and an average line."""
    d = df.assign(**{"Other deductions": df["Total deduction"] - df["TDS"]})
    parts = [("Net paid", "#003893"), ("Other deductions", "#E8A317"), ("TDS", "#C8102E")]
    long = d.melt(id_vars=["Month", "Gross"], value_vars=[n for n, _ in parts], var_name="Part", value_name="Amount")
    long = long.assign(order=long["Part"].map({n: i for i, (n, _) in enumerate(parts)}))
    long["Selected"] = long["Month"] == selected
    months = list(df["Month"])
    x = alt.X("Month:N", sort=months, axis=alt.Axis(labelAngle=0, title=None, labelFontSize=12))
    tooltip = [
        alt.Tooltip("Month:N"),
        alt.Tooltip("Part:N", title="Component"),
        alt.Tooltip("Amount:Q", format=",.0f", title="Amount (NPR)"),
        alt.Tooltip("Gross:Q", format=",.0f", title="Gross (NPR)"),
    ]
    bars = (
        alt.Chart(long)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=x,
            y=alt.Y("Amount:Q", stack="zero", title="NPR", axis=alt.Axis(labelExpr=COMPACT_NPR, tickCount=5)),
            color=alt.Color(
                "Part:N",
                sort=[n for n, _ in parts],
                scale=alt.Scale(domain=[n for n, _ in parts], range=[c for _, c in parts]),
                legend=alt.Legend(orient="top", title=None, symbolType="square"),
            ),
            order=alt.Order("order:Q"),
            opacity=alt.condition("datum.Selected", alt.value(1), alt.value(0.72)),
            tooltip=tooltip,
        )
    )
    net_labels = (
        alt.Chart(d)
        .mark_text(dy=14, color="white", fontSize=11, fontWeight=600, baseline="top")
        .transform_calculate(label="format(datum['Net paid'] / 100000, '.2f') + ' L'")
        .encode(x=x, y=alt.Y("Net paid:Q"), text="label:N", tooltip=alt.value(None))
    )
    top_labels = (
        alt.Chart(d)
        .mark_text(dy=-6, color="#2A1A14", fontSize=11, baseline="bottom")
        .transform_calculate(label="'TDS ' + format(datum['TDS'], ',.0f')")
        .encode(x=x, y=alt.Y("Gross:Q"), text="label:N", tooltip=alt.value(None))
    )
    average = alt.Chart(d).mark_rule(color="#2A1A14", strokeDash=[5, 4], opacity=0.55).encode(
        y=alt.Y("mean(Net paid):Q"), tooltip=alt.value(None)
    )
    return (
        alt.layer(bars, net_labels, top_labels, average)
        .properties(height=360)
        .configure_view(stroke=None, fill="transparent")
        .configure(background="transparent")
        .configure_axis(grid=True, gridColor="rgba(42,26,20,.10)", domain=False, labelColor="#6b5148", titleColor="#6b5148")
        .configure_legend(labelFontSize=12)
    )


def tab_payslip(result: t.SalaryResult) -> None:
    month = month_picker("Select pay month", "slip_month")
    st.markdown(slip_html(result.slips[month], result.settings), unsafe_allow_html=True)

    st.markdown("### All 12 months")
    st.markdown(schedule_html(result, month), unsafe_allow_html=True)
    df = schedule_frame(result)
    st.download_button(
        "⬇️ Download schedule (CSV)",
        df.round(2).to_csv(index=False).encode(),
        file_name=f"nepal-salary-schedule-{t.FISCAL_YEAR.replace('/', '-')}.csv",
        mime="text/csv",
    )
    st.markdown("### Where each month's pay goes")
    st.altair_chart(monthly_chart(df.iloc[:-1], t.MONTHS[month]), width="stretch")
    st.caption(
        f"Bars add up to gross income. Dashed line = average net pay (NPR {npr(df['Net paid'].iloc[:-1].mean())}). "
        f"{t.MONTHS[month]} is highlighted; hover a bar for amounts."
    )


def tab_forecast(result: t.SalaryResult) -> None:
    a = result.annual
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gross annual income", npr_card(a.gross_income))
    c2.metric("Taxable income", npr_card(a.taxable_income))
    c3.metric("Annual income tax", npr_card(a.annual_tax), f"{a.effective_rate:.2%} of gross", delta_color="off")
    c4.metric("Net take-home", npr_card(result.total_net_pay))

    es = result.entries
    parts = [
        ("Basic salary", sum(e.basic_salary for e in es)),
        ("Allowance", sum(e.allowance for e in es)),
        ("Project incentive", sum(e.project_incentive for e in es)),
        ("Festival allowance", sum(e.festival_allowance for e in es)),
        ("Leave/Extra Encashment", sum(e.leave_encashment for e in es)),
        ("SSF contribution (employer 20%)", a.ssf_income),
    ]
    left, right = st.columns(2)
    with left:
        st.markdown("**Annual gross income**")
        rows = [(n, npr(v)) for n, v in parts if v] + [("**Gross annual income**", npr(a.gross_income))]
        st.dataframe(pd.DataFrame(rows, columns=["Component", "Annual (NPR)"]), hide_index=True, width="stretch")
    with right:
        st.markdown("**Net annual take-home**")
        s = result.slips
        rows = [
            ("Gross annual income", npr(a.gross_income)),
            ("− SSF deduction", npr(sum(x.ssf_deduction for x in s))),
            ("− CIT", npr(sum(x.entry.cit for x in s))),
            ("− Retirement fund / EPF", npr(sum(x.entry.retirement_fund for x in s))),
            ("− Income tax (TDS)", npr(result.total_tds)),
            ("**Net annual take-home**", npr(result.total_net_pay)),
        ]
        st.dataframe(pd.DataFrame(rows, columns=["Item", "Amount (NPR)"]), hide_index=True, width="stretch")

    settle = result.tax_settlement
    if abs(settle) >= 1:
        if settle > 0:
            st.warning(f"TDS deducted over the year is NPR {npr(settle)} less than the annual tax.")
        else:
            st.warning(f"TDS deducted over the year is NPR {npr(-settle)} more than the annual tax (refundable).")


def forecast_steps(slip: t.MonthlySlip, settings: t.Settings) -> None:
    f = slip.forecast
    st.markdown("#### Step 1 · Annual income forecast")
    st.markdown(
        f"Payroll treats months up to **{slip.month}** as actual and repeats the current basic salary, "
        "allowance and project incentive for the months left. Festival allowance and leave/extra encashment "
        "only count once they are paid."
        if settings.tds_method == t.TDS_PAYROLL
        else "Whole-year income from the month-by-month table."
    )
    st.markdown(
        f'<div class="formula">Cash income NPR {npr(f.cash_income)}'
        + (f" + employer SSF NPR {npr(f.ssf_income)}" if f.ssf_income else "")
        + f" = <b>NPR {npr(f.gross_income)}</b></div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### Step 2 · Deductions before the slabs")
    st.markdown(
        f"""
* **Retirement contributions** (SSF + retirement fund + CIT) over the year: NPR {npr(f.retirement_actual)}.
  Allowed = lowest of *actual*, *⅓ of gross* (NPR {npr(f.gross_income / 3)}) and *NPR 5,00,000*
  → cap NPR {npr(f.retirement_cap)} → **NPR {npr(f.retirement_deduction)}**
* **Life insurance** (max NPR 40,000): **NPR {npr(f.life_insurance_deduction)}**
* **Health insurance** (max NPR 20,000): **NPR {npr(f.health_insurance_deduction)}**
{f"* **Disability** (50% of the NPR 10,00,000 exemption limit): **NPR {npr(f.handicap_deduction)}**" if f.handicap_deduction else ""}
* Total deductions: **NPR {npr(f.total_deduction)}**
"""
    )

    st.markdown("#### Step 3 · Taxable income")
    st.markdown(
        f'<div class="formula">NPR {npr(f.gross_income)} − NPR {npr(f.total_deduction)} = '
        f"<b>NPR {npr(f.taxable_income)}</b></div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### Step 4 · Progressive slabs (FY 2083/84)")
    rows = []
    for s in f.slabs:
        upper = "and above" if s.upper is None else npr(s.upper, 0)
        rate = f"{s.rate:.0%}" + (" SST – waived (SSF)" if s.waived else (" SST" if s.lower == 0 else ""))
        rows.append((f"{npr(s.lower, 0)} – {upper}", rate, npr(s.taxable_in_slab), npr(s.tax)))
    rows.append(("**Total**", "", npr(f.taxable_income), npr(f.tax_before_rebate)))
    st.dataframe(
        pd.DataFrame(rows, columns=["Slab (NPR)", "Rate", "Income in slab", "Tax"]),
        hide_index=True,
        width="stretch",
    )
    if settings.female_rebate:
        st.markdown(f"Female rebate 10%: − NPR {npr(f.female_rebate)}")
    st.markdown(f"**Forecast annual tax = NPR {npr(f.annual_tax)}**")

    st.markdown(f"#### Step 5 · TDS for {slip.month}")
    if settings.tds_method == t.TDS_EVEN:
        st.markdown(
            f'<div class="formula">NPR {npr(f.annual_tax)} ÷ 12 = <b>NPR {npr(slip.tds)}</b></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="formula">(forecast annual tax NPR {npr(f.annual_tax)} − TDS already deducted '
            f"NPR {npr(slip.tds_paid_before)}) ÷ {slip.months_remaining} remaining month(s) = "
            f"<b>NPR {npr(slip.tds)}</b> (rounded to the nearest rupee)</div>",
            unsafe_allow_html=True,
        )


def profile_chips(s: t.Settings) -> str:
    chips = [
        f"👤 {html.escape(s.name)}" if s.name else "",
        s.gender,
        "Couple" if s.couple else "Single",
        "Person with disability" if s.handicapped else "",
        "SSF contributor" if s.ssf_enrolled else "Not in SSF",
        "10% female rebate" if s.female_rebate else "",
    ]
    return "".join(f'<span class="pchip">{c}</span>' for c in chips if c)


def tab_tds(result: t.SalaryResult) -> None:
    st.markdown("### Tax sheet")
    st.markdown(f'<div class="pchips">{profile_chips(result.settings)}</div>', unsafe_allow_html=True)
    sel = month_picker("Actual payroll up to", "sheet_month")
    st.markdown(sheet_html(result, sel), unsafe_allow_html=True)
    st.caption(
        f"Months up to {t.MONTHS[sel]} are actual. Later months are projected from the information you entered: "
        "basic salary, allowance and project incentive repeat, CIT and retirement fund continue, and festival "
        "allowance and leave/extra encashment count only once paid. The projection changes whenever your pay "
        "changes, and each month re-forecasts the year so TDS = remaining tax ÷ remaining months. "
        "Scroll sideways for all months."
    )
    st.markdown("### Step-by-step calculation")
    month = month_picker("Explain TDS for", "tds_month", default=sel)
    if month <= sel:
        slip, slip_settings = result.slips[month], result.settings
    else:
        slip_settings = replace(result.settings, tds_method=t.TDS_PAYROLL)
        projected = t.calculate_salary(t.forecast_entries(result.entries, sel, slip_settings), slip_settings)
        slip = projected.slips[month]
    forecast_steps(slip, slip_settings)
    st.info(
        f"Total TDS over the year: NPR {npr(result.total_tds)} · actual annual tax on the full-year "
        f"income: NPR {npr(result.annual.annual_tax)}."
    )


def tab_rules() -> None:
    st.markdown(f"### Tax rules used · FY {t.FISCAL_YEAR} (Shrawan 2083 – Ashadh 2084)")
    st.markdown(
        """
| Annual taxable income (NPR) | Rate |
|---|---|
| Up to 10,00,000 | 1% Social Security Tax (**waived for SSF contributors**) |
| 10,00,001 – 15,00,000 | 10% |
| 15,00,001 – 25,00,000 | 20% |
| 25,00,001 – 40,00,000 | 27% |
| Above 40,00,000 | 29% |

* One common set of slabs for every resident individual (no separate single / married schedule).
* **SSF** is fixed on basic salary: 11% employee + 20% employer. Payrolls typically show the employer 20%
  as income ("SSF Contribution") and deduct the full 31% ("SSF Deduction").
* **Retirement deduction (SSF, EPF, CIT):** lowest of actual contribution, ⅓ of assessable income, NPR 5,00,000.
* **Life insurance:** up to NPR 40,000. **Health insurance:** up to NPR 20,000.
* **Female rebate:** 10% of tax for a resident woman with remuneration-only income.
* Festival allowance, project incentive and leave/extra encashment are taxable remuneration.
* **Monthly TDS (payroll style):** `(forecast annual tax − TDS already deducted) ÷ remaining months`.

**Not modelled:** remote-area allowance, medical tax credit, pension income and
tax-exempt leave encashment on retirement.
"""
    )
    st.markdown("### Sources")
    for title, url, note in SOURCES:
        st.markdown(f"* [{title}]({url}) – {note}")
    st.warning(
        "Estimates for planning only. IRD publishes the rates each year and they can be amended by the Finance "
        "Act or IRD notices. Verify with ird.gov.np and your employer's payroll before filing."
    )


def main() -> None:
    st.set_page_config(
        page_title="Nepal Salary & TDS Calculator",
        page_icon="🇳🇵",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(HERO, unsafe_allow_html=True)

    section("calculator", 1, "Your salary", "तपाईंको तलब", "Enter what your employer pays you. Everything updates instantly.")
    base, settings = collect_inputs()
    entries = month_editor(base)
    result = t.calculate_salary(entries, settings)

    if result.annual.gross_income == 0:
        st.info("Enter a basic salary above (or load the sample payslip) to generate your pay slip.")
    else:
        g1, g2, g3 = st.columns(3)
        g1.metric("Net take-home (year)", npr_card(result.total_net_pay))
        g2.metric("Income tax (TDS, year)", npr_card(result.total_tds))
        g3.metric("Average net pay / month", npr_card(result.total_net_pay / 12))

    section("payslip", 2, "Pay slip", "तलबी भर्पाई", "Your monthly pay slip, month by month.")
    tab_payslip(result)

    section("forecast", 3, "Annual income forecast", "वार्षिक आय", "What you will earn and keep this fiscal year.")
    tab_forecast(result)

    section("tds", 4, "TDS calculation", "आयकर गणना", "Exactly how your tax and monthly TDS are worked out.")
    tab_tds(result)

    section("insights", 5, "Dashboard", "ड्यासबोर्ड", "Charts, insights and what-if scenarios built from your numbers.")
    dashboard.render(result, card_title)

    section("rules", 6, "Rules & sources", "नियम र स्रोत", "The FY 2083/84 rules used and where they come from.")
    tab_rules()

    st.markdown(FOOTER, unsafe_allow_html=True)


main()
