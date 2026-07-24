# Hiring Agent Web Demo 使用说明

这是一个本地课堂演示与测试平台，用于展示简历上传、异步解析、AI 优先级评分、人工复核、模型切换和运行结果对比。界面使用 `templates/hiring_agent_glass_editorial_template.html`，后端使用 FastAPI + SQLite，文件与运行产物保存在本地。

## 启动

在 `hiring-agent` 目录执行：

```powershell
\.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File web_demo/scripts/dev_local.ps1
```

然后打开 <http://127.0.0.1:3000>。

Windows 启动脚本会自动执行 Alembic 数据库迁移、启动 FastAPI（8000 端口）和 Next.js（3000 端口）。macOS/Linux 可执行：

```bash
sh web_demo/scripts/dev_local.sh
```

## 演示账号

- Staff：`staff@demo.local` / `demo123`
- Candidate：`alice@demo.local` / `demo123`

Candidate 只能上传自己的 PDF 并查看处理状态，不能看到评分、排名、Evidence、模型或运行产物。Staff 可以查看申请列表、候选人详情、PDF、结构化简历、评分证据、Pipeline 阶段和历史 Evaluation Run。

## 推荐演示流程

1. 以 Candidate 登录并上传 PDF，观察 `Processing` 状态。
2. 退出后以 Staff 登录，查看 Applications 和候选人详情。
3. 在 Models 中切换默认模型，或在候选人详情中创建新的 Rerun。
4. 在 Experiments 中比较不同 Evaluation Run。
5. 在 Demo Controls 中执行 Seed/Reset，恢复固定演示数据。

## 模型配置

本地 Ollama 可选配置：

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:4b
```

DeepSeek 为可选服务，在 `web_demo/.env` 中配置 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL`。密钥只在后端使用，不会发送到浏览器。模型不可用时，Demo 会记录 Provider 状态并使用确定性的本地回退评分，便于离线演示。

阿里云百炼可使用 OpenAI-compatible 接口，在 `web_demo/.env` 中配置：

```env
DASHSCOPE_API_KEY=你的百炼APIKey
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-plus
```

重启后端后，Staff 的 Models 页面会显示 Alibaba DashScope，之后可以将它设为默认模型或在 Rerun 中单独选择。不要把真实 API Key 提交到 GitHub；免费额度由阿里云按模型和账号管理，额度用完不会自动切换模型。

## 检查与测试

服务启动后执行：

```powershell
\.venv\Scripts\python.exe web_demo/scripts/verify_local.py
\.venv\Scripts\python.exe -m unittest discover -s web_demo/tests -v
```

数据库、上传文件和运行产物位于 `web_demo/data/`，这些目录已加入 Git 忽略。Demo Reset 只删除标记为 Demo 的记录，不会删除测试过程中产生的非 Demo 数据。
