#!/usr/bin/env python3
"""Genera el dashboard autocontenido de NVIDIA (NVDA) desde data/nvda_fy.json.

Uso:
  python nvda_dashboard.py
"""

from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
from plotly.subplots import make_subplots

from translations import translate, translate_obj

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "nvda_fy.json"
OUT_PATH = ROOT / "nvda_dashboard.html"

if not DATA_PATH.exists():
    raise SystemExit("Missing data/nvda_fy.json. Run: python fetch_sec_nvda.py --refresh")

D = json.loads(DATA_PATH.read_text(encoding="utf-8"))
YEARS = D["fiscal_years"]
N = len(YEARS)
TAX = D["meta"].get("tax_rate_statutory", 0.21)
RF, ERP, BETA = 0.045, 0.055, 1.7
KE = RF + BETA * ERP
NV_GREEN = "#76b900"
NV_DARK = "#1b5e20"
NV_RED = "#c62828"
NV_BLUE = "#1565c0"
NV_ORANGE = "#ef6c00"
NV_PURPLE = "#6a1b9a"
NV_GRAY = "#607d8b"


def arr(block: str, key: str) -> list[float | None]:
    return D[block][key]


def safe_div(a, b):
    return None if a is None or b in (None, 0) else a / b


def safe_sub(a, b):
    return None if a is None or b is None else a - b


def safe_add(a, b):
    return None if a is None or b is None else a + b


def pct(a, b):
    r = safe_div(a, b)
    return None if r is None else r * 100


def yoy(series: list[float | None]) -> list[float | None]:
    out: list[float | None] = [None]
    for i in range(1, len(series)):
        out.append(pct(safe_sub(series[i], series[i - 1]), series[i - 1]))
    return out


def cagr(series: list[float | None]) -> float | None:
    if len(series) < 2 or not series[0] or series[-1] is None or series[0] <= 0:
        return None
    return ((series[-1] / series[0]) ** (1 / (len(series) - 1)) - 1) * 100


def fmt_m(v, paren: bool = False, dec: int = 0) -> str:
    if v is None:
        return "—"
    s = f"{abs(v) / 1e6:,.{dec}f}"
    return f"({s})" if v < 0 or (paren and v != 0) else s


def fmt_pct(v, dec: int = 1) -> str:
    return "—" if v is None else f"{v:,.{dec}f}%"


def fmt_x(v, dec: int = 2) -> str:
    return "—" if v is None else f"{v:,.{dec}f}x"


def fmt_days(v, dec: int = 1) -> str:
    return "—" if v is None else f"{v:,.{dec}f}"


def fmt_num(v, dec: int = 2) -> str:
    return "—" if v is None else f"{v:,.{dec}f}"


def fmt_eps(v) -> str:
    return "—" if v is None else f"{v:,.2f}"


def fmt_b(v) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1e12:
        return f"${v / 1e12:,.2f}T"
    return f"${v / 1e9:,.1f}B"


# ---------- Datos base ----------
revenue = arr("income", "revenue")
cogs = arr("income", "cost_of_revenue")
gross = arr("income", "gross_profit")
opex = arr("income", "operating_expenses")
rd = arr("income", "research_development")
sga = arr("income", "selling_general_admin")
ebit = arr("income", "operating_income")
nonop = arr("income", "nonoperating_income")
interest = arr("income", "interest_expense")
pretax = arr("income", "pretax_income")
tax = arr("income", "income_tax")
net = arr("income", "net_income")
eps = arr("income", "eps_diluted")

cash = arr("balance", "cash")
mkt_cur = arr("balance", "marketable_securities_current")
ar = arr("balance", "accounts_receivable")
inventory = arr("balance", "inventory")
other_ca = arr("balance", "other_current_assets")
current_assets = arr("balance", "current_assets")
ppe = arr("balance", "ppe")
goodwill = arr("balance", "goodwill")
intangibles = arr("balance", "intangibles")
other_nca = arr("balance", "other_noncurrent_assets")
total_assets = arr("balance", "total_assets")
ap = arr("balance", "accounts_payable")
accrued = arr("balance", "accrued_liabilities")
debt_cur = arr("balance", "debt_current")
other_cl = arr("balance", "other_current_liabilities")
current_liabilities = arr("balance", "current_liabilities")
debt_ncur = arr("balance", "debt_noncurrent")
other_ncl = arr("balance", "other_noncurrent_liabilities")
total_liabilities = arr("balance", "total_liabilities")
equity = arr("balance", "equity")
retained = arr("balance", "retained_earnings")

cfo = arr("cashflow", "cfo")
capex = arr("cashflow", "capex")
cfi = arr("cashflow", "cfi")
cff = arr("cashflow", "cff")
dividends = arr("cashflow", "dividends")
buybacks = arr("cashflow", "buybacks")
da = arr("cashflow", "depreciation_amortization")
sbc = arr("cashflow", "share_based_comp")

market_cap = arr("meta", "market_cap")
market_cap_source = D["meta"].get("market_cap_source", "")
debt_average = arr("meta", "debt_average")
shares = arr("meta", "shares_outstanding")
shares_diluted = arr("meta", "shares_diluted")

SEGMENT_LABELS = [
    "Data Center",
    "Gaming",
    "Professional Visualization",
    "Automotive",
    "OEM & Other",
]
SEGMENT_COLORS = {
    "Data Center": NV_GREEN,
    "Gaming": NV_BLUE,
    "Professional Visualization": NV_ORANGE,
    "Automotive": NV_PURPLE,
    "OEM & Other": NV_GRAY,
}
segments = {label: D["segments"].get(label, [None] * N) for label in SEGMENT_LABELS}

# ---------- Métricas derivadas ----------
ebitda = [safe_add(e, d) for e, d in zip(ebit, da)]
total_debt = [safe_add(a, b) for a, b in zip(debt_cur, debt_ncur)]
cash_sec = [safe_add(c, m) for c, m in zip(cash, mkt_cur)]
net_debt = [safe_sub(d, cs) for d, cs in zip(total_debt, cash_sec)]
net_cash = [safe_sub(cs, d) for d, cs in zip(total_debt, cash_sec)]
fcf = [safe_sub(o, c) for o, c in zip(cfo, capex)]
market_value = [m if m is not None else e for m, e in zip(market_cap, equity)]
avg_debt = [d if d is not None else t for d, t in zip(debt_average, total_debt)]

nopat = [e * (1 - TAX) if e is not None else None for e in ebit]
invested_capital = [
    safe_sub(safe_add(e, d), c) for e, d, c in zip(equity, total_debt, cash_sec)
]
roic = [pct(n, ic) for n, ic in zip(nopat, invested_capital)]

wacc: list[float | None] = []
kd_pct: list[float | None] = []
for i in range(N):
    e = market_value[i]
    d = total_debt[i]
    if e is None or d is None:
        wacc.append(None)
        kd_pct.append(None)
        continue
    kd = (interest[i] or 0) / avg_debt[i] * (1 - TAX) if avg_debt[i] else 0.0
    kd_pct.append(kd * 100)
    v = e + d
    wacc.append(((e / v) * KE + (d / v) * kd) * 100 if v else KE * 100)

eva = [
    n - (w / 100) * ic if n is not None and w is not None and ic is not None else None
    for n, w, ic in zip(nopat, wacc, invested_capital)
]
spread = [r - w if r is not None and w is not None else None for r, w in zip(roic, wacc)]


def altman_z(i: int, equity_value: float | None) -> float | None:
    ta, tl, ca, cl = total_assets[i], total_liabilities[i], current_assets[i], current_liabilities[i]
    re, eb, rev = retained[i], ebit[i], revenue[i]
    if None in (ta, tl, ca, cl, re, eb, rev, equity_value) or ta == 0 or tl == 0:
        return None
    wc = ca - cl
    return (
        1.2 * (wc / ta)
        + 1.4 * (re / ta)
        + 3.3 * (eb / ta)
        + 0.6 * (equity_value / tl)
        + 1.0 * (rev / ta)
    )


