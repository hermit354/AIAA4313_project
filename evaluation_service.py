"""Request-scoped formal resume evaluation shared by CLI and the web demo."""

from __future__ import annotations

import time
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from evaluator import ResumeEvaluator
from github import fetch_and_display_github_info
from models import Basics, EvaluationData, JSONResume, Profile
from pdf import PDFHandler
from prompt import DEFAULT_MODEL, MODEL_PARAMETERS
from scoring import ScoreSummary, calculate_score
from transform import convert_github_data_to_text, convert_json_resume_to_text


FORMAL_PROMPT_VERSION = "formal-software-developer-v1"


@dataclass(frozen=True)
class EvaluationConfig:
    model_id: str = DEFAULT_MODEL
    temperature: float = 0.1
    top_p: float = 0.9
    extraction_schema_mode: str = "balanced"
    github_enrichment: bool = True
    github_sanitize_mode: str = "instruction_filter"
    scoring_prompt_profile: str = "semantic"
    prompt_version: str = FORMAL_PROMPT_VERSION

    @property
    def model_params(self) -> dict[str, float]:
        defaults = MODEL_PARAMETERS.get(
            self.model_id, {"temperature": 0.1, "top_p": 0.9}
        )
        return {
            **defaults,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }


@dataclass
class ServiceStage:
    name: str
    status: str
    duration_ms: int
    note: str = ""


@dataclass
class FormalEvaluationResult:
    raw_text: str
    resume: JSONResume
    github_data: dict[str, Any] | None
    evaluation: EvaluationData
    score_summary: ScoreSummary
    config: EvaluationConfig
    stages: list[ServiceStage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "resume": self.resume.model_dump(mode="json"),
            "github_data": self.github_data,
            "evaluation": self.evaluation.model_dump(mode="json"),
            "score_summary": self.score_summary.to_dict(),
            "config": asdict(self.config),
            "stages": [asdict(stage) for stage in self.stages],
            "evaluation_engine": "formal_resume_evaluator",
        }


class FormalEvaluationError(RuntimeError):
    """Formal pipeline failure carrying completed/failed stage information."""

    def __init__(self, message: str, stages: list[ServiceStage]):
        super().__init__(message)
        self.stages = list(stages)


PROFILE_DOMAINS = {
    "github.com": "GitHub",
    "linkedin.com": "LinkedIn",
    "gitlab.com": "GitLab",
    "bitbucket.org": "Bitbucket",
    "stackoverflow.com": "Stack Overflow",
    "leetcode.com": "LeetCode",
    "github.io": "Portfolio",
    "twitter.com": "X / Twitter",
    "x.com": "X / Twitter",
}
URL_PATTERN = re.compile(
    r"""(?i)(?:https?://|www\.)[^\s<>{}\[\]"']+|"""
    r"(?:github\.com|linkedin\.com|gitlab\.com|bitbucket\.org|"
    r"""stackoverflow\.com|leetcode\.com)/[^\s<>{}\[\]"']+"""
)


def _normalize_url(raw_url: str) -> str | None:
    value = raw_url.strip().rstrip(".,;:!?)]}>")
    if not value:
        return None
    if not re.match(r"(?i)^https?://", value):
        value = "https://" + value
    parsed = urlparse(value)
    if not parsed.netloc or "." not in parsed.netloc:
        return None
    return value


def _profile_from_url(url: str) -> Profile:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    network = next(
        (label for domain, label in PROFILE_DOMAINS.items() if host.endswith(domain)),
        "Portfolio",
    )
    parts = [part for part in parsed.path.split("/") if part]
    username = parts[-1] if parts else None
    if network == "LinkedIn" and len(parts) >= 2 and parts[-2] in {"in", "pub"}:
        username = parts[-1]
    return Profile(network=network, username=username, url=url)


