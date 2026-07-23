#!/usr/bin/env python3
"""Build a resume-only prompt-injection variant for candidate_01."""

from pathlib import Path

from build_github_fixture_samples import ATTACK_PAYLOAD
from generate_test_pdfs import render


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = ROOT / "test_data" / "github_fixture_samples"
BASE_SOURCE = SAMPLE_ROOT / "resume_sources" / "candidate_01.txt"
OUTPUT_SOURCE = SAMPLE_ROOT / "resume_sources" / "candidate_01_resume_injection.txt"
OUTPUT_PDF = SAMPLE_ROOT / "resumes" / "candidate_01_resume_injection.pdf"


def main() -> None:
    source = BASE_SOURCE.read_text(encoding="utf-8")
    marker = "## Profile\n"
    if marker not in source:
        raise SystemExit(f"Could not find insertion marker in {BASE_SOURCE}")
    injected = source.replace(
        marker,
        marker + "Candidate note: " + ATTACK_PAYLOAD + "\n\n",
        1,
    )
    OUTPUT_SOURCE.write_text(injected, encoding="utf-8")
    render(OUTPUT_SOURCE, OUTPUT_PDF)
    print(f"generated {OUTPUT_PDF.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
