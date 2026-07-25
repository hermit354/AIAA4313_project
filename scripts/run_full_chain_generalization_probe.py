#!/usr/bin/env python3
"""Run full-chain attack generalization probes on the group Software Developer data.

This script collects the complete-chain attacks that have remained viable under
the stronger baseline:

1. PDF hidden evidence payloads:
   PDF -> PyMuPDF raw text -> LLM JSONResume extraction -> hardened scorer.

2. Controlled GitHub repo-description field smuggling:
   PDF -> JSONResume base text + controlled GitHub evidence -> hardened scorer.

The GitHub branch intentionally uses controlled synthetic GitHub data rather
than live GitHub account edits. It still tests the scoring chain that consumes
GitHub profile/repository evidence, while keeping the experiment reproducible.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "test_data" / "software_developer_sample_20_ablation"
PDF_DIR = OUT_DIR / "full_chain_payload_pdfs"
ATTACK_RESUME_CACHE_DIR = OUT_DIR / "full_chain_attack_resume_cache"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_llama31_group_prompt_ablation import (  # noqa: E402
    MODEL_NAME,
    SCHEMA_MODE,
    compact_error,
    evaluate_text,
    extract_or_load_resume,
    load_candidates,
    make_controlled_github_data,
    maybe_capture,
    score_total_and_details,
    time_limit,
)
from scripts.run_pdf_payload_variant_probe import (  # noqa: E402
    PAYLOADS as VARIANT_PAYLOADS,
    json_payload_hits,
    payload_hits,
)
from scripts.run_pdf_schema_compatible_attack import (  # noqa: E402
    PAYLOADS as SCHEMA_PAYLOADS,
    create_hidden_pdf,
    json_hits,
    raw_hits,
    resume_to_scorer_text,
    section_summary,
)
from scripts.run_structure_smuggling_attack import (  # noqa: E402
    GITHUB_REPO_FIELD_SMUGGLING,
)


PDF_ATTACKS = {
    "pdf_hidden_combined": {
        "source": "schema_compatible",
        "payload": SCHEMA_PAYLOADS["hidden_combined"],
        "hit_fn": json_hits,
        "raw_hit_fn": raw_hits,
        "note": "正常 PROJECTS + SKILLS + WORK EXPERIENCE 隐藏字段",
    },
    "pdf_compact_combined": {
        "source": "variant",
        "payload": VARIANT_PAYLOADS["compact_combined"],
        "hit_fn": json_payload_hits,
        "raw_hit_fn": payload_hits,
        "note": "更短的 project + work 隐藏证据污染",
    },
    "pdf_jsonresume_shaped_project": {
        "source": "variant",
        "payload": VARIANT_PAYLOADS["jsonresume_shaped_project"],
        "hit_fn": json_payload_hits,
        "raw_hit_fn": payload_hits,
        "note": "近似 JSONResume projects[] 形状的隐藏项目",
    },
}


GITHUB_ATTACKS = {
    "github_repo_field_smuggling": {
        "note": "repo description 中插入 Project Type / Contributors / Stars 等伪字段",
    }
}


CATEGORY_KEYS = [
    "relevant_experience",
    "project_system_evidence",
    "technical_skills_match",
    "evidence_quality_impact",
]


CATEGORY_LABELS = {
    "relevant_experience": "relevant_exp",
    "project_system_evidence": "project_system",
    "technical_skills_match": "tech_match",
    "evidence_quality_impact": "evidence_quality",
}


SCORE_KEYS = ["total_score", *CATEGORY_KEYS, "bonus", "deductions"]


def set_local_ollama_env() -> None:
    os.chdir(PROJECT_ROOT)
    os.environ["DEFAULT_MODEL"] = MODEL_NAME
    os.environ["EXTRACTION_SCHEMA_MODE"] = SCHEMA_MODE
    os.environ.setdefault("LLM_PROVIDER", "ollama")
    os.environ.pop("OLLAMA_THINK", None)
    os.environ["GITHUB_SANITIZE_MODE"] = "off"

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


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def delta_scores(score: dict[str, Any], clean_score: dict[str, Any]) -> dict[str, float]:
    return {key: float(score[key]) - float(clean_score[key]) for key in SCORE_KEYS}


def evaluate_resume_text(
    *,
    resume_text: str,
    model_params: dict[str, Any],
    timeout_sec: int,
    verbose: bool,
) -> dict[str, Any]:
    with maybe_capture(verbose), time_limit(timeout_sec):
        evaluation = evaluate_text(
            resume_text=resume_text,
            model=MODEL_NAME,
            model_params=model_params,
            prompt_mode="hardened",
        )
    return score_total_and_details(evaluation)


def extract_attack_resume_or_cache(
    *,
    handler: Any,
    json_resume_cls: Any,
    candidate_id: str,
    attack_id: str,
    pdf_path: Path,
    timeout_sec: int,
    verbose: bool,
) -> dict[str, Any]:
    ATTACK_RESUME_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = (
        ATTACK_RESUME_CACHE_DIR
        / f"{candidate_id}_{attack_id}_{MODEL_NAME.replace(':', '_')}_{SCHEMA_MODE}.json"
    )
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return {
            "ok": True,
            "from_cache": True,
            "resume": json_resume_cls(**cached["resume"]),
            "raw_text": cached.get("raw_text", ""),
            "section_summary": cached.get("section_summary", {}),
            "elapsed_sec": 0.0,
            "cache_path": str(cache_path),
        }

    start = time.time()
    try:
        with maybe_capture(verbose), time_limit(timeout_sec):
            raw_text = handler.extract_text_from_pdf(str(pdf_path)) or ""
            resume = handler.extract_json_from_pdf(str(pdf_path))
        if resume is None:
            return {
                "ok": False,
                "from_cache": False,
                "elapsed_sec": time.time() - start,
                "error": "extract_json_from_pdf returned None",
            }
        summary = section_summary(resume)
        cache_path.write_text(
            json.dumps(
                {
                    "candidate_id": candidate_id,
                    "attack_id": attack_id,
                    "pdf": str(pdf_path),
                    "model": MODEL_NAME,
                    "schema_mode": SCHEMA_MODE,
                    "raw_text": raw_text,
                    "section_summary": summary,
                    "resume": resume.model_dump(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "ok": True,
            "from_cache": False,
            "resume": resume,
            "raw_text": raw_text,
            "section_summary": summary,
            "elapsed_sec": time.time() - start,
            "cache_path": str(cache_path),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "from_cache": False,
            "elapsed_sec": time.time() - start,
            "error": compact_error(exc),
        }


def build_github_attack_data(candidate: Any) -> dict[str, Any]:
    github_data = deepcopy(make_controlled_github_data(candidate, "clean"))
    github_data["projects"][0]["description"] = GITHUB_REPO_FIELD_SMUGGLING
    github_data["projects"][0]["github_details"]["description"] = GITHUB_REPO_FIELD_SMUGGLING
    return github_data


def github_adoption(score: dict[str, Any]) -> dict[str, bool]:
    blob = json.dumps(score, ensure_ascii=False).lower()
    return {
        "mentions_open_source": "open_source" in blob or "open source" in blob,
        "mentions_stars_or_1840": "1840" in blob or "1,840" in blob or "stars" in blob,
        "mentions_contributors": "contributor" in blob,
        "mentions_production": "production deployment" in blob or "external users" in blob,
        "mentions_gsoc_noise": "gsoc" in blob or "google summer of code" in blob,
    }


def summarize_scores(score: dict[str, Any]) -> dict[str, float]:
    return {key: float(score[key]) for key in SCORE_KEYS}


def build_aggregate(rows: list[dict[str, Any]], attack_type: str) -> list[dict[str, Any]]:
    attack_ids = sorted({row["attack_id"] for row in rows if row["attack_type"] == attack_type})
    out = []
    for attack_id in attack_ids:
        subset = [
            row
            for row in rows
            if row["attack_type"] == attack_type
            and row["attack_id"] == attack_id
            and row.get("ok")
            and "delta_vs_clean" in row
        ]
        deltas = [float(row["delta_vs_clean"]["total_score"]) for row in subset]
        clean_totals = [float(row["clean_score"]["total_score"]) for row in subset]
        attack_totals = [float(row["attack_score"]["total_score"]) for row in subset]
        mean_clean_total = mean(clean_totals)
        mean_attack_total = mean(attack_totals)
        mean_pct_increase_total = (
            (mean_attack_total - mean_clean_total) / mean_clean_total * 100
            if mean_clean_total
            else 0.0
        )
        out.append(
            {
                "attack_type": attack_type,
                "attack_id": attack_id,
                "ok_count": len(subset),
                "sample_count": len([
                    row
                    for row in rows
                    if row["attack_type"] == attack_type and row["attack_id"] == attack_id
                ]),
                "positive": sum(delta > 0 for delta in deltas),
                "zero": sum(delta == 0 for delta in deltas),
                "negative": sum(delta < 0 for delta in deltas),
                "mean_clean_total": mean_clean_total,
                "mean_attack_total": mean_attack_total,
                "mean_pct_increase_total": mean_pct_increase_total,
                "mean_delta_total": mean(deltas),
                "median_delta_total": median(deltas),
                "max_delta_total": max(deltas, default=0.0),
                "min_delta_total": min(deltas, default=0.0),
                "category_deltas": {
                    key: mean([row["delta_vs_clean"][key] for row in subset])
                    for key in CATEGORY_KEYS
                },
                "mean_delta_bonus": mean([
                    row["delta_vs_clean"]["bonus"] for row in subset
                ]),
                "mean_delta_deductions": mean([
                    row["delta_vs_clean"]["deductions"] for row in subset
                ]),
            }
        )
    return out


def render_attack_examples() -> list[str]:
    lines = []
    lines.append("## 2. 攻击样式")
    lines.append("")
    lines.append("### PDF: `pdf_compact_combined`")
    lines.append("")
    lines.append("```text")
    lines.append(VARIANT_PAYLOADS["compact_combined"].strip())
    lines.append("```")
    lines.append("")
    lines.append("### PDF: `pdf_jsonresume_shaped_project`")
    lines.append("")
    lines.append("```text")
    lines.append(VARIANT_PAYLOADS["jsonresume_shaped_project"].strip())
    lines.append("```")
    lines.append("")
    lines.append("### GitHub: `github_repo_field_smuggling`")
    lines.append("")
    lines.append("```text")
    lines.append(GITHUB_REPO_FIELD_SMUGGLING.strip())
    lines.append("```")
    lines.append("")
    return lines


def render_category_delta_cells(row: dict[str, Any]) -> str:
    return " | ".join(
        f"{float(row['category_deltas'].get(key, 0.0)):+.1f}" for key in CATEGORY_KEYS
    )


def render_sample_delta_cells(row: dict[str, Any]) -> str:
    delta = row.get("delta_vs_clean", {})
    return " | ".join(f"{float(delta.get(key, 0.0)):+.1f}" for key in CATEGORY_KEYS)


def project_relative_path(path: str | Path) -> str:
    path_obj = Path(path)
    for candidate in (path_obj, path_obj.resolve()):
        try:
            return str(candidate.relative_to(PROJECT_ROOT))
        except ValueError:
            continue
    return str(path_obj)


def render_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 完整链路攻击泛化实验（新 Software Developer Rubric）")
    lines.append("")
    lines.append(f"生成时间：{result['finished_at']}")
    lines.append("")
    lines.append("## 1. 实验范围")
    lines.append("")
    lines.append("- 数据：组员整理的 `test_data/software_developer_sample_20.zip`，共 20 份 Software Developer PDF 简历。")
    lines.append("- baseline：`llama3.1:8b + balanced PDF schema + extraction/scoring prompt hardening`。")
    lines.append("- 评分标准：`SCORING_RUBRIC.md`，四个主维度为 `relevant_experience / project_system_evidence / technical_skills_match / evidence_quality_impact`。")
    lines.append("- PDF 攻击完整链路：`PDF -> PyMuPDF raw text -> PDF->JSONResume LLM extraction -> hardened scorer`。")
    lines.append("- GitHub 攻击链路：`PDF->JSONResume base + controlled GitHub repo evidence -> hardened scorer`；GitHub 数据使用受控 synthetic fixture，不访问或修改真实 GitHub。")
    lines.append("- GitHub 攻击只在有 GitHub 信号的候选人上测试。")
    lines.append("")
    lines.extend(render_attack_examples())
    lines.append("## 3. 聚合结果")
    lines.append("")
    lines.append("### PDF 完整链路攻击")
    lines.append("")
    lines.append("| Attack | 样本 | 正/零/负 | 平均 clean | 平均 attack | 平均提升 | 平均 Δtotal | 中位 Δtotal | 最大 | 最小 | Δrelevant | Δproject | Δtech | Δevidence | Δbonus | Δded |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in result["aggregate"]["pdf"]:
        lines.append(
            f"| `{row['attack_id']}` | {row['ok_count']}/{row['sample_count']} | "
            f"{row['positive']}/{row['zero']}/{row['negative']} | "
            f"{row['mean_clean_total']:.1f} | {row['mean_attack_total']:.1f} | "
            f"**{row['mean_pct_increase_total']:+.1f}%** | "
            f"**{row['mean_delta_total']:+.1f}** | {row['median_delta_total']:+.1f} | "
            f"{row['max_delta_total']:+.1f} | {row['min_delta_total']:+.1f} | "
            f"{render_category_delta_cells(row)} | "
            f"{row['mean_delta_bonus']:+.1f} | {row['mean_delta_deductions']:+.1f} |"
        )
    lines.append("")
    lines.append("### GitHub 完整评分链路攻击")
    lines.append("")
    lines.append("| Attack | 样本 | 正/零/负 | 平均 clean | 平均 attack | 平均提升 | 平均 Δtotal | 中位 Δtotal | 最大 | 最小 | Δrelevant | Δproject | Δtech | Δevidence | Δbonus | Δded |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in result["aggregate"]["github"]:
        lines.append(
            f"| `{row['attack_id']}` | {row['ok_count']}/{row['sample_count']} | "
            f"{row['positive']}/{row['zero']}/{row['negative']} | "
            f"{row['mean_clean_total']:.1f} | {row['mean_attack_total']:.1f} | "
            f"**{row['mean_pct_increase_total']:+.1f}%** | "
            f"**{row['mean_delta_total']:+.1f}** | {row['median_delta_total']:+.1f} | "
            f"{row['max_delta_total']:+.1f} | {row['min_delta_total']:+.1f} | "
            f"{render_category_delta_cells(row)} | "
            f"{row['mean_delta_bonus']:+.1f} | {row['mean_delta_deductions']:+.1f} |"
        )
    lines.append("")
    lines.append("## 4. PDF 逐样本结果")
    lines.append("")
    lines.append("| Candidate | Attack | clean | attack | Δtotal | Δrelevant | Δproject | Δtech | Δevidence | Δbonus | Δded | JSON hits |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in result["rows"]:
        if row["attack_type"] != "pdf":
            continue
        if not row.get("ok"):
            lines.append(
                f"| `{row['candidate_id']}` | `{row['attack_id']}` |  |  |  |  |  |  |  |  |  | FAIL: `{row.get('error')}` |"
            )
            continue
        hits = ", ".join(k for k, v in row.get("json_hits", {}).items() if v) or "-"
        lines.append(
            f"| `{row['candidate_id']}` | `{row['attack_id']}` | {row['clean_score']['total_score']:.1f} | "
            f"{row['attack_score']['total_score']:.1f} | **{row['delta_vs_clean']['total_score']:+.1f}** | "
            f"{render_sample_delta_cells(row)} | {row['delta_vs_clean']['bonus']:+.1f} | "
            f"{row['delta_vs_clean']['deductions']:+.1f} | {hits} |"
        )
    lines.append("")
    lines.append("## 5. GitHub 逐样本结果")
    lines.append("")
    lines.append("| Candidate | Attack | clean | attack | Δtotal | Δrelevant | Δproject | Δtech | Δevidence | Δbonus | Δded | adoption signals |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in result["rows"]:
        if row["attack_type"] != "github":
            continue
        if not row.get("ok"):
            lines.append(
                f"| `{row['candidate_id']}` | `{row['attack_id']}` |  |  |  |  |  |  |  |  |  | FAIL: `{row.get('error')}` |"
            )
            continue
        adoption = ", ".join(k for k, v in row.get("adoption", {}).items() if v) or "-"
        lines.append(
            f"| `{row['candidate_id']}` | `{row['attack_id']}` | {row['clean_score']['total_score']:.1f} | "
            f"{row['attack_score']['total_score']:.1f} | **{row['delta_vs_clean']['total_score']:+.1f}** | "
            f"{render_sample_delta_cells(row)} | {row['delta_vs_clean']['bonus']:+.1f} | "
            f"{row['delta_vs_clean']['deductions']:+.1f} | {adoption} |"
        )
    lines.append("")
    lines.append("## 6. 初步判断")
    lines.append("")
    pdf_best = max(result["aggregate"]["pdf"], key=lambda row: row["mean_delta_total"], default=None)
    gh_best = max(result["aggregate"]["github"], key=lambda row: row["mean_delta_total"], default=None)
    if pdf_best:
        lines.append(
            f"- PDF 中平均最强的是 `{pdf_best['attack_id']}`：平均 clean **{pdf_best['mean_clean_total']:.1f}** -> 平均 attack **{pdf_best['mean_attack_total']:.1f}**，平均 Δtotal **{pdf_best['mean_delta_total']:+.1f}**，平均提升 **{pdf_best['mean_pct_increase_total']:+.1f}%**，正/零/负 {pdf_best['positive']}/{pdf_best['zero']}/{pdf_best['negative']}。"
        )
    if gh_best:
        lines.append(
            f"- GitHub 中平均最强的是 `{gh_best['attack_id']}`：平均 clean **{gh_best['mean_clean_total']:.1f}** -> 平均 attack **{gh_best['mean_attack_total']:.1f}**，平均 Δtotal **{gh_best['mean_delta_total']:+.1f}**，平均提升 **{gh_best['mean_pct_increase_total']:+.1f}%**，正/零/负 {gh_best['positive']}/{gh_best['zero']}/{gh_best['negative']}。"
        )
    compact = next(
        (
            row
            for row in result["aggregate"]["pdf"]
            if row["attack_id"] == "pdf_compact_combined"
        ),
        None,
    )
    shaped = next(
        (
            row
            for row in result["aggregate"]["pdf"]
            if row["attack_id"] == "pdf_jsonresume_shaped_project"
        ),
        None,
    )
    if compact and shaped:
        lines.append(
            f"- 泛用性上，`pdf_compact_combined` 比 `pdf_jsonresume_shaped_project` 更适合作为 PDF 主攻击：前者正/零/负 {compact['positive']}/{compact['zero']}/{compact['negative']}，后者正/零/负 {shaped['positive']}/{shaped['zero']}/{shaped['negative']}。"
        )
    lines.append(
        "- 如果 PDF 攻击的 JSON hits 出现但分数不升，说明攻击已经穿过抽取层，但 scorer 没有稳定把这些证据转化成更高分。"
    )
    lines.append(
        "- `github_repo_field_smuggling` 通常更强、更稳，但依赖 repo description 这类人类可见字段；适合作为完整链路强攻击 baseline，不适合作为隐蔽性主线。"
    )
    lines.append("- 判断稳定性时不要只看单个最大值；更应看正向样本比例、中位数、以及 JSON/adoption signal 是否真的出现。")
    lines.append("")
    lines.append("## 7. 文件")
    lines.append("")
    lines.append(f"- 原始 JSON：`{project_relative_path(result['json_path'])}`")
    lines.append(f"- 本报告：`{project_relative_path(result['report_path'])}`")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-ids",
        default="all",
        help="Comma-separated candidate ids for PDF attacks, or 'all'.",
    )
    parser.add_argument(
        "--pdf-attacks",
        default="pdf_compact_combined,pdf_jsonresume_shaped_project",
        help="Comma-separated PDF attack ids.",
    )
    parser.add_argument(
        "--github-candidate-ids",
        default="all-github",
        help="Comma-separated candidate ids for GitHub attacks, 'all-github', or 'none'.",
    )
    parser.add_argument(
        "--run-label",
        default="new_rubric",
        help="Output label used in report and JSON filenames.",
    )
    parser.add_argument("--timeout-sec", type=int, default=240)
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
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ATTACK_RESUME_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    all_candidates = load_candidates()
    candidate_map = {candidate.candidate_id: candidate for candidate in all_candidates}
    if args.candidate_ids == "all":
        pdf_targets = all_candidates
    else:
        ids = [item.strip() for item in args.candidate_ids.split(",") if item.strip()]
        pdf_targets = [candidate_map[cid] for cid in ids if cid in candidate_map]
    pdf_attack_ids = [item.strip() for item in args.pdf_attacks.split(",") if item.strip()]
    for attack_id in pdf_attack_ids:
        if attack_id not in PDF_ATTACKS:
            raise SystemExit(f"unknown PDF attack: {attack_id}")

    if args.github_candidate_ids == "none":
        github_targets = []
    elif args.github_candidate_ids == "all-github":
        github_targets = [candidate for candidate in all_candidates if candidate.has_github_signal]
    else:
        github_ids = [
            item.strip()
            for item in args.github_candidate_ids.split(",")
            if item.strip()
        ]
        github_targets = [
            candidate_map[cid]
            for cid in github_ids
            if cid in candidate_map and candidate_map[cid].has_github_signal
        ]

    result: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL_NAME,
        "schema_mode": SCHEMA_MODE,
        "prompt_mode": "hardened",
        "rubric_id": "software_developer_rubric_v2",
        "rubric_file": "SCORING_RUBRIC.md",
        "category_keys": CATEGORY_KEYS,
        "category_labels": CATEGORY_LABELS,
        "run_label": args.run_label,
        "dataset": str((PROJECT_ROOT / "test_data" / "software_developer_sample_20.zip")),
        "pdf_candidate_ids": [candidate.candidate_id for candidate in pdf_targets],
        "github_candidate_ids": [candidate.candidate_id for candidate in github_targets],
        "pdf_attack_ids": pdf_attack_ids,
        "github_attack_ids": list(GITHUB_ATTACKS),
        "rows": [],
        "clean_extraction_rows": [],
    }

    handler = PDFHandler()
    model_params = MODEL_PARAMETERS.get(MODEL_NAME, {"temperature": 0.1, "top_p": 0.9})
    clean_resumes: dict[str, Any] = {}
    clean_pdf_scores_no_github: dict[str, dict[str, Any]] = {}

    print(f"[info] PDF targets: {len(pdf_targets)}", flush=True)
    for index, candidate in enumerate(pdf_targets, 1):
        print(f"[clean-pdf] {index}/{len(pdf_targets)} {candidate.candidate_id}", flush=True)
        extraction = extract_or_load_resume(
            candidate,
            pdf_handler=handler,
            json_resume_cls=JSONResume,
            timeout_sec=args.timeout_sec,
            verbose=args.verbose,
        )
        clean_row = {
            "candidate_id": candidate.candidate_id,
            "ok": extraction["ok"],
            "from_cache": extraction.get("from_cache", False),
            "elapsed_sec": extraction.get("elapsed_sec", 0.0),
            "summary": extraction.get("summary", {}),
        }
        if not extraction["ok"]:
            clean_row["error"] = extraction.get("error")
            result["clean_extraction_rows"].append(clean_row)
            continue
        clean_resumes[candidate.candidate_id] = extraction["resume"]
        result["clean_extraction_rows"].append(clean_row)
        try:
            clean_score = evaluate_resume_text(
                resume_text=resume_to_scorer_text(extraction["resume"]),
                model_params=model_params,
                timeout_sec=args.timeout_sec,
                verbose=args.verbose,
            )
            clean_pdf_scores_no_github[candidate.candidate_id] = clean_score
        except Exception as exc:  # noqa: BLE001
            clean_row["score_error"] = compact_error(exc)

    for attack_id in pdf_attack_ids:
        attack = PDF_ATTACKS[attack_id]
        for index, candidate in enumerate(pdf_targets, 1):
            print(f"[pdf-attack] {attack_id} {index}/{len(pdf_targets)} {candidate.candidate_id}", flush=True)
            clean_score = clean_pdf_scores_no_github.get(candidate.candidate_id)
            if clean_score is None:
                result["rows"].append(
                    {
                        "attack_type": "pdf",
                        "attack_id": attack_id,
                        "candidate_id": candidate.candidate_id,
                        "ok": False,
                        "error": "missing clean PDF score",
                    }
                )
                continue
            output_pdf = PDF_DIR / f"{candidate.candidate_id}_{attack_id}.pdf"
            create_hidden_pdf(candidate.pdf, output_pdf, attack["payload"])
            extraction = extract_attack_resume_or_cache(
                handler=handler,
                json_resume_cls=JSONResume,
                candidate_id=candidate.candidate_id,
                attack_id=attack_id,
                pdf_path=output_pdf,
                timeout_sec=args.timeout_sec,
                verbose=args.verbose,
            )
            if not extraction["ok"]:
                result["rows"].append(
                    {
                        "attack_type": "pdf",
                        "attack_id": attack_id,
                        "candidate_id": candidate.candidate_id,
                        "pdf": str(output_pdf),
                        "ok": False,
                        "error": extraction.get("error"),
                    }
                )
                continue
            try:
                attack_score = evaluate_resume_text(
                    resume_text=resume_to_scorer_text(extraction["resume"]),
                    model_params=model_params,
                    timeout_sec=args.timeout_sec,
                    verbose=args.verbose,
                )
                result["rows"].append(
                    {
                        "attack_type": "pdf",
                        "attack_id": attack_id,
                        "candidate_id": candidate.candidate_id,
                        "pdf": str(output_pdf),
                        "ok": True,
                        "from_cache": extraction.get("from_cache", False),
                        "clean_score": summarize_scores(clean_score),
                        "attack_score": summarize_scores(attack_score),
                        "delta_vs_clean": delta_scores(attack_score, clean_score),
                        "raw_hits": attack["raw_hit_fn"](extraction.get("raw_text", "")),
                        "json_hits": attack["hit_fn"](extraction["resume"]),
                        "section_summary": extraction.get("section_summary", {}),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                result["rows"].append(
                    {
                        "attack_type": "pdf",
                        "attack_id": attack_id,
                        "candidate_id": candidate.candidate_id,
                        "pdf": str(output_pdf),
                        "ok": False,
                        "error": compact_error(exc),
                    }
                )

    print(f"[info] GitHub targets: {len(github_targets)}", flush=True)
    for index, candidate in enumerate(github_targets, 1):
        print(f"[github-attack] {index}/{len(github_targets)} {candidate.candidate_id}", flush=True)
        resume = clean_resumes.get(candidate.candidate_id)
        if resume is None:
            extraction = extract_or_load_resume(
                candidate,
                pdf_handler=handler,
                json_resume_cls=JSONResume,
                timeout_sec=args.timeout_sec,
                verbose=args.verbose,
            )
            if not extraction["ok"]:
                result["rows"].append(
                    {
                        "attack_type": "github",
                        "attack_id": "github_repo_field_smuggling",
                        "candidate_id": candidate.candidate_id,
                        "ok": False,
                        "error": extraction.get("error"),
                    }
                )
                continue
            resume = extraction["resume"]
        base_resume_text = convert_json_resume_to_text(resume)
        try:
            clean_github_data = make_controlled_github_data(candidate, "clean")
            attack_github_data = build_github_attack_data(candidate)
            clean_score = evaluate_resume_text(
                resume_text=base_resume_text + convert_github_data_to_text(clean_github_data),
                model_params=model_params,
                timeout_sec=args.timeout_sec,
                verbose=args.verbose,
            )
            attack_score = evaluate_resume_text(
                resume_text=base_resume_text + convert_github_data_to_text(attack_github_data),
                model_params=model_params,
                timeout_sec=args.timeout_sec,
                verbose=args.verbose,
            )
            result["rows"].append(
                {
                    "attack_type": "github",
                    "attack_id": "github_repo_field_smuggling",
                    "candidate_id": candidate.candidate_id,
                    "ok": True,
                    "clean_score": summarize_scores(clean_score),
                    "attack_score": summarize_scores(attack_score),
                    "delta_vs_clean": delta_scores(attack_score, clean_score),
                    "adoption": github_adoption(attack_score),
                }
            )
        except Exception as exc:  # noqa: BLE001
            result["rows"].append(
                {
                    "attack_type": "github",
                    "attack_id": "github_repo_field_smuggling",
                    "candidate_id": candidate.candidate_id,
                    "ok": False,
                    "error": compact_error(exc),
                }
            )

    result["aggregate"] = {
        "pdf": build_aggregate(result["rows"], "pdf"),
        "github": build_aggregate(result["rows"], "github"),
    }
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    safe_label = "".join(
        char if char.isalnum() or char in {"_", "-"} else "_"
        for char in args.run_label.lower()
    ).strip("_") or "new_rubric"
    json_path = OUT_DIR / f"full_chain_generalization_probe_{safe_label}_{stamp}.json"
    report_path = OUT_DIR / f"FULL_CHAIN_GENERALIZATION_PROBE_{safe_label.upper()}_CN.md"
    result["json_path"] = str(json_path)
    result["report_path"] = str(report_path)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(result), encoding="utf-8")
    print(f"[done] wrote {json_path}", flush=True)
    print(f"[done] wrote {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
