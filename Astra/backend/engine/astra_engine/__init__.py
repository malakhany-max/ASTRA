"""Deterministic, side-effect-free ASTRA analytics engine."""

from .evaluation import evaluate
from .plan import make_weekly_plan

__all__ = ["evaluate", "make_weekly_plan"]
