# BioLearn AI 开发状态

快照时间：2026-10-21 09:35（Asia/Shanghai）

本次快照完成 **V1.0 功能冻结 + Windows 本地部署封装 + 端到端验收**。真实业务数据未被删除；题库和练习数据由用户在 2026-10-20 生成，验收后保留。

## V1.0 本轮新增（2026-10-21）

### 功能冻结范围

| 能力 | 状态 |
| --- | --- |
| 学科/章节管理 | 已完成 |
| 课件导入（PDF/DOCX/PPTX/TXT/MD）、解析、分块 | 已完成 |
| 智能导入：预设章节 / 自动建章 / 智能归档 | 已完成 |
| 外部 AI JSON 知识点导入（schema 1.0、预览、重复策略） | 已完成 |
| 知识点审核：搜索/筛选/编辑/批量/合并/重审 | 已完成 |
| 题库：手动题目、审核、批量审核、重复提示、重新生成 | 已完成 |
| AI 出题（仅 approved 知识点、结构校验、取消/重试） | 已完成（真实模型质量待验证） |
| 练习：抽题、自动判分、简答人工评分、错题本、错题再练 | 已完成 |
| 结果页展示全部选项 | 已完成 |
| **外部题目导入（题型 JSON 文件）** | **未实现**，列入 V1.1 |
| 学习分析（掌握度/间隔复习） | 未实现，仅保存答题明细 |

### 部署封装

- 单端口部署：后端托管 `frontend/dist`；`/` 返回 SPA，`/assets/*` 返回静态资源，未知前端路由回退 `index.html`，`/api/*` 不存在返回 JSON 404，`/health` 等保留路径不被 SPA 吞掉。
- CORS 增加本地回环正则，允许开发模式多端口。
- 前端 API 地址：`VITE_API_BASE_URL` 有值时使用；生产构建留空时自动使用同源 `/api/v1`。
- 相对路径统一按 `backend/` 解析：`DATABASE_URL`、`UPLOAD_DIR`、`AI_CONFIG_PATH`、`LOG_DIR`、`FRONTEND_DIST_DIR`。
- 新增脚本：`install.bat`、`build_frontend.bat`、`start.bat`、`stop.bat`、`backup.bat`、`restore.bat`、`start-dev.bat`；对应 `scripts/run_backend.py`、`prepare_env.py`、`stop_services.py`、`backup_data.py`、`restore_data.py`。
- 迁移前自动备份到 `backend/data/pre_migration_backups/<时间>`；恢复时旧数据移动到 `_restore_previous_<时间>`。
- AI 出题失败信息包含前 3 个 Schema 错误位置（不含提示词内容）。

### 安全核查

- `.gitignore` 覆盖 `.env`、`*.db`、`backend/data/*`、`uploads/`、`*.log`、`dist/`、`backups/`；`git check-ignore` 实测均被忽略。
- 备份脚本不自动复制 `.env`；`ai_config.json` 备份提示含密钥。
- 未创建任何 Git 提交。

### 验收实测（2026-10-21，真实服务 8000 端口）

| 流程 | 结果 |
| --- | --- |
| `start.bat` 启动（无 pause 包装） | 端口检查 → `0009` 已最新 → 完整性检查通过 → 服务 200 |
| 端口被占用时启动 | `[ERROR] 端口 8000 已被占用`，退出码 1 |
| 单端口访问 | `/`、`/practice`、`/questions` 200；`/assets/index-*.js` 200；`/api/v1/nope` JSON 404 |
| 重复上传同一 PPTX | 201，复用 `document_id`，`duplicate=true`，未重复建章 |
| 外部 JSON 导入（新文件） | 预览 → 确认归档，2 个章节 + 1 条 pending 知识点 |
| 外部 JSON 重复导入 | `duplicate_import=true`，重复知识点提示 |
| 知识点审核 | pending → approved；编辑后回 pending 且清空 `published_at`；重新 approved |
| 题目创建/去重 | 两次 201，第二次 `duplicate_of_id` 指向第一条；非法答案 422 |
| 练习提交 | 判断题答错 `is_correct=false`、得分 0；重复提交 409 |
| 重启前后端 | 停止后 `start.bat` 重建；学科/知识点/题目/练习/错题/导入任务全部保留 |
| 备份 → 恢复 | 校验 → 旧数据移入 `_restore_previous_*` → 恢复 → 迁移；`integrity_check=ok`，78 知识点/5 题/5 答题明细均在 |
| AI 出题（真实模型） | **两次失败**：`AI 出题返回格式不符合要求`（4.3s/5.2s）；无半成品题目 |

