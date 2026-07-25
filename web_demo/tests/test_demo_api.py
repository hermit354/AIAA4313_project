import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

import web_demo.backend as backend
from web_demo.pipeline import PipelineConfig, PipelineResult, StageResult


def formal_result(config=None):
    config = config or PipelineConfig()
    categories = {
        "relevant_experience": {
            "score": 24,
            "max": 30,
            "evidence": "Relevant work.",
        },
        "project_system_evidence": {
            "score": 23,
            "max": 30,
            "evidence": "Concrete systems.",
        },
        "technical_skills_match": {
            "score": 20,
            "max": 25,
            "evidence": "Matching skills.",
        },
        "evidence_quality_impact": {
            "score": 12,
            "max": 15,
            "evidence": "Specific evidence.",
        },
    }
    return PipelineResult(
        status="COMPLETED",
        score=82,
        base=79,
        bonus=4,
        deduction=1,
        categories=categories,
        resume={"basics": {"name": "Test Candidate"}, "skills": []},
        evidence={
            "strengths": ["Formal result."],
            "improvements": ["Add metrics."],
        },
        evaluation={"scores": categories},
        github_data=None,
        stages=[StageResult(name, "COMPLETED", 10) for name in backend.STAGE_NAMES],
        raw_text="Test Candidate",
        config=config,
    )


class DemoApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(cls.temp.name)
        backend.DATA = root / "data"
        backend.UPLOADS = backend.DATA / "uploads"
        backend.ARTIFACTS = backend.DATA / "artifacts"
        backend.DB = backend.DATA / "demo.db"
        backend.seed()
        cls.client = TestClient(backend.app)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        connection = backend.db()
        connection.execute("delete from stage_runs")
        connection.execute("delete from evaluation_runs")
        connection.execute("delete from applications")
        connection.commit()
        connection.close()

    def login(self, email):
        response = self.client.post(
            "/api/auth/login", json={"email": email, "password": "demo123"}
        )
        self.assertEqual(response.status_code, 200)
        return {"Authorization": "Bearer " + response.json()["token"]}

    def upload_queued(self):
        headers = self.login("alice@demo.local")
        with patch("web_demo.backend.enqueue"):
            response = self.client.post(
                "/api/candidate/resume",
                headers=headers,
                files={
                    "file": (
                        "resume.pdf",
                        b"%PDF-1.4\nformal test",
                        "application/pdf",
                    )
                },
            )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_candidate_cannot_read_formal_score_or_run_details(self):
        queued = self.upload_queued()
        headers = self.login("alice@demo.local")
        self.assertEqual(
            self.client.get("/api/staff/applications", headers=headers).status_code,
            403,
        )
        payload = self.client.get("/api/candidate/application", headers=headers).json()[
            "application"
        ]
        self.assertEqual(payload["id"], queued["application_id"])
        self.assertNotIn("score", payload)
        self.assertNotIn("runs", payload)

    def test_staff_view_exposes_candidate_number_from_filename(self):
        headers = self.login("alice@demo.local")
        with patch("web_demo.backend.enqueue"):
            self.client.post(
                "/api/candidate/resume",
                headers=headers,
                files={
                    "file": (
                        "20734_Software_Developer.pdf",
                        b"%PDF-1.4\nformal test",
                        "application/pdf",
                    )
                },
            )
        staff_headers = self.login("staff@demo.local")
        payload = self.client.get(
            "/api/staff/applications", headers=staff_headers
        ).json()
        self.assertEqual(payload[0]["candidate_identifier"], "20734")

    def test_normal_database_read_does_not_mark_active_run_stale(self):
        queued = self.upload_queued()
        connection = backend.db()
        connection.execute(
            "update evaluation_runs set status='RUNNING' where id=?",
            (queued["run_id"],),
        )
        connection.commit()
        connection.close()
        connection = backend.db()
        status = connection.execute(
            "select status from evaluation_runs where id=?",
            (queued["run_id"],),
        ).fetchone()["status"]
        connection.close()
        self.assertEqual(status, "RUNNING")

    def test_formal_result_is_persisted_per_run(self):
        queued = self.upload_queued()
        connection = backend.db()
        run = connection.execute(
            "select config_json from evaluation_runs where id=?",
            (queued["run_id"],),
        ).fetchone()
        config = PipelineConfig(**json.loads(run["config_json"]))
        connection.close()
        with patch(
            "web_demo.backend.run_resume_pipeline",
            return_value=formal_result(config),
        ):
            backend.execute_run(
                queued["application_id"],
                queued["run_id"],
                backend.UPLOADS / "unused.pdf",
                config,
            )
        headers = self.login("staff@demo.local")
        payload = self.client.get(
            f"/api/staff/runs/{queued['run_id']}", headers=headers
        ).json()
        self.assertEqual(payload["evaluation_engine"], "formal_resume_evaluator")
        self.assertEqual(payload["core_score"], 79)
        self.assertEqual(payload["categories"]["relevant_experience"]["max"], 30)
        self.assertEqual(payload["categories"]["evidence_quality_impact"]["max"], 15)
        self.assertTrue(payload["artifact_path"])
        self.assertEqual(len(payload["stages"]), 5)

    def test_formal_pipeline_failure_does_not_create_heuristic_score(self):
        queued = self.upload_queued()
        connection = backend.db()
        config = PipelineConfig(
            **json.loads(
                connection.execute(
                    "select config_json from evaluation_runs where id=?",
                    (queued["run_id"],),
                ).fetchone()["config_json"]
            )
        )
        connection.close()
        with patch(
            "web_demo.backend.run_resume_pipeline",
            side_effect=RuntimeError("structured extraction failed"),
        ):
            backend.execute_run(
                queued["application_id"], queued["run_id"], "unused.pdf", config
            )
        connection = backend.db()
        run = connection.execute(
            "select status,score,error,evaluation_engine from evaluation_runs where id=?",
            (queued["run_id"],),
        ).fetchone()
        connection.close()
        self.assertEqual(run["status"], "FAILED")
        self.assertIsNone(run["score"])
        self.assertIn("structured extraction failed", run["error"])
        self.assertEqual(run["evaluation_engine"], "formal_resume_evaluator")

    def test_unknown_or_unavailable_model_is_rejected(self):
        queued = self.upload_queued()
        headers = self.login("staff@demo.local")
        response = self.client.post(
            f"/api/staff/applications/{queued['application_id']}/rerun",
            headers=headers,
            json={"model": "not-allowlisted"},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
