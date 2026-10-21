# BioLearn AI V1.0

BioLearn AI 是面向医学生与生命科学学习者的本地优先知识工作台：资料可追溯，回答有出处，学习进度保存在自己的数据库里。

**V1.0 已完成功能冻结**：学科/章节 → 课件导入与智能归档 → AI 知识点提取或外部 JSON 导入 → 知识点审核 → AI 出题或手动建题 → 题目审核 → 练习判分 → 错题复盘，数据全部保存在本机 SQLite。

```text
上传资料 → 解析文件 → 识别 PPT/文档结构 → 匹配或创建章节
→ 预览确认（可配置） → 归档资料 → 可选自动 AI 分析
→ 整章分析 → 分块提取 → 全章合并去重 → 待审核知识点 → 人工审核
→ 题库生成/录入 → 题目审核 → 练习判分 → 错题与答题记录
```

学科、章节、资料、分块、AI 任务、知识点、题目和练习记录全部使用真实后端 API 与 SQLite，不是前端假数据。

**快速开始：`install.bat` → `start.bat` → 打开 `http://127.0.0.1:8000/`**（详见“Windows 本地部署”）。

## 交接状态（2026-10-21，V1.0）

本项目准备交接给 DSH，目标模型为 DSH 中配置的 **DSF1017**。当前仓库没有提交记录，分支为 `main`，所有源码/文档仍是未跟踪状态；交接文档见：

- [PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)
- [DEVELOPMENT_STATUS.md](docs/DEVELOPMENT_STATUS.md)
- [DEVELOPMENT_RULES.md](docs/DEVELOPMENT_RULES.md)
- [AI_HANDOFF.md](docs/AI_HANDOFF.md)

**交接时与接管期间的真实数据。** 资料 `4c4a5a20-1ddd-4e90-865a-966edc191536`（第二章第三节-蛋白质的分子结构）已解析为 66 个分块；任务 `b060e7e8-03a4-4130-8f15-918dd6bb8afc` 于本地时间 20:23:54 完成，从 252 条候选中合并出 39 条知识点；这些知识点已在 20:39 全部审核通过。之后又启动过一次重复识别（任务 `594fe265-6f48-4073-a704-9d98a2471395`），已在 44% 时停止并标记为 `cancelled`，没有生成新草稿。

用户随后通过智能导入上传了 PPTX `第二章第一节`，解析为 51 个分块，创建章节 `第二章第一节`，并完成一次 AI 提取（任务 `a4ed602f-90eb-4b48-916d-dae40a11ee52`，180 条候选，39 条待审核知识点）。当前数据库共有 **2 份资料、117 个分块、6 个章节、78 个知识点（39 已通过 + 39 待审核）、3 个 AI 任务、1 个导入任务**。不要删除这些资料、章节、知识点或任务记录。

当前运行时 AI 配置存在，状态接口显示模型字段为 `deepseek-flash`，密钥保存在被忽略的 `backend/data/ai_config.json`。这不是 DSF1017；本次接管期间完成的这次任务是用户此前触发的，使用的是该运行时配置，没有 DSF1017 的真实联调记录。交接时不要读取、复制或提交该文件中的密钥。

## 已完成能力

| 能力 | 状态 |
| --- | --- |
| 学科与章节管理 | 可用 |
| 统一智能导入（预设章节 / 自动建章 / 智能归档） | 可用 |
| 外部 AI 预处理 JSON 导入（schema_version 1.0 + 预览确认） | 可用 |
| 网页 AI 分析并发提取、阶段计时与部分失败重试 | 可用 |
| 导入偏好持久化（默认学科/章节/模式/自动分析/预览/不确定策略） | 可用 |
| PDF / DOCX / PPTX / TXT / Markdown 上传 | 可用 |
| 文件签名、扩展名、大小、空文件校验 | 可用 |
| 服务器存储 + SHA-256 重复检测 | 可用 |
| 按页/幻灯片/标题结构解析 | 可用 |
| 页码、幻灯片、字符范围、标题路径追踪 | 可用 |
| 扫描版 PDF 检测与 OCR 能力提示 | 可用 |
| 文档处理状态、失败原因、重试 | 可用 |
| OpenAI 兼容 AI 配置与连接测试 | 可用 |
| 整章结构分析 → 分块提取 → 全章合并 | 可用 |
| AI 输出 Pydantic 结构化校验 | 可用 |
| AI 草稿审核树、编辑、批量审核、合并 | 可用 |
| 重新提取时保护已审核/人工知识点 | 可用 |
| 停止运行中的 AI 识别 | 可用（协作式停止） |
| 任务状态持久化与重启恢复 | 可用 |
| 题库管理与人工审核 | 可用 |
| 从已审核知识点 AI 出题 | 可用（生成题目默认待审核） |
| 基础练习、自动判分、错题本 | 可用 |
| 后端 pytest | 110 项通过 |
| 前端 Vitest | 30 项通过 |

## 技术栈

- 前端：React 19、TypeScript 5.9、Vite 8、React Router 7、Vitest 4、Testing Library、ESLint 10
- 后端：Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、SQLite
- 文档解析：pypdf、python-docx、python-pptx、标准库文本/Markdown 解析
- AI 调用：HTTPX + OpenAI 兼容 `/chat/completions`
- 测试：pytest + FastAPI TestClient（HTTPX/httpx2）
- 包管理：pnpm（前端）、pip + venv（后端）

## 目录结构

