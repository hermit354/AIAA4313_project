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
    parser.add_argument("--pdf", required=True, help="Path to the PDF resume.")
    parser.add_argument(
        "--github-json",
        required=True,
        help="Path to the controlled GitHub fixture JSON.",
    )
    parser.add_argument(
        "--sanitize-mode",
        default="semantic_filter",
        choices=["off", "instruction_filter", "semantic_filter"],
        help="GitHub sanitizer mode.",
    )
    parser.add_argument(
        "--github-evidence-mode",
        default="raw",
        choices=["raw", "structured_extract", "adaptive_structured"],
        help="GitHub evidence serialization/gate mode.",
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
    return parser.parse_args()


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


def main() -> int:
    args = parse_args()

    os.environ["DEFAULT_MODEL"] = args.model
    os.environ["EXTRACTION_SCHEMA_MODE"] = args.schema_mode
    os.environ["GITHUB_SANITIZE_MODE"] = args.sanitize_mode
    os.environ["GITHUB_EVIDENCE_MODE"] = args.github_evidence_mode
    os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
    os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

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
        resume_data = JSONResume(
            **json.loads(resume_cache_path.read_text(encoding="utf-8"))
        )
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
        f"sanitize={args.sanitize_mode}, github_evidence={args.github_evidence_mode}, model={args.model}"
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
        "sanitize_mode": args.sanitize_mode,
        "github_evidence_mode": args.github_evidence_mode,
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
