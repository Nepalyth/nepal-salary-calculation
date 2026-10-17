from dataclasses import replace

import pytest

from nepal_salary_calculation.tax import (
    SSF_BASIS_EMPLOYEE,
    SSF_BASIS_FULL,
    TDS_EVEN,
    MonthEntry,
    Settings,
    calculate_annual_tax,
    calculate_salary,
    format_npr,
    min_monthly_cit,
)


def flat(**kwargs) -> list[MonthEntry]:
    return [MonthEntry(**kwargs) for _ in range(12)]


def test_user_payslips_match_exactly():
    """Real payslips: Shrawan, Bhadra (+leave encashment) and Ashwin (+festival) 2083."""
    base = {"basic_salary": 72_000, "allowance": 48_000, "project_incentive": 71_000}
    entries = [MonthEntry(**base, cit=19_400) for _ in range(12)]
    entries[0] = MonthEntry(**base, cit=46_800)
    entries[1] = MonthEntry(**base, cit=19_400, leave_encashment=20_000)
    entries[2] = MonthEntry(**base, cit=19_400, festival_allowance=72_000)

    result = calculate_salary(entries, Settings(standard_cit=19_400))
    shrawan, bhadra, ashwin = result.slips[:3]

    assert (shrawan.gross_income, shrawan.ssf_deduction, shrawan.tds) == (205_400, 22_320, 11_913)
    assert shrawan.total_deductions == 81_033
    assert shrawan.net_pay == 124_367

    assert (bhadra.gross_income, bhadra.tds) == (225_400, 12_277)
    assert bhadra.total_deductions == 53_997
    assert bhadra.net_pay == 171_403

    assert (ashwin.gross_income, ashwin.ssf_income, ashwin.ssf_deduction) == (277_400, 14_400, 22_320)
    assert ashwin.tds == 13_717
    assert ashwin.total_deductions == 55_437
    assert ashwin.net_pay == 221_963


def test_payroll_tds_settles_to_annual_tax():
    entries = flat(basic_salary=72_000, allowance=48_000, project_incentive=71_000, cit=19_400)
    entries[2] = MonthEntry(72_000, 48_000, 71_000, 72_000, 0, 19_400)
    entries[11] = MonthEntry(72_000, 48_000, 71_000, 0, 150_000, 19_400)
    result = calculate_salary(entries, Settings(standard_cit=19_400))
    assert result.total_tds == pytest.approx(result.annual.annual_tax, abs=1)


def test_even_method():
    result = calculate_salary(flat(basic_salary=150_000, allowance=50_000), Settings(tds_method=TDS_EVEN))
    assert result.total_tds == pytest.approx(result.annual.annual_tax)
    assert len({s.tds for s in result.slips}) == 1


def test_ssf_payroll_style_adds_employer_share_to_income():
    entries = flat(basic_salary=72_000, allowance=48_000)
    slip = calculate_salary(entries, Settings()).slips[0]
    assert slip.ssf_income == 14_400
    assert slip.ssf_deduction == 22_320  # 31% of basic
    assert slip.gross_income == 134_400


def test_ssf_employee_only_style():
    entries = flat(basic_salary=72_000, allowance=48_000)
    slip = calculate_salary(entries, Settings(ssf_basis=SSF_BASIS_EMPLOYEE)).slips[0]
    assert slip.ssf_income == 0
    assert slip.ssf_deduction == pytest.approx(7_920)
    assert slip.gross_income == 120_000


def test_not_in_ssf_pays_one_percent_first_slab():
    entries = flat(basic_salary=80_000)
    with_ssf = calculate_annual_tax(entries, Settings(ssf_basis=SSF_BASIS_EMPLOYEE))
    without = calculate_annual_tax(entries, Settings(ssf_enrolled=False))
    assert with_ssf.annual_tax == 0
    assert without.annual_tax == pytest.approx(9_600)


def test_progressive_slabs():
    # IRD table: 15 lakh taxable -> 10,000 + 50,000
    assert calculate_annual_tax(flat(basic_salary=125_000), Settings(ssf_enrolled=False)).annual_tax == pytest.approx(60_000)
    # 60 lakh -> 10k + 50k + 200k + 405k + 29% of 20 lakh
    top = calculate_annual_tax(flat(basic_salary=500_000), Settings(ssf_enrolled=False))
    assert top.annual_tax == pytest.approx(10_000 + 50_000 + 200_000 + 405_000 + 580_000)


def test_retirement_cap_is_lower_of_third_or_five_lakh():
    r = calculate_annual_tax(flat(basic_salary=100_000, cit=50_000), Settings(ssf_enrolled=False))
    assert r.retirement_actual == 600_000
    assert r.retirement_cap == 400_000
    big = calculate_annual_tax(flat(basic_salary=300_000, cit=100_000), Settings(ssf_enrolled=False))
    assert big.retirement_cap == 500_000


def test_insurance_caps_and_female_rebate():
    s = Settings(ssf_enrolled=False, life_insurance=100_000, health_insurance=50_000, female_rebate=True)
    r = calculate_annual_tax(flat(basic_salary=125_000), s)
    assert (r.life_insurance_deduction, r.health_insurance_deduction) == (40_000, 20_000)
    assert r.taxable_income == pytest.approx(1_500_000 - 60_000)
    assert r.annual_tax == pytest.approx(r.tax_before_rebate * 0.9)


def test_handicapped_gets_extra_five_lakh_deduction():
    plain = calculate_annual_tax(flat(basic_salary=125_000), Settings(ssf_enrolled=False))
    handi = calculate_annual_tax(flat(basic_salary=125_000), Settings(ssf_enrolled=False, handicapped=True))
    assert handi.handicap_deduction == 500_000
    assert handi.taxable_income == pytest.approx(plain.taxable_income - 500_000)


def test_default_scenario_min_cit():
    entries = [MonthEntry(60_000, 40_000, 50_000) for _ in range(12)]
    entries[2] = MonthEntry(60_000, 40_000, 50_000, festival_allowance=60_000)
    cit = min_monthly_cit(entries, Settings())
    assert cit == 23_067
    with_cit = [replace(e, cit=cit) for e in entries]
    assert calculate_annual_tax(with_cit, Settings()).retirement_deduction == 500_000
    assert min_monthly_cit(with_cit, Settings()) == cit  # existing CIT is ignored
    assert min_monthly_cit(flat(basic_salary=200_000), Settings()) == 0  # SSF alone already fills the cap


def test_zero_income():
    result = calculate_salary(flat(), Settings())
    assert result.annual.annual_tax == 0
    assert result.total_net_pay == 0


def test_requires_twelve_entries():
    with pytest.raises(ValueError):
        calculate_salary([MonthEntry()], Settings())


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, "0.00"), (999.5, "999.50"), (1234567.891, "12,34,567.89"), (-100000, "-1,00,000.00"), (-0.001, "0.00")],
)
def test_format_npr(value, expected):
    assert format_npr(value) == expected