```text
.
├─ backend/
│  ├─ alembic/versions/
│  │  ├─ 0001_initial.py
│  │  ├─ 0002_subjects_chapters.py
│  │  ├─ 0003_seed_initial_subjects.py
│  │  ├─ 0004_documents_and_knowledge.py
│  │  ├─ 0005_knowledge_review_note.py
│  │  ├─ 0006_job_cancellation.py
│  │  ├─ 0007_smart_import.py
│  │  ├─ 0008_external_import.py
│  │  └─ 0009_question_bank.py
│  ├─ app/
│  │  ├─ api/v1/               # health、subjects、chapters、documents、knowledge、ai
│  │  ├─ core/                 # 配置、枚举、DomainError
│  │  ├─ db/                   # SQLAlchemy、会话、SQLite 外键
│  │  ├─ models/               # Subject、Chapter、Document、Chunk、Job、KnowledgePoint
│  │  ├─ schemas/              # Pydantic API/AI 契约
│  │  ├─ services/             # 解析、分块、AI、文档、知识点业务
│  │  └─ main.py
│  ├─ data/
│  │  ├─ biolearn.db           # SQLite（已忽略）
│  │  └─ uploads/              # 上传文件（已忽略）
│  ├─ tests/
│  ├─ alembic.ini
│  └─ pyproject.toml
├─ frontend/
│  ├─ src/
│  │  ├─ components/           # 上传卡、知识树、表单、模态框、Toast
│  │  ├─ layouts/
│  │  ├─ lib/api/              # typed API 客户端
│  │  ├─ lib/                  # 章节/知识点树工具、格式化
│  │  ├─ pages/                # 学科、资料库、知识点审核、题库、练习、首页
│  │  ├─ router.tsx
│  │  └─ styles.css
│  └─ ...
├─ docs/
│  ├─ architecture.md
│  └─ reference-research.md
├─ outputs/                    # 验收截图
├─ .env.example
├─ .gitignore
└─ README.md
```

## 数据库与存储

- 数据库：SQLite
- 文件：`backend/data/biolearn.db`
- 当前迁移 head：`0009_question_bank`
- 上传文件：`backend/data/uploads/`（由 `UPLOAD_DIR` 配置）
- 文件只保存到服务器磁盘，数据库保存文件名、存储名、大小、哈希、格式、状态、解析时间等元数据
- `.env`、`*.db`、`backend/data/*`、上传目录、虚拟环境、构建产物均被 `.gitignore` 排除

新增表：

- `documents`：资料元数据、状态、解析错误、页数/幻灯片数、SHA-256
- `document_chunks`：稳定 chunk ID、顺序、标题路径、文本、页码/幻灯片、字符范围
- `knowledge_extraction_jobs`：AI 阶段、进度、错误、尝试次数、统计
- `knowledge_points`：名称、类型、解释、要点、条件、来源、引文、置信度、审核状态、审核备注
- `import_preferences`：默认学科、默认章节、默认模式、自动分析、预览确认、不确定策略
- `import_jobs`：导入阶段、进度、结构建议、归档结果、AI 分析状态和错误
- `import_jobs` 新增外部 AI 字段：`source_type`、`payload`、`duplicate_strategy`、`timings`
- `knowledge_points` 新增外部 AI 字段：`importance`、`prerequisites`、`external_id`
- `knowledge_extraction_jobs` 新增 `timings`（分析/提取/合并/保存耗时）
- `chapters` 新增来源字段：`source_document_id`、`source_import_job_id`、`source_slide`
- `questions`：题型、题干、JSON 选项/答案/评分规则、解析、难度、审核状态、来源、重复标记
- `question_generation_jobs`：AI 出题请求、阶段、进度、错误、取消、尝试次数和耗时
- `question_knowledge_points`：题目与一个或多个知识点的真实多对多关联
- `practice_sessions`：学科/章节、筛选条件、抽题 ID、得分和完成状态
- `practice_answers`：用户答案、判分、评分方式、题目快照和作答时间

删除策略：

- 删除资料默认拒绝，如果已有关联知识点；确认后 `?cascade=true` 会删除资料、分块、AI 任务和关联知识点，并删除磁盘文件。
- 删除知识点默认拒绝，如果有后代；确认后级联删除整棵子树。
- 删除学科/章节沿用阶段二策略；资料通过外键处理。

## 支持的文件格式与限制

| 格式 | 解析方式 | 来源位置 |
| --- | --- | --- |
| PDF | pypdf 按页提取文字 | 页码、文本顺序 |
| DOCX | python-docx 保留标题/段落/表格 | 标题层级、段落、字符范围 |
| PPTX | python-pptx 按幻灯片提取标题/文本框/表格 | 幻灯片编号 |
| TXT | 编码识别 + 段落/标题启发式 | 标题路径、字符范围 |
| MD/Markdown | 标题、列表、表格、代码块结构解析 | 标题路径、字符范围 |

默认限制：

- 单文件最大 25 MB（`MAX_UPLOAD_BYTES`）
- 仅允许 `.pdf`、`.docx`、`.pptx`、`.txt`、`.md`、`.markdown`
- 空文件、内容签名与扩展名不匹配、旧版 `.ppt` 会被拒绝
- 扫描版 PDF 如果提取不到可读文字，会标记为 `needs_ocr` 并提示“当前未启用 OCR”，不会继续 AI 提取
- 文件名会被清理，存储名由服务端 UUID 生成，防止路径穿越

## AI 配置

可以直接在页面输入，不需要手改 `.env`：

打开 `http://127.0.0.1:5173/settings/ai`，填写：

- 提供商类型（OpenAI / OpenAI 兼容 / 自定义兼容网关）
- API Base URL（通常包含 `/v1`）
- 模型名称
- API Key

保存后 Key 只写入后端本地文件 `backend/data/ai_config.json`，权限尽量限制为仅当前用户可读；该目录已被 `.gitignore` 排除。页面只显示“Key 已保存”，不会回显 Key，也不会把 Key 放进任何 API 响应。

也可以继续使用环境变量作为回退：

```dotenv
AI_PROVIDER=openai-compatible
AI_API_BASE=https://your-provider.example/v1
AI_API_KEY=
AI_MODEL=DSF1017
AI_CONFIG_PATH=./data/ai_config.json
AI_TIMEOUT_SECONDS=90
AI_MAX_RETRIES=2
AI_EXTRACTION_CONCURRENCY=3
```

真实 Key 由 DSH secret 注入，或在 `/settings/ai` 页面填写；不要写进 README、`.env.example` 或 Git。

要求：

