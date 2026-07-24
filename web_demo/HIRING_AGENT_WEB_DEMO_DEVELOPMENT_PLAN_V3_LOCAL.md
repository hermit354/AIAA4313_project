# Hiring Agent Web Demo 开发执行计划（V3：本机单机版）

> **目标仓库**：`https://github.com/interviewstreet/hiring-agent`  
> **基线审计日期**：2026-07-23  
> **计划更新时间**：2026-07-23  
> **当前运行策略**：先实现本机单机版，不使用 Docker、PostgreSQL、Redis 或 Celery。  
> **模型准备状态**：本机 Ollama 已下载 `gemma3:4b`；后续由用户在 `.env` 中提供 DeepSeek V4 API 配置。  
> **当前状态**：UI/UX 方案与可交互静态 HTML 原型已经完成；现在进入 Core 重构、本机 FastAPI、SQLite、后台任务执行器、模型 Provider 和真实前后端融合阶段。  
> **文档用途**：本文件是 Coding Agent 的主执行规范。除非发现明确技术阻塞，不要擅自扩大范围、重新设计 UI 或引入额外基础设施。  
> **当前阶段目标**：把已经确认的浅蓝白 Glass Editorial HTML 原型嵌入真实 Hiring Agent 系统。具体攻击与防御逻辑暂不在本阶段实现，但系统必须为后续安全实验保留可插拔入口、运行追踪和结果对比能力。

---


## 当前实施进度与交接资产

### 已完成

- 产品范围已经确定：
  - 不做岗位页；
  - 只保留 Candidate 与 Staff 两种角色；
  - Recruiter 与 Researcher 已合并为 Staff Console；
  - Demo Mode 只通过 Staff 顶栏的唯一开关控制。
- 页面信息架构已经确定：
  - `/login`
  - `/candidate`
  - `/staff/applications`
  - `/staff/applications/[id]`
  - `/staff/experiments`
  - `/staff/models`
  - `/staff/runs`
  - `/staff/demo`
- 视觉方向已经确定为：
  - 浅蓝白毛玻璃；
  - Editorial 衬线标题；
  - 无衬线 UI 正文；
  - 克制的蓝灰色状态系统；
  - 模块层级清楚但避免重复卡片。
- 已完成一个可直接浏览和交互的静态 HTML 原型：
  - `hiring_agent_demo_template_v2_blue.html`
- 静态原型已经包含：
  - 登录；
  - Candidate Workspace；
  - Staff Sidebar 和 Topbar；
  - Applications；
  - Candidate Detail；
  - Experiments / Run Compare；
  - Models；
  - System Runs；
  - Demo Controls；
  - Mock 登录、上传、模型切换、Rerun 和 Reset；
  - Desktop / tablet / mobile 响应式。
- 已去除冗余的页面内 `Enable Demo Mode` 区块，Demo Mode 只保留顶栏开关。

### 尚未完成

- 尚未确认目标仓库当前 commit 和原 CLI 回归基线；
- 尚未完成 `PipelineConfig` 与请求级模型注入；
- 尚未完成 FastAPI、SQLite 和本机后台任务执行器；
- 尚未完成真实登录、权限和数据隔离；
- 尚未完成文件存储、SHA-256、Evaluation Run 和 Stage Run；
- 本机 `gemma3:4b` 已下载，但尚未完成 Backend Model Registry 和真实调用接入；
- DeepSeek V4 API 尚未接入，等待 `.env` 中提供真实 `BASE_URL`、`API_KEY` 和 `MODEL`；
- 尚未将静态 HTML 拆分为 Next.js 组件；
- 尚未将 `mockApi` 和 Mock 数据替换为真实 API；
- 尚未完成真实 PDF 预览、状态轮询、Run Compare 和 Demo Reset；
- 尚未完成测试、本机启动脚本和一键启动。

### UI 交接约束

Coding Agent 必须把下面的文件作为唯一视觉源：

```text
frontend_reference/hiring_agent_demo_template_v2_blue.html
```

若该文件当前位于仓库外，第一步将其复制进仓库的 `frontend_reference/` 目录，并保留原文件不改，作为视觉回归基准。

Agent 不得：

- 重新生成一套 Dashboard；
- 改回暖米色或橙棕色主题；
- 使用 Claude 风格的米色/陶土色作为主配色；
- 恢复页面内第二个 Demo Mode 开关；
- 用 stock shadcn 页面替换现有设计；
- 因为接后端而删除已经确认的页面结构；
- 在 React/Next.js 重构时任意更改文案层级、留白、字体或玻璃透明度。

Agent 可以：

- 把原生 CSS Token 迁移到 `globals.css`；
- 把页面拆成可复用组件；
- 用真实 Loading、Empty、Error 状态替换 Mock 状态；
- 为可访问性、响应式和真实数据长度做必要微调；
- 在不改变视觉语言的前提下优化 DOM 和组件结构。

---

## 0. 最终交付目标

将当前以 CLI 为主的简历评分仓库升级为一个视觉完整、可交互、方便调试的 Web 应用，能够展示：

```text
候选人登录
  → 上传 PDF 简历
  → 后端异步解析
  → 结构化简历提取
  → 可选 GitHub 信息补充
  → LLM 评分
  → Staff 端排序与筛选
  → 查看评分证据和完整 Pipeline 运行详情
  → 切换模型并重新运行
```

系统只保留两类用户视角：

1. **Candidate Workspace**
   - 候选人登录；
   - 上传或替换自己的 PDF；
   - 查看处理进度和申请状态；
   - 不得看到评分、排名、模型、Prompt、缓存或其他候选人信息。

2. **Staff Console**
   - 合并原先的 Recruiter 与 Researcher 视角；
   - 查看全部申请、AI 分数、排名、评分证据和 PDF；
   - 切换默认模型；
   - 对单份简历选择模型并重新运行；
   - 查看每个 Pipeline 阶段、耗时、输入输出和错误；
   - 比较同一申请的不同 Evaluation Run；
   - 通过网页右上角的 **Demo Mode** 开关进入简化演示视图。

---

## 1. 项目定位与边界

### 1.1 产品定位

这是一个 **AI-assisted resume prioritization system**，不是自动录用系统。

前端文案应表达：

- AI 用于安排人工审阅优先级；
- 低分只代表低优先级或低于人工审阅 cutoff；
- 最终决策由人类招聘人员完成。

推荐状态文案：

- `High Priority`
- `Standard Review`
- `Below Review Cutoff`
- `Requires Human Review`

禁止使用：

- `AI Rejected`
- `Automatically Rejected`
- `Unqualified Candidate`
- `Hiring Decision Made by AI`

### 1.2 本阶段必须实现

- 简单邮箱密码登录 UI；
- Candidate 与 Staff 两种角色；
- 候选人 PDF 上传；
- PDF 文本提取；
- 分区结构化解析；
- 可选 GitHub enrichment；
- LLM 评分；
- 候选人排名与筛选；
- 评分证据展示；
- Evaluation Run 历史；
- 运行阶段状态与错误追踪；
- 模型列表、健康状态和一键切换；
- 单次运行模型覆盖；
- 后台处理与前端状态轮询；
- 数据持久化；
- 本机一键启动脚本；
- Demo Mode；
- Demo 数据初始化与重置；
- Glass Editorial 视觉规范；
- 基本自动化测试和演示稳定性保障。

### 1.3 本阶段明确不做

- 岗位列表和岗位详情页；
- 多职位申请；
- 候选人注册；
- 邮箱验证；
- 找回密码；
- OAuth；
- 多因素认证；
- 真实邮件通知；
- 面试安排；
- Offer 管理；
- 多公司 multi-tenant；
- 外部 ATS 集成；
- Kubernetes；
- 完整云部署；
- Docker / Docker Compose；
- PostgreSQL；
- Redis；
- Celery；
- 复杂 Prompt 在线编辑器；
- 聊天式 HR 助手；
- 正式攻击与防御实现；
- 大量动画、视差或 3D 效果。

