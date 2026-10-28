#!/usr/bin/env python3
"""Fetch the latest NVDA close from Nasdaq and write data/nvda_price.csv.

The dashboard reads the committed CSV, so the HTML build stays offline and
reproducible. Run this script only when you want to refresh the market price.
"""

from __future__ import annotations

import csv
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "nvda_price.csv"
URL = "https://api.nasdaq.com/api/quote/NVDA/info?assetclass=stocks"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)
MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_price(raw: str) -> float:
    return float(raw.replace("$", "").replace(",", "").strip())


def parse_date(timestamp: str) -> str:
    match = re.search(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", timestamp)
    if not match:
        raise SystemExit(f"Unrecognised Nasdaq timestamp: {timestamp!r}")
    month, day, year = match.groups()
    return date(int(year), MONTHS[month], int(day)).isoformat()


def main() -> int:
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    quote = payload.get("data", {})
    secondary = quote.get("secondaryData") or {}
    primary = quote.get("primaryData") or {}

    price_raw = secondary.get("lastSalePrice") or primary.get("lastSalePrice")
    if not price_raw:
        raise SystemExit("Nasdaq response does not contain a last sale price.")

    timestamp = (
        secondary.get("lastTradeTimestamp")
        or primary.get("lastTradeTimestamp")
        or ""
    )
    price = parse_price(price_raw)
    as_of = parse_date(timestamp)
    source = "Nasdaq close" if secondary.get("lastSalePrice") else "Nasdaq last sale"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["price", "as_of", "source"])
        writer.writeheader()
        writer.writerow({"price": f"{price:.2f}", "as_of": as_of, "source": source})

    print(f"Saved {OUT}")
    print(f"NVDA {price:.2f} USD · {as_of} · {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