- `AI_API_BASE` 指向 OpenAI 兼容 API 的基础地址，通常包含 `/v1`
- 客户端调用 `POST {AI_API_BASE}/chat/completions`
- 连接测试调用 `GET {AI_API_BASE}/models`
- 支持 429/5xx/超时的有限重试与 `Retry-After`
- 只有 `AI_API_BASE`、`AI_API_KEY`、`AI_MODEL` 都有值时，状态才显示已配置
- 页面保存的配置优先于环境变量；删除页面配置后回退到环境变量
- 未配置时不会生成伪造结果

配置后可直接在 AI 设置页测试，或打开知识点审核页：

- 点击“测试模型连接”
- 点击“开始 AI 识别”
- 页面轮询 `/knowledge-jobs/{id}` 显示结构分析、分块提取、合并和进度

当前运行时已有用户保存的 AI 配置，但模型字段是 `deepseek-flash`，不是目标 DSF1017。接管验证期间，该配置真实完成了一次 66 分块的合并任务并生成 39 条知识点（已由用户审核通过）；之后的一次重复识别已停止并标记为 `cancelled`。这只能证明 `deepseek-flash` 的现有调用链可用，不能替代 DSF1017 联调。切换模型前先备份现场。

## 智能导入规则

入口：`/import`。默认设置保存在 SQLite 表 `import_preferences`，刷新页面或重启后仍然有效。

### 三种模式

- **归入预设章节**：使用默认学科/章节；本次显式选择优先。没有默认学科时要求先选择或保存一次默认设置。
- **自动识别并建章**：对 PPTX 优先读取目录页、编号标题、幻灯片标题和正文；对 DOCX/Markdown 读取标题层级；PDF 只建议资料标题章节。自动创建缺失章节，章节顺序遵循识别顺序。
- **智能归档**：优先复用学科内、同一父级下的同名章节；同名但父级不同或名称相似时标记为待确认，避免重复建章；无匹配时按模式创建。

### 识别与安全规则

- 每个识别出的章节尽量记录来源幻灯片编号；自动创建的章节记录 `source_document_id`、`source_import_job_id`、`source_slide`。
- PPT 没有清晰目录或编号标题时，只建议一个资料标题章节，不把普通幻灯片标题批量当成章节。
- 同一父级同名章节复用；不同学科允许同名；不会跨学科关联父章节，也不会产生循环。
- 同一文件在同一学科重复导入会返回已有资料，不重复创建章节；不同学科可以分别导入。
- 章节创建在单一事务中完成；中途失败会回滚全部新章节，保留已解析资料并显示错误。
- 默认设置中的“预览确认”开启时，自动建章会先进入 `awaiting_confirmation`，确认后才保存章节关联。
- 不确定策略：`confirm` 等待确认；`use_default` 使用默认章节或学科根目录；`create` 按建议继续，但同名/相似章节仍优先复用，避免重复建章。
- 自动 AI 分析在归档成功后启动；停止 AI 只停止分析，不会删除已导入文件或章节。

当前识别以确定性规则为主，没有调用模型做学科/章节语义分类；无法可靠推断时使用用户选择的学科或待确认状态，不擅自放入错误学科。

## 外部 AI 预处理导入

入口：`/import` → “导入 AI 预处理 JSON”。网页同时提供“查看导入模板”，可从后端 `GET /imports/external/template` 获取与校验规则一致的提示词、JSON Schema 和示例。

### 交换格式（schema_version 1.0）

```json
{
  "schema_version": "1.0",
  "document": {"name": "资料名", "type": "pptx", "summary": "可选"},
  "subject": {"id": null, "name": "生物化学"},
  "chapter_tree": [
    {"name": "第一章", "source_slide": 2, "children": [{"name": "第一节", "source_slide": 5}]}
  ],
  "knowledge_points": [
    {
      "point_id": "稳定外部标识",
      "title": "知识点名称",
      "content": "详细说明",
      "chapter_path": ["第一章", "第一节"],
      "category": "structure",
      "importance": "high",
      "key_terms": ["关键词"],
      "source": {"document_name": "资料名", "slide": 5, "page": null, "quote": "原文引文"},
      "prerequisites": ["前置知识点"],
      "confidence": 0.9
    }
  ],
  "metadata": {"model": "外部模型", "generated_at": "2026-10-19T12:00:00Z", "shard_index": 1, "shard_total": 1}
}
```

- 后端用 Pydantic 校验；未知 `schema_version`、字段缺失、JSON 语法错误、超大文件都会返回明确错误。
- 不需要外部 AI 生成数据库 ID；`subject.id` 可复用已有学科，否则按名称匹配；章节和知识点由导入服务映射/创建。
- `chapter_path` 可以是空数组（归入资料根章节）；最多 8 层。
- 长课件可按 shard 输出多个 JSON；每个分片保持相同 `chapter_tree`，用稳定 `point_id` 去重；当前按文件逐个导入，重复项默认跳过。
- `source` 缺少页码/幻灯片时仍可导入，但会标记待审核并显示警告，不伪造来源。

### 导入与预览

```text
上传 JSON → 解析 → Pydantic/Schema 校验 → 匹配学科/章节
→ 预览章节树、知识点数量、重复项、来源异常
→ 用户确认 → 单事务创建/复用章节 + 写入待审核知识点
→ 复用现有知识点审核页
```

- 外部知识点默认 `pending`、`origin=ai`、`needs_review=true`、`source_quote_verified=false`。
- `duplicate_strategy=skip`（默认）跳过重复；`update_pending` 只更新同一资料下未审核的 AI 草稿，已通过/需修改/已忽略/人工知识点永不覆盖。
- 同一 JSON 文件重复导入会显示重复预览，不直接重复写入。
- 原始 JSON 存到上传目录，文件元数据和 SHA-256 存在 `documents`；完整校验后的 payload 存在 `import_jobs.payload`，便于审计。
- 外部 JSON 导入不启动网页 AI 分析（没有解析分块），而是直接进入人工审核。

## 知识点闭环审查结论