### 本轮测试结果

- 后端：**77 passed**（新增 `tests/test_static_hosting.py` 2 项）。
- 前端：TypeScript、ESLint、**12 个文件 / 26 passed**、生产构建 62 模块通过。

### 未验证事项

- `install.bat` 未在干净机器上完整执行（本机已有 `.venv` 与 `dist`）。
- 新课件文件的首解析 → 建章 → AI 提取链路本轮未执行（AI 提取此前有真实成功记录）。
- **AI 出题真实模型质量未验证**，两次均结构校验失败。
- 前端页面浏览器交互回归仅有组件测试，无自动化 E2E。
- 未验证远程访问与防火墙；默认 `127.0.0.1`。

### 验收遗留数据（已保留，待用户决定）

- 章节：`验收临时外部JSON`、`验收临时章节`
- 知识点：`验收临时知识点`（approved）
- 资料：`验收临时外部JSON`（外部 JSON，0 分块）
- 题目：2 道 `验收临时题…` 已 `rejected`
- 练习：会话 `e91b2047…`（1 题，答错）

## 历史：知识点闭环审查与题库 MVP（2026-10-20）

### 第一阶段审查结论

- 网页 AI 分析与外部 JSON 导入都写入同一张 `knowledge_points` 表，进入同一套审核 API 和审核页。
- 已有点击树、详情、编辑、逐题/批量审核、需修改、忽略（拒绝）、合并、删除保护；来源、页码/幻灯片、章节、资料均真实存储。
- 真实缺口 1：已通过知识点被编辑后仍保持 `approved`。已修复：内容字段变更会重新置为 `pending`、清空 `published_at`，必须重新审核。
- 真实缺口 2：知识点列表没有搜索/筛选。已补 API `q`/`point_type`/`origin`/`needs_review`/分页，审核页增加搜索和审核状态筛选。
- 重复检测、外部导入保护、取消/重试/事务回滚已有测试，没有重复实现。

### 题库与练习

- 迁移 `0009_question_bank`：`questions`、`question_generation_jobs`、`question_knowledge_points`、`practice_sessions`、`practice_answers`。
- 题型：单选、多选、判断、简答；选项/答案/评分规则为 JSON；题目与知识点多对多真实关联。
- 题目状态：pending/approved/rejected/needs_revision；生成和编辑后待审核，只有 approved 可被练习抽取。
- AI 出题：只使用 approved 知识点；结构化 Pydantic 校验；选项/答案/题型/知识点归属一致性检查；题干去重；最多 4 次模型调用、最多 20 题、无半成品写入；支持取消、失败重试和重新生成。
- 题目管理页 `/questions`：真实 API 列表、搜索、学科/章节/题型/难度/状态筛选、详情、编辑、通过/拒绝/需修改、批量审核、重复提示、重新生成。
- AI 出题知识点支持搜索、全选当前范围、全选筛选结果、清空和反选；大量知识点不必逐项勾选。
- 练习页 `/practice`：真实 API 抽 approved 题；单选/多选/判断自动判分；多选题集合比较、顺序无关、重复答案去重；简答题人工评分；答题记录/错题本/错题再练。
- 练习结果展示全部选项，并用“正确答案/你的选择”标记；不再只显示错误项和答案。
- 未开发掌握度、遗忘曲线、自适应算法；只保留练习和答题明细数据。

### 数据与迁移

- 迁移前备份：`D:\BioLearnBackup\2026-10-19-2302\biolearn-before-question-bank.db`，SHA-256 `0f47333ea785208ac52f68fbae83eeb81592c57ca13f0f8e5390544360e2fa17`。
- 真实库已到 `0009_question_bank`；验证 `0008 → 0009 → 0008 → 0009` 通过。
- 当前数据：2 份资料、117 个分块、6 个章节、78 个知识点（39 approved + 39 pending）、3 个 AI 任务、1 个导入任务；**0 道题、0 个练习记录**（题库从空开始，未伪造数据）。

### 验证

- 后端：**75 passed**（含 8 项题库/练习）。
- 前端：TypeScript、ESLint 通过；**12 个测试文件 / 26 passed**；生产构建 62 个模块。
- 后端/前端均返回 200；OpenAPI 已包含 `/questions*`、`/practice*`。

