"""Dashboard section: interactive charts, what-if scenarios and plain-language insights."""

from __future__ import annotations

from collections.abc import Callable

import altair as alt
import pandas as pd
import streamlit as st

from nepal_salary_calculation import insights as ins
from nepal_salary_calculation import tax as t
from nepal_salary_calculation.tax import format_npr as npr

BLUE, RED, GOLD, TEAL, PURPLE, INK = "#003893", "#C8102E", "#E8A317", "#0F8B8D", "#7B4FA3", "#2A1A14"
SPLIT_COLORS = {
    "Net take-home": BLUE,
    "Income tax": RED,
    "SSF": GOLD,
    "CIT": TEAL,
    "Retirement fund": PURPLE,
}
INCOME_COLORS = {
    "Basic salary": BLUE,
    "Allowance": "#4C7BD9",
    "Project incentive": TEAL,
    "Festival allowance": GOLD,
    "Leave/Extra Encashment": PURPLE,
    ins.EMPLOYER_SSF: "#B9A27A",
}
# Axis labels in lakh/crore, the way amounts are usually written in Nepal.
AXIS_NPR = (
    "datum.value >= 10000000 ? format(datum.value / 10000000, '.2~f') + ' Cr' : "
    "datum.value >= 100000 ? format(datum.value / 100000, '.2~f') + ' L' : "
    "datum.value >= 1000 ? format(datum.value / 1000, '.0~f') + 'k' : datum.value"
)

CardTitle = Callable[[str, str, str], None]


def finish(chart: alt.TopLevelMixin) -> alt.TopLevelMixin:
    """Transparent background so the charts sit on the glass theme."""
    return (
        chart.configure_view(stroke=None, fill="transparent")
        .configure(background="transparent", font="Mukta")
        .configure_axis(grid=True, gridColor="rgba(42,26,20,.10)", domain=False, labelColor="#6b5148", titleColor="#6b5148")
        .configure_legend(labelFontSize=12, symbolType="square")
    )


def money(series: pd.Series) -> pd.Series:
    return series.map(lambda v: npr(v, 0))


def show(chart: alt.TopLevelMixin, width: str = "stretch") -> None:
    st.altair_chart(finish(chart), width=width)


def donut(b: ins.Breakdown) -> alt.LayerChart:
    df = ins.split_frame(b).assign(Label=lambda d: money(d["Amount"]))
    parts = [p for p in SPLIT_COLORS if p in set(df["Part"])]
    pick = alt.selection_point(fields=["Part"], bind="legend")
    # Radii follow the plot area, which Streamlit shrinks to make room for the legend.
    outer = alt.expr("min(width, height) / 2 - 4")
    arcs = (
        alt.Chart(df)
        .mark_arc(innerRadius=alt.expr("min(width, height) / 2 * 0.56"), outerRadius=outer, stroke="white", strokeWidth=2)
        .encode(
            theta=alt.Theta("Amount:Q", stack=True),
            color=alt.Color(
                "Part:N",
                scale=alt.Scale(domain=parts, range=[SPLIT_COLORS[p] for p in parts]),
                legend=alt.Legend(orient="bottom", title=None, columns=3),
            ),
            order=alt.Order("Amount:Q", sort="descending"),
            opacity=alt.condition(pick, alt.value(1), alt.value(0.3)),
            tooltip=[
                alt.Tooltip("Part:N"),
                alt.Tooltip("Label:N", title="NPR"),
                alt.Tooltip("Share:Q", format=".1%", title="Share of gross"),
            ],
        )
        .add_params(pick)
    )
    rate = (
        alt.Chart(pd.DataFrame({"t": [f"{b.take_home_rate:.1%}"]}))
        .mark_text(fontSize=34, fontWeight=700, color=INK, dy=-8, x=alt.expr("width / 2"), y=alt.expr("height / 2"))
        .encode(text="t:N")
    )
    caption = (
        alt.Chart(pd.DataFrame({"t": ["kept as take-home"]}))
        .mark_text(fontSize=12, color="#6b5148", dy=16, x=alt.expr("width / 2"), y=alt.expr("height / 2"))
        .encode(text="t:N")
    )
    shares = (
        alt.Chart(df.assign(Pct=df["Share"].map(lambda v: f"{v:.1%}")))
        .mark_text(radius=alt.expr("min(width, height) / 2 * 0.78"), fontSize=11, fontWeight=700, color="white")
        .transform_filter(alt.datum.Share >= 0.05)
        .encode(
            theta=alt.Theta("Amount:Q", stack=True),
            order=alt.Order("Amount:Q", sort="descending"),
            text="Pct:N",
            tooltip=alt.value(None),
        )
    )
    return alt.layer(arcs, shares, rate, caption).properties(height=320)


