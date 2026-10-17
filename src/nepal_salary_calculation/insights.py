"""Numbers behind the dashboard: breakdowns, what-if scenarios and plain-language insights.

Pure functions only (no Streamlit), built on top of the tax engine in `tax.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from nepal_salary_calculation import tax as t
from nepal_salary_calculation.tax import format_npr as npr

INCOME_PARTS = [
    ("Basic salary", "basic_salary"),
    ("Allowance", "allowance"),
    ("Project incentive", "project_incentive"),
    ("Festival allowance", "festival_allowance"),
    ("Leave/Extra Encashment", "leave_encashment"),
]
EMPLOYER_SSF = "SSF (employer 20%)"


@dataclass(frozen=True)
class Breakdown:
    gross: float
    ssf: float
    cit: float
    retirement_fund: float
    tax: float

    @property
    def net(self) -> float:
        return self.gross - self.ssf - self.cit - self.retirement_fund - self.tax

    @property
    def take_home_rate(self) -> float:
        return self.net / self.gross if self.gross else 0.0


def tax_for_taxable(taxable: float, settings: t.Settings) -> float:
    """Annual tax on a taxable income, using the same slabs, SSF waiver and rebate as the engine."""
    total = 0.0
    for lower, upper, rate in t.SLABS:
        in_slab = max(0.0, min(taxable, upper if upper is not None else taxable) - lower)
        if not (settings.ssf_enrolled and lower == 0):
            total += in_slab * rate
    return total * (1 - t.FEMALE_REBATE_RATE) if settings.female_rebate else total


def breakdown_of(entries: list[t.MonthEntry], settings: t.Settings) -> Breakdown:
    annual = t.calculate_annual_tax(entries, settings)
    return Breakdown(
        gross=annual.gross_income,
        ssf=sum(t.monthly_ssf(e, settings)[1] for e in entries),
        cit=sum(e.cit for e in entries),
        retirement_fund=sum(e.retirement_fund for e in entries),
        tax=annual.annual_tax,
    )


def breakdown(result: t.SalaryResult) -> Breakdown:
    """Where the year's gross income goes, using the TDS actually deducted on the pay slips."""
    b = breakdown_of(result.entries, result.settings)
    return replace(b, tax=result.total_tds)


def month_breakdown(slip: t.MonthlySlip) -> Breakdown:
    """Where one month's gross income goes, straight from that month's pay slip."""
    return Breakdown(
        gross=slip.gross_income,
        ssf=slip.ssf_deduction,
        cit=slip.entry.cit,
        retirement_fund=slip.entry.retirement_fund,
        tax=slip.tds,
    )


def waterfall_frame(b: Breakdown) -> pd.DataFrame:
    """Gross income down to net take-home, one row per step with its start/end level."""
    steps = [("SSF", b.ssf), ("CIT", b.cit), ("Retirement fund", b.retirement_fund), ("Income tax", b.tax)]
    rows = [{"Step": "Gross income", "Start": 0.0, "End": b.gross, "Kind": "Total", "Amount": b.gross}]
    share = (lambda v: v / b.gross) if b.gross else (lambda v: 0.0)
    level = b.gross
    for name, amount in steps:
        if amount:
            rows.append(
                {"Step": name, "Start": level, "End": level - amount, "Kind": "Deduction", "Amount": amount, "Share": share(amount)}
            )
            level -= amount
    rows.append({"Step": "Net take-home", "Start": 0.0, "End": b.net, "Kind": "Take-home", "Amount": b.net, "Share": share(b.net)})
    rows[0]["Share"] = 1.0 if b.gross else 0.0
    return pd.DataFrame(rows)


def split_frame(b: Breakdown) -> pd.DataFrame:
    """Share of gross income per destination, for the donut."""
    parts = [
        ("Net take-home", b.net),
        ("Income tax", b.tax),
        ("SSF", b.ssf),
        ("CIT", b.cit),
        ("Retirement fund", b.retirement_fund),
    ]
    df = pd.DataFrame([(n, v) for n, v in parts if v > 0], columns=["Part", "Amount"])
    df["Share"] = df["Amount"] / b.gross if b.gross else 0.0
    return df


def monthly_income_frame(result: t.SalaryResult) -> pd.DataFrame:
    rows = []
    for slip in result.slips:
        for label, field in INCOME_PARTS:
            value = getattr(slip.entry, field)
            if value:
                rows.append({"Month": slip.month, "Component": label, "Amount": value})
        if slip.ssf_income:
            rows.append({"Month": slip.month, "Component": EMPLOYER_SSF, "Amount": slip.ssf_income})
    return pd.DataFrame(rows, columns=["Month", "Component", "Amount"])


def monthly_net_frame(result: t.SalaryResult) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Month": [s.month for s in result.slips],
            "Gross": [s.gross_income for s in result.slips],
            "Net paid": [s.net_pay for s in result.slips],
            "TDS": [s.tds for s in result.slips],
        }
    )


