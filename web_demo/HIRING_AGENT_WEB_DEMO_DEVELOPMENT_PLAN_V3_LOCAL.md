# Development Progress

## Baseline

- Baseline commit: `4db8655` (recorded 2026-07-23).
- Existing CLI and experimental assets were preserved. Pre-existing edits in the repository were not changed.
- Visual reference: `templates/hiring_agent_glass_editorial_template.html`.

## Delivered local demo slice

- FastAPI server with SQLite persistence and local UUID-based PDF storage.
- Server-enforced candidate/staff sessions, PDF validation, staff rerun, default-model setting, stage/artifact records, and demo reset.
- Request-scoped `PipelineConfig`, deterministic configuration fingerprinting, real PyMuPDF extraction, structured resume data, evidence, and immutable evaluation runs.
- When the selected local Gemma model is reachable, evaluation calls Ollama; DeepSeek uses only server-side `.env` configuration. Provider failures are recorded in evidence and fall back to a deterministic local evaluator so classroom testing remains available offline.
- The approved Glass Editorial template remains the UI; staff views hydrate their application and model data from SQLite after login.
- A Next.js route shell now owns `/login`, `/candidate`, and `/staff/*`, proxies `/api` to FastAPI, and loads the approved template through a same-origin route so its visual baseline is preserved.
- Alembic revision `0001_local_demo_schema` is applied during local startup.
- Local startup and readiness scripts plus a tester-facing README.

## Verification

- Python compilation succeeded for `web_demo`.
- FastAPI tests: staff login, application listing, candidate/staff authorization, valid PDF upload, real background PDF evaluation, stage persistence, and non-PDF rejection all passed.
- `npm run build` succeeded for the Next.js frontend.
- Browser regression confirmed that `http://127.0.0.1:3000/login` loads the approved template in its Next.js route shell with no horizontal overflow.
- Unit/API regression suite: 6 tests passed, including candidate privacy, reset isolation, PDF processing, Safe Reuse, artifact access, score cap and fingerprint stability.
- `verify_local.py` passed with FastAPI, Next.js, Alembic, local storage, seed users/applications, and a completed run available.
- Desktop (1440 × 900) and candidate-mobile (390 × 844) browser checks passed with no horizontal page overflow.

## Remaining integration work

- The legacy CLI is intentionally preserved and is not invoked by the web adapter; the web pipeline is request-scoped to avoid global-model contamination.
- The supplied template remains a single visual source loaded within the Next.js shell; replacing its internal imperative state with native React components and TanStack Query remains a future visual-regression-preserving refactor.