- 网页 AI 分析与外部 JSON 导入都写入同一张 `knowledge_points` 表，使用同一套 `knowledge_review` API 和 `/documents/{id}/review` 审核页。
- 已支持知识点树/列表、详情、编辑、逐题/批量审核、需修改、忽略（拒绝）、合并和删除保护。
- 已补搜索/筛选：`GET /knowledge-points` 支持 `q`、`point_type`、`origin`、`needs_review`、`review_status`、`subject_id`、`chapter_id`、分页；审核页增加名称/解释搜索和审核状态筛选。
- 已修复真实缺口：编辑已通过知识点的内容会重新置为 `pending`，清空 `published_at`，必须再次审核后才能用于正式出题；只改层级不会强制重审。
- 来源信息真实存储并可查看：资料、章节、页码/幻灯片、来源 chunk、引文以及外部 AI locator。
- 重复检测：AI 草稿会标记 `duplicate_of_id`；审核页可合并；外部 JSON 默认跳过重复，可选择只更新未审核 AI 草稿；已通过/人工内容不会被覆盖。
- 取消、失败重试、数据库持久化和事务回滚已有测试；本次未重复实现这些能力。

## 题库与智能练习

### 数据模型

- 题型：`single_choice`、`multiple_choice`、`true_false`、`short_answer`。
- `options`、`answer`、`grading_rule` 都是 JSON：不再把选项和答案拼进一个字符串，后续可扩展评分规则。
- 题目通过 `question_knowledge_points` 关联一个或多个知识点；同时保存学科、章节、来源资料、来源定位、AI 服务/模型和重复标记。
- 状态：`pending`、`approved`、`rejected`、`needs_revision`；生成/编辑后默认待审核，只有 `approved` 才能被正式练习抽中。
- 练习记录保存 `practice_sessions` 和 `practice_answers`；答案保存题目快照，方便题目后续变更时审计。

### AI 出题

```text
选择学科/章节/已审核知识点/题型/题量/难度
→ 后端校验知识点必须是 approved
→ 有界批量调用模型（最多 4 次调用，单次最多 20 题；JSON 模式可自动降级）
→ 稳健 JSON 提取（纯 JSON / ```json / JSON 前后有解释文字）
→ 字段归一化（判断题 answer 布尔、选择题 answer 列表/字符串、选项字典/列表、题型同义词）
→ Pydantic 校验 + 本题语义校验
→ 校验选项 key/文本唯一、答案 key 存在、单选仅一个答案、判断题布尔值、简答参考答案
→ 校验知识点归属和题型是否符合请求
→ 题干去重（已有题目/同批重复跳过）
→ 一次性写入 pending 题目
```

- 出题知识点支持搜索、全选当前范围、全选筛选结果、清空和反选，适合一次选择大量已审核知识点。
- 出题任务支持查询、取消、失败重试；失败不会写入半成品题目。
- 字段错误最多修复 1 次（总调用次数仍受 4 次上限约束），修复后仍失败会给出字段级原因；不会无限重试或重复扣费。
- 单题不合格会被跳过并记入 `timings.warnings`，不会伪装成成功；整批都不合格才失败。
- 模型 API 错误按超时、网络、认证、余额不足（402）、限流（429）、服务端（5xx）、参数/上下文（400）分别提示，`timings.error_kind` 便于排查。
- 生成题目必须人工审核；编辑题目会重新进入待审核。
- 模型只依据已审核知识点起草，不做“事实已验证”的承诺；解析与答案的结构一致性会被校验，但语义事实仍需人工确认。

详细诊断与实测见 [`docs/PHASE4_AI_RELIABILITY.md`](docs/PHASE4_AI_RELIABILITY.md)。

V1.0 发布候选验收（批量稳定性、422 兼容、Android 真机闭环、备份恢复）见
[`docs/PHASE5_ACCEPTANCE.md`](docs/PHASE5_ACCEPTANCE.md)。

### 练习

- 从 `approved` 题库按学科/章节/知识点/题型/难度抽题。
- 单选题、多选题、判断题自动判分；多选题比较答案集合，顺序无关，重复选项会被去重。
- 练习结果展示每道题的全部选项，标记“正确答案”和“你的选择”，不只是展示错误项；同时给出答案、解析和关联知识点。
- 简答题保存为 `pending`，由人工输入 0–1 分并记录评语；人工评分后可重新计算总分。
- 错题由 `is_correct=false` 的答题记录聚合；支持“错题再练”，创建新的练习会话。
- 练习页 `/practice`，题库页 `/questions`；数据全部来自真实 API。

## Windows 本地部署（V1.0 推荐方式）

V1.0 采用**单端口本地 Web 部署**：后端 FastAPI 同时提供 API 和已构建的前端页面，浏览器访问
`http://127.0.0.1:8000/` 即可，不需要单独运行前端服务，也不使用 Docker。

### 前置要求

| 项目 | 要求 | 说明 |
| --- | --- | --- |
| Windows | 10 / 11 | 仅验证 Windows |
| Python | 3.12+ | 安装时勾选 “Add python.exe to PATH” |
| Node.js | 20.19+ | 仅首次构建前端需要；发布包若已包含 `frontend/dist` 则可跳过 |
| 磁盘 | 约 500 MB | 依赖 + 数据 |

### 脚本一览

| 脚本 | 用途 |
| --- | --- |
| `install.bat` | 创建 `backend\.venv`、安装后端依赖；缺前端构建时自动构建 |
| `build_frontend.bat` | 构建前端到 `frontend\dist` |
| `start.bat` | **日常启动**：检查端口 → 初始化/升级数据库 → 启动服务并打开浏览器 |
| `stop.bat` | 停止占用 8000 端口的服务（安全退出） |
| `backup.bat` | 备份数据库、上传文件、AI 运行时配置到带时间戳的目录 |
| `restore.bat` | 从备份目录恢复（旧数据移到 `_restore_previous_*`，不删除） |
| `start-dev.bat` | 开发模式：后端 `--reload` + Vite 5173 热更新 |

### 首次启动步骤

1. 双击 `install.bat`，等待依赖安装完成。
2. 双击 `start.bat`。首次运行会自动：
   - 由 `.env.example` 生成 `.env`（不会覆盖已有 `.env`）
   - 创建 `backend/data/`、`data/uploads/`、`data/logs/`
   - 执行数据库迁移并做完整性检查
   - 打开 `http://127.0.0.1:8000/`
