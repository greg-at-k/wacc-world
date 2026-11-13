"""Pure finance calculations for the international WACC app.

All rates are decimals (6.5% is 0.065). Keeping this module free of Streamlit
and network code makes the class formulas easy to audit and unit test.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CurrencyResults:
    cost_of_equity: float
    pretax_cost_of_debt: float
    after_tax_cost_of_debt: float
    wacc: float


@dataclass(frozen=True)
class WaccResults:
    levered_beta: float
    foreign_spread: float
    usd: CurrencyResults
    foreign: CurrencyResults

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_rate(name: str, value: float, *, upper: float = 1.0) -> None:
    if not 0 <= value <= upper:
        raise ValueError(f"{name} must be between 0 and {upper:.0%}.")


def lever_beta(unlevered_beta: float, tax_rate: float, debt_share: float) -> float:
    """Relever beta using beta_E = beta_U [1 + (1-tax) D/E]."""
    if unlevered_beta < 0:
        raise ValueError("Unlevered beta cannot be negative.")
    _validate_rate("Tax rate", tax_rate)
    _validate_rate("Debt share", debt_share)
    if debt_share == 1:
        raise ValueError("Debt share must be below 100% so D/E is defined.")
    debt_to_equity = debt_share / (1 - debt_share)
    return unlevered_beta * (1 + (1 - tax_rate) * debt_to_equity)


def convert_rate(rate_usd: float, usd_yield: float, foreign_yield: float) -> float:
    """Convert a USD annual rate using equal real rates and relative PPP."""
    if 1 + usd_yield <= 0:
        raise ValueError("The gross U.S. government yield must be positive.")
    return (1 + rate_usd) * (1 + foreign_yield) / (1 + usd_yield) - 1


def convert_spread(usd_spread: float, usd_yield: float, foreign_yield: float) -> float:
    """Scale the USD spread by the same gross government-yield factor."""
    if usd_spread < 0:
        raise ValueError("Borrowing spread cannot be negative.")
    if 1 + usd_yield <= 0:
        raise ValueError("The gross U.S. government yield must be positive.")
    return usd_spread * (1 + foreign_yield) / (1 + usd_yield)


def calculate_wacc(
    *,
    unlevered_beta: float,
    tax_rate: float,
    debt_share: float,
    equity_risk_premium: float,
    usd_yield: float,
    foreign_yield: float,
    usd_spread: float,
    foreign_spread_override: float | None = None,
) -> WaccResults:
    """Calculate equity, debt, and WACC in USD and a foreign currency."""
    _validate_rate("Tax rate", tax_rate)
    _validate_rate("Debt share", debt_share)
    if debt_share == 1:
        raise ValueError("Debt share must be below 100%.")
    if equity_risk_premium < 0:
        raise ValueError("Equity risk premium cannot be negative.")

    beta_e = lever_beta(unlevered_beta, tax_rate, debt_share)
    usd_equity = usd_yield + beta_e * equity_risk_premium
    foreign_equity = convert_rate(usd_equity, usd_yield, foreign_yield)

    foreign_spread = (
        convert_spread(usd_spread, usd_yield, foreign_yield)
        if foreign_spread_override is None
        else foreign_spread_override
    )
    if foreign_spread < 0:
        raise ValueError("Foreign borrowing spread cannot be negative.")

    usd_debt = usd_yield + usd_spread
    foreign_debt = foreign_yield + foreign_spread
    usd_debt_after_tax = usd_debt * (1 - tax_rate)
    foreign_debt_after_tax = foreign_debt * (1 - tax_rate)

    equity_share = 1 - debt_share
    usd_wacc = equity_share * usd_equity + debt_share * usd_debt_after_tax
    foreign_wacc = (
        equity_share * foreign_equity + debt_share * foreign_debt_after_tax
    )

    return WaccResults(
        levered_beta=beta_e,
        foreign_spread=foreign_spread,
        usd=CurrencyResults(
            cost_of_equity=usd_equity,
            pretax_cost_of_debt=usd_debt,
            after_tax_cost_of_debt=usd_debt_after_tax,
            wacc=usd_wacc,
        ),
        foreign=CurrencyResults(
            cost_of_equity=foreign_equity,
            pretax_cost_of_debt=foreign_debt,
            after_tax_cost_of_debt=foreign_debt_after_tax,
            wacc=foreign_wacc,
        ),
    )