def waterfall(b: ins.Breakdown) -> alt.LayerChart:
    df = ins.waterfall_frame(b).assign(Label=lambda d: money(d["Amount"]))
    x = alt.X("Step:N", sort=df["Step"].tolist(), axis=alt.Axis(labelAngle=0, title=None, labelLimit=90))
    bars = (
        alt.Chart(df)
        .mark_bar(cornerRadius=3, size=46)
        .encode(
            x=x,
            y=alt.Y("Start:Q", title=None, axis=alt.Axis(labelExpr=AXIS_NPR, tickCount=5), scale=alt.Scale(domain=[0, b.gross * 1.18], nice=False)),
            y2="End:Q",
            color=alt.Color(
                "Kind:N",
                scale=alt.Scale(domain=["Total", "Deduction", "Take-home"], range=[GOLD, RED, BLUE]),
                legend=None,
            ),
            tooltip=[alt.Tooltip("Step:N"), alt.Tooltip("Label:N", title="NPR")],
        )
    )
    labels = (
        alt.Chart(df)
        .mark_text(dy=-20, fontSize=12, fontWeight=700, color=INK, baseline="bottom")
        .transform_calculate(top="max(datum.Start, datum.End)")
        .encode(x=x, y=alt.Y("top:Q"), text="Label:N", tooltip=alt.value(None))
    )
    notes = (
        alt.Chart(df.assign(Note=df.apply(waterfall_note, axis=1)))
        .mark_text(dy=-6, fontSize=11, color="#6b5148", baseline="bottom")
        .transform_calculate(top="max(datum.Start, datum.End)")
        .encode(x=x, y=alt.Y("top:Q"), text="Note:N", tooltip=alt.value(None))
    )
    return alt.layer(bars, labels, notes).properties(height=330)


def waterfall_note(row: pd.Series) -> str:
    if row["Kind"] == "Total":
        return "100% of gross"
    if row["Kind"] == "Take-home":
        return f"{row['Share']:.1%} kept"
    return f"−{row['Share']:.1%} of gross"


