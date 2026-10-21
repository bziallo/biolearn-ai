# BioLearn AI → DSH 交接说明

## 目标

把当前项目交给 DSH 继续开发，目标模型为 DSH 中配置的 **DSF1017**。

本轮已完成：接管检查、解析/测试修复、AI 识别停止、智能资料导入、外部 AI JSON 导入、网页 AI 并发优化、知识点闭环审查、题库/智能练习 MVP、迁移 `0006–0009`、**V1.0 功能冻结与 Windows 本地部署封装**。下一步优先用真实模型验证出题质量，并继续学习分析，不要做无关大规模重构。

## 当前现场（2026-10-21 09:35 Asia/Shanghai）

### Git

- 分支：`main`
- 提交：**0 个提交**，没有 HEAD
- 远程：未配置
- stash：无
- 未跟踪：176 条（源码/脚本/文档；`.env`、数据库、上传、日志、`dist/` 均被忽略）
- **不要擅自 commit**

### 服务（V1.0 单端口部署）

- 生产访问：`http://127.0.0.1:8000/`（后端同时提供 API 与 `frontend/dist` 页面）
- 启动 `start.bat`、停止 `stop.bat`、开发 `start-dev.bat`（Vite 5173）
- 数据：`backend/data/biolearn.db`、`backend/data/uploads/`、`backend/data/ai_config.json`
- 日志：控制台；`backend/data/server.err.log`

### 真实数据

- 10 个学科、7 个章节（含 2 个验收临时章节）
- 2 份真实资料：PDF 66 分块（39 approved 知识点）、PPTX 51 分块（39 pending 知识点）
- 1 份验收临时外部 JSON 资料（0 分块，1 条 approved 验收知识点）
- 5 道用户生成题目（approved）+ 2 道验收临时题目（rejected）
- 2 个用户练习会话（1 completed + 1 in_progress）+ 1 个验收会话（completed）
- 5 条答题明细、3 条错题、4 个导入任务、5 个出题任务（其中 2 次失败）
- 上传文件：1 个 PDF + 1 个 PPTX + 1 个外部 JSON

**不要删除这些资料、章节、分块、知识点或任务行；不要重置数据库。已通过内容不得回退，pending 内容不得被批量覆盖。**

### 本轮新增：V1.0 部署封装（2026-10-21）

- 后端托管前端构建产物（`SERVE_FRONTEND`、`FRONTEND_DIST_DIR`），单端口运行；SPA 回退与 API 404 分离。
- CORS 允许本地回环任意端口；前端生产构建默认同源 API。
- 相对路径统一按 `backend/` 解析，从任意工作目录启动都指向同一数据。
- 脚本：`install.bat`、`build_frontend.bat`、`start.bat`、`stop.bat`、`backup.bat`、`restore.bat`、`start-dev.bat`；`scripts/` 下 5 个 Python 工具。
- 迁移前自动备份；恢复不删除旧数据；已实测备份/恢复/重启数据保留。

### 本轮新增：知识点闭环与题库（23:05）

- 修复编辑已通过知识点后仍保持 approved 的缺口：内容变更重新 pending，需再次审核。
- 知识点列表 API 增加 `q`/`point_type`/`origin`/`needs_review`/分页；审核页增加搜索和状态筛选。
- 迁移 `0009_question_bank`：questions、question_generation_jobs、question_knowledge_points、practice_sessions、practice_answers。
- AI 出题只使用 approved 知识点；结构化校验、重复跳过、最多 4 次模型调用、失败/取消/重试、题目默认 pending。
- 题库页 `/questions`、练习页 `/practice`；自动判分、错题本、简答人工评分。
- 备份 `D:\BioLearnBackup\2026-10-19-2302\biolearn-before-question-bank.db`，SHA-256 `0f47333ea785208ac52f68fbae83eeb81592c57ca13f0f8e5390544360e2fa17`。

### 历史新增（22:25）：外部 AI 与并发优化

- 外部 AI JSON：`schema_version 1.0`、Pydantic 校验、预览确认、章节匹配/创建、重复检测、`skip/update_pending`、原始 JSON 留档、模板接口。
- 外部知识点字段：`importance`、`prerequisites`、`external_id`；默认 `pending`、`origin=ai`、`source_quote_verified=false`。
- 网页 AI：`AI_EXTRACTION_CONCURRENCY` 有界并发（默认 3）、分析/提取/合并/保存 `timings`、提示词压缩、部分失败重试、真实阶段显示。
- 迁移 `0008_external_import` 已应用；备份 `D:\BioLearnBackup\2026-10-19-2225\biolearn-before-external.db`。

