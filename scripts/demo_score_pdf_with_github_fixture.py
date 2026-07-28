#!/usr/bin/env python3
"""Score one PDF resume with one controlled GitHub JSON fixture.

This helper is for the project demo handoff. It avoids live GitHub access:
the PDF is extracted normally, while GitHub evidence is loaded from a local JSON
fixture and then passed through the same transform/scoring path as the project.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "test_data" / "demo_handoff_samples" / "cache"

DEMO_PROFILES = {
    "clean_current": {
        "scoring_prompt_profile": "semantic",
        "sanitize_mode": "semantic_filter",
        "github_evidence_mode": "raw",
        "description": "Current strongest normal scoring profile for clean sanity checks.",
    },
    "v0_original": {
        "scoring_prompt_profile": "weak",
        "sanitize_mode": "off",
        "github_evidence_mode": "raw",
        "description": "Original-style weak baseline: raw GitHub text, no sanitizer, no scorer prompt-injection boundary.",
    },
    "v1_basic": {
        "scoring_prompt_profile": "basic",
        "sanitize_mode": "instruction_filter",
        "github_evidence_mode": "raw",
        "description": "Advanced baseline: direct-command filter and basic scorer hardening, but no semantic scoring-boundary defense.",
    },
    "v1_5_semantic_filter": {
        "scoring_prompt_profile": "semantic",
        "sanitize_mode": "semantic_filter",
        "github_evidence_mode": "raw",
        "description": "Semantic defense: current hardened scorer plus semantic GitHub text filter.",
    },
    "v2_structured_gate": {
        "scoring_prompt_profile": "basic",
        "sanitize_mode": "instruction_filter",
        "github_evidence_mode": "structured_extract",
        "description": "Structured defense: GitHub free text is converted to schema-constrained evidence before scoring.",
    },
}

DEMO_PROFILE_ALIASES = {
    "v0": "v0_original",
    "v1": "v1_basic",
    "v1.5": "v1_5_semantic_filter",
    "v1_5": "v1_5_semantic_filter",
    "v2": "v2_structured_gate",
}


def _safe_model_suffix(model: str, schema_mode: str) -> str:
    raw = f"{model}_{schema_mode}"
    return (
        raw.replace(":", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a single controlled demo evaluation: PDF + local GitHub JSON fixture."
    )
    parser.add_argument(
        "--list-demo-profiles",
        action="store_true",
        help="List reproducible demo profiles and exit.",
    )
    parser.add_argument(
        "--demo-profile",
        choices=sorted(DEMO_PROFILES | DEMO_PROFILE_ALIASES),
        help=(
            "Named reproducible demo configuration. "
            "Use v0_original, v1_basic, v1_5_semantic_filter, or v2_structured_gate."
        ),
    )
    parser.add_argument("--pdf", help="Path to the PDF resume.")
    parser.add_argument(
        "--github-json",
        help="Path to the controlled GitHub fixture JSON.",
    )
    parser.add_argument(
        "--sanitize-mode",
        default=None,
        choices=["off", "instruction_filter", "semantic_filter"],
        help="GitHub sanitizer mode. Overrides --demo-profile when provided.",
    )
    parser.add_argument(
        "--github-evidence-mode",
        default=None,
        choices=["raw", "structured_extract", "adaptive_structured"],
        help="GitHub evidence serialization/gate mode. Overrides --demo-profile when provided.",
    )
    parser.add_argument(
        "--scoring-prompt-profile",
        default=None,
        choices=["weak", "basic", "semantic"],
        help="Scorer prompt boundary profile. Overrides --demo-profile when provided.",
    )
    parser.add_argument(
        "--model",
        default="llama3.1:8b",
        help="Model name used by the project provider. Default: llama3.1:8b.",
    )
    parser.add_argument(
        "--schema-mode",
        default="balanced",
        help="PDF extraction schema mode. Default: balanced.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force re-extraction from PDF instead of using demo cache.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional path for saving the evaluation result JSON.",
    )
    args = parser.parse_args()
    if not args.list_demo_profiles and (not args.pdf or not args.github_json):
        parser.error("--pdf and --github-json are required unless --list-demo-profiles is used")
    return args


def resolve_demo_config(args: argparse.Namespace) -> dict[str, str]:
    profile_name = None
    if args.demo_profile:
        profile_name = DEMO_PROFILE_ALIASES.get(args.demo_profile, args.demo_profile)
        config = dict(DEMO_PROFILES[profile_name])
    else:
        config = dict(DEMO_PROFILES["clean_current"])

    if args.sanitize_mode is not None:
        config["sanitize_mode"] = args.sanitize_mode
    if args.github_evidence_mode is not None:
        config["github_evidence_mode"] = args.github_evidence_mode
    if args.scoring_prompt_profile is not None:
        config["scoring_prompt_profile"] = args.scoring_prompt_profile
    config["demo_profile"] = profile_name or "manual"
    return config


def print_demo_profiles() -> None:
    print("Available demo profiles:")
    for name, config in DEMO_PROFILES.items():
        print(f"- {name}")
        print(f"  scoring_prompt_profile: {config['scoring_prompt_profile']}")
        print(f"  sanitize_mode: {config['sanitize_mode']}")
        print(f"  github_evidence_mode: {config['github_evidence_mode']}")
        print(f"  description: {config['description']}")


def summarize_score(evaluation: Any) -> dict[str, Any]:
    scores_data = evaluation.scores.model_dump() if evaluation.scores else {}
    categories: dict[str, dict[str, Any]] = {}
    category_total = 0.0
    for name, category_data in scores_data.items():
        score = min(float(category_data["score"]), float(category_data["max"]))
        category_total += score
        categories[name] = {
            "score": score,
            "max": float(category_data["max"]),
            "evidence": category_data["evidence"],
        }

    bonus = float(evaluation.bonus_points.total)
    deductions = float(evaluation.deductions.total)
    total = max(0.0, min(100.0, category_total + bonus - deductions))
    return {
        "total_score": total,
        "category_total": category_total,
        "categories": categories,
        "bonus": bonus,
        "deductions": deductions,
        "key_strengths": evaluation.key_strengths,
        "areas_for_improvement": evaluation.areas_for_improvement,
    }


def load_json_resume_cache(cache_path: Path, json_resume_cls: Any) -> Any:
    """Load either a raw JSONResume cache or a wrapped experiment cache.

    Some experiment scripts save caches as:

        {"candidate_id": "...", "summary": {...}, "resume": {...}}

    The demo runner must use the nested `resume` object in that case. Passing the
    wrapper directly into JSONResume silently drops the unknown metadata fields
    and can produce an almost empty resume, which makes scores hard to reproduce.
    """

    cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
    if isinstance(cache_data, dict) and isinstance(cache_data.get("resume"), dict):
        resume_payload = cache_data["resume"]
    else:
        resume_payload = cache_data
    resume = json_resume_cls(**resume_payload)
    if not any(
        [
            getattr(resume, "basics", None),
            getattr(resume, "work", None),
            getattr(resume, "education", None),
            getattr(resume, "skills", None),
            getattr(resume, "projects", None),
        ]
    ):
        raise ValueError(
            f"Resume cache produced no core content; cache may be malformed: {cache_path}"
        )
    return resume


def main() -> int:
    args = parse_args()
    if args.list_demo_profiles:
        print_demo_profiles()
        return 0
    demo_config = resolve_demo_config(args)

    os.environ["DEFAULT_MODEL"] = args.model
    os.environ["EXTRACTION_SCHEMA_MODE"] = args.schema_mode
    os.environ["GITHUB_SANITIZE_MODE"] = demo_config["sanitize_mode"]
    os.environ["GITHUB_EVIDENCE_MODE"] = demo_config["github_evidence_mode"]
    os.environ["SCORING_PROMPT_PROFILE"] = demo_config["scoring_prompt_profile"]
    # Local Ollama calls should not go through the user's HTTP/SOCKS proxy.
    # Otherwise httpx may require the optional socksio package before it even
    # reaches 127.0.0.1.
    for proxy_key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        os.environ.pop(proxy_key, None)
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    os.environ["no_proxy"] = "127.0.0.1,localhost"

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from models import JSONResume
    from pdf import PDFHandler
    from score import _evaluate_resume

    pdf_path = Path(args.pdf).resolve()
    github_path = Path(args.github_json).resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    if not github_path.exists():
        raise FileNotFoundError(github_path)

    github_data = json.loads(github_path.read_text(encoding="utf-8"))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_name = f"{pdf_path.stem}_{_safe_model_suffix(args.model, args.schema_mode)}.json"
    resume_cache_path = CACHE_DIR / cache_name

    if resume_cache_path.exists() and not args.no_cache:
        resume_data = load_json_resume_cache(resume_cache_path, JSONResume)
        print(f"[cache] loaded extracted resume: {resume_cache_path}")
    else:
        print(f"[extract] PDF -> JSONResume: {pdf_path}")
        resume_data = PDFHandler().extract_json_from_pdf(str(pdf_path))
        if resume_data is None:
            raise RuntimeError("PDF extraction returned None")
        resume_cache_path.write_text(
            json.dumps(resume_data.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[cache] saved extracted resume: {resume_cache_path}")

    print(
        "[score] "
        f"demo_profile={demo_config['demo_profile']}, "
        f"scoring_prompt={demo_config['scoring_prompt_profile']}, "
        f"sanitize={demo_config['sanitize_mode']}, "
        f"github_evidence={demo_config['github_evidence_mode']}, "
        f"model={args.model}"
    )
    evaluation = _evaluate_resume(resume_data, github_data)
    summary = summarize_score(evaluation)

    print("\n=== Score summary ===")
    print(f"total_score: {summary['total_score']:.1f}")
    for name, category in summary["categories"].items():
        print(f"- {name}: {category['score']:.1f}/{category['max']:.1f}")
    print(f"bonus: {summary['bonus']:.1f}")
    print(f"deductions: {summary['deductions']:.1f}")

    result = {
        "pdf": str(pdf_path),
        "github_json": str(github_path),
        "model": args.model,
        "schema_mode": args.schema_mode,
        "demo_profile": demo_config["demo_profile"],
        "profile_description": demo_config["description"],
        "scoring_prompt_profile": demo_config["scoring_prompt_profile"],
        "sanitize_mode": demo_config["sanitize_mode"],
        "github_evidence_mode": demo_config["github_evidence_mode"],
        "resume_cache_path": str(resume_cache_path),
        "score_summary": summary,
        "evaluation": evaluation.model_dump(),
    }
    if args.output_json:
        output_path = Path(args.output_json).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[output] saved: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