3. 需要 AI 功能时，进入“AI 设置”填写 API Base、Key、模型（密钥只存后端），或直接编辑 `.env`。

### 启动脚本会给出的提示

| 情况 | 行为 |
| --- | --- |
| 缺少 `backend\.venv` | 提示先运行 `install.bat` 后退出 |
| 端口 8000 被占用 | 提示可能已在运行；可用 `stop.bat` 停止后重试 |
| 缺少前端构建产物 | 警告“只能使用 API”，并提示运行 `build_frontend.bat` |
| AI 未配置 | 警告：导入/审核/练习可用，AI 识别与出题不可用 |
| 数据库需要升级 | 先自动备份到 `backend/data/pre_migration_backups/<时间>`，再迁移 |
| 数据库完整性异常 | 打印警告，不自动删除数据 |

### 生产运行注意事项

- 服务只监听 `127.0.0.1`，默认仅本机可访问；不要直接暴露到公网（无用户认证）。
- 关闭启动窗口或按 `Ctrl+C` 即安全停止；也可以运行 `stop.bat`。
- 日志：控制台输出；后端错误也会写入 `backend/data/server.err.log`（开发脚本时）。

### 开发模式（可选）

```powershell
start-dev.bat
```

- 后端：`uvicorn --reload` on `http://127.0.0.1:8000`
- 前端：Vite dev server `http://127.0.0.1:5173`（热更新）
- 开发模式使用 `.env` 里的 `VITE_API_BASE_URL`；生产构建留空时会自动同源。

### 手动命令（不使用脚本）

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe ..\scripts\prepare_env.py
.\.venv\Scripts\python.exe ..\scripts\run_backend.py --port 8000
```

## Android APK 与手机同步（阶段三）

手机端是同一个前端构建产物的 Capacitor 封装，**不是另一套 App**：手机与电脑访问同一台
FastAPI 后端和同一个 SQLite，APK 内没有数据库副本，也没有任何服务端密钥。

### 产物与构建

```
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

构建要求：JDK **21**（JDK 17 无法编译 Capacitor 7）、Android SDK
`platforms;android-35` 与 `build-tools;35.0.0`、Gradle 8.11.1。

```powershell
$env:JAVA_HOME = "C:\path\to\jdk-21"
$env:ANDROID_HOME = "C:\path\to\android-sdk"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"

cd frontend
pnpm build:android        # 使用 .env.android，不把开发机地址打进 APK
pnpm exec cap sync android
cd android
gradlew.bat assembleDebug
```

`frontend/android/local.properties` 由本机生成（含 SDK 路径），已被 gitignore。

### 连接电脑后端（局域网）

1. 电脑 `.env` 设置共享口令（推荐）：`ACCESS_TOKEN=<随机字符串>`。
2. 双击 `start-lan.bat`（等价于 `python scripts/run_backend.py --lan --port 8000`），
   启动日志会打印 `手机请填写：http://<电脑IPv4>:8000/api/v1`。
3. 手机与电脑连接同一 Wi-Fi；首次安装后打开 App → “连接设置” → 填地址与口令 → 保存并测试。
4. 手机不能填 `localhost`：那是手机自己。Windows 防火墙需放行 8000/TCP（仅专用网络）。

**安全边界**：默认只监听 `127.0.0.1`；`--lan` 是显式开关。访问口令是单一共享口令，
不是多用户系统，不要把服务直接暴露到公网。远程部署必须 HTTPS，release 构建默认禁止明文 HTTP。

### Release 签名

- 签名材料（`frontend/android/keystore/`、`keystore.properties`）已被 gitignore，
  不得提交；**必须离线备份 keystore 与口令**，否则无法升级已安装包。
- Gradle 只从环境变量或本地 `keystore.properties` 读取：
  `BIOLEARN_KEYSTORE`、`BIOLEARN_STORE_PASSWORD`、`BIOLEARN_KEY_ALIAS`、
  `BIOLEARN_KEY_PASSWORD`；没有材料时 `assembleRelease` 仍产出未签名包，Debug 不受影响。
- 版本号通过 `BIOLEARN_VERSION_CODE` / `BIOLEARN_VERSION_NAME` 注入。
- **Release 只允许 HTTPS**：Android 9+ 默认阻止明文 HTTP；局域网 HTTP 测试请用 Debug APK。
- 发布候选验收与 HTTPS 方案：[`docs/PHASE5_RELEASE_READINESS.md`](docs/PHASE5_RELEASE_READINESS.md)

### 验证记录

- APK 在实体机 PA2553（Android 16）安装并运行，通过 `http://10.61.232.199:8000/api/v1` 在线。
- 手机新建学科 → 桌面 API 立即可见；桌面新建 → 手机刷新可见。
- 手机完成 4 题练习（75 分）→ 桌面读取到同一会话的 4 条作答。
- 阶段五又完成 2 题真机闭环（AI 出题→审核→练习 100 分）；签名 RC 完成安装与原地升级，
  但 Release 因无 HTTPS 服务器无法联网验证。
- 指向不可达地址时显示超时排查提示。
- 详细报告：[`docs/PHASE3_ANDROID.md`](docs/PHASE3_ANDROID.md)、
  [`docs/PHASE5_RELEASE_READINESS.md`](docs/PHASE5_RELEASE_READINESS.md)

### 代码位置

| 路径 | 说明 |
| --- | --- |
| `frontend/src/lib/api/connection.ts` | API Base 解析（运行时 > 构建时 > 同源；APK 不回退 localhost） |
| `frontend/src/pages/ConnectionSettingsPage.tsx` | 连接设置页（地址、口令、测试） |
| `frontend/src/layouts/AppLayout.tsx` | 底部导航（窄屏） |
| `frontend/capacitor.config.ts` | Capacitor 配置 |
| `frontend/android/` | Android 工程 |
| `backend/app/core/security.py` | 可选共享口令中间件 |
| `backend/app/api/v1/auth.py` | `GET /api/v1/auth` 状态接口 |
| `start-lan.bat` | 显式局域网启动 |

