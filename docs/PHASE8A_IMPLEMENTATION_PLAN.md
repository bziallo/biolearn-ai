# 阶段 8A 详细实施计划（待确认）

日期：2026-10-22
状态：**计划稿；等待确认后才修改业务代码。**
基于：`docs/MOBILE_FEATURE_INVENTORY.md`、7A/7B/7C 验收记录、当前 `main@1ac8867`。

---

## 一、8A 目标

把移动端从“FastAPI 页面 + 两个离线缓存 + 诊断式本地库”推进到：

> **课程/章节/资料元数据/知识点/题库可以在本机 SQLite 中查询、创建、编辑、删除；已下载课程在飞行模式下可完整浏览；所有数据访问经过 Repository；默认仍是 FastAPI。**

8A 只实现第三阶段的 **A（课程、章节、资料、知识点、题目、资料的本地查询与管理）**。
B（刷题/错题/收藏）、C（搜索/统计）、D（AI）不在 8A 实现，但 v4 会一次性补齐它们所需的结构，避免频繁迁移。

### 8A 完成后用户应能做到

- 开关关闭：现有 FastAPI 页面、上传、AI 完全不变。
- 开关开启：
  - 从服务器把某一门课程下载到本机；
  - 飞行模式下打开课程、章节、资料元数据、知识点、题目；
  - 本地新建/编辑/删除课程、章节、知识点、题目；
  - 本地导入 TXT/MD，文件与文档记录关联；
  - 重启应用后数据仍在；
  - 不联网也能浏览，不显示“正在请求 API”或过期数据；
  - 不把本地修改自动上传服务器。

### 明确不在 8A

- 本地刷题、判分、练习历史（8B）
- 错题本、收藏、复习计划（8B）
- 全局搜索、学习统计（8C）
- 联网 AI 提取/生成的离线化（8D）
- 双向同步、删除同步、冲突解决
- 自动上传（服务端幂等键未完成）
- PDF/DOCX/PPTX 本地解析
- 跨设备共号/账号合并

---

## 二、Schema v4 设计

### 2.1 为什么必须 v4

v3 能表达基本关系，但缺少：

- 知识点层级、条件、引用来源、重要度、前置知识、审核字段；
- 题目评分规则、来源资料、生成任务、AI 元数据、审核字段；
- 文档解析警告/页数/幻灯片数；
- 练习会话筛选条件、已答数、待人工评分；
- 收藏表、错题状态表；
- 迁移前备份保护。

这些字段在现有 `KnowledgeReviewPage`、`QuestionsPage`、`PracticePage` 中已经存在服务端语义，若本地模型缺失，本地编辑/离线展示会丢信息。

### 2.2 v4 变更（只增不删）

**A. `local_knowledge_points` 增加：**

`parent_id`（FK 自身）、`conditions`、`source_quote`、`source_quote_verified`、`source_page_end`、`source_slide`、`source_locator`、`importance`、`prerequisites`（JSON）、`duplicate_of_id`、`needs_review`、`review_note`、`reviewed_at`、`published_at`。

**B. `local_questions` 增加：**

`grading_rule`（JSON）、`source_document_id`、`source_locator`、`generation_job_id`、`ai_provider`、`ai_model`、`confidence`、`score`、`reviewed_at`、`published_at`。

**C. `local_documents` 增加：**

`parse_warnings`、`page_count`、`slide_count`、`content_title`。

**D. `local_practice_sessions` 增加：**

`filters`（JSON）、`answered_count`、`pending_manual_count`、`created_at`。

**E. 新表：**

```sql
local_wrong_questions (
  question_id TEXT PRIMARY KEY REFERENCES local_questions(id) ON DELETE CASCADE,
  wrong_count INTEGER NOT NULL DEFAULT 0,
  last_answer TEXT NOT NULL DEFAULT '{}',
  last_answered_at TEXT,
  resolved_at TEXT
)

local_question_favorites (
  question_id TEXT PRIMARY KEY REFERENCES local_questions(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL
)

local_knowledge_favorites (
  knowledge_point_id TEXT PRIMARY KEY REFERENCES local_knowledge_points(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL
)
```