## 历史快照：外部 AI 导入与网页分析优化（22:25）

### 外部 AI JSON 导入

- 页面 `/import` 新增“导入 AI 预处理 JSON”和“查看导入模板”。
- 新增 `POST /imports/external`、`GET /imports/external/template`。
- 新增版本化交换格式 `schema_version 1.0`：`document`、`subject`、`chapter_tree`、`knowledge_points`、`metadata`；字段包括 title/content/chapter_path/category/importance/key_terms/source/prerequisites。
- 后端 Pydantic 校验；未知版本、JSON 语法、字段缺失、超大文件返回明确错误。
- 上传后先进入预览：章节树、知识点数量、重复项、缺失来源、异常项；用户确认后才写入。
- 外部知识点默认 `pending`、`origin=ai`、`needs_review=true`、`source_quote_verified=false`。
- 重复策略：`skip`（默认）/`update_pending`；只更新同一资料下的未审核 AI 草稿，已通过/人工内容永不覆盖。
- 原始 JSON 存盘并在 `documents` 记录 SHA-256；完整 payload 存在 `import_jobs.payload`。
- 外部导入不启动网页 AI 分析；直接进入现有审核页。
- 知识字段：`importance`、`prerequisites`、`external_id`（迁移 0008）。

### 网页 AI 分析优化

- `AI_EXTRACTION_CONCURRENCY`（默认 3，范围 1–8）对**逐块 AI 请求**做有界并发；数据库写入仍在主线程。
- 分析提纲按 `AI_OUTLINE_MAX_CHARS` 截断；逐块/合并提示词使用紧凑结构上下文，不再每块重复完整 analysis JSON。
- `knowledge_extraction_jobs.timings` 记录分析/提取/合并/保存/总耗时与并发数。
- 部分分块失败时任务失败且不保存半成品；重试从新任务重新执行；已审核内容不受影响。
- 前端提取阶段显示真实“已处理 N/M 块”；合并阶段不显示伪造精确百分比；导入阶段只显示阶段文本。
- 导入页展示最近导入，刷新后可从数据库恢复任务状态。

### 迁移与运行

- 迁移 `0008_external_import` 已应用到真实库。
- 迁移前备份：`D:\BioLearnBackup\2026-10-19-2225\biolearn-before-external.db`，SHA-256 `77e2aa95997a59ccdda93205b1394cfe0a2bea2f5e0314d65ea19c593666e2f1`。
- 迁移在真实库副本上验证 upgrade → 检查字段 → downgrade → upgrade。
- 当前真实数据：**2 份资料、117 个分块、6 个章节、78 个知识点（39 approved + 39 pending）、3 个 AI 任务、1 个导入任务**。
- 用户导入的 `第二章第一节` PPTX 及其 39 条待审核知识点必须保留。

### 实测耗时

| 项目 | 数值 |
| --- | --- |
| 真实 PDF 解析（66 分块） | 0.433 s |
| 固定 50 ms/块 mock，串行提取 | 3.349 s（总 3.401 s） |
| 固定 50 ms/块 mock，并发 3 提取 | 1.150 s（总 1.192 s） |
| 草稿保存 | 0.003–0.007 s |

优化前真实 `deepseek-flash` 任务（同 66 分块）：提取约 803 s，合并约 1,161 s，总计约 1,964 s。未在优化后重跑真实模型；上表 mock 对照只衡量并发/数据库路径，不构成真实模型提速承诺。

### 新增/修改的关键文件

- `backend/alembic/versions/0008_external_import.py`
- `backend/app/schemas/external_import.py`
- `backend/app/services/external_import.py`
- `backend/app/api/v1/imports.py`
- `backend/app/services/importing.py`（外部任务分支、章节解析复用）
- `backend/app/core/config.py`（并发配置）
- `backend/app/services/knowledge.py`（并发提取、提示词压缩、timings）
- `backend/app/models/knowledge.py`、`backend/app/models/importing.py`
- `backend/app/schemas/imports.py`、`knowledge.py`、`mappers.py`
- `backend/tests/test_external_import.py`（9 项）
- `backend/tests/test_extraction_performance.py`（2 项）
- `backend/tests/test_migrations.py`
- `frontend/src/lib/api/imports.ts`
- `frontend/src/pages/ImportPage.tsx`（外部 JSON/模板/最近导入）
- `frontend/src/pages/ImportPage.test.tsx`（5 项）
- `frontend/src/lib/api/knowledge.ts`、`frontend/src/pages/KnowledgeReviewPage.tsx`
- `frontend/src/styles.css`
- `.env.example`