---

## 2. 原仓库基线与改造原则

当前仓库的核心流程为：

```text
pymupdf_rag.py
  → PDF 转 Markdown-like text

pdf.py
  → Basics / Work / Education / Skills / Projects / Awards 分区 LLM 提取
  → JSONResume

github.py
  → GitHub profile 与 repositories 补充

evaluator.py
  → Open Source / Self Projects / Production / Technical Skills
  → Bonus / Deductions / Evidence

score.py
  → 同步编排
  → stdout
  → development mode 下写 basename cache 和 CSV
```

当前实现依赖全局 `DEFAULT_MODEL`，`score.py` 是同步 CLI 编排，Development Mode 使用原始 PDF basename 生成缓存文件。

### 2.1 改造原则

1. **不要先重写评分算法。**
2. **保留原 CLI 可运行性。**
3. **优先以兼容方式为原类增加参数注入。**
4. **Web Pipeline 不得依赖 stdout、CSV 或原始文件名作为唯一标识。**
5. **每次评分必须形成不可覆盖的 Evaluation Run。**
6. **每个 Run 必须保存完整模型配置和版本快照。**
7. **不同候选人上传相同文件名时不得发生数据混淆。**
8. **前端切换模型不得通过修改全局环境变量实现。**
9. **攻击和防御以后通过 PipelineConfig、CachePolicy、PromptVersion 等扩展，不修改主页面架构。**

---

## 3. 推荐技术栈

### 3.1 Frontend

- Next.js，App Router；
- TypeScript；
- Tailwind CSS 可用于布局，但现有 HTML 原型中的 CSS Token 和关键组件样式必须被保留；
- `hiring_agent_demo_template_v2_blue.html` 是视觉与交互基准，不再进行 UI 探索；
- Radix UI 或 shadcn/ui 只用于 Dialog、Dropdown、Tabs、Tooltip 等可访问性基础组件；
- 必须覆盖默认样式，禁止保留 stock shadcn 外观；
- Lucide Icons；
- TanStack Query 用于 API 状态、缓存失效和轮询；
- TanStack Table 用于 Staff 申请表；
- Recharts 仅用于确有必要的分数分布，不做复杂 Dashboard；
- 原生 `<iframe>` 或 `<object>` 用于受保护 PDF 预览，优先避免第一阶段引入复杂 PDF renderer；
- 迁移顺序必须是：保留视觉 → 拆组件 → 接 Mock Adapter → 接真实 API，而不是先重写页面再尝试还原视觉。

### 3.2 Backend

- FastAPI；
- Pydantic；
- SQLAlchemy 2.x；
- SQLite，数据库文件默认位于 `data/hiring_agent.db`；
- Alembic 可保留，用于管理 SQLite schema；
- `pydantic-settings`；
- `httpx`；
- `python-multipart`；
- JWT 或签名 Session Cookie；
- bcrypt 密码哈希；
- `concurrent.futures.ThreadPoolExecutor` 或等价的单机 Job Runner；
- 任务状态持久化到 SQLite；
- 本地文件系统保存 PDF 和 Run Artifacts；
- 不使用 PostgreSQL、Redis、Celery 或独立 Worker 服务。

### 3.3 Model Providers

当前只接入两个 Provider：

1. **Ollama Local**
   - 本机已经下载 `gemma3:4b`；
   - Ollama 服务地址默认：`http://127.0.0.1:11434`；
   - Backend 通过 Ollama API 调用；
   - 这是首个必须跑通的真实模型。

2. **DeepSeek V4 API**
   - 用户后续在 `.env` 中提供；
   - 不在代码中硬编码 Endpoint、API Key 或模型名称；
   - 通过环境变量配置；
   - 如果 API 兼容 OpenAI Chat Completions，可使用统一 OpenAI-compatible Provider；
   - 如果实际协议不同，Agent 应以用户提供的 API 文档为准实现 Adapter；
   - 这是第二个模型，用于云端运行和 Run Compare。

`providers.json` 继续作为应用允许展示的模型白名单和默认参数来源。实际可用性由 Backend Model Registry 动态判断。

运行时必须通过请求级 `PipelineConfig` 传入模型，不能修改全局 `DEFAULT_MODEL`。

前端只能获得：

```text
model_id
display_name
provider
local_or_cloud
configured
healthy
default_parameters
```

前端不得获得：

```text
API key
模型文件路径
完整 Provider 密钥配置
```

### 3.3.1 本机模型位置

当前本机已经通过 Ollama 下载：

```text
gemma3:4b
```

不需要将模型复制进项目目录，也不要把模型放进：

```text
frontend/
backend/
data/uploads/
Git repository
```

Ollama 负责管理模型文件。Backend 只需要连接：

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:4b
```

验证命令：

```bash
ollama list
curl http://127.0.0.1:11434/api/tags
ollama run gemma3:4b "Return only: OK"
```

### 3.3.2 DeepSeek V4 API 配置

`.env` 中预留：

```env
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=
DEEPSEEK_MODEL=
DEEPSEEK_API_STYLE=openai_compatible
```

规则：

- `DEEPSEEK_MODEL` 必须使用 API Provider 实际要求的精确模型 ID；
- 不要在计划中假设公开名称一定就是 `deepseek-v4`；
- `DEEPSEEK_BASE_URL` 必须来自用户提供的 API；
- 缺少任一必要配置时，前端显示 `Not configured`；
- 不得因为 DeepSeek 未配置而影响 Gemma 本地流程；
- 健康检查默认只验证配置和轻量连接，不要反复产生昂贵请求；
- 真实评分调用失败时，应保存 Provider 错误并允许切回 Gemma。

### 3.3.3 Model Registry 三层关系

```text
Ollama / DeepSeek Provider
        ↓ 实际是否可用
providers.json
        ↓ 应用允许展示的模型与默认参数
app_settings.default_model_id
        ↓ 新 Run 默认选择
PipelineConfig.model_id
        ↓ 单次 Run 的不可变模型快照
```

首版前端模型选择器应显示：

```text
Gemma 3 4B · Local
DeepSeek V4 · API
```

但 DeepSeek 的实际 `model_id` 从 `.env` 或 Provider 配置读取，不能只使用展示名称调用 API。

### 3.4 Local Runtime

当前阶段采用纯本机运行：

```text
Browser
  ├── Next.js Frontend: http://localhost:3000
  └── FastAPI Backend:  http://127.0.0.1:8000
          ├── SQLite: data/hiring_agent.db
          ├── Uploads: data/uploads/
          ├── Artifacts: data/artifacts/
          ├── Local Job Runner
          ├── Ollama: http://127.0.0.1:11434
          └── DeepSeek API: remote, configured by .env