def monthly_composition(result: t.SalaryResult, selected: int | None = None) -> alt.LayerChart:
    income = ins.monthly_income_frame(result).assign(Label=lambda d: money(d["Amount"]))
    net = ins.monthly_net_frame(result).assign(Label=lambda d: money(d["Net paid"]))
    components = [c for c in INCOME_COLORS if c in set(income["Component"])]
    pick = alt.selection_point(fields=["Component"], bind="legend")
    x = alt.X("Month:N", sort=t.MONTHS, axis=alt.Axis(labelAngle=-35, title=None))
    bars = (
        alt.Chart(income)
        .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
        .encode(
            x=x,
            y=alt.Y(
                "Amount:Q",
                stack="zero",
                title=None,
                axis=alt.Axis(labelExpr=AXIS_NPR, tickCount=5),
                scale=alt.Scale(domain=[0, float(net["Gross"].max()) * 1.3], nice=False),
            ),
            color=alt.Color(
                "Component:N",
                sort=components,
                scale=alt.Scale(domain=components, range=[INCOME_COLORS[c] for c in components]),
                legend=alt.Legend(orient="top", title=None, columns=3),
            ),
            opacity=alt.condition(pick, alt.value(0.95), alt.value(0.25)),
            tooltip=[alt.Tooltip("Month:N"), alt.Tooltip("Component:N"), alt.Tooltip("Label:N", title="NPR")],
        )
        .add_params(pick)
    )
    line = (
        alt.Chart(net)
        .mark_line(color=INK, strokeWidth=2.5, point=alt.OverlayMarkDef(color=INK, filled=True, size=55))
        .encode(
            x=x,
            y="Net paid:Q",
            tooltip=[alt.Tooltip("Month:N"), alt.Tooltip("Label:N", title="Net paid (NPR)")],
        )
    )
    net = net.assign(Short=net["Net paid"].map(lambda v: f"net {ins.lakh(v)}"))
    net_labels = (
        alt.Chart(net)
        .mark_text(dy=-6, fontSize=10, color="#6b5148", baseline="bottom")
        .encode(x=x, y="Gross:Q", text="Short:N", tooltip=alt.value(None))
    )
    layers = [bars, line, net_labels]
    if selected is not None:
        band = alt.Chart(pd.DataFrame({"Month": [t.MONTHS[selected]]})).mark_rect(color=GOLD, opacity=0.18).encode(x=x)
        layers.insert(0, band)
    peak = ins.peak_month(result)
    if peak:
        month, why = peak
        top = float(net.loc[net["Month"] == month, "Gross"].iloc[0])
        idx = t.MONTHS.index(month)
        note = pd.DataFrame({"Month": [month], "Gross": [top], "Note": ["★ Peak month" + (f": {why}" if why else "")]})
        layers.append(
            alt.Chart(note)
            .mark_text(
                dy=-22,
                fontSize=11,
                fontWeight=700,
                color=RED,
                baseline="bottom",
                align="left" if idx <= 1 else "right" if idx >= 10 else "center",
            )
            .encode(x=x, y="Gross:Q", text="Note:N", tooltip=alt.value(None))
        )
    return alt.layer(*layers).properties(height=360)


def slab_chart(annual: t.AnnualTax) -> alt.LayerChart:
    df = ins.slab_frame(annual)
    last = int(df.index[df["Filled"] > 0].max())
    notes_text = []
    for i, (filled_amount, tax_amount, rate_text) in enumerate(zip(df["Filled"], df["Tax"], df["Rate"], strict=True)):
        if filled_amount <= 0:
            notes_text.append("")
            continue
        text = f"NPR {npr(filled_amount, 0)} → tax {npr(tax_amount, 0)}"
        if rate_text.startswith("waived"):
            text = f"NPR {npr(filled_amount, 0)} → no tax (SST waived for SSF)"
        if i == last:
            text += "   ◀ you end here"
        notes_text.append(text)
    df["Note"] = notes_text
    df["FilledLabel"] = money(df["Filled"])
    y = alt.Y("Slab:N", sort=df["Slab"].tolist(), title=None, axis=alt.Axis(labelLimit=220))
    room = (
        alt.Chart(df)
        .mark_bar(color="rgba(200,176,130,.35)", cornerRadius=4, size=26)
        .encode(x=alt.X("Capacity:Q", title=None, axis=alt.Axis(labelExpr=AXIS_NPR, tickCount=6)), y=y, tooltip=alt.value(None))
    )
    filled = (
        alt.Chart(df)
        .mark_bar(cornerRadius=4, size=26)
        .encode(
            x="Filled:Q",
            y=y,
            color=alt.condition(alt.datum.Rate == "waived (SSF)", alt.value("#8FA8D8"), alt.value(RED)),
            tooltip=[
                alt.Tooltip("Slab:N"),
                alt.Tooltip("FilledLabel:N", title="Income in slab"),
                alt.Tooltip("Tax:Q", format=",.0f", title="Tax (NPR)"),
            ],
        )
    )
    notes = (
        alt.Chart(df)
        .mark_text(align="left", dx=6, fontSize=11, color=INK)
        .encode(x="Filled:Q", y=y, text="Note:N", tooltip=alt.value(None))
    )
    return alt.layer(room, filled, notes).properties(height=230)


