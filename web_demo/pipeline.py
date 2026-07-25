"""Formal request-scoped resume pipeline used by the local web demo."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from evaluation_service import (
    FORMAL_PROMPT_VERSION,
    EvaluationConfig,
    evaluate_pdf,
)
from models import ModelProvider
from prompt import (
    DEFAULT_MODEL,
    GEMINI_API_KEY,
    MODEL_PARAMETERS,
    MODEL_PROVIDER_MAPPING,
    OPENAI_COMPATIBLE_API_KEY,
    OPENAI_COMPATIBLE_BASE_URL,
)


@dataclass(frozen=True)
class PipelineConfig:
    provider: str = "ollama"
    model_id: str = DEFAULT_MODEL
    temperature: float = 0.1
    top_p: float = 0.9
    prompt_version: str = FORMAL_PROMPT_VERSION
    extraction_schema_mode: str = "balanced"
    github_enrichment: bool = True
    github_sanitize_mode: str = "instruction_filter"
    force_fresh: bool = False

    def fingerprint(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True).encode()
        ).hexdigest()

    def formal_config(self) -> EvaluationConfig:
        return EvaluationConfig(
            model_id=self.model_id,
            temperature=self.temperature,
            top_p=self.top_p,
            extraction_schema_mode=self.extraction_schema_mode,
            github_enrichment=self.github_enrichment,
            github_sanitize_mode=self.github_sanitize_mode,
            prompt_version=self.prompt_version,
        )


@dataclass
class StageResult:
    name: str
    status: str
    duration_ms: int
    note: str = ""


@dataclass
class PipelineResult:
    status: str
    score: float
    base: float
    bonus: float
    deduction: float
    categories: dict[str, dict[str, Any]]
    resume: dict[str, Any]
    evidence: dict[str, Any]
    evaluation: dict[str, Any]
    github_data: dict[str, Any] | None
    stages: list[StageResult]
    raw_text: str
    config: PipelineConfig
    evaluation_engine: str = "formal_resume_evaluator"

    def to_json(self) -> dict[str, Any]:
        value = asdict(self)
        value["config"] = asdict(self.config)
        return value


def run_resume_pipeline(pdf_path: str | Path, config: PipelineConfig) -> PipelineResult:
    formal = evaluate_pdf(pdf_path, config.formal_config())
    summary = formal.score_summary
    evaluation = formal.evaluation.model_dump(mode="json")
    stages = [
        StageResult(stage.name, stage.status, stage.duration_ms, stage.note)
        for stage in formal.stages
    ]
    stages.append(
        StageResult("RANK_AND_PERSIST", "COMPLETED", 0, "Ready for staff review")
    )
    return PipelineResult(
        status="COMPLETED",
        score=summary.final_score,
        base=summary.core_score,
        bonus=summary.bonus,
        deduction=summary.deduction,
        categories=summary.categories,
        resume=formal.resume.model_dump(mode="json"),
        evidence={
            "strengths": evaluation["key_strengths"],
            "improvements": evaluation["areas_for_improvement"],
        },
        evaluation=evaluation,
        github_data=formal.github_data,
        stages=stages,
        raw_text=formal.raw_text,
        config=config,
    )


def provider_for(model_id: str) -> str:
    return MODEL_PROVIDER_MAPPING.get(model_id, ModelProvider.OLLAMA).value


def _ollama_models() -> set[str]:
    try:
        import requests

        url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        response = requests.get(url.rstrip("/") + "/api/tags", timeout=1)
        response.raise_for_status()
        return {item.get("name", "") for item in response.json().get("models", [])}
    except Exception:
        return set()


def provider_registry() -> list[dict[str, Any]]:
    installed_ollama = _ollama_models()
    result = []
    for model_id, provider in MODEL_PROVIDER_MAPPING.items():
        if provider == ModelProvider.OLLAMA:
            healthy = model_id in installed_ollama
            provider_name, provider_type = "Ollama", "Local"
        elif provider == ModelProvider.GEMINI:
            healthy = bool(GEMINI_API_KEY)
            provider_name, provider_type = "Google Gemini", "Cloud"
        else:
            healthy = bool(OPENAI_COMPATIBLE_API_KEY and OPENAI_COMPATIBLE_BASE_URL)
            provider_name, provider_type = "OpenAI-compatible", "Cloud"
        result.append(
            {
                "id": model_id,
                "name": model_id,
                "provider": provider_name,
                "provider_id": provider.value,
                "type": provider_type,
                "healthy": healthy,
                "installed": healthy,
                "structured": True,
                "temperature": MODEL_PARAMETERS.get(model_id, {}).get(
                    "temperature", 0.1
                ),
                "topP": MODEL_PARAMETERS.get(model_id, {}).get("top_p", 0.9),
                "availability": "Available" if healthy else "Not configured",
            }
        )
    return result