z_book = [altman_z(i, equity[i]) for i in range(N)]
z_market = [altman_z(i, market_value[i]) for i in range(N)]

# ---------- Ratios ----------
current_ratio = [safe_div(a, b) for a, b in zip(current_assets, current_liabilities)]
quick_ratio = [
    safe_div(safe_sub(a, i), b) for a, i, b in zip(current_assets, inventory, current_liabilities)
]
cash_ratio = [safe_div(cs, b) for cs, b in zip(cash_sec, current_liabilities)]
working_capital = [safe_sub(a, b) for a, b in zip(current_assets, current_liabilities)]
wc_sales = [pct(w, r) for w, r in zip(working_capital, revenue)]
liab_assets = [pct(t, a) for t, a in zip(total_liabilities, total_assets)]
liab_equity = [safe_div(t, e) for t, e in zip(total_liabilities, equity)]
assets_equity = [safe_div(a, e) for a, e in zip(total_assets, equity)]
equity_assets = [pct(e, a) for e, a in zip(equity, total_assets)]
debt_ebitda = [safe_div(d, e) for d, e in zip(total_debt, ebitda)]
net_debt_ebitda = [safe_div(d, e) for d, e in zip(net_debt, ebitda)]
icr = [safe_div(e, i) for e, i in zip(ebit, interest)]

gross_margin = [pct(g, r) for g, r in zip(gross, revenue)]
op_margin = [pct(e, r) for e, r in zip(ebit, revenue)]
ebitda_margin = [pct(e, r) for e, r in zip(ebitda, revenue)]
net_margin = [pct(n, r) for n, r in zip(net, revenue)]
roa = [pct(n, a) for n, a in zip(net, total_assets)]
roe = [pct(n, e) for n, e in zip(net, equity)]

asset_turnover = [safe_div(r, a) for r, a in zip(revenue, total_assets)]
inv_turnover = [safe_div(c, i) for c, i in zip(cogs, inventory)]
dio = [safe_div(365, t) for t in inv_turnover]
ar_turnover = [safe_div(r, a) for r, a in zip(revenue, ar)]
dso = [safe_div(365, t) for t in ar_turnover]
ap_turnover = [safe_div(c, a) for c, a in zip(cogs, ap)]
dpo = [safe_div(365, t) for t in ap_turnover]
ccc = [
    safe_add(safe_sub(d1, d2), d3)
    for d1, d2, d3 in zip(dio, dpo, dso)
]
fixed_turnover = [safe_div(r, p) for r, p in zip(revenue, ppe)]
equity_turnover = [safe_div(r, e) for r, e in zip(revenue, equity)]

rev_growth = yoy(revenue)
net_growth = yoy(net)
dc_share = [pct(segments["Data Center"][i], revenue[i]) for i in range(N)]
pe = [safe_div(m, n) for m, n in zip(market_value, net)]
ev_ebitda = [
    safe_div(safe_sub(safe_add(m, d), cs), e)
    for m, d, cs, e in zip(market_value, total_debt, cash_sec, ebitda)
]

# ---------- Proyección FY2027 ----------
G_REV = 0.18
GM_TARGET = 0.715
OPEX_GROWTH = 0.18
DA_GROWTH = 0.15
INTEREST_27 = 0.30e9
CAPEX_27 = 8.0e9
DIV_27 = 1.0e9
BUYBACK_27 = 40.0e9

rev27 = revenue[-1] * (1 + G_REV)
cogs27 = rev27 * (1 - GM_TARGET)
gross27 = rev27 * GM_TARGET
opex27 = opex[-1] * (1 + OPEX_GROWTH)
ebit27 = gross27 - opex27
da27 = da[-1] * (1 + DA_GROWTH)
ebitda27 = ebit27 + da27
pretax27 = ebit27 - INTEREST_27
tax27 = pretax27 * TAX
net27 = pretax27 - tax27
cfo27 = net27 + da27 + (sbc[-1] or 0)
fcf27 = cfo27 - CAPEX_27
debt27 = total_debt[-1]
cash27 = cash[-1] + fcf27 - DIV_27 - BUYBACK_27
icr27 = safe_div(ebit27, INTEREST_27)
net_cash27 = cash27 + mkt_cur[-1] - debt27


def scenario(growth: float, gm: float):
    r = revenue[-1] * (1 + growth)
    e = r * gm - opex[-1] * (1 + OPEX_GROWTH)
    p = e - INTEREST_27
    n = p * (1 - TAX)
    return r, e, n


# ---------- Gráficos ----------
def base_layout(title: str, height: int = 380):
    return dict(
        title=dict(text=title, font=dict(size=15, color=NV_DARK)),
        template="plotly_white",
        height=height,
        margin=dict(l=55, r=25, t=55, b=45),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )


figs = {}

# 1. Ingresos vs Ganancia Neta
f = make_subplots(specs=[[{"secondary_y": True}]])
f.add_trace(
    go.Bar(x=YEARS, y=[v / 1e9 for v in revenue], name="Ingresos", marker_color=NV_GREEN),
    secondary_y=False,
)
f.add_trace(
    go.Scatter(
        x=YEARS,
        y=[v / 1e9 for v in net],
        name="Ganancia neta",
        mode="lines+markers",
        line=dict(color=NV_RED, width=3),
    ),
    secondary_y=True,
)
f.update_layout(**base_layout("1. Ingresos vs Ganancia Neta (USD B)"))
f.update_yaxes(title_text="Ingresos (USD B)", secondary_y=False, tickprefix="$", ticksuffix="B")
f.update_yaxes(title_text="Ganancia neta (USD B)", secondary_y=True, tickprefix="$", ticksuffix="B")
figs["chart1"] = f

# 2. Márgenes
f = go.Figure()
for name, series, color in [
    ("Margen bruto", gross_margin, NV_GREEN),
    ("Margen operativo", op_margin, NV_BLUE),
    ("Margen EBITDA", ebitda_margin, NV_ORANGE),
    ("Margen neto", net_margin, NV_RED),
]:
    f.add_trace(
        go.Scatter(
            x=YEARS,
            y=series,
            name=name,
            mode="lines+markers",
            line=dict(width=3, color=color),
        )
    )
f.update_layout(**base_layout("2. Evolución de Márgenes (%)"), yaxis_title="%")
f.update_yaxes(ticksuffix="%")
figs["chart2"] = f

# 3. Deuda vs Patrimonio vs Caja
f = go.Figure()
f.add_trace(
    go.Bar(
        x=YEARS,
        y=[v / 1e9 for v in total_debt],
        name="Deuda financiera",
        marker_color=NV_RED,
    )
)
f.add_trace(
    go.Bar(
        x=YEARS,
        y=[v / 1e9 for v in equity],
        name="Patrimonio",
        marker_color=NV_GREEN,
    )
)
f.add_trace(
    go.Bar(
        x=YEARS,
        y=[v / 1e9 for v in cash_sec],
        name="Caja + inversiones",
        marker_color=NV_BLUE,
    )
)
f.update_layout(**base_layout("3. Deuda vs Patrimonio vs Caja (USD B)"), barmode="group")
f.update_yaxes(title_text="USD B", tickprefix="$", ticksuffix="B")
figs["chart3"] = f

