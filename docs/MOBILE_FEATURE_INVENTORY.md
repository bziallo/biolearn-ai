# BioLearn AI 移动端功能盘点（2026-10-22）

## 0. 盘点结论

本轮只做**只读盘点与计划**，没有修改业务代码、真实数据库、签名、包名、Release 标签或网络暴露。

| 项 | 实际值 |
| --- | --- |
| 分支 | `main` |
| HEAD | `1ac8867`（7C 文档） |
| 7C 代码 | `77ebb3b` |
| `v1.0.0-rc.1` | `930f279`，未移动 |
| 真实库 | `0009_question_bank`，未修改 |
| 真实数据 | 10 学科 / 6 章节 / 2 资料 / 117 分块 / 78 知识点 / 7 题 / 3 练习 / 6 答题 |
| 默认数据源 | FastAPI；本地开关默认关闭 |
| 本地 Schema | v3 |
| 插件 | SQLite `7.0.3`、Filesystem `7.1.9` |

**总体判断：**

- 现有业务页面仍是 **FastAPI 直连**，不是 Repository 驱动；
- 7B/7C 的本地 SQLite、文件存储和待上传队列是**诊断/合成数据基础层**；
- 现有离线能力只有 **Subjects 列表**与 **SubjectKnowledge 快照**的 IndexedDB/localStorage 缓存；
- 没有本地业务 CRUD、本地刷题、错题本/收藏、本地搜索/学习统计、备份恢复；
- 因此不能把 7C 的“本地文件解析”误认为“移动端业务已经离线可用”。

---

## 1. 逐模块盘点

> 状态只用以下五类：**已完整实现 / 部分实现 / 未实现 / 仅在线可用 / 需要真机验证**。
> 本盘点的“实现”以实际页面调用、API 路由、Repository 使用、SQLite 表和测试代码为依据，不按文件名推断。

### 1. 课程与章节管理

**结论：仅在线可用。**

| 项 | 实际 |
| --- | --- |
| 页面 | `SubjectsPage.tsx`、`SubjectDetailPage.tsx`、`SubjectKnowledgePage.tsx` |
| API | `/api/v1/subjects`、`/api/v1/subjects/{id}`、`/api/v1/subjects/{id}/chapters`、`/chapters/{id}` |
| 前端访问 | 直接调用 `frontend/src/lib/api/subjects.ts`、`chapters.ts`；**没有**调用 `createRepositoryBundle()` |
| Repository | `LocalRepositoryBundle` 只有 `courses.list/get/chapters` 的只读方法；无 create/update/delete |
| SQLite | `local_courses`、`local_chapters`（v3 已有）；只有 `seedSynthetic()` 和只读 `readAll()` |
| 离线 | Subjects 列表有 IndexedDB 缓存；课程详情/章节树没有独立缓存；离线不能编辑 |
| 测试 | `SubjectsPage.test.tsx`（列表/空状态/错误）、`SubjectDetailPage.test.tsx`（三级树/详情）、`SubjectKnowledgePage.test.tsx`；后端 `test_subjects.py`、`test_chapters.py` |
| 缺口 | 本地 CRUD、事务、章节移动/删除保护、离线详情、页面到 Repository 的切换 |

### 2. 资料导入、文件管理和解析

**结论：仅在线可用。**

| 项 | 实际 |
| --- | --- |
| 页面 | `ImportPage.tsx`、`DocumentsPage.tsx`、`KnowledgeReviewPage.tsx`、`DocumentUploadCard.tsx` |
| API | `/api/v1/documents`、`/documents/{id}`、`/documents/{id}/parse`、`/documents/{id}/chunks`、`/imports`、`/imports/{id}` |
| 前端访问 | 直接 API；上传/解析/AI 导入/重试/删除均依赖 FastAPI |
| Repository | `documents.listByCourse` 只读；没有本地文档 CRUD；7C 文件服务没有被 `DocumentsPage` 使用 |
| SQLite | `local_documents`、`local_chunks`、`local_files`、`local_parse_jobs`、`local_upload_jobs` |
| 离线 | 文档列表、分块查看、上传、解析、重试均无离线回退；7C 只做诊断页私有 TXT/MD |
| 测试 | `DocumentsPage.test.tsx`（列表/分块/归属）、`ImportPage.test.tsx`（5 个场景）、`DocumentUploadCard.test.tsx`；后端 `test_documents.py`、`test_imports.py`、`test_parsing.py` |
| 缺口 | 业务页读取本地文件/本地文档、离线分块预览、上传队列与文档页关联、parse_warnings/page_count 等字段 |