> 收藏拆成题目/知识点两张表，避免多态外键无法约束。8A 只创建表，不实现收藏 UI。

**F. 索引：**

- `local_knowledge_points(parent_id)`、`(course_id, chapter_id)`
- `local_questions(source_document_id)`、`(course_id, status)`
- `local_practice_sessions(course_id, started_at)`
- `local_wrong_questions(resolved_at, last_answered_at)`

**G. 不引入 FTS5：**

本地数据量预期小，8A 搜索用 `LIKE` + 现有索引；8C 再评估 FTS。

### 2.3 迁移安全

顺序：

1. 读取 v3 `schema_migrations`、`user_version`；
2. 若 schema < 4，先写 **迁移前快照**：
   - 导出所有 v3 表行（含 files/parse/upload jobs）；
   - 记录 schema 版本、行数、时间、格式版本；
   - 写入 `biolearn/backups/pre-v4-<timestamp>.json`；
   - SHA-256 校验写盘后文件；
   - 快照失败 → 不迁移。
3. `BEGIN` → 所有 v4 `ALTER/CREATE/INDEX` → 写 `schema_migrations(4)` → `PRAGMA user_version=4` → `COMMIT`；
4. 任一步失败 → `ROLLBACK`；v3 保持可用；
5. 启动时检测 `user_version` 与 `schema_migrations` 不一致 → 明确错误，不自动删除数据库；
6. 不执行 `DROP TABLE`、不重建 DB；
7. 真实服务端数据库、Alembic 历史完全不参与。

**恢复策略：**

- v4 失败：保留 v3 + 快照，页面提示“迁移失败，数据未变”；
- 快照仅供恢复/诊断，不自动覆盖；
- 8A 只做“迁移前保底”，完整用户备份/恢复 UI 留到后续阶段（见开放决策）。

---

## 三、Repository 设计

### 3.1 现有问题

`createRepositoryBundle()` 已存在，但：

- 没有任何业务页面调用；
- local bundle 只有只读查询；
- 页面直接 import API；
- 功能开关只影响诊断页。

### 3.2 目标接口

```ts
interface LocalDataRepository {
  courses: {
    list(); get(id); create(input); update(id, input); delete(id);
  }
  chapters: {
    list(courseId); get(id); create(courseId, input);
    update(id, input); delete(id); move(id, direction);
  }
  documents: {
    listByCourse(courseId); get(id); updateAttribution(id, input);
    delete(id); importLocalFile(file); listChunks(documentId);
  }
  knowledgePoints: {
    listByCourse(courseId); listByDocument(documentId); get(id);
    create(input); update(id, input); delete(id); review(id, status);
  }
  questions: {
    listByCourse(courseId); get(id); create(input); update(id, input);
    delete(id); review(id, status);
  }
  downloads: {
    downloadCourse(courseId, onProgress); status(courseId);
  }
}
```

所有写操作：

- 一个业务操作 = 一个事务；
- 外键/唯一约束由 SQLite 兜底；
- 删除课程/章节时先做引用检查；
- 删除资料时同步删除 chunks/KP/题关联，并删除私有文件（仅受控路径）；
- 所有本地实体使用 UUID；下载实体保留 `server_id`；
- 更新 `updated_at`/`version`；
- 本地写 `sync_state`：
  - 下载：`synced`
  - 本地新建：`pending_create`
  - 本地修改：`pending_update`
  - 本地删除：`pending_delete` 或直接删除（8A 不推服务端，优先直接删除 + 审计）

### 3.3 页面接入方式

- 新增 `RepositoryProvider` + `useRepository()`（或 `useDataRepository()`）；
- 页面不再直接 import `createSubject/update...` 等数据函数；
- flag 关闭：bundle 为 remote adapter（内部仍调用现有 API）；
- flag 开启：bundle 为 local adapter；
- `health`、`AI`、`上传到服务器` 仍保留独立 API 客户端；
- 先改造 5 个 A 页面：
  1. `SubjectsPage`
  2. `SubjectDetailPage`
  3. `DocumentsPage`
  4. `SubjectKnowledgePage`
  5. `QuestionsPage`