## 原有交接记录（历史）

### 智能导入

- 新增统一导入入口 `/import`：拖拽/选择文件、学科/章节选择、三种模式、自动分析开关、预览开关、阶段进度和建议树。
- 模式：
  - `preset`：归入预设/本次选择的章节，不做结构推断。
  - `auto_create`：从 PPT 目录页、编号标题或 DOCX/Markdown 标题层级生成章节树；无明确结构时只建议资料标题章节。
  - `smart_archive`：学科内同父级同名章节复用；同名异父级/相似名称进入待确认，避免重复建章。
- 导入偏好持久化到 `import_preferences`：默认学科、默认章节、默认模式、自动分析、预览确认、不确定策略。
- 导入任务持久化到 `import_jobs`：`queued → parsing → detecting → awaiting_confirmation/archiving → analyzing → completed/failed`。
- 新增 `POST /imports`、`GET /imports/{id}`、`POST /imports/{id}/confirm`、`POST /imports/{id}/retry`、`GET/PUT /imports/preferences`。
- `chapters` 新增 `source_document_id`、`source_import_job_id`、`source_slide`，自动建章可追溯。
- 同一文件按学科去重；重复导入返回已有资料，不重复建章。不同学科允许分别导入。
- 章节创建在单事务中；失败回滚全部新章节，保留已解析资料并标记导入失败。
- 归档成功后可按设置自动创建 AI 任务并运行；停止 AI 只停止分析，不删除已导入文件和章节。
- 新增 `PATCH /documents/{id}`，可在分析前/后调整资料学科和章节，并同步知识点归属。
- 重启恢复：导入中断标记失败可重试；AI 阶段中断保留已归档资料并标记 AI 失败。

### 实际识别规则与限制

- PPTX 复用现有解析器的标题占位符、文本框、表格、幻灯片编号；结构识别只采用目录页、编号标题或文档标题，不把每张普通幻灯片标题都当章节。
- 没有调用模型做学科/章节语义分类；无法推断学科时必须使用默认学科或本次选择。
- PDF 没有标题结构时只建议资料标题章节；DOCX/Markdown 使用标题层级。
- 组合形状、备注页、图片内文字不参与识别。
- 预览默认开启；关闭后自动建章会直接执行。

### 迁移与运行

- 迁移 `0007_smart_import`：新增 `import_preferences`、`import_jobs`、章节来源列；真实库已应用。
- 迁移前备份：`D:\BioLearnBackup\2026-10-19-2110\biolearn-before-smart-import.db`，SHA-256 `7d6663220ff9ced78b26c5c6c59502bb70fcd40577569758d4363ffa56d1b46b`。
- 迁移先在真实库副本上验证 upgrade → 检查表/列 → downgrade → upgrade，均通过。
- 21:10 当时后端：监听 PID `174668`，启动器 PID `175616`（已被 22:25 重启取代）。
- 21:10 当时数据：1 份资料、66 分块、2 个 AI 任务（completed + cancelled）、39 条已通过知识点、0 个导入任务；该快照已被 22:25 的新数据取代。

### 新增/修改的关键文件

- `backend/alembic/versions/0007_smart_import.py`
- `backend/app/models/importing.py`
- `backend/app/models/chapter.py`（来源字段）
- `backend/app/schemas/imports.py`
- `backend/app/services/importing.py`
- `backend/app/api/v1/imports.py`
- `backend/app/api/v1/documents.py`（PATCH 归属）
- `backend/app/services/documents.py`（按学科去重、归属调整、来源清理）
- `backend/app/services/recovery.py`（导入任务恢复）
- `backend/app/api/v1/router.py`
- `backend/tests/test_imports.py`（15 项）
- `backend/tests/test_migrations.py`
- `frontend/src/lib/api/imports.ts`
- `frontend/src/pages/ImportPage.tsx`
- `frontend/src/pages/ImportPage.test.tsx`（3 项）
- `frontend/src/pages/DocumentsPage.test.tsx`（新增归属调整测试）
- `frontend/src/router.tsx`、`frontend/src/layouts/AppLayout.tsx`
- `frontend/src/styles.css`、`frontend/src/pages/DocumentsPage.tsx`