def lakh(value: float) -> str:
    """Compact NPR for labels: 10,00,000 -> '10 L', 25,00,000 -> '25 L', 1,50,000 -> '1.5 L'."""
    def trim(number: float) -> str:
        return f"{number:.2f}".rstrip("0").rstrip(".")

    if value >= 10_000_000:
        return f"{trim(value / 10_000_000)} Cr"
    return f"{trim(value / 100_000)} L"


def slab_frame(annual: t.AnnualTax) -> pd.DataFrame:
    """Each slab with its capacity and how much of the taxable income lands in it."""
    top = max(annual.taxable_income * 1.15, t.SLABS[-1][0] + 1_000_000)
    rows = []
    for row in annual.slabs:
        upper = row.upper if row.upper is not None else top
        rate = "SST waived" if row.waived else f"{row.rate:.0%}"
        label = f"{lakh(row.lower)} – {lakh(row.upper) if row.upper else 'above'}  ·  {rate}"
        rows.append(
            {
                "Slab": label,
                "Capacity": upper - row.lower,
                "Filled": row.taxable_in_slab,
                "Tax": row.tax,
                "Rate": "waived (SSF)" if row.waived else f"{row.rate:.0%}",
            }
        )
    return pd.DataFrame(rows)


def marginal_rate(annual: t.AnnualTax, settings: t.Settings) -> tuple[float, float | None]:
    """(effective tax rate on the next rupee of taxable income, rupees left before the next slab)."""
    taxable = annual.taxable_income
    for row in annual.slabs:
        if row.upper is None or taxable < row.upper:
            rate = 0.0 if row.waived else row.rate
            if settings.female_rebate:
                rate *= 1 - t.FEMALE_REBATE_RATE
            return rate, (row.upper - taxable if row.upper is not None else None)
    return 0.0, None


def with_monthly_cit(entries: list[t.MonthEntry], cit: float) -> list[t.MonthEntry]:
    return [replace(e, cit=cit) for e in entries]


def cit_curve(result: t.SalaryResult, upper: float, steps: int = 40) -> pd.DataFrame:
    """Annual income tax at each monthly CIT level from 0 to `upper`."""
    rows = []
    for i in range(steps + 1):
        cit = upper * i / steps
        tax = t.calculate_annual_tax(with_monthly_cit(result.entries, cit), result.settings).annual_tax
        rows.append({"Monthly CIT": cit, "Income tax": tax})
    return pd.DataFrame(rows)


def tax_at_cit(curve: pd.DataFrame, monthly_cit: float) -> float:
    """Annual tax on a `cit_curve` at the point closest to `monthly_cit`."""
    row = curve.iloc[(curve["Monthly CIT"] - monthly_cit).abs().argmin()]
    return float(row["Income tax"])


@dataclass(frozen=True)
class CitScenario:
    monthly_cit: float
    tax: float
    tax_change: float  # negative = you pay less tax
    cash_change: float  # change in cash take-home (CIT is money you set aside, so cash falls)
    saved_change: float  # extra retirement savings (CIT) over the year


def cit_scenario(result: t.SalaryResult, monthly_cit: float) -> CitScenario:
    current_cit = result.entries[0].cit if result.entries else 0.0
    base = t.calculate_annual_tax(result.entries, result.settings).annual_tax
    entries = with_monthly_cit(result.entries, monthly_cit)
    new_tax = t.calculate_annual_tax(entries, result.settings).annual_tax
    saved = (monthly_cit - current_cit) * 12
    tax_change = new_tax - base
    return CitScenario(monthly_cit, new_tax, tax_change, -saved - tax_change, saved)


@dataclass(frozen=True)
class BonusScenario:
    bonus: float
    extra_tax: float

    @property
    def keep(self) -> float:
        return self.bonus - self.extra_tax

    @property
    def rate(self) -> float:
        return self.extra_tax / self.bonus if self.bonus else 0.0


def bonus_scenario(result: t.SalaryResult, bonus: float) -> BonusScenario:
    """Extra annual tax if `bonus` more taxable cash is received during the year."""
    base = t.calculate_annual_tax(result.entries, result.settings).annual_tax
    entries = list(result.entries)
    entries[-1] = replace(entries[-1], leave_encashment=entries[-1].leave_encashment + bonus)
    return BonusScenario(bonus, t.calculate_annual_tax(entries, result.settings).annual_tax - base)


def bonus_curve(result: t.SalaryResult, upper: float, steps: int = 50) -> pd.DataFrame:
    rows = []
    for i in range(steps + 1):
        s = bonus_scenario(result, upper * i / steps)
        rows.append({"Bonus": s.bonus, "You keep": s.keep, "Tax": s.extra_tax, "Rate": s.rate})
    return pd.DataFrame(rows)