- `ImportPage` 的“服务器导入”保持 API；“本地 TXT/MD”继续走 7C 文件服务，但在 8A 中接入本地文档/资料列表。
- `KnowledgeReviewPage` 的 AI 提取/审核仍在线；本地审核只对已下载知识点可编辑，不在 8A 做 AI。

### 3.4 默认行为

- `VITE_MOBILE_LOCAL_DB=false`；
- 运行时 key 不变：`biolearn.mobile_local_db`；
- 关闭 → remote + 现有缓存，业务行为与 7C 一致；
- 开启 → local；页面显示“本机数据”标记；
- 不要求删除 DB 回滚；关闭后本地数据保留但页面回到 FastAPI；
- 回滚不触碰真实服务端数据。

---

## 四、下载（单向，不是同步）

### 4.1 为什么需要

本地空库无法离线；必须先把已授权课程拉成本地快照。

### 4.2 规则

- 入口：课程列表/课程详情“下载到本机”；
- 范围：单门课程（course + chapters + document metadata + chunks + KP + questions + relations）；
- 分页拉取（API 已有 limit/offset）；
- 事务 upsert：
  - 以 `server_id` 匹配；
  - `synced` 行可更新；
  - `pending_*` 本地行**不覆盖**；
  - 服务器已删除的条目在 8A **不自动删除**（避免误删本地学习记录）；
- 进度/结果：课程、章节、资料、知识点、题目数量；
- 失败：整个下载事务回滚，保留旧本地快照；
- 不下载 AI Key、服务端配置、其他用户数据；
- 下载完成后可飞行模式浏览。

### 4.3 明确不做的同步

- 不上传本地修改；
- 不删除服务器内容；
- 不做冲突合并/双向同步；
- 不做后台定时同步。

> 这是“离线快照 + 本地工作区”，不是“多端同步”。

---

## 五、实施顺序（建议分 4 个可审查批次）

### 8A-0 预检与保护（0.5 天）

- 复核 HEAD/worktree/tag/DB；
- 记录 v3 表行数、文件清单、SHA；
- 设计并测试迁移前快照格式；
- 不改业务页面。

**门禁：** 快照校验通过；v3 备份可读；现有 117/59 测试基线不变。

### 8A-1 Schema v4 + Repository 契约（2–3 天）

- 实现 v4 迁移；
- 实现迁移前快照；
- 扩展类型/Repository 接口；
- 实现 local CRUD（课程/章节/资料元数据/KP/题目）；
- 实现 remote/local bundle 与 Provider；
- 测试：
  - v3→v4、重复迁移、失败回滚；
  - 快照校验；
  - CRUD/事务/FK/唯一约束/级联；
  - local/remote 契约测试；
  - flag 关闭回归。

**门禁：** 全部单测通过；页面尚未切换，默认行为不变。

### 8A-2 下载与离线快照（2 天）

- 单课程下载；
- upsert/保留本地行；
- 进度和错误；
- 本地文档/文件关联；
- 测试下载幂等、失败回滚、离线读取、重启恢复。

**门禁：** 合成课程下载后飞行模式可浏览；不修改真实数据。

### 8A-3 页面接入（3–4 天）

- 5 个 A 页面改为 `useRepository()`；
- local 模式空状态/下载入口/本机标记；
- remote 模式保持现有页面行为；
- 资料页显示本地 TXT/MD 文档和文件状态；
- 题库/KP 的本地编辑/删除；
- 测试页面 local/remote 双路径、离线、错误。

**门禁：** flag off 时现有 59 个前端测试通过；flag on 时离线流程通过。

### 8A-4 Android 真机与验收（1–2 天）