## 数据备份与恢复

### 备份

1. 先运行 `stop.bat` 停止服务（推荐；不停机时 SQLite 在线备份也可用，但练习中的写入可能跨时刻）。
2. 运行 `backup.bat`，或：

```powershell
backend\.venv\Scripts\python.exe scripts\backup_data.py --output-dir D:\BioLearnBackup
```

备份内容：`biolearn.db`（SQLite 在线备份 API + 完整性检查）、`uploads/`、`ai_config.json`、`.env.example`。
**不会自动复制 `.env`**（避免密钥外泄），如自定义过请手动保存。

### 恢复

1. `stop.bat` 停止服务。
2. 运行 `restore.bat`，把备份目录拖进窗口回车。
3. 脚本会：校验备份完整性 → 把当前数据移动到 `backend/data/_restore_previous_<时间>` → 复制恢复 → 自动迁移到最新结构。
4. 运行 `start.bat` 验证。

### 升级与迁移

- 升级程序后直接 `start.bat`：检测到迁移差异会**先自动备份**，再执行只增不改的 Alembic 迁移。
- 迁移从不删除已有资料、知识点、题目或答题记录；如迁移失败会停止启动并提示检查备份。

## 快速开始（开发环境）

所有命令从仓库根目录开始，使用 PowerShell。

### 1. 环境变量

```powershell
Copy-Item .env.example .env
```

按需填写 AI 配置。不要提交 `.env`。

### 2. 后端

```powershell
cd backend

& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

普通开发机把创建 venv 的命令替换为 `python -m venv .venv`。

### 3. 前端

```powershell
cd frontend
pnpm install
pnpm dev
```

打开：

- 首页：`http://127.0.0.1:5173/`
- 智能导入：`http://127.0.0.1:5173/import`（可先打开“默认设置”保存默认学科/章节）
- 学科：`http://127.0.0.1:5173/subjects`
- 资料库：从学科详情点“资料库”
- 知识点审核：资料卡片点“审核知识点”

## API

基础地址：`http://127.0.0.1:8000/api/v1`

### 学科与章节

- `GET/POST /subjects`
- `GET/PATCH/DELETE /subjects/{subject_id}`
- `GET/POST /subjects/{subject_id}/chapters`
- `GET/PATCH/DELETE /chapters/{chapter_id}`
- `POST /chapters/{chapter_id}/move`

### 智能导入

- `GET /imports/preferences`：读取默认导入设置
- `PUT /imports/preferences`：保存默认学科、章节、模式、自动分析、预览确认、不确定策略
- `POST /imports`（multipart：`file`、`subject_id`、`chapter_id`、`name`、`mode`、`auto_analyze`、`require_preview`、`uncertain_policy`）
- `GET /imports/{import_id}`：导入阶段、进度、结构建议、归档结果、AI 分析状态
- `POST /imports/{import_id}/confirm`：预览后确认归档；支持接受建议或指定学科/章节
- `POST /imports/{import_id}/retry`：失败重试（重试不会重复建章）
- `GET /imports?limit=20`：最近导入任务
- `POST /imports/external`（multipart：`file`、`subject_id`、`duplicate_strategy`）：导入外部 AI JSON
- `GET /imports/external/template`：返回 JSON Schema、可复制提示词和示例
- `GET /questions`：题目列表，支持学科/章节/知识点/题型/难度/状态/关键词过滤
- `POST /questions`、`PATCH /questions/{id}`、`GET /questions/{id}`：题目创建、编辑、详情
- `POST /questions/{id}/review`、`POST /questions/bulk-review`：逐题/批量审核
- `POST /questions/generate`、`POST /questions/{id}/regenerate`：从已审核知识点生成/重新生成
- `GET /questions/generation-jobs/{id}`、`.../retry`、`.../cancel`：出题任务查询、重试、取消
- `POST /practice/sessions`：从已通过题库抽题开始练习
- `POST /practice/sessions/{id}/submit`：提交并自动判分（简答题待人工评分）
- `GET /practice/sessions/{id}/result`、`POST /practice/answers/{id}/grade`：结果和人工评分
- `GET /practice/wrong-questions`：错题本

`mode` 取值：

- `preset`：归入预设/本次选择的学科章节。
- `auto_create`：从 PPT 目录、编号标题或文档标题结构生成章节树，自动创建缺失章节。
- `smart_archive`：优先复用已有章节；同名或相似章节需要确认，避免重复创建。

### 资料

- `GET /documents?subject_id=&chapter_id=&status=`
- `POST /documents`（multipart：`file`、`subject_id`、`chapter_id`、`name`、`force`）
- `GET /documents/{document_id}`（含解析分块与最近 AI 任务）
- `PATCH /documents/{document_id}`：调整资料名称/学科/章节，并同步知识点归属
- `GET /documents/{document_id}/chunks`
- `POST /documents/{document_id}/retry-parse`
- `DELETE /documents/{document_id}?cascade=false`
- `POST /documents/{document_id}/extract`
- `GET /documents/{document_id}/jobs`
- `GET /documents/{document_id}/knowledge-points`

### 知识点与任务

- `GET /knowledge-points?document_id=&subject_id=&chapter_id=&review_status=`
- `POST /knowledge-points`
- `GET /knowledge-points/{point_id}`
- `PATCH /knowledge-points/{point_id}`
- `DELETE /knowledge-points/{point_id}?cascade=false`
- `POST /knowledge-points/{point_id}/review`
- `POST /knowledge-points/bulk-review`
- `POST /knowledge-points/merge`
- `GET /knowledge-jobs/{job_id}`
- `POST /knowledge-jobs/{job_id}/retry`
- `POST /knowledge-jobs/{job_id}/cancel`：请求停止排队中/运行中的任务；运行中的任务会在当前模型请求返回后停止

### AI

- `GET /ai/status`：只返回配置是否完整、provider/model/base，不返回密钥
- `GET /ai/config`：读取 AI 配置状态
- `PUT /ai/config`：保存 provider、API Base、模型和 Key；Key 不会回显
- `DELETE /ai/config`：移除页面保存的配置，回退到环境变量
- `POST /ai/test`：测试 OpenAI 兼容连接

