# Hiring Agent Web Demo：队友快速接入手册

这套 Demo 用于统一做简历 PDF、Prompt、模型和输入注入实验。每个人可以在自己的电脑上运行，使用自己的 Ollama 模型或 API；实验结果保存在自己的 `web_demo/data/` 中，不会上传到 GitHub。

## 一、最快启动

在仓库根目录 `hiring-agent/` 执行：

```powershell
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item web_demo\.env.example web_demo\.env
powershell -ExecutionPolicy Bypass -File web_demo/scripts/dev_local.ps1
```

打开 <http://127.0.0.1:3000>。

macOS/Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp web_demo/.env.example web_demo/.env
sh web_demo/scripts/dev_local.sh
```

Demo 账号：

- Staff：`staff@demo.local` / `demo123`
- Candidate：`alice@demo.local` / `demo123`

## 二、换成本地 Ollama 模型

先确认模型已经下载：

```bash
ollama serve
ollama pull llama3.1:8b
ollama list
```

编辑 `web_demo/.env`：

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.1:8b
```

也可以换成其他本机模型，例如 `gemma3:4b`、`qwen3:8b`。修改后重启后端，Staff → Models 会显示新的模型。

## 三、接入阿里云百炼或其他 OpenAI-compatible API

在 `web_demo/.env` 中配置阿里云百炼：

```env
DASHSCOPE_API_KEY=你的APIKey
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-plus
```

重启后端后，Staff → Models 会出现 `Alibaba DashScope`。可以把它设为默认模型，或在候选人详情中创建 Rerun。

如果队友使用其他 OpenAI-compatible 服务，可以复用同样的接口结构；最小适配只需要提供：

```text
API Key
Base URL（能够访问 /chat/completions）
Model ID
```

目前项目内置了 Ollama、DeepSeek 和 DashScope。新的服务如果不是 OpenAI-compatible，需要在 `web_demo/pipeline.py` 增加一个 Provider Adapter，不要修改前端页面。

## 四、如何把自己的实验接入

推荐把实验分成三层：

```text
实验代码 / Prompt / Sanitizer
          ↓
统一输出 PipelineResult
          ↓
web_demo/backend.py 保存 Evaluation Run 和 Artifact
```

如果你的实验只改变评分逻辑或 Prompt：

1. 在 `web_demo/pipeline.py` 中保留 PDF 提取和 `PipelineConfig`。
2. 替换或扩展 `_evaluate()`，返回 `score/base/bonus/deduction/evidence`。
3. 保持 `PipelineResult` 字段结构不变。
4. 在 `web_demo/tests/` 增加一个针对该实验的测试。

如果你的实验会大幅修改后端：

1. 不要改动 Candidate/Staff API 的返回权限。
2. 继续使用 `application_id` 和 `run_id` 区分数据。
3. 每次实验生成新的 Evaluation Run，不要覆盖历史 Run。
4. 把实验配置写入 `PipelineConfig`，这样可以在 Experiments 页面比较。
5. 如果新增数据库字段，补一条 Alembic migration。

如果只是想快速试验，不想改 Web Demo，可以先在仓库根目录运行原有 CLI，确认结果后再把核心逻辑接到 `_evaluate()`。

## 五、推荐团队实验方法

每个人使用自己的 `.env` 和本地模型，但使用相同的：

- 测试 PDF 集合；
- Prompt 版本；
- `PipelineConfig` 参数；
- 评分输出格式。

实验完成后，可以分享 `web_demo/data/artifacts/*.json` 中的 Run 结果，或手动整理成 CSV。不要提交以下内容：

- `web_demo/.env`；
- API Key；
- 真实简历 PDF；
- `web_demo/data/`；
- `node_modules/` 和 `.next/`。

## 六、检查和排错

```powershell
python web_demo/scripts/verify_local.py
python -m unittest discover -s web_demo/tests -v
```

常见问题：

- Models 页面显示模型不可用：检查 `ollama list` 或 `.env` 中的 API 配置。
- 上传后一直 Processing：查看运行中的 FastAPI 终端，以及 `web_demo/data/artifacts/`。
- 改了模型但页面没有变化：确认重启的是后端，而不仅是浏览器。
- API Key 不生效：确认变量写在 `web_demo/.env`，不要只写在根目录旧的 CLI `.env` 中。

## 七、数据位置

```text
web_demo/data/hiring_agent.db   SQLite 数据库
web_demo/data/uploads/          上传 PDF
web_demo/data/artifacts/        Evaluation Run JSON
```

查看本地实验记录时：

- `artifacts/run-<id>.json`：包含原始 PDF 文本、结构化简历 JSON、模型配置、评分、Evidence 和每个 Pipeline 阶段的结果；
- `hiring_agent.db`：包含 `applications`、`evaluation_runs` 和 `stage_runs` 表。`evaluation_runs.error` 保存失败原因，`stage_runs` 保存队列、运行和完成状态；
- FastAPI 终端：显示请求、异常和启动错误；
- Staff → System Runs：显示每次 Run 的状态。排查时也可以直接访问 `GET /api/staff/runs/<run_id>/stages` 和 `GET /api/staff/runs/<run_id>/artifact`（需要 Staff 登录 Token）。

Windows 下快速列出本地 Artifact：

```powershell
Get-ChildItem web_demo/data/artifacts
Get-Content web_demo/data/artifacts/run-你的run_id.json -Raw
```

Demo Reset 只清理标记为 Demo 的数据，不会删除队友创建的非 Demo 实验记录。