> 7C 的“本地 TXT/MD 解析”只在 `/settings/local-db` 诊断页；它不是 `DocumentsPage` 的业务路径，也不能替代 PDF/DOCX/PPTX 服务端解析。

### 3. 知识点管理

**结论：仅在线可用。**

| 项 | 实际 |
| --- | --- |
| 页面 | `SubjectKnowledgePage.tsx`、`KnowledgeReviewPage.tsx` |
| API | `/api/v1/documents/{id}/knowledge-points`、`/knowledge-points`、`/knowledge-points/{id}`、`/review`、`/bulk-review`、`/merge`、`/documents/{id}/knowledge-jobs` |
| 前端访问 | 直接 API；AI 提取、审核、编辑、删除、合并均在线 |
| Repository | `knowledgePoints.listByCourse/listByDocument` 只读；没有 create/update/delete/review |
| SQLite | `local_knowledge_points`、`local_chunks`；只有 seed 合成知识点，没有业务页读写 |
| 离线 | SubjectKnowledge 有整页快照缓存（课程+章节+资料+知识点+题）；KnowledgeReview 无缓存 |
| 测试 | `SubjectKnowledgePage.test.tsx`（含离线缓存）、`KnowledgeReviewPage.test.tsx`（树/详情/来源/取消/重提取）；后端 `test_knowledge.py` |
| 缺口 | 本地层级（parent_id）、条件/引用/来源字段、本地增删改审、离线审核 |

### 4. 题库管理

**结论：仅在线可用。**

| 项 | 实际 |
| --- | --- |
| 页面 | `QuestionsPage.tsx` |
| API | `/api/v1/questions`（列表/搜索/筛选）、`POST/PATCH`、`/review`、`/bulk-review`、`/generate`、`/generation-jobs`、`/regenerate` |
| 前端访问 | 直接 API；AI 生成、人工编辑、审核、批量审核均在线 |
| Repository | `questions.listByCourse` 只读；没有本地创建/编辑/删除/审核 |
| SQLite | `local_questions`、`local_question_knowledge_points`；只有 seed 合成题 |
| 离线 | 无题库缓存；离线打开 `QuestionsPage` 会请求 API 失败 |
| 测试 | `QuestionsPage.test.tsx`（列表/筛选/审核），后端 `test_questions.py` |
| 缺口 | 本地题型/选项/答案/解析/评分规则、本地 CRUD、离线搜索、题目与知识点关联的事务 |

### 5. 刷题、判分、练习历史

**结论：仅在线可用。**

| 项 | 实际 |
| --- | --- |
| 页面 | `PracticePage.tsx` |
| API | `/practice/sessions`（创建/列表/详情/提交/结果）、`/practice/answers/{id}/grade`、`/practice/wrong-questions` |
| 前端访问 | 直接 API；开始练习、提交、自动判分、简答人工评分、历史/错题均在线 |
| Repository | `practice.sessionsByCourse/answers` 只读；没有本地 start/submit/grade/history |
| SQLite | `local_practice_sessions`、`local_practice_answers`；只有 seed 一条练习 |
| 离线 | 无本地练习；离线时不能开始/提交/评分 |
| 测试 | `PracticePage.test.tsx`（开始/提交/简答人工评分/错题），后端练习服务测试 |
| 缺口 | 本地选题/组卷、答案判分、会话持久化、未完成进度恢复、历史列表、错题聚合 |

### 6. 错题本、收藏与复习

**结论：部分实现。**

| 项 | 实际 |
| --- | --- |
| 页面 | `PracticePage.tsx` 的错题面板/“只练错题” |
| API | `/practice/wrong-questions`；错题由服务端从答题记录计算 |
| 收藏 | **没有**收藏页面、API、Repository、SQLite 表 |
| 复习 | 只有练习中的错题再练；没有间隔重复、复习计划、掌握度 |
| SQLite | 无 `local_favorites`、无 `local_wrong_questions` |
| 测试 | `PracticePage.test.tsx` 覆盖错题；无收藏/复习测试 |
| 缺口 | 收藏表与页面、离线错题本、错题解决/忽略、复习队列、与练习/知识点的关联 |

### 7. 搜索与学习统计

**结论：部分实现。**