# 4. EVA y ROIC vs WACC
f = make_subplots(specs=[[{"secondary_y": True}]])
f.add_trace(
    go.Bar(
        x=YEARS,
        y=[v / 1e9 if v is not None else None for v in eva],
        name="EVA",
        marker_color=NV_GREEN,
    ),
    secondary_y=False,
)
f.add_trace(
    go.Scatter(
        x=YEARS,
        y=roic,
        name="ROIC",
        mode="lines+markers",
        line=dict(color=NV_BLUE, width=3),
    ),
    secondary_y=True,
)
f.add_trace(
    go.Scatter(
        x=YEARS,
        y=wacc,
        name="WACC",
        mode="lines+markers",
        line=dict(color=NV_RED, width=3, dash="dash"),
    ),
    secondary_y=True,
)
f.add_hline(y=0, line_dash="dot", line_color="#777")
f.update_layout(**base_layout("4. EVA y ROIC vs WACC"))
f.update_yaxes(title_text="EVA (USD B)", secondary_y=False, tickprefix="$", ticksuffix="B")
f.update_yaxes(title_text="%", secondary_y=True, ticksuffix="%")
max_roic = max((v for v in roic if v is not None), default=0)
f.update_yaxes(range=[0, max_roic * 1.15], secondary_y=True)
figs["chart4"] = f
figs["chart4b"] = f

# 5. Liquidez
f = go.Figure()
for name, series, color in [
    ("Razón corriente", current_ratio, NV_GREEN),
    ("Prueba ácida", quick_ratio, NV_BLUE),
    ("Prueba defensiva", cash_ratio, NV_ORANGE),
]:
    f.add_trace(
        go.Scatter(
            x=YEARS,
            y=series,
            name=name,
            mode="lines+markers",
            line=dict(width=3, color=color),
        )
    )
f.add_hline(y=1.5, line_dash="dash", line_color=NV_GREEN, annotation_text="RC 1.5x")
f.add_hline(y=1.0, line_dash="dash", line_color=NV_ORANGE, annotation_text="Ácida 1.0x")
f.update_layout(**base_layout("5. Ratios de Liquidez"), yaxis_title="veces")
f.update_yaxes(ticksuffix="x")
figs["chart5"] = f

# 6. Solvencia
f = make_subplots(specs=[[{"secondary_y": True}]])
f.add_trace(
    go.Scatter(
        x=YEARS,
        y=liab_assets,
        name="Pasivos / Activos",
        mode="lines+markers",
        line=dict(width=3, color=NV_RED),
    ),
    secondary_y=False,
)
f.add_trace(
    go.Scatter(
        x=YEARS,
        y=debt_ebitda,
        name="Deuda / EBITDA",
        mode="lines+markers",
        line=dict(width=3, color=NV_ORANGE, dash="dot"),
    ),
    secondary_y=True,
)
f.add_hline(y=60, line_dash="dash", line_color=NV_GREEN, annotation_text="Referencia 60%")
f.update_layout(**base_layout("6. Solvencia y Endeudamiento"))
f.update_yaxes(title_text="Pasivos / Activos (%)", secondary_y=False, ticksuffix="%")
f.update_yaxes(title_text="Deuda / EBITDA (x)", secondary_y=True, ticksuffix="x")
figs["chart6"] = f

# 7. ROA y ROE
f = go.Figure()
f.add_trace(go.Bar(x=YEARS, y=roa, name="ROA", marker_color=NV_BLUE))
f.add_trace(go.Bar(x=YEARS, y=roe, name="ROE", marker_color=NV_GREEN))
f.update_layout(**base_layout("7. ROA y ROE (%)"), barmode="group")
f.update_yaxes(title_text="%", ticksuffix="%")
figs["chart7"] = f

# 8. Ciclo de conversión de efectivo
f = go.Figure()
f.add_trace(go.Bar(x=YEARS, y=dio, name="DIO (días)", marker_color=NV_BLUE))
f.add_trace(go.Bar(x=YEARS, y=dso, name="DSO (días)", marker_color=NV_ORANGE))
f.add_trace(go.Bar(x=YEARS, y=dpo, name="DPO (días)", marker_color=NV_GREEN))
f.add_trace(
    go.Scatter(
        x=YEARS,
        y=ccc,
        name="CCE (días)",
        mode="lines+markers",
        line=dict(color=NV_RED, width=3),
    )
)
f.update_layout(**base_layout("8. Ciclo de Conversión de Efectivo"), barmode="group")
f.update_yaxes(title_text="días")
figs["chart8"] = f

# 9. Flujo de efectivo
f = go.Figure()
f.add_trace(go.Bar(x=YEARS, y=[v / 1e9 for v in cfo], name="FCO", marker_color=NV_GREEN))
f.add_trace(go.Bar(x=YEARS, y=[v / 1e9 for v in cfi], name="FCI", marker_color=NV_ORANGE))
f.add_trace(go.Bar(x=YEARS, y=[v / 1e9 for v in cff], name="FCFin", marker_color=NV_BLUE))
f.add_trace(
    go.Scatter(
        x=YEARS,
        y=[v / 1e9 for v in fcf],
        name="FCF libre",
        mode="lines+markers",
        line=dict(color=NV_RED, width=3),
    )
)
f.add_hline(y=0, line_dash="dot", line_color="#777")
f.update_layout(**base_layout("9. Flujo de Efectivo y FCF (USD B)"), barmode="group")
f.update_yaxes(title_text="USD B", tickprefix="$", ticksuffix="B")
figs["chart9"] = f

# 10. Proyección FY2027
proj_years = [YEARS[-1], "FY2027P"]
f = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.14,
    subplot_titles=("Ingresos y EBITDA (USD B)", "Deuda e ICR"),
    specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
)
f.add_trace(
    go.Bar(
        x=proj_years,
        y=[revenue[-1] / 1e9, rev27 / 1e9],
        name="Ingresos",
        marker_color=NV_GREEN,
    ),
    row=1,
    col=1,
)
f.add_trace(
    go.Bar(
        x=proj_years,
        y=[ebitda[-1] / 1e9, ebitda27 / 1e9],
        name="EBITDA",
        marker_color=NV_BLUE,
    ),
    row=1,
    col=1,
)
f.add_trace(
    go.Bar(
        x=proj_years,
        y=[total_debt[-1] / 1e9, debt27 / 1e9],
        name="Deuda",
        marker_color=NV_RED,
    ),
    row=2,
    col=1,
)
f.add_trace(
    go.Scatter(
        x=proj_years,
        y=[icr[-1], icr27],
        name="ICR",
        mode="lines+markers",
        line=dict(color=NV_ORANGE, width=3),
    ),
    row=2,
    col=1,
    secondary_y=True,
)
f.update_layout(**base_layout("10. Proyección FY2027 — Escenario Base", height=520))
f.update_yaxes(title_text="USD B", row=1, col=1, tickprefix="$", ticksuffix="B")
f.update_yaxes(title_text="Deuda (USD B)", row=2, col=1, tickprefix="$", ticksuffix="B")
f.update_yaxes(title_text="ICR (x)", row=2, col=1, secondary_y=True, ticksuffix="x")
figs["chart10"] = f

# 11. Segmentos
f = make_subplots(specs=[[{"secondary_y": True}]])
for label in SEGMENT_LABELS:
    f.add_trace(
        go.Bar(
            x=YEARS,
            y=[v / 1e9 if v is not None else None for v in segments[label]],
            name=label,
            marker_color=SEGMENT_COLORS[label],
        ),
        secondary_y=False,
    )
f.add_trace(
    go.Scatter(
        x=YEARS,
        y=dc_share,
        name="Data Center (% del total)",
        mode="lines+markers",
        line=dict(color="#1a1a1a", width=3, dash="dot"),
    ),
    secondary_y=True,
)
f.update_layout(**base_layout("11. Ingresos por Mercado (USD B)"), barmode="stack")
f.update_yaxes(title_text="Ingresos (USD B)", secondary_y=False, tickprefix="$", ticksuffix="B")
f.update_yaxes(title_text="Data Center (%)", secondary_y=True, ticksuffix="%")
figs["chart11"] = f