### 智能导入（0007）

- 页面：`/import`；API：`/api/v1/imports`、`/imports/preferences`。
- 模式：`preset`（预设章节）、`auto_create`（自动建章）、`smart_archive`（智能归档）。
- 偏好表 `import_preferences`；导入任务表 `import_jobs`；章节来源列 `source_document_id` / `source_import_job_id` / `source_slide`。
- 迁移 `0007_smart_import` 已应用到真实库；备份 `D:\BioLearnBackup\2026-10-19-2110\biolearn-before-smart-import.db`。
- 识别规则：PPT 目录页/编号标题/标题占位符；DOCX/Markdown 标题层级；PDF 无结构时只建议资料标题章节。不把普通 PPT 幻灯片标题批量当成章节。
- 归档安全：同父级同名复用；同名异父级/相似名称待确认；单事务建章；同一文件按学科去重；跨学科允许同名章节。
- 当前 `import_preferences` 为空，首次使用需要在 `/import` 选择学科并保存一次默认设置。
- 取消 AI 分析只停止分析，不删除已导入文件/章节；已审核知识点不会被覆盖。

### 任务 A：首次识别（已完成）

```text
job_id=b060e7e8-03a4-4130-8f15-918dd6bb8afc
status=completed
progress=100
extracted_count=252
merged_count=39
error=None
finished_at=12:23:54 UTC（20:23:54 本地）
```

### 任务 B：重复识别（已停止）

用户在 39 条知识点全部通过后又启动了一次重复识别：

```text
job_id=594fe265-6f48-4073-a704-9d98a2471395
created_at=12:39:26 UTC（20:39:26 本地）
status=cancelled
stage=已停止（服务重启中断）
progress=44
processed_chunks=32/66
extracted_count=0
merged_count=0
cancel_requested=1
error=None
finished_at=12:46:41 UTC（20:46:41 本地）
```

该任务没有生成新草稿。停止方式：停止旧后端 → 备份 → 迁移 `0006` → 标记 `cancel_requested` → 启动新后端；新恢复逻辑将其标记为 `cancelled`。

当前没有运行中的解析或 AI 任务。

### 任务 C：用户新导入 PPTX 的 AI 提取（已完成）

```text
job_id=a4ed602f-90eb-4b48-916d-dae40a11ee52
document_id=b8dfeebc-ad52-4790-a2a0-e2a9664172a3
status=completed
extracted_count=180
merged_count=0（历史行；实际生成 39 条 pending）
created_at=13:58:51 UTC（21:58:51 本地）
finished_at=14:21:43 UTC（22:21:43 本地）
```

该任务由用户在智能导入页面触发，属于真实业务数据；不要删除其 39 条待审核知识点。本轮新增的 `timings` 字段对历史任务为空，后续任务才会记录。

### AI 配置

- 运行时配置：`backend/data/ai_config.json`
- 模型字段：`deepseek-flash`，不是 DSF1017
- 该文件含真实 Key，已被 `.gitignore` 排除
- **不要读取、复制、展示或提交 Key**
- 三次真实任务都使用 `deepseek-flash`；没有 DSF1017 联调记录

## 本次完成的能力

### 停止 AI 识别

- `POST /api/v1/knowledge-jobs/{job_id}/cancel`
- `queued` 立即 `cancelled`；运行中先 `cancelling`，当前模型请求返回后 `cancelled`
- 审核页显示“停止 AI 识别”；`cancelling` 显示“正在停止…”
- 停止不保存本次新草稿；已通过/需修改/已忽略/人工知识点不受影响
- 停止是协作式的，最长约一次 `AI_TIMEOUT_SECONDS`（默认 90 秒）
- 服务重启时，`cancel_requested=1` 或 `cancelling` 的任务标记 `cancelled`；其他运行中任务标记失败
- “重新识别整章”增加二次确认，减少误触重复识别

### 迁移与修复

- `0006_job_cancellation` 增加 `cancel_requested`；真实库已应用
- 测试 `TestClient` 不再触发真实库恢复
- `retry-parse` 拒绝已解析/有知识点/有运行任务的资料
- 超长 block 拆分后记录真实字符范围
- 新增 4 项后端测试、1 项前端测试

## 关键文件

### 取消/任务

