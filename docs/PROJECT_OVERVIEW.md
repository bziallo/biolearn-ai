# BioLearn AI 项目概览

## 1. 项目目标

BioLearn AI 是面向医学生与生命科学学习者的本地优先学习工作台：

1. 用学科和章节组织课程知识结构。
2. 导入 PDF、DOCX、PPTX、TXT、Markdown 资料。
3. 将资料解析为保留来源位置的文本分块。
4. 使用 AI 分阶段提取知识点，先形成待审核草稿。
5. 人工审核、编辑、合并并正式入库。

当前不包含认证、多用户、OCR、向量检索、问答、闪卡或题目生成。

## 2. 目标交接环境

- 下一开发环境：DSH
- 目标模型：DSH 中配置的 `DSF1017`
- 当前运行时 AI 配置的模型字段是 `deepseek-flash`，不是 DSF1017
- 当前没有 DSF1017 的真实连接、输出质量或成本验证记录
- API Key 只应由 DSH secret/环境配置或本机 AI 设置页注入，不能写入 Git

## 3. 架构

```text
React 19 + TypeScript + Vite
        │ JSON / multipart
        ▼
FastAPI /api/v1
  ├─ 学科/章节服务
  ├─ 文档上传、文件校验、解析、分块
  ├─ AI 配置与 OpenAI 兼容客户端
  ├─ 多阶段知识点提取/合并
  └─ 知识点审核与入库
        │ SQLAlchemy
        ▼
SQLite backend/data/biolearn.db
        ▲
        │
Alembic 迁移（0001–0009）

上传文件 → backend/data/uploads（服务器磁盘，不入库）
AI Key → backend/data/ai_config.json（服务器本地，已被 .gitignore 排除）
```

### 关键设计

- 前端只通过版本化 HTTP API 访问数据，不直接读数据库。
- 文件不存进数据库；数据库保存元数据、状态、分块和来源位置。
- 文件扩展名与实际内容签名双重校验，存储名由服务端 UUID 生成。
- PDF 按页、PPTX 按幻灯片、DOCX/Markdown 按标题结构分块。
- AI 输出先通过 Pydantic 校验；页码/幻灯片由系统从 chunk 注入，不信任模型。
- AI 结果先进入 `pending` 草稿，人工审核通过才写 `published_at`。
- 重新提取只替换未审核 AI 草稿，保留已审核/人工知识点。
- AI 任务支持协作式停止：`cancel_requested` + `cancelling`/`cancelled` 状态；停止不会保存本次新草稿。

## 4. 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 19.3、TypeScript 5.9、Vite 8、React Router 7、Vitest 4、Testing Library、ESLint 10 |
| 后端 | Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、SQLite |
| 解析 | pypdf、python-docx、python-pptx、标准库文本/Markdown 解析 |
| AI | HTTPX + OpenAI 兼容 `/chat/completions` |
| 测试 | pytest、FastAPI TestClient（HTTPX/httpx2）、Vitest |
| 包管理 | pnpm、pip + venv |

## 5. 目录结构

```text
backend/
  alembic/versions/       0001 基线 → 0002 学科章节 → 0003 初始学科
                          → 0004 文档/分块/任务/知识点 → 0005 审核备注
                          → 0006 任务取消标记 → 0007 智能导入/偏好/章节来源
                          → 0008 外部 AI 导入字段/任务计时
                          → 0009 题库/出题任务/练习记录
  app/api/v1/             health、imports、subjects、chapters、documents、knowledge、ai
  app/core/               Settings、枚举、DomainError
  app/db/                 SQLite 引擎、会话、外键 PRAGMA、声明式基类
  app/models/             Subject、Chapter、Document、DocumentChunk、
                          KnowledgeExtractionJob、KnowledgePoint、
                          ImportPreferences、ImportJob
  app/schemas/            API 与 AI 输出的 Pydantic 契约（含 imports）
  app/services/           parsing、chunking、documents、importing、ai_client、
                          ai_config、knowledge、knowledge_review、
                          knowledge_common、mappers、recovery
  app/main.py             FastAPI 应用、CORS、错误处理、启动恢复
  tests/                  75 项后端测试（2026-10-19 验证）
  data/                   SQLite、上传文件、AI 运行时配置（全部忽略）
frontend/
  src/pages/              首页、智能导入、学科、学科详情、资料库、
                          知识点审核、AI 设置
  src/components/         上传卡、知识树、表单、模态框、Toast、确认框
  src/lib/api/            typed fetch 与导入/文档/知识点/AI API
  src/lib/                章节树、知识点树、格式化、Toast hook
docs/                     架构、调研、交接文档
outputs/                  验收截图
```

## 6. 数据模型

