# Local deployment

This working copy uses the repository's default local model, `llama3.1:8b`, on
Ollama. Python dependencies live in `.venv`; Ollama binaries live in `.tools`;
model blobs live in `.ollama/models`.

## Start the model server

```bash
./scripts/start_ollama.sh
```

The launcher defaults to physical GPU 4 through `CUDA_VISIBLE_DEVICES=4` and
listens only on `127.0.0.1:11434`. Override either variable at launch if needed.
The helper scripts add localhost to `NO_PROXY` and unset the redundant SOCKS
`ALL_PROXY`, while preserving the shell's HTTP/HTTPS proxy for model downloads
and GitHub requests. This avoids an `httpx[socks]` dependency for local calls.

In another terminal, verify the server and model:

```bash
./scripts/ollama.sh list
./scripts/ollama.sh ps
```

The default extraction schema mode is `balanced`, which requires top-level
section keys while still allowing empty optional lists such as awards. Override
with `EXTRACTION_SCHEMA_MODE=original` only when reproducing the upstream
baseline.

## Score a prepared resume

```bash
./scripts/score_resume.sh test_data/generated/baseline_no_github.pdf
```

Development mode is enabled upstream. Results are appended to
`resume_evaluations.csv`, while extraction and GitHub responses are cached under
`cache/`. Delete only the relevant cache file when rerunning a modified sample
under the same filename, or give every experimental PDF a unique filename.

The unauthenticated GitHub API limit is low. To use a token, add
`GITHUB_TOKEN=...` to `.env` or export it in the scoring shell. Never commit the
token.

## Run the controlled GitHub injection samples

The four-sample offline fixture set does not use real GitHub accounts or make
live GitHub requests:

```bash
./scripts/run_github_fixture_matrix.sh candidate_01
```

Omit the candidate argument to run all four candidates. See
`test_data/github_fixture_samples/REPORT.md` for the threat model, sample
provenance, experiment design, and preliminary results.
