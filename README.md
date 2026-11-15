# International Cost of Capital App

A Streamlit app that compares a project's cost of equity, borrowing cost, and
weighted average cost of capital (WACC) in USD and a selected country's local
currency.

## Features

- Refreshable U.S. industry unlevered betas from Aswath Damodaran
- Refreshable Baa2/BBB USD borrowing spread from Damodaran
- Combined statutory corporate tax rates from OECD Corporate Tax Statistics
- Country-specific 10-year government yields from Trading Economics, without an API key
- Manual overrides for every fetched calculation input
- U.S./foreign project-tax-rate switch
- Side-by-side USD and local-currency results
- Live step-by-step walkthrough with the configured values substituted into each formula
- All-industry comparison and CSV downloads
- Source dates, fetch status, and transparent assumptions

The opening defaults are Software (System & Application), United States, the
U.S. tax rate, a 6.5% equity risk premium, and 30% debt financing.

## Formulas

Rates are stored as decimals and calculations retain full precision.

```text
D/E = d / (1 - d)
beta_E = beta_U * [1 + (1 - tax) * D/E]
Re_USD = Rf_USD + beta_E * ERP
1 + Re_foreign = (1 + Re_USD) * (1 + Rf_foreign) / (1 + Rf_USD)
spread_foreign = spread_USD * (1 + Rf_foreign) / (1 + Rf_USD)
Rd = Rf + spread
WACC = (1 - d) * Re + d * Rd * (1 - tax)
```

These formulas reproduce the Colombia class example: 10.6486% USD cost of
equity, 8.5265% USD WACC, 19.1600% COP cost of equity, and 16.0670% COP WACC.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Run the calculation tests with:

```powershell
pytest -q
```

## Data behavior

The refresh button clears Streamlit's caches and requests the sources again.
Betas, tax rates, and the BBB spread are cached for 24 hours; bond yields are
cached for one hour. If a workbook source is temporarily unavailable, the app
uses a clearly labeled saved snapshot. If a selected-country yield cannot be
retrieved, the app requires a manual value instead of silently substituting a
different country.

Trading Economics' aggregate bonds table is protected by a browser challenge.
The app therefore reads the public country-specific 10-year bond page, which
does not require an API key.

## Sources

- [Damodaran U.S. industry betas](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls)
- [Damodaran ratings and default spreads](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html)
- [OECD Corporate Tax Statistics](https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html)
- [Trading Economics government bond yields](https://tradingeconomics.com/bonds)

## Deploy on Streamlit Community Cloud

1. Push this repository to GitHub.
2. In Streamlit Community Cloud, select the repository and `app.py`.
3. Deploy. The app uses only public sources and requires no secrets.

This app is an educational model, not investment advice. Government yields are
risk-free proxies and may contain sovereign, liquidity, and term premia.

