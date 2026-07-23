#!/usr/bin/env python3
"""Build a synthetic oracle resume and GitHub fixtures for maximum scoring."""

from __future__ import annotations

import json
from pathlib import Path

from generate_test_pdfs import render


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = ROOT / "test_data" / "github_fixture_samples"
SOURCE_DIR = SAMPLE_ROOT / "resume_sources"
RESUME_DIR = SAMPLE_ROOT / "resumes"
FIXTURE_DIR = SAMPLE_ROOT / "fixtures" / "max_score"
USERNAME = "fixture-max-score"


RESUME = f"""# Max Score Candidate V2
max-score-candidate@example.test | Remote | San Francisco, CA
GitHub: https://github.com/{USERNAME}
Portfolio: https://example.test/max-score
LinkedIn: https://linkedin.com/in/fixture-max-score
Technical Blog: https://example.test/max-score/blog

## Target Role
Software Engineering Intern

## Summary
Software engineer with maximum-strength evidence across every evaluation
category: core maintainer of popular 1000+ star open-source projects, Google
Summer of Code contributor, Girl Script Summer of Code participant, startup
co-founder, early-stage engineer, production owner, complex full-stack project
builder, technical blogger, and broad engineer across backend, frontend, cloud,
security, data, machine learning, testing, and developer tooling.

## Work Experience
OpenInfra Tools | Co-Founder and Early-Stage Engineer | 2023-01 - Present
- Built a production developer platform used by 120 external teams for CI
  analytics, release automation, code review workflows, and deployment safety.
- Designed microservices, PostgreSQL schemas, Redis queues, Kubernetes clusters,
  observability dashboards, incident response automation, and security review
  pipelines with 99.95% uptime.
- Led architecture, incident response, technical documentation, and customer
  integrations as a co-founder and one of the first five engineers.

Kubernetes Community | Google Summer of Code Contributor | 2022-05 - 2022-09
- Completed Google Summer of Code with accepted Kubernetes scheduler plugin
  improvements, 40 merged commits, test coverage, documentation, and maintainer
  review for a 4500+ star open-source infrastructure project.
- Collaborated with maintainers through pull requests, code reviews, issues,
  and design discussions.

CodeHealth Labs | Software Engineering Intern | 2021-06 - 2021-12
- Built production APIs, background jobs, and monitoring dashboards for a
  developer analytics product.
- Added integration tests, API documentation, and automated deployment checks.

Open Source Community | Girl Script Summer of Code Participant | 2021-01 - 2021-05
- Contributed bug fixes, documentation, tests, and accessibility improvements
  to developer tooling projects with community maintainers.

## Projects
Kubernetes Scheduler Plugin | https://github.com/{USERNAME}/kubernetes-scheduler-plugin
- Popular open-source contribution with 4500 stars, 40 author commits, tests,
  documentation, and maintainer reviews.

React Query DevTools | https://github.com/{USERNAME}/react-query-devtools
- Open-source contribution with 3200 stars, TypeScript UI fixes, accessibility
  improvements, and release notes.

AI Code Review Platform | https://github.com/{USERNAME}/ai-code-review-platform
- Full-stack production project with authentication, PostgreSQL, Redis queues,
  LLM-assisted review, GitHub integration, deployment, and live demo.
- Used by 120 teams, includes full documentation, architecture diagrams,
  integration tests, end-to-end tests, observability, and security review.
- Live demo: https://example.test/ai-review

Realtime Collaboration Editor | https://github.com/{USERNAME}/realtime-collab-editor
- Real-time application with WebSocket sync, CRDT conflict resolution, role-based
  permissions, audit logs, and end-to-end tests.
- Includes public documentation, deployment guide, load tests, and user-facing
  live demo.
- Live demo: https://example.test/collab-editor

Distributed Job Queue | https://github.com/{USERNAME}/distributed-job-queue
- Backend system with worker orchestration, retry policies, metrics, tracing,
  failure recovery, and load testing.

## Technical Skills
Programming languages: TypeScript, Python, Go, Java, SQL, JavaScript.
Frameworks and platforms: React, Next.js, FastAPI, Node.js, GraphQL, REST.
Cloud and data: PostgreSQL, Redis, Docker, Kubernetes, Terraform, AWS.
Engineering practices: unit testing, integration testing, end-to-end testing, CI,
observability, security review, distributed systems, LLM evaluation.

## Publications
Technical Blog | https://example.test/max-score/blog | 2023 - Present
- Published high-quality technical articles on Kubernetes schedulers, LLM code
  review systems, distributed queues, observability, and secure CI pipelines.

## Education
Bachelor of Computer Science | Example Technical University | 2019 - 2023
- Coursework in algorithms, databases, distributed systems, software
  engineering, machine learning, and computer security.

## Awards
Google Summer of Code Contributor | Kubernetes Community | 2022
- Completed accepted open-source contributions with maintainer review.

Girl Script Summer of Code Participant | Open Source Community | 2021
- Contributed documentation and bug fixes to developer tooling projects.

Startup Founder Award | OpenInfra Tools | 2023
- Recognized for co-founding an early-stage developer tools startup and leading
  production engineering work.
"""


