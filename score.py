import os
import sys
import json
import logging
import csv
from pdf import PDFHandler
from github import fetch_and_display_github_info
from models import JSONResume, EvaluationData
from typing import List, Optional, Dict
from pathlib import Path
from prompt import DEFAULT_MODEL, MODEL_PARAMETERS
from evaluation_service import EvaluationConfig, evaluate_resume_data
from scoring import CATEGORY_MAXIMA, calculate_score
from transform import (
    transform_evaluation_response,
    convert_json_resume_to_text,
    convert_github_data_to_text,
    convert_blog_data_to_text,
)
from config import DEVELOPMENT_MODE

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)5s - %(lineno)5d - %(funcName)33s - %(levelname)5s - %(message)s",
)


def print_evaluation_results(
    evaluation: EvaluationData, candidate_name: str = "Candidate"
):
    """Print evaluation results in a readable format for the new rubric."""
    print("\n" + "=" * 80)
    print(f"RESUME EVALUATION RESULTS FOR: {candidate_name}")
    print("=" * 80)

    if not evaluation:
        print("No evaluation data available")
        return

    category_labels = {
        "relevant_experience": "Relevant Software Development Experience",
        "project_system_evidence": "Software Project / System Evidence",
        "technical_skills_match": "Technical Skills Depth & Match",
        "evidence_quality_impact": "Evidence Quality, Specificity & Impact",
    }

    summary = calculate_score(evaluation)
    core_max = sum(CATEGORY_MAXIMA.values())
    for category_name, category_data in evaluation.scores.model_dump().items():
        category_score = summary.categories[category_name]["score"]
        if category_score < float(category_data["score"]):
            print(
                f"Warning: {category_name} score capped from "
                f"{category_data['score']} to {category_score} "
                f"(max: {summary.categories[category_name]['max']})"
            )

    print(f"\nCORE SCORE: {summary.core_score:.1f}/{core_max:.0f}")
    print(f"BONUS: +{summary.bonus:.1f}")
    print(f"DEDUCTIONS: -{summary.deduction:.1f}")
    print(f"FINAL SCORE: {summary.final_score:.1f}/100")

    print("\nDETAILED SCORES:")
    print("-" * 60)
    if evaluation.scores:
        for category_name, category_data in evaluation.scores.model_dump().items():
            label = category_labels.get(
                category_name, category_name.replace("_", " ").title()
            )
            normalized = summary.categories[category_name]
            print(f"{label}: {normalized['score']:.1f}/{normalized['max']}")
            print(f"   Evidence: {category_data['evidence']}")
            print()

    if evaluation.bonus_points:
        print(f"\nBONUS BREAKDOWN: +{evaluation.bonus_points.total}")
        print("-" * 30)
        print(f"   {evaluation.bonus_points.breakdown}")

    if evaluation.deductions and evaluation.deductions.total > 0:
        print(f"\nDEDUCTIONS: -{evaluation.deductions.total}")
        print("-" * 30)
        print(f"   {evaluation.deductions.reasons}")

    if evaluation.key_strengths:
        print("\nKEY STRENGTHS:")
        print("-" * 30)
        for i, strength in enumerate(evaluation.key_strengths, 1):
            print(f"  {i}. {strength}")

    if evaluation.areas_for_improvement:
        print("\nAREAS FOR IMPROVEMENT:")
        print("-" * 30)
        for i, area in enumerate(evaluation.areas_for_improvement, 1):
            print(f"  {i}. {area}")

    print("\n" + "=" * 80)


def _evaluate_resume(
    resume_data: JSONResume, github_data: dict = None, blog_data: dict = None
) -> Optional[EvaluationData]:
    """Evaluate the resume using AI and display results."""

    model_params = MODEL_PARAMETERS.get(
        DEFAULT_MODEL, {"temperature": 0.1, "top_p": 0.9}
    )
    config = EvaluationConfig(
        model_id=DEFAULT_MODEL,
        temperature=model_params.get("temperature", 0.1),
        top_p=model_params.get("top_p", 0.9),
        extraction_schema_mode=os.environ.get("EXTRACTION_SCHEMA_MODE", "balanced"),
        github_enrichment=bool(github_data),
        github_sanitize_mode=os.environ.get("GITHUB_SANITIZE_MODE", "off"),
        scoring_prompt_profile=os.environ.get("SCORING_PROMPT_PROFILE", "semantic"),
    )
    evaluation_result, _ = evaluate_resume_data(resume_data, config, github_data)
    return evaluation_result


def is_valid_resume_data(resume_data: JSONResume) -> bool:
    """Check if the resume data has at least some extracted core content."""
    if not resume_data:
        return False
    core_sections = [
        resume_data.basics,
        resume_data.work,
        resume_data.education,
        resume_data.skills,
        resume_data.projects,
    ]
    return any(section is not None for section in core_sections)


def find_profile(profiles, network):
    if not profiles:
        return None
    return next(
        (p for p in profiles if p.network and p.network.lower() == network.lower()),
        None,
    )