| 表 | 作用 |
| --- | --- |
| `subjects` / `chapters` | 学科和任意层级章节，稳定 UUID |
| `documents` | 资料元数据、存储名、SHA-256、状态、解析错误/警告 |
| `document_chunks` | 稳定 chunk、顺序、标题路径、正文、页码/幻灯片、字符范围 |
| `knowledge_extraction_jobs` | AI 阶段、进度、错误、尝试次数、提取/合并计数 |
| `knowledge_points` | AI/人工知识点、来源、引文、置信度、审核状态、审核备注 |
| `import_preferences` | 默认学科/章节、默认模式、自动分析、预览确认、不确定策略 |
| `import_jobs` | 导入阶段、进度、结构建议、归档结果、外部 JSON payload、重复策略、AI 分析状态、计时 |
| `knowledge_points` 外部字段 | `importance`、`prerequisites`、`external_id` |
| `questions` | 题型、题干、JSON 选项/答案/评分规则、难度、审核、重复标记、来源 |
| `question_generation_jobs` | AI 出题请求、阶段、错误、取消、尝试次数、耗时 |
| `question_knowledge_points` | 题目与知识点的真实多对多关联 |
| `practice_sessions` / `practice_answers` | 练习筛选、抽题 ID、用户答案、判分/人工评分、快照 |

`chapters` 还记录自动建章来源：`source_document_id`、`source_import_job_id`、`source_slide`。`knowledge_extraction_jobs.timings` 记录分析/提取/合并/保存耗时。

所有结构变更必须通过 Alembic；当前 head 是 `0009_question_bank`。

## 7. 主要流程

### 资料导入

```text
multipart upload
→ 扩展名白名单 + 大小/空文件检查
→ 写入服务端 UUID 文件
→ 实际内容签名校验
→ SHA-256 重复检测
→ documents 状态 uploaded
→ BackgroundTasks 解析
→ document_chunks + status parsed
```

### 智能导入（0007）

```text
POST /imports（文件 + 学科 + 模式 + 选项）
→ documents.uploaded + import_jobs.queued
→ 解析（复用 documents.process_document）
→ 结构识别（PPT 目录/编号/标题；DOCX/MD 标题；PDF 回退）
→ 章节匹配（同父级同名复用；相似/异父级待确认）
→ 预览确认（可配置）或自动建章
→ 单事务写入章节 + 资料归属（来源资料/导入任务/幻灯片）
→ 可选创建 AI 任务并运行
→ import_jobs.completed / failed / awaiting_confirmation
```

### 外部 AI JSON 导入（0008）

```text
POST /imports/external（JSON + 学科 + 重复策略）
→ JSON 解析 + Pydantic schema_version 1.0 校验
→ 匹配学科/章节，生成预览（数量/重复/来源异常）
→ import_jobs.awaiting_confirmation + 原始 JSON 存盘 + payload 入库
→ 用户确认
→ 单事务创建/复用章节 + 写入 pending 知识点
→ 复用现有审核页；不启动网页 AI
```

### AI 知识点

```text
整章结构分析
→ 逐块提取（有界并发，默认 3；timings 记录耗时）
→ 引文与原文逐字校验
→ 分批/递归全章合并
→ 服务端去重与来源 ID 校验
→ pending 草稿
→ 人工审核/编辑/合并
→ approved + published_at 正式入库
```

### 题库与 AI 出题（0009）

```text
选择学科/章节/approved 知识点/题型/题量/难度
→ question_generation_jobs.queued
→ 有界批量调用模型（最多 4 次，单次最多 20 题）
→ Pydantic + 选项/答案/题型/知识点归属校验
→ 题干去重（已有/同批）
→ 一次性写入 pending 题目 + question_knowledge_points
→ 人工通过/拒绝/需修改/编辑/重新生成
→ approved 才可被练习抽取
```

### 练习

```text
选择范围（只查 approved）
→ practice_sessions + 抽题 ID
→ 用户提交答案
→ 单选/多选/判断自动判分；简答 pending 人工评分
→ practice_answers 保存答案、判分、快照、时间
→ 错题本按 is_correct=false 聚合；错题再练创建新会话
```

## 8. 重要限制

- 无 OCR；扫描版 PDF 只能标记 `needs_ocr`。
- 旧版 `.ppt` 不支持，只支持 `.pptx`。
- 复杂 PDF 表格/版式不能保证视觉还原。
- 当前没有 DSF1017 真实联调记录。
- 当前没有持久任务队列；服务重启会把运行中任务标记失败，需要重试。
- AI 出题只做结构一致性校验，题目事实正确性仍需人工审核；所有 AI 题默认 pending。
- 练习题按章节精确过滤，不自动包含子章节；简答题只有人工评分；未开发掌握度/间隔复习。

## 9. 交接文档索引

- [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md)
- [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md)
- [AI_HANDOFF.md](AI_HANDOFF.md)
- [architecture.md](architecture.md)
- [reference-research.md](reference-research.md)
