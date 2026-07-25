# AIAA4313 Project Version

这是我们课程项目使用的改造版仓库，基于原始 [interviewstreet/hiring-agent](https://github.com/interviewstreet/hiring-agent)。

本项目当前关注：

- LLM 招聘 Agent 的 resume / GitHub 输入注入攻击；
- ranking / scoring 被外部候选人可控文本影响的问题；
- `llama3.1:8b` baseline、prompt hardening、balanced schema、GitHub sanitizer 等攻防配置；
- 课程 Demo 与报告的可复现实验。

组员请优先阅读中文项目说明：[PROJECT_OVERVIEW_CN.md](PROJECT_OVERVIEW_CN.md)。

然后再根据需要阅读具体实验报告：

- **最新完整链路泛化实验（当前主报告，新 Software Developer rubric）**：[FULL_CHAIN_GENERALIZATION_PROBE_NEW_RUBRIC_CN.md](test_data/software_developer_sample_20_ablation/FULL_CHAIN_GENERALIZATION_PROBE_NEW_RUBRIC_CN.md)
- **新 rubric 下的 PDF hidden-span 防御闭环实验（demo 重点）**：[PDF_HIDDEN_SPAN_DEFENSE_PROBE_NEW_RUBRIC_CN.md](test_data/software_developer_sample_20_ablation/PDF_HIDDEN_SPAN_DEFENSE_PROBE_NEW_RUBRIC_CN.md)
- [LLM_INPUT_INJECTION_BASELINE_SUMMARY_CN.md](test_data/github_fixture_samples/LLM_INPUT_INJECTION_BASELINE_SUMMARY_CN.md)
- [LLAMA31_GROUP_PROMPT_ABLATION_AUDIT_CN.md](test_data/software_developer_sample_20_ablation/LLAMA31_GROUP_PROMPT_ABLATION_AUDIT_CN.md)
- 历史旧 rubric 结果：[FULL_CHAIN_GENERALIZATION_PROBE_CN.md](test_data/software_developer_sample_20_ablation/FULL_CHAIN_GENERALIZATION_PROBE_CN.md)

说明：各实验报告末尾会列出对应的原始结果 JSON；例如当前完整链路实验的结果 JSON 位于 [`test_data/software_developer_sample_20_ablation/full_chain_generalization_probe_new_rubric_20260724.json`](test_data/software_developer_sample_20_ablation/full_chain_generalization_probe_new_rubric_20260724.json)。
新 rubric 下 PDF 防御闭环的原始 JSON 位于 [`test_data/software_developer_sample_20_ablation/pdf_hidden_span_defense_probe_new_rubric_20260725.json`](test_data/software_developer_sample_20_ablation/pdf_hidden_span_defense_probe_new_rubric_20260725.json)。

## Web Demo 快速入口

本地 Web Demo 位于 [`web_demo/`](web_demo/)，用于上传 PDF、切换 Ollama/API 模型、执行 Rerun、保存 Evaluation Run，并比较不同实验结果。

新成员请先阅读 [Web Demo 队友快速接入手册](web_demo/README.md)，其中包含：

- Windows 和 macOS/Linux 启动命令；
- 切换 `llama3.1:8b`、Gemma、Qwen 等 Ollama 模型的方法；
- 配置阿里云百炼 DashScope 或其他 OpenAI-compatible API 的方法；
- 如何把自己的 Prompt、Sanitizer 或评分实验适配到 Web Demo；
- 哪些数据和 API Key 不能提交到 GitHub。

Web Demo 默认使用本地 SQLite 和本地文件存储，每位组员可以独立运行自己的模型和实验，不会互相覆盖数据。

---

以下为原项目repo的README：

# Hiring Agent

<p align="center"><strong>Resume-to-Score pipeline</strong> that extracts structured data from PDFs, enriches with GitHub signals, and outputs a fair, explainable evaluation.</p>

<p align="center">
  <a href="https://www.python.org/downloads/release/python-3110/">
    <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue.svg">
  </a>
  <a href="https://github.com/interviewstreet/hiring-agent/blob/master/LICENSE">
    <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-yellow.svg">
  </a>
  <a href="https://github.com/psf/black">
    <img alt="Code style: Black" src="https://img.shields.io/badge/code%20style-Black-000000.svg">
  </a>
</p>

---

## Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation and Setup](#installation-and-setup)
  - [Prerequisites](#prerequisites)
  - [Quick setup with pip](#quick-setup-with-pip)
  - [Ollama models](#ollama-models)
- [Configuration](#configuration)
- [How it works](#how-it-works)
- [CLI usage](#cli-usage)
- [Directory layout](#directory-layout)
- [Provider details](#provider-details)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Hiring Agent parses a resume PDF to Markdown, extracts sectioned JSON using a local or hosted LLM, augments the data with GitHub profile and repository signals, then produces an objective evaluation with category scores, evidence, bonus points, and deductions. You can run fully local with Ollama or use Google Gemini.


---

## Architecture

<table>
<tr>
<td>

**Flow**

1. `pymupdf_rag.py` converts PDF pages to Markdown-like text.
2. `pdf.py` calls the LLM per section using Jinja templates under `prompts/templates`.
3. `github.py` fetches profile and repos, classifies projects, and asks the LLM to select the top 7.
4. `evaluator.py` runs a strict-scored evaluation with fairness constraints.
5. `score.py` orchestrates everything end to end and writes CSV when development mode is on.

</td>
<td>

**Key modules**

- `models.py`
  Pydantic schemas and LLM provider interfaces.

- `llm_utils.py`
  Provider initialization and response cleanup.

- `transform.py`
  Normalization from loose LLM JSON to JSON Resume style.

- `prompts/`
  All Jinja templates for extraction and scoring.

</td>
</tr>
</table>

---

## Installation and Setup

### Prerequisites

- **Python 3.11+**

  The repository pins `.python-version` to 3.11.13.

- **One LLM backend** (either of them)

  - **Ollama** for local models
    Install from the [official site](https://ollama.com/), then run `ollama serve`.
  - **Google Gemini** if you have an API key, get it from [here](https://aistudio.google.com/api-keys).

### Quick setup with pip

```bash
$ git clone https://github.com/interviewstreet/hiring-agent
$ cd hiring-agent

$ python -m venv .venv
# Linux or macOS
$ source .venv/bin/activate
# Windows
# .venv\Scripts\activate

$ pip install -r requirements.txt
```

### Ollama Models

Pull the model you want to use. For example:

```bash
$ ollama pull gemma3:4b
```

If you want different results, you can pull other models such as:

```bash
# For higher system configuration
$ ollama pull gemma3:12b

# For lower system configuration
$ ollama pull gemma3:1b
```

---

## Configuration

Copy the template and set your environment variables.

```bash
$ cp .env.example .env
```

**Environment variables**

| Variable         | Values                                      | Description                                                            |
| ---------------- | ------------------------------------------- | ---------------------------------------------------------------------- |
| `LLM_PROVIDER`   | `ollama` or `gemini`                        | Chooses provider. Defaults to Ollama.                                  |
| `DEFAULT_MODEL`  | for example `gemma3:4b` or `gemini-2.5-pro` | Model name passed to the provider.                                     |
| `GEMINI_API_KEY` | string                                      | Required when `LLM_PROVIDER=gemini`.                                   |
| `GITHUB_TOKEN`   | optional                                    | Inherits from your shell environment, improves GitHub API rate limits. |

Provider mapping lives in `prompt.py` and `models.py`. The `config.py` file has a single flag:

```python
# config.py
DEVELOPMENT_MODE = True  # enables caching and CSV export
```

You can leave it on during iteration. See the next section for details.

---

## How it works

<details>
<summary><b>1) PDF extraction</b></summary>

- `pymupdf_rag.py` and `pdf.py` read the PDF using PyMuPDF and convert pages to Markdown-like text.
- The `to_markdown` routine handles headings, links, tables, and basic formatting.

</details>

<details>
<summary><b>2) Section parsing with templates</b></summary>

- `prompts/templates/*.jinja` define strict instructions for each section
  Basics, Work, Education, Skills, Projects, Awards.
- `pdf.PDFHandler` calls the LLM per section and assembles a `JSONResume` object (see `models.py`).

</details>

<details>
<summary><b>3) GitHub enrichment</b></summary>

- `github.py` extracts a username from the resume profiles, fetches profile and repos, and classifies each project.
- It asks the LLM to select exactly 7 unique projects with a minimum author commit threshold, favoring meaningful contributions.

</details>

<details>
<summary><b>4) Evaluation</b></summary>

- `evaluator.py` uses templates that encode fairness and scoring rules.
- The current project rubric is documented in [`SCORING_RUBRIC.md`](SCORING_RUBRIC.md).
- Scores include `relevant_experience`, `project_system_evidence`, `technical_skills_match`, and `evidence_quality_impact`, plus bonus and deductions, then an explanation for evidence.

</details>

<details>
<summary><b>5) Output and CSV export</b></summary>

- `score.py` prints a readable summary to stdout.
- When `DEVELOPMENT_MODE=True` it creates or appends a `resume_evaluations.csv` with key fields, and caches intermediate JSON under `cache/`.

</details>

---

## CLI usage

### End to end scoring

Provide a path to a resume PDF.

```bash
$ python score.py /path/to/resume.pdf
```

What happens:

1. If development mode is on, the PDF extraction result is cached to `cache/resumecache_<basename>.json`.
2. If a GitHub profile is found in the resume, repositories are fetched and cached to `cache/githubcache_<basename>.json`.
3. The evaluator prints a report and, in development mode, appends a CSV row to `resume_evaluations.csv`.

---

## Directory layout

```text
.
├── .env.example
├── .python-version
├── config.py
├── evaluator.py
├── github.py
├── llm_utils.py
├── models.py
├── pdf.py
├── prompt.py
├── prompts/
│   ├── template_manager.py
│   └── templates/
│       ├── awards.jinja
│       ├── basics.jinja
│       ├── education.jinja
│       ├── github_project_selection.jinja
│       ├── projects.jinja
│       ├── resume_evaluation_criteria.jinja
│       ├── resume_evaluation_system_message.jinja
│       ├── skills.jinja
│       ├── system_message.jinja
│       └── work.jinja
├── pymupdf_rag.py
├── requirements.txt
├── score.py
└── transform.py
```

---

## Provider details

### Ollama

- Set `LLM_PROVIDER=ollama`
- Set `DEFAULT_MODEL` to any pulled model, for example `gemma3:4b`
- The provider wrapper in `models.OllamaProvider` calls `ollama.chat`

### Gemini

- Set `LLM_PROVIDER=gemini`
- Set `DEFAULT_MODEL` to a supported Gemini model, for example `gemini-2.0-flash`
- Provide `GEMINI_API_KEY`
- The wrapper in `models.GeminiProvider` adapts responses to a unified format

---

## Contributing

Please read the [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines on filing issues, proposing changes, and submitting pull requests. Key principles include:

- Keep prompts declarative and provider-agnostic.
- Validate changes with a couple of real resumes under different providers.
- Add or adjust unit-free smoke tests that call each stage with minimal inputs.

---


## License

[MIT](https://github.com/interviewstreet/hiring-agent/blob/master/LICENSE) © HackerRank