```

启动方式：

```text
Terminal 1: Ollama service
Terminal 2: FastAPI backend
Terminal 3: Next.js frontend
```

也应提供本机聚合启动脚本：

```text
scripts/dev_local.sh
scripts/dev_local.ps1
```

Windows 用户优先使用 PowerShell 脚本。

Backend 应启用只允许本机前端的 CORS：

```text
http://localhost:3000
http://127.0.0.1:3000
```

不需要：

- Docker image；
- Docker Compose；
- 容器网络；
- Redis；
- 独立 Worker；
- 数据库服务进程。

---

## 4. 建议目录结构

在尽量不破坏原仓库的前提下，改造成：

```text
hiring-agent/
├── score.py
├── pdf.py
├── evaluator.py
├── github.py
├── models.py
├── transform.py
├── prompt.py
├── config.py
├── providers.json
├── prompts/
│
├── backend/
│   ├── requirements-web.txt
│   ├── alembic.ini
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── settings.py
│       ├── database.py
│       ├── dependencies.py
│       │
│       ├── api/
│       │   ├── auth.py
│       │   ├── candidate.py
│       │   ├── staff.py
│       │   ├── models.py
│       │   ├── runs.py
│       │   └── demo.py
│       │
│       ├── db_models/
│       ├── schemas/
│       │
│       ├── services/
│       │   ├── auth_service.py
│       │   ├── storage_service.py
│       │   ├── model_registry.py
│       │   ├── local_job_runner.py
│       │   ├── ranking_service.py
│       │   ├── artifact_service.py
│       │   └── demo_seed_service.py
│       │
│       ├── providers/
│       │   ├── base.py
│       │   ├── ollama_provider.py
│       │   └── deepseek_provider.py
│       │
│       ├── pipeline/
│       │   ├── config.py
│       │   ├── orchestrator.py
│       │   ├── legacy_adapter.py
│       │   ├── stages.py
│       │   └── artifacts.py
│       │
│       └── tests/
│
├── frontend/
│   ├── package.json
│   ├── next.config.ts
│   └── src/
│       ├── app/
│       ├── components/
│       ├── features/
│       ├── lib/
│       └── styles/
│
├── frontend_reference/
│   └── hiring_agent_demo_template_v2_blue.html
│
├── data/
│   ├── hiring_agent.db
│   ├── uploads/
│   └── artifacts/
│
├── scripts/
│   ├── dev_local.sh
│   ├── dev_local.ps1
│   ├── seed_demo.py
│   ├── reset_demo.py
│   └── verify_local.py
│
├── .env.example
├── DEV_PROGRESS.md
└── README_WEB_DEMO.md
```

不要把原始 Python 文件立即全部移动。先建立 Web Adapter，待回归测试通过后再考虑进一步整理。

## 4.1 静态 HTML 到真实系统的迁移合同

静态 HTML 中已经使用 `BACKEND INTEGRATION POINT` 标出核心接入位置。Agent 必须先将 `mockApi` 抽象为独立 API Client，再逐项替换，禁止在各页面中零散写 `fetch()`。

建议结构：

```text
frontend/src/lib/api/
├── client.ts
├── auth.ts
├── candidate.ts
├── staff.ts
├── runs.ts
├── models.ts
└── demo.ts
```

页面与 API 对应关系：

| 静态原型能力 | 真实 API |
|---|---|
| `mockApi.login` | `POST /api/auth/login` |
| 当前用户 | `GET /api/auth/me` |
| Candidate 申请页 | `GET /api/candidate/application` |
| `mockApi.uploadResume` | `POST /api/candidate/resume` |
| Candidate 状态 | `GET /api/candidate/status` |
| Applications Mock 数组 | `GET /api/staff/applications` |
| Candidate Detail | `GET /api/staff/applications/{id}` |
| PDF Preview | `GET /api/staff/applications/{id}/resume` |
| `mockApi.rerun` | `POST /api/staff/applications/{id}/rerun` |
| Run 列表 | `GET /api/staff/applications/{id}/runs` |
| Run Detail | `GET /api/runs/{run_id}` |
| Stage Timeline | `GET /api/runs/{run_id}/stages` |
| Run Compare | `GET /api/staff/applications/{id}/runs/compare` |
| Models Mock 数组 | `GET /api/models` |
| 模型健康状态 | `GET /api/models/health` |
| `mockApi.setDefaultModel` | `PATCH /api/staff/settings/default-model` |
| `mockApi.resetDemo` | `POST /api/demo/reset` |

### 组件拆分建议

```text
components/
├── shell/
│   ├── StaffShell.tsx
│   ├── StaffSidebar.tsx
│   ├── StaffTopbar.tsx
│   └── DemoModeSwitch.tsx
├── candidate/
│   ├── ResumeUploadPanel.tsx
│   └── ApplicationTimeline.tsx
├── applications/
│   ├── ApplicationsTable.tsx
│   ├── ApplicationFilters.tsx
│   ├── ScoreSummary.tsx
│   └── ReviewTierBadge.tsx
├── application-detail/
│   ├── PdfPreview.tsx
│   ├── StructuredResume.tsx
│   ├── EvaluationEvidence.tsx
│   ├── StaffDecisionPanel.tsx
│   └── AdvancedRunDetails.tsx
├── runs/
│   ├── PipelineTimeline.tsx
│   ├── RunTable.tsx
│   └── RunCompare.tsx
└── models/
    ├── ModelSelector.tsx
    └── ModelHealthTable.tsx
```

### 迁移验收原则

- 第一次 Next.js 渲染必须与静态 HTML 在 1440px 下视觉基本一致；
- Mock 数据可短暂保留，但必须通过统一 API Adapter 提供；
- 接入真实 API 时只替换数据源，不重新布局；
- 顶栏 Demo Mode 开关是唯一 Demo Mode 入口；
- `/staff/demo` 不得再出现第二个 Enable/Disable 模块；
- 后端不可用时展示原设计语言下的 Error State，而不是退回裸 JSON 或浏览器错误页。

---

## 5. 核心后端设计

## 5.1 PipelineConfig

新增不可变运行配置：

```python
from dataclasses import dataclass
from enum import Enum

class CachePolicy(str, Enum):
    FORCE_FRESH = "force_fresh"
    SAFE_REUSE = "safe_reuse"
    LEGACY_BASENAME = "legacy_basename"  # 只为后续受控实验保留，默认不可用

@dataclass(frozen=True)
class PipelineConfig:
    model_id: str
    provider: str
    temperature: float
    top_p: float
    prompt_version: str
    pipeline_version: str
    cache_policy: CachePolicy
    github_enrichment: bool
```

约束：

- Web 默认使用 `SAFE_REUSE`；
- Staff 可以选择 `FORCE_FRESH`；
- `LEGACY_BASENAME` 暂不暴露给普通页面；
- 每次 Run 将配置完整复制到数据库；
- 已完成 Run 的配置不得被全局设置修改。

## 5.2 最小侵入式改造原核心

将现有类改为支持可选参数，同时保留旧行为：

```python
class PDFHandler:
    def __init__(
        self,
        model_name: str | None = None,
        model_params: dict | None = None,
        provider=None,
    ):
        ...
```

旧代码未传参数时继续使用当前默认模型。

同样处理：

- `ResumeEvaluator`
- GitHub project selection 中的 LLM 调用
- Provider 初始化逻辑

新增统一入口：

```python
def run_resume_pipeline(
    pdf_path: str,
    config: PipelineConfig,
    on_stage_update: Callable[[StageEvent], None] | None = None,
) -> PipelineResult:
    ...
```

禁止新 Web API 直接调用 `score.main()`。

## 5.3 Pipeline 阶段

统一阶段枚举：

```text
UPLOAD_VALIDATE
PDF_TEXT_EXTRACT
RESUME_SECTION_PARSE
GITHUB_ENRICH
RESUME_EVALUATE
RANK_AND_PERSIST
```

阶段状态：

```text
PENDING
RUNNING
COMPLETED
SKIPPED
FAILED
CACHED
```

Application 对候选人展示的粗粒度状态：

```text
SUBMITTED
PROCESSING
UNDER_REVIEW
CLOSED
```

Run 的细粒度状态：

```text
QUEUED
RUNNING
COMPLETED
FAILED
CANCELLED
```

处理逻辑：

1. 校验 PDF；
2. 保存文件；
3. 计算 SHA-256；
4. 创建 Evaluation Run；
5. 提交 LocalJobRunner；
6. 后台任务逐阶段更新 `stage_runs`；
7. 任何阶段失败时保存错误；
8. 成功后保存结果并重新计算排名；
9. Candidate 状态变为 `UNDER_REVIEW`。

## 5.4 Artifact 设计

每次 Run 创建独立目录：

```text
data/artifacts/<run_uuid>/
├── run_config.json
├── extracted_text.md
├── structured_resume.json
├── github_data.json
├── evaluation.json
└── error.json
```

SQLite 保存：

- 常用结构化结果以 JSON 字符串或 SQLAlchemy JSON 类型保存；
- Artifact 路径；
- Run 配置；
- Score 数值；
- 错误摘要；
- 阶段状态。

原始 PDF 保存为：

```text
data/uploads/<application_uuid>/<resume_file_uuid>.pdf
```

不得使用用户原文件名作为磁盘唯一标识。

## 5.5 Safe Reuse

P0 不实现复杂的逐阶段 Cache Store。采用完整 Run 安全复用：

```text
config_fingerprint =
SHA256(
  resume_sha256
  + model_id
  + temperature
  + top_p
  + prompt_version
  + pipeline_version
  + github_enrichment
)
```

当 `cache_policy=SAFE_REUSE` 且找到相同 fingerprint 的成功 Run：

- 创建新的 Run 记录或引用复用来源；
- 标记阶段为 `CACHED`；
- 复制结果快照；
- UI 明确显示 `Reused from Run #...`。