## 原有交接记录（历史）

### 1. 停止 AI 识别

- 新增 `cancel_requested` 字段（迁移 `0006_job_cancellation`）。
- 新增 `POST /api/v1/knowledge-jobs/{job_id}/cancel`。
- 新增 `cancelling` / `cancelled` 任务状态。
- 审核页在任务运行中显示“停止 AI 识别”；`cancelling` 时显示“正在停止…”。
- 停止是协作式的：`queued` 立即取消；运行中的任务在当前模型请求返回后停止。单次请求最长受 `AI_TIMEOUT_SECONDS`（默认 90 秒）限制。
- 停止不会保存本次新草稿；已有已通过/需修改/已忽略/人工知识点不受影响。
- 服务重启时，`cancel_requested=1` 或 `cancelling` 的任务标记为 `cancelled`；其他运行中任务仍标记失败。
- “重新识别整章”增加二次确认，减少误触重复识别；取消确认不会发起提取请求。

### 2. 解析与测试修复

- 测试 `TestClient` 不再触发真实库的 `recover_interrupted_tasks()`。
- `retry-parse` 拒绝正在解析、有运行中 AI 任务、已 `parsed`、已有知识点的资料。
- 超长单 block 拆分后按片段记录真实 `char_start/char_end`。

### 3. 之前的后端重启与迁移（历史）

- 旧后端 PID `177776` 已停止；停止前任务 `594fe265…` 正在提取第 29/66 块。
- 备份：`D:\BioLearnBackup\2026-10-19-2046\biolearn-before-cancel.db`，SHA-256 `34d5e6fd4e11be9a360246891711b81693f227a7a30d511f807378687958a35d`，上传目录也已复制备份。
- 真实库已从 `0005_knowledge_review_note` 升级到 `0006_job_cancellation`。
- 迁移先在真实库副本上验证 upgrade → 检查列 → downgrade → upgrade，均通过。
- 新后端已启动：监听进程 PID `169388`，启动器 PID `138744`，命令 `uvicorn app.main:app --host 127.0.0.1 --port 8000`（无 `--reload`）；日志在 `backend/data/server.out.log` / `server.err.log`。

### 修改的关键文件

- `backend/alembic/versions/0006_job_cancellation.py`
- `backend/app/core/enums.py`
- `backend/app/models/knowledge.py`
- `backend/app/schemas/knowledge.py`
- `backend/app/services/job_control.py`
- `backend/app/services/ai_client.py`
- `backend/app/services/knowledge.py`
- `backend/app/services/recovery.py`
- `backend/app/services/mappers.py`
- `backend/app/services/documents.py`
- `backend/app/services/chunking.py`
- `backend/app/api/v1/knowledge.py`
- `backend/tests/conftest.py`
- `backend/tests/test_knowledge.py`
- `backend/tests/test_documents.py`
- `backend/tests/test_parsing.py`
- `backend/tests/test_migrations.py`
- `frontend/src/lib/api/knowledge.ts`
- `frontend/src/lib/format.ts`
- `frontend/src/pages/KnowledgeReviewPage.tsx`
- `frontend/src/pages/KnowledgeReviewPage.test.tsx`
- `README.md`、`docs/DEVELOPMENT_STATUS.md`、`docs/AI_HANDOFF.md`、`docs/PROJECT_OVERVIEW.md`、`docs/architecture.md`

## 1. Git 状态

| 项目 | 实际结果 |
| --- | --- |
| 分支 | `main` |
| 提交记录 | **没有任何提交**，`git log` 报 “does not have any commits yet” |
| HEAD | 不存在 |
| 远程仓库 | 未配置 |
| stash | 无 |
| 已跟踪文件 | 无 |
| `git diff` | 空（所有内容都未跟踪） |
| 未跟踪条目 | 163 条 |

所有源码、配置、文档和截图仍处于未跟踪状态。**没有执行 `git add` 或 `git commit`。**

完整清单命令：

```powershell
git status --porcelain -uall
```

## 2. 当前运行状态

| 服务 | 地址 | 状态 |
| --- | --- | --- |
| 后端 Uvicorn | `http://127.0.0.1:8000` | 200 |
| 前端 Vite | `http://127.0.0.1:5173` | 200 |
| AI 设置页 | `/settings/ai` | 200 |

