from __future__ import annotations

from pathlib import Path

import altair as alt
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

with st.sidebar:
    st.header("Calculator controls")
    if st.button("↻ Refresh source data", type="primary", width="stretch"):
        st.cache_data.clear()
        st.session_state["refresh_notice"] = True
        st.rerun()
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
    st.subheader("Project")
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
    st.subheader("Financing assumptions")
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

with st.sidebar:
    st.subheader("Tax jurisdiction")
    if country_name == "United States":
        tax_choice = "United States"
        st.caption("The U.S. rate applies because the target country is the United States.")
    else:
        tax_choice = st.radio(
            "Project tax rate used in both currencies",
            ["United States", country_name],
            index=0,
        )

    with st.expander("Advanced manual overrides", expanded=False):
        st.caption("Switch on an override to replace fetched data. Rates are annual.")
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
overview_tab, walkthrough_tab, industries_tab, sources_tab = st.tabs(
    ["Overview", "Calculation walkthrough", "All industries", "Sources"]
)

with overview_tab:
    wacc_difference = results.foreign.wacc - results.usd.wacc
    yield_difference = foreign_yield - usd_yield
    currency_factor = (1 + foreign_yield) / (1 + usd_yield)

    if country_name == "United States":
        st.markdown(
            f"### {industry} has a **{results.usd.wacc:.2%} USD WACC** under the current assumptions."
        )
        st.info(
            "United States is the baseline, so there is no currency comparison yet. "
            "Select another target country in the sidebar to compare WACCs."
        )
        metric_col, prompt_col = st.columns([1, 2])
        metric_col.metric("USD WACC", f"{results.usd.wacc:.4%}")
        with prompt_col:
            st.markdown("**What to look at next**")
            st.write(
                "A foreign-country selection reveals how the government-yield gap changes "
                "the local-currency cost of equity, borrowing cost, and WACC."
            )
    else:
        direction = "higher" if wacc_difference > 0 else "lower"
        st.markdown(
            f"### Financing {industry} in {selected_country.currency} produces a "
            f"**{results.foreign.wacc:.2%} WACC**—**{abs(wacc_difference) * 100:.2f} percentage points "
            f"{direction}** than its {results.usd.wacc:.2%} USD WACC."
        )
        usd_metric, foreign_metric, difference_metric = st.columns(3)
        usd_metric.metric("USD WACC", f"{results.usd.wacc:.4%}")
        foreign_metric.metric(f"{selected_country.currency} WACC", f"{results.foreign.wacc:.4%}")
        difference_metric.metric(
            "Local minus USD", f"{wacc_difference * 100:+.4f} pp"
        )

    chart_rows = [
        ("Cost of equity", "USD", results.usd.cost_of_equity),
        ("After-tax debt", "USD", results.usd.after_tax_cost_of_debt),
        ("WACC", "USD", results.usd.wacc),
    ]
    if country_name != "United States":
        chart_rows.extend(
            [
                ("Cost of equity", selected_country.currency, results.foreign.cost_of_equity),
                ("After-tax debt", selected_country.currency, results.foreign.after_tax_cost_of_debt),
                ("WACC", selected_country.currency, results.foreign.wacc),
            ]
        )
    chart_data = pd.DataFrame(chart_rows, columns=["Component", "Currency", "Rate"])
    component_chart = (
        alt.Chart(chart_data)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Component:N", title=None, sort=["Cost of equity", "After-tax debt", "WACC"]),
            xOffset="Currency:N",
            y=alt.Y("Rate:Q", title="Annual rate", axis=alt.Axis(format=".1%")),
            color=alt.Color(
                "Currency:N",
                scale=alt.Scale(range=["#315a8a", "#d97706"]),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("Component:N"),
                alt.Tooltip("Currency:N"),
                alt.Tooltip("Rate:Q", format=".4%"),
            ],
        )
        .properties(height=310)
    )
    st.altair_chart(component_chart, width="stretch")

    st.markdown("#### What drives the result?")
    if country_name == "United States":
        st.write(
            f"The USD calculation uses a {usd_yield:.2%} government-yield proxy, "
            f"a {usd_spread:.2%} BBB spread, and a {selected_tax:.2%} project tax rate."
        )
    else:
        driver_cols = st.columns(2)
        driver_cols[0].metric(
            "Government-yield gap", f"{yield_difference * 100:+.4f} pp"
        )
        driver_cols[1].metric("Currency conversion factor", f"{currency_factor:.6f}x")
        st.write(
            f"{country_name}'s {foreign_yield:.2%} 10-year yield is compared with the "
            f"{usd_yield:.2%} U.S. yield. That gap drives the conversion of the USD cost "
            "of equity and BBB spread into local-currency terms."
        )

    with st.expander("Detailed rates and assumptions"):
        if country_name == "United States":
            detail_frame = pd.DataFrame(
                [
                    ("Cost of equity", results.usd.cost_of_equity),
                    ("Pretax cost of debt", results.usd.pretax_cost_of_debt),
                    ("After-tax cost of debt", results.usd.after_tax_cost_of_debt),
                    ("WACC", results.usd.wacc),
                ],
                columns=["Measure", "USD"],
            )
        else:
            detail_frame = pd.DataFrame(
                [
                    ("Cost of equity", results.usd.cost_of_equity, results.foreign.cost_of_equity),
                    ("Pretax cost of debt", results.usd.pretax_cost_of_debt, results.foreign.pretax_cost_of_debt),
                    ("After-tax cost of debt", results.usd.after_tax_cost_of_debt, results.foreign.after_tax_cost_of_debt),
                    ("WACC", results.usd.wacc, results.foreign.wacc),
                ],
                columns=["Measure", "USD", selected_country.currency],
            )
        st.dataframe(
            detail_frame.style.format(
                {column: "{:.4%}" for column in detail_frame.columns if column != "Measure"}
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            f"Unlevered beta {unlevered_beta:.4f} · Relevered beta {results.levered_beta:.4f} · "
            f"Tax rate {selected_tax:.2%} · ERP {erp:.2%} · Debt share {debt_share:.1%}"
        )

with walkthrough_tab:
    def latex_percent(value: float) -> str:
        return f"{value * 100:.4f}\\%"

    st.markdown("### Inputs currently in use")
    selected_tax_manual = us_tax_manual if tax_choice == "United States" else foreign_tax_manual
    input_rows = [
        ("Industry", industry, "User selection"),
        ("Target country / currency", f"{country_name} / {selected_country.currency}", "User selection"),
        ("Unlevered beta", f"{unlevered_beta:.6f}", "Manual override" if beta_override else "Damodaran"),
        ("Project tax rate", f"{selected_tax:.4%}", "Manual override" if selected_tax_manual else f"OECD - {tax_choice}"),
        ("Equity risk premium", f"{erp:.4%}", "User assumption"),
        ("Debt share", f"{debt_share:.4%}", "User assumption"),
        ("U.S. 10-year yield", f"{usd_yield:.4%}", "Manual override" if usd_yield_manual else "Trading Economics"),
        ("USD BBB spread", f"{usd_spread:.4%}", "Manual override" if usd_spread_manual else "Damodaran Baa2/BBB"),
    ]
    if country_name != "United States":
        input_rows.extend(
            [
                (f"{country_name} 10-year yield", f"{foreign_yield:.4%}", "Manual override" if foreign_yield_manual else "Trading Economics"),
                (f"{selected_country.currency} BBB spread", f"{results.foreign_spread:.4%}", "Manual override" if foreign_spread_manual else "Automatically converted"),
            ]
        )
    input_snapshot = pd.DataFrame(input_rows, columns=["Input", "Value", "Mode / source"])
    st.dataframe(input_snapshot, hide_index=True, width="stretch")
    st.caption("Each equation below substitutes these live values. Calculations retain full precision; displayed values are rounded.")

    debt_to_equity = debt_share / (1 - debt_share)
    currency_factor = (1 + foreign_yield) / (1 + usd_yield)

    st.markdown("#### 1. Convert the target debt share to D/E")
    st.latex(
        rf"\frac{{D}}{{E}}=\frac{{d}}{{1-d}}=\frac{{{debt_share:.6f}}}{{1-{debt_share:.6f}}}={debt_to_equity:.6f}"
    )

    st.markdown("#### 2. Relever the industry beta")
    st.latex(
        rf"\beta_E=\beta_U\left[1+(1-\tau)\frac{{D}}{{E}}\right]"
        rf"={unlevered_beta:.6f}\left[1+(1-{selected_tax:.6f})({debt_to_equity:.6f})\right]"
        rf"={results.levered_beta:.6f}"
    )

    st.markdown("#### 3. Calculate the cost of equity in USD")
    st.latex(
        rf"R_e=R_f+\beta_E(ERP)={latex_percent(usd_yield)}+({results.levered_beta:.6f})({latex_percent(erp)})"
        rf"={latex_percent(results.usd.cost_of_equity)}"
    )

    st.markdown("#### 4. Calculate the USD borrowing cost")
    st.latex(
        rf"R_d=R_f+s={latex_percent(usd_yield)}+{latex_percent(usd_spread)}={latex_percent(results.usd.pretax_cost_of_debt)}"
    )
    st.latex(
        rf"R_d(1-\tau)={latex_percent(results.usd.pretax_cost_of_debt)}(1-{latex_percent(selected_tax)})"
        rf"={latex_percent(results.usd.after_tax_cost_of_debt)}"
    )

    st.markdown("#### 5. Calculate WACC in USD")
    st.latex(
        rf"WACC=(1-d)R_e+dR_d(1-\tau)"
        rf"=({1-debt_share:.4f})({latex_percent(results.usd.cost_of_equity)})"
        rf"+({debt_share:.4f})({latex_percent(results.usd.pretax_cost_of_debt)})(1-{latex_percent(selected_tax)})"
        rf"={latex_percent(results.usd.wacc)}"
    )

    if country_name == "United States":
        st.success(f"The USD calculation is complete: WACC = {results.usd.wacc:.4%}.")
        st.info(
            "Select a country other than the United States in the sidebar to continue "
            "with Steps 6–9 and compare USD WACC with local-currency WACC."
        )
    else:
        st.markdown(f"#### 6. Find the USD-to-{selected_country.currency} conversion factor")
        st.latex(
            rf"F=\frac{{1+R_f^*}}{{1+R_f}}=\frac{{1+{foreign_yield:.6f}}}{{1+{usd_yield:.6f}}}"
            rf"={currency_factor:.6f}"
        )

        st.markdown(f"#### 7. Convert the cost of equity to {selected_country.currency}")
        st.latex(
            rf"1+R_e^*=(1+R_e)F=(1+{results.usd.cost_of_equity:.6f})({currency_factor:.6f})"
        )
        st.latex(rf"R_e^*={latex_percent(results.foreign.cost_of_equity)}")

        st.markdown(f"#### 8. Calculate the {selected_country.currency} borrowing cost")
        if foreign_spread_manual:
            st.markdown(
                f"The automatic spread conversion is switched off, so the configured "
                f"manual spread of **{results.foreign_spread:.4%}** is used."
            )
        else:
            st.latex(
                rf"s^*=sF={latex_percent(usd_spread)}({currency_factor:.6f})={latex_percent(results.foreign_spread)}"
            )
        st.latex(
            rf"R_d^*=R_f^*+s^*={latex_percent(foreign_yield)}+{latex_percent(results.foreign_spread)}"
            rf"={latex_percent(results.foreign.pretax_cost_of_debt)}"
        )
        st.latex(
            rf"R_d^*(1-\tau)={latex_percent(results.foreign.pretax_cost_of_debt)}(1-{latex_percent(selected_tax)})"
            rf"={latex_percent(results.foreign.after_tax_cost_of_debt)}"
        )

        st.markdown(f"#### 9. Calculate WACC in {selected_country.currency}")
        st.latex(
            rf"WACC^*=(1-d)R_e^*+dR_d^*(1-\tau)"
            rf"=({1-debt_share:.4f})({latex_percent(results.foreign.cost_of_equity)})"
            rf"+({debt_share:.4f})({latex_percent(results.foreign.pretax_cost_of_debt)})(1-{latex_percent(selected_tax)})"
            rf"={latex_percent(results.foreign.wacc)}"
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

with industries_tab:
    st.markdown("### All-industry comparison")
    st.caption(
        f"Every industry uses the current {tax_choice} tax rate, {erp:.1%} ERP, "
        f"and {debt_share:.0%} target debt share. The selected industry is highlighted."
    )
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
        height=520,
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

with sources_tab:
    st.markdown("### Sources and dates")
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
        f"Trading Economics country directory: {TRADING_ECONOMICS_URL}. "
        "Manual overrides are identified in the sidebar and calculation walkthrough."
    )

