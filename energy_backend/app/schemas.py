from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class BillBase(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    kilowatt_hours: float = Field(..., gt=0, description="Energy consumed in kWh for the billing period")
    cost: float = Field(..., ge=0, description="Total bill amount for the period in currency units")
    emission_factor_kg_per_kwh: float = Field(
        0.7,
        ge=0,
        description="Grid emission factor in kg CO2e per kWh (configurable)",
    )


class BillCreate(BillBase):
    pass


class BillRead(BillBase):
    id: int


class UsagePoint(BaseModel):
    year: int
    month: int
    kilowatt_hours: float
    cost: float
    emissions_kg: float


class UsageSummary(BaseModel):
    total_kwh: float
    total_cost: float
    total_emissions_kg: float
    average_kwh: float
    average_cost: float
    average_emissions_kg: float


class CurrentMonthReport(BaseModel):
    year: int
    month: int
    kilowatt_hours: float
    cost: float
    emissions_kg: float


class TrendPoint(BaseModel):
    year: int
    month: int
    kilowatt_hours: float
    month_over_month_delta_kwh: Optional[float] = None
    moving_average_3mo_kwh: Optional[float] = None


class TrendAnalysis(BaseModel):
    points: list[TrendPoint]


class PredictionPoint(BaseModel):
    year: int
    month: int
    predicted_kwh: float


class PredictionResult(BaseModel):
    horizon_months: int
    predictions: list[PredictionPoint]


class AdviceItem(BaseModel):
    title: str
    detail: str


class AdviceBundle(BaseModel):
    tips: list[AdviceItem]