进程快照：

- 后端监听 PID `152052`（python），启动器 PID `179276`
- 前端 PID `130352`（node，Vite 5173）
- 后端标准输出/错误：`backend/data/server.out.log`、`backend/data/server.err.log`
- 新后端已加载取消、智能导入、外部 AI JSON、题库和练习 API；`/openapi.json` 包含 `/api/v1/questions*`、`/api/v1/practice*`

当前数据库实际状态（2026-10-20 12:30 只读查询）：

| 表 | 数量 |
| --- | --- |
| subjects | 10 |
| chapters | 6（“生物化学”下含用户新导入章节“第二章第一节”） |
| documents | **2**（1 PDF + 1 PPTX） |
| document_chunks | **117**（66 + 51） |
| knowledge_extraction_jobs | **3**（2 completed + 1 cancelled） |
| knowledge_points | **78（39 approved + 39 pending）** |
| import_jobs | **1**（completed，用户智能导入） |
| import_preferences | 0（尚未设置默认导入位置） |
| questions | **0**（题库从空开始，未导入假数据） |
| practice_sessions / practice_answers | **0 / 0** |
| 上传文件 | 1 个 PDF + 1 个 PPTX |

**不要清理或删除这些用户数据。** 39 条知识点已审核通过；用户新导入的 39 条知识点仍待审核，不要回退或覆盖。

## 3. AI 任务状态

### 任务 A：首次完整识别（已完成）

| 字段 | 值 |
| --- | --- |
| document_id | `4c4a5a20-1ddd-4e90-865a-966edc191536` |
| document name | `第二章第三节-蛋白质的分子结构` |
| document status | `parsed` |
| page_count | 75 |
| chunk_count | 66 |
| job_id | `b060e7e8-03a4-4130-8f15-918dd6bb8afc` |
| job status | `completed` |
| stage | `知识点草稿已生成` |
| progress | 100 |
| processed_chunks | 66 / 66 |
| extracted_count | 252 |
| merged_count | 39 |
| duplicate_count | 0 |
| attempts | 1 |
| error | `None` |
| created_at / started_at | 11:51:10 UTC（19:51 本地） |
| finished_at | 12:23:54 UTC（20:23:54 本地） |

该任务的 39 条知识点已全部人工审核通过（`approved`，`published_at` 已写入）。

### 任务 B：重复识别（已停止）

| 字段 | 值 |
| --- | --- |
| job_id | `594fe265-6f48-4073-a704-9d98a2471395` |
| 触发时间 | 12:39:26 UTC（20:39:26 本地） |
| 停止前状态 | `extracting`，第 29/66 块 |
| 最终状态 | `cancelled` |
| progress | 44 |
| processed_chunks | 32 / 66 |
| extracted_count | 0 |
| merged_count | 0 |
| cancel_requested | 1 |
| error | `None` |
| finished_at | 12:46:41 UTC（20:46:41 本地） |

这次任务是在 39 条知识点全部通过后再次启动的重复识别，没有生成新草稿。停止时旧后端尚不支持取消，因此通过“停止旧进程 → 迁移 → 标记 cancel_requested → 重启”完成；新后端的恢复逻辑将其标记为 `cancelled`，没有伪造完成状态。

当前没有运行中的解析或 AI 任务。

## 4. 功能进度

### 已完成

- 学科 CRUD、章节树、子章节、排序、跨学科/循环/删除保护。
- 资料上传、服务器存储、扩展名/签名/大小/空文件校验、路径安全。
- SHA-256 重复检测、`force` 重复上传、状态轮询、解析重试。
- PDF/DOCX/PPTX/TXT/MD 解析和分块。
- 页码、幻灯片、标题路径、字符范围、Markdown 表格/列表保留。
- 文档删除保护与级联、文件删除。
- 文档状态和 AI 任务状态持久化、重启中断标记。
- AI 配置页、保存/清除 Key、连接测试、Key 不回显。
- OpenAI 兼容客户端、超时、有限重试、429/5xx 处理。
- AI 整章分析、分块提取、来源引文校验、分批/递归合并、去重。
- AI 草稿审核树、编辑、单条/批量审核、合并、层级调整。
- 重新提取时保留已审核/人工知识点，重复项标记 `duplicate_of_id`，审核备注 `review_note`。
- 停止排队中/运行中的 AI 识别，审核页显示停止按钮和 `cancelling` 状态。
- 前端资料库和知识点审核页，桌面/手机响应式布局。