def label(x: float, y: float, text: str, *, dx: int = 0, dy: int = 0, align: str = "left", color: str = INK, baseline: str = "middle") -> alt.Chart:
    """A text annotation placed at a data coordinate."""
    return (
        alt.Chart(pd.DataFrame({"x": [x], "y": [y], "t": [text]}))
        .mark_text(align=align, dx=dx, dy=dy, color=color, fontSize=11, fontWeight=600, baseline=baseline)
        .encode(x="x:Q", y="y:Q", text="t:N", tooltip=alt.value(None))
    )


def cit_chart(curve: pd.DataFrame, current: ins.CitScenario, chosen: ins.CitScenario, best: float) -> alt.LayerChart:
    upper = float(curve["Monthly CIT"].max())
    no_cit = float(curve["Income tax"].iloc[0])
    x = alt.X("Monthly CIT:Q", title="Monthly CIT (NPR)", axis=alt.Axis(labelExpr=AXIS_NPR))
    y = alt.Y("Income tax:Q", title="Annual income tax", axis=alt.Axis(labelExpr=AXIS_NPR), scale=alt.Scale(zero=True, domain=[0, no_cit * 1.12]))
    line = alt.Chart(curve).mark_line(color=RED, strokeWidth=3, interpolate="monotone").encode(x=x, y=y)
    area = alt.Chart(curve).mark_area(color=RED, opacity=0.08, interpolate="monotone").encode(x=x, y=y)
    points = pd.DataFrame(
        [
            {"Monthly CIT": current.monthly_cit, "Income tax": current.tax, "Point": "Your current CIT"},
            {"Monthly CIT": chosen.monthly_cit, "Income tax": chosen.tax, "Point": "What-if"},
        ]
    )
    dots = (
        alt.Chart(points)
        .mark_point(filled=True, size=130, stroke="white", strokeWidth=2)
        .encode(
            x=x,
            y=y,
            color=alt.Color(
                "Point:N",
                scale=alt.Scale(domain=["Your current CIT", "What-if"], range=[INK, GOLD]),
                legend=alt.Legend(orient="top", title=None),
            ),
            tooltip=[
                alt.Tooltip("Point:N"),
                alt.Tooltip("Monthly CIT:Q", format=",.0f"),
                alt.Tooltip("Income tax:Q", format=",.0f"),
            ],
        )
    )
    layers = [area, line, dots]
    layers.append(label(0, no_cit, f"No CIT: tax {npr(no_cit, 0)}", dx=8, dy=-12, color="#6b5148"))
    right = current.monthly_cit > upper * 0.55
    layers.append(
        label(
            current.monthly_cit,
            current.tax,
            f"You: CIT {npr(current.monthly_cit, 0)} → tax {npr(current.tax, 0)}",
            dx=-10 if right else 10,
            dy=26,
            align="right" if right else "left",
        )
    )
    if abs(chosen.monthly_cit - current.monthly_cit) >= 1:
        right = chosen.monthly_cit > upper * 0.55
        layers.append(
            label(
                chosen.monthly_cit,
                chosen.tax,
                f"What-if: CIT {npr(chosen.monthly_cit, 0)} → tax {npr(chosen.tax, 0)}",
                dx=-10 if right else 10,
                dy=-24,
                align="right" if right else "left",
                color="#9A6B00",
            )
        )
    if best > 0:
        saves = no_cit - ins.tax_at_cit(curve, best)
        rule = alt.Chart(pd.DataFrame({"x": [best]}))
        layers.append(rule.mark_rule(color=TEAL, strokeDash=[5, 4], strokeWidth=2).encode(x="x:Q"))
        far = best > upper * 0.35
        layers.append(
            label(
                best,
                no_cit * 0.08,
                f"Max tax saving at {npr(best, 0)}: saves NPR {npr(saves, 0)}",
                dx=-6 if far else 6,
                align="right" if far else "left",
                color=TEAL,
            )
        )
    return alt.layer(*layers).properties(height=320)


