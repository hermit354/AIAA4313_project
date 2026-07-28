#!/usr/bin/env python3
"""Run one frozen demo configuration without mutating the frozen copy.

Usage:
    ASAP_DEMO_CONFIG=v1 python scripts/run_frozen_demo_config.py --candidate-ids 22456

The selected frozen environment is copied to /tmp first. All experiment output
is copied back to backups/demo_config_runs/ with metadata and logs.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).absolute().parents[1]
FROZEN_ROOT = Path(
    os.environ.get(
        "ASAP_FROZEN_ROOT",
        "/home/ouyang/others/ASAP/proj/hiring-agent_frozen_envs/"
        "frozen_v_envs_20260725T2026",
    )
)
DEFAULT_PYTHON = Path(
    os.environ.get(
        "ASAP_DEMO_PYTHON",
        "/home/ouyang/others/ASAP/proj/hiring-agent/.venv/bin/python",
    )
)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "backups" / "demo_config_runs"
DEFAULT_CANDIDATES = "20734,21780,22456,22992,23030,23372"


CONFIGS: dict[str, dict[str, Any]] = {
    "v0a": {
        "label": "V0A original weak baseline + schema-targeted direct command",
        "frozen_dir": "V0_123bf8e_direct_command",
        "kind": "v0a_historical_script",
        "script": PROJECT_ROOT
        / "backups"
        / "v0a_historical_tmp_results_20260725T2050Z"
        / "asap_v0_best_payload_stability_historical.py",
        "expected_tmp_result": Path("/tmp/asap_v0_best_payload_stability.json"),
        "env": {
            "GITHUB_EVIDENCE_MODE": "raw",
        },
        "notes": [
            "Runs the backed-up V0A stability script.",
            "Candidate subset is fixed inside the historical script.",
            "ASAP_V0_REPEATS controls repeat count; default here is 1.",
        ],
    },
    "v1": {
        "label": "V1 advanced baseline + non-fact evaluation patch attack",
        "frozen_dir": "V1_50bfee1_prompt_serializer_nonfact",
        "kind": "non_fact_probe",
        "sanitize_mode": "instruction_filter",
        "github_evidence_mode": "raw",
    },
    "v1_5": {
        "label": "V1.5 semantic scorer hardening + semantic_filter defense",
        "frozen_dir": "V2_3640769_semantic_filter",
        "kind": "non_fact_probe",
        "sanitize_mode": "semantic_filter",
        "github_evidence_mode": "raw",
    },
    "v2": {
        "label": "V2 structured GitHub evidence gate defense",
        "frozen_dir": "V3_3640769_structured_gate",
        "kind": "non_fact_probe",
        "sanitize_mode": "instruction_filter",
        "github_evidence_mode": "structured_extract",
    },
}


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default=os.environ.get("ASAP_DEMO_CONFIG"),
        choices=sorted(CONFIGS),
        help="Demo config. Can also be set with ASAP_DEMO_CONFIG.",
    )
    parser.add_argument(
        "--candidate-ids",
        default=os.environ.get("ASAP_DEMO_CANDIDATES", DEFAULT_CANDIDATES),
        help="Comma-separated candidate ids for v1/v1_5/v2 probes.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=int(os.environ.get("ASAP_DEMO_TIMEOUT_SEC", "240")),
    )
    parser.add_argument(
        "--v0-repeats",
        type=int,
        default=int(os.environ.get("ASAP_V0_REPEATS", "1")),
        help="Repeat count for v0a historical script.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(os.environ.get("ASAP_DEMO_OUTPUT_ROOT", DEFAULT_OUTPUT_ROOT)),
    )
    parser.add_argument(
        "--tmp-root",
        type=Path,
        default=Path(os.environ.get("ASAP_DEMO_TMP_ROOT", "/tmp/asap_demo_config_runs")),
    )
    parser.add_argument(
        "--cleanup-run-dir",
        action="store_true",
        help="Delete the writable temporary copy after preserving logs/results.",
    )
    parser.add_argument("--list-configs", action="store_true")
    return parser.parse_args()


def print_configs() -> None:
    for config_id, cfg in CONFIGS.items():
        print(f"{config_id}: {cfg['label']}")
        print(f"  frozen: {FROZEN_ROOT / cfg['frozen_dir']}")


def make_writable(path: Path) -> None:
    for item in [path, *path.rglob("*")]:
        try:
            mode = item.stat().st_mode
            item.chmod(mode | stat.S_IWUSR)
        except OSError:
            pass


def base_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "GITHUB_EVIDENCE_MODE",
        "GITHUB_SANITIZE_MODE",
        "SCORING_PROMPT_PROFILE",
    ]:
        env.pop(key, None)
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    env.setdefault("LLM_PROVIDER", "ollama")
    env.setdefault("DEFAULT_MODEL", "llama3.1:8b")
    env.setdefault("EXTRACTION_SCHEMA_MODE", "balanced")
    if extra:
        env.update({key: str(value) for key, value in extra.items()})
    return env


def copy_frozen_env(config_id: str, cfg: dict[str, Any], tmp_root: Path) -> Path:
    source = FROZEN_ROOT / cfg["frozen_dir"]
    if not source.is_dir():
        raise SystemExit(f"missing frozen env: {source}")
    tmp_root.mkdir(parents=True, exist_ok=True)
    run_dir = tmp_root / f"{utc_stamp()}_{config_id}_{os.getpid()}"
    shutil.copytree(source, run_dir, symlinks=True)
    make_writable(run_dir)
    return run_dir


def newest_probe_result(run_dir: Path, *, started_epoch: float) -> Path | None:
    out_dir = run_dir / "test_data" / "software_developer_sample_20_ablation"
    files = sorted(
        [
            item
            for item in out_dir.glob("non_fact_boundary_attack_probe_*.json")
            if item.stat().st_mtime >= started_epoch
        ],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def run_command(
    *,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> int:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_file:
        proc = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
            check=False,
        )
    return proc.returncode


def build_command(config_id: str, cfg: dict[str, Any], args: argparse.Namespace) -> tuple[list[str], dict[str, str]]:
    if not DEFAULT_PYTHON.exists():
        raise SystemExit(f"missing python interpreter: {DEFAULT_PYTHON}")

    if cfg["kind"] == "v0a_historical_script":
        script = Path(cfg["script"])
        if not script.exists():
            raise SystemExit(f"missing V0A historical script: {script}")
        env_extra = dict(cfg.get("env", {}))
        env_extra["ASAP_V0_REPEATS"] = str(args.v0_repeats)
        command = [str(DEFAULT_PYTHON), str(script)]
        return command, env_extra

    if cfg["kind"] == "non_fact_probe":
        command = [
            str(DEFAULT_PYTHON),
            "scripts/run_non_fact_boundary_attack_probe.py",
            "--candidate-ids",
            args.candidate_ids,
            "--scenarios",
            "github_eval_json_patch",
            "--sanitize-mode",
            cfg["sanitize_mode"],
            "--timeout-sec",
            str(args.timeout_sec),
        ]
        env_extra = {
            "GITHUB_EVIDENCE_MODE": cfg["github_evidence_mode"],
        }
        return command, env_extra

    raise SystemExit(f"unsupported config kind: {cfg['kind']}")


def preserve_outputs(
    *,
    config_id: str,
    cfg: dict[str, Any],
    run_dir: Path,
    output_dir: Path,
    started_epoch: float,
) -> list[str]:
    copied: list[str] = []
    if cfg["kind"] == "v0a_historical_script":
        src = Path(cfg["expected_tmp_result"])
        dst = output_dir / f"{config_id}_v0a_best_payload_stability.json"
        if src.exists() and src.stat().st_mtime >= started_epoch:
            if copy_if_exists(src, dst):
                copied.append(str(dst))
        return copied

    probe_json = newest_probe_result(run_dir, started_epoch=started_epoch)
    if probe_json is not None:
        dst = output_dir / f"{config_id}_{probe_json.name}"
        if copy_if_exists(probe_json, dst):
            copied.append(str(dst))

    report = run_dir / "test_data" / "software_developer_sample_20_ablation" / "NON_FACT_BOUNDARY_ATTACK_PROBE_CN.md"
    if report.exists() and report.stat().st_mtime >= started_epoch:
        dst = output_dir / f"{config_id}_NON_FACT_BOUNDARY_ATTACK_PROBE_CN.md"
        if copy_if_exists(report, dst):
            copied.append(str(dst))
    return copied


def main() -> int:
    args = parse_args()
    if args.list_configs:
        print_configs()
        return 0
    if not args.config:
        raise SystemExit("missing config: set ASAP_DEMO_CONFIG or pass --config")

    config_id = args.config
    cfg = CONFIGS[config_id]
    stamp = utc_stamp()
    output_dir = args.output_root / f"{stamp}_{config_id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    run_dir = copy_frozen_env(config_id, cfg, args.tmp_root)
    command, env_extra = build_command(config_id, cfg, args)
    env = base_env(env_extra)

    stdout_path = output_dir / "stdout.log"
    stderr_path = output_dir / "stderr.log"
    started_epoch = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    returncode = run_command(
        command=command,
        cwd=run_dir,
        env=env,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    finished_at = datetime.now(timezone.utc).isoformat()
    copied_outputs = preserve_outputs(
        config_id=config_id,
        cfg=cfg,
        run_dir=run_dir,
        output_dir=output_dir,
        started_epoch=started_epoch,
    )

    metadata = {
        "config": config_id,
        "label": cfg["label"],
        "started_at": started_at,
        "finished_at": finished_at,
        "returncode": returncode,
        "frozen_root": str(FROZEN_ROOT),
        "frozen_env": str(FROZEN_ROOT / cfg["frozen_dir"]),
        "writable_run_dir": str(run_dir),
        "output_dir": str(output_dir),
        "python": str(DEFAULT_PYTHON),
        "command": command,
        "env_overrides": env_extra,
        "candidate_ids": args.candidate_ids if cfg["kind"] == "non_fact_probe" else "fixed in V0A historical script",
        "v0_repeats": args.v0_repeats if cfg["kind"] == "v0a_historical_script" else None,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "copied_outputs": copied_outputs,
        "notes": cfg.get("notes", []),
    }
    metadata_path = output_dir / "run_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.cleanup_run_dir:
        shutil.rmtree(run_dir)
        metadata["writable_run_dir_deleted"] = True
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