当 `FORCE_FRESH`：

- 不复用已有结果；
- 强制实际调用模型。

---

## 6. SQLite 数据模型

## 6.1 users

```text
id                  UUID PK
email               unique
password_hash
role                candidate | staff
display_name
is_active
created_at
```

不实现用户注册。只通过 seed 脚本创建 Demo 用户。

## 6.2 applications

系统默认只有一个固定招聘项目，因此不建立 jobs 表。

```text
id                  UUID PK
candidate_id        FK users
public_reference    APP-XXXXXX
candidate_status    SUBMITTED | PROCESSING | UNDER_REVIEW | CLOSED
staff_decision      NONE | ADVANCE | HOLD | ARCHIVE
staff_note
current_resume_id
latest_run_id
created_at
updated_at
```

每个 Candidate 默认只有一个 Application。

## 6.3 resume_files

```text
id
application_id
original_filename
storage_key
sha256
mime_type
size_bytes
uploaded_at
superseded_at
```

替换简历时：

- 创建新记录；
- 旧文件保留；
- `current_resume_id` 指向新文件；
- 自动创建新 Run；
- Candidate 只能看到当前文件；
- Staff 可以看到历史版本。

## 6.4 evaluation_runs

```text
id
application_id
resume_file_id
status
provider
model_id
temperature
top_p
prompt_version
pipeline_version
cache_policy
config_fingerprint
reused_from_run_id
github_enrichment
base_score
bonus_score
deduction_score
adjusted_score
below_cutoff
structured_resume_json
github_json
evaluation_json
error_code
error_message
queued_at
started_at
finished_at
created_by_user_id
```

评分定义：

```text
base_score =
  capped open_source
  + capped self_projects
  + capped production
  + capped technical_skills

adjusted_score =
  max(0, base_score + bonus_score - deduction_score)
```

排名使用 `adjusted_score`。

不要在 UI 中强行显示 `/100`，因为 Bonus 可能让调整后分数超过 100。使用：

```text
Priority score: 86.5
Base score: 82
Bonus: +6
Deductions: -1.5
```

## 6.5 stage_runs

```text
id
evaluation_run_id
stage_name
status
started_at
finished_at
duration_ms
summary
artifact_path
metadata_json
error_message
```

## 6.6 app_settings

```text
key
value_json
updated_at
updated_by
```

至少保存：

```text
default_model_id
default_prompt_version
review_cutoff
github_enrichment_default
```

Cutoff 是 Demo 配置项，不要硬编码到评分函数。

---

## 7. 登录和权限

## 7.1 Login UI

统一入口：

```text
/login
```

字段：

```text
Email
Password
Sign in
```

后端根据账户角色重定向：

```text
candidate → /candidate
staff     → /staff/applications
```

不提供角色选择按钮。

## 7.2 Demo 账户

Seed 以下账户，密码统一为 `demo123`，数据库中保存哈希：

```text
staff@demo.local
alice@example.com
bob@example.com
charlie@example.com
```

登录页底部可提供折叠的 `Demo accounts` 提示，但不要默认占据主视觉。

## 7.3 权限规则

Candidate：

- 只能读取自己的用户信息；
- 只能读取自己的 Application；
- 只能上传或替换自己的简历；
- 只能读取粗粒度状态；
- 不能访问 Evaluation、Score、Run、Model、Artifact、Staff API。

Staff：

- 可以读取全部 Application；
- 可以读取全部 Run；
- 可以查看 PDF 和 Artifact；
- 可以修改人工状态和备注；
- 可以修改默认模型；
- 可以触发重新运行；
- 可以使用 Demo Reset。

后端必须做真实 role 和 ownership 检查，不能只在前端隐藏按钮。

---

## 8. API 规范

统一前缀：

```text
/api
```

## 8.1 Auth

```http
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

`POST /login`：

```json
{
  "email": "alice@example.com",
  "password": "demo123"
}
```

推荐使用 HttpOnly Cookie 保存 token。

## 8.2 Candidate

```http
GET  /api/candidate/application
POST /api/candidate/resume
GET  /api/candidate/resume
GET  /api/candidate/status
```

上传要求：

- `multipart/form-data`；
- 只接受 `.pdf`；
- 校验 MIME；
- 最大 10 MB；
- 文件头必须为 PDF；
- 上传后立即返回，不等待评分完成。

响应：

```json
{
  "application_id": "...",
  "resume_file_id": "...",
  "run_id": "...",
  "status": "PROCESSING"
}
```

## 8.3 Staff Applications

```http
GET   /api/staff/applications
GET   /api/staff/applications/{application_id}
PATCH /api/staff/applications/{application_id}
GET   /api/staff/applications/{application_id}/resume
POST  /api/staff/applications/{application_id}/rerun
```

列表查询参数：

```text
search
candidate_status
staff_decision
below_cutoff
model_id
sort=score_desc|score_asc|submitted_desc|name_asc
page
page_size
```

## 8.4 Runs

```http
GET /api/runs/{run_id}
GET /api/runs/{run_id}/stages
GET /api/runs/{run_id}/artifact/{artifact_type}
GET /api/staff/applications/{application_id}/runs
GET /api/staff/applications/{application_id}/runs/compare?left=...&right=...
```

## 8.5 Models

```http
GET   /api/models
GET   /api/models/health
PATCH /api/staff/settings/default-model
GET   /api/staff/settings
```

模型列表响应至少包含：

```json
{
  "id": "gemma3:4b",
  "provider": "ollama",
  "configured": true,
  "installed": true,
  "healthy": true,
  "temperature": 0.1,
  "top_p": 0.9
}
```

## 8.6 Demo

只在 `DEMO_FEATURES_ENABLED=true` 时注册：

```http
POST /api/demo/reset
POST /api/demo/seed
GET  /api/demo/status
```

生产配置默认关闭。

---

## 9. 本机后台任务与前端进度

首版不使用 Celery 或 Redis。

实现一个 Backend 内置的 `LocalJobRunner`：

```python
class LocalJobRunner:
    def __init__(self, max_workers: int = 1):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit_evaluation(self, run_id: str) -> None:
        self.executor.submit(execute_evaluation_run, run_id)
```

默认：

```text
max_workers = 1
```

原因：

- 本机 4B 模型可能占用大量内存或显存；
- Demo 更重视稳定性而不是吞吐；
- 避免多个候选人同时评分导致系统卡死；
- 后续再根据机器能力调整到 2。

上传流程：

```text
POST resume
  → 保存 PDF
  → 创建 Evaluation Run: QUEUED
  → 提交 LocalJobRunner
  → 立即向前端返回 run_id
  → 后台线程逐阶段更新 SQLite
  → 前端轮询状态
```

前端轮询：

- Run 为 `QUEUED` 或 `RUNNING` 时，每 2 秒请求；
- 完成后停止；
- 页面隐藏时降低频率；
- 连续错误时指数退避；
- 超时后显示可恢复提示。

每个阶段必须：

- 开始前更新 SQLite；
- 完成后更新 SQLite；
- 捕获异常；
- 保存错误摘要；
- 不吞异常；
- 不留下永久 `RUNNING` 状态。

Backend 启动时：

- 检查上次异常退出留下的 `RUNNING` Run；
- 将其标记为 `FAILED_STALE`；
- Staff 可点击 `Rerun`；
- 不自动重复发送可能产生 API 费用的 DeepSeek 请求。

限制说明：

- FastAPI 进程重启会终止正在运行的本机线程；
- 该限制对课堂 Demo 可接受；
- 通过 SQLite 状态修复和 Rerun 保证可恢复；
- 报告中可将其列为当前单机实现限制。

---

## 10. 页面与交互

## 10.1 `/login`

结构：

```text
品牌标识
Hiring Agent
AI-assisted resume prioritization

