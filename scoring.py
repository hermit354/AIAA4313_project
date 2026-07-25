"""Shared score calculation for CLI and web evaluation entry points."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from models import EvaluationData


CATEGORY_MAXIMA = {
    "relevant_experience": 30.0,
    "project_system_evidence": 30.0,
    "technical_skills_match": 25.0,
    "evidence_quality_impact": 15.0,
}


@dataclass(frozen=True)
class ScoreSummary:
    final_score: float
    core_score: float
    bonus: float
    deduction: float
    categories: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def calculate_score(evaluation: EvaluationData) -> ScoreSummary:
    """Apply the canonical Software Developer rubric and score caps."""
    raw_categories = evaluation.scores.model_dump()
    categories: dict[str, dict[str, Any]] = {}

    for name, maximum in CATEGORY_MAXIMA.items():
        item = raw_categories[name]
        score = max(0.0, min(float(item["score"]), maximum))
        categories[name] = {
            "score": round(score, 1),
            "max": int(maximum),
            "evidence": str(item["evidence"]),
        }

    core_score = sum(item["score"] for item in categories.values())
    bonus = max(0.0, min(float(evaluation.bonus_points.total), 12.0))
    deduction = max(0.0, min(float(evaluation.deductions.total), 5.0))
    final_score = max(0.0, min(core_score + bonus - deduction, 100.0))

    return ScoreSummary(
        final_score=round(final_score, 1),
        core_score=round(core_score, 1),
        bonus=round(bonus, 1),
        deduction=round(deduction, 1),
        categories=categories,
    )
