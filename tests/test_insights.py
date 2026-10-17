import pandas as pd
import pytest

from nepal_salary_calculation import insights as ins
from nepal_salary_calculation.tax import (
    MonthEntry,
    Settings,
    calculate_annual_tax,
    calculate_salary,
    min_monthly_cit,
)


def sample(**overrides):
    entries = [MonthEntry(basic_salary=60_000, allowance=40_000, project_incentive=50_000, cit=23_067) for _ in range(12)]
    entries[2] = MonthEntry(60_000, 40_000, 50_000, 60_000, 0, 23_067)
    settings = Settings(standard_cit=23_067, **overrides)
    return calculate_salary(entries, settings)


def test_breakdown_adds_up_to_the_pay_slips():
    result = sample()
    b = ins.breakdown(result)
    assert b.net == pytest.approx(result.total_net_pay)
    assert b.gross == pytest.approx(result.annual.gross_income)


def test_waterfall_ends_at_net_take_home():
    b = ins.breakdown(sample())
    frame = ins.waterfall_frame(b)
    assert frame.iloc[0]["Step"] == "Gross income" and frame.iloc[-1]["Step"] == "Net take-home"
    deductions = frame[frame["Kind"] == "Deduction"]
    assert deductions.iloc[-1]["End"] == pytest.approx(b.net)
    assert ins.split_frame(b)["Share"].sum() == pytest.approx(1.0)


@pytest.mark.parametrize("settings", [{}, {"female_rebate": True}, {"ssf_enrolled": False}, {"handicapped": True}])
def test_tax_for_taxable_matches_the_engine(settings):
    result = sample(**settings)
    a = result.annual
    assert ins.tax_for_taxable(a.taxable_income, result.settings) == pytest.approx(a.annual_tax)


def test_marginal_rate_and_headroom():
    result = sample()
    rate, headroom = ins.marginal_rate(result.annual, result.settings)
    assert rate == 0.20  # taxable income 20,04,000 - 5,00,000 sits in the 15-25 lakh slab
    assert headroom == pytest.approx(2_500_000 - result.annual.taxable_income)


def test_marginal_rate_top_slab_has_no_headroom():
    entries = [MonthEntry(basic_salary=500_000) for _ in range(12)]
    result = calculate_salary(entries, Settings())
    rate, headroom = ins.marginal_rate(result.annual, result.settings)
    assert rate == 0.29 and headroom is None


def test_cit_scenario_saves_tax_up_to_the_cap_only():
    entries = [MonthEntry(basic_salary=60_000, allowance=40_000) for _ in range(12)]
    result = calculate_salary(entries, Settings())
    best = min_monthly_cit(entries, Settings())
    at_best = ins.cit_scenario(result, best)
    beyond = ins.cit_scenario(result, best + 20_000)
    assert at_best.tax_change < 0
    assert beyond.tax == pytest.approx(at_best.tax)
    assert beyond.saved_change == pytest.approx((best + 20_000) * 12)


def test_cit_curve_is_non_increasing():
    curve = ins.cit_curve(sample(), 60_000)
    assert curve["Income tax"].is_monotonic_decreasing


def test_bonus_scenario_taxes_at_the_marginal_rate():
    result = sample()
    s = ins.bonus_scenario(result, 100_000)
    assert s.extra_tax == pytest.approx(20_000)
    assert s.keep == pytest.approx(80_000)
    assert ins.bonus_scenario(result, 0).extra_tax == 0
    curve = ins.bonus_curve(result, 1_000_000)
    assert (curve["You keep"] + curve["Tax"]).tolist() == pytest.approx(curve["Bonus"].tolist())
    assert curve["Rate"].iloc[1] == pytest.approx(0.20)


def test_monthly_frames_and_slabs():
    result = sample()
    income = ins.monthly_income_frame(result)
    assert income["Amount"].sum() == pytest.approx(result.annual.gross_income)
    assert set(ins.monthly_net_frame(result).columns) == {"Month", "Gross", "Net paid", "TDS"}
    slabs = ins.slab_frame(result.annual)
    assert slabs["Filled"].sum() == pytest.approx(result.annual.taxable_income)
    assert slabs.iloc[0]["Rate"] == "waived (SSF)"


def test_insights_mention_the_key_facts():
    text = " ".join(ins.insights(sample()))
    assert "You keep" in text and "next rupee" in text and "highest-paid month" in text


def test_insights_empty_without_income():
    result = calculate_salary([MonthEntry() for _ in range(12)], Settings())
    assert ins.insights(result) == []
    assert isinstance(ins.split_frame(ins.breakdown(result)), pd.DataFrame)
    assert calculate_annual_tax(result.entries, result.settings).annual_tax == 0


def test_month_breakdown_matches_the_pay_slip():
    result = sample()
    for slip in result.slips:
        b = ins.month_breakdown(slip)
        assert b.net == pytest.approx(slip.net_pay)
        assert b.gross == pytest.approx(slip.gross_income)
    text = " ".join(ins.month_insights(result, 2))
    assert "Ashwin" in text and "TDS this month" in text and "above your average month" in text


def test_peak_month_names_what_stands_out():
    month, why = ins.peak_month(sample())
    assert month == "Ashwin" and "festival allowance" in why
    flat = calculate_salary([MonthEntry(basic_salary=50_000) for _ in range(12)], Settings())
    assert ins.peak_month(flat) is None


def test_slab_crossings_and_tax_at_cit():
    result = sample()
    crossings = ins.slab_crossings(result.annual, 1_500_000)
    assert [rate for _, rate in crossings] == [0.27]
    assert crossings[0][0] == pytest.approx(2_500_000 - result.annual.taxable_income)
    curve = ins.cit_curve(result, 40_000)
    assert ins.tax_at_cit(curve, 0) == curve["Income tax"].iloc[0]


def test_lakh_labels_are_short():
    assert ins.lakh(1_159_93) == "1.16 L"
    assert ins.lakh(1_000_000) == "10 L"
    assert ins.lakh(150_000) == "1.5 L"
    assert ins.lakh(25_000_000) == "2.5 Cr"