Email
Password
Sign in

折叠 Demo accounts
```

要求：

- 单栏布局；
- 暖米白背景；
- 一个主要毛玻璃登录模块；
- 不添加岗位介绍；
- 登录失败给出明确错误；
- 不暴露账户是否存在的生产级细节不是本阶段重点，但错误文案保持统一。

## 10.2 `/candidate`

Candidate Workspace 只做一个页面。

内容：

1. 页面标题；
2. Application reference；
3. 当前状态；
4. PDF 上传区；
5. 已上传文件信息；
6. Replace Resume；
7. Application timeline；
8. Logout。

状态时间线：

```text
Application submitted
Resume received
Resume processing
Under human review
```

不得出现：

- Score；
- Rank；
- Model；
- Prompt；
- Internal stage；
- Cache；
- Staff decision；
- 其他候选人。

上传体验：

- Drag and drop；
- 选择文件；
- 上传进度；
- 文件校验错误；
- 上传成功后自动轮询状态；
- Replace Resume 必须二次确认。

## 10.3 `/staff/applications`

默认 Staff 首页，不单独制作复杂 Overview 首页。

页面结构：

```text
左侧 Sidebar
顶部标题和全局模型选择器
摘要指标
搜索与筛选
候选人排名表
```

Sidebar：

```text
RECRUITMENT
  Applications

AI LAB
  Experiments
  Models & Prompts
  System Runs

DEMO
  Demo Controls
```

P0 中 `Experiments` 主要承载 Run Compare，不实现攻击逻辑。

摘要指标：

- Total applications；
- Processing；
- Ready for review；
- Below cutoff。

表格字段：

```text
Rank
Candidate
Priority Score
Review Tier
Candidate Status
Staff Decision
Model
Updated
```

表格功能：

- 搜索；
- 排序；
- 状态筛选；
- 模型筛选；
- 点击整行进入详情；
- loading skeleton；
- empty state；
- failed run 标记。

## 10.4 `/staff/applications/[id]`

这是最重要的演示页面。

Desktop 推荐三列：

```text
左：PDF Preview
中：Structured Resume
右：Score / Evidence / Staff Actions
```

窗口较窄时改成：

```text
PDF | Resume Data | Evaluation | Run Details
```

Tabs 或两列布局。

必须展示：

- Candidate name；
- Application ID；
- Candidate status；
- Staff decision；
- Current model；
- Priority score；
- Base / Bonus / Deduction；
- 四个类别分数；
- 每类 evidence；
- Key strengths；
- Areas for improvement；
- PDF；
- Work / Education / Skills / Projects；
- GitHub signals；
- Advance / Hold / Archive；
- Staff note；
- Rerun；
- Compare runs；
- Advanced Run Details 折叠区。

Advanced Run Details：

- Run ID；
- Provider；
- Model；
- Temperature；
- Top-p；
- Prompt version；
- Pipeline version；
- Cache policy；
- Reused from；
- Stage timeline；
- Stage duration；
- Raw artifacts；
- Error details。

## 10.5 `/staff/experiments`

当前阶段做通用 Run 对比工具：

```text
选择 Application
选择 Left Run
选择 Right Run
Compare
```

对比内容：

- 模型配置；
- 总分；
- 分项分数；
- Bonus；
- Deduction；
- 排名；
- Evidence 文本；
- Structured resume 差异摘要；
- 各阶段耗时；
- Cache 状态。

不要实现攻击 Payload 编辑器。

为后续预留：

```text
experiment_type
attack_config
defense_config
```

但 P0 不在 UI 显示未完成的按钮。

## 10.6 `/staff/models`

展示：

- Provider；
- Model ID；
- Local / Cloud；
- Configured；
- Installed；
- Health；
- Temperature；
- Top-p；
- Set as default。

默认模型切换后只影响新 Run，不修改历史 Run。

模型不可用时：

- 禁止设为默认；
- 显示明确原因；
- 不让页面崩溃。

## 10.7 `/staff/runs`

列表字段：

```text
Run
Candidate
Status
Model
Cache
Duration
Started
```

功能：

- 状态筛选；
- 模型筛选；
- 打开详情；
- 失败 Run 重新运行；
- 查看错误。

---

## 11. Demo Mode

Demo Mode 不是第三套系统，而是 Staff Console 顶栏的唯一显示开关。

位置：

```text
Staff 顶栏右上角：Demo Mode OFF / ON
```

实现建议：

```text
/staff/applications?demo=1
```

前端以 URL 状态控制，刷新后仍能保持；后端业务逻辑和权限不因 Demo Mode 改变。

开启后：

- 只显示 Seed Demo 候选人；
- 隐藏非必要筛选；
- 放大 Pipeline、Score、Model 和 Compare；
- 显示演示步骤导航；
- Demo Controls 只提供操作，不再提供第二个 Enable/Disable 按钮；
- 不修改底层评分逻辑。

P0 Demo Controls：

- Reset Demo Data；
- Seed Demo Data；
- Open Candidate View；
- Open Staff View；
- Run Baseline；
- Compare Latest Runs。

明确删除：

- 页面正文中的 `Enable Demo Mode`；
- 页面正文中的 `Disable Demo Mode`；
- 尚未接入真实逻辑的 Attack/Defense 占位块；
- 与顶栏开关重复的状态卡片。

后续安全阶段再加入真实可用的：

- Apply Attack；
- Enable Defense；
- Attack vs Defense。

不要在功能未完成前显示假按钮。

---

## 12. Glass Editorial 视觉规范

最终风格名称：

> **Glass Editorial**

设计来源组合：

- A 模板的 Dashboard 信息架构；
- 克制的毛玻璃和模块层级；
- Wayrise 风格的大号衬线标题与留白；
- GenTac 风格的编号章节和连续实验叙事。

## 12.1 字体

推荐使用 `next/font` 自托管：

```text
Display / Editorial:
  Cormorant Garamond
  fallback: Georgia, Noto Serif SC, serif

UI / Body:
  Inter
  fallback: Noto Sans SC, system-ui, sans-serif

Technical:
  JetBrains Mono
  fallback: ui-monospace, monospace
```

使用规则：

- 页面 H1、H2、候选人姓名：Display；
- 表格、按钮、表单、说明：Inter；
- Run ID、模型参数、SHA、技术配置：JetBrains Mono；
- 不允许整张表使用衬线体；
- 不允许所有标题都超大。

## 12.2 色彩 Token

```css
:root {
  --page-bg: #F5F9FD;
  --page-bg-deep: #E7F0F8;

  --surface-nav: rgba(248, 252, 255, 0.62);
  --surface-card: rgba(255, 255, 255, 0.74);
  --surface-raised: rgba(255, 255, 255, 0.93);
  --surface-subtle: rgba(239, 247, 253, 0.54);

  --text-primary: #1D2B3A;
  --text-secondary: #607489;
  --text-soft: #8A9BAD;

  --accent-primary: #5B8FCA;
  --accent-primary-soft: rgba(91, 143, 202, 0.12);
  --accent-secondary: #6D9D9A;

  --border-soft: rgba(58, 91, 122, 0.14);
  --border-strong: rgba(58, 91, 122, 0.24);

  --success: #6D9D9A;
  --warning: #A57F49;
  --danger: #B45E68;
}
```

必须检查浅色背景下的文字对比度。必要时加深状态文字，不要为了“柔和”牺牲可读性。

## 12.3 毛玻璃层级

只使用三层，不允许所有卡片完全相同。

### Background

- 浅蓝白；
- 使用非常轻的冰蓝与青蓝 radial tint；
- 可选细微噪点；
- 禁止 Claude 风格的米色、陶土橙和棕黑主色；
- 禁止强烈蓝紫科技渐变。

### Navigation Surface

```text
透明度较高
blur 20px
边框轻
```

### Main Content Surface

```text
透明度中等
blur 12–16px
用于表格、PDF 周边、Resume Data
```

### Raised Control Surface

```text
接近不透明
用于 Model Selector、Run Detail、Dialog、Demo Controls
```

禁止：

- Card 套 Card 后每层都 blur；
- 大面积 glow；
- 高饱和蓝紫渐变；
- 过重阴影；
- 每个模块都画相同颜色条。

## 12.4 模块形态

混合使用：

- 玻璃面板；
- 无背景的编辑式章节；
- 细分隔线；
- 编号标记；
- 小型状态 pill；
- 局部进度轨迹；
- 表格行；
- 折叠详情。

不要把所有信息都装进独立圆角卡片。

## 12.5 页面标题

Staff 列表页：

```text
APPLICATIONS

