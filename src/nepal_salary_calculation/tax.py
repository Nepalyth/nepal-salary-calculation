"""Nepal salary tax engine for FY 2083/84 (Shrawan 2083 - Ashadh 2084).

Pure functions only (no Streamlit) so the rules are easy to test and audit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

FISCAL_YEAR = "2083/84"

# Fiscal year order: Shrawan is month 1, Ashadh is month 12.
MONTHS = [
    "Shrawan", "Bhadra", "Ashwin", "Kartik", "Mangsir", "Poush",
    "Magh", "Falgun", "Chaitra", "Baisakh", "Jestha", "Ashadh",
]  # fmt: skip
MONTHS_NE = [
    "श्रावण", "भाद्र", "आश्विन", "कार्तिक", "मंसिर", "पौष",
    "माघ", "फाल्गुन", "चैत्र", "वैशाख", "जेष्ठ", "असार",
]  # fmt: skip
# Approximate Gregorian span of each Nepali month in FY 2083/84.
MONTH_SPANS = [
    "July - August, 2026", "August - September, 2026", "September - October, 2026",
    "October - November, 2026", "November - December, 2026", "December, 2026 - January, 2027",
    "January - February, 2027", "February - March, 2027", "March - April, 2027",
    "April - May, 2027", "May - June, 2027", "June - July, 2027",
]  # fmt: skip


def month_title(index: int) -> str:
    """e.g. 'Ashwin - 2083 (September - October, 2026)'."""
    bs_year = 2083 if index < 9 else 2084
    return f"{MONTHS[index]} - {bs_year} ({MONTH_SPANS[index]})"


# (lower bound, upper bound or None, rate). The first slab is the 1% Social Security Tax slab.
SLABS: list[tuple[float, float | None, float]] = [
    (0, 1_000_000, 0.01),
    (1_000_000, 1_500_000, 0.10),
    (1_500_000, 2_500_000, 0.20),
    (2_500_000, 4_000_000, 0.27),
    (4_000_000, None, 0.29),
]

SSF_EMPLOYEE_RATE = 0.11
SSF_EMPLOYER_RATE = 0.20
RETIREMENT_CAP_ABSOLUTE = 500_000
RETIREMENT_CAP_SHARE = 1 / 3
LIFE_INSURANCE_CAP = 40_000
HEALTH_INSURANCE_CAP = 20_000
FEMALE_REBATE_RATE = 0.10
# Source: IRD/RSA natural-person table - handicapped persons get 50% of the exemption limit
# (the first 10 lakh band) as an additional deduction.
HANDICAPPED_EXTRA_DEDUCTION = SLABS[0][1] * 0.5  # type: ignore[operator]

# Payroll style: employer's 20% appears as income on the payslip and the full 31% is deducted.
SSF_BASIS_FULL = "full"
# Only the employee's 11% is deducted; the employer's 20% never touches the payslip.
SSF_BASIS_EMPLOYEE = "employee"

# Remaining annual tax / remaining months, re-forecast every month (how Nepali payroll works).
TDS_PAYROLL = "payroll"
TDS_EVEN = "even"


@dataclass(frozen=True)
class MonthEntry:
    """Amounts for a single month. Everything is in NPR."""

    basic_salary: float = 0.0
    allowance: float = 0.0
    project_incentive: float = 0.0
    festival_allowance: float = 0.0
    leave_encashment: float = 0.0
    cit: float = 0.0
    retirement_fund: float = 0.0

    @property
    def cash_income(self) -> float:
        return (
            self.basic_salary
            + self.allowance
            + self.project_incentive
            + self.festival_allowance
            + self.leave_encashment
        )


@dataclass(frozen=True)
class Settings:
    ssf_enrolled: bool = True
    ssf_basis: str = SSF_BASIS_FULL
    female_rebate: bool = False
    handicapped: bool = False  # extra deduction of 50% of the exemption limit
    couple: bool = False  # informational: FY 2083/84 has one common slab table
    name: str = ""
    gender: str = "Male"
    life_insurance: float = 0.0  # annual premium
    health_insurance: float = 0.0  # annual premium
    tds_method: str = TDS_PAYROLL
    # Used by payroll forecasts for months that have not happened yet.
    standard_cit: float = 0.0
    standard_retirement_fund: float = 0.0


@dataclass(frozen=True)
class SlabRow:
    lower: float
    upper: float | None
    rate: float
    taxable_in_slab: float
    tax: float
    waived: bool = False


@dataclass(frozen=True)
class AnnualTax:
    cash_income: float
    ssf_income: float  # employer SSF counted as income (payroll style)
    gross_income: float
    retirement_actual: float
    retirement_cap: float
    retirement_deduction: float
    life_insurance_deduction: float
    health_insurance_deduction: float
    handicap_deduction: float
    total_deduction: float
    taxable_income: float
    slabs: list[SlabRow]
    tax_before_rebate: float
    female_rebate: float
    annual_tax: float

    @property
    def effective_rate(self) -> float:
        return self.annual_tax / self.gross_income if self.gross_income else 0.0


@dataclass(frozen=True)
class MonthlySlip:
    index: int
    entry: MonthEntry
    ssf_income: float  # employer SSF shown as an earning
    ssf_deduction: float  # amount shown under deductions
    ssf_employee: float
    ssf_employer: float
    tds: float
    forecast: AnnualTax  # annual forecast used for this month's TDS
    tds_paid_before: float
    months_remaining: int

    @property
    def month(self) -> str:
        return MONTHS[self.index]

    @property
    def gross_income(self) -> float:
        return self.entry.cash_income + self.ssf_income

    @property
    def total_deductions(self) -> float:
        return self.ssf_deduction + self.entry.cit + self.entry.retirement_fund + self.tds

    @property
    def net_pay(self) -> float:
        return self.gross_income - self.total_deductions


@dataclass(frozen=True)
class SalaryResult:
    entries: list[MonthEntry]
    settings: Settings
    annual: AnnualTax
    slips: list[MonthlySlip] = field(default_factory=list)

    @property
    def total_tds(self) -> float:
        return sum(s.tds for s in self.slips)

    @property
    def total_net_pay(self) -> float:
        return sum(s.net_pay for s in self.slips)

    @property
    def tax_settlement(self) -> float:
        """Annual tax minus TDS deducted. Positive = still payable, negative = over-deducted."""
        return self.annual.annual_tax - self.total_tds


def ssf_amounts(basic_salary: float, settings: Settings) -> tuple[float, float]:
    """(employee, employer) SSF for one month, calculated on basic salary only."""
    if not settings.ssf_enrolled:
        return 0.0, 0.0
    return basic_salary * SSF_EMPLOYEE_RATE, basic_salary * SSF_EMPLOYER_RATE


def _ssf_income(entry: MonthEntry, settings: Settings) -> float:
    if settings.ssf_basis != SSF_BASIS_FULL:
        return 0.0
    return ssf_amounts(entry.basic_salary, settings)[1]


def _ssf_deduction(entry: MonthEntry, settings: Settings) -> float:
    employee, employer = ssf_amounts(entry.basic_salary, settings)
    return employee + (employer if settings.ssf_basis == SSF_BASIS_FULL else 0.0)


def monthly_ssf(entry: MonthEntry, settings: Settings) -> tuple[float, float]:
    """(SSF shown as income, SSF shown as deduction) for one month's payslip."""
    return _ssf_income(entry, settings), _ssf_deduction(entry, settings)


