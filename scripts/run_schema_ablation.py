#!/usr/bin/env python3
"""Run a small schema-strictness ablation for PDF section extraction.

The script compares the project's original Pydantic schemas with stricter
schemas that require the target top-level section key and non-empty core lists.
It intentionally calls only selected sections for a small set of samples so the
experiment stays fast enough for interactive iteration.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from llm_utils import extract_json_from_response
from models import (
    AwardsSection,
    Basics,
    BasicsSection,
    Education,
    EducationSection,
    Project,
    ProjectsSection,
    Skill,
    SkillsSection,
    Work,
    WorkSection,
)
from pdf import PDFHandler
from prompt import DEFAULT_MODEL, MODEL_PARAMETERS


SAMPLE_DIR = ROOT / "test_data" / "github_fixture_samples"
RESUME_DIR = SAMPLE_DIR / "resumes"
OUT_JSON = SAMPLE_DIR / "schema_ablation_results.json"
OUT_MD = SAMPLE_DIR / "SCHEMA_ABLATION_RESULTS_CN.md"


class StrictSkill(BaseModel):
    name: str
    level: Optional[str] = None
    keywords: List[str] = Field(min_length=1)


class StrictWork(BaseModel):
    name: str
    position: str
    url: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    summary: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)


class StrictEducation(BaseModel):
    institution: str
    url: Optional[str] = None
    area: Optional[str] = None
    studyType: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    score: Optional[str] = None
    courses: List[str] = Field(default_factory=list)


class StrictProject(BaseModel):
    name: str
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    description: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)
    url: Optional[str] = None


class StrictAward(BaseModel):
    title: str
    date: Optional[str] = None
    awarder: Optional[str] = None
    summary: Optional[str] = None


class StrictBasicsSection(BaseModel):
    basics: Basics


class StrictWorkSection(BaseModel):
    work: List[StrictWork] = Field(min_length=1)


class StrictEducationSection(BaseModel):
    education: List[StrictEducation] = Field(min_length=1)


class StrictSkillsSection(BaseModel):
    skills: List[StrictSkill] = Field(min_length=1)


class StrictProjectsSection(BaseModel):
    projects: List[StrictProject] = Field(min_length=1)


class StrictAwardsSection(BaseModel):
    # Awards are optional in the project pipeline, but require the top-level key
    # so `{}` is no longer a valid structured output for this section.
    awards: List[StrictAward]


ORIGINAL_SCHEMAS: Dict[str, Type[BaseModel]] = {
    "basics": BasicsSection,
    "work": WorkSection,
    "education": EducationSection,
    "skills": SkillsSection,
    "projects": ProjectsSection,
    "awards": AwardsSection,
}

STRICT_SCHEMAS: Dict[str, Type[BaseModel]] = {
    "basics": StrictBasicsSection,
    "work": StrictWorkSection,
    "education": StrictEducationSection,
    "skills": StrictSkillsSection,
    "projects": StrictProjectsSection,
    "awards": StrictAwardsSection,
}

CASES = [
    {
        "sample": "short_candidate_02.pdf",
        "label": "clean baseline",
        "sections": ["work", "skills", "projects"],
    },
    {
        "sample": "short_candidate_02_rubric_project_injection.pdf",
        "label": "rubric language before skills; previous skills failure",
        "sections": ["skills"],
    },
    {
        "sample": "candidate_01_visible_descriptive_repeated.pdf",
        "label": "repeated visible self-praise; previous work failure",
        "sections": ["work"],
    },
    {
        "sample": "candidate_01_visible_instructive_single.pdf",
        "label": "visible direct instruction; previous awards failure",
        "sections": ["awards"],
    },
    {
        "sample": "short_candidate_02_matrix_capstone_pilot.pdf",
        "label": "natural matrix sample; previous intermittent skills failure",
        "sections": ["skills"],
    },
]


def call_section(
    handler: PDFHandler,
    text: str,
    section: str,
    schema_model: Type[BaseModel],
) -> Dict[str, Any]:
    prompt = handler.template_manager.render_template(section, text_content=text)
    system_message = handler.template_manager.render_template(
        "system_message", section_name_param=section
    )
    model_params = MODEL_PARAMETERS.get(DEFAULT_MODEL, {"temperature": 0.1, "top_p": 0.9})
    started_at = time.time()
    result: Dict[str, Any] = {
        "section": section,
        "schema": schema_model.__name__,
        "ok_json": False,
        "ok_business": False,
        "has_target_key": False,
        "target_len": None,
        "raw": None,
        "parsed": None,
        "error": None,
        "elapsed_sec": None,
    }

    try:
        response = handler.provider.chat(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            options={
                "stream": False,
                "temperature": model_params["temperature"],
                "top_p": model_params["top_p"],
            },
            format=schema_model.model_json_schema(),
        )
        raw = response["message"]["content"]
        result["raw"] = raw
        cleaned = extract_json_from_response(raw)
        parsed = json.loads(cleaned)
        result["ok_json"] = True
        result["parsed"] = parsed
        if isinstance(parsed, dict):
            result["has_target_key"] = section in parsed
            value = parsed.get(section)
            if isinstance(value, list):
                result["target_len"] = len(value)
                result["ok_business"] = section == "awards" or len(value) > 0
            elif value is not None:
                result["ok_business"] = True
    except Exception as exc:  # noqa: BLE001 - experiment should record failures
        result["error"] = repr(exc)
    finally:
        result["elapsed_sec"] = round(time.time() - started_at, 2)

    return result


def summarize_raw(raw: Optional[str], limit: int = 180) -> str:
    if raw is None:
        return ""
    compact = " ".join(raw.split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def write_markdown(results: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Schema 收紧消融实验结果")
    lines.append("")
    lines.append(f"模型：`{results['model']}`")
    lines.append("")
    lines.append("## 实验目的")
    lines.append("")
    lines.append(
        "比较原版 Optional schema 和收紧 schema 对 PDF section extraction 的影响，重点观察原版是否会返回 `{}`，以及收紧后是恢复有效抽取还是转成其他失败。"
    )
    lines.append("")
    lines.append("收紧 schema 的主要变化：")
    lines.append("")
    lines.append("- top-level section key 必须出现，例如必须有 `skills`；")
    lines.append("- `work` / `education` / `skills` / `projects` 要求非空列表；")
    lines.append("- `skills[*].name` 和 `skills[*].keywords` 必填；")
    lines.append("- `awards` 仍允许空列表，但不允许直接 `{}`。")
    lines.append("")
    lines.append("## 结果总表")
    lines.append("")
    lines.append("| 样本 | Section | 原版结果 | 原版 raw 摘要 | 收紧结果 | 收紧 raw 摘要 |")
    lines.append("|---|---|---|---|---|---|")
    for row in results["rows"]:
        original = row["original"]
        strict = row["strict"]
        original_status = status_text(original)
        strict_status = status_text(strict)
        lines.append(
            "| "
            + row["sample"]
            + " | `"
            + row["section"]
            + "` | "
            + original_status
            + " | `"
            + summarize_raw(original.get("raw"))
            + "` | "
            + strict_status
            + " | `"
            + summarize_raw(strict.get("raw"))
            + "` |"
        )
    lines.append("")
    lines.append("## 初步观察")
    lines.append("")
    lines.append("1. 原版 schema 的 `{}` 失败确实可复现：在若干历史失败 section 上，原版 structured output 会直接返回空对象。")
    lines.append("2. 收紧 schema 能阻止 `{}` 作为合法输出；模型被迫生成带目标 key 的 JSON。")
    lines.append("3. 收紧 schema 不等价于语义正确。它可能恢复有效抽取，也可能诱导模型生成空列表、低质量字段或幻觉字段。")
    lines.append("4. 因此 schema 收紧适合作为防御的一部分，但不能单独作为完整防御；还需要 evidence check、业务校验和 retry。")
    lines.append("")
    lines.append("## 对项目展示的含义")
    lines.append("")
    lines.append("- 可以把原版 `{}` 失败解释为宽松 schema 造成的 parser availability 问题。")
    lines.append("- 可以把收紧 schema 展示为一个低成本防御：减少空输出，让失败更显式。")
    lines.append("- 但最终报告应强调：schema 只约束格式，不验证事实；对 GitHub metadata injection 仍然需要不可信文本隔离和 evidence-grounded scoring。")
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def status_text(result: Dict[str, Any]) -> str:
    if result.get("error"):
        return "ERR"
    if not result.get("ok_json"):
        return "non-JSON"
    if not result.get("has_target_key"):
        return "JSON but missing key"
    target_len = result.get("target_len")
    if target_len is not None:
        if result.get("ok_business"):
            return f"OK len={target_len}"
        return f"empty len={target_len}"
    return "OK"


def main() -> None:
    handler = PDFHandler()
    rows: List[Dict[str, Any]] = []

    for case in CASES:
        pdf_path = RESUME_DIR / case["sample"]
        text = handler.extract_text_from_pdf(str(pdf_path))
        if text is None:
            raise RuntimeError(f"Failed to extract text from {pdf_path}")
        for section in case["sections"]:
            original = call_section(handler, text, section, ORIGINAL_SCHEMAS[section])
            strict = call_section(handler, text, section, STRICT_SCHEMAS[section])
            rows.append(
                {
                    "sample": case["sample"],
                    "label": case["label"],
                    "section": section,
                    "original": original,
                    "strict": strict,
                }
            )

    payload = {
        "model": DEFAULT_MODEL,
        "cases": CASES,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(payload)
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
