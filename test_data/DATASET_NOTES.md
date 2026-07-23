# Test data notes

## Why the linked Zenodo dataset was not downloaded

The suggested record is **OpenResume: Advancing Career Trajectory Modeling with
Anonymized and Synthetic Resume Datasets** (Zenodo record 14726170). Its files
are restricted and require an approved access request from an institutional
email address. More importantly for this project, the published description
says its core fields are anonymized user/company identifiers, normalized job
titles, and job start/end dates. That makes it useful for career-trajectory
modeling, but not a direct source of the full PDF resumes expected by
`score.py`; it lacks controlled resume prose, projects, skills, and GitHub URLs.

Record: https://zenodo.org/records/14726170

## Prepared samples

- `baseline_no_github.pdf`: exercises PDF parsing and resume evaluation without
  external GitHub input.
- `baseline_github_octocat.pdf`: smoke-tests the public GitHub enrichment path.
  Octocat is not an experimental account and must not be modified.
- `template_controlled_github.pdf`: replace the placeholder URL in the matching
  source text with a team-owned test account before GitHub bio/repository
  description injection experiments.

All candidate identities, contact details, employers, and resume claims are
synthetic. The generated PDFs are deterministic derivatives of the text files
in `test_data/sources/`, making clean/attack pairs easy to compare.

Regenerate all PDFs with:

```bash
.venv/bin/python scripts/generate_test_pdfs.py
```
