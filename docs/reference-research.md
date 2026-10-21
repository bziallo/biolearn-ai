# 参考项目调研记录

调研日期：2026-10-19。网络可用，以下仓库均通过 `git clone --depth 1` 实际克隆到 `work/refs/` 后检查；该目录已被 `.gitignore` 排除，不属于 BioLearn AI 的交付代码。

调研目的：理解同类学习工具的产品边界、后端分层、数据组织和测试方式，为 Phase 0 的技术选型提供依据。未复制任何项目的源代码。

## 1. PndaMan/cortex

- 仓库：<https://github.com/PndaMan/cortex>
- 检查提交：`6d205c6`（2026-08-05）
- 许可证：Apache-2.0
- 形态：Tauri 2 桌面应用，Svelte 5 前端，Rust 后端，本地 SQLite

### 观察到的结构

- 前端按 `views`、`components` 组织，覆盖仪表盘、资料、聊天、闪卡、测验、日历、分析等大量学习场景。
- Rust 侧按领域拆文件，如 `sync.rs`、`review.rs`、`vector.rs`、`asr.rs`、`analytics.rs`、`calendar.rs`。
- 数据采用 `Subjects → Topics → Sources` 层级，强调资料、嵌入和生成物都留在本地。
- 后台任务具有持久化状态，例如音频转写会重新入队仍处于 `ingesting` 的来源，以处理崩溃恢复。

### 对 BioLearn AI 的启发

- 本地优先不仅是数据库位置，还包括任务状态可恢复、导出与备份路径清晰。
- 资料组织需要显式的层级与来源身份，否则后续引用和复习无法稳定关联。
- 长流程应拆成可观察的状态机，而不是依赖一次 HTTP 请求完成全部工作。

### 不直接照搬

- Tauri/Rust 桌面形态与本阶段 Web 单仓库目标不同。
- 功能面很广，BioLearn AI 需要按阶段收敛，避免同时铺开录音、日历、分析等多个领域。

## 2. LRriver/NotebookLM-Lite

- 仓库：<https://github.com/LRriver/NotebookLM-Lite>
- 检查提交：`0fb41d0`（2026-07-10）
- 许可证：Apache-2.0
- 形态：React + Vite 前端，FastAPI 后端，pytest 测试

### 观察到的结构

- 后端明确分为 `api/routes`、`api/schemas`、`core/interfaces`、`core/services`、`core/workflows`、`domain`、`infrastructure`。
- 路由覆盖 sources、documents、chat、notes、artifacts、podcast、slide decks、config。
- `main.py` 注册版本化前缀（项目内为 `/api`）并配置 CORS，健康检查包含存储后端状态。
- 前端采用来源、聊天、Studio 三栏工作台；组件与测试同目录，使用 Vitest 与 Playwright。
- 依赖清单使用较宽的下界，未锁定精确版本，安装结果会随上游变化。

### 对 BioLearn AI 的启发

- HTTP 适配、业务服务、领域模型与基础设施应分层，避免路由直接承担解析、检索和生成。
- Pydantic 既用于 API 契约，也用于结构化生成结果，边界清晰。
- 测试应覆盖工作流而不只是路由 smoke test。

### 不直接照搬

- 不采用其未锁定的依赖策略；BioLearn AI 使用兼容范围并在 lockfile/虚拟环境中固定实际版本。
- 本阶段不引入 Docling、SeekDB、LangGraph 等重依赖，等资料链路需求明确后再评估。

## 3. amnaabdul/StudyMate-AI

- 仓库：<https://github.com/amnaabdul/StudyMate-AI>
- 检查提交：`40c2f50`（2026-10-14）
- 许可证：该提交的仓库根目录未发现 LICENSE 文件
- 形态：Python 3.12 + Streamlit 单体应用

### 观察到的结构

- `app.py` 负责界面与流程，`src/` 拆出 `text_chunker`、`embeddings`、`semantic_search`、`summarizer`、`quiz_generator`、`flashcards`、`llm`、`database`。
- 使用 PyMuPDF 提取 PDF、sentence-transformers 生成嵌入、Ollama 本地生成内容。
- SQLite 保存测验尝试、闪卡进度与闪卡牌组，使用参数化 SQL 与事务。
- 测试用临时数据库替换模块级路径，覆盖数据往返、替换、非法输入与初始化幂等性。

### 对 BioLearn AI 的启发

- 最小学习闭环是“资料 → 摘要/检索 → 测验/闪卡 → 进度”，产品价值不必等所有高级功能齐备。
- 存储层测试应验证非法输入不会破坏已有数据。
- 数据库路径必须可注入，测试不能碰真实用户数据。

### 不直接照搬

- Streamlit 把界面与业务流程耦合在一个进程内，不适合需要稳定 API 契约和可替换前端的项目。
- 由于未发现许可证文件，代码复用需谨慎；本调研只提炼设计思路。

## 4. devyanshyadav/librenote-ai

- 仓库：<https://github.com/devyanshyadav/librenote-ai>
- 检查提交：`7d8950b`（2026-08-23）
- 许可证：MIT
- 形态：Next.js 16 + TypeScript 全栈应用，Supabase/PostgreSQL，Drizzle ORM，Bun

### 观察到的结构

- 路由按 `notebooks`、`sources`、`chat`、`studio` 划分，Studio 再按 artifact 类型组织。
- 来源处理拆分为 PDF、Word、表格、纯文本、网页、YouTube、音频等工具模块。
- 前端使用多个领域 store（应用、仪表盘、聊天、引用、Studio），说明复杂工作台需要明确的状态边界。
- 提供 `.env.example`、初始化脚本、数据库 schema push 与安全说明，部署假设是 Docker + 本地 Supabase。

### 对 BioLearn AI 的启发

- 来源、对话、引用、Studio 产物应作为独立实体与 API 资源，而不是塞进一个“文档”表。
- 环境变量示例与一键初始化能显著降低本地启动成本。
- 引用状态独立建模，有助于实现“点击引用跳回原文”的可审计体验。

### 不直接照搬

- 本阶段不引入 Supabase、Docker 与 Drizzle；BioLearn AI 先用 SQLite 保持本地零依赖。
- 不在业务模型稳定前引入多个全局 store。

## 综合结论

1. **采用分层单体**：React SPA + FastAPI + SQLite，先保证边界与可测试性，再按需引入队列、向量库或外部服务。
2. **资料与引用是核心资产**：Phase 1 的模型必须为来源身份、片段定位和任务状态留出位置。
3. **本地优先需要可恢复性**：长流程不能只存在内存中，任务状态应持久化。
4. **测试围绕契约与状态**：后端验证 API 契约和迁移，前端验证加载/成功/失败状态。
5. **控制依赖面**：参考项目普遍引入较重的解析、向量与生成栈；BioLearn AI 在需求确认前不提前安装。

## 调研限制

- 仅检查默认分支的最新浅克隆，未审阅完整提交历史、issue 或运行时行为。
- 仓库结构反映作者当前选择，不代表唯一正确方案。
- StudyMate-AI 在检查提交中未发现许可证文件，不能据此推断授权条款。