# ---------- Tablas ----------
def tabla(headers, rows, table_id):
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows
    )
    return (
        f'<table id="{table_id}" class="data-table"><thead><tr>{th}</tr></thead>'
        f"<tbody>{trs}</tbody></table>"
    )


er_headers = ["Concepto", *YEARS]
er_rows = [
    ["Ingresos", *[fmt_m(v) for v in revenue]],
    ["Costo de ventas", *[fmt_m(v, paren=True) for v in cogs]],
    ["Ganancia bruta", *[fmt_m(v) for v in gross]],
    ["I+D", *[fmt_m(v, paren=True) for v in rd]],
    ["SG&A", *[fmt_m(v, paren=True) for v in sga]],
    ["Gastos operativos totales", *[fmt_m(v, paren=True) for v in opex]],
    ["EBIT", *[fmt_m(v) for v in ebit]],
    ["Otros ingresos/(gastos)", *[fmt_m(v) for v in nonop]],
    ["Gastos financieros", *[fmt_m(v, paren=True) for v in interest]],
    ["Ganancia antes de impuestos", *[fmt_m(v) for v in pretax]],
    ["Impuesto a la renta", *[fmt_m(v, paren=True) for v in tax]],
    ["Ganancia neta", *[fmt_m(v) for v in net]],
    ["EPS diluido (USD)", *[fmt_eps(v) for v in eps]],
]
tabla_er = tabla(er_headers, er_rows, "tabla-er")

bg_headers = ["Concepto", *YEARS]
bg_rows = [
    ["Efectivo y equivalentes", *[fmt_m(v) for v in cash]],
    ["Inversiones corrientes", *[fmt_m(v) for v in mkt_cur]],
    ["Cuentas por cobrar", *[fmt_m(v) for v in ar]],
    ["Inventarios", *[fmt_m(v) for v in inventory]],
    ["Otros activos corrientes", *[fmt_m(v) for v in other_ca]],
    ["Total activo corriente", *[fmt_m(v) for v in current_assets]],
    ["PP&E neto", *[fmt_m(v) for v in ppe]],
    ["Goodwill", *[fmt_m(v) for v in goodwill]],
    ["Intangibles", *[fmt_m(v) for v in intangibles]],
    ["Otros activos no corrientes", *[fmt_m(v) for v in other_nca]],
    ["TOTAL ACTIVOS", *[fmt_m(v) for v in total_assets]],
    ["Cuentas por pagar", *[fmt_m(v) for v in ap]],
    ["Gastos acumulados", *[fmt_m(v) for v in accrued]],
    ["Deuda corriente", *[fmt_m(v) for v in debt_cur]],
    ["Otros pasivos corrientes", *[fmt_m(v) for v in other_cl]],
    ["Total pasivo corriente", *[fmt_m(v) for v in current_liabilities]],
    ["Deuda no corriente", *[fmt_m(v) for v in debt_ncur]],
    ["Otros pasivos no corrientes", *[fmt_m(v) for v in other_ncl]],
    ["TOTAL PASIVOS", *[fmt_m(v) for v in total_liabilities]],
    ["PATRIMONIO", *[fmt_m(v) for v in equity]],
    ["Utilidades retenidas", *[fmt_m(v) for v in retained]],
    ["Deuda total", *[fmt_m(v) for v in total_debt]],
    ["Caja neta (caja + inversiones - deuda)", *[fmt_m(v) for v in net_cash]],
]
tabla_bg = tabla(bg_headers, bg_rows, "tabla-bg")

fl_headers = ["Concepto", *YEARS]
fl_rows = [
    ["Flujo de caja operativo (CFO)", *[fmt_m(v) for v in cfo]],
    ["CAPEX", *[fmt_m(v, paren=True) for v in capex]],
    ["Flujo de caja libre (FCF)", *[fmt_m(v) for v in fcf]],
    ["Flujo de inversión (CFI)", *[fmt_m(v) for v in cfi]],
    ["Flujo de financiamiento (CFF)", *[fmt_m(v) for v in cff]],
    ["Dividendos", *[fmt_m(v, paren=True) for v in dividends]],
    ["Recompras de acciones", *[fmt_m(v, paren=True) for v in buybacks]],
    ["Depreciación y amortización", *[fmt_m(v) for v in da]],
    ["Stock-based compensation", *[fmt_m(v) for v in sbc]],
]
tabla_fl = tabla(fl_headers, fl_rows, "tabla-fl")

ratio_headers = ["Ratio", *YEARS, "Referencia"]
liq_rows = [
    ["Razón corriente", *[fmt_x(v) for v in current_ratio], "≥1.5x"],
    ["Prueba ácida", *[fmt_x(v) for v in quick_ratio], "≥1.0x"],
    ["Prueba defensiva", *[fmt_x(v) for v in cash_ratio], "≥0.3x"],
    ["Capital de trabajo (USD M)", *[fmt_m(v) for v in working_capital], "Positivo"],
    ["Capital de trabajo / ventas", *[fmt_pct(v) for v in wc_sales], "—"],
]
tabla_liq = tabla(ratio_headers, liq_rows, "tabla-liq")

sol_rows = [
    ["Pasivos / Activos", *[fmt_pct(v) for v in liab_assets], "≤60%"],
    ["Pasivos / Patrimonio", *[fmt_x(v) for v in liab_equity], "≤1.5x"],
    ["Activos / Patrimonio", *[fmt_x(v) for v in assets_equity], "≤2.5x"],
    ["Independencia financiera", *[fmt_pct(v) for v in equity_assets], "≥40%"],
    ["Deuda / EBITDA", *[fmt_x(v) for v in debt_ebitda], "≤3.0x"],
    ["Deuda neta / EBITDA", *[fmt_x(v) for v in net_debt_ebitda], "≤2.5x"],
    ["Cobertura de intereses (EBIT / intereses)", *[fmt_x(v) for v in icr], "≥5.0x"],
]
tabla_sol = tabla(ratio_headers, sol_rows, "tabla-sol")

rent_rows = [
    ["Margen bruto", *[fmt_pct(v) for v in gross_margin], "≥60%"],
    ["Margen operativo", *[fmt_pct(v) for v in op_margin], "≥25%"],
    ["Margen EBITDA", *[fmt_pct(v) for v in ebitda_margin], "≥30%"],
    ["Margen neto", *[fmt_pct(v) for v in net_margin], "≥20%"],
    ["ROA", *[fmt_pct(v) for v in roa], "≥15%"],
    ["ROE", *[fmt_pct(v) for v in roe], "≥20%"],
    ["ROIC", *[fmt_pct(v) for v in roic], "≥WACC"],
]
tabla_rent = tabla(ratio_headers, rent_rows, "tabla-rent")

ef_rows = [
    ["Rotación de activos", *[fmt_x(v) for v in asset_turnover], "≥0.5x"],
    ["Rotación de inventarios", *[fmt_x(v) for v in inv_turnover], "≥4.0x"],
    ["DIO (días)", *[fmt_days(v) for v in dio], "≤90"],
    ["Rotación de cartera", *[fmt_x(v) for v in ar_turnover], "≥6.0x"],
    ["DSO (días)", *[fmt_days(v) for v in dso], "≤60"],
    ["Rotación de proveedores", *[fmt_x(v) for v in ap_turnover], "—"],
    ["DPO (días)", *[fmt_days(v) for v in dpo], "45-60"],
    ["Ciclo de conversión de efectivo", *[fmt_days(v) for v in ccc], "≤60"],
    ["Rotación de activos fijos", *[fmt_x(v) for v in fixed_turnover], "—"],
    ["Rotación de patrimonio", *[fmt_x(v) for v in equity_turnover], "—"],
]
tabla_ef = tabla(ratio_headers, ef_rows, "tabla-ef")