- Debug 构建/安装；
- v3→v4 迁移；
- 下载合成课程；
- 飞行模式浏览/编辑/重启；
- 原有 FastAPI 页面回归；
- 文档与 APK 哈希。

---

## 六、测试计划

### 自动化

- v3→v4 成功、重复、失败回滚、迁移前快照；
- `server_id` 唯一、FK、级联、事务；
- 本地 CRUD（课程/章节/KP/题目/资料元数据）；
- 章节树移动/删除保护；
- 资料删除清 chunks/文件（受控路径）；
- 下载幂等、保留 pending 行、失败回滚；
- local/remote Repository 契约；
- flag on/off 页面路径；
- 离线/网络恢复；
- 浏览器无 SQLite/Filesystem 的能力降级；
- 现有 117 后端 + 59 前端回归。

### Android 真机

1. v3→v4 迁移，7C 文件/任务保留；
2. 下载合成课程；
3. 飞行模式打开课程/章节/资料/KP/题库；
4. 本地新建/编辑/删除；
5. 进程重启后数据/进度/状态恢复；
6. 关闭开关，FastAPI 页面正常；
7. 本地文件仍可读，SHA 一致；
8. 不出现重复上传或假成功。

> 所有测试用合成数据/专用测试课程；不导入真实资料。

---

## 七、安全与边界

- 不修改真实服务端数据库/Alembic；
- 不移动 `v1.0.0-rc.1`；
- 不改签名/包名/HTTPS；
- 不开放公网/Tunnel/端口映射；
- 不把 AI Key 放客户端；
- 文件只写私有目录；
- v4 只增不删；
- 迁移前快照；
- 默认 FastAPI；开关可回滚；
- 本地删除不自动影响服务器。

### 仍需决策

1. **`allowBackup=true`**：8A 是否改为 `false` 或增加 backup rules？
   - 建议：8A 先不改，但把“本地数据可能被云备份”写入 UI/文档；在真实用户数据前再决策。
2. **SQLCipher/Keystore**：8A 是否引入？
   - 建议：8A 不引入密钥迁移；先保证备份/迁移安全，加密单独评估。
3. **8A 是否包含本地编辑已下载内容**：
   - 建议：允许，标记 `pending_*`，不自动上传；刷新不覆盖。
4. **下载粒度**：
   - 建议：单课程下载；不做“全库下载”。
5. **v4 是否一次补齐 B/C 字段**：
   - 建议：是；本次一次迁移，8A 只使用 A 字段，8B/8C 复用，减少二次迁移风险。

---

## 八、验收标准

- [ ] 8A 代码只在确认后修改；基线 `1ac8867` 可回退。
- [ ] flag 关闭：现有 FastAPI 路径、59 前端/117 后端测试不回归。
- [ ] flag 开启：无 API 也可浏览已下载课程/章节/资料元数据/KP/题库。
- [ ] 本地 CRUD 有事务、外键、唯一约束、删除保护。
- [ ] v3→v4 保留 7C 文件/任务/合成数据；失败回滚。
- [ ] 下载不覆盖本地 pending 行；失败不破坏旧快照。
- [ ] 飞行模式 + 进程重启可用。
- [ ] 不自动上传、不标记假成功。
- [ ] 真实库、标签、签名、HTTPS 未变。
- [ ] Android Debug 构建、真机证据、APK SHA-256、文档。

---

## 九、建议确认项

请确认以下决定后再开始 8A-0：

1. 8A 范围 = A（课程/章节/资料元数据/KP/题库）+ v4 结构；B/C/D 后续。
2. 允许本地编辑已下载内容，但 8A 不推送服务器。
3. 下载按单课程；服务器删除不在 8A 自动传播。
4. v4 一次补齐 B/C 字段，8A 不实现 B/C 行为。
5. `allowBackup` 暂不改，只记录风险；SQLCipher 不在 8A 引入。
6. 是否同意“迁移前 JSON 快照”作为 8A 的恢复保护（完整用户备份/恢复 UI 后续）。

确认后从 **8A-0 预检与保护** 开始；在确认前不修改业务代码。