### 上传示例

```powershell
$base = "http://127.0.0.1:8000/api/v1"
$subjects = (curl.exe -s "$base/subjects" | ConvertFrom-Json)
$subject = $subjects[0]

curl.exe -X POST "$base/documents" `
  -F "file=@C:\path\to\protein.pdf;type=application/pdf" `
  -F "subject_id=$($subject.id)" `
  -F "name=蛋白质结构"
```

上传后轮询 `GET /documents/{id}`，状态依次为 `uploaded → parsing → parsed`（或 `failed` / `needs_ocr`）。解析成功后才允许 `POST /documents/{id}/extract`。

## AI 知识点构建流程

1. **整章结构分析**：发送文档标题、章节、分块标题路径和内容摘要，得到本章主题、学习目标、小节关系、核心概念、过程、公式/实验、易混淆项、前置知识。
2. **分块提取**：按 `AI_EXTRACTION_CONCURRENCY` 有界并发发送结构与原文，模型返回知识点草稿；超过 `AI_MAX_POINTS_PER_CHUNK` 的部分截断。
3. **来源校验**：模型提供的 `source_quote` 必须能在对应原文块中逐字匹配（忽略空白差异）；不匹配的引文会被丢弃，并标记 `needs_review` 和审核备注。
4. **全章整合**：按批合并重复项，再递归合并批次结果，最后形成知识树；合并结果只能引用已有 `source_point_ids`，引用不存在会导致任务失败，避免来源丢失。
5. **草稿入库**：只删除同一资料下未审核的 AI 草稿；已通过、需修改、已忽略和人工知识点保留。与已审核知识点同名的草稿会写入 `duplicate_of_id` 并标记待确认。
6. **人工审核**：通过/需修改/忽略、批量审核、编辑、新增子知识点、合并、调整层级；通过后 `published_at` 写入，视为正式入库。

任务状态保存在 `knowledge_extraction_jobs`，刷新页面可恢复；服务重启时，运行中的解析/AI 任务会被标记为失败并提示重试；已请求停止（`cancel_requested=1`）的任务会标记为 `cancelled`。

### 停止 AI 识别

- 审核页在任务运行中显示“停止 AI 识别”按钮，调用 `POST /knowledge-jobs/{job_id}/cancel`。
- `queued` 任务立即变为 `cancelled`；运行中的任务先变为 `cancelling`，当前正在等待的模型请求返回后停止，最终变为 `cancelled`。
- 停止不会保存本次新生成的草稿；已有已通过、需修改、已忽略和人工知识点不受影响。
- 单次模型请求可能持续到 `AI_TIMEOUT_SECONDS`（默认 90 秒），因此停止不是秒级中断；页面上会显示“正在停止…”。

## 网页 AI 分析性能与阶段

- 逐块 AI 提取使用**有界并发**：`AI_EXTRACTION_CONCURRENCY`（默认 3，范围 1–8）。并发只作用于 AI 请求，SQLAlchemy 写入仍在主线程。
- 分析提纲受 `AI_OUTLINE_MAX_CHARS` 限制；逐块/合并提示词使用紧凑结构上下文，不再每块重复完整 analysis JSON。
- 任务在 `knowledge_extraction_jobs.timings` 记录 `analysis_seconds`、`extraction_seconds`、`merge_seconds`、`persist_seconds`、`total_seconds` 和并发数。
- 前端阶段：等待 → 解析/结构识别 → 逐块提取（显示已处理 N/M 块，提取阶段百分比来自真实块数）→ 全章合并（不显示伪造精确百分比）→ 保存草稿 → 等待审核/完成/取消/失败。
- 任务状态持久化；切换页面或刷新后可查询 `knowledge-jobs/{id}`。取消会传播到未开始的分块请求；运行中的单次模型请求仍需等待超时。
- 分块失败会标记任务失败且不保存半成品；重试从新的任务重新执行，已有审核内容不受影响。

### 实测数据

同一份真实 PDF、66 个分块：

| 指标 | 结果 |
| --- | --- |
| 文件解析 | 0.433 s（pypdf + 分块，不含 AI） |
| 数据库保存草稿 | 0.003–0.007 s |
| 固定 50 ms/块 mock 模型，串行（并发 1） | 提取 3.349 s，总 3.401 s |
| 固定 50 ms/块 mock 模型，并发 3 | 提取 1.150 s，总 1.192 s |

上表是同一代码、同一 66 分块、同一固定延迟 mock 的对照，只衡量并发与数据库路径，**不是真实模型提速承诺**。真实 provider 的速率限制、超时和输出大小会改变结果。

交接前的真实 `deepseek-flash` 任务（同 66 分块）观测：创建 19:51:10、提取结束 20:04:33（约 803 s）、合并结束 20:23:54（约 1,161 s），总计约 1,964 s。该任务运行在优化前代码，未在优化后重跑真实模型；后续真实任务会在 `timings` 中记录新数据。

## 审核界面

路径：`/documents/{document_id}/review`

- 顶部显示统计：总数、待审核、已通过、需修改、已忽略、待确认、重复项、失败任务
- AI 面板：配置状态、连接测试、开始/重新识别、任务阶段与进度、失败重试、停止运行中的识别
- 左栏：知识树，支持展开/收起、复选、批量审核、合并
- 中栏：选中知识点的解释、类型、核心要点、条件、来源、审核按钮
- 右栏：所属学科/章节、页码/幻灯片、逐字引文、原文分块
- 支持新增根知识点、添加子知识点、编辑层级、删除子树

电脑端三栏，手机端自动纵向堆叠。

资料库卡片的“调整归属”可以修改资料的学科/章节，并同步该资料下已有知识点的归属；审核状态和知识点内容不变。

## 测试与检查

后端：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

前端：

```powershell
cd frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

本次实际结果（阶段五）：

