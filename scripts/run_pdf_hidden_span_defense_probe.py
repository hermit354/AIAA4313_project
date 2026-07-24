#!/usr/bin/env python3
"""Probe hidden-span detection + ablation for PDF schema-compatible attacks.

This is a defense-side follow-up to run_pdf_schema_compatible_attack.py.

Pipeline tested here:

1. clean PDF -> JSONResume -> hardened scorer
2. attacked PDF with white/tiny schema-compatible hidden text -> JSONResume -> scorer
3. same attacked PDF -> remove near-white tiny text spans -> JSONResume -> scorer

The point is not to build a perfect PDF sanitizer. The point is to test whether
the attack signal is actually carried by visually hidden PDF spans and whether a
simple rendering-aware ablation can remove that signal before LLM extraction.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import fitz


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "test_data" / "software_developer_sample_20_ablation"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_llama31_group_prompt_ablation import (  # noqa: E402
    MODEL_NAME,
    SCHEMA_MODE,
    compact_error,
    evaluate_text,
    load_candidates,
    maybe_capture,
    score_total_and_details,
    time_limit,
)
from scripts.run_pdf_schema_compatible_attack import (  # noqa: E402
    PAYLOADS as SCHEMA_COMPATIBLE_PAYLOADS,
    create_hidden_pdf,
    json_hits,
    raw_hits,
    resume_to_scorer_text,
    section_summary,
)
from scripts.run_pdf_payload_variant_probe import (  # noqa: E402
    PAYLOADS as VARIANT_PAYLOADS,
    json_payload_hits,
    payload_hits,
)


PAYLOADS = {**SCHEMA_COMPATIBLE_PAYLOADS, **VARIANT_PAYLOADS}


@dataclass(frozen=True)
class SpanRecord:
    page: int
    text: str
    size: float
    color: int
    bbox: tuple[float, float, float, float]


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


def is_near_white(color: int, threshold: int = 245) -> bool:
    r = (color >> 16) & 255
    g = (color >> 8) & 255
    b = color & 255
    return r >= threshold and g >= threshold and b >= threshold


def collect_spans(pdf_path: Path) -> list[SpanRecord]:
    spans: list[SpanRecord] = []
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc):
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = (span.get("text") or "").strip()
                        if not text:
                            continue
                        spans.append(
                            SpanRecord(
                                page=page_index + 1,
                                text=text,
                                size=float(span.get("size", 0.0)),
                                color=int(span.get("color", 0)),
                                bbox=tuple(float(x) for x in span.get("bbox", (0, 0, 0, 0))),
                            )
                        )
    return spans


def is_hidden_span(span: SpanRecord, *, min_font_size: float, white_threshold: int) -> bool:
    return span.size < min_font_size and is_near_white(span.color, white_threshold)


def visible_text_from_pdf(
    pdf_path: Path, *, min_font_size: float = 4.5, white_threshold: int = 245
) -> tuple[str, list[SpanRecord], list[SpanRecord]]:
    kept: list[SpanRecord] = []
    dropped: list[SpanRecord] = []
    for span in collect_spans(pdf_path):
        if is_hidden_span(span, min_font_size=min_font_size, white_threshold=white_threshold):
            dropped.append(span)
        else:
            kept.append(span)

    lines: list[str] = []
    current_page = None
    for span in kept:
        if span.page != current_page:
            if lines:
                lines.append("")
            current_page = span.page
        lines.append(span.text)
    return "\n".join(lines), kept, dropped


def delta_scores(score: dict[str, Any], clean_score: dict[str, Any]) -> dict[str, float]:
    keys = [
        "total_score",
        "open_source",
        "self_projects",
        "production",
        "technical_skills",
        "bonus",
        "deductions",
    ]
    return {key: float(score[key]) - float(clean_score[key]) for key in keys}


def evaluate_resume_text(resume_text: str, *, timeout_sec: int, verbose: bool):
    from prompt import MODEL_PARAMETERS

    model_params = MODEL_PARAMETERS.get(MODEL_NAME, {"temperature": 0.1, "top_p": 0.9})
    with maybe_capture(verbose), time_limit(timeout_sec):
        return evaluate_text(
            resume_text=resume_text,
            model=MODEL_NAME,
            model_params=model_params,
            prompt_mode="hardened",
        )


def run_case(
    *,
    candidate: Any,
    payload_id: str,
    timeout_sec: int,
    verbose: bool,
    min_font_size: float,
    white_threshold: int,
) -> dict[str, Any]:
    from pdf import PDFHandler

    handler = PDFHandler()
    attack_pdf = OUT_DIR / "pdf_schema_compatible_payloads" / f"{candidate.candidate_id}_{payload_id}.pdf"
    if payload_id in VARIANT_PAYLOADS:
        attack_pdf = OUT_DIR / "pdf_payload_variant_payloads" / f"{candidate.candidate_id}_{payload_id}.pdf"
    if not attack_pdf.exists():
        create_hidden_pdf(candidate.pdf, attack_pdf, PAYLOADS[payload_id])

    row: dict[str, Any] = {
        "candidate_id": candidate.candidate_id,
        "payload_id": payload_id,
        "clean_pdf": str(candidate.pdf),
        "attack_pdf": str(attack_pdf),
    }

    start = time.time()
    clean_resume = handler.extract_json_from_pdf(str(candidate.pdf))
    if clean_resume is None:
        raise RuntimeError("clean extraction returned None")
    clean_eval = evaluate_resume_text(
        resume_to_scorer_text(clean_resume), timeout_sec=timeout_sec, verbose=verbose
    )
    clean_score = score_total_and_details(clean_eval)
    row["clean"] = {
        "score": clean_score,
        "section_summary": section_summary(clean_resume),
        "elapsed_sec": time.time() - start,
    }

    start = time.time()
    raw_text = handler.extract_text_from_pdf(str(attack_pdf)) or ""
    attack_resume = handler.extract_json_from_pdf(str(attack_pdf))
    if attack_resume is None:
        raise RuntimeError("attack extraction returned None")
    attack_eval = evaluate_resume_text(
        resume_to_scorer_text(attack_resume), timeout_sec=timeout_sec, verbose=verbose
    )
    attack_score = score_total_and_details(attack_eval)
    hit_fn = json_payload_hits if payload_id in VARIANT_PAYLOADS else json_hits
    raw_hit_fn = payload_hits if payload_id in VARIANT_PAYLOADS else raw_hits

    row["attack"] = {
        "score": attack_score,
        "delta_vs_clean": delta_scores(attack_score, clean_score),
        "raw_hits": raw_hit_fn(raw_text),
        "json_hits": hit_fn(attack_resume),
        "section_summary": section_summary(attack_resume),
        "elapsed_sec": time.time() - start,
    }

    start = time.time()
    visible_text, kept, dropped = visible_text_from_pdf(
        attack_pdf,
        min_font_size=min_font_size,
        white_threshold=white_threshold,
    )
    defended_resume = handler.extract_json_from_text(visible_text)
    if defended_resume is None:
        raise RuntimeError("defended extraction returned None")
    defended_eval = evaluate_resume_text(
        resume_to_scorer_text(defended_resume), timeout_sec=timeout_sec, verbose=verbose
    )
    defended_score = score_total_and_details(defended_eval)
    row["defense"] = {
        "score": defended_score,
        "delta_vs_clean": delta_scores(defended_score, clean_score),
        "delta_vs_attack": delta_scores(defended_score, attack_score),
        "json_hits": hit_fn(defended_resume),
        "section_summary": section_summary(defended_resume),
        "visible_text_len": len(visible_text),
        "kept_span_count": len(kept),
        "dropped_span_count": len(dropped),
        "dropped_snippets": [span.text[:180] for span in dropped[:12]],
        "elapsed_sec": time.time() - start,
    }

    return row


def render_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# PDF hidden-span detection + ablation 防御对照")
    lines.append("")
    lines.append(f"生成时间：{result['finished_at']}")
    lines.append("")
    lines.append("## 1. 实验目的")
    lines.append("")
    lines.append("验证一个最小防御：在 PDF 文本进入 LLM 抽取前，删除近白色且极小字号的文本 span。")
    lines.append("")
    lines.append("链路对比：")
    lines.append("")
    lines.append("```text")
    lines.append("clean PDF -> JSONResume -> hardened scorer")
    lines.append("attack PDF -> JSONResume -> hardened scorer")
    lines.append("attack PDF -> hidden-span ablation -> JSONResume -> hardened scorer")
    lines.append("```")
    lines.append("")
    lines.append("## 2. 防御规则")
    lines.append("")
    lines.append(
        f"- 删除条件：`font_size < {result['min_font_size']}` 且 `RGB >= {result['white_threshold']}`。"
    )
    lines.append("- 这个规则专门针对本轮 white tiny text 攻击；它不是通用 PDF 安全方案。")
    lines.append("")
    lines.append("## 3. 结果")
    lines.append("")
    lines.append("| Candidate | Payload | clean | attack | Δattack | defended | Δdefense vs clean | Δdefense vs attack | dropped spans | attack JSON hits | defense JSON hits |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for row in result["rows"]:
        if not row["ok"]:
            lines.append(
                f"| `{row['candidate_id']}` | `{row['payload_id']}` |  |  |  |  |  |  |  | FAIL: `{row.get('error')}` |  |"
            )
            continue
        clean_total = row["clean"]["score"]["total_score"]
        attack_total = row["attack"]["score"]["total_score"]
        defense_total = row["defense"]["score"]["total_score"]
        attack_hits = ", ".join(k for k, v in row["attack"]["json_hits"].items() if v) or "-"
        defense_hits = ", ".join(k for k, v in row["defense"]["json_hits"].items() if v) or "-"
        lines.append(
            f"| `{row['candidate_id']}` | `{row['payload_id']}` | {clean_total:.1f} | "
            f"{attack_total:.1f} | **{row['attack']['delta_vs_clean']['total_score']:+.1f}** | "
            f"{defense_total:.1f} | **{row['defense']['delta_vs_clean']['total_score']:+.1f}** | "
            f"**{row['defense']['delta_vs_attack']['total_score']:+.1f}** | "
            f"{row['defense']['dropped_span_count']} | {attack_hits} | {defense_hits} |"
        )
    lines.append("")
    lines.append("## 4. 被删除文本示例")
    lines.append("")
    for row in result["rows"]:
        if not row["ok"]:
            continue
        lines.append(f"### `{row['candidate_id']}` / `{row['payload_id']}`")
        lines.append("")
        for snippet in row["defense"]["dropped_snippets"][:8]:
            lines.append(f"- `{snippet}`")
        lines.append("")
    lines.append("## 5. 初步结论")
    lines.append("")
    ok_rows = [row for row in result["rows"] if row["ok"]]
    if ok_rows:
        avg_attack_delta = sum(row["attack"]["delta_vs_clean"]["total_score"] for row in ok_rows) / len(ok_rows)
        avg_defense_delta = sum(row["defense"]["delta_vs_clean"]["total_score"] for row in ok_rows) / len(ok_rows)
        avg_recovery = sum(row["defense"]["delta_vs_attack"]["total_score"] for row in ok_rows) / len(ok_rows)
        lines.append(
            f"- 攻击平均 Δtotal：**{avg_attack_delta:+.1f}**；防御后相对 clean 平均 Δtotal：**{avg_defense_delta:+.1f}**；防御相对 attack 平均变化：**{avg_recovery:+.1f}**。"
        )
    clean_demo = next(
        (
            row
            for row in ok_rows
            if row["candidate_id"] == "20734" and row["payload_id"] == "compact_combined"
        ),
        None,
    )
    if clean_demo:
        lines.append(
            f"- `20734 + compact_combined` 是当前最干净的 demo case：clean **{clean_demo['clean']['score']['total_score']:.1f}** -> "
            f"attack **{clean_demo['attack']['score']['total_score']:.1f}** -> defense **{clean_demo['defense']['score']['total_score']:.1f}**。"
        )
    schema_demo = next(
        (
            row
            for row in ok_rows
            if row["candidate_id"] == "23030" and row["payload_id"] == "jsonresume_shaped_project"
        ),
        None,
    )
    if schema_demo:
        lines.append(
            f"- `23030 + jsonresume_shaped_project` 适合展示 schema-shaped 污染：clean **{schema_demo['clean']['score']['total_score']:.1f}** -> "
            f"attack **{schema_demo['attack']['score']['total_score']:.1f}** -> defense **{schema_demo['defense']['score']['total_score']:.1f}**。"
        )
    lines.append(
        "- defense JSON hits 里偶尔还会出现 `production` / `ci_tests` 这类通用词，不一定来自 payload，因为 clean 简历本身也可能包含这些词。更应看唯一 anchor，例如 `maintainer-dashboard` / `portfolio-api` / `open-source` / `FastAPI` / `PostgreSQL` 是否还存在。"
    )
    lines.append("- 如果唯一 payload anchor 在 defense JSON 中消失，说明攻击内容主要是通过隐藏 span 穿过抽取层。")
    lines.append("- 这能作为 demo 的防御闭环：不是靠 scorer prompt 识别语义，而是在 PDF ingestion 阶段移除人类不可见输入。")
    lines.append("")
    lines.append("## 6. 文件")
    lines.append("")
    lines.append(f"- 原始 JSON：`{Path(result['json_path']).relative_to(PROJECT_ROOT)}`")
    lines.append(f"- 本报告：`{Path(result['report_path']).relative_to(PROJECT_ROOT)}`")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        default="20734:hidden_combined,23030:hidden_project,23030:hidden_combined,23372:hidden_combined",
        help="Comma-separated candidate_id:payload_id cases.",
    )
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--min-font-size", type=float, default=4.5)
    parser.add_argument("--white-threshold", type=int, default=245)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    set_local_ollama_env()

    candidates = {candidate.candidate_id: candidate for candidate in load_candidates()}
    cases: list[tuple[str, str]] = []
    for item in args.cases.split(","):
        if not item.strip():
            continue
        candidate_id, payload_id = item.strip().split(":", 1)
        if candidate_id not in candidates:
            raise SystemExit(f"unknown candidate id: {candidate_id}")
        if payload_id not in PAYLOADS:
            raise SystemExit(f"unknown payload id: {payload_id}")
        cases.append((candidate_id, payload_id))

    result: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL_NAME,
        "schema_mode": SCHEMA_MODE,
        "min_font_size": args.min_font_size,
        "white_threshold": args.white_threshold,
        "cases": [{"candidate_id": cid, "payload_id": pid} for cid, pid in cases],
        "rows": [],
    }

    for candidate_id, payload_id in cases:
        print(f"[case] {candidate_id} {payload_id}", flush=True)
        try:
            row = run_case(
                candidate=candidates[candidate_id],
                payload_id=payload_id,
                timeout_sec=args.timeout_sec,
                verbose=args.verbose,
                min_font_size=args.min_font_size,
                white_threshold=args.white_threshold,
            )
            row["ok"] = True
        except Exception as exc:  # noqa: BLE001
            row = {
                "candidate_id": candidate_id,
                "payload_id": payload_id,
                "ok": False,
                "error": compact_error(exc),
            }
        result["rows"].append(row)

    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    json_path = OUT_DIR / f"pdf_hidden_span_defense_probe_{stamp}.json"
    report_path = OUT_DIR / "PDF_HIDDEN_SPAN_DEFENSE_PROBE_CN.md"
    result["json_path"] = str(json_path)
    result["report_path"] = str(report_path)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(result), encoding="utf-8")
    print(f"[done] wrote {json_path}", flush=True)
    print(f"[done] wrote {report_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
