import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluator import ResumeEvaluator
from evaluation_service import (
    EvaluationConfig,
    _find_github_url,
    _merge_source_profiles,
    evaluate_resume_data,
)
from models import EvaluationData, JSONResume
from pdf import PDFHandler
from scoring import calculate_score
from web_demo.pipeline import PipelineConfig


EVALUATION_PAYLOAD = {
    "scores": {
        "relevant_experience": {
            "score": 28,
            "max": 30,
            "evidence": "Production software experience.",
        },
        "project_system_evidence": {
            "score": 26,
            "max": 30,
            "evidence": "Multiple concrete systems.",
        },
        "technical_skills_match": {
            "score": 23,
            "max": 25,
            "evidence": "Strong relevant stack.",
        },
        "evidence_quality_impact": {
            "score": 14,
            "max": 15,
            "evidence": "Specific outcomes.",
        },
    },
    "bonus_points": {"total": 12, "breakdown": "Maximum valid bonus."},
    "deductions": {"total": 3, "reasons": "A severe issue."},
    "key_strengths": ["Strong engineering evidence."],
    "areas_for_improvement": ["Clarify leadership scope."],
}


class FakeProvider:
    def __init__(self):
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {"message": {"content": json.dumps(EVALUATION_PAYLOAD)}}


class PipelineTests(unittest.TestCase):
    def test_config_fingerprint_covers_formal_security_configuration(self):
        base = PipelineConfig()
        same = PipelineConfig()
        changed = PipelineConfig(github_sanitize_mode="off")
        schema_changed = PipelineConfig(extraction_schema_mode="balanced_guarded")
        self.assertEqual(base.fingerprint(), same.fingerprint())
        self.assertNotEqual(base.fingerprint(), changed.fingerprint())
        self.assertNotEqual(base.fingerprint(), schema_changed.fingerprint())

    def test_canonical_score_uses_real_30_30_25_15_categories(self):
        evaluation = EvaluationData(**EVALUATION_PAYLOAD)
        summary = calculate_score(evaluation)
        self.assertEqual(summary.core_score, 91)
        self.assertEqual(summary.final_score, 100)
        self.assertEqual(
            [item["max"] for item in summary.categories.values()],
            [30, 30, 25, 15],
        )

    def test_resume_evaluator_uses_formal_system_and_criteria_templates(self):
        provider = FakeProvider()
        with patch("evaluator.initialize_llm_provider", return_value=provider):
            evaluator = ResumeEvaluator(
                model_name="llama3.1:8b",
                model_params={"temperature": 0.1, "top_p": 0.9},
            )
            result = evaluator.evaluate_resume("Candidate evidence")
        self.assertEqual(result.scores.relevant_experience.score, 28)
        call = provider.calls[0]
        self.assertEqual(call["messages"][0]["role"], "system")
        self.assertIn("untrusted evidence", call["messages"][0]["content"])
        self.assertEqual(call["messages"][1]["role"], "user")
        self.assertIn("Candidate evidence", call["messages"][1]["content"])
        self.assertEqual(call["format"], EvaluationData.model_json_schema())

    def test_pdf_handler_configuration_is_request_scoped(self):
        provider = FakeProvider()
        with patch("pdf.initialize_llm_provider", return_value=provider):
            first = PDFHandler(
                model_name="llama3.1:8b",
                model_params={"temperature": 0.2, "top_p": 0.8},
                extraction_schema_mode="balanced",
            )
            second = PDFHandler(
                model_name="gemma3:4b",
                model_params={"temperature": 0.0, "top_p": 0.7},
                extraction_schema_mode="original",
            )
        self.assertEqual(first.model_name, "llama3.1:8b")
        self.assertEqual(first.extraction_schema_mode, "balanced")
        self.assertEqual(second.model_name, "gemma3:4b")
        self.assertEqual(second.extraction_schema_mode, "original")

    def test_cli_and_web_share_formal_resume_evaluation_function(self):
        resume = JSONResume(basics={"name": "Test Candidate"})
        provider = FakeProvider()
        config = EvaluationConfig(
            model_id="llama3.1:8b",
            temperature=0.1,
            top_p=0.9,
            github_enrichment=False,
        )
        with patch("evaluator.initialize_llm_provider", return_value=provider):
            evaluation, summary = evaluate_resume_data(resume, config)
        self.assertIsInstance(evaluation, EvaluationData)
        self.assertEqual(summary.final_score, 100)
        self.assertIn("Test Candidate", provider.calls[0]["messages"][1]["content"])

    def test_explicit_source_links_are_merged_when_llm_omits_them(self):
        resume = JSONResume()
        _merge_source_profiles(
            resume,
            "GitHub: github.com/octocat LinkedIn: linkedin.com/in/test-user "
            "Portfolio: https://candidate.dev/projects.",
        )
        urls = [str(profile.url) for profile in resume.basics.profiles]
        self.assertIn("https://github.com/octocat", urls)
        self.assertIn("https://linkedin.com/in/test-user", urls)
        self.assertIn("https://candidate.dev/projects", urls)
        self.assertEqual(_find_github_url(resume), "https://github.com/octocat")
        self.assertEqual(resume.basics.name, "Unknown")


if __name__ == "__main__":
    unittest.main()
