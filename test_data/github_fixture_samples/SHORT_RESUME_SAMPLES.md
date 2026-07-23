# Short Resume Samples

This folder contains a short, resume-like subset derived from the controlled
Djinni candidate fixtures. The files are intended to reduce parser instability
caused by long, duplicated profile text while keeping enough structure for the
Hiring Agent pipeline.

## Files

| Alias | PDF | Source text | Quality band | Controlled GitHub user |
| --- | --- | --- | --- | --- |
| `short_candidate_01` | `resumes/short_candidate_01.pdf` | `resume_sources/short_candidate_01.txt` | Junior / low-mid | `fixture-candidate-01` |
| `short_candidate_02` | `resumes/short_candidate_02.pdf` | `resume_sources/short_candidate_02.txt` | Entry-level / weaker | `fixture-candidate-02` |
| `short_candidate_03` | `resumes/short_candidate_03.pdf` | `resume_sources/short_candidate_03.txt` | Mid-level | `fixture-candidate-03` |
| `short_candidate_04` | `resumes/short_candidate_04.pdf` | `resume_sources/short_candidate_04.txt` | Stronger / senior | `fixture-candidate-04` |

All four resumes are one page. Each includes basic information, target role,
summary, work experience, projects, skills, education, and awards.

## Length Check

| PDF | Pages | Approx. words |
| --- | ---: | ---: |
| `short_candidate_01.pdf` | 1 | 207 |
| `short_candidate_02.pdf` | 1 | 192 |
| `short_candidate_03.pdf` | 1 | 192 |
| `short_candidate_04.pdf` | 1 | 219 |

## Parser Smoke Test

The short PDFs were tested with the project default `gemma3:4b` model and the
default Optional Pydantic section schemas. In the final smoke test, all four
PDFs successfully extracted all six sections:

`basics`, `work`, `education`, `skills`, `projects`, and `awards`.

## Regeneration

Regenerate the short text sources and PDFs with:

```bash
./scripts/build_short_resume_samples.py
```

For GitHub metadata experiments, use the existing clean/bio/repo fixture
directories. The short resumes keep the same controlled GitHub usernames as the
original four samples.
