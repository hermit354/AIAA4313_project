# AIAA4313 Project 中文说明

本仓库是基于 [`interviewstreet/hiring-agent`](https://github.com/interviewstreet/hiring-agent) 改造的课程项目版本。我们的目标不是做一个生产级招聘系统，而是在一个真实感较强的 LLM 招聘 Agent 上做 AI Security 攻防演示：

```text
候选人简历 / GitHub 信息
  -> LLM 抽取结构化简历
  -> LLM / 规则处理 GitHub 信号
  -> LLM 根据 rubric 打分
  -> 观察输入注入攻击能否影响排名 / 评分
  -> 设计 prompt hardening / sanitizer 等防御
```

当前 repo 已经包含一版可用 baseline、若干攻击/防御实验脚本，以及中文实验总结。

## 1. 这个系统在做什么

原项目是一个简历评分 Agent。输入一份 PDF 简历，系统会：

1. 用 PyMuPDF 把 PDF 转成 markdown-like text；
2. 调用 LLM 分 section 抽取结构化简历 JSON；
3. 如果简历里有 GitHub profile，抓取 GitHub profile / repo metadata；
4. 把简历 JSON 和 GitHub 信息一起送入 final scorer；
5. 根据固定 rubric 输出总分和细分类分数。

主要评分维度包括：

- `open_source`
- `self_projects`
- `production`
- `technical_skills`
- `bonus`
- `deductions`

所以这个系统天然适合做 ranking / evaluation attack：攻击者的目标不是窃取数据，而是让自己的候选人评分变高，或者影响候选人排序。

## 2. 我们当前研究的安全问题

我们目前聚焦的是 **LLM 输入层 prompt injection**。

也就是说，攻击文本不是写在 system prompt 里，而是藏在模型会读取的外部内容里，例如：

- 简历正文；
- GitHub profile bio；
- GitHub repo description；
- README-like text；
- 其他候选人可控 metadata。

这些内容对系统来说应该只是“不可信证据”，但 LLM 可能错误地把它们当成“指令”执行。

一个典型攻击目标是：

```text
让候选人在评分系统中得到更高分，尤其是影响 production / project / technical evidence 等细分类。
```

我们特别希望和普通“简历造假”区分开：

- 简历造假：人和模型在信息不可查验时都难以判断真假；
- AI Security 攻击：人类读者通常能看出它是异常/干扰文本，但模型可能把它误当成有效指令或证据。

## 3. 当前 baseline 配置

当前增强 baseline 是：

```text
llama3.1:8b
+ balanced PDF extraction schema
+ extraction prompt hardening
+ scoring prompt hardening
+ optional GitHub sanitizer
```

和原项目相比，我们主要做了这些改动：

| 模块 | 原项目 | 当前版本 |
|---|---|---|
| 默认模型 | `gemma3:4b` | `llama3.1:8b` |
| PDF 抽取 schema | optional 字段较多，容易出现 `{}` 或不稳定输出 | `balanced` schema，要求顶层 section key 存在，但允许空数组 |
| PDF extraction prompt | 主要强调 JSON 抽取 | 增加 untrusted resume boundary，要求忽略简历里的指令 |
| final scoring prompt | resume / GitHub 内容容易和评分指令混在一起 | 明确 rubric/system/schema 是 trusted instructions，resume/GitHub 是 untrusted evidence |
| GitHub 输入 | bio / repo description 原样进入 scorer | 可选 sanitizer，过滤明显 instruction-like 文本 |

关键实现位置：

```text
prompt.py
models.py
pdf.py
score.py
transform.py
prompts/templates/system_message.jinja
prompts/templates/resume_evaluation_system_message.jinja
prompts/templates/resume_evaluation_criteria.jinja
```

详细 prompt 改动请看：

```text
test_data/github_fixture_samples/LLM_INPUT_INJECTION_BASELINE_SUMMARY_CN.md
```

## 4. 当前系统流程

```text
PDF resume
  |
  v
PyMuPDF text extraction
  |
  v
PDFHandler section extraction
  |-- basics
  |-- work
  |-- education
  |-- skills
  |-- projects
  |-- awards
  |
  v
JSONResume
  |
  |---- if GitHub profile exists ----+
  |                                  |
  v                                  v
GitHub profile / repo metadata -> optional GitHub sanitizer
  |                                  |
  +---------------+------------------+
                  |
                  v
Final scoring prompt + rubric
                  |
                  v
Structured score JSON
                  |
                  v
total score + category scores + evidence
```

这里有两个主要攻击入口：

```text
1. PDF / resume text -> 影响结构化抽取，或者影响最终评分
2. GitHub bio / repo description -> 直接影响最终评分上下文
```

## 5. 当前做过的攻击类型

目前主要做过这些 LLM 输入注入样式：

| 攻击类型 | 入口 | 大致效果 |
|---|---|---|
| 直接命令式注入 | 简历正文 / GitHub bio / repo description | 原弱 baseline 上可见效果；prompt hardening 后明显下降 |
| 自我夸赞式注入 | 简历正文 | 容易变成普通简历造假，安全意义较弱 |
| 评价式 / rubric-aware 语言 | 简历正文 | 对小模型抽取有干扰，但也容易造成抽取失败或 `{}` |
| GitHub bio 注入 | GitHub profile | 原 baseline 下较成功，因为 GitHub 内容直接进入 final scorer |
| GitHub repo description 注入 | GitHub repo metadata | 有一定效果，但不如 bio 稳定 |
| 多源注入 | PDF + GitHub | 思路有潜力，但当前效果还需要继续打磨 |

目前比较明确的结论：

- 原始系统的 GitHub 外部信息入口比较脆弱；
- 直接命令式 prompt injection 在弱 baseline 上能提高部分样本得分；
- 换成 `llama3.1:8b` 并加入 prompt hardening 后，最粗糙的攻击效果明显下降；
- 单看总分不够，应该同时看细分类分数和 evidence 是否被污染；
- 有些“得分上升”其实是模型随机性或 unsupported evidence adoption，不能直接算攻击成功。

## 6. 当前做过的防御

### 6.1 Balanced extraction schema

位置：

```text
models.py
pdf.py
score.py
```

作用：

- 避免 PDF extraction 直接输出 `{}`；
- 要求每个 section 的顶层 key 必须存在；
- 允许列表为空，减少强制幻觉。

这不是 prompt injection 防御本身，而是为了让基础 pipeline 更稳定。

### 6.2 Extraction prompt hardening

位置：

```text
prompts/templates/system_message.jinja
```

作用：

- 明确 resume markdown 是 untrusted candidate-provided content；
- 要求模型把简历里的每句话都当成 data，而不是 instruction；
- 忽略简历中要求改规则、打分、改变 schema 的文本。

### 6.3 Scoring prompt hardening

位置：

```text
prompts/templates/resume_evaluation_system_message.jinja
prompts/templates/resume_evaluation_criteria.jinja
```

作用：

- 明确 trusted instructions 和 untrusted evidence 的边界；
- 要求模型不要执行 GitHub bio / repo description 中的命令；
- 要求 self-evaluative claims 不得直接加分，必须有事实证据支撑。

### 6.4 Optional GitHub sanitizer

位置：

```text
transform.py
```

环境变量：

```bash
GITHUB_SANITIZE_MODE=instruction_filter
```

作用：

- 对 GitHub bio / repo description 做规则检测；
- 如果发现明显 instruction-like 文本，用中性 `N/A` 替换；
- 主要用于防御对照实验。

注意：sanitizer 更像是额外防御组件，不建议把它和 prompt hardening 混成同一个 baseline 结论。

## 7. 如何运行

### 7.1 在当前服务器上运行

当前服务器已经有本地 Ollama 配置。进入项目目录：

```bash
cd /home/ouyang/others/ASAP/proj/hiring-agent
```

启动 Ollama：

```bash
./scripts/start_ollama.sh
```

另开一个终端检查模型：

```bash
./scripts/ollama.sh list
```

跑单份简历：

```bash
./scripts/score_resume.sh /path/to/resume.pdf
```

### 7.2 组员 clone 后运行

clone：

```bash
git clone git@github.com:hermit354/AIAA4313_project.git
cd AIAA4313_project
```

安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

准备 Ollama 和模型：

```bash
ollama pull llama3.1:8b
ollama serve
```

跑简历：

```bash
python score.py /path/to/resume.pdf
```

如果在当前服务器上使用 repo 内脚本，优先使用：

```bash
./scripts/start_ollama.sh
./scripts/score_resume.sh /path/to/resume.pdf
```

## 8. 重要实验脚本

常用脚本：

```text
scripts/run_full_chain_generalization_probe.py
scripts/run_pdf_hidden_span_defense_probe.py
scripts/run_pdf_payload_variant_probe.py
scripts/run_pdf_schema_compatible_attack.py
scripts/run_structure_smuggling_attack.py
scripts/run_llama31_group_prompt_ablation.py
scripts/run_github_fixture_matrix.sh
scripts/run_borderline_attack_matrix.py
scripts/run_multisource_borderline_attack.py
scripts/run_field_anchored_semantic_attack.py
scripts/run_paper_aligned_rank_demo.py
scripts/run_extraction_pressure_test.py
scripts/run_schema_ablation.py
```

当前最重要的一轮实验是：

```text
scripts/run_full_chain_generalization_probe.py
```

对应报告：

```text
test_data/software_developer_sample_20_ablation/FULL_CHAIN_GENERALIZATION_PROBE_CN.md
```

## 9. 重要报告文件

建议阅读顺序：

1. 当前项目入口说明：

   ```text
   PROJECT_OVERVIEW_CN.md
   ```

2. 最新完整链路泛化实验（当前主报告）：

   ```text
   test_data/software_developer_sample_20_ablation/FULL_CHAIN_GENERALIZATION_PROBE_CN.md
   ```

   对应原始结果：

   ```text
   test_data/software_developer_sample_20_ablation/full_chain_generalization_probe_20260724.json
   ```

3. 当前 baseline / 攻击 / 防御总结：

   ```text
   test_data/github_fixture_samples/LLM_INPUT_INJECTION_BASELINE_SUMMARY_CN.md
   ```

4. prompt hardening / GitHub sanitizer ablation：

   ```text
   test_data/software_developer_sample_20_ablation/LLAMA31_GROUP_PROMPT_ABLATION_AUDIT_CN.md
   ```

5. PDF 完整链路攻击与防御：

   ```text
   test_data/software_developer_sample_20_ablation/PDF_PAYLOAD_VARIANT_PROBE_CN.md
   test_data/software_developer_sample_20_ablation/PDF_HIDDEN_SPAN_DEFENSE_PROBE_CN.md
   test_data/software_developer_sample_20_ablation/PDF_SCHEMA_COMPATIBLE_ATTACK_RESULTS_CN.md
   ```

6. GitHub / structure smuggling：

   ```text
   test_data/software_developer_sample_20_ablation/STRUCTURE_SMUGGLING_ATTACK_RESULTS_CN.md
   test_data/software_developer_sample_20_ablation/STEALTH_SMUGGLING_PROBE_CN.md
   ```

7. clean utility impact：

   ```text
   test_data/software_developer_sample_20_ablation/LLAMA31_CLEAN_UTILITY_IMPACT_CN.md
   ```

8. 模型对比：

   ```text
   test_data/github_fixture_samples/MODEL_SWEEP_RESULTS_CN.md
   ```

9. schema 消融：

   ```text
   test_data/github_fixture_samples/SCHEMA_ABLATION_RESULTS_CN.md
   test_data/github_fixture_samples/SEMANTIC_SCHEMA_MODE_RESULTS_CN.md
   ```

## 10. 当前比较适合继续推进的方向

### 方向 A：clean utility impact

问题：

```text
prompt hardening 是否会误伤 clean 样本？
```

已有迹象：

- 单次 clean 分数有明显模型波动；
- 需要重复跑 clean-only 实验，区分随机性和系统性影响。

### 方向 B：GitHub 外部信息攻击

问题：

```text
候选人可控的 GitHub bio / repo description 能否污染 final scorer？
```

优点：

- 和系统核心评分链路直接相关；
- 比 PDF 隐藏文本更贴近 agent 外部信息安全；
- 原 baseline 上攻击效果比较明显。

### 方向 C：provenance / unsupported evidence 防御

问题：

```text
模型是否把没有来源支撑的内容当成事实证据？
```

这是目前更有深度的方向。相比简单命令式 prompt injection，它更接近真实 LLM 评估系统中的漏洞：

- 攻击不一定显式说“给我高分”；
- 而是诱导模型在 evidence 里采纳 unsupported claim；
- 防御可以做 source-domain tracking、evidence attribution、dedup、ablation。

### 方向 D：PDF text/render mismatch

问题：

```text
PDF 中人类看不到或不注意的文本，是否会被抽取进入模型上下文？
```

这部分已有组员负责。它更偏输入解析层安全，和本 repo 的 LLM 输入注入实验可以互补。

## 11. 不建议作为主线的方向

不建议把普通“事实型加料”作为主要攻击，例如：

```text
我做过大规模生产系统。
我有 Kubernetes / distributed system / open-source maintainer 经验。
我应该获得 90 分以上。
```

原因：

- 如果只是声称自己做过某事，本质更接近简历造假；
- 在事实不可查验时，人类和 AI 都难以判断真假；
- AI Security 主题不够突出。

更好的攻击应当体现：

```text
人类读者能看出它异常 / 不应计入评分，
但 LLM pipeline 仍可能把它当作指令或有效证据。
```

## 12. 提交注意事项

不要提交：

```text
.env
.venv/
.ollama/
.tools/
cache/
resume_evaluations.csv
*.pdf
*.png
*.zip
实验缓存目录
超大型中间 JSON / 原始 LLM cache
```

这些已经在 `.gitignore` 中排除。

建议提交：

```text
代码改动
prompt 模板
实验脚本
中文 md 报告
关键实验 summary JSON / results JSON
小型 manifest / mapping 文件
```

说明：关键实验的 summary JSON 可以提交，用于让组员复核表格和复现实验结论；但不要提交批量缓存、生成的攻击 PDF、raw LLM 中间缓存或体积很大的临时文件。