- 后端：`110 passed`
- 前端：`13` 个测试文件，`30 passed`
- ESLint：通过
- TypeScript：通过
- 生产构建：通过
- Android：debug APK 安装到真机并完成 AI 出题→审核→练习→结果；release 构建通过
- AI 批量评估：20 题 / 4 批次，20 保存、0 跳过、0 失败、4 次调用、9,552 tokens（见 `docs/PHASE5_ACCEPTANCE.md`）
- Alembic：空库 upgrade → downgrade → upgrade 通过
- 真实 PDF：`第二章第三节-蛋白质的分子结构.pdf` 75 页，解析为 66 个按页分块；`第二章第四节-蛋白质结构与功能的关系.pdf` 38 页可解析
- 旧版 `.ppt`：明确返回 `legacy_ppt_unsupported`

测试使用临时 SQLite 和临时上传目录，不接触真实资料。AI 相关测试使用 FakeAI 覆盖成功、格式错误、调用失败、重试和已审核内容保护。

DSH 接管验证时，真实库中的 AI 合并任务已经完成；为不接触真实库，后端测试通过环境变量指向临时数据库并加 `--basetemp` 运行，结果为 **77 passed**（含 15 项智能导入、9 项外部 JSON、2 项并发/部分失败、8 项题库/练习、2 项 SPA 托管测试）。前端 `tsc --noEmit`、ESLint 通过；Vitest 为 **12 个测试文件 / 26 passed**；生产构建通过（62 个模块）。最初在 `workspace-write` 沙箱下 Vite 因 `net use` 子进程返回 `spawn EPERM`，切换为 `danger-full-access` 后已正常复跑。

接管期间已修复：

- 测试 lifespan 不再触发真实库的任务恢复；`retry-parse` 会拒绝已解析/已有知识点/仍有 AI 任务的资料，避免删除分块后把知识点来源置空。
- 超长单 block 拆分后的 `char_start/char_end` 现在按每个片段记录，不再让所有片段共用整个 block 的范围。
- 新增“停止 AI 识别”：`POST /knowledge-jobs/{job_id}/cancel` + 审核页按钮；新增 `cancel_requested` 字段和迁移 `0006_job_cancellation`。停止是协作式的，会在当前模型请求返回后生效。
- “重新识别整章”增加二次确认，减少误触重复识别。

当前实际后端进程的命令行是 `uvicorn app.main:app --host 127.0.0.1 --port 8000`，**没有 `--reload`**；上述源码修复尚未加载到该进程，需在确认后重启后端才会生效。

## 已知限制

- 没有 OCR；扫描版 PDF 只能识别并提示，不能提取文字。
- 旧版 `.ppt` 不支持，需要另存为 `.pptx`。
- PDF 仅提取文本层；表格/复杂版式可能退化为普通文本，不保证还原视觉版式。
- 分块按页/幻灯片/标题边界，不做语义向量切分；超长单页按句子/字符上限切分。
- 没有消息队列；使用 FastAPI BackgroundTasks + 数据库状态，单进程重启会把未请求停止的运行中任务标记为失败；已请求停止的标记为 `cancelled`。
- 停止 AI 识别是协作式的：无法中断已经发出的单次 HTTP 模型请求，最长需等待一次 `AI_TIMEOUT_SECONDS`（默认 90 秒）后生效。
- 智能导入的结构识别是确定性启发式：PPT 目录/编号标题、DOCX/Markdown 标题；没有调用模型做学科分类。无法推断学科时必须使用默认学科或本次选择。
- PPTX 只读取现有解析器支持的文本/表格/标题占位符；组合形状、备注页和图片内文字不参与章节识别。
- 自动建章预览默认开启；关闭预览后会直接创建/复用章节，建议只在默认位置明确时关闭。
- 同一文件按“学科”去重；同一文件在同一学科重复导入返回已有资料，不同学科可分别导入。
- 外部 AI JSON 的 `source_quote`/页码是外部模型提供的，不会在网页端与原文逐字核验；默认 `source_quote_verified=false` 并进入待审核。
- 外部 JSON 长课件目前按 shard 文件逐个导入；分片之间用 `point_id`/标题去重，不是单次多文件合并。
- 并发提取受 provider 速率限制影响；合并阶段仍串行。真实模型提速需以实际运行数据为准，当前只提供固定延迟 mock 对照。
- 题库的“一致性校验”是结构性的：选项 key/文本唯一、答案必须存在、单选/判断/简答规则、知识点归属和题型校验；**没有自动证明题干与解析在语义事实层面绝对正确**，所有 AI 题目默认待人工审核。
- AI 出题使用进程内 BackgroundTasks，没有持久队列；服务重启会把运行中的出题任务标记失败，用户可重试。生成使用固定最多 4 次模型调用，避免无限循环，但可能少于请求题量。
- 练习按章节精确过滤，不自动包含子章节全部题目；错题本只聚合已通过题目。
- 简答题只有人工评分，没有 AI 自动评分，也没有掌握度/间隔复习算法。
- 没有认证和多租户；API 只有可选的单一共享口令，默认仅本机访问。
- 单题不合格时可能少于请求题量；`skipped_count` 与 `timings.warnings` 会记录原因，不保证一次生成满 N 道。
- AI 合并是批处理/递归合并，不是可编辑的无限层级语义图谱；极多知识点仍可能受模型上下文限制。
- 预览只展示解析文本，不渲染 PDF/PPTX 原始视觉页面。
- 删除是硬删除，没有回收站。
- 没有 Playwright E2E；前端交互用 Vitest + Testing Library 覆盖。

## 下一步

建议下一阶段：

1. 接入 OCR（扫描版 PDF/图片资料）。
2. 为知识点增加跨资料全局知识库视图、搜索和相关知识点推荐（当前已支持 API 搜索/筛选）。
3. 题库增强：题目版本/历史、重复题目合并、更多评分规则和 AI 辅助简答评分（必须人工复核）。
4. 学习分析：掌握度、错题重练计划、间隔复习；当前已保存练习和答题明细。
5. 评估持久任务队列（如 Redis/RQ/Celery）与多进程部署。
6. 在 DSH 中验证 DSF1017 的真实连接、输出质量和用量/成本；真实 Key 只由 DSH 注入，不写入仓库。