Candidate
Review Queue
```

右侧或下方：

```text
AI-assisted prioritization for human review.
48 applications · 44 evaluated
```

Candidate Detail：

```text
APPLICATION / APP-0027

Alice
Chen
```

但标题区域总高度不能压缩核心工作区。

## 12.6 动效优先级

P0 只做：

- 150–200ms hover；
- focus 状态；
- dropdown/dialog 过渡；
- skeleton；
- 当前 Pipeline 状态轻微强调；
- 数字加载时避免 layout shift。

P2 再做：

- 页面淡入；
- stagger；
- 分数数字动画；
- Pipeline 脉冲；
- Attack / Defense 场景过渡；
- 复杂滚动叙事。

核心功能完成前禁止投入大量时间做动效。

---

## 13. 前端状态与错误处理

每个异步页面必须有：

- loading；
- empty；
- success；
- partial；
- failed；
- retry。

错误文案示例：

```text
The resume was uploaded, but evaluation failed during section parsing.
You can retry this run without uploading the PDF again.
```

禁止：

- 只显示 `500 Internal Server Error`；
- 无限 spinner；
- 后端失败后表格整页消失；
- 模型不可用时悄悄切换模型；
- 自动覆盖历史结果。

---

## 14. 本地开发体验

## 14.1 Python 环境

推荐使用项目级虚拟环境：

```bash
python -m venv .venv
```

激活：

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

安装：

```bash
pip install -r requirements.txt
pip install -r backend/requirements-web.txt
```

## 14.2 Backend 启动

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## 14.3 Frontend 启动

```bash
cd frontend
npm install
npm run dev
```

访问：

```text
http://localhost:3000
```

## 14.4 Ollama

先确认服务已启动：

```bash
ollama list
curl http://127.0.0.1:11434/api/tags
```

当前必须看到：

```text
gemma3:4b
```

## 14.5 本机启动脚本

创建：

```text
scripts/dev_local.ps1
scripts/dev_local.sh
```

脚本至少检查：

```text
Python venv
Backend dependencies
Frontend dependencies
Ollama reachable
gemma3:4b installed
.env exists
SQLite writable
```

脚本可以打开两个子进程：

```text
FastAPI
Next.js
```

不要自动下载模型，也不要自动发送 DeepSeek 付费请求。

## 14.6 `.env.example`

```env
APP_ENV=development
APP_SECRET=change-me
DATABASE_URL=sqlite:///./data/hiring_agent.db

UPLOAD_ROOT=./data/uploads
ARTIFACT_ROOT=./data/artifacts
MAX_PDF_SIZE_MB=10

OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:4b

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=
DEEPSEEK_MODEL=
DEEPSEEK_API_STYLE=openai_compatible

DEFAULT_MODEL=gemma3:4b
DEFAULT_PROMPT_VERSION=baseline-v1
DEFAULT_REVIEW_CUTOFF=20
LOCAL_JOB_MAX_WORKERS=1

FRONTEND_ORIGIN=http://localhost:3000
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api