### 部分完成

- **DSF1017 / DSH 真实模型联调**：未完成。当前运行时模型是 `deepseek-flash`；两次真实任务都使用该模型。
- **停止延迟**：协作式停止，无法中断已发出的单次模型请求；最长约一次 `AI_TIMEOUT_SECONDS`（90 秒）。
- **多来源追踪**：合并知识点只保留一个 primary chunk；27/39 条有引文不在 primary chunk 中。
- **稀疏 PDF**：75 页中 9 页无文本，66 个分块中 9 个少于 20 字符；`needs_ocr` 只看全文总量。
- **合并阶段进度**：合并期间状态曾停在 `extracting/72%`；本次首个任务合并约 19 分钟。

### 尚未实现

- OCR（扫描版 PDF/图片）。
- 旧版 `.ppt`。
- 认证、多用户、权限和租户隔离。
- 持久任务队列（Redis/RQ/Celery 等）。
- 正式知识库检索、向量索引、引用问答、题目/闪卡/学习记录。
- 知识树拖拽、回收站/撤销、E2E Playwright。
- PDF/PPTX 原始视觉页面预览。

## 5. 文档解析与迁移验证

真实文件：

| 文件 | 结果 |
| --- | --- |
| `第二章第三节-蛋白质的分子结构.pdf` | 75 页，77 个 block，66 个分块；9 页无文本；总字符 6,592；9 个分块 <20 字符 |
| `第二章第四节-蛋白质结构与功能的关系.pdf` | 38 页，34 个 block，34 个分块；4 页无文本；总字符 3,235 |
| `第二章第一节.ppt` / `第二章第二节-肽.ppt` | 旧版 `.ppt`，返回 `legacy_ppt_unsupported` |

分块一致性：

- 用当前 `parse_document` + `build_chunks` 重新解析真实 PDF，66 个分块与数据库逐字一致。
- 每个分块内容都能在格式化后的 block 流中找到；无正文丢失。
- 分块 `char_start/char_end` 单调不重叠。
- 超长单 block 拆分后按片段记录真实范围（实测 `(0,495)`…`(1980,2200)`）。

合成 DOCX/PPTX/TXT/Markdown：标题层级、表格、列表、幻灯片编号、代码块内容均保留。

迁移验证：

- 空库 Alembic upgrade → downgrade → upgrade 通过。
- 真实库副本 `0005 → 0006` upgrade、列检查、downgrade、再次 upgrade 通过。
- 真实库已应用 `0009_question_bank`，数据行数不变（2 资料/117 分块/78 知识点/1 导入任务）。

## 6. 测试结果

- 后端：**75 passed**（36.49s；41 项原有/取消 + 15 项智能导入 + 9 项外部 JSON + 2 项并发/部分失败 + 8 项题库/练习）。
- 前端：TypeScript 通过；ESLint 通过；Vitest **12 个文件 / 26 passed**；生产构建通过（62 个模块）。
- 题库测试覆盖：手动创建/校验、已审核限制、AI 生成/重复跳过/失败重试/取消、编辑重置审核、批量审核、题目筛选、练习自动判分、答案顺序/重复去重、简答人工评分、重复提交 409、答题记录持久化、错题再练。
- 前端新增测试：题库列表/筛选/详情/审核真实 API；练习抽题/提交/简答评分真实 API。
- 前端新增测试：运行中任务点击“停止 AI 识别”后显示“正在停止…”；“重新识别整章”会先弹出确认框，取消时不会发起提取请求。
- 测试使用临时 SQLite/上传目录；没有触碰真实库。
- 最初 `workspace-write` 下 Vitest 因 Vite `net use` 子进程返回 `spawn EPERM`；切换 `danger-full-access` 后正常复跑。

## 7. 当前错误观察

- 后端健康检查 200；新 API 已加载。
- 取消已完成/已取消任务返回 409 `job_not_cancellable`（已实测）。
- 没有失败任务；任务 A/新导入任务 completed，任务 B cancelled，`error=None`。
- 78 条知识点：39 approved + 39 pending（用户新导入，等待审核）。
- 后端日志：`backend/data/server.err.log` 仅包含正常启动信息。

## 8. 已知风险与下一步

### 已知风险