def bonus_chart(
    curve: pd.DataFrame, chosen: float, outcome: ins.BonusScenario, crossings: list[tuple[float, float]]
) -> alt.LayerChart:
    """Share of an extra payment that goes to tax, by size of the payment (steps up at each slab)."""
    curve = curve[curve["Bonus"] > 0]
    top = max(0.4, curve["Rate"].max() * 1.35)
    upper = float(curve["Bonus"].max())
    x = alt.X("Bonus:Q", title="Extra income received (NPR)", axis=alt.Axis(labelExpr=AXIS_NPR))
    y = alt.Y("Rate:Q", title="Share lost to tax", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, top]))
    tips = [
        alt.Tooltip("Bonus:Q", format=",.0f", title="Extra income"),
        alt.Tooltip("Tax:Q", format=",.0f", title="Extra tax"),
        alt.Tooltip("Rate:Q", format=".1%", title="Tax share"),
    ]
    area = alt.Chart(curve).mark_area(color=RED, opacity=0.12, interpolate="step-after").encode(x=x, y=y)
    line = alt.Chart(curve).mark_line(color=RED, strokeWidth=3, interpolate="step-after").encode(x=x, y=y, tooltip=tips)
    rule = alt.Chart(pd.DataFrame({"x": [chosen]})).mark_rule(color=INK, strokeDash=[4, 3], strokeWidth=2).encode(x="x:Q")
    dot = (
        alt.Chart(pd.DataFrame({"x": [chosen], "y": [outcome.rate]}))
        .mark_point(filled=True, size=140, color=GOLD, stroke="white", strokeWidth=2)
        .encode(x="x:Q", y="y:Q")
    )
    layers = [area, line, rule, dot]
    right = chosen > upper * 0.5
    layers.append(
        label(
            chosen,
            outcome.rate,
            f"You keep {npr(outcome.keep, 0)} · tax {npr(outcome.extra_tax, 0)} ({outcome.rate:.1%})",
            dx=-10 if right else 10,
            dy=-26,
            align="right" if right else "left",
        )
    )
    for gap, rate in crossings:
        layers.append(alt.Chart(pd.DataFrame({"x": [gap]})).mark_rule(color=TEAL, strokeDash=[3, 3]).encode(x="x:Q"))
        layers.append(
            label(gap, top, f"{rate:.0%} slab starts at +{npr(gap, 0)}", dx=-5, dy=6, align="right", color=TEAL, baseline="top")
        )
    return alt.layer(*layers).properties(height=320)