seg_headers = ["Mercado", *YEARS, "CAGR FY22-FY26", "% FY2026"]
seg_rows = []
for label in SEGMENT_LABELS:
    vals = segments[label]
    share = pct(vals[-1], revenue[-1]) if vals[-1] is not None else None
    seg_rows.append(
        [label, *[fmt_m(v) for v in vals], fmt_pct(cagr(vals)), fmt_pct(share)]
    )
seg_rows.append(["Total", *[fmt_m(v) for v in revenue], fmt_pct(cagr(revenue)), "100.0%"])
tabla_seg = tabla(seg_headers, seg_rows, "tabla-seg")

seg_growth_headers = ["Mercado", "FY2025", "FY2026", "Var. FY2026", "% FY2022", "% FY2026", "Δ share"]
seg_growth_rows = []
for label in SEGMENT_LABELS:
    vals = segments[label]
    share22 = pct(vals[0], revenue[0])
    share26 = pct(vals[-1], revenue[-1])
    delta = (share26 - share22) if share22 is not None and share26 is not None else None
    seg_growth_rows.append(
        [
            label,
            fmt_m(vals[-2]),
            fmt_m(vals[-1]),
            fmt_pct(yoy(vals)[-1]),
            fmt_pct(share22),
            fmt_pct(share26),
            "—" if delta is None else f"{delta:+.1f} pp",
        ]
    )
tabla_seg_growth = tabla(seg_growth_headers, seg_growth_rows, "tabla-seg-growth")

wacc_headers = ["Año", "Deuda", "Patrimonio (mercado)", "E/V", "D/V", "Ke", "Kd", "WACC"]
wacc_rows = []
for i, year in enumerate(YEARS):
    e, d = market_value[i], total_debt[i]
    v = (e or 0) + (d or 0)
    wacc_rows.append(
        [
            year,
            fmt_m(d),
            fmt_m(e),
            fmt_pct(100 * (e or 0) / v) if v else "—",
            fmt_pct(100 * (d or 0) / v) if v else "—",
            fmt_pct(KE * 100),
            fmt_pct(kd_pct[i]),
            fmt_pct(wacc[i]),
        ]
    )
tabla_wacc = tabla(wacc_headers, wacc_rows, "tabla-wacc")

eva_headers = ["Año", "EBIT", "NOPAT", "Capital invertido", "WACC", "Cargo de capital", "EVA", "ROIC", "Spread"]
eva_rows = []
for i, year in enumerate(YEARS):
    charge = (wacc[i] / 100) * invested_capital[i] if wacc[i] is not None and invested_capital[i] is not None else None
    eva_rows.append(
        [
            year,
            fmt_m(ebit[i]),
            fmt_m(nopat[i]),
            fmt_m(invested_capital[i]),
            fmt_pct(wacc[i]),
            fmt_m(charge),
            fmt_m(eva[i]),
            fmt_pct(roic[i]),
            fmt_pct(spread[i]),
        ]
    )
tabla_eva = tabla(eva_headers, eva_rows, "tabla-eva")

risk_headers = ["Risk", "Probability", "Impact", "Level", "Evidence"]
risk_rows = [
    ["Data Center concentration", "High", "High", "🔴 Critical", f"Data Center = {fmt_pct(dc_share[-1])} of FY2026 revenue"],
    ["Customer concentration", "High", "High", "🔴 Critical", "Two direct customers = 22% + 14% of FY2026 revenue"],
    ["Supplier concentration", "High", "Very High", "🔴 Critical", "Manufacturing dependent on TSMC; HBM and CoWoS"],
    ["Export controls / China", "High", "High", "🔴 Critical", "31% of revenue outside the US; advanced-chip restrictions"],
    ["AI capex cyclicality", "Medium", "Very High", "🟠 High", f"FY2026 growth {fmt_pct(rev_growth[-1])}, tied to hyperscalers"],
    ["Competition (AMD, ASICs, Intel)", "High", "Medium", "🟠 High", "High margins attract competition"],
    ["Valuation and expectations", "Medium", "High", "🟠 High", f"P/E {fmt_x(pe[-1], 1)}; market cap {fmt_b(market_value[-1])}"],
    ["Inventory and commitments", "Medium", "Medium", "🟡 Moderate", f"DIO {fmt_days(dio[-1])} days; inventory {fmt_b(inventory[-1])}"],
    ["Taiwan geopolitics", "Medium", "Very High", "🔴 Critical", "Supply chain concentrated in Taiwan"],
    ["Roadmap execution", "Medium", "High", "🟠 High", "Blackwell/Rubin transition and supply capacity"],
]
tabla_riesgos = tabla(risk_headers, risk_rows, "tabla-riesgos")

mit_headers = ["Risk", "Mitigation strategy", "Horizon", "Owner"]
mit_rows = [
    ["Data Center concentration", "Diversify Gaming, Auto and ProViz; long-term agreements", "12-36 months", "CEO / CFO"],
    ["Customer concentration", "Expand direct and indirect customer base; framework contracts", "12-24 months", "Sales"],
    ["Supplier concentration", "Dual-source HBM; TSMC Arizona; inventory buffers", "12-36 months", "COO / Supply Chain"],
    ["Export controls", "Compliance program; variants for permitted markets", "0-6 months", "Legal / CEO"],
    ["AI capex cyclicality", "Demand forecasting; flexible supply; recurring software", "Ongoing", "CFO / CEO"],
    ["Competition", "R&D; CUDA ecosystem; performance leadership", "Ongoing", "CTO"],
    ["Valuation", "Buybacks; communication; capital discipline", "Ongoing", "CFO / Board"],
    ["Inventory", "Demand planning; commitment visibility", "0-6 months", "COO / CFO"],
    ["Taiwan geopolitics", "Geographic diversification; business continuity", "12-36 months", "COO / Board"],
    ["Roadmap execution", "Talent; R&D investment; customer validation", "Ongoing", "CTO / CEO"],
]
tabla_mit = tabla(mit_headers, mit_rows, "tabla-mit")

proj_headers = ["Item", "FY2026 actual", "FY2027P", "Assumption"]
proj_rows = [
    ["Revenue", fmt_m(revenue[-1]), fmt_m(rev27), "+18.0%"],
    ["Cost of revenue", fmt_m(cogs[-1], paren=True), fmt_m(cogs27, paren=True), "Gross margin 71.5%"],
    ["Gross profit", fmt_m(gross[-1]), fmt_m(gross27), "—"],
    ["Operating expenses", fmt_m(opex[-1], paren=True), fmt_m(opex27, paren=True), "+18.0%"],
    ["EBIT", fmt_m(ebit[-1]), fmt_m(ebit27), "—"],
    ["EBITDA", fmt_m(ebitda[-1]), fmt_m(ebitda27), "—"],
    ["Interest expense", fmt_m(interest[-1], paren=True), fmt_m(INTEREST_27, paren=True), "—"],
    ["Net income", fmt_m(net[-1]), fmt_m(net27), "—"],
    ["Capex", fmt_m(capex[-1], paren=True), fmt_m(CAPEX_27, paren=True), "—"],
    ["FCF", fmt_m(fcf[-1]), fmt_m(fcf27), "—"],
    ["Financial debt", fmt_m(total_debt[-1]), fmt_m(debt27), "—"],
    ["ICR", fmt_x(icr[-1]), fmt_x(icr27), "—"],
]
tabla_proj = tabla(proj_headers, proj_rows, "tabla-proj")