def main(pdf_path):
    # Create cache filename based on PDF path
    extraction_schema_mode = os.environ.get(
        "EXTRACTION_SCHEMA_MODE", "balanced"
    ).lower()
    schema_suffix = (
        "" if extraction_schema_mode == "original" else f"_{extraction_schema_mode}"
    )
    model_suffix = "" if DEFAULT_MODEL == "gemma3:4b" else f"_{DEFAULT_MODEL}"
    model_suffix = (
        model_suffix.replace(":", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
    )
    cache_filename = f"cache/resumecache_{os.path.basename(pdf_path).replace('.pdf', '')}{schema_suffix}{model_suffix}.json"
    fixture_dir = os.environ.get("GITHUB_FIXTURE_DIR")
    fixture_suffix = f"_{Path(fixture_dir).name}" if fixture_dir else ""
    github_cache_filename = f"cache/githubcache_{os.path.basename(pdf_path).replace('.pdf', '')}{fixture_suffix}{model_suffix}.json"

    resume_data = None
    cache_loaded = False

    # Check if cache exists and we're in development mode
    if DEVELOPMENT_MODE and os.path.exists(cache_filename):
        print(f"Loading cached data from {cache_filename}")
        try:
            cached_data = json.loads(Path(cache_filename).read_text(encoding="utf-8"))
            loaded_resume = JSONResume(**cached_data)
            if not is_valid_resume_data(loaded_resume):
                raise ValueError("Cached resume data contains no core content")
            resume_data = loaded_resume
            cache_loaded = True
        except Exception as e:
            print(f"⚠️ Warning: Invalid cache file {cache_filename}: {e}")
            print("Ignoring cache and reprocessing PDF...")
            try:
                os.remove(cache_filename)
            except Exception as delete_err:
                print(
                    f"Failed to delete invalid cache file {cache_filename}: {delete_err}"
                )

    if not cache_loaded:
        logger.debug(
            f"Extracting data from PDF"
            + (" and caching to " + cache_filename if DEVELOPMENT_MODE else "")
        )
        pdf_handler = PDFHandler()
        resume_data = pdf_handler.extract_json_from_pdf(pdf_path)

        if resume_data == None:
            return None

        if DEVELOPMENT_MODE:
            if is_valid_resume_data(resume_data):
                os.makedirs(os.path.dirname(cache_filename), exist_ok=True)
                Path(cache_filename).write_text(
                    json.dumps(resume_data.model_dump(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            else:
                logger.warning(
                    "Newly extracted resume data is empty/invalid. Skipping cache write."
                )

    # Check if cache exists and we're in development mode
    github_data = {}
    github_cache_loaded = False
    if DEVELOPMENT_MODE and os.path.exists(github_cache_filename):
        print(f"Loading cached data from {github_cache_filename}")
        try:
            loaded_github = json.loads(
                Path(github_cache_filename).read_text(encoding="utf-8")
            )
            if (
                not isinstance(loaded_github, dict)
                or not loaded_github
                or "profile" not in loaded_github
            ):
                raise ValueError("Cached GitHub data is invalid or empty")
            github_data = loaded_github
            github_cache_loaded = True
        except Exception as e:
            print(f"⚠️ Warning: Invalid GitHub cache file {github_cache_filename}: {e}")
            print("Ignoring GitHub cache and refetching...")
            try:
                os.remove(github_cache_filename)
            except Exception as delete_err:
                print(
                    f"Failed to delete invalid GitHub cache file {github_cache_filename}: {delete_err}"
                )

    if not github_cache_loaded:
        # Add validation to handle None values
        profiles = []
        if resume_data and hasattr(resume_data, "basics") and resume_data.basics:
            profiles = resume_data.basics.profiles or []
        github_profile = find_profile(profiles, "Github")

        if github_profile:
            print(
                f"Fetching GitHub data"
                + (
                    " and caching to " + github_cache_filename
                    if DEVELOPMENT_MODE
                    else ""
                )
            )
            github_data = fetch_and_display_github_info(github_profile.url)

            if (
                DEVELOPMENT_MODE
                and github_data
                and isinstance(github_data, dict)
                and "profile" in github_data
            ):
                os.makedirs(os.path.dirname(github_cache_filename), exist_ok=True)
                Path(github_cache_filename).write_text(
                    json.dumps(github_data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

    score = _evaluate_resume(resume_data, github_data)

    # Get candidate name for display
    candidate_name = os.path.basename(pdf_path).replace(".pdf", "")
    if (
        resume_data
        and hasattr(resume_data, "basics")
        and resume_data.basics
        and resume_data.basics.name
    ):
        candidate_name = resume_data.basics.name

    # Print evaluation results in readable format
    print_evaluation_results(score, candidate_name)

    if DEVELOPMENT_MODE:
        csv_row = transform_evaluation_response(
            file_name=os.path.basename(pdf_path),
            evaluation=score,
            resume_data=resume_data,
            github_data=github_data,
        )

        # Write CSV row to file
        csv_path = os.environ.get(
            "RESUME_EVALUATIONS_CSV", "resume_evaluations_new_rubric.csv"
        )
        file_exists = os.path.exists(csv_path)

        with open(csv_path, "a", newline="", encoding="utf-8") as csvfile:
            fieldnames = list(csv_row.keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write headers if file doesn't exist
            if not file_exists:
                writer.writeheader()

            # Write the row
            writer.writerow(csv_row)

    return score


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python score.py <pdf_path>")
        exit(1)
    pdf_path = sys.argv[1]

    if not os.path.exists(pdf_path):
        print(f"Error: File '{pdf_path}' does not exist.")
        exit(1)

    main(pdf_path)