def calculate_annual_tax(entries: list[MonthEntry], settings: Settings) -> AnnualTax:
    cash = sum(e.cash_income for e in entries)
    ssf_income = sum(_ssf_income(e, settings) for e in entries)
    gross = cash + ssf_income

    retirement_actual = sum(
        _ssf_deduction(e, settings) + e.cit + e.retirement_fund for e in entries
    )
    retirement_cap = min(RETIREMENT_CAP_ABSOLUTE, gross * RETIREMENT_CAP_SHARE)
    retirement_deduction = min(retirement_actual, retirement_cap)

    life = min(max(settings.life_insurance, 0.0), LIFE_INSURANCE_CAP)
    health = min(max(settings.health_insurance, 0.0), HEALTH_INSURANCE_CAP)
    handicap = HANDICAPPED_EXTRA_DEDUCTION if settings.handicapped else 0.0
    total_deduction = retirement_deduction + life + health + handicap
    taxable = max(0.0, gross - total_deduction)

    rows: list[SlabRow] = []
    tax = 0.0
    for lower, upper, rate in SLABS:
        in_slab = max(0.0, min(taxable, upper if upper is not None else taxable) - lower)
        waived = settings.ssf_enrolled and lower == 0
        slab_tax = 0.0 if waived else in_slab * rate
        tax += slab_tax
        rows.append(SlabRow(lower, upper, rate, in_slab, slab_tax, waived))

    rebate = tax * FEMALE_REBATE_RATE if settings.female_rebate else 0.0
    return AnnualTax(
        cash_income=cash,
        ssf_income=ssf_income,
        gross_income=gross,
        retirement_actual=retirement_actual,
        retirement_cap=retirement_cap,
        retirement_deduction=retirement_deduction,
        life_insurance_deduction=life,
        health_insurance_deduction=health,
        handicap_deduction=handicap,
        total_deduction=total_deduction,
        taxable_income=taxable,
        slabs=rows,
        tax_before_rebate=tax,
        female_rebate=rebate,
        annual_tax=tax - rebate,
    )