sens_headers = ["Scenario", "FY2027P Revenue", "FY2027P EBIT", "FY2027P Net income"]
sens_rows = []
for label, growth, gm in [
    ("Growth -10 pp", G_REV - 0.10, GM_TARGET),
    ("Base", G_REV, GM_TARGET),
    ("Growth +10 pp", G_REV + 0.10, GM_TARGET),
]:
    r, e, n = scenario(growth, gm)
    sens_rows.append([label, fmt_m(r), fmt_m(e), fmt_m(n)])
for label, growth, gm in [
    ("Gross margin -2 pp", G_REV, GM_TARGET - 0.02),
    ("Base (margin)", G_REV, GM_TARGET),
    ("Gross margin +2 pp", G_REV, GM_TARGET + 0.02),
]:
    r, e, n = scenario(growth, gm)
    sens_rows.append([label, fmt_m(r), fmt_m(e), fmt_m(n)])
tabla_sens = tabla(sens_headers, sens_rows, "tabla-sens")

kpi_headers = ["KPI", "FY2027 target", "FY2026 actual"]
kpi_rows = [
    ["Revenue achievement", "≥95%", "—"],
    ["Gross margin", "≥70%", fmt_pct(gross_margin[-1])],
    ["Operating margin", "≥55%", fmt_pct(op_margin[-1])],
    ["FCF / revenue", "≥40%", fmt_pct(pct(fcf[-1], revenue[-1]))],
    ["Net cash / EBITDA", "≥0.3x", fmt_x(-net_debt_ebitda[-1])],
    ["Interest coverage", "≥10x", fmt_x(icr[-1])],
    ["Data Center / revenue", "≤85%", fmt_pct(dc_share[-1])],
    ["Capex / revenue", "≤10%", fmt_pct(pct(capex[-1], revenue[-1]))],
]
tabla_kpi = tabla(kpi_headers, kpi_rows, "tabla-kpi")

conc_headers = ["#", "Finding", "Evidence"]
conc_rows = [
    ["1", "Extraordinary growth", f"Revenue CAGR FY22-FY26 {fmt_pct(cagr(revenue))}; FY2026 {fmt_b(revenue[-1])}"],
    ["2", "World-class margins", f"Gross margin {fmt_pct(gross_margin[-1])}; operating {fmt_pct(op_margin[-1])}; net {fmt_pct(net_margin[-1])}"],
    ["3", "Creates economic value", f"ROIC {fmt_pct(roic[-1])} vs WACC {fmt_pct(wacc[-1])}; EVA {fmt_b(eva[-1])}"],
    ["4", "Net-cash balance sheet", f"Cash + securities {fmt_b(cash_sec[-1])} vs debt {fmt_b(total_debt[-1])}"],
    ["5", "Cash generation", f"FCF {fmt_b(fcf[-1])}; CFO {fmt_b(cfo[-1])}"],
    ["6", "Data Center concentration", f"Data Center {fmt_pct(dc_share[-1])} of revenue (FY2022: {fmt_pct(dc_share[0])})"],
    ["7", "Capital returned", f"Buybacks {fmt_b(buybacks[-1])} + dividends {fmt_b(dividends[-1])} in FY2026"],
    ["8", "Strategic risk, not solvency risk", f"Debt/EBITDA {fmt_x(debt_ebitda[-1])}; ICR {fmt_x(icr[-1])}"],
]
tabla_conc = tabla(conc_headers, conc_rows, "tabla-conc")

rec_headers = ["Priority", "Action", "Horizon", "Expected impact"]
rec_rows = [
    ["🔴 1", "Diversify revenue beyond Data Center", "12-36 months", "Reduces concentration"],
    ["🔴 2", "Secure supply capacity (TSMC/HBM)", "12-36 months", "Protects growth"],
    ["🟠 3", "Export-control compliance program", "0-6 months", "Mitigates regulatory risk"],
    ["🟠 4", "Maintain R&D and performance leadership", "Ongoing", "Defends margins"],
    ["🟠 5", "Inventory and purchase commitment management", "0-6 months", "Frees cash and reduces risk"],
    ["🟡 6", "Geopolitical risk committee", "Ongoing", "Continuous monitoring"],
    ["🟡 7", "Capital discipline in buybacks", "Ongoing", "Protects liquidity"],
    ["🟢 8", "Communicate sensitivity to the AI capex cycle", "1-2 months", "Aligns expectations"],
]
tabla_rec = tabla(rec_headers, rec_rows, "tabla-rec")

trend_headers = ["Indicator", *YEARS, "Trend"]
trend_rows = [
    ["Revenue", *[fmt_b(v) for v in revenue], "📈"],
    ["EBITDA", *[fmt_b(v) for v in ebitda], "📈"],
    ["Net income", *[fmt_b(v) for v in net], "📈"],
    ["ROE", *[fmt_pct(v) for v in roe], "📈"],
    ["Liabilities / Assets", *[fmt_pct(v) for v in liab_assets], "📉"],
    ["Debt / EBITDA", *[fmt_x(v) for v in debt_ebitda], "📉"],
    ["ICR", *[fmt_x(v) for v in icr], "📈"],
    ["WACC", *[fmt_pct(v) for v in wacc], "—"],
    ["EVA", *[fmt_b(v) for v in eva], "📈"],
    ["FCF", *[fmt_b(v) for v in fcf], "📈"],
]
tabla_trend = tabla(trend_headers, trend_rows, "tabla-trend")

# ---------- KPIs ----------
rev26 = revenue[-1]
net26 = net[-1]
rev_growth_26 = rev_growth[-1]
net_growth_26 = net_growth[-1]
gm26 = gross_margin[-1]
roe26 = roe[-1]
debt_ebitda26 = debt_ebitda[-1]
net_cash26 = net_cash[-1]
eva26 = eva[-1]
dc_share26 = dc_share[-1]
spread26 = spread[-1]
cagr_rev = cagr(revenue)
cagr_net = cagr(net)

# ---------- HTML ----------
CSS = """
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #f1f5ee; color: #222; }
header { background: linear-gradient(135deg, #0d1b0d, #1b5e20); color: white; padding: 24px 32px; }
header h1 { margin: 0; font-size: 26px; }
header p { margin: 6px 0 0; opacity: 0.9; font-size: 14px; }
.container { max-width: 1400px; margin: 0 auto; padding: 20px; }
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.kpi { background: white; border-radius: 10px; padding: 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); border-left: 5px solid #76b900; }
.kpi .label { font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
.kpi .value { font-size: 24px; font-weight: 700; margin-top: 6px; }
.kpi .delta { font-size: 12px; margin-top: 4px; color: #555; }
.kpi.red { border-left-color: #c62828; }
.kpi.green { border-left-color: #2e7d32; }
.kpi.orange { border-left-color: #ef6c00; }
.tabs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 20px; }
.tab-btn { background: white; border: 1px solid #cfd8dc; padding: 10px 16px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 600; color: #455a64; }
.tab-btn.active { background: #1b5e20; color: white; border-color: #1b5e20; }
.tab-content { display: none; }
.tab-content.active { display: block; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 18px; }
.card { background: white; border-radius: 10px; padding: 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
h2 { color: #1b5e20; font-size: 20px; margin: 28px 0 12px; border-bottom: 2px solid #c8e6c9; padding-bottom: 6px; }
h3 { color: #2e7d32; font-size: 16px; margin: 18px 0 8px; }
table.data-table { width: 100%; border-collapse: collapse; font-size: 13px; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.08); margin-bottom: 18px; }
table.data-table th { background: #1b5e20; color: white; padding: 10px 8px; text-align: left; font-weight: 600; }
table.data-table td { padding: 8px; border-bottom: 1px solid #eceff1; }
table.data-table tr:hover { background: #f1f8e9; }
table.data-table tr:last-child td { font-weight: 700; background: #e8f5e9; }
.note { background: #fff8e1; border-left: 4px solid #ffb300; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin: 10px 0; }
.alert { background: #ffebee; border-left: 4px solid #c62828; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin: 10px 0; }
.ok { background: #e8f5e9; border-left: 4px solid #2e7d32; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin: 10px 0; }
footer { text-align: center; padding: 20px; color: #78909c; font-size: 12px; }
ul { margin: 8px 0 16px 20px; }
li { margin: 4px 0; }
@media (max-width: 900px) {
  .grid2, .grid3 { grid-template-columns: 1fr; }
  .container { padding: 12px; }
}
"""

