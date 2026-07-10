"""Shared RiskReport/RiskItem schema.

Risk is computed in plain Python (app/services/risk.py) — never by the LLM,
per CLAUDE.md's non-negotiable "Risk score must be computed in plain Python"
constraint. This model is the ONE shared shape for risk data; both the graph
state and the FastAPI response models import it directly.
"""

from typing import Literal

from pydantic import BaseModel


class RiskItem(BaseModel):
    skill: str
    hours_at_risk: float
    severity: Literal["low", "medium", "high"]
    detail: str


class RiskReport(BaseModel):
    score: int  # 0..100, higher = riskier
    level: Literal["low", "medium", "high"]
    items: list[RiskItem]
    narrative: str  # human-readable, AI-suggested-style text
