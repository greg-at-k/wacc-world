from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from calculations import calculate_wacc
from data_sources import (
    BETA_URL,
    COUNTRIES,
    COUNTRY_BY_NAME,
    OECD_PAGE_URL,
    RATINGS_URL,
    TRADING_ECONOMICS_URL,
    fetch_bbb_spread,
    fetch_bond_yield,
    fetch_industry_betas,
    fetch_oecd_tax_rates,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_INDUSTRY = "Software (System & Application)"
US_COUNTRY = COUNTRY_BY_NAME["United States"]

st.set_page_config(
    page_title="International Cost of Capital",
    page_icon="🌐",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1320px;}
      [data-testid="stMetric"] {background: #f6f8fb; border: 1px solid #e3e8ef;
        border-radius: 12px; padding: 0.8rem 1rem;}
      .source-card {background: #f8fafc; border-left: 4px solid #315a8a;
        padding: .65rem .9rem; border-radius: 4px; margin-bottom: .5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_betas():
    return fetch_industry_betas()


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_taxes():
    return fetch_oecd_tax_rates()


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_spread():
    return fetch_bbb_spread()


@st.cache_data(ttl=60 * 60, show_spinner=False)
def cached_yield(country_name: str):
    return fetch_bond_yield(COUNTRY_BY_NAME[country_name])


def load_betas():
    try:
        frame, source_date = cached_betas()
        return frame, source_date, "Live"
    except Exception as exc:
        frame = pd.read_csv(DATA_DIR / "fallback_betas.csv")
        source_date = str(frame.pop("source_date").iloc[0])
        return frame, source_date, f"Saved snapshot ({exc})"


def load_taxes():
    try:
        frame, source_date = cached_taxes()
        return frame, source_date, "Live"
    except Exception as exc:
        frame = pd.read_csv(DATA_DIR / "fallback_tax_rates.csv")
        source_date = str(frame.pop("source_year").iloc[0])
        return frame, source_date, f"Saved snapshot ({exc})"


def load_spread():
    try:
        value, source_date = cached_spread()
        return value, source_date, "Live"
    except Exception as exc:
        return 0.0111, "January 2026", f"Saved snapshot ({exc})"


def load_yield(country_name: str):
    try:
        value, source_date, url = cached_yield(country_name)
        return value, source_date, url, "Live"
    except Exception as exc:
        # The opening default remains usable if Trading Economics is temporarily down.
        if country_name == "United States":
            return (
                0.05136,
                "2026-11-13",
                "https://tradingeconomics.com/united-states/government-bond-yield",
                f"Saved snapshot ({exc})",
            )
        return None, "Unavailable", f"https://tradingeconomics.com/{COUNTRY_BY_NAME[country_name].slug}/government-bond-yield", f"Manual value required ({exc})"


def percent_input(label: str, auto_value: float | None, key: str, help_text: str):
    force_manual = auto_value is None
    manual = st.toggle(
        f"Override {label}", value=force_manual, key=f"{key}_toggle", disabled=force_manual
    )
    displayed = 0.0 if auto_value is None else auto_value * 100
    entered = st.number_input(
        label,
        min_value=0.0,
        max_value=100.0,
        value=float(displayed),
        step=0.01,
        format="%.4f",
        key=f"{key}_value",
        disabled=not manual,
        help=help_text,
    )
    return entered / 100 if manual else auto_value, manual


st.title("International Cost of Capital")
st.caption("Compare project financing in USD and a selected country's currency.")

refresh_col, note_col = st.columns([1, 5], vertical_alignment="center")
with refresh_col:
    if st.button("↻ Refresh source data", type="primary", width="stretch"):
        st.cache_data.clear()
        st.session_state["refresh_notice"] = True
        st.rerun()
with note_col:
    if st.session_state.pop("refresh_notice", False):
        st.success("Source caches cleared and data refreshed.")

with st.spinner("Loading public data sources..."):
    betas, beta_date, beta_status = load_betas()
    taxes, tax_year, tax_status = load_taxes()
    usd_spread_auto, spread_date, spread_status = load_spread()

tax_by_iso = dict(zip(taxes["iso3"], taxes["tax_rate"]))
available_countries = [country for country in COUNTRIES if country.iso3 in tax_by_iso]
country_names = [country.name for country in available_countries]

with st.sidebar:
    st.header("Project assumptions")
    industry = st.selectbox(
        "Industry",
        betas["industry"].tolist(),
        index=betas["industry"].tolist().index(DEFAULT_INDUSTRY),
    )
    country_name = st.selectbox(
        "Target country",
        country_names,
        index=country_names.index("United States"),
    )
    selected_country = COUNTRY_BY_NAME[country_name]
    erp = st.slider(
        "Equity risk premium",
        min_value=0.0,
        max_value=15.0,
        value=6.5,
        step=0.1,
        format="%.1f%%",
    ) / 100
    debt_share = st.slider(
        "Target debt financing",
        min_value=0,
        max_value=90,
        value=30,
        step=1,
        format="%d%%",
    ) / 100

with st.spinner(f"Loading {country_name} bond yield..."):
    usd_yield_auto, usd_yield_date, usd_yield_url, usd_yield_status = load_yield("United States")
    if country_name == "United States":
        foreign_yield_auto = usd_yield_auto
        foreign_yield_date = usd_yield_date
        foreign_yield_url = usd_yield_url
        foreign_yield_status = usd_yield_status
    else:
        (
            foreign_yield_auto,
            foreign_yield_date,
            foreign_yield_url,
            foreign_yield_status,
        ) = load_yield(country_name)

beta_auto = float(
    betas.loc[betas["industry"] == industry, "unlevered_beta"].iloc[0]
)
us_tax_auto = float(tax_by_iso["USA"])
foreign_tax_auto = float(tax_by_iso[selected_country.iso3])

st.subheader("Tax jurisdiction")
if country_name == "United States":
    tax_choice = "United States"
    st.caption("The U.S. tax rate applies because the target country is the United States.")
else:
    tax_choice = st.radio(
        "Use the same project tax rate in both financing currencies:",
        ["United States", country_name],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
    )

with st.expander("Manual overrides", expanded=False):
    st.caption("Switch on any override to replace the fetched value. Percentages are annual rates.")
    col1, col2 = st.columns(2)
    with col1:
        beta_override = st.toggle("Override unlevered beta", value=False)
        beta_entered = st.number_input(
            "Unlevered beta",
            min_value=0.0,
            max_value=10.0,
            value=beta_auto,
            step=0.01,
            format="%.4f",
            disabled=not beta_override,
        )
        usd_spread, usd_spread_manual = percent_input(
            "USD BBB spread",
            usd_spread_auto,
            "usd_spread",
            "Damodaran Baa2/BBB spread for large non-financial service firms.",
        )
        usd_yield, usd_yield_manual = percent_input(
            "U.S. 10-year government yield",
            usd_yield_auto,
            "usd_yield",
            "Trading Economics 10-year government bond yield.",
        )
    with col2:
        us_tax, us_tax_manual = percent_input(
            "U.S. corporate tax rate", us_tax_auto, "us_tax", "OECD combined statutory rate."
        )
        if country_name == "United States":
            foreign_tax, foreign_tax_manual = us_tax, us_tax_manual
            foreign_yield, foreign_yield_manual = usd_yield, usd_yield_manual
            st.info("For a U.S. target, both currency columns use the same U.S. tax rate and yield.")
        else:
            foreign_tax, foreign_tax_manual = percent_input(
                f"{country_name} corporate tax rate",
                foreign_tax_auto,
                f"foreign_tax_{selected_country.iso3}",
                "OECD combined statutory rate.",
            )
            foreign_yield, foreign_yield_manual = percent_input(
                f"{country_name} 10-year government yield",
                foreign_yield_auto,
                f"foreign_yield_{selected_country.iso3}",
                "Trading Economics 10-year government bond yield.",
            )

    unlevered_beta = beta_entered if beta_override else beta_auto
    selected_tax = us_tax if tax_choice == "United States" else foreign_tax
    auto_foreign_spread = usd_spread * (1 + foreign_yield) / (1 + usd_yield)
    if country_name == "United States":
        foreign_spread_manual = False
        foreign_spread_entered = auto_foreign_spread
    else:
        foreign_spread_manual = st.toggle(
            f"Override {selected_country.currency} BBB spread", value=False
        )
        foreign_spread_entered = st.number_input(
            f"{selected_country.currency} BBB spread",
            min_value=0.0,
            max_value=100.0,
            value=float(auto_foreign_spread * 100),
            step=0.01,
            format="%.4f",
            disabled=not foreign_spread_manual,
            help="When off, the USD spread is scaled by (1 + foreign yield) / (1 + U.S. yield).",
        ) / 100

foreign_spread_override = foreign_spread_entered if foreign_spread_manual else None

results = calculate_wacc(
    unlevered_beta=unlevered_beta,
    tax_rate=selected_tax,
    debt_share=debt_share,
    equity_risk_premium=erp,
    usd_yield=usd_yield,
    foreign_yield=foreign_yield,
    usd_spread=usd_spread,
    foreign_spread_override=foreign_spread_override,
)

st.divider()
st.subheader("Results")
usd_col, foreign_col = st.columns(2)


def result_card(container, heading, values):
    with container:
        st.markdown(f"### {heading}")
        a, b = st.columns(2)
        a.metric("Cost of equity", f"{values.cost_of_equity:.4%}")
        b.metric("Pretax cost of debt", f"{values.pretax_cost_of_debt:.4%}")
        c, d = st.columns(2)
        c.metric("After-tax cost of debt", f"{values.after_tax_cost_of_debt:.4%}")
        d.metric("WACC", f"{values.wacc:.4%}")


result_card(usd_col, "USD", results.usd)
result_card(foreign_col, f"{selected_country.currency} · {country_name}", results.foreign)

detail_cols = st.columns(4)
detail_cols[0].metric("Unlevered beta", f"{unlevered_beta:.4f}")
detail_cols[1].metric("Relevered beta", f"{results.levered_beta:.4f}")
detail_cols[2].metric("Project tax rate", f"{selected_tax:.2%}")
detail_cols[3].metric(
    f"{selected_country.currency} BBB spread", f"{results.foreign_spread:.4%}"
)

with st.expander("Calculation method and main assumptions"):
    st.markdown(
        f"""
1. **Relever beta:** βE = βU × [1 + (1 − τ) × d/(1 − d)].
2. **USD cost of equity:** Re = U.S. 10-year yield + βE × ERP.
3. **Foreign cost of equity:** 1 + Re* = (1 + Re) × (1 + Rf*)/(1 + Rf).
4. **Debt:** Rd = Rf + spread. The automatic foreign spread is the USD spread × (1 + Rf*)/(1 + Rf).
5. **WACC:** (1 − d) × Re + d × Rd × (1 − τ).

The calculation uses the **{tax_choice} tax rate ({selected_tax:.2%})** in both currencies,
target market-value debt of **{debt_share:.1%}**, and ERP of **{erp:.1%}**. Government
yields proxy for risk-free rates. It assumes equal real rates/relative PPP, zero debt and
tax-shield betas, fully usable interest deductions, constant target leverage, and no separate
country equity-risk premium. Displayed values are rounded; calculations retain full precision.
"""
    )

comparison_rows = []
for row in betas.itertuples(index=False):
    industry_result = calculate_wacc(
        unlevered_beta=float(row.unlevered_beta),
        tax_rate=selected_tax,
        debt_share=debt_share,
        equity_risk_premium=erp,
        usd_yield=usd_yield,
        foreign_yield=foreign_yield,
        usd_spread=usd_spread,
        foreign_spread_override=foreign_spread_override,
    )
    comparison_rows.append(
        {
            "Industry": row.industry,
            "Unlevered beta": row.unlevered_beta,
            "Relevered beta": industry_result.levered_beta,
            "USD cost of equity": industry_result.usd.cost_of_equity,
            "USD WACC": industry_result.usd.wacc,
            f"{selected_country.currency} cost of equity": industry_result.foreign.cost_of_equity,
            f"{selected_country.currency} WACC": industry_result.foreign.wacc,
        }
    )
comparison = pd.DataFrame(comparison_rows)

st.subheader("All-industry comparison")
st.dataframe(
    comparison.style.format(
        {
            "Unlevered beta": "{:.4f}",
            "Relevered beta": "{:.4f}",
            "USD cost of equity": "{:.4%}",
            "USD WACC": "{:.4%}",
            f"{selected_country.currency} cost of equity": "{:.4%}",
            f"{selected_country.currency} WACC": "{:.4%}",
        }
    ).apply(
        lambda row: ["background-color: #e8f1fb" if row["Industry"] == industry else ""] * len(row),
        axis=1,
    ),
    width="stretch",
    hide_index=True,
    height=480,
)

summary = pd.DataFrame(
    [
        {
            "Industry": industry,
            "Target country": country_name,
            "Foreign currency": selected_country.currency,
            "Tax jurisdiction": tax_choice,
            "Tax rate": selected_tax,
            "ERP": erp,
            "Debt share": debt_share,
            "Unlevered beta": unlevered_beta,
            "Relevered beta": results.levered_beta,
            "U.S. 10Y yield": usd_yield,
            f"{country_name} 10Y yield": foreign_yield,
            "USD BBB spread": usd_spread,
            f"{selected_country.currency} BBB spread": results.foreign_spread,
            "USD cost of equity": results.usd.cost_of_equity,
            "USD pretax cost of debt": results.usd.pretax_cost_of_debt,
            "USD WACC": results.usd.wacc,
            f"{selected_country.currency} cost of equity": results.foreign.cost_of_equity,
            f"{selected_country.currency} pretax cost of debt": results.foreign.pretax_cost_of_debt,
            f"{selected_country.currency} WACC": results.foreign.wacc,
        }
    ]
)

download1, download2 = st.columns(2)
download1.download_button(
    "Download selected result (CSV)",
    summary.to_csv(index=False).encode("utf-8"),
    "international_wacc_result.csv",
    "text/csv",
    width="stretch",
)
download2.download_button(
    "Download all-industry comparison (CSV)",
    comparison.to_csv(index=False).encode("utf-8"),
    "international_wacc_all_industries.csv",
    "text/csv",
    width="stretch",
)

st.divider()
st.subheader("Sources and dates")
st.markdown(
    f"""
<div class="source-card"><b>Industry unlevered betas</b> — <a href="{BETA_URL}">Damodaran U.S. industry data</a><br>
As of {beta_date}; status: {beta_status}</div>
<div class="source-card"><b>Corporate tax rates</b> — <a href="{OECD_PAGE_URL}">OECD Corporate Tax Statistics</a><br>
Data year {tax_year}; status: {tax_status}</div>
<div class="source-card"><b>USD BBB borrowing spread</b> — <a href="{RATINGS_URL}">Damodaran ratings and default spreads</a><br>
As of {spread_date}; Baa2/BBB for large non-financial service firms; status: {spread_status}</div>
<div class="source-card"><b>U.S. 10-year government yield</b> — <a href="{usd_yield_url}">Trading Economics</a><br>
As of {usd_yield_date}; status: {usd_yield_status}</div>
<div class="source-card"><b>{country_name} 10-year government yield</b> — <a href="{foreign_yield_url}">Trading Economics</a><br>
As of {foreign_yield_date}; status: {foreign_yield_status}</div>
""",
    unsafe_allow_html=True,
)
st.caption(
    f"Trading Economics country directory: {TRADING_ECONOMICS_URL}. Manual overrides are identified by their active switches above."
)