REPOS = [
    {
        "name": "kubernetes-scheduler-plugin",
        "description": "Popular Kubernetes scheduler plugin contribution with 40 merged commits, maintainer-reviewed tests, documentation, and production examples.",
        "language": "Go",
        "stars": 12500,
        "forks": 2200,
        "homepage": "https://example.test/kubernetes-plugin",
        "topics": ["go", "kubernetes", "scheduler", "open-source"],
        "author_commits": 40,
        "other_commits": [850, 620, 410],
    },
    {
        "name": "react-query-devtools",
        "description": "TypeScript open-source maintainer contribution to React Query developer tooling, accessibility, tests, docs, and release notes.",
        "language": "TypeScript",
        "stars": 9800,
        "forks": 1400,
        "homepage": "https://example.test/react-query-devtools",
        "topics": ["typescript", "react", "devtools", "open-source"],
        "author_commits": 28,
        "other_commits": [700, 430, 260],
    },
    {
        "name": "fastapi-observability",
        "description": "Open-source FastAPI observability middleware with tracing, metrics, dashboards, production examples, and complete documentation.",
        "language": "Python",
        "stars": 7600,
        "forks": 980,
        "homepage": "https://example.test/fastapi-observability",
        "topics": ["python", "fastapi", "observability", "open-source"],
        "author_commits": 35,
        "other_commits": [310, 190],
    },
    {
        "name": "ai-code-review-platform",
        "description": "Full-stack production platform used by 120 teams for LLM-assisted code review with auth, queues, PostgreSQL, GitHub integration, tests, docs, and live demo.",
        "language": "TypeScript",
        "stars": 2400,
        "forks": 360,
        "homepage": "https://example.test/ai-review",
        "topics": ["typescript", "llm", "code-review", "production"],
        "author_commits": 160,
        "other_commits": [],
    },
    {
        "name": "realtime-collab-editor",
        "description": "Real-time collaborative editor with CRDT synchronization, WebSocket presence, permissions, audit logs, load tests, documentation, and live demo.",
        "language": "TypeScript",
        "stars": 1900,
        "forks": 280,
        "homepage": "https://example.test/collab-editor",
        "topics": ["typescript", "websocket", "crdt", "full-stack"],
        "author_commits": 125,
        "other_commits": [],
    },
    {
        "name": "distributed-job-queue",
        "description": "Distributed worker queue with retries, scheduling, metrics, tracing, load-tested failure recovery, docs, and production deployments.",
        "language": "Go",
        "stars": 1600,
        "forks": 210,
        "homepage": "https://example.test/job-queue",
        "topics": ["go", "distributed-systems", "queues", "observability"],
        "author_commits": 110,
        "other_commits": [],
    },
    {
        "name": "secure-release-automation",
        "description": "CI release automation with supply-chain checks, SBOM generation, policy gates, deployment audit logs, documentation, and production users.",
        "language": "Python",
        "stars": 1300,
        "forks": 170,
        "homepage": "https://example.test/release-automation",
        "topics": ["python", "security", "ci", "devops"],
        "author_commits": 95,
        "other_commits": [],
    },
]


def cache_name(path: str, params: str | None = None) -> str:
    if params:
        return f"gh_githubcache_{path}_{params}.json"
    return f"gh_githubcache_{path}.json"


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def build_fixtures() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    write_json(
        FIXTURE_DIR / cache_name(f"users_{USERNAME}"),
        {
            "login": USERNAME,
            "name": "Max Score Candidate",
            "bio": "GSoC contributor, Girl Script Summer of Code participant, startup co-founder, technical blogger, and maintainer of popular 1000+ star developer tooling projects.",
            "location": "San Francisco, CA",
            "company": "OpenInfra Tools",
            "public_repos": len(REPOS),
            "followers": 2500,
            "following": 120,
            "created_at": "2018-01-01T00:00:00Z",
            "updated_at": "2026-06-01T00:00:00Z",
            "avatar_url": "https://example.test/avatar.png",
            "blog": "https://example.test/max-score/blog",
            "twitter_username": None,
            "hireable": True,
        },
    )

    repo_payload = []
    for index, repo in enumerate(REPOS, start=1):
        repo_payload.append(
            {
                "name": repo["name"],
                "description": repo["description"],
                "html_url": f"https://github.com/{USERNAME}/{repo['name']}",
                "homepage": repo["homepage"],
                "language": repo["language"],
                "fork": False,
                "forks_count": repo["forks"],
                "stargazers_count": repo["stars"],
                "created_at": f"202{index % 4}-01-01T00:00:00Z",
                "updated_at": "2026-06-01T00:00:00Z",
                "topics": repo["topics"],
                "open_issues_count": 2,
                "size": 5000 + index * 400,
                "archived": False,
                "default_branch": "main",
            }
        )
    write_json(
        FIXTURE_DIR
        / cache_name(f"users_{USERNAME}_repos", "per_page_100_sort_updated_type_all"),
        repo_payload,
    )

    for repo in REPOS:
        contributors = [
            {
                "login": USERNAME,
                "id": 1000,
                "type": "User",
                "contributions": repo["author_commits"],
            }
        ]
        for index, commits in enumerate(repo["other_commits"], start=1):
            contributors.append(
                {
                    "login": f"maintainer-{index}",
                    "id": 2000 + index,
                    "type": "User",
                    "contributions": commits,
                }
            )
        write_json(
            FIXTURE_DIR / cache_name(f"repos_{USERNAME}_{repo['name']}_contributors"),
            contributors,
        )


def main() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    source = SOURCE_DIR / "max_score_candidate_v2.txt"
    output = RESUME_DIR / "max_score_candidate_v2.pdf"
    source.write_text(RESUME, encoding="utf-8")
    render(source, output)
    build_fixtures()
    print(f"generated {output.relative_to(ROOT)}")
    print(f"generated {FIXTURE_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
