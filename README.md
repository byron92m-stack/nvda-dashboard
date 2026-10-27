# NVIDIA Financial Dashboard — FY2022–FY2026

A self-contained, interactive financial dashboard for **NVIDIA Corporation (NVDA)** built from
official **SEC XBRL** data. It covers five fiscal years, from **FY2022** (ended January 30, 2022)
to **FY2026** (ended January 25, 2026), and runs entirely in the browser with no server, database
or internet connection.

**Live demo:** `https://byron92m-stack.github.io/nvda-dashboard/`  
*(available after GitHub Pages is enabled; see [Publishing](#publishing-the-dashboard))*

---

## What the dashboard includes

Nine tabs and eleven unique charts (twelve Plotly containers, because the EVA chart appears in both
the Overview and WACC/EVA tabs):

| Tab | Contents |
|---|---|
| **Overview** | Revenue vs net income, margins, debt vs equity vs cash, EVA and ROIC vs WACC |
| **Financial Statements** | Five-year income statement and balance sheet |
| **Cash Flow** | CFO, CFI, CFF, free cash flow, capex, buybacks and dividends |
| **Ratios** | Liquidity, solvency, profitability and efficiency ratios |
| **Segments** | Revenue by market: Data Center, Gaming, Professional Visualization, Automotive, OEM & Other |
| **WACC / EVA** | Cost of capital, economic value added, ROIC and spread |
| **Risks** | Financial and strategic risk matrix, mitigation plan, methodologies |
| **FY2027 Forecast** | Base-case projection, sensitivity analysis and budget KPIs |
| **Conclusions** | Findings, prioritized recommendations and trend summary |

The HTML is **fully self-contained** (~4.9 MB): Plotly.js, CSS, data and JavaScript are embedded in
one file. It works offline and can be shared by email or WhatsApp.

### FY2026 snapshot

| Metric | FY2026 |
|---|---:|
| Revenue | $215.9B |
| Net income | $120.1B |
| Gross margin | 71.1% |
| ROIC | 99.8% |
| WACC | 13.8% |
| EVA | $88.7B |
| Net cash | $54.1B |
| Data Center share | 89.7% of revenue |

These values come from the FY2026 10-K and are recalculated every time the dashboard is generated.

---

## Data sources

- **Consolidated financials:** [SEC XBRL companyfacts](https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json)
  for CIK `0001045810` (NVIDIA CORP).
- **Segment revenue:** XBRL instances of NVIDIA's 10-K filings, using the
  `ProductOrServiceAxis` dimension (`DataCenterMember`, `GamingMember`,
  `ProfessionalVisualizationMember`, `AutomotiveMember`, `OEMAndOtherMember`).
- **Market capitalization:** `dei:EntityPublicFloat` from the SEC by default. This is the market
  value of the public float at the end of the **second fiscal quarter**, not at fiscal year-end.
  For a company with marginal debt like NVIDIA, the effect on WACC is negligible (D/V below 1%).
  An optional CSV can override it with exact market capitalization (see below).

### Fiscal years

NVIDIA's fiscal year ends in late January:

| Fiscal year | Fiscal year-end |
|---|---|
| FY2022 | 2022-01-30 |
| FY2023 | 2023-01-29 |
| FY2024 | 2024-01-28 |
| FY2025 | 2025-01-26 |
| FY2026 | 2026-01-25 |

---

## Project structure

```
nvda-dashboard/
├── fetch_sec_nvda.py       Download and normalize SEC XBRL data
├── nvda_dashboard.py       Build the self-contained HTML dashboard
├── translations.py         Spanish-to-English map for the rendered UI
├── requirements.txt        Python dependency: plotly
├── data/
│   ├── nvda_fy.json        Normalized five-year dataset (committed)
│   ├── nvda_companyfacts.json   Cached companyfacts API (ignored)
│   ├── nvda_submissions.json    Cached SEC submissions (ignored)
│   ├── nvda_10k_FY20xx.xml      Cached 10-K XBRL instances (ignored)
│   └── index_FY20xx.json        Cached filing indexes (ignored)
├── nvda_dashboard.html     Generated dashboard (committed)
├── index.html              Redirect so the repository root opens the dashboard
├── .nojekyll               Disable Jekyll processing on GitHub Pages
├── .gitignore
└── README.md
```

`fetch_sec_nvda.py` and `nvda_dashboard.py` only need the Python standard library plus **Plotly**.
The downloader itself uses `urllib` and `xml.etree.ElementTree`; no `requests` or `pandas` required.

---

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/byron92m-stack/nvda-dashboard.git
cd nvda-dashboard
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Set a real SEC contact

The SEC requires a `User-Agent` with a real contact:

```bash
export SEC_USER_AGENT="Your Name your@email.com"
```

If it is not set, the script uses a sample contact and prints a warning. The scripts still work,
but you should comply with the SEC policy.

### 4. Download and normalize the data

```bash
.venv/bin/python fetch_sec_nvda.py --refresh
```

This downloads `companyfacts`, the submissions JSON and the five 10-K XBRL instances. The result is
`data/nvda_fy.json`. The script validates accounting identities and prints a summary.

### 5. Generate the dashboard

```bash
.venv/bin/python nvda_dashboard.py
```

Output: `nvda_dashboard.html`.

### 6. Open it

```bash
xdg-open nvda_dashboard.html
```

On macOS/Windows, double-click the file or open it with Chrome, Edge or Firefox. It is **not** an
executable; do not run it from bash.

---

## Regenerating and caching

```bash
# Use the cache when available
.venv/bin/python fetch_sec_nvda.py

# Force a fresh download
.venv/bin/python fetch_sec_nvda.py --refresh

# Work without network, using the cached files
.venv/bin/python fetch_sec_nvda.py --offline

# Rebuild the HTML from data/nvda_fy.json
.venv/bin/python nvda_dashboard.py
```

The large caches (`companyfacts`, 10-K instances and filing indexes) are ignored by git. The small
normalized dataset `data/nvda_fy.json` is committed, so the dashboard can be rebuilt without
redownloading anything.

---

## Optional exact market capitalization

Create `data/nvda_market_cap.csv` to override the SEC public float:

```csv
fiscal_year,market_cap_usd
FY2022,600000000000
FY2023,480000000000
FY2024,1500000000000
FY2025,3000000000000
FY2026,4500000000000
```

If the file exists, the script uses it and reports `CSV` as the source. Otherwise it uses
`EntityPublicFloat (SEC, fiscal Q2 end)`.

---

## Methodology

### WACC

- Risk-free rate: **4.5%**
- Market risk premium: **5.5%**
- Beta: **1.7**
- Cost of equity: `Ke = 4.5% + 1.7 × 5.5% = 13.85%`
- Tax rate: **21%**
- Cost of debt: interest expense / average debt × (1 − 21%)
- Weights: market capitalization and financial debt

### EVA and ROIC

- `NOPAT = EBIT × (1 − 21%)`
- `Invested capital = equity + debt − cash and marketable securities`
- `ROIC = NOPAT / invested capital`
- `EVA = NOPAT − WACC × invested capital`
- `Spread = ROIC − WACC`

Because cash and marketable securities are subtracted, ROIC can exceed 100% in years with a large
cash pile. This is intentional and is explained in the dashboard.

### Altman Z-Score

The dashboard reports the Z-Score using **book equity** (conservative) and **market capitalization**.
The original model is calibrated for manufacturers; NVIDIA is asset-light and its market cap is far
above book value, so the market-based Z is not very informative.

### Segment revenue

Segment revenue is read from each 10-K XBRL instance. The script maps the `ProductOrServiceAxis`
members to:

- Data Center
- Gaming
- Professional Visualization
- Automotive
- OEM & Other

It validates that the segments sum to total revenue each year. If a member disappears from a future
filing, the script reports a warning instead of silently inventing a value.

### Split normalization

NVIDIA executed a **10-for-1 stock split** in June 2024. `companyfacts` mixes pre-split and
post-split share counts. The script normalizes shares and diluted EPS to the post-split basis and
adds a data warning to the dashboard.

### FY2027 forecast

The base case is illustrative, not analyst consensus:

- Revenue growth: **+18.0%**
- Gross margin: **71.5%**
- Operating expenses: **+18.0%**
- D&A: **+15.0%**
- Interest expense: **USD 300M**
- Tax rate: **21%**
- Capex: **USD 8.0B**
- Dividends: **USD 1.0B**
- Buybacks: **USD 40.0B**
- Debt: stable at **USD 8.5B**

Adjust the constants in `nvda_dashboard.py` (`G_REV`, `GM_TARGET`, `OPEX_GROWTH`, etc.) to test
other scenarios.

### Units

- Tables: **USD millions**
- Charts: **USD billions ($B)**
- Ratios: multiples (`x`), percentages (`%`) or days

---

## Validation

`fetch_sec_nvda.py` runs these checks before writing the dataset:

- Five complete fiscal years for the key series.
- `Assets = Liabilities + Equity`.
- `Gross profit = Revenue − Cost of revenue`.
- Segment revenue sums to total revenue.
- `CFO + CFI + CFF = Change in cash`.
- Other current and non-current assets are non-negative.
- Market capitalization is available.

The result is stored in `data/nvda_fy.json` under `validation`:

```json
{
  "ok": true,
  "checks": [...],
  "warnings": [...]
}
```

The dashboard shows a warning banner if validation fails and lists data warnings in the
**Financial Statements** tab.

### Rendering verification

The dashboard was tested with Chrome headless and the network blocked:

```bash
google-chrome --headless=new --no-sandbox --disable-gpu \
  --host-resolver-rules="MAP * ~NOTFOUND" \
  --virtual-time-budget=15000 --dump-dom \
  "file:///home/linux/proyectos/nvda-dashboard/nvda_dashboard.html" \
  > /tmp/nvda_dom.html
```

Expected result: twelve Plotly containers (`chart1`–`chart11` plus `chart4b`), no JavaScript
errors, and no external `<script src>` or `<link href>` resources.

---

## Publishing the dashboard

The dashboard is a static, self-contained HTML file. Any static host can serve it; no server-side
runtime is needed. The repository includes a small `index.html` that redirects the root URL to
`nvda_dashboard.html`.

### Option A — GitHub Pages (recommended)

GitHub Pages is free for public repositories and is the natural choice for this project.

1. Create a **public** repository on GitHub named `nvda-dashboard` (do not initialize it with a
   README, because this repository already has one).
2. Add the remote and push:

   ```bash
   git remote add origin https://github.com/byron92m-stack/nvda-dashboard.git
   git push -u origin main
   ```

   Use your GitHub username and a **personal access token** as the password. Never commit the token.

3. In the repository, open **Settings → Pages**.
4. Under **Build and deployment**, choose **Deploy from a branch**.
5. Select branch **`main`** and folder **`/ (root)`**, then **Save**.
6. Wait one or two minutes. The dashboard will be at:

   ```
   https://byron92m-stack.github.io/nvda-dashboard/
   ```

   The root `index.html` redirects to `nvda_dashboard.html`, so the clean URL works.

**Important:** GitHub Pages sites are public. NVIDIA's data is public SEC data, so this is fine for
this project. Do not use GitHub Pages for confidential company data.

### Option B — Netlify Drop (fastest, no git)

1. Open <https://app.netlify.com/drop>.
2. Drag the project folder (or just `index.html` and `nvda_dashboard.html`) into the page.
3. Netlify returns a public URL immediately.
4. Create a free account to keep the site and rename it.

This is the quickest way to share the dashboard without using GitHub. Updates require uploading
the new HTML again.

### Option C — Cloudflare Pages

1. Push the repository to GitHub (steps A1–A2).
2. In Cloudflare Pages, connect the repository.
3. Framework preset: **None**.
4. Build command: leave empty.
5. Output directory: `/` (the repository root).
6. Deploy.

Cloudflare Pages is free for static sites. If you need restricted access, **Cloudflare Access**
(free tier, up to 50 users) can require an email login. This is the best option if you later want a
private link.

### Option D — Vercel

1. Import the GitHub repository into Vercel.
2. Framework preset: **Other**.
3. Build command: leave empty.
4. Output directory: `.`.
5. Deploy.

Vercel's free Hobby plan is fine for a public dashboard. Password protection is a paid feature.

### Public vs. private

| Host | Cost | Access control |
|---|---|---|
| GitHub Pages | Free | Public only (unless Enterprise) |
| Netlify | Free tier | Public; password protection is paid |
| Cloudflare Pages | Free tier | Public; Cloudflare Access free up to 50 users |
| Vercel | Free Hobby | Public; password protection is paid |

For this NVIDIA dashboard, public hosting is reasonable because all data comes from public SEC
filings. If you reuse the template for private company data, use Cloudflare Access, Netlify password
protection, or share the HTML file directly instead of publishing it.

### Custom domain

All four hosts support a custom domain. Add the domain in the host's dashboard and create the
requested `CNAME`/`A` records at your DNS provider. GitHub Pages can also use a `CNAME` file in the
repository root.

---

## Customization

- **Language:** `translations.py` maps the generator's Spanish labels to English. Adapt it for
  another language, or edit the strings in `nvda_dashboard.py`.
- **Forecast assumptions:** `G_REV`, `GM_TARGET`, `OPEX_GROWTH`, `DA_GROWTH`, `INTEREST_27`,
  `CAPEX_27`, `DIV_27`, `BUYBACK_27` in `nvda_dashboard.py`.
- **Theme:** `NV_GREEN`, `NV_DARK`, `NV_RED`, etc. at the top of `nvda_dashboard.py`, plus the CSS
  block near the bottom.
- **Data refresh:** run `fetch_sec_nvda.py --refresh` and regenerate the HTML.

---

## Limitations

- `EntityPublicFloat` is a second-quarter market value, not a fiscal year-end value. Use the optional
  CSV for exact market capitalization.
- The FY2027 forecast is illustrative and not a consensus estimate.
- Segment extraction depends on the SEC continuing to use `ProductOrServiceAxis` members. The script
  fails visibly if they change.
- `companyfacts` may contain restatements. The script picks the most recently filed 10-K value for
  each fiscal year-end.
- The dashboard is an analytical tool, **not investment advice**.

---

## Author

**byron92m-stack**  
GitHub: <https://github.com/byron92m-stack>

Data: U.S. Securities and Exchange Commission (SEC) XBRL. NVIDIA and the NVIDIA logo are trademarks
of NVIDIA Corporation. This project is an independent analysis and is not affiliated with NVIDIA.
