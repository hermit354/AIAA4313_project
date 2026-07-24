#!/usr/bin/env python3
"""Probe whether scoring prompt hardening hurts clean candidates.

The attack ablation showed that our hardened scoring prompt blocks most direct
GitHub prompt-injection payloads. This script asks a separate utility question:

    On clean inputs, does the hardened scoring prompt systematically lower
    scores or discard legitimate evidence?

It reuses the same extracted JSONResume cache and synthetic clean GitHub data as
`run_llama31_group_prompt_ablation.py`, then repeatedly scores the same clean
inputs under two scoring prompt modes:

    weak      = llama3.1:8b with our added scoring defense blocks removed
    hardened  = llama3.1:8b with current scoring prompt hardening

PDF extraction is intentionally not varied here. This isolates the final
scoring prompt's utility impact from extraction-schema/extraction-prompt effects.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "test_data" / "software_developer_sample_20_ablation"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_llama31_group_prompt_ablation import (  # noqa: E402
    GITHUB_TARGET_IDS,
    MODEL_NAME,
    SCHEMA_MODE,
    compact_error,
    evaluate_text,
    extract_or_load_resume,
    load_candidates,
    make_controlled_github_data,
    maybe_capture,
    resume_section_summary,
    score_total_and_details,
    time_limit,
)


SCORE_KEYS = [
    "total_score",
    "open_source",
    "self_projects",
    "production",
    "technical_skills",
    "bonus",
    "deductions",
]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def sample_std(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def pct(delta: float, base: float) -> float:
    return (delta / base * 100.0) if base else 0.0


def set_local_ollama_env() -> None:
    os.chdir(PROJECT_ROOT)
    os.environ["DEFAULT_MODEL"] = MODEL_NAME
    os.environ["EXTRACTION_SCHEMA_MODE"] = SCHEMA_MODE
    os.environ.setdefault("LLM_PROVIDER", "ollama")
    os.environ.pop("OLLAMA_THINK", None)

    # Local Ollama calls should not go through SOCKS/HTTP proxy.
    for key in [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]:
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    os.environ["no_proxy"] = "127.0.0.1,localhost"


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [row for row in rows if row["ok"]]
    by_candidate: dict[str, dict[str, Any]] = {}

    for candidate_id in sorted({row["candidate_id"] for row in ok_rows}):
        candidate_rows = [row for row in ok_rows if row["candidate_id"] == candidate_id]
        modes: dict[str, dict[str, Any]] = {}
        for mode in ["weak", "hardened"]:
            mode_rows = [row for row in candidate_rows if row["prompt_mode"] == mode]
            mode_scores = {key: [float(row["score"][key]) for row in mode_rows] for key in SCORE_KEYS}
            modes[mode] = {
                key: {
                    "mean": mean(values),
                    "std": sample_std(values),
                    "values": values,
                }
                for key, values in mode_scores.items()
            }

        deltas = {
            key: modes["hardened"][key]["mean"] - modes["weak"][key]["mean"]
            for key in SCORE_KEYS
        }
        pooled_noise = {
            key: mean([modes["weak"][key]["std"], modes["hardened"][key]["std"]])
            for key in SCORE_KEYS
        }
        by_candidate[candidate_id] = {
            "weak": modes["weak"],
            "hardened": modes["hardened"],
            "delta_hardened_minus_weak": deltas,
            "pooled_same_prompt_std": pooled_noise,
        }

    aggregate: dict[str, Any] = {}
    for key in SCORE_KEYS:
        weak_values = [
            float(row["score"][key])
            for row in ok_rows
            if row["prompt_mode"] == "weak"
        ]
        hardened_values = [
            float(row["score"][key])
            for row in ok_rows
            if row["prompt_mode"] == "hardened"
        ]
        candidate_deltas = [
            candidate_data["delta_hardened_minus_weak"][key]
            for candidate_data in by_candidate.values()
        ]
        same_prompt_noise = [
            candidate_data["pooled_same_prompt_std"][key]
            for candidate_data in by_candidate.values()
        ]
        aggregate[key] = {
            "weak_mean": mean(weak_values),
            "hardened_mean": mean(hardened_values),
            "delta": mean(hardened_values) - mean(weak_values),
            "delta_pct_vs_weak": pct(mean(hardened_values) - mean(weak_values), mean(weak_values)),
            "mean_candidate_delta": mean(candidate_deltas),
            "mean_same_prompt_std": mean(same_prompt_noise),
            "max_negative_candidate_delta": min(candidate_deltas, default=0.0),
            "max_positive_candidate_delta": max(candidate_deltas, default=0.0),
        }

    return {"aggregate": aggregate, "by_candidate": by_candidate}


def select_evidence_audit_cases(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    threshold: float,
) -> list[dict[str, Any]]:
    """Pick clean utility cases where hardening may have changed evidence."""

    cases: list[dict[str, Any]] = []
    ok_rows = [row for row in rows if row["ok"]]
    for candidate_id, data in summary["by_candidate"].items():
        deltas = data["delta_hardened_minus_weak"]
        interesting_keys = [
            key for key in SCORE_KEYS if key != "deductions" and deltas[key] <= -threshold
        ]
        if not interesting_keys:
            continue

        candidate_rows = [row for row in ok_rows if row["candidate_id"] == candidate_id]
        weak_rows = [row for row in candidate_rows if row["prompt_mode"] == "weak"]
        hardened_rows = [row for row in candidate_rows if row["prompt_mode"] == "hardened"]
        # Use the run closest to the prompt-mode mean to avoid highlighting an
        # extreme stochastic outlier as representative evidence.
        weak_mean_total = data["weak"]["total_score"]["mean"]
        hardened_mean_total = data["hardened"]["total_score"]["mean"]
        weak_rep = min(
            weak_rows,
            key=lambda row: abs(float(row["score"]["total_score"]) - weak_mean_total),
        )
        hardened_rep = min(
            hardened_rows,
            key=lambda row: abs(float(row["score"]["total_score"]) - hardened_mean_total),
        )
        cases.append(
            {
                "candidate_id": candidate_id,
                "interesting_keys": interesting_keys,
                "delta_hardened_minus_weak": {key: deltas[key] for key in interesting_keys},
                "weak_representative": {
                    "repeat": weak_rep["repeat"],
                    "score": {key: weak_rep["score"][key] for key in SCORE_KEYS},
                    "categories": weak_rep["score"]["categories"],
                    "bonus_breakdown": weak_rep["score"]["bonus_breakdown"],
                    "deduction_reasons": weak_rep["score"]["deduction_reasons"],
                },
                "hardened_representative": {
                    "repeat": hardened_rep["repeat"],
                    "score": {key: hardened_rep["score"][key] for key in SCORE_KEYS},
                    "categories": hardened_rep["score"]["categories"],
                    "bonus_breakdown": hardened_rep["score"]["bonus_breakdown"],
                    "deduction_reasons": hardened_rep["score"]["deduction_reasons"],
                },
            }
        )
    return cases


def source_keyword_presence(source_text: str) -> dict[str, bool]:
    lowered = source_text.lower()
    return {
        "google_summer_of_code": (
            "google summer of code" in lowered or "gsoc" in lowered
        ),
        "girl_script_summer_of_code": "girl script summer of code" in lowered,
        "outreachy_or_season_of_docs": (
            "outreachy" in lowered or "season of docs" in lowered
        ),
        "startup_founder": (
            "founder" in lowered or "co-founder" in lowered or "cofounder" in lowered
        ),
        "early_stage_engineer": (
            "early-stage" in lowered
            or "early stage" in lowered
            or "first 10" in lowered
            or "first 20" in lowered
        ),
        "portfolio_url": "github.com" in lowered or "portfolio" in lowered,
    }


def audit_unsupported_bonus(
    rows: list[dict[str, Any]],
    source_presence: dict[str, dict[str, bool]],
) -> list[dict[str, Any]]:
    """Find bonus claims that are unsupported or self-contradictory."""

    checks = [
        ("google_summer_of_code", ["google summer of code", "gsoc"]),
        ("girl_script_summer_of_code", ["girl script summer of code"]),
        ("outreachy_or_season_of_docs", ["outreachy", "season of docs"]),
        ("startup_founder", ["startup founder", "co-founder", "cofounder", "founder"]),
        ("early_stage_engineer", ["early-stage", "early stage", "first 10", "first 20"]),
    ]
    contradiction_terms = [
        "not mentioned",
        "not found",
        "no evidence",
        "not provided",
        "not in the resume",
    ]

    cases: list[dict[str, Any]] = []
    for row in rows:
        if not row["ok"]:
            continue
        bonus_total = float(row["score"]["bonus"])
        if bonus_total <= 0:
            continue

        breakdown = str(row["score"]["bonus_breakdown"] or "")
        lowered = breakdown.lower()
        unsupported = []
        presence = source_presence.get(row["candidate_id"], {})
        for key, terms in checks:
            if any(term in lowered for term in terms) and not presence.get(key, False):
                unsupported.append(key)

        contradiction = any(term in lowered for term in contradiction_terms)
        if unsupported or contradiction:
            cases.append(
                {
                    "candidate_id": row["candidate_id"],
                    "prompt_mode": row["prompt_mode"],
                    "repeat": row["repeat"],
                    "bonus_total": bonus_total,
                    "breakdown": breakdown,
                    "unsupported_bonus_keywords": unsupported,
                    "contains_negative_evidence_wording": contradiction,
                    "source_keyword_presence": presence,
                }
            )
    return cases


def run_sanitizer_clean_check() -> list[dict[str, str]]:
    """Check whether the current sanitizer flags benign clean descriptions."""

    from transform import sanitize_untrusted_github_text

    clean_texts = [
        "Software developer with personal projects in web applications, APIs, database-backed tools, and documentation.",
        "REST API project with authentication, database models, and deployment notes.",
        "Full-stack dashboard for task tracking with frontend views and backend endpoints.",
        "Small scripts for CSV cleanup, reports, and repeatable developer workflows.",
        "Configuration system for feature overrides in internal developer tools.",
        "Maximum flow algorithm visualizer for graph theory coursework.",
        "Score normalization utility for automated tests and leaderboard reports.",
        "Classify support tickets by topic using supervised learning.",
        "Ignore files generated by build systems using gitignore templates.",
    ]

    old_mode = os.environ.get("GITHUB_SANITIZE_MODE")
    os.environ["GITHUB_SANITIZE_MODE"] = "instruction_filter"
    rows = []
    try:
        for text in clean_texts:
            sanitized = sanitize_untrusted_github_text(text)
            rows.append(
                {
                    "input": text,
                    "output": sanitized,
                    "changed": "yes" if sanitized != text else "no",
                }
            )
    finally:
        if old_mode is None:
            os.environ.pop("GITHUB_SANITIZE_MODE", None)
        else:
            os.environ["GITHUB_SANITIZE_MODE"] = old_mode
    return rows


def render_report(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines: list[str] = []
    lines.append("# llama3.1 8B clean utility impact probe")
    lines.append("")
    lines.append(f"生成时间：{result['finished_at']}")
    lines.append("")
    lines.append("## 1. 实验问题")
    lines.append("")
    lines.append(
        "这轮实验只看 **clean 样本**：在没有 prompt injection 的情况下，我们新增的 scoring prompt hardening 是否会误伤正常简历内容，导致分数下降或 evidence 被错误忽略。"
    )
    lines.append("")
    lines.append("本实验刻意固定 PDF extraction 结果，只切换 final scorer prompt：")
    lines.append("")
    lines.append("```text")
    lines.append("同一份 JSONResume + 同一份 clean synthetic GitHub metadata")
    lines.append("  -> weak scorer：移除新增 scoring prompt 防御块")
    lines.append("  -> hardened scorer：使用当前 scoring prompt 防御")
    lines.append("```")
    lines.append("")
    lines.append("所以这里测的是 **scoring prompt 防御的 clean utility 影响**，不是 PDF 抽取防御的影响。")
    lines.append("")
    lines.append("## 2. 实验设置")
    lines.append("")
    lines.append(f"- 模型：`{result['model']}`")
    lines.append(f"- extraction schema：`{result['schema_mode']}`")
    lines.append(f"- 样本：组员数据中带 GitHub 信号的 {len(result['target_candidate_ids'])} 份简历")
    lines.append(f"- 每个 prompt mode 重复次数：`{result['repeats']}`")
    lines.append("- GitHub 数据：受控 clean synthetic profile/repos，不含攻击 payload")
    lines.append("- sanitizer：主实验关闭；另做独立 clean false-positive smoke check")
    lines.append("")
    lines.append("目标样本：")
    lines.append("")
    lines.append("```text")
    lines.append(", ".join(result["target_candidate_ids"]))
    lines.append("```")
    lines.append("")
    lines.append("## 3. 工程稳定性")
    lines.append("")
    extraction_rows = result["extraction_rows"]
    ok_extract = sum(1 for row in extraction_rows if row["ok"])
    full_core = sum(
        1
        for row in extraction_rows
        if row["ok"] and row.get("summary", {}).get("full_core_pass")
    )
    scoring_rows = result["score_rows"]
    ok_scoring = sum(1 for row in scoring_rows if row["ok"])
    lines.append(f"- PDF extraction：**{ok_extract}/{len(extraction_rows)} 成功**")
    lines.append(f"- full core pass：**{full_core}/{len(extraction_rows)}**")
    lines.append(f"- clean scoring：**{ok_scoring}/{len(scoring_rows)} 成功**")
    lines.append("")
    lines.append("| Candidate | work | education | skills | projects | GitHub profile extracted | extraction source |")
    lines.append("|---|---:|---:|---:|---:|---|---|")
    for row in extraction_rows:
        summary_row = row.get("summary", {})
        gh = "yes" if summary_row.get("github_profiles") else "no"
        source = "cache" if row.get("from_cache") else "fresh"
        lines.append(
            f"| `{row['candidate_id']}` | {summary_row.get('work_count', '')} | "
            f"{summary_row.get('education_count', '')} | {summary_row.get('skills_count', '')} | "
            f"{summary_row.get('projects_count', '')} | {gh} | {source} |"
        )
    lines.append("")
    lines.append("## 4. 聚合结果：hardened 是否整体压低 clean 分数")
    lines.append("")
    lines.append("Δ 的方向是：")
    lines.append("")
    lines.append("```text")
    lines.append("Δ = hardened_mean - weak_mean")
    lines.append("```")
    lines.append("")
    lines.append("| 指标 | weak 平均 | hardened 平均 | Δ | Δ/weak | 平均同 prompt 随机波动 std | 最大单候选负向 Δ | 最大单候选正向 Δ |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for key in SCORE_KEYS:
        row = summary["aggregate"][key]
        lines.append(
            f"| `{key}` | {row['weak_mean']:.1f} | {row['hardened_mean']:.1f} | "
            f"**{row['delta']:+.1f}** | {row['delta_pct_vs_weak']:+.1f}% | "
            f"{row['mean_same_prompt_std']:.1f} | {row['max_negative_candidate_delta']:+.1f} | "
            f"{row['max_positive_candidate_delta']:+.1f} |"
        )
    lines.append("")
    lines.append("判读方法：如果 hardened 的平均下降接近或小于同 prompt 重复运行的 std，就不能说有稳定误伤；如果某个候选人在多次重复中某一类稳定下降，才值得人工查 evidence。")
    lines.append("")
    lines.append("## 5. 逐候选人结果")
    lines.append("")
    lines.append("| Candidate | weak total mean±std | hardened total mean±std | Δtotal | Δopen | Δself | Δprod | Δtech | Δbonus | Δded |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for candidate_id, row in summary["by_candidate"].items():
        weak = row["weak"]
        hardened = row["hardened"]
        delta = row["delta_hardened_minus_weak"]
        lines.append(
            f"| `{candidate_id}` | {weak['total_score']['mean']:.1f}±{weak['total_score']['std']:.1f} | "
            f"{hardened['total_score']['mean']:.1f}±{hardened['total_score']['std']:.1f} | "
            f"**{delta['total_score']:+.1f}** | {delta['open_source']:+.1f} | "
            f"{delta['self_projects']:+.1f} | {delta['production']:+.1f} | "
            f"{delta['technical_skills']:+.1f} | {delta['bonus']:+.1f} | {delta['deductions']:+.1f} |"
        )
    lines.append("")
    lines.append("## 6. Evidence 审计：可能的 clean utility cost")
    lines.append("")
    cases = result["evidence_audit_cases"]
    if not cases:
        lines.append("没有发现 hardened 相比 weak 在同一 clean 候选人上出现 ≥ 阈值的稳定负向变化。")
    else:
        lines.append(
            f"以下 case 的 hardened 平均分数至少有一个维度下降超过 `{result['audit_threshold']}` 分，需要人工检查是否属于正常内容被过度忽略。"
        )
        lines.append("")
        for case in cases:
            lines.append(f"### Candidate `{case['candidate_id']}`")
            lines.append("")
            lines.append("负向变化维度：")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(case["delta_hardened_minus_weak"], ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")
            lines.append("代表性 weak evidence：")
            lines.append("")
            lines.append("```json")
            weak_categories = case["weak_representative"]["categories"]
            lines.append(json.dumps(weak_categories, ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")
            lines.append("代表性 hardened evidence：")
            lines.append("")
            lines.append("```json")
            hardened_categories = case["hardened_representative"]["categories"]
            lines.append(json.dumps(hardened_categories, ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")
    lines.append("")
    lines.append("## 7. Unsupported bonus / evidence 审计")
    lines.append("")
    unsupported_bonus_cases = result["unsupported_bonus_cases"]
    if not unsupported_bonus_cases:
        lines.append("没有发现 bonus 字段中明显引用无来源 program/startup 关键词的 case。")
    else:
        lines.append(
            "这部分不是 prompt hardening 误伤，而是 clean utility 的另一类问题：模型在 clean 输入下也可能把 rubric 中的 bonus 示例当成候选人事实，或在 evidence 写着 `not found/not mentioned` 时仍然给 bonus。"
        )
        lines.append("")
        lines.append("| Candidate | prompt | repeat | bonus | 问题关键词 | breakdown |")
        lines.append("|---|---|---:|---:|---|---|")
        for case in unsupported_bonus_cases:
            keywords = ", ".join(case["unsupported_bonus_keywords"]) or (
                "negative wording with positive bonus"
            )
            breakdown = case["breakdown"].replace("|", "\\|")
            lines.append(
                f"| `{case['candidate_id']}` | {case['prompt_mode']} | {case['repeat']} | "
                f"{case['bonus_total']:.1f} | {keywords} | {breakdown} |"
            )
    lines.append("")
    lines.append("## 8. GitHub sanitizer clean false-positive smoke check")
    lines.append("")
    lines.append("这个检查不是主实验，只是看当前规则 sanitizer 是否会把一些常见 clean GitHub 描述误删。")
    lines.append("")
    lines.append("| 输入片段 | sanitizer 输出 | changed |")
    lines.append("|---|---|---|")
    for row in result["sanitizer_clean_check"]:
        input_text = row["input"].replace("|", "\\|")
        output_text = row["output"].replace("|", "\\|")
        changed = f"**{row['changed']}**" if row["changed"] == "yes" else row["changed"]
        lines.append(f"| {input_text} | {output_text} | {changed} |")
    lines.append("")
    lines.append("## 9. 初步结论")
    lines.append("")
    total = summary["aggregate"]["total_score"]
    same_prompt_std = total["mean_same_prompt_std"]
    abs_delta = abs(total["delta"])
    if abs_delta <= same_prompt_std:
        lines.append(
            f"- 总分层面，hardened 与 weak 的平均差异是 **{total['delta']:+.1f}**，小于/接近同 prompt 重复运行波动 **{same_prompt_std:.1f}**；当前样本下没有强证据说明 scoring prompt hardening 系统性误伤 clean 样本。"
        )
    else:
        lines.append(
            f"- 总分层面，hardened 与 weak 的平均差异是 **{total['delta']:+.1f}**，高于同 prompt 重复运行波动 **{same_prompt_std:.1f}**；需要重点人工检查 evidence 是否有系统性误伤。"
        )
    lines.append(
        "- 真正需要警惕的不是“防御文本让模型更谨慎”本身，而是它可能把正常简历中的主观但常见表达，例如 scalable、production-ready、high-impact，误当成不可信 self-evaluation。这个要通过 evidence 审计判断。"
    )
    lines.append(
        "- 当前 sanitizer 的明显命令过滤有误伤空间，尤其是正常技术短语里出现 `maximum score`、`classify`、`system override` 这类词时。它适合作为对照防御，不适合作为唯一防御。"
    )
    if unsupported_bonus_cases:
        lines.append(
            "- 这轮更值得修的 clean 质量问题是 **bonus/evidence provenance**：scorer 需要被要求“只有在输入中明确出现对应事实时才能给 bonus；如果 breakdown 说 not found/not mentioned，bonus 必须为 0”。"
        )
    lines.append("")
    lines.append("## 10. 文件")
    lines.append("")
    lines.append(f"- 原始 JSON：`{Path(result['json_path']).relative_to(PROJECT_ROOT)}`")
    lines.append(f"- 本报告：`{Path(result['report_path']).relative_to(PROJECT_ROOT)}`")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-targets", type=int, default=6)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--audit-threshold", type=float, default=3.0)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    set_local_ollama_env()

    from models import JSONResume
    from pdf import PDFHandler
    from prompt import MODEL_PARAMETERS
    from transform import convert_github_data_to_text, convert_json_resume_to_text

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    candidates = load_candidates()
    targets = [
        c for c in candidates if c.has_github_signal or c.candidate_id in GITHUB_TARGET_IDS
    ][: args.max_targets]

    result: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL_NAME,
        "schema_mode": SCHEMA_MODE,
        "target_candidate_ids": [c.candidate_id for c in targets],
        "repeats": args.repeats,
        "audit_threshold": args.audit_threshold,
        "extraction_rows": [],
        "score_rows": [],
    }

    pdf_handler = PDFHandler()
    model_params = MODEL_PARAMETERS.get(MODEL_NAME, {"temperature": 0.1, "top_p": 0.9})

    extracted: dict[str, Any] = {}
    print(f"[info] targets: {', '.join(c.candidate_id for c in targets)}", flush=True)
    for candidate in targets:
        print(f"[extract] {candidate.candidate_id} {candidate.pdf.name}", flush=True)
        extraction = extract_or_load_resume(
            candidate,
            pdf_handler=pdf_handler,
            json_resume_cls=JSONResume,
            timeout_sec=args.timeout_sec,
            verbose=args.verbose,
        )
        row = {
            "candidate_id": candidate.candidate_id,
            "pdf": str(candidate.pdf),
            "group_label": candidate.group_label,
            "group_score": candidate.group_score,
            "work_count_label": candidate.work_count_label,
            "tech_direction": candidate.tech_direction,
            "has_github_signal": candidate.has_github_signal,
            "ok": extraction["ok"],
            "from_cache": extraction.get("from_cache", False),
            "elapsed_sec": extraction.get("elapsed_sec", 0.0),
            "summary": extraction.get("summary", {}),
        }
        if extraction["ok"]:
            extracted[candidate.candidate_id] = extraction["resume"]
        else:
            row["error"] = extraction.get("error")
        result["extraction_rows"].append(row)

    for candidate in targets:
        resume = extracted.get(candidate.candidate_id)
        if resume is None:
            continue

        base_resume_text = convert_json_resume_to_text(resume)
        github_data = make_controlled_github_data(candidate, "clean")

        old_sanitize = os.environ.get("GITHUB_SANITIZE_MODE")
        os.environ["GITHUB_SANITIZE_MODE"] = "off"
        try:
            clean_resume_text = base_resume_text + convert_github_data_to_text(github_data)
        finally:
            if old_sanitize is None:
                os.environ.pop("GITHUB_SANITIZE_MODE", None)
            else:
                os.environ["GITHUB_SANITIZE_MODE"] = old_sanitize
        result.setdefault("source_keyword_presence", {})[
            candidate.candidate_id
        ] = source_keyword_presence(clean_resume_text)

        for prompt_mode in ["weak", "hardened"]:
            for repeat in range(1, args.repeats + 1):
                print(
                    f"[score] candidate={candidate.candidate_id} prompt={prompt_mode} repeat={repeat}/{args.repeats}",
                    flush=True,
                )
                start = time.time()
                try:
                    with maybe_capture(args.verbose), time_limit(args.timeout_sec):
                        evaluation = evaluate_text(
                            resume_text=clean_resume_text,
                            model=MODEL_NAME,
                            model_params=model_params,
                            prompt_mode=prompt_mode,
                        )
                    score = score_total_and_details(evaluation)
                    row = {
                        "candidate_id": candidate.candidate_id,
                        "prompt_mode": prompt_mode,
                        "repeat": repeat,
                        "ok": True,
                        "elapsed_sec": time.time() - start,
                        "score": score,
                    }
                except Exception as exc:  # noqa: BLE001
                    row = {
                        "candidate_id": candidate.candidate_id,
                        "prompt_mode": prompt_mode,
                        "repeat": repeat,
                        "ok": False,
                        "elapsed_sec": time.time() - start,
                        "error": compact_error(exc),
                    }
                result["score_rows"].append(row)

    result["summary"] = build_summary(result["score_rows"])
    result["evidence_audit_cases"] = select_evidence_audit_cases(
        result["score_rows"],
        result["summary"],
        threshold=args.audit_threshold,
    )
    result["unsupported_bonus_cases"] = audit_unsupported_bonus(
        result["score_rows"],
        result.get("source_keyword_presence", {}),
    )
    result["sanitizer_clean_check"] = run_sanitizer_clean_check()
    result["finished_at"] = datetime.now(timezone.utc).isoformat()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    json_path = OUT_DIR / f"llama31_clean_utility_probe_{stamp}.json"
    report_path = OUT_DIR / "LLAMA31_CLEAN_UTILITY_IMPACT_CN.md"
    result["json_path"] = str(json_path)
    result["report_path"] = str(report_path)

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(result), encoding="utf-8")
    print(f"[done] wrote {json_path}", flush=True)
    print(f"[done] wrote {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