- `backend/app/services/job_control.py`
- `backend/app/services/knowledge.py`
- `backend/app/services/ai_client.py`
- `backend/app/services/recovery.py`
- `backend/app/api/v1/knowledge.py`
- `backend/app/models/knowledge.py`
- `backend/app/schemas/knowledge.py`
- `backend/alembic/versions/0006_job_cancellation.py`
- `frontend/src/pages/KnowledgeReviewPage.tsx`
- `frontend/src/lib/api/knowledge.ts`
- `frontend/src/lib/format.ts`

### 文档解析

- `backend/app/services/parsing.py`
- `backend/app/services/chunking.py`
- `backend/tests/test_parsing.py`
- `backend/tests/test_documents.py`

### 数据库

- `backend/app/models/`
- `backend/alembic/versions/`
- `backend/app/db/session.py`
- `backend/data/biolearn.db`（不提交）

### 配置

- `.env.example`（占位，无真实 Key）
- `.env`（本地，忽略）
- `backend/data/ai_config.json`（本地 Key，忽略）

## 启动命令

### 后端

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

当前进程**没有 `--reload`**；改代码后需要手动重启。

### 前端

```powershell
cd frontend
pnpm install
pnpm dev
```

## 本次验证结果

- 后端：**77 passed**（含 2 项 SPA 托管测试）
- 前端：TypeScript 通过；ESLint 通过；Vitest **12 个文件 / 26 passed**；生产构建通过（62 个模块）
- 迁移：空库 upgrade → downgrade → upgrade 通过；真实库副本 `0008 → 0009 → 0008 → 0009` 通过；真实库已到 `0009_question_bank`
- 真实 PDF：75 页/66 分块，重新解析与数据库逐字一致；9 页无文本
- 第二个真实 PDF：38 页/34 分块，4 页无文本
- 旧版 `.ppt`：`legacy_ppt_unsupported`
- 合成 DOCX/PPTX/TXT/MD：标题、表格、列表、幻灯片编号、代码块内容保留
- 取消 API：已完成/已取消任务返回 409 `job_not_cancellable`（实测）
- 停止当前重复任务：任务 B `cancelled`，39 条已通过知识点未变
- 智能导入：15 项后端测试覆盖预设归档、PPT 目录建章、预览确认、同文件去重、
  自动分析、取消分析保留资料、无目录回退、事务回滚、跨学科同名、智能归档复用/待确认
- 智能导入：3 项前端测试覆盖默认设置、预设归档、建议树确认、偏好保存
- 外部 JSON：9 项后端测试覆盖合法导入、语法/Schema/版本/超大文件、章节匹配、指定章节归档、
  重复文件/知识点、已审核保护、事务回滚、来源缺失、模板、200 条 payload
- 外部 JSON：2 项前端测试覆盖导入方式切换、模板加载、预览与确认
- 并发：2 项后端测试覆盖 3 分块并发、timings、部分失败后重试恢复
- 实测：真实 PDF 66 分块解析 0.433s；固定 50ms mock 串行提取 3.349s → 并发 3 提取 1.150s；草稿保存 0.003–0.007s
- 优化前真实任务：提取约 803s、合并约 1,161s、总计约 1,964s；未在优化后重跑真实模型

## 已知风险

1. **停止不是秒级**：无法中断已发出的单次 HTTP 模型请求；最长等待 90 秒。
2. **重新识别确认**：审核页已加二次确认；仍建议保留，避免误触。
3. **稀疏 PDF 判定**：`needs_ocr` 只看全文总字符数，不按页。
4. **多来源追踪**：只保存一个 `source_chunk_id`；27/39 条有引文不在 primary chunk 中。
5. **合并阶段无精确进度**：合并时只显示“合并中”；批次进度可继续增强。
6. **UTF-16 TXT 上传**：上传校验用 NUL 字节判定二进制。
7. **`uploaded` 卡住**：后台解析任务在设置 `parsing` 前失败时没有重试入口。
8. **后端无 `--reload`**：修改代码后必须重启才生效。
9. **智能导入结构识别是启发式**：没有模型语义分类；PPT 仅目录/编号/标题，组合形状和图片文字不参与。
10. **默认导入设置为空**：首次使用 `/import` 需要选择学科并保存一次默认设置。
11. **外部来源未核验**：外部 AI JSON 的引文/页码只做结构校验，不与原文逐字核对；默认待审核。
12. **外部长课件分片**：目前按文件逐个导入，分片间用 `point_id`/标题去重，不是一次多文件合并。
13. **并发受 provider 限制**：默认并发 3；速率限制/超时可能抵消收益，合并仍串行。
14. **真实模型优化后未重跑**：只有固定延迟 mock 对照和优化前真实数据，不能引用未测得的提速承诺。