DEMO_FEATURES_ENABLED=true
GITHUB_TOKEN=
```

注意：

- `.env` 必须加入 `.gitignore`；
- `.env.example` 不写真实 Key；
- DeepSeek 未配置时系统仍应完整支持 Gemma；
- 如果 DeepSeek Provider 的实际字段名称不同，只修改 Provider Adapter，不让前端依赖密钥细节。

---

## 15. Demo 数据

Seed 至少四个账户、五个申请。

建议数据角色：

```text
Alice Chen       strong profile
Bob Martin       medium profile
Charlie Kim      weak profile
Dana Patel       GitHub profile present
Evan Liu         one intentionally failed historical run
```

要求：

- Seed 脚本幂等；
- Reset 后恢复固定状态；
- Demo 文件放在 `demo_assets/`；
- 不使用真实个人敏感简历；
- Demo PDF 可以由团队自制或匿名化；
- 至少两份 PDF 使用相同原始文件名，验证 Web Storage 不混淆；
- Seed 结果固定，便于截图和录屏。

`reset_demo.py`：

- 删除 Demo 用户相关 Application、Run 和 Artifact；
- 不删除非 Demo 数据；
- 重新 Seed；
- 输出账户和页面入口。

---

## 16. 测试要求

## 16.1 Core Unit Tests

至少覆盖：

- PDF 不存在；
- 非 PDF；
- 空 PDF；
- JSON Resume 校验；
- 总分计算；
- Score cap；
- Bonus / Deduction；
- Config fingerprint；
- 相同 basename、不同内容不冲突；
- 相同内容、相同 config 可 safe reuse；
- 相同内容、不同模型不可复用；
- Force fresh 不复用。

## 16.2 API Tests

至少覆盖：

- Candidate 登录；
- Staff 登录；
- 未登录拒绝；
- Candidate 不能访问 Staff API；
- Candidate 不能读取其他 Candidate；
- Candidate 上传；
- 大文件拒绝；
- MIME 错误拒绝；
- Staff 列表；
- Staff 详情；
- Staff rerun；
- 默认模型切换；
- 模型不可用时返回可解释错误；
- Demo reset 只允许 Staff；
- Demo endpoint 在功能关闭时不存在或拒绝。

## 16.3 Local Job Runner Tests

对 Ollama 与 DeepSeek Provider 使用 mock：

- 正常完整流程；
- GitHub 缺失时 SKIPPED；
- 解析阶段失败；
- Evaluation 阶段失败；
- DB 状态正确；
- Backend 重启后的 stale Run 修复；
- Retry 后产生新 Run；
- 原 Run 不被覆盖。

## 16.4 E2E

使用 Playwright：

1. Candidate 登录；
2. 上传 PDF；
3. 看到 Processing；
4. Mock Local Job Runner 完成；
5. 看到 Under Review；
6. Candidate 页面没有 Score；
7. Staff 登录；
8. 看到 Candidate；
9. 打开详情；
10. 看到 PDF、分数和 Evidence；
11. 切换模型；
12. Rerun；
13. Compare 两个 Run；
14. Demo Mode 开关正常；
15. Reset Demo Data 正常。

---

## 17. 视觉验收

Agent 必须生成以下截图供人工检查：

```text
artifacts/ui/login-1440.png
artifacts/ui/candidate-1440.png
artifacts/ui/applications-1440.png
artifacts/ui/application-detail-1440.png
artifacts/ui/models-1440.png
artifacts/ui/run-compare-1440.png
artifacts/ui/candidate-mobile-390.png
```

检查项：

- 1440×900 无横向滚动；
- 1280 宽仍可用；
- Candidate 页 390px 宽不溢出；
- Staff 表格在窄屏合理降级；
- PDF 区不会挤压 Score 到不可读；
- 衬线字体只用于标题；
- 毛玻璃层级明显但不影响文字；
- 没有 stock shadcn 的默认组件外观；
- 浅蓝白配色与 HTML v2 一致；
- 没有一排完全相同的白卡片；
- 颜色状态不只依赖颜色；
- 按钮、Input、Select 有 focus；
- Empty 和 Error 页面视觉完整。

---

## 18. 分阶段执行顺序

虽然 UI 原型已提前完成，但真实系统仍必须按照 Core → Backend → Frontend Integration 的依赖顺序推进。

当前状态：

```text
Phase 0  基线冻结             未验证
Phase 1  Core Adapter         未开始
Phase 2  Backend / Local Job Runner  未开始
Phase 3A 静态 UI 原型         已完成
Phase 3B Next.js + API 融合   未开始
Phase 4  Candidate 联调       未开始
Phase 5  Staff 联调           未开始
Phase 6  Compare / Demo       未开始
Phase 7  QA                   未开始
```

Coding Agent 必须按顺序执行。每个阶段完成后：

1. 运行对应测试；
2. 更新 `DEV_PROGRESS.md`；
3. 列出新增文件；
4. 列出未解决问题；
5. 不在测试失败时继续扩大功能。

---

### Phase 0 — 基线冻结与审计

任务：

- 记录当前 Git commit；
- 成功运行原 CLI；
- 保存至少两份测试简历输出；
- 记录模型和环境；
- 增加最小 smoke test；
- 梳理 `PDFHandler`、GitHub enrichment、Evaluator 的调用签名；
- 不改 UI。

完成标准：

- 原 CLI 有可复现基线；
- 之后改造能比较结果；
- `DEV_PROGRESS.md` 建立。

---

### Phase 1 — Core Adapter 与模型注入

任务：

- 新增 `PipelineConfig`；
- 原 Core 支持显式 model/provider/options；
- 新增 `run_resume_pipeline()`；
- 拆开 PDF text extraction 和 section parsing 调用；
- 统一返回 `PipelineResult`；
- stdout 不再是 Web 结果来源；
- 保持 `score.py` 可运行；
- 添加 Core unit tests。

完成标准：

- CLI 仍可用；
- Python 代码可通过函数传入不同模型；
- 同进程连续运行两个模型不会互相污染；
- Pipeline 返回结构化结果。

---

### Phase 2 — Backend、SQLite、Storage 与 Local Job Runner

任务：

- FastAPI scaffold；
- SQLite models；
- Alembic migration；
- Local Storage；
- `LocalJobRunner`；
- Candidate/Staff auth；
- Seed 用户；
- Upload API；
- Evaluation Run；
- Stage Run；
- Model Registry；
- Safe Reuse；
- Rerun；
- Artifact API；
- 权限测试；
- Ollama Gemma Provider；
- DeepSeek API Provider Adapter。

完成标准：

- 上传请求快速返回；
- Local Job Runner 可完成真实或 Mock Pipeline；
- Backend 重启后 SQLite 数据仍在；
- stale Run 能被识别并恢复；
- Candidate 无法读取 Score；
- Staff 可读取完整 Run；
- 同名 PDF 不冲突；
- `gemma3:4b` 可真实评分；
- DeepSeek 未配置时显示 `Not configured`，不会导致系统启动失败。

---

### Phase 3 — Frontend 视觉骨架与迁移

**当前状态**：

```text
视觉设计：已完成
静态交互 HTML：已完成
Next.js 组件化：未完成
真实 API 接入：未完成
```

现有资产：

```text
hiring_agent_demo_template_v2_blue.html
```

任务：

- 将静态 HTML 复制到 `frontend_reference/` 作为只读视觉基准；
- 创建 Next.js scaffold；
- 迁移 Glass Editorial Blue tokens；
- 使用 `next/font` 或本地字体方案迁移字体；
- 拆分 Login、Candidate Workspace、Staff Shell、Sidebar、Topbar、Applications、Candidate Detail、Experiments、Models、Runs、Demo Controls；
- 先实现统一 Mock API Adapter，确认视觉一致；
- 再将 Mock API Adapter 替换为真实后端调用；
- 实现 Loading / Empty / Partial / Error 状态；
- 不重新设计 UI；
- 不恢复冗余 Demo Mode 模块。

完成标准：

- 核心页面与静态 HTML 基本一致；
- 1440px 截图视觉回归通过；
- 所有页面由 Next.js Route 提供；
- 页面不直接读取全局 Mock 数组；
- 数据全部通过 API Client 和 Query 层获得；
- 无 stock template 感；
- 不依赖动画掩盖布局问题。

---

### Phase 4 — Candidate 端完整联调

任务：

- 登录；
- 上传；
- 文件校验；
- Replace Resume；
- 状态轮询；
- 退出；
- 权限错误处理；
- 移动端适配。

完成标准：

- Candidate 完整流程可跑；
- 页面不显示任何内部评分信息；
- 上传后无需刷新；
- 后端失败时可恢复。

---

### Phase 5 — Staff 端完整联调

任务：

- Applications 排名表；
- 搜索、筛选、排序；
- Candidate Detail；
- PDF；
- Structured Resume；
- Score 和 Evidence；
- GitHub signals；
- Staff decision；
- Staff note；
- Advanced Run Details；
- Rerun；
- Models；
- System Runs。

完成标准：

- Staff 可以完成所有核心操作；
- 模型切换无需重启；
- 历史 Run 不被覆盖；
- 模型不可用时有明确提示。

---

### Phase 6 — Run Compare 与 Demo Mode

任务：

- Experiments 通用 Run Compare；
- Demo Mode URL 状态；
- Demo Controls；
- Seed；
- Reset；
- 演示步骤导航；
- 只显示 Demo 数据；
- Demo 验证脚本。

完成标准：

- 可在 15 分钟内完成 Candidate → Staff → Rerun → Compare；
- Reset 后状态一致；
- 不需要手动改数据库；
- 不显示尚未实现的攻击/防御按钮。

---

### Phase 7 — QA、视觉精修与文档

任务：

- 完整测试；
- Playwright；
- 截图；
- 修复可访问性；
- 修复响应式；
- 优化日志；
- README；
- 本机一键启动；
- 录屏 fallback；
- 演示 rehearsal。

完成标准：

- `python scripts/verify_local.py` 通过；
- 冷启动说明清楚；
- 网络断开且使用本地模型时可演示；
- 如果模型临时故障，Seed 的历史结果仍可浏览；
- 关键流程没有假数据硬编码在前端。

---

## 19. `python scripts/verify_local.py` 必须检查

脚本应自动检查：

```text
[ ] Python environment available
[ ] SQLite database path writable
[ ] Database schema current
[ ] FastAPI reachable
[ ] Frontend reachable
[ ] Ollama reachable
[ ] gemma3:4b installed
[ ] DeepSeek configured or explicitly skipped
[ ] Upload directory writable
[ ] Artifact directory writable
[ ] Demo users exist
[ ] Demo applications exist
[ ] At least one completed Evaluation Run
```

输出必须清楚指出修复命令。

---

## 20. 演示路线

推荐课堂 Demo 顺序：

### 1. Candidate View

- 登录 Candidate；
- 上传 PDF；
- 展示 Processing；
- 强调候选人看不到评分。

### 2. Staff Applications

- 切换 Staff；
- 展示排名；
- 展示 low cutoff 与 human review 定位。

### 3. Candidate Detail

- PDF；
- 结构化解析；
- GitHub signals；
- 四项分数；
- Evidence；
- Pipeline stages。

### 4. Model Switching

- 选择另一模型；
- Force Fresh；
- Rerun；
- 展示独立 Evaluation Run。

### 5. Run Compare

- 左右对比分数、Evidence、阶段耗时；
- 为后续 Attack/Defense 演示说明系统已经具备实验基础。

本阶段 Demo 应能独立获得 end-to-end system demonstration 的分数，即使攻击和防御模块尚未接入。

---

## 21. 最终验收清单

### Core

- [ ] PDF 上传、提取、解析、评分完整运行；
- [ ] GitHub enrichment 可选；
- [ ] 排名正确；
- [ ] Cutoff 可配置；
- [ ] 同名文件不混淆；
- [ ] 每次运行独立记录；
- [ ] 模型请求级注入；
- [ ] CLI 保持可用。

### Candidate

- [ ] 简单登录；
- [ ] 只能看自己；
- [ ] 上传和替换；
- [ ] 处理状态；
- [ ] 无 Score、Rank、Model 泄漏。

### Staff

- [ ] 查看全部候选人；
- [ ] 排序与筛选；
- [ ] PDF；
- [ ] Resume JSON 可读展示；
- [ ] Score；
- [ ] Evidence；
- [ ] 人工状态；
- [ ] 模型切换；
- [ ] Rerun；
- [ ] Run History；
- [ ] Compare；
- [ ] Stage Details；
- [ ] Error Details。

### Operations

- [ ] 本机 FastAPI 启动；
- [ ] 本机 Next.js 启动；
- [ ] SQLite 持久化；
- [ ] Local Job Runner；
- [ ] Ollama Gemma 3 4B；
- [ ] DeepSeek API 可选配置；
- [ ] 一键 Seed；
- [ ] 一键 Reset；
- [ ] `verify_local.py`；
- [ ] 本机日志清晰；
- [ ] `.env.example`；
- [ ] README。

### Visual

- [ ] Glass Editorial；
- [ ] 暖米白和陶土红；
- [ ] 衬线标题与无衬线 UI 分工；
- [ ] 三层玻璃表面；
- [ ] 模块不死板；
- [ ] 无模板感；
- [ ] 响应式；
- [ ] Error/Empty/Loading 完整；
- [ ] 动效不是核心依赖。

---

## 22. Agent 工作规则

1. 先读完整仓库和本文件。
2. 不要把原仓库描述成正式 ATS 产品。
3. 不要删除原 CLI。
4. 不要为了“架构优雅”一次性重写全部代码。
5. 不要在模型切换时修改进程全局变量。
6. 不要使用原文件名作为缓存或存储唯一键。
7. 不要只做前端隐藏，必须后端鉴权。
8. 不要将 API Key 发送到浏览器。
9. 不要覆盖历史 Run。
10. 不要在 P0 投入复杂动效。
11. 不要显示未实现的攻击和防御按钮。
12. 每阶段必须测试并更新进度文档。
13. 遇到原模型输出不稳定时，先保存 Raw Artifact，不要静默修正。
14. 新依赖必须写入 lockfile 和 README。
15. 当前阶段不要引入 Docker、PostgreSQL、Redis、Celery 或其他独立基础设施。
16. Gemma 通过本机 Ollama 调用；DeepSeek 只从 `.env` 读取配置。
17. 所有 UI 文案优先使用英文，以便课堂展示。
18. 代码注释和开发文档可使用英文。
19. 任何偏离本计划的重大决定必须写入 `DEV_PROGRESS.md` 的 `Architecture Decisions`。

---

## 23. 参考来源

- Upstream repository:  
  `https://github.com/interviewstreet/hiring-agent`