def cit_upper(result: t.SalaryResult, best: float) -> int:
    """Upper end of the CIT slider and curve, rounded up to a multiple of 5,000."""
    raw = max(best * 1.8, result.entries[0].cit * 1.6, 20_000)
    return int(-(-raw // 5_000) * 5_000)


def signed(value: float) -> str | None:
    return f"{value:+,.0f}" if abs(value) >= 1 else None


def render(result: t.SalaryResult, card_title: CardTitle) -> None:
    annual, settings = result.annual, result.settings
    if annual.gross_income <= 0:
        st.info("Fill in your salary above (or load the sample payslip) to see your dashboard.")
        return

    choice = st.pills("View", ["Full year", *t.MONTHS], default="Full year", key="dash_view")
    month = t.MONTHS.index(choice) if choice in t.MONTHS else None

    if month is None:
        b = ins.breakdown(result)
        saved = max(0.0, ins.tax_for_taxable(annual.gross_income, settings) - annual.annual_tax)
        rate, headroom = ins.marginal_rate(annual, settings)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Take-home rate", f"{b.take_home_rate:.1%}", help="Net take-home as a share of gross income.")
        k2.metric("Effective tax rate", f"{b.tax / b.gross:.2%}", help="Income tax (TDS) as a share of gross income.")
        k3.metric(
            "Tax saved by deductions",
            npr(saved, 0),
            help="Tax you would pay with no retirement, insurance or other deductions, minus what you pay.",
        )
        k4.metric(
            "Next-rupee tax rate",
            f"{rate:.1%}",
            f"NPR {npr(headroom, 0)} to next slab" if headroom is not None else "top slab",
            delta_color="off",
            help="The tax on one more rupee of taxable income, after the 10% female rebate if it applies.",
        )
        notes, scope, where = ins.insights(result), "your year", ""
    else:
        slip = result.slips[month]
        b = ins.month_breakdown(slip)
        average = result.total_net_pay / 12
        k1, k2, k3, k4 = st.columns(4)
        gap = signed(b.net - average)
        k1.metric(f"Net pay · {slip.month}", npr(b.net, 0), f"{gap} vs average month" if gap else None)
        k2.metric("Take-home rate", f"{b.take_home_rate:.1%}", help="This month's net pay as a share of its gross income.")
        k3.metric("TDS this month", npr(slip.tds, 0), help="Income tax deducted on this month's pay slip.")
        k4.metric("Gross income", npr(b.gross, 0), help="Includes the employer's SSF share when your payslip shows it as income.")
        notes, scope, where = ins.month_insights(result, month), slip.month, f" · {slip.month}"

    with st.container(border=True):
        card_title("💡", "Insights", f"Plain-language observations about {scope}")
        for line in notes:
            st.markdown(f"- {line}")

    left, right = st.columns([2, 3])
    with left, st.container(border=True):
        card_title("🍩", f"Where gross goes{where}", "Click a legend item to focus on it")
        show(donut(b))
    with right, st.container(border=True):
        card_title("🪜", f"From gross to take-home{where}", "Every deduction, step by step")
        show(waterfall(b))

    with st.container(border=True):
        card_title(
            "📆",
            "Income by month",
            "Components stacked, net pay as the line"
            + (f"; {t.MONTHS[month]} is highlighted" if month is not None else "")
            + ". Click a legend item to focus",
        )
        show(monthly_composition(result, month))

    with st.container(border=True):
        card_title(
            "🏔️",
            "How your taxable income fills the slabs",
            f"Taxable income NPR {npr(annual.taxable_income, 0)} after deductions",
        )
        show(slab_chart(annual))

    st.markdown("#### What if…")
    w_left, w_right = st.columns(2)
    best = t.min_monthly_cit(result.entries, settings)
    current_cit = result.entries[0].cit
    with w_left, st.container(border=True):
        card_title("🏦", "I change my monthly CIT", "See the tax you save and where the saving stops")
        upper = cit_upper(result, best)
        chosen_cit = st.slider("Monthly CIT (NPR)", 0, upper, int(min(current_cit, upper)), step=500)
        scenario = ins.cit_scenario(result, float(chosen_cit))
        m1, m2, m3 = st.columns(3)
        m1.metric("Tax / year", npr(scenario.tax, 0), signed(scenario.tax_change), delta_color="inverse")
        m2.metric(
            "Cash / year",
            npr(result.total_net_pay + scenario.cash_change, 0),
            signed(scenario.cash_change),
        )
        m3.metric(
            "Saved in CIT",
            npr(max(scenario.saved_change, 0.0), 0),
            help="Extra CIT over the year compared with your current amount. It is still yours, held in a fund.",
        )
        if best <= 0:
            st.caption("Your SSF already fills the retirement deduction cap, so extra CIT would not save tax.")
        show(cit_chart(ins.cit_curve(result, upper), ins.cit_scenario(result, current_cit), scenario, best))

    with w_right, st.container(border=True):
        card_title("🎁", "I receive extra income", "A bonus or one-off, and how much of it you keep")
        bonus = st.slider("Extra income this year (NPR)", 0, 1_500_000, 100_000, step=10_000)
        outcome = ins.bonus_scenario(result, float(bonus))
        n1, n2, n3 = st.columns(3)
        n1.metric("You keep", npr(outcome.keep, 0))
        n2.metric("Extra tax", npr(outcome.extra_tax, 0))
        n3.metric(
            "Tax share",
            f"{outcome.rate:.1%}",
            help="Can be above your slab rate if the bonus crosses into the next slab.",
        )
        show(bonus_chart(ins.bonus_curve(result, 1_500_000), float(bonus), outcome, ins.slab_crossings(annual, 1_500_000)))