PLOTLY_JS = get_plotlyjs()

warnings_html = "".join(f"<li>{w}</li>" for w in D["validation"].get("warnings", []))
validation_banner = ""
if not D["validation"].get("ok", True):
    validation_banner = (
        '<div class="alert"><b>La validación de datos falló.</b> '
        "Revisa data/nvda_fy.json antes de usar las cifras.</div>"
    )
data_notes = (
    '<div class="note"><b>Notas de datos:</b><ul>'
    + (warnings_html or "<li>Sin advertencias.</li>")
    + "</ul></div>"
)

head = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard Financiero — NVIDIA Corporation (NVDA)</title>
<script>__PLOTLY_JS__</script>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>📊 Dashboard Financiero — NVIDIA Corporation (NVDA)</h1>
  <p>Análisis integral FY2022–FY2026 · SEC XBRL · Ratios · WACC/EVA · Segmentos · Riesgos · Proyección FY2027</p>
</header>
<div class="container">
{validation_banner}
<div class="kpi-grid">
  <div class="kpi"><div class="label">Ingresos FY2026</div><div class="value">{fmt_b(rev26)}</div><div class="delta">{rev_growth_26:+.1f}% vs FY2025</div></div>
  <div class="kpi green"><div class="label">Ganancia Neta FY2026</div><div class="value">{fmt_b(net26)}</div><div class="delta">{net_growth_26:+.1f}% vs FY2025</div></div>
  <div class="kpi green"><div class="label">Margen Bruto</div><div class="value">{fmt_pct(gm26)}</div><div class="delta">Margen operativo {fmt_pct(op_margin[-1])}</div></div>
  <div class="kpi green"><div class="label">ROE</div><div class="value">{fmt_pct(roe26)}</div><div class="delta">ROIC {fmt_pct(roic[-1])}</div></div>
  <div class="kpi green"><div class="label">Deuda / EBITDA</div><div class="value">{fmt_x(debt_ebitda26)}</div><div class="delta">Caja neta {fmt_b(net_cash26)}</div></div>
  <div class="kpi green"><div class="label">EVA FY2026</div><div class="value">{fmt_b(eva26)}</div><div class="delta">Spread ROIC−WACC {spread26:+.1f} pp</div></div>
  <div class="kpi orange"><div class="label">Data Center</div><div class="value">{fmt_pct(dc_share26)}</div><div class="delta">del total de ingresos</div></div>
  <div class="kpi orange"><div class="label">P/E</div><div class="value">{fmt_x(pe[-1], 1)}</div><div class="delta">Capitalización {fmt_b(market_value[-1])}</div></div>
</div>

<div class="tabs">
  <button class="tab-btn active" onclick="showTab('resumen', this)">📈 Resumen</button>
  <button class="tab-btn" onclick="showTab('estados', this)">📋 Estados Financieros</button>
  <button class="tab-btn" onclick="showTab('flujo', this)">💵 Flujo de Efectivo</button>
  <button class="tab-btn" onclick="showTab('ratios', this)">📊 Ratios</button>
  <button class="tab-btn" onclick="showTab('segmentos', this)">🧩 Segmentos</button>
  <button class="tab-btn" onclick="showTab('wacc', this)">⚖️ WACC / EVA</button>
  <button class="tab-btn" onclick="showTab('riesgos', this)">⚠️ Riesgos</button>
  <button class="tab-btn" onclick="showTab('proyeccion', this)">🔮 Proyección FY2027</button>
  <button class="tab-btn" onclick="showTab('conclusiones', this)">📌 Conclusiones</button>
</div>
"""

head = translate(head).replace("__PLOTLY_JS__", PLOTLY_JS)

body = f"""
<!-- TAB: RESUMEN -->
<div id="tab-resumen" class="tab-content active">
  <h2>Resumen Ejecutivo — Gráficos Principales</h2>
  <div class="grid2">
    <div class="card"><div id="chart1"></div></div>
    <div class="card"><div id="chart2"></div></div>
  </div>
  <div class="grid2" style="margin-top:18px">
    <div class="card"><div id="chart3"></div></div>
    <div class="card"><div id="chart4"></div></div>
  </div>
  <div class="ok"><b>Executive read:</b> NVDA grew from {fmt_b(revenue[0])} to {fmt_b(rev26)} in revenue (CAGR {fmt_pct(cagr_rev)}), with a gross margin of {fmt_pct(gm26)} and ROIC of {fmt_pct(roic[-1])} versus a WACC of {fmt_pct(wacc[-1])}. It generates an EVA of {fmt_b(eva26)} and has net cash of {fmt_b(net_cash26)}. The main risk is concentration: Data Center already represents {fmt_pct(dc_share26)} of revenue.</div>
</div>

<!-- TAB: ESTADOS -->
<div id="tab-estados" class="tab-content">
  <h2>Estado de Resultados (USD millones)</h2>
  {tabla_er}
  <h2>Balance General (USD millones)</h2>
  {tabla_bg}
  {data_notes}
  <div class="note"><b>Methodology notes:</b> FY = NVIDIA fiscal year (ends in late January). Figures are in USD millions. "Other non-current assets" includes operating leases, deferred tax, non-marketable equity investments and other assets. The FY2026 "Marketable securities" line uses the issuer-specific XBRL tag (MarketableSecuritiesAndEquitySecuritiesFVNI). Shares and EPS are normalized for the 10:1 split in June 2024.</div>
</div>

<!-- TAB: FLUJO -->
<div id="tab-flujo" class="tab-content">
  <h2>Flujo de Efectivo (Método Indirecto)</h2>
  <div class="card"><div id="chart9"></div></div>
  {tabla_fl}
  <h3>Key takeaways</h3>
  <ul>
    <li><b>FY2026:</b> CFO of {fmt_b(cfo[-1])}, capex of {fmt_b(capex[-1])} and FCF of {fmt_b(fcf[-1])}. Net cash rises to {fmt_b(net_cash26)}.</li>
    <li><b>Capital returned:</b> share repurchases of {fmt_b(buybacks[-1])} and dividends of {fmt_b(dividends[-1])} in FY2026.</li>
    <li><b>Cash flow quality:</b> FCF comfortably exceeds capex; growth is funded with internal cash, not debt.</li>
    <li><b>Risk:</b> strong cash generation depends on the AI investment cycle continuing.</li>
  </ul>
  <div class="ok"><b>Conclusion:</b> NVDA is a cash-generating machine: it funds capex, buybacks and dividends from CFO while still accumulating net cash. The risk is not liquidity, but demand sustainability.</div>
</div>

