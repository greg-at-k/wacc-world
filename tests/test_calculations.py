import pytest

from calculations import calculate_wacc, convert_rate, convert_spread, lever_beta


def test_colombia_class_example():
    result = calculate_wacc(
        unlevered_beta=0.80,
        tax_rate=0.35,
        debt_share=0.30,
        equity_risk_premium=0.065,
        usd_yield=0.04,
        foreign_yield=0.12,
        usd_spread=0.015,
    )

    assert result.levered_beta == pytest.approx(1.022857142857)
    assert result.usd.cost_of_equity == pytest.approx(0.106485714286)
    assert result.usd.pretax_cost_of_debt == pytest.approx(0.055)
    assert result.usd.wacc == pytest.approx(0.085265)
    assert result.foreign_spread == pytest.approx(0.016153846154)
    assert result.foreign.cost_of_equity == pytest.approx(0.1916)
    assert result.foreign.pretax_cost_of_debt == pytest.approx(0.136153846154)
    assert result.foreign.wacc == pytest.approx(0.16067)


def test_same_currency_produces_same_results():
    result = calculate_wacc(
        unlevered_beta=1.2,
        tax_rate=0.25,
        debt_share=0.30,
        equity_risk_premium=0.065,
        usd_yield=0.05,
        foreign_yield=0.05,
        usd_spread=0.011,
    )
    assert result.foreign.cost_of_equity == pytest.approx(result.usd.cost_of_equity)
    assert result.foreign.pretax_cost_of_debt == pytest.approx(result.usd.pretax_cost_of_debt)
    assert result.foreign.wacc == pytest.approx(result.usd.wacc)


def test_formula_helpers():
    assert lever_beta(0.8, 0.35, 0.30) == pytest.approx(1.022857142857)
    assert convert_rate(0.106485714286, 0.04, 0.12) == pytest.approx(0.1916)
    assert convert_spread(0.015, 0.04, 0.12) == pytest.approx(0.016153846154)


def test_invalid_full_debt_share_is_rejected():
    with pytest.raises(ValueError):
        lever_beta(1.0, 0.25, 1.0)