| 项 | 实际 |
| --- | --- |
| 搜索 | `QuestionsPage` 调 `/questions?q=` 搜索题干/解析；`KnowledgeReviewPage` 只在已加载树中客户端过滤名称/解释；无全局搜索页 |
| 统计 | `QuestionsPage` 题目审核统计、`DocumentsPage` 文档计数、`KnowledgeReviewPage` 知识点统计、`SubjectDetailPage` 章节统计；**没有学习统计**（练习正确率趋势、错题分布、复习完成度） |
| Repository | 无搜索/统计接口；`LocalRepositoryBundle` 无聚合方法 |
| SQLite | 可用 `LIKE` 查询已有文本；无统计表/FTS/学习事件表 |
| 测试 | Questions/KnowledgeReview 页面测试覆盖局部过滤；无全局搜索/学习统计测试 |
| 缺口 | 本地跨课程搜索、搜索结果定位、学习统计聚合、空结果/离线提示 |

### 8. AI 知识提取与题目生成

**结论：仅在线可用。**

| 项 | 实际 |
| --- | --- |
| 页面 | `AISettingsPage.tsx`、`ImportPage`（AI 分析/确认）、`KnowledgeReviewPage`（提取/重提取/取消）、`QuestionsPage`（生成/重生成/取消/重试） |
| API | `/ai/status|config|test`、`/documents/{id}/knowledge-jobs`、`/questions/generate`、`/generation-jobs` |
| 前端访问 | 直接 API；AI Key 只提交给后端，不在客户端持久化 |
| Repository | 无 AI Repository；AI 不是本地能力 |
| SQLite | 无 AI 任务表（只有 7C 的本地解析/上传任务，不是 AI） |
| 测试 | `AISettingsPage.test.tsx`（不回显 Key）、`ImportPage` AI 场景、`KnowledgeReviewPage`/`QuestionsPage` 任务场景；后端 AI 测试 |
| 缺口 | 明确“AI 不可用时本地题库/解析仍可用”的 UI 与降级路径；AI 任务不在本地队列 |

### 9. 设置、备份与恢复

**结论：部分实现。**

| 项 | 实际 |
| --- | --- |
| 页面 | `ConnectionSettingsPage.tsx`、`AISettingsPage.tsx`、`LocalDatabasePage.tsx` |
| API | `/health`、`/auth`、`/ai/*`；无备份/恢复 API |
| Repository | 无备份/恢复接口 |
| SQLite | `local_meta` 只存键值；`exportData()` 是合成数据 JSON，不含文件/任务，不是用户备份 |
| 备份/恢复 | **未实现**（没有“导出全部本地数据/恢复校验/冲突处理”） |
| 测试 | `ConnectionSettingsPage` 相关 API 测试、`AISettingsPage.test.tsx`、`HomePage` 连接状态；无备份恢复测试 |
| 缺口 | 用户备份清单、文件+DB 一致性、校验和、恢复前保护、迁移前快照、`allowBackup`/SQLCipher 决策 |

### 10. Android 导航、返回、离线状态与异常提示

**结论：部分实现。**

| 项 | 实际 |
| --- | --- |
| 导航 | `AppLayout.tsx` 顶部导航 + 底部 tab bar；React Router |
| 返回 | `MainActivity.java` 优先 `WebView.goBack()`，否则原生返回 |
| 离线状态 | `OfflineBanner` 基于 `navigator.onLine`；只说明“只能浏览已缓存内容” |
| 离线缓存 | Subjects 列表、SubjectKnowledge 快照；登录/退出清空；其他页面无缓存 |
| 异常 | 页面有 Notice/Toast；上传/导入提示网络中断；但离线题库/练习/资料页仍会直接失败 |
| 测试 | `HomePage.test`（在线/离线）、`SubjectKnowledgePage.test`（缓存/离线）、`SubjectKnowledgePage` 真实设备 7B/7C 验证；无完整飞行模式矩阵 |
| 缺口 | 课程详情/资料/题库/练习的离线矩阵、Android 返回键回归、进程重启后的页面状态、网络恢复刷新策略 |

---

## 2. 状态汇总