def _merge_source_profiles(resume: JSONResume, raw_text: str) -> None:
    """Recover explicit source URLs that the LLM section extractor omitted."""
    if not resume.basics:
        resume.basics = Basics(name="Unknown", profiles=[])
    profiles: list[Profile] = []
    seen: set[str] = set()
    for profile in resume.basics.profiles or []:
        normalized = _normalize_url(str(profile.url))
        if not normalized or normalized.lower() in seen:
            continue
        detected = _profile_from_url(normalized)
        profiles.append(
            Profile(
                network=(
                    detected.network
                    if not profile.network or profile.network == "Portfolio"
                    else profile.network
                ),
                username=profile.username or detected.username,
                url=normalized,
            )
        )
        seen.add(normalized.lower())
    if resume.basics.url:
        normalized = _normalize_url(str(resume.basics.url))
        if normalized:
            resume.basics.url = normalized
            seen.add(normalized.lower())
        else:
            resume.basics.url = None
    for match in URL_PATTERN.finditer(raw_text):
        normalized = _normalize_url(match.group(0))
        if not normalized or normalized.lower() in seen:
            continue
        profiles.append(_profile_from_url(normalized))
        seen.add(normalized.lower())
    resume.basics.profiles = profiles


def _find_github_url(resume: JSONResume) -> str | None:
    if not resume.basics or not resume.basics.profiles:
        return None
    for profile in resume.basics.profiles:
        host = urlparse(str(profile.url)).netloc.lower().removeprefix("www.")
        if (
            (profile.network and profile.network.lower() == "github")
            or host.endswith("github.com")
        ) and profile.url:
            return str(profile.url)
    return None


def _timed(stages: list[ServiceStage], name: str, fn):
    start = time.perf_counter()
    try:
        value = fn()
    except Exception as exc:
        stages.append(
            ServiceStage(
                name=name,
                status="FAILED",
                duration_ms=int((time.perf_counter() - start) * 1000),
                note=f"{type(exc).__name__}: {exc}",
            )
        )
        raise
    stages.append(
        ServiceStage(
            name=name,
            status="COMPLETED",
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
    )
    return value


def _required(value, message: str):
    if value is None or value == "":
        raise RuntimeError(message)
    return value


def evaluate_resume_data(
    resume: JSONResume,
    config: EvaluationConfig,
    github_data: dict[str, Any] | None = None,
) -> tuple[EvaluationData, ScoreSummary]:
    """Evaluate already structured resume data with the formal Jinja prompts."""
    resume_text = convert_json_resume_to_text(resume)
    if github_data:
        resume_text += convert_github_data_to_text(
            github_data, sanitize_mode=config.github_sanitize_mode
        )
    evaluator = ResumeEvaluator(
        model_name=config.model_id,
        model_params=config.model_params,
        scoring_prompt_profile=config.scoring_prompt_profile,
    )
    evaluation = evaluator.evaluate_resume(resume_text)
    return evaluation, calculate_score(evaluation)


def evaluate_pdf(
    pdf_path: str | Path,
    config: EvaluationConfig,
) -> FormalEvaluationResult:
    """Run the complete formal PDF-to-score pipeline without silent fallback."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(path)

    stages: list[ServiceStage] = []
    handler = PDFHandler(
        model_name=config.model_id,
        model_params=config.model_params,
        extraction_schema_mode=config.extraction_schema_mode,
    )

    try:
        raw_text = _timed(
            stages,
            "PDF_TEXT_EXTRACTION",
            lambda: _required(
                handler.extract_text_from_pdf(str(path)),
                "PDF contains no extractable text",
            ),
        )
        resume = _timed(
            stages,
            "RESUME_SECTION_PARSE",
            lambda: _required(
                handler.extract_json_from_text(raw_text),
                "Formal resume section extraction failed",
            ),
        )
        _merge_source_profiles(resume, raw_text)

        github_data: dict[str, Any] | None = None
        github_url = _find_github_url(resume)
        if config.github_enrichment and github_url:
            github_data = _timed(
                stages,
                "GITHUB_ENRICHMENT",
                lambda: fetch_and_display_github_info(
                    github_url,
                    model_name=config.model_id,
                    model_params=config.model_params,
                ),
            )
        else:
            reason = (
                "Disabled by run configuration"
                if not config.github_enrichment
                else "No GitHub profile found in the structured resume"
            )
            stages.append(ServiceStage("GITHUB_ENRICHMENT", "SKIPPED", 0, reason))

        evaluation, summary = _timed(
            stages,
            "EVALUATION",
            lambda: evaluate_resume_data(resume, config, github_data),
        )
        return FormalEvaluationResult(
            raw_text=raw_text,
            resume=resume,
            github_data=github_data,
            evaluation=evaluation,
            score_summary=summary,
            config=config,
            stages=stages,
        )
    except Exception as exc:
        if isinstance(exc, FormalEvaluationError):
            raise
        raise FormalEvaluationError(str(exc), stages) from exc