def min_monthly_cit(entries: list[MonthEntry], settings: Settings) -> float:
    """Smallest whole-rupee monthly CIT that lifts the retirement deduction to its legal cap.

    CIT beyond this amount gives no extra tax saving. Any CIT already in `entries` is ignored.
    """
    base = calculate_annual_tax([replace(e, cit=0.0) for e in entries], settings)
    shortfall = max(0.0, base.retirement_cap - base.retirement_actual)
    return float(math.ceil(shortfall / 12 - 1e-9))


def forecast_entries(entries: list[MonthEntry], index: int, settings: Settings) -> list[MonthEntry]:
    """What payroll believes the year looks like in month `index`.

    Past and current months are actuals. Future months repeat the current basic salary,
    allowance and project incentive, use the standard CIT / retirement fund, and contain no
    festival allowance or leave encashment (those are unknown until they are paid).
    """
    current = entries[index]
    future = replace(
        current,
        festival_allowance=0.0,
        leave_encashment=0.0,
        cit=settings.standard_cit,
        retirement_fund=settings.standard_retirement_fund,
    )
    return [*entries[: index + 1], *[future] * (11 - index)]


def _round_rupee(value: float) -> float:
    return float(math.floor(value + 0.5))


def calculate_salary(entries: list[MonthEntry], settings: Settings) -> SalaryResult:
    if len(entries) != 12:
        raise ValueError("Exactly 12 monthly entries are required")

    annual = calculate_annual_tax(entries, settings)
    slips: list[MonthlySlip] = []
    paid = 0.0
    for i, entry in enumerate(entries):
        if settings.tds_method == TDS_EVEN:
            forecast = annual
            tds = annual.annual_tax / 12
        else:
            forecast = calculate_annual_tax(forecast_entries(entries, i, settings), settings)
            tds = _round_rupee(max(0.0, forecast.annual_tax - paid) / (12 - i))
        employee, employer = ssf_amounts(entry.basic_salary, settings)
        slips.append(
            MonthlySlip(
                index=i,
                entry=entry,
                ssf_income=_ssf_income(entry, settings),
                ssf_deduction=_ssf_deduction(entry, settings),
                ssf_employee=employee,
                ssf_employer=employer,
                tds=tds,
                forecast=forecast,
                tds_paid_before=paid,
                months_remaining=12 - i,
            )
        )
        paid += tds
    return SalaryResult(entries, settings, annual, slips)


def format_npr(value: float, decimals: int = 2) -> str:
    """Format with Nepali/Indian lakh-crore digit grouping, e.g. 12,34,567.00."""
    sign = "-" if value < 0 and round(abs(value), decimals) != 0 else ""
    whole, _, frac = f"{abs(value):.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join([*groups, tail])
    return f"{sign}{whole}.{frac}" if decimals else f"{sign}{whole}"