| 模块 | 状态 | 真机状态 | 关键缺口 |
| --- | --- | --- | --- |
| 课程与章节 | 仅在线可用 | 部分已验证（7B 缓存列表） | 本地 CRUD、离线详情、Repository 接入 |
| 资料导入/文件/解析 | 仅在线可用 | 部分验证（7C 仅私有 TXT/MD） | 业务页本地文件、离线分块、上传队列关联 |
| 知识点 | 仅在线可用 | 部分验证（7B 快照） | 本地层级/审核/CRUD |
| 题库 | 仅在线可用 | 需补测离线 | 本地题目 CRUD/搜索/关联 |
| 刷题/判分/历史 | 仅在线可用 | 需补测离线 | 本地组卷/判分/会话恢复 |
| 错题/收藏/复习 | 部分实现 | 需补测；收藏未实现 | 收藏缺失；错题在线；复习未实现 |
| 搜索/学习统计 | 部分实现 | 未实现全局能力 | 全局搜索、学习统计缺失 |
| AI | 仅在线可用 | 需补测离线降级 | 离线降级、任务本地化 |
| 设置/备份恢复 | 部分实现 | 备份恢复未验证 | 备份恢复缺失；迁移前保护 |
| Android 导航/离线 | 部分实现 | 返回键已做基础验证，完整矩阵需补测 | 完整离线矩阵、返回键回归 |

> “真机状态”是补充列，不替代左侧单一功能状态；本阶段没有一项达到完整移动端离线可用。

**没有一项达到“完整移动端离线可用”。**

---

## 3. Schema v3 评估

### 3.1 v3 已能表达

- 课程 → 章节 → 资料 → 知识点/题目；
- 题目选项 `options`、答案 `answer`、解析 `explanation`、题型 `question_type`；
- 题目-知识点多对多；
- 练习会话/答题、分数/判分/快照；
- 文件记录、解析任务、上传任务；
- 稳定本地 ID、`server_id`、外键、部分索引；
- 7C 私有文件路径/SHA/大小。

### 3.2 v3 缺口（独立移动端所需）

| 领域 | 缺口 |
| --- | --- |
| 知识点 | `parent_id`（层级）、`conditions`、`source_quote`、`source_quote_verified`、`source_page_end/slide/locator`、`importance`、`prerequisites`、`duplicate_of_id`、`needs_review`、`review_note`、`reviewed_at`、`published_at` |
| 题目 | `grading_rule`、`source_document_id`、`source_locator`、`generation_job_id`、`ai_provider/model`、`confidence`、`score`、`reviewed_at`、`published_at` |
| 文档 | `parse_warnings`、`page_count`、`slide_count`、`content_title` |
| 练习 | `filters`、`answered_count`、`pending_manual_count`、`created_at` |
| 错题/收藏 | 无 `local_wrong_questions`、无 `local_favorites` |
| 本地管理 | 无 create/update/delete/事务 API；Repository 只读 |
| 搜索/统计 | 无统一查询/聚合；可用 LIKE，无需 FTS 也可起步 |
| 备份/恢复 | 无完整本地备份格式；迁移前保护未实现 |

**结论：v3 是“只读合成数据 + 文件基础层”，不足以支撑独立移动端。需要 v4；但不能删除数据库重建。**

---

## 4. 关键风险

1. **页面直连 API**：即使本地有数据，页面也不读；只改数据库不会产生业务效果。
2. **离线缓存只覆盖两页**：其他页面在飞行模式下会直接失败。
3. **v3 字段不足**：知识点层级/题目评分规则/收藏/错题/练习统计无法无损表达。
4. **无备份恢复**：v4 迁移前无保护；用户无法导出/恢复本地学习记录。
5. **`allowBackup=true`**：私有文件和本地 DB 可能进入 Android 云备份，尚未处理。
6. **上传无幂等**：7C 已正确暂停真实上传；8A 不应偷偷打开自动上传。
7. **移动端导航/返回**：已有 WebView 返回逻辑，但缺少完整真机回归矩阵。

---

## 5. 盘点证据

- 路由：`frontend/src/router.tsx`（无收藏/搜索/统计/备份页面）
- 布局/导航：`frontend/src/layouts/AppLayout.tsx`
- Android 返回：`frontend/android/app/src/main/java/ai/biolearn/app/MainActivity.java`
- 离线缓存：`frontend/src/lib/offline/cache.ts`、`network.ts`、`OfflineBanner.tsx`
- 本地 Repository：`frontend/src/lib/local/repositories.ts`（只读，页面未使用）
- 本地 Schema：`frontend/src/lib/local/schema.ts`（v3）
- 本地 DB 方法：`frontend/src/lib/local/localDatabase.ts`（seed/export/import/files/jobs，无业务 CRUD）
- 后端模型：`backend/app/models/question.py`、`knowledge.py`、`document.py`、`subject.py`、`chapter.py`
- 页面/API/测试：见上表及 `frontend/src/pages/*.test.tsx`、`backend/tests/test_*.py`

> 本盘点只读；未修改任何业务代码或真实数据。