<!-- TAB: RATIOS -->
<div id="tab-ratios" class="tab-content">
  <h2>Ratios de Liquidez</h2>
  {tabla_liq}
  <div class="card"><div id="chart5"></div></div>
  <h2>Ratios de Solvencia</h2>
  {tabla_sol}
  <div class="card"><div id="chart6"></div></div>
  <div class="note">Una deuda neta / EBITDA negativa indica caja neta: la empresa tiene más efectivo e inversiones corrientes que deuda financiera.</div>
  <h2>Ratios de Rentabilidad</h2>
  {tabla_rent}
  <div class="card"><div id="chart7"></div></div>
  <h2>Ratios de Eficiencia</h2>
  {tabla_ef}
  <div class="card"><div id="chart8"></div></div>
  <div class="note">Las referencias son orientativas para una empresa de semiconductores asset-light; no sustituyen un análisis de comparables.</div>
</div>

<!-- TAB: SEGMENTOS -->
<div id="tab-segmentos" class="tab-content">
  <h2>Ingresos por Mercado (USD millones)</h2>
  <div class="card"><div id="chart11"></div></div>
  {tabla_seg}
  <h3>Dinámica por mercado</h3>
  {tabla_seg_growth}
  <h3>Key takeaways</h3>
  <ul>
    <li><b>Data Center:</b> grew from {fmt_pct(dc_share[0])} of revenue in FY2022 to {fmt_pct(dc_share[-1])} in FY2026. It is the growth engine and the main source of concentration.</li>
    <li><b>Gaming:</b> grew in absolute terms but lost relative weight (from {fmt_pct(pct(segments['Gaming'][0], revenue[0]))} to {fmt_pct(pct(segments['Gaming'][-1], revenue[-1]))}).</li>
    <li><b>Automotive and ProViz:</b> small but growing markets; they are the natural diversification path.</li>
    <li><b>Risk:</b> a fall in AI infrastructure spending would directly affect 89.7% of the business.</li>
  </ul>
  <div class="alert"><b>Conclusion:</b> Data Center concentration explains current profitability and, at the same time, NVDA's central strategic risk.</div>
</div>

<!-- TAB: WACC -->
<div id="tab-wacc" class="tab-content">
  <h2>WACC and EVA (FY2022–FY2026)</h2>
  <div class="note"><b>Parameters:</b> Rf 4.5% · Market risk premium 5.5% · Beta 1.7 · Ke = 4.5% + 1.7 × 5.5% = 13.85% · Tax rate 21% · Kd = interest expense / average debt × (1 − 21%). Market capitalization: {market_cap_source}.</div>
  {tabla_wacc}
  {tabla_eva}
  <div class="card"><div id="chart4b"></div></div>
  <div class="ok"><b>Conclusion:</b> NVDA creates economic value in all five years: ROIC well above WACC and positive, growing EVA. WACC is dominated by the cost of equity because debt is marginal (D/V below 1%).</div>
  <div class="note"><b>Note:</b> EVA uses invested capital = equity + debt − cash and marketable securities. Market capitalization comes from the SEC's EntityPublicFloat (end of the second fiscal quarter); if you add data/nvda_market_cap.csv with fiscal_year,market_cap_usd, the script uses exact market capitalization.</div>
</div>

<!-- TAB: RIESGOS -->
<div id="tab-riesgos" class="tab-content">
  <h2>Matriz de Riesgos Financieros y Estratégicos</h2>
  {tabla_riesgos}
  <h2>Estrategias de Mitigación</h2>
  {tabla_mit}
  <h3>Methodologies applied</h3>
  <ul>
    <li>Ratio and trend analysis FY2022–FY2026.</li>
    <li>Altman Z-Score: {fmt_num(z_book[-1])} on book equity and {fmt_num(z_market[-1])} on market capitalization (safe zone in both cases).</li>
    <li>WACC and market capitalization sensitivity analysis.</li>
    <li>Stress testing of the AI capex cycle and revenue concentration.</li>
    <li>Covenant analysis: Debt/EBITDA, ICR and liquidity.</li>
    <li>Probability × Impact matrix and mitigation plan.</li>
  </ul>
  <div class="note">Altman Z is calibrated for manufacturers; NVDA is asset-light and its market cap is far above book value, so the market-based Z is not very informative. The book-equity Z is shown as a conservative reference.</div>
</div>

<!-- TAB: PROYECCIÓN -->
<div id="tab-proyeccion" class="tab-content">
  <h2>FY2027 Forecast — Base Case</h2>
  <div class="card"><div id="chart10"></div></div>
  {tabla_proj}
  <h3>Key assumptions</h3>
  <ul>
    <li>Revenue +18.0% (deceleration from +65.5% in FY2026).</li>
    <li>Gross margin 71.5% (vs. 71.1% in FY2026).</li>
    <li>Operating expenses +18.0%; D&A +15.0%.</li>
    <li>Interest expense USD 300M; tax rate 21%.</li>
    <li>Capex USD 8.0B; dividends USD 1.0B; buybacks USD 40.0B.</li>
    <li>Debt stable at USD 8.5B; net cash continues to grow.</li>
  </ul>
  <h3>Sensitivity analysis</h3>
  {tabla_sens}
  <h3>Budget control KPIs</h3>
  {tabla_kpi}
  <h3>Forecast methodologies</h3>
  <ul>
    <li><b>3+9 forecast:</b> 3 closed months + 9 projected, with margin and capex review.</li>
    <li><b>Rolling forecast:</b> monthly update of a 12-month rolling horizon.</li>
    <li><b>Driver-based:</b> volume, price, mix and unit cost by market.</li>
    <li><b>Multiple scenarios:</b> base, optimistic and pessimistic.</li>
    <li><b>Cash flow forecasting:</b> weekly/monthly given sensitivity to the AI cycle.</li>
  </ul>
  <div class="note">Illustrative forecast, not analyst consensus. Adjust the assumptions in <code>nvda_dashboard.py</code> (G_REV, GM_TARGET, OPEX_GROWTH, etc.).</div>
</div>

<!-- TAB: CONCLUSIONES -->
<div id="tab-conclusiones" class="tab-content">
  <h2>Conclusions</h2>
  {tabla_conc}
  <div class="ok">
    <b>Verdict:</b> NVIDIA is the opposite of Danec: it creates economic value on a massive scale, has net cash and extraordinary margins. Its risk is not solvency but Data Center concentration, dependence on TSMC/HBM, export controls and sensitivity to the AI capex cycle.
  </div>
  <h2>Prioritized recommendations</h2>
  {tabla_rec}
  <h3>Trend summary</h3>
  {tabla_trend}
</div>
</div>
<footer>Dashboard generated with Python + Plotly · Data: SEC XBRL (companyfacts + 10-K) · NVIDIA Corporation (NVDA) · FY2022–FY2026 · Self-contained HTML</footer>
"""

body = translate(body)

charts_js = ""
for key, fig in figs.items():
    fig_dict = json.loads(fig.to_json())
    charts_js += f"var {key} = {json.dumps(translate_obj(fig_dict), ensure_ascii=False)};\n"

plot_calls = ""
for key in figs:
    plot_calls += f"Plotly.newPlot('{key}', {key}.data, {key}.layout, {{responsive: true}});\n"

script = (
    "<script>\n"
    + charts_js
    + """
function showTab(id, btn) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
  setTimeout(() => {
    document.querySelectorAll('#tab-' + id + ' [id^="chart"]').forEach(el => {
      if (el.data) Plotly.Plots.resize(el);
    });
  }, 50);
}
"""
    + plot_calls
    + """
window.addEventListener('resize', () => {
  document.querySelectorAll('[id^="chart"]').forEach(el => {
    if (el.data) Plotly.Plots.resize(el);
  });
});
</script>
</body>
</html>
"""
)

html = head + body + script
OUT_PATH.write_text(html, encoding="utf-8")
print(f"✅ Dashboard generated: {OUT_PATH}")
print(f"📊 {len(figs)} charts across {len(YEARS)} fiscal years")
print(f"📦 Size: {OUT_PATH.stat().st_size / 1e6:.1f} MB")