## 推荐执行顺序

1. **不要删除** 资料、章节、分块、78 条知识点或任务行；不要重置数据库。39 approved 不得回退，39 pending 不得批量覆盖。
2. 日常备份：
   - `backend/data/biolearn.db`
   - `backend/data/uploads/`
   - `backend/data/ai_config.json`（含密钥，放加密/受控位置）
   - `docs/`、`README.md`
   - 记录 Git 状态和文件哈希
3. 在审核页确认 39 条新 pending 内容的来源和层级；停止功能只阻止新草稿，不会回退已审核内容。
4. 保留“重新识别整章”的确认框，减少重复识别。
5. 评估可中断的 AI 调用（异步或子进程），缩短停止延迟。
6. 继续导入/解析修复：稀疏 PDF 按页检测、UTF-16、`uploaded` 卡住、相邻小页分块。
7. 智能导入增强：允许编辑建议章节后再确认；评估模型辅助学科分类（仅高置信度采用）。
8. 外部 JSON 增强：多 shard 合并上传、章节路径编辑、来源抽样核验。
9. 用真实模型跑一次 66 分块对照并记录 `timings`；按 provider 限流调整并发。
10. 多来源 chunk/locator 结构（需要迁移）。
11. 合并阶段按批次更新 `merging` 进度。
12. DSF1017 联调：先测连接，再用小资料验证，最后跑完整章节。
13. 只在用户确认后创建首个 Git 基线提交。

## 安全保存/切换建议

- 本次备份：`D:\BioLearnBackup\2026-10-19-2046\biolearn-before-cancel.db`（SHA-256 `34d5e6fd…`）、`D:\BioLearnBackup\2026-10-19-2110\biolearn-before-smart-import.db`（SHA-256 `7d666322…`）、`D:\BioLearnBackup\2026-10-19-2225\biolearn-before-external.db`（SHA-256 `77e2aa95997a59ccdda93205b1394cfe0a2bea2f5e0314d65ea19c593666e2f1`）、`D:\BioLearnBackup\2026-10-19-2302\biolearn-before-question-bank.db`（SHA-256 `0f47333ea785208ac52f68fbae83eeb81592c57ca13f0f8e5390544360e2fa17`），上传目录也在对应目录。
- 备份目录放在仓库外，不要放进 `work/` 后随仓库移动。
- 不要通过聊天、文档、日志或 Git 输出真实 Key。
- 初次提交建议只包含源码、测试、文档、`.env.example` 和 `.gitignore`；数据库/上传/配置由外部备份。

## 工作区与权限

项目位于 DSH 会话工作区之外：

```text
C:\Users\bzlciallo\Documents\Codex\2026-10-19\biolearn-ai-git-python-node-js
```

当前 DSH 文件策略为 `danger-full-access`，可直接修改。DSH 工作区仍是 `C:\Users\bzlciallo\Documents\deepseek-harness\default-workspace`。不要在没有备份的情况下移动或重置项目。

## 最后验证记录

- 后端 pytest：77 passed（隔离临时库）
- 前端 TypeScript：通过
- 前端 ESLint：通过
- 前端 Vitest：12 个测试文件 / 26 passed
- 前端生产构建：通过（62 个模块）
- 真实库迁移：0009_question_bank 已应用
- 真实任务 A：completed，39 条知识点已审核通过
- 真实任务 B：cancelled，未生成新草稿
- 真实任务 C：completed，39 条 pending（用户 PPTX 导入）
- 题库：5 道用户题 + 2 道验收临时题（rejected）；练习 3 个会话、5 条答题明细
- V1.0 部署：`start.bat`/`stop.bat`/`backup.bat`/`restore.bat` 已实测；备份→恢复→重启数据完整
- 当前服务：单端口 `http://127.0.0.1:8000/`

交接待办：**AI 出题真实模型连续失败（结构校验未通过），需排查；DSF1017 未联调；停止为协作式；AI 题目只做结构校验、事实仍需人工审核；智能导入/外部来源为启发式/未核验；稀疏 PDF、多来源、合并进度待处理；Git 无提交。**