- Upstream README baseline:  
  `https://github.com/interviewstreet/hiring-agent#readme`

- UI reference — glass module direction:  
  `https://builderx.csdn.net/activity-site/gpassdev/index`

- UI reference — editorial typography and spacing:  
  `https://wayrise.github.io/`

- UI reference — sectioned visual storytelling:  
  `https://jyrao.github.io/GenTac/`

---

## 24. 下一阶段执行指令

将下面内容直接作为 Coding Agent 的主任务：

```text
你正在继续开发 interviewstreet/hiring-agent 的 Web Demo。

已知条件：
- UI 已经确定，不要重新设计。
- 视觉基准是 frontend_reference/hiring_agent_demo_template_v2_blue.html。
- 本机 Ollama 已安装 gemma3:4b。
- 用户稍后会在 .env 中提供 DeepSeek V4 API 的真实配置。
- 当前阶段只做本机单机运行。
- 不要使用 Docker、PostgreSQL、Redis、Celery 或独立 Worker。
- 使用 FastAPI + SQLite + LocalJobRunner + 本地文件系统。
- Demo Mode 只能通过 Staff 顶栏开关控制。
- 主配色保持浅蓝白。

按以下顺序执行：

A. 基线冻结
1. 记录当前 git commit。
2. 验证 score.py CLI。
3. 保存至少两份基线输入输出。
4. 创建或更新 DEV_PROGRESS.md。
5. 记录所有模型调用点、缓存点和文件输出点。

B. Core Adapter
1. 实现不可变 PipelineConfig。
2. 为 PDFHandler、ResumeEvaluator、GitHub enrichment 增加请求级
   model/provider/options 注入。
3. 新增 run_resume_pipeline() 和结构化 PipelineResult。
4. 保持 score.py CLI 兼容。
5. 使用 Mock Provider 测试同一进程连续运行两个模型配置。
6. 禁止修改全局 DEFAULT_MODEL 来切换模型。

C. 本机 Backend
1. 创建 FastAPI。
2. 使用 SQLite：data/hiring_agent.db。
3. 使用 SQLAlchemy 和 Alembic。
4. 实现 users、applications、resume_files、evaluation_runs、
   stage_runs、app_settings。
5. 文件使用 UUID 路径并计算 SHA-256。
6. 实现 Candidate/Staff 登录和后端鉴权。
7. 实现上传、Run、Stage、Artifact、Safe Reuse、Rerun。
8. 实现 LocalJobRunner，默认 ThreadPoolExecutor(max_workers=1)。
9. Backend 启动时将遗留 RUNNING 任务标记为 FAILED_STALE。
10. 不自动重试 DeepSeek 付费请求。

D. 模型 Provider
1. 先接通本机 Ollama：
   OLLAMA_BASE_URL=http://127.0.0.1:11434
   OLLAMA_MODEL=gemma3:4b
2. 启动时检查 /api/tags，确认 gemma3:4b 已安装。
3. 实现 DeepSeekProvider，但配置全部来自：
   DEEPSEEK_API_KEY
   DEEPSEEK_BASE_URL
   DEEPSEEK_MODEL
   DEEPSEEK_API_STYLE
4. DeepSeek 配置缺失时标记 Not configured，不影响 Gemma。
5. providers.json 是 allowlist，不能代替实际 Provider 健康检查。
6. 每个 Evaluation Run 保存 provider、model_id 和参数快照。

E. 前端真实嵌入
1. 将静态 HTML 拆为 Next.js Routes 和组件。
2. 先通过统一 Mock API Adapter 复现视觉。
3. 再替换为真实 API：
   auth → candidate → applications → detail → runs → models → demo。
4. 所有请求放在 frontend/src/lib/api。
5. 使用 TanStack Query 管理状态和 2 秒轮询。
6. 保留浅蓝白 Glass Editorial 视觉。
7. 不恢复正文中的 Enable Demo Mode 区块。
8. 生成 1440px 与 390px 截图做视觉回归。

F. 本机运行
1. 提供 scripts/dev_local.ps1 和 scripts/dev_local.sh。
2. 提供 .env.example。
3. 提供 scripts/verify_local.py。
4. README 说明三个启动步骤：
   Ollama → FastAPI → Next.js。
5. 不自动下载模型，不自动发送 DeepSeek 测试请求。

G. 联调验收
1. Candidate 上传 PDF 后立即获得 run_id。
2. 页面轮询并展示处理进度。
3. Staff 可查看真实 PDF、结构化简历、评分、Evidence 和 Pipeline。
4. 模型切换只影响新 Run。
5. 同一申请可用 Gemma 和 DeepSeek 创建独立 Run 并对比。
6. Candidate API 不得泄漏内部评分。
7. Demo Reset 恢复固定 Seed 数据。

每完成一个阶段先运行测试并更新 DEV_PROGRESS.md，
不要在失败状态下继续扩展功能。
```