def peak_month(result: t.SalaryResult) -> tuple[str, str] | None:
    """(month, what made it stand out) for the month with the highest gross income, if it stands out."""
    frame = monthly_income_frame(result)
    if frame.empty:
        return None
    totals = frame.groupby("Month")["Amount"].sum()
    top = totals.idxmax()
    if totals.max() - totals.median() < 1:
        return None
    wide = frame.pivot_table(index="Month", columns="Component", values="Amount", aggfunc="sum").fillna(0.0)
    extra = (wide.loc[top] - wide.median()).sort_values(ascending=False)
    names = [c.lower() for c, v in extra.items() if v >= 1][:2]
    return top, " + ".join(names)


def slab_crossings(annual: t.AnnualTax, limit: float) -> list[tuple[float, float]]:
    """(extra taxable income needed, slab rate) for each slab above the current one, up to `limit`."""
    out = []
    for lower, _upper, rate in t.SLABS:
        gap = lower - annual.taxable_income
        if 0 < gap <= limit:
            out.append((gap, rate))
    return out


def month_insights(result: t.SalaryResult, index: int) -> list[str]:
    """Short observations about one month's pay slip."""
    slip = result.slips[index]
    b = month_breakdown(slip)
    if b.gross <= 0:
        return []
    average = result.total_net_pay / 12
    out = [
        f"In **{slip.month}** you earn NPR {npr(b.gross, 0)} gross and take home **NPR {npr(b.net, 0)}** "
        f"({b.take_home_rate:.1%})."
    ]
    diff = b.net - average
    if abs(diff) >= 1:
        out.append(
            f"That is NPR {npr(abs(diff), 0)} {'above' if diff > 0 else 'below'} your average month "
            f"(NPR {npr(average, 0)})."
        )
    out.append(f"TDS this month is **NPR {npr(slip.tds, 0)}**, {slip.tds / b.gross:.1%} of gross.")
    parts = [("SSF", b.ssf), ("CIT", b.cit), ("retirement fund", b.retirement_fund)]
    parts = [(n, v) for n, v in parts if v > 0]
    if parts:
        out.append(
            "Set aside for retirement this month: "
            + ", ".join(f"{n} NPR {npr(v, 0)}" for n, v in parts)
            + f" (NPR {npr(sum(v for _, v in parts), 0)} in total)."
        )
    return out


def insights(result: t.SalaryResult) -> list[str]:
    """Short plain-language observations about the user's year."""
    a, s = result.annual, result.settings
    if a.gross_income <= 0:
        return []
    b = breakdown(result)
    out = [f"You keep **{b.take_home_rate:.1%}** of your gross income: NPR {npr(b.net, 0)} of NPR {npr(b.gross, 0)}."]

    saved = tax_for_taxable(a.gross_income, s) - a.annual_tax
    if saved >= 1:
        out.append(
            f"Retirement, insurance and other deductions cut your income tax by about **NPR {npr(saved, 0)}** "
            f"(tax of NPR {npr(a.annual_tax, 0)} instead of NPR {npr(a.annual_tax + saved, 0)})."
        )

    rate, headroom = marginal_rate(a, s)
    if a.taxable_income > 0:
        text = f"Your next rupee of taxable income is taxed at **{rate:.1%}**"
        if headroom is not None:
            text += f"; NPR {npr(headroom, 0)} more taxable income moves you into the next slab."
        else:
            text += " (you are in the top slab)."
        out.append(text)

    recommended = t.min_monthly_cit(result.entries, s)
    current_cit = result.entries[0].cit
    if recommended > current_cit and a.taxable_income > 0:
        gain = -cit_scenario(result, recommended).tax_change
        if gain >= 1:
            out.append(
                f"Raising CIT from NPR {npr(current_cit, 0)} to **NPR {npr(recommended, 0)}** a month would save "
                f"about NPR {npr(gain, 0)} more tax."
            )
    elif a.retirement_actual > a.retirement_cap + 1_000:
        out.append(
            f"Your retirement contributions (NPR {npr(a.retirement_actual, 0)}) are above the deduction cap "
            f"(NPR {npr(a.retirement_cap, 0)}), so the extra NPR {npr(a.retirement_actual - a.retirement_cap, 0)} "
            "gives no further tax saving."
        )

    nets = monthly_net_frame(result)
    best, worst = nets.loc[nets["Net paid"].idxmax()], nets.loc[nets["Net paid"].idxmin()]
    if best["Net paid"] - worst["Net paid"] >= 1:
        out.append(
            f"**{best['Month']}** is your highest-paid month (NPR {npr(best['Net paid'], 0)} net) and "
            f"**{worst['Month']}** the lowest (NPR {npr(worst['Net paid'], 0)})."
        )
    return out
