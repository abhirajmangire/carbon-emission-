from __future__ import annotations

from typing import List, Optional

from ..schemas import (
    AdviceBundle,
    AdviceItem,
    CurrentMonthReport,
    PredictionPoint,
    PredictionResult,
    TrendAnalysis,
    TrendPoint,
    UsagePoint,
    UsageSummary,
)
from ..storage import storage


def _emissions_kg(kwh: float, factor: float) -> float:
    return kwh * factor


def get_usage_points() -> List[UsagePoint]:
    points: List[UsagePoint] = []
    for b in storage.list_bills():
        points.append(
            UsagePoint(
                year=b.year,
                month=b.month,
                kilowatt_hours=b.kilowatt_hours,
                cost=b.cost,
                emissions_kg=_emissions_kg(b.kilowatt_hours, b.emission_factor_kg_per_kwh),
            )
        )
    return points


def get_recent_usage(limit: int = 6) -> List[UsagePoint]:
    pts = get_usage_points()
    pts.sort(key=lambda p: (p.year, p.month), reverse=True)
    return pts[: max(0, limit)]


def build_summary() -> UsageSummary:
    pts = get_usage_points()
    if not pts:
        return UsageSummary(
            total_kwh=0.0,
            total_cost=0.0,
            total_emissions_kg=0.0,
            average_kwh=0.0,
            average_cost=0.0,
            average_emissions_kg=0.0,
        )
    total_kwh = sum(p.kilowatt_hours for p in pts)
    total_cost = sum(p.cost for p in pts)
    total_emissions = sum(p.emissions_kg for p in pts)
    n = len(pts)
    return UsageSummary(
        total_kwh=total_kwh,
        total_cost=total_cost,
        total_emissions_kg=total_emissions,
        average_kwh=total_kwh / n,
        average_cost=total_cost / n,
        average_emissions_kg=total_emissions / n,
    )


def current_month_report() -> Optional[CurrentMonthReport]:
    b = storage.latest_bill()
    if b is None:
        return None
    return CurrentMonthReport(
        year=b.year,
        month=b.month,
        kilowatt_hours=b.kilowatt_hours,
        cost=b.cost,
        emissions_kg=_emissions_kg(b.kilowatt_hours, b.emission_factor_kg_per_kwh),
    )


def analyze_trends() -> TrendAnalysis:
    pts = get_usage_points()
    pts.sort(key=lambda p: (p.year, p.month))
    trend_points: List[TrendPoint] = []
    kwh_series = [p.kilowatt_hours for p in pts]
    for idx, p in enumerate(pts):
        delta = None
        if idx > 0:
            delta = p.kilowatt_hours - pts[idx - 1].kilowatt_hours
        moving_avg = None
        if idx >= 2:
            window = kwh_series[idx - 2 : idx + 1]
            moving_avg = sum(window) / 3.0
        trend_points.append(
            TrendPoint(
                year=p.year,
                month=p.month,
                kilowatt_hours=p.kilowatt_hours,
                month_over_month_delta_kwh=delta,
                moving_average_3mo_kwh=moving_avg,
            )
        )
    return TrendAnalysis(points=trend_points)


def _linear_regression_predict(y_values: List[float], horizon: int) -> List[float]:
    # Simple OLS for y = a + b*x with x = 1..n
    n = len(y_values)
    if n == 0:
        return [0.0 for _ in range(horizon)]
    x_vals = list(range(1, n + 1))
    mean_x = sum(x_vals) / n
    mean_y = sum(y_values) / n
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_values))
    ss_xx = sum((x - mean_x) ** 2 for x in x_vals)
    if ss_xx == 0:
        # All x are same (n==1). Predict flat line.
        return [y_values[-1] for _ in range(horizon)]
    b = ss_xy / ss_xx
    a = mean_y - b * mean_x
    future = []
    for h in range(1, horizon + 1):
        x_future = n + h
        future.append(a + b * x_future)
    return future


def predict_usage(horizon_months: int = 3) -> PredictionResult:
    pts = get_usage_points()
    pts.sort(key=lambda p: (p.year, p.month))
    y_values = [p.kilowatt_hours for p in pts]
    preds = _linear_regression_predict(y_values, horizon_months)

    predictions: List[PredictionPoint] = []
    if pts:
        start_year = pts[-1].year
        start_month = pts[-1].month
    else:
        start_year = 2000
        start_month = 1

    year, month = start_year, start_month
    for value in preds:
        month += 1
        if month > 12:
            month = 1
            year += 1
        predictions.append(PredictionPoint(year=year, month=month, predicted_kwh=max(0.0, value)))

    return PredictionResult(horizon_months=horizon_months, predictions=predictions)


def generate_advice() -> AdviceBundle:
    pts = get_usage_points()
    tips: List[AdviceItem] = []
    if not pts:
        tips.append(AdviceItem(title="Add data", detail="Submit recent bills to unlock insights and advice."))
        return AdviceBundle(tips=tips)

    # Cost per kWh heuristic
    latest = sorted(pts, key=lambda p: (p.year, p.month))[-1]
    cost_per_kwh = latest.cost / latest.kilowatt_hours if latest.kilowatt_hours > 0 else 0
    if cost_per_kwh > 0.15:
        tips.append(
            AdviceItem(
                title="High cost per kWh",
                detail=(
                    "Consider switching to a time-of-use plan, shifting heavy loads to off-peak, "
                    "or auditing for phantom loads (standby electronics)."
                ),
            )
        )

    # Increasing trend heuristic
    if len(pts) >= 3:
        last3 = sorted(pts, key=lambda p: (p.year, p.month))[-3:]
        if last3[2].kilowatt_hours > last3[0].kilowatt_hours:
            tips.append(
                AdviceItem(
                    title="Rising energy usage",
                    detail=(
                        "Usage is trending up. Check HVAC filters, lighting schedules, and appliance efficiency. "
                        "Seal drafts and consider LED retrofits."
                    ),
                )
            )

    # Emissions factor advice
    avg_emission_factor = 0.0
    if pts:
        # We approximate by dividing emissions by kWh across points
        total_kwh = sum(p.kilowatt_hours for p in pts)
        total_emissions = sum(p.emissions_kg for p in pts)
        avg_emission_factor = (total_emissions / total_kwh) if total_kwh > 0 else 0.0
    if avg_emission_factor >= 0.6:
        tips.append(
            AdviceItem(
                title="Carbon intensity is high",
                detail=(
                    "Your grid has relatively high CO2e/kWh. Consider rooftop solar or purchasing green energy credits."
                ),
            )
        )

    # Always-on practicals
    tips.append(
        AdviceItem(
            title="Quick wins",
            detail=(
                "Set thermostats efficiently (24-26°C cooling, 19-21°C heating), use smart power strips, "
                "and schedule appliances."
            ),
        )
    )

    return AdviceBundle(tips=tips)