1. **停止延迟**：最长等待当前模型请求返回；如需秒级中断，需要把 AI 调用改成可取消的异步/子进程架构。
2. **重复识别入口（已加确认）**：审核页“重新识别整章”现在会先弹出确认框；仍建议保持这一行为，避免误触。
3. **稀疏 PDF 判定**：按全文总字符数判断 OCR，不按页。
4. **多来源追踪**：只保存一个 `source_chunk_id`。
5. **合并阶段无批次进度**：合并期间只显示“合并中”，不伪造精确百分比；批次进度仍可继续增强。
6. **UTF-16 TXT 上传**：上传签名校验用 NUL 字节判定二进制。
7. **卡在 `uploaded`**：后台解析任务在设置 `parsing` 前失败时没有重试入口。
8. **后端无 `--reload`**：代码修改后必须手动重启才生效。
9. **结构识别是启发式**：没有调用模型做学科/章节语义分类；PPT 仅依赖目录/编号/标题，组合形状和图片文字不参与。
10. **默认导入设置尚未配置**：`import_preferences` 当前为空，首次使用 `/import` 需要选择学科并保存一次默认设置，否则每次都要选学科。
11. **外部来源未核验**：外部 AI JSON 的 `source_quote`/页码由外部模型提供，系统只校验结构，不逐字核对原文；因此默认 `source_quote_verified=false` 并进入待审核。
12. **外部长课件分片**：当前按 shard 文件逐个导入并用 `point_id`/标题去重，不是一次上传多文件合并；分片之间可能出现标题不一致。
13. **并发受 provider 限制**：`AI_EXTRACTION_CONCURRENCY` 默认 3，provider 速率限制/超时可能抵消并发收益；合并阶段仍串行。
14. **真实模型优化后未重跑**：已有固定延迟 mock 对照和优化前真实任务数据，但尚未用 `deepseek-flash`/DSF1017 重跑完整 66 分块；不要引用未测得的提速数字。
15. **AI 题目语义事实未自动验证**：只校验选项/答案/题型/知识点归属等结构一致性，题干与解析的事实正确性仍依赖人工审核；所有 AI 题默认 pending。
16. **出题任务不是持久队列**：使用 BackgroundTasks；服务重启会把运行中任务标记失败，用户可重试；固定最多 4 次模型调用，可能少于请求题量。
17. **练习章节过滤是精确匹配**：选择父章节不会自动包含子章节题目；错题本只聚合 approved 题目。
18. **没有掌握度/间隔复习**：当前只有练习会话、答题明细和错题；学习分析算法未开发。
19. **真实 AI 出题未联调**：测试使用 FakeAI；尚未用真实模型验证题目质量、成本和延迟。

### 下一步

1. 保持“重新识别整章”的二次确认；后续可增加“最近一次任务摘要”，减少重复启动。
2. 评估把取消升级为可中断的 AI 调用（异步或子进程），缩短停止延迟。
3. 稀疏 PDF 按页检测/提示；视需要合并相邻小页分块。
4. 多来源 chunk/locator 结构（迁移 + 服务 + 审核页展示）。
5. 合并阶段按批次更新 `merging` 进度。
6. UTF-16 TXT 与 `uploaded` 卡住问题。
7. 智能导入增强：支持对建议章节拖拽/编辑后再确认、评估用模型辅助学科分类（仅在高置信度时采用）。
8. 外部 AI 导入增强：支持多 shard 合并上传、章节路径可视化编辑、来源页/引文与原文的抽样核验。
9. 用真实模型跑一次 66 分块对照，记录 `timings`；根据 provider 限流调整默认并发，评估合并阶段分批进度。
10. 用真实模型验证 AI 出题质量、成本和失败率；补充题目版本/历史和重复合并。
11. 学习分析：掌握度、错题重练计划、间隔复习；基于已有 `practice_answers` 扩展。
12. DSF1017 联调：先测连接，再用小资料验证，最后跑完整章节。
13. 只在用户确认后创建首个 Git 基线提交。

## 9. 工作区与权限

项目位于 DSH 会话工作区之外：

```text
C:\Users\bzlciallo\Documents\Codex\2026-10-19\biolearn-ai-git-python-node-js
```

当前 DSH 文件策略为 `danger-full-access`，可直接修改。DSH 工作区仍是 `C:\Users\bzlciallo\Documents\deepseek-harness\default-workspace`。不要在没有备份的情况下移动或重置项目。
