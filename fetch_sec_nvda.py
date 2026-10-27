#!/usr/bin/env python3
"""Descarga y normaliza los datos XBRL de NVIDIA (NVDA) desde la SEC.

Fuentes:
  - companyfacts: https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json
  - submissions:  https://data.sec.gov/submissions/CIK0001045810.json
  - instancias XBRL de los 10-K (para ingresos por mercado)

Salida:
  data/nvda_fy.json  (5 años fiscales normalizados, en USD)

Uso:
  python fetch_sec_nvda.py              # usa caché si existe
  python fetch_sec_nvda.py --refresh    # vuelve a descargar todo
  python fetch_sec_nvda.py --offline    # solo caché, sin red
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from datetime import date
from pathlib import Path

CIK = "0001045810"
CIK_INT = int(CIK)
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
COMPANYFACTS_URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
SUBMISSIONS_URL = f"https://data.sec.gov/submissions/CIK{CIK}.json"

# SEC exige un User-Agent con contacto real. Configúralo con:
#   export SEC_USER_AGENT="Tu Nombre tu@email.com"
DEFAULT_UA = "NVDA-Dashboard/1.0 (contact: contact@example.com)"
UA = os.environ.get("SEC_USER_AGENT", DEFAULT_UA)
OFFLINE = False

SEGMENT_MAP = {
    "DataCenterMember": "Data Center",
    "GamingMember": "Gaming",
    "ProfessionalVisualizationMember": "Professional Visualization",
    "AutomotiveMember": "Automotive",
    "OEMAndOtherMember": "OEM & Other",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def http_get(url: str, cache: Path, refresh: bool = False, binary: bool = False):
    """Descarga con caché. Devuelve bytes o texto."""
    if cache.exists() and not refresh:
        return cache.read_bytes() if binary else cache.read_text(encoding="utf-8")
    if OFFLINE:
        raise SystemExit(f"Offline mode: missing cache {cache}")

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json, text/xml, */*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            encoding = (resp.headers.get("Content-Encoding") or "").lower()
    except Exception as exc:
        raise SystemExit(f"Error descargando {url}: {exc}") from exc

    if encoding == "gzip":
        raw = gzip.decompress(raw)
    elif encoding == "deflate":
        raw = zlib.decompress(raw)

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(raw)
    time.sleep(0.2)  # cortesía: la SEC limita a 10 req/s
    return raw if binary else raw.decode("utf-8")


def annual_entries(facts: dict, tag: str, unit: str = "USD") -> list[dict]:
    node = facts.get(tag)
    if not node:
        return []
    return [
        x
        for x in node.get("units", {}).get(unit, [])
        if x.get("form") == "10-K" and x.get("fp") == "FY"
    ]


def pick(entries: list[dict], end: str, duration: bool) -> float | None:
    candidates = [x for x in entries if x.get("end") == end]
    if duration:
        candidates = [
            x
            for x in candidates
            if x.get("start")
            and 350
            <= (date.fromisoformat(x["end"]) - date.fromisoformat(x["start"])).days
            <= 380
        ]
    else:
        candidates = [x for x in candidates if not x.get("start")]
    if not candidates:
        return None
    chosen = max(candidates, key=lambda x: (x.get("filed", ""), x.get("accn", "")))
    return chosen.get("val")


def pick_tag(
    facts: dict, tags: list[str], end: str, duration: bool, unit: str = "USD"
) -> tuple[float | None, str | None]:
    for tag in tags:
        value = pick(annual_entries(facts, tag, unit), end, duration)
        if value is not None:
            return value, tag
    return None, None


def build_series(
    facts: dict, tags: list[str], ends: list[str], duration: bool, unit: str = "USD"
) -> list[float | None]:
    out = []
    for end in ends:
        value, _ = pick_tag(facts, tags, end, duration, unit)
        out.append(value)
    return out


def fiscal_ends(facts: dict) -> list[str]:
    """Últimos 6 cierres fiscales detectados en Assets (10-K)."""
    instants: dict[str, dict] = {}
    for entry in annual_entries(facts, "Assets"):
        if entry.get("start"):
            continue
        end = entry["end"]
        if end not in instants or entry.get("filed", "") > instants[end].get("filed", ""):
            instants[end] = entry
    ends = sorted(instants)
    if len(ends) < 5:
        raise SystemExit(f"Solo se encontraron {len(ends)} cierres fiscales; se necesitan 5.")
    return ends[-6:]


def fy_label(end: str) -> str:
    return f"FY{end[:4]}"


def get_10k_accessions(submissions: dict) -> dict[str, str]:
    recent = submissions["filings"]["recent"]
    out: dict[str, str] = {}
    for form, report_date, accession in zip(
        recent["form"], recent["reportDate"], recent["accessionNumber"]
    ):
        if form == "10-K":
            out[report_date] = accession
    return out


def get_public_float(dei: dict, accn_by_end: dict[str, str], ends: list[str]) -> list[float | None]:
    facts = dei.get("EntityPublicFloat", {}).get("units", {}).get("USD", [])
    out: list[float | None] = []
    for end in ends:
        accn = accn_by_end.get(end)
        candidates = [x for x in facts if x.get("accn") == accn]
        if not candidates:
            dated = [x for x in facts if x.get("form") == "10-K"]
            dated.sort(key=lambda x: abs((date.fromisoformat(x["end"]) - date.fromisoformat(end)).days))
            if dated and abs((date.fromisoformat(dated[0]["end"]) - date.fromisoformat(end)).days) <= 220:
                candidates = [dated[0]]
        out.append(candidates[0]["val"] if candidates else None)
    return out


def get_instance(accession: str, label: str, refresh: bool) -> bytes:
    accn_path = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{CIK_INT}/{accn_path}"
    index_path = DATA_DIR / f"index_{label}.json"
    index = json.loads(http_get(f"{base}/index.json", index_path, refresh))
    files = [
        item["name"]
        for item in index.get("directory", {}).get("item", [])
        if item["name"].endswith("_htm.xml")
    ]
    if not files:
        raise SystemExit(f"Could not find the 10-K XBRL instance {label} ({accession})")
    return http_get(f"{base}/{files[0]}", DATA_DIR / f"nvda_10k_{label}.xml", refresh, binary=True)


def parse_segments(xml_bytes: bytes) -> dict[str, dict[str, float]]:
    """Devuelve {fecha_fin: {miembro: ingreso}} desde la instancia XBRL."""
    root = ET.fromstring(xml_bytes)
    ns = "{http://www.xbrl.org/2003/instance}"
    contexts: dict[str, tuple[str | None, dict[str, str]]] = {}
    for ctx in root.findall(ns + "context"):
        period = ctx.find(ns + "period")
        end = period.findtext(ns + "endDate") if period is not None else None
        dims: dict[str, str] = {}
        for member in ctx.iter():
            if member.tag.endswith("explicitMember"):
                dim = (member.get("dimension") or "").split(":")[-1]
                val = (member.text or "").split(":")[-1]
                if dim and val:
                    dims[dim] = val
        contexts[ctx.get("id", "")] = (end, dims)

    out: dict[str, dict[str, float]] = {}
    for fact in root:
        tag = fact.tag.split("}")[-1]
        if tag not in ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"):
            continue
        ctx_id = fact.get("contextRef")
        if not ctx_id or ctx_id not in contexts:
            continue
        end, dims = contexts[ctx_id]
        member = dims.get("ProductOrServiceAxis")
        if not end or not member:
            continue
        try:
            value = float(fact.text)
        except (TypeError, ValueError):
            continue
        out.setdefault(end, {})[member] = value
    return out


def parse_scalar_fact(xml_bytes: bytes, localname: str, end: str) -> float | None:
    """Lee un hecho escalar (sin dimensiones) de la instancia XBRL.

    Los hechos del balance usan <instant>; los del estado de resultados usan
    <startDate>/<endDate>. Se aceptan ambos y se descartan los dimensionales.
    """
    root = ET.fromstring(xml_bytes)
    ns = "{http://www.xbrl.org/2003/instance}"
    ctx_info: dict[str, tuple[str | None, bool]] = {}
    for ctx in root.findall(ns + "context"):
        period = ctx.find(ns + "period")
        if period is None:
            ctx_info[ctx.get("id", "")] = (None, True)
            continue
        end_date = period.findtext(ns + "endDate") or period.findtext(ns + "instant")
        has_dims = any(m.tag.endswith("explicitMember") for m in ctx.iter())
        ctx_info[ctx.get("id", "")] = (end_date, has_dims)

    for fact in root:
        if fact.tag.split("}")[-1] != localname:
            continue
        ctx_id = fact.get("contextRef")
        ctx_end, has_dims = ctx_info.get(ctx_id or "", (None, True))
        if ctx_end == end and not has_dims:
            try:
                return float(fact.text)
            except (TypeError, ValueError):
                continue
    return None


def normalize_split(values: list[float | None]) -> tuple[list[float | None], list[int]]:
    """Lleva las cifras de acciones a la base post-split (10:1 en 2024).

    companyfacts mezcla años pre-split (FY2022/FY2023) con años post-split.
    Se detecta una cifra anómala si está a menos de la mitad de la mediana
    de los tres últimos años y se multiplica por el factor entero que la alinea.
    """
    recent = sorted(v for v in values[-3:] if v)
    median = recent[len(recent) // 2] if recent else 0
    adjusted: list[float | None] = []
    factors: list[int] = []
    for value in values:
        if value is None or median == 0:
            adjusted.append(value)
            factors.append(1)
            continue
        factor = max(1, round(median / value)) if value < median / 2 else 1
        adjusted.append(value * factor)
        factors.append(factor)
    return adjusted, factors


def load_market_cap_csv(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    import csv

    out: dict[str, float] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row.get("fiscal_year") or "").strip().upper()
            raw = (row.get("market_cap_usd") or "").strip()
            if key and raw:
                out[key] = float(raw)
    return out


def fmt_b(value: float | None) -> str:
    return "—" if value is None else f"{value / 1e9:,.1f}"


def main() -> int:
    global OFFLINE
    parser = argparse.ArgumentParser(description="NVIDIA XBRL data from the SEC")
    parser.add_argument("--refresh", action="store_true", help="ignore the cache and re-download")
    parser.add_argument("--offline", action="store_true", help="use only the local cache")
    parser.add_argument(
        "--market-cap-csv",
        type=Path,
        default=DATA_DIR / "nvda_market_cap.csv",
        help="optional CSV with fiscal_year,market_cap_usd",
    )
    args = parser.parse_args()
    OFFLINE = args.offline

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not os.environ.get("SEC_USER_AGENT"):
        log("⚠️  SEC_USER_AGENT is not set; using a sample contact.")
        log("    Set SEC_USER_AGENT with your name and email to comply with SEC policy.\n")

    log("Downloading SEC companyfacts and submissions…")
    companyfacts = json.loads(
        http_get(COMPANYFACTS_URL, DATA_DIR / "nvda_companyfacts.json", args.refresh)
    )
    submissions = json.loads(
        http_get(SUBMISSIONS_URL, DATA_DIR / "nvda_submissions.json", args.refresh)
    )

    gaap = companyfacts["facts"]["us-gaap"]
    dei = companyfacts["facts"].get("dei", {})
    all_ends = fiscal_ends(gaap)
    display_ends = all_ends[-5:]
    years = [fy_label(e) for e in display_ends]
    log(f"Fiscal year ends: {', '.join(years)}")

    # ---------- Estado de resultados ----------
    revenue = build_series(gaap, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"], display_ends, True)
    cogs = build_series(gaap, ["CostOfRevenue", "CostOfGoodsAndServicesSold"], display_ends, True)
    gross = build_series(gaap, ["GrossProfit"], display_ends, True)
    gross = [
        g if g is not None else (r - c if r is not None and c is not None else None)
        for g, r, c in zip(gross, revenue, cogs)
    ]
    opex = build_series(gaap, ["OperatingExpenses"], display_ends, True)
    rd = build_series(gaap, ["ResearchAndDevelopmentExpense"], display_ends, True)
    sga = build_series(gaap, ["SellingGeneralAndAdministrativeExpense"], display_ends, True)
    opex = [
        o if o is not None else ((r or 0) + (s or 0) if r is not None or s is not None else None)
        for o, r, s in zip(opex, rd, sga)
    ]
    ebit = build_series(gaap, ["OperatingIncomeLoss"], display_ends, True)
    nonop = build_series(gaap, ["NonoperatingIncomeExpense"], display_ends, True)
    interest = build_series(
        gaap,
        ["InterestExpenseNonoperating", "InterestExpense", "InterestExpenseDebt"],
        display_ends,
        True,
    )
    pretax = build_series(
        gaap,
        [
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxes",
        ],
        display_ends,
        True,
    )
    tax = build_series(gaap, ["IncomeTaxExpenseBenefit"], display_ends, True)
    net = build_series(gaap, ["NetIncomeLoss"], display_ends, True)
    eps = build_series(gaap, ["EarningsPerShareDiluted"], display_ends, True, "USD/shares")
    pretax = [
        p if p is not None else ((n + t) if n is not None and t is not None else None)
        for p, n, t in zip(pretax, net, tax)
    ]

    # ---------- Balance ----------
    cash = build_series(gaap, ["CashAndCashEquivalentsAtCarryingValue"], display_ends, False)
    mkt_cur = build_series(
        gaap,
        ["MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtMaturitiesWithinOneYearFairValue"],
        display_ends,
        False,
    )
    # NVDA no tiene una línea de "marketable securities" no corrientes:
    # las inversiones no corrientes son "non-marketable equity securities"
    # y se agrupan dentro de otros activos no corrientes.
    mkt_noncur = [0.0] * len(display_ends)
    ar = build_series(gaap, ["AccountsReceivableNetCurrent"], display_ends, False)
    inventory = build_series(gaap, ["InventoryNet"], display_ends, False)
    current_assets = build_series(gaap, ["AssetsCurrent"], display_ends, False)
    ppe = build_series(gaap, ["PropertyPlantAndEquipmentNet"], display_ends, False)
    goodwill = build_series(gaap, ["Goodwill"], display_ends, False)
    intangibles = build_series(gaap, ["IntangibleAssetsNetExcludingGoodwill"], display_ends, False)
    other_noncurrent = build_series(gaap, ["OtherAssetsNoncurrent"], display_ends, False)
    total_assets = build_series(gaap, ["Assets"], display_ends, False)
    ap = build_series(gaap, ["AccountsPayableCurrent"], display_ends, False)
    accrued = build_series(gaap, ["AccruedLiabilitiesCurrent"], display_ends, False)
    debt_current = build_series(gaap, ["LongTermDebtCurrent", "DebtCurrent"], display_ends, False)
    current_liabilities = build_series(gaap, ["LiabilitiesCurrent"], display_ends, False)
    debt_noncurrent = build_series(gaap, ["LongTermDebtNoncurrent"], display_ends, False)
    other_noncurrent_liab = build_series(gaap, ["OtherLiabilitiesNoncurrent"], display_ends, False)
    total_liabilities = build_series(gaap, ["Liabilities"], display_ends, False)
    equity = build_series(gaap, ["StockholdersEquity"], display_ends, False)
    retained = build_series(gaap, ["RetainedEarningsAccumulatedDeficit"], display_ends, False)

    def derive(total, *parts):
        if total is None:
            return None
        if any(p is None for p in parts):
            return None
        return total - sum(parts)

    other_noncurrent = [
        derive(t, c, p, g, i)
        for t, c, p, g, i in zip(
            total_assets, current_assets, ppe, goodwill, intangibles
        )
    ]
    other_current_liab = [
        derive(c, a, ac, d)
        for c, a, ac, d in zip(current_liabilities, ap, accrued, debt_current)
    ]
    other_noncurrent_liab = [
        derive(t, c, d)
        for t, c, d in zip(total_liabilities, current_liabilities, debt_noncurrent)
    ]
    total_debt = [
        (d or 0) + (dn or 0) for d, dn in zip(debt_current, debt_noncurrent)
    ]

    # ---------- Flujo de efectivo ----------
    cfo = build_series(gaap, ["NetCashProvidedByUsedInOperatingActivities"], display_ends, True)
    capex = build_series(
        gaap,
        ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
        display_ends,
        True,
    )
    cfi = build_series(gaap, ["NetCashProvidedByUsedInInvestingActivities"], display_ends, True)
    cff = build_series(gaap, ["NetCashProvidedByUsedInFinancingActivities"], display_ends, True)
    dividends = build_series(
        gaap,
        ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock", "DividendsCommonStockCash"],
        display_ends,
        True,
    )
    buybacks = build_series(gaap, ["PaymentsForRepurchaseOfCommonStock"], display_ends, True)
    da = build_series(
        gaap,
        ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet"],
        display_ends,
        True,
    )
    sbc = build_series(gaap, ["ShareBasedCompensation"], display_ends, True)

    # ---------- Acciones y valor de mercado ----------
    shares = build_series(gaap, ["CommonStockSharesOutstanding"], display_ends, False, "shares")
    shares_diluted = build_series(
        gaap, ["WeightedAverageNumberOfDilutedSharesOutstanding"], display_ends, True, "shares"
    )
    accn_by_end = get_10k_accessions(submissions)
    public_float = get_public_float(dei, accn_by_end, display_ends)
    market_cap_csv = load_market_cap_csv(args.market_cap_csv)
    market_cap = [
        market_cap_csv.get(year, pf) for year, pf in zip(years, public_float)
    ]
    market_cap_source = "CSV" if market_cap_csv else "EntityPublicFloat (SEC, fiscal Q2 end)"

    # ---------- Deuda promedio (necesita el año anterior) ----------
    debt_by_end: dict[str, float] = {}
    for end in all_ends:
        dc, _ = pick_tag(gaap, ["LongTermDebtCurrent", "DebtCurrent"], end, False)
        dn, _ = pick_tag(gaap, ["LongTermDebtNoncurrent"], end, False)
        debt_by_end[end] = (dc or 0) + (dn or 0)
    debt_average = []
    for end in display_ends:
        idx = all_ends.index(end)
        prior = all_ends[idx - 1] if idx > 0 else end
        debt_average.append((debt_by_end.get(prior, 0) + debt_by_end.get(end, 0)) / 2)

    # ---------- Segmentos por mercado ----------
    log("Downloading 10-K XBRL instances for segment data…")
    segments = {label: [] for label in SEGMENT_MAP.values()}
    segment_warnings: list[str] = []
    marketable_custom: list[float | None] = [None] * len(display_ends)
    for idx, (end, year) in enumerate(zip(display_ends, years)):
        accession = accn_by_end.get(end)
        if not accession:
            segment_warnings.append(f"{year}: could not find the 10-K ({end})")
            for label in segments:
                segments[label].append(None)
            continue
        try:
            xml_bytes = get_instance(accession, year, args.refresh)
            by_end = parse_segments(xml_bytes)
            marketable_custom[idx] = parse_scalar_fact(
                xml_bytes, "MarketableSecuritiesAndEquitySecuritiesFVNI", end
            )
        except Exception as exc:
            segment_warnings.append(f"{year}: could not parse segments ({exc})")
            for label in segments:
                segments[label].append(None)
            continue

        data = by_end.get(end)
        if data is None:
            # tolerancia por si el cierre difiere un día
            close = sorted(by_end, key=lambda d: abs((date.fromisoformat(d) - date.fromisoformat(end)).days))
            if close and abs((date.fromisoformat(close[0]) - date.fromisoformat(end)).days) <= 7:
                data = by_end[close[0]]
        if data is None:
            segment_warnings.append(f"{year}: the instance has no ProductOrServiceAxis for {end}")
        for member, label in SEGMENT_MAP.items():
            segments[label].append((data or {}).get(member))
        if data and len(data) < len(SEGMENT_MAP):
            missing = [m for m in SEGMENT_MAP if m not in data]
            segment_warnings.append(f"{year}: missing members {missing}")

    for idx, value in enumerate(marketable_custom):
        if value is not None:
            mkt_cur[idx] = value
    if any(value is not None for value in marketable_custom):
        segment_warnings.append(
            "Marketable securities: used the issuer-specific XBRL tag "
            "where companyfacts does not expose it."
        )

    other_current = [
        derive(c, ca, mc, a, i)
        for c, ca, mc, a, i in zip(current_assets, cash, mkt_cur, ar, inventory)
    ]

    # ---------- Validaciones ----------
    checks: list[dict] = []
    warnings: list[str] = list(segment_warnings)

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    key_series = {
        "ingresos": revenue,
        "costo de ventas": cogs,
        "ganancia bruta": gross,
        "EBIT": ebit,
        "ganancia neta": net,
        "activos": total_assets,
        "pasivos": total_liabilities,
        "patrimonio": equity,
    }
    missing = [name for name, series in key_series.items() if any(v is None for v in series)]
    check("complete series", not missing, "missing: " + ", ".join(missing) if missing else "5/5 years complete")

    balance_ok = all(
        ta is not None and tl is not None and eq is not None and abs(ta - (tl + eq)) <= 1e6
        for ta, tl, eq in zip(total_assets, total_liabilities, equity)
    )
    check("assets = liabilities + equity", balance_ok, "tolerance USD 1M")

    gross_ok = all(
        g is not None and r is not None and c is not None and abs(g - (r - c)) <= 1e6
        for g, r, c in zip(gross, revenue, cogs)
    )
    check("gross profit = revenue - cost", gross_ok, "tolerance USD 1M")

    other_ok = all((v is None or v >= 0) for v in other_current + other_noncurrent)
    check("other assets non-negative", other_ok, "other balance sheet items")

    segment_ok = True
    for i, year in enumerate(years):
        vals = [segments[label][i] for label in segments]
        if any(v is None for v in vals) or revenue[i] is None:
            segment_ok = False
            warnings.append(f"{year}: incomplete segments")
        elif abs(sum(vals) - revenue[i]) > 1e6:
            segment_ok = False
            warnings.append(
                f"{year}: segments sum to {sum(vals)/1e9:.1f} B vs revenue {revenue[i]/1e9:.1f} B"
            )
    check("segments sum to revenue", segment_ok, "tolerance USD 1M")

    # Caja: CFO + CFI + CFF = variación de efectivo
    cash_all = build_series(gaap, ["CashAndCashEquivalentsAtCarryingValue"], all_ends, False)
    cash_by_end = dict(zip(all_ends, cash_all))
    cash_ok = True
    for end in display_ends:
        i = all_ends.index(end)
        prior = all_ends[i - 1] if i > 0 else None
        if prior is None or cash_by_end.get(prior) is None:
            continue
        delta = (cash_by_end.get(end) or 0) - (cash_by_end.get(prior) or 0)
        flows = (cfo[display_ends.index(end)] or 0) + (cfi[display_ends.index(end)] or 0) + (cff[display_ends.index(end)] or 0)
        if abs(delta - flows) > 5e6:
            cash_ok = False
            warnings.append(f"{fy_label(end)}: change in cash {delta/1e9:.2f} B vs cash flows {flows/1e9:.2f} B")
    check("CFO + CFI + CFF = change in cash", cash_ok, "tolerance USD 5M")

    market_ok = all(v is not None and v > 0 for v in market_cap)
    check("market capitalization", market_ok, market_cap_source)
    if not market_ok:
        warnings.append("Market capitalization missing; WACC will fall back to book equity.")

    ok = all(c["ok"] for c in checks)

    # ---------- Normalización de acciones por split ----------
    shares, split_factors = normalize_split(shares)
    shares_diluted, split_factors_diluted = normalize_split(shares_diluted)
    eps = [
        e / f if e is not None and f else e
        for e, f in zip(eps, split_factors_diluted)
    ]
    if any(f > 1 for f in split_factors + split_factors_diluted):
        warnings.append("Shares and EPS normalized for the 10:1 split in June 2024.")

    # ---------- JSON normalizado ----------
    def series(values):
        return [None if v is None else round(v, 2) for v in values]

    output = {
        "company": companyfacts.get("entityName", "NVIDIA CORP"),
        "ticker": "NVDA",
        "cik": CIK,
        "source": "SEC XBRL companyfacts + 10-K instances",
        "generated_at": date.today().isoformat(),
        "fiscal_years": years,
        "fiscal_year_ends": display_ends,
        "currency": "USD",
        "income": {
            "revenue": series(revenue),
            "cost_of_revenue": series(cogs),
            "gross_profit": series(gross),
            "operating_expenses": series(opex),
            "research_development": series(rd),
            "selling_general_admin": series(sga),
            "operating_income": series(ebit),
            "nonoperating_income": series(nonop),
            "interest_expense": series(interest),
            "pretax_income": series(pretax),
            "income_tax": series(tax),
            "net_income": series(net),
            "eps_diluted": series(eps),
        },
        "balance": {
            "cash": series(cash),
            "marketable_securities_current": series(mkt_cur),
            "accounts_receivable": series(ar),
            "inventory": series(inventory),
            "other_current_assets": series(other_current),
            "current_assets": series(current_assets),
            "ppe": series(ppe),
            "goodwill": series(goodwill),
            "intangibles": series(intangibles),
            "marketable_securities_noncurrent": series(mkt_noncur),
            "other_noncurrent_assets": series(other_noncurrent),
            "total_assets": series(total_assets),
            "accounts_payable": series(ap),
            "accrued_liabilities": series(accrued),
            "debt_current": series(debt_current),
            "other_current_liabilities": series(other_current_liab),
            "current_liabilities": series(current_liabilities),
            "debt_noncurrent": series(debt_noncurrent),
            "other_noncurrent_liabilities": series(other_noncurrent_liab),
            "total_liabilities": series(total_liabilities),
            "equity": series(equity),
            "retained_earnings": series(retained),
        },
        "cashflow": {
            "cfo": series(cfo),
            "capex": series(capex),
            "cfi": series(cfi),
            "cff": series(cff),
            "dividends": series(dividends),
            "buybacks": series(buybacks),
            "depreciation_amortization": series(da),
            "share_based_comp": series(sbc),
        },
        "meta": {
            "shares_outstanding": series(shares),
            "shares_diluted": series(shares_diluted),
            "share_split_factors": split_factors,
            "public_float": series(public_float),
            "market_cap": series(market_cap),
            "market_cap_source": market_cap_source,
            "debt_average": series(debt_average),
            "tax_rate_statutory": 0.21,
        },
        "segments": {label: series(values) for label, values in segments.items()},
        "validation": {"ok": ok, "checks": checks, "warnings": warnings},
    }

    out_path = DATA_DIR / "nvda_fy.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---------- Resumen por consola ----------
    log("")
    log(f"{'Year':<8}{'Revenue':>14}{'EBITDA':>10}{'Net income':>14}{'Assets':>12}{'Equity':>12}{'Debt':>10}  (USD B)")
    for i, year in enumerate(years):
        ebitda = (ebit[i] or 0) + (da[i] or 0)
        log(
            f"{year:<8}{fmt_b(revenue[i]):>14}{fmt_b(ebitda):>10}{fmt_b(net[i]):>14}"
            f"{fmt_b(total_assets[i]):>12}{fmt_b(equity[i]):>12}{fmt_b(total_debt[i]):>10}"
        )
    log("")
    for item in checks:
        log(f"{'✅' if item['ok'] else '❌'} {item['name']}: {item['detail']}")
    for warning in warnings:
        log(f"⚠️  {warning}")
    log("")
    log(f"Saved: {out_path}")
    log(f"Market capitalization: {market_cap_source}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
