# Demo handoff samples

这个目录给现场 demo 使用。它不依赖真实 GitHub，不需要访问或修改任何真实账号。

## 1. 五个主样本

| 编号 | PDF | GitHub fixture | 用途 |
|---:|---|---|---|
| 01 | `pdf/01_clean_strong_22456.pdf` | `github_fixtures/01_clean_strong_22456_github_clean.json` | clean 强样本 |
| 02 | `pdf/02_clean_medium_23030.pdf` | `github_fixtures/02_clean_medium_23030_github_clean.json` | clean 中样本 |
| 03 | `pdf/03_clean_weak_20734.pdf` | `github_fixtures/03_clean_weak_20734_github_clean.json` | clean 弱样本 |
| 04 | `pdf/04_weak_basic_github_polluted_20734.pdf` | `github_fixtures/04_weak_basic_github_polluted_20734_direct_command.json` | 弱简历 + 初级 GitHub 直接命令注入 |
| 05 | `pdf/05_weak_advanced_github_polluted_20734.pdf` | `github_fixtures/05_weak_advanced_github_polluted_20734_eval_patch.json` | 弱简历 + 进阶 GitHub evaluation patch 注入 |

注意：04/05 的 PDF 内容故意和 03 相同。污染发生在配套 GitHub JSON 中，用来展示“同一份简历，只改变候选人可控外部文本，分数会被影响/被防住”。

## 2. 可选 PDF 隐藏文本样本

| 文件 | 用途 |
|---|---|
| `optional_pdf_hidden_text/20734_clean_original.pdf` | 原始 clean PDF |
| `optional_pdf_hidden_text/20734_attack_hidden_compact_combined.pdf` | 插入极小、近白色隐藏文本的攻击 PDF |
| `optional_pdf_hidden_text/20734_defended_sanitized.pdf` | 删除 hidden span 后的防御版本 |

这条线可以作为补充 demo，不建议和 GitHub 主线混讲。

## 3. 缓存

`cache/` 里已经放了这 5 个主 PDF 对应的 JSONResume 抽取缓存。现场运行 `scripts/demo_score_pdf_with_github_fixture.py` 时会优先加载缓存，因此通常只需要等待 final scorer。

如果要强制重新抽取 PDF，可以加：

```bash
--no-cache
```

## 4. 单样本命令行运行方式

在项目根目录运行：

```bash
cd /home/ouyang/others/ASAP/proj/hiring-agent
```

clean 弱样本：

```bash
.venv/bin/python scripts/demo_score_pdf_with_github_fixture.py \
  --pdf test_data/demo_handoff_samples/pdf/03_clean_weak_20734.pdf \
  --github-json test_data/demo_handoff_samples/github_fixtures/03_clean_weak_20734_github_clean.json \
  --sanitize-mode semantic_filter \
  --github-evidence-mode raw
```

进阶攻击，旧规则防御：

```bash
.venv/bin/python scripts/demo_score_pdf_with_github_fixture.py \
  --pdf test_data/demo_handoff_samples/pdf/05_weak_advanced_github_polluted_20734.pdf \
  --github-json test_data/demo_handoff_samples/github_fixtures/05_weak_advanced_github_polluted_20734_eval_patch.json \
  --sanitize-mode instruction_filter \
  --github-evidence-mode raw
```

进阶攻击，最终自适应结构化防御：

```bash
.venv/bin/python scripts/demo_score_pdf_with_github_fixture.py \
  --pdf test_data/demo_handoff_samples/pdf/05_weak_advanced_github_polluted_20734.pdf \
  --github-json test_data/demo_handoff_samples/github_fixtures/05_weak_advanced_github_polluted_20734_eval_patch.json \
  --sanitize-mode semantic_filter \
  --github-evidence-mode adaptive_structured
```

## 5. 精确复现实验表

单样本现场跑会有 LLM 波动。PPT/report 中的精确平均数应优先引用：

- `test_data/software_developer_sample_20_ablation/GITHUB_STRUCTURED_EVIDENCE_GATE_RESULTS_CN.md`
- `test_data/software_developer_sample_20_ablation/GITHUB_SEMANTIC_DEFENSE_RESULTS_CN.md`
- `test_data/software_developer_sample_20_ablation/PDF_HIDDEN_SPAN_DEFENSE_PROBE_NEW_RUBRIC_CN.md`
- `test_data/software_developer_sample_20_ablation/non_fact_boundary_attack_probe_20260725_075256.json`
- `test_data/software_developer_sample_20_ablation/non_fact_boundary_attack_probe_20260725_150605.json`
- `test_data/software_developer_sample_20_ablation/non_fact_boundary_attack_probe_20260725_154051.json`
