# 阶段 7A：移动端优先目标架构

日期：2026-10-22
基线：`df94cf8`
状态：**架构设计；未实现本地数据库、未安装 SQLite/Filesystem 插件、未修改真实库。**

---

## 一、目标与原则

### 产品定位

- Android 是主使用平台；
- 电脑端保留为辅助管理与同步节点；
- 在线时使用 FastAPI + 外部 AI 的高质量能力；
- 离线时手机能读、能整理、能保存，不伪造服务端/AI 结果。

### 五条原则

1. **不重写现有 React 业务**：保留页面、路由、API 客户端和电脑端。
2. **本地优先，不等于全部本地 AI**：本地负责数据与文件，AI 仍可远程。
3. **单一写入路径**：每个实体在手机上只有一个 repository 入口，UI 不直接写 SQLite/API。
4. **可回滚**：本地库/同步用 feature flag，关闭后仍可使用旧远程模式。
5. **不破坏旧客户端**：FastAPI 只新增同步接口，不删除/改义现有接口。

---

## 二、方案比较

| 方案 | 必要性 | 引入成本 | Android 兼容性 | 数据迁移风险 | 离线能力 |
| --- | --- | --- | --- | --- | --- |
| **A. Capacitor + `@capacitor-community/sqlite`** | 高：复用 React/TypeScript，最小改动 | 中：新增原生插件、schema/migration、Repository 层 | 高：Capacitor 7 对应插件，API 23+ 可用；需真机验证 | 中：本地 schema 独立，通过导出/导入而非复制服务端库 | 读+写（本地库）；文件可本地 |
| B. Android 原生 Room + Kotlin | 中：性能/后台任务最好 | 高：重写数据层、双技术栈、UI 桥接 | 最高 | 高：两套模型/迁移 | 读+写+后台同步 |
| C. 现有 FastAPI 作为可选同步服务 | 高：保留电脑端与共享数据 | 中：新增 delta/tombstone/idempotency 接口 | 无 Android 风险 | 中：服务端需兼容旧 API | 仅在线 |
| D. 本地解析/规则提取 | 中：TXT/MD 可先做，PDF/Office 成本高 | 中→高：JS/原生解析器、测试语料 | PDF/Office 质量差异大 | 低（只产生草稿） | 部分离线 |
| E. 未来端侧 AI | 低（当前非必须） | 很高：模型、内存、热、评测 | 设备差异大 | 低 | 完全离线但质量/性能风险 |

### 推荐

**A + C + D（分阶段）**：

- **A** 先解决“手机有自己的数据库和文件”；
- **C** 保持 FastAPI 作为同步/共享/高质量计算服务；
- **D** 先做 TXT/MD 与规则型候选，不承诺 PDF/Office 端侧等价；
- **E** 只做技术评估，不进入 7B–7E 的交付承诺。

**B 暂不采用**：当前 UI/业务在 React 中，全原生 Room 需要重写 repository 和大量页面桥接；
只有在 SQLite 插件无法满足后台同步/大文件时，才用 Kotlin 补一个窄插件（WorkManager/Keystore/SAF）。

---

## 三、目标架构

```
┌──────────────────────────────────────────────┐
│ React UI（现有页面/路由）                     │
│  Subjects / Knowledge / Import / Review ...   │
└──────────────────────┬───────────────────────┘
                       │ Repository 接口
        ┌──────────────┴──────────────┐
        │                             │
┌───────▼────────┐          ┌─────────▼─────────┐
│ LocalStore      │          │ RemoteDataSource  │
│ SQLite (plugin) │          │ FastAPI (optional)│
│ Files (private) │          │ AI/parse jobs     │
└───────┬────────┘          └─────────┬─────────┘
        │                             │
        └──────────┬──────────────────┘
                   ▼
             SyncEngine
       outbox / cursor / conflict
```

### 3.1 权威边界

| 数据 | 手机本地 | 服务端 | 权威 |
| --- | --- | --- | --- |
| 手机新建的课程/章节/知识点草稿/练习 | SQLite | 可选同步副本 | **本地**（未同步前） |
| Owner 共享/授权的课程内容 | 只读镜像 | SQLite | **服务端**（拉取更新） |
| 手机上传的源文件 | App 私有文件 | 服务端 `uploads/` | 本地保留副本；服务端用于解析 |
| 解析/AI 任务结果 | 任务镜像 | 服务端 job | **服务端**（除非本地 TXT/MD 解析） |
| 电脑端编辑 | 拉取 | SQLite | **服务端**；本地按版本合并 |
| 练习记录 | SQLite | SQLite | **本地优先**，同步到服务端 |

### 3.2 写入路径

```
UI → Repository.save(entity)
   → LocalStore transaction (updated_at, sync_state=pending)
   → SyncOutbox.enqueue(operation)
   → UI 立即得到本地结果
   → SyncEngine 在线时推送/拉取
```

UI 不得直接 `fetch` 写 API；所有写操作走 Repository，保证本地/远程一致。

### 3.3 读取路径

```
Repository.get...
  → LocalStore (with cache metadata)
  → 若需要且在线，RemoteDataSource 拉取增量
  → 合并写入 LocalStore
```

---

## 四、技术选型细节

### 4.1 Capacitor SQLite

建议：`@capacitor-community/sqlite`（与 Capacitor 7 匹配的版本；实施时锁定精确版本）。

- 数据库位置：App 私有目录（`Directory.Data`/`databases`），不放在可被其他 App 读取的共享存储；
- 提供原生 SQLite、事务、migration、import/export；
- 浏览器无原生 SQLite，开发/测试可接 `jeep-sqlite` 或 mock repository；
- 不把服务端 Alembic 迁移直接搬过来；移动端 schema 独立版本；
- 可选 SQLCipher（单独评估；不能把密钥硬编码）。

### 4.2 Capacitor Filesystem

- 用户选择文件后，立即把 SAF URI 内容复制到 `Directory.Data/biolearn/files/<uuid>.<ext>`；
- 计算 SHA-256、大小、MIME，写 `documents.local_path`/`file_assets`；
- 上传使用本地副本，不依赖临时 URI；
- 删除资料时先删本地文件/记录，后同步 tombstone；
- 25 MB 上限与后端一致。

### 4.3 原生 Kotlin 的边界

仅在以下场景补窄插件：

- SAF 流式复制（WebView `File` 大文件内存问题）；
- WorkManager 后台同步；
- Android Keystore 保存 token/DB 密钥；
- 大文件/PDF 原生解析（如未来采用）。

不把全部业务搬到 Kotlin，避免双实现。

### 4.4 FastAPI 同步服务

保留现有资源 API（旧客户端兼容），新增：

- `GET /sync/changes?cursor=...`（服务端变更流）；
- `POST /sync/push`（批量 outbox，幂等键）；
- `GET /sync/export`（首次导入/恢复，带 schema/checksum）；
- tombstone/version/change_seq 字段（新迁移，需单独批准）；
- 旧接口行为不变。

---

## 五、移动端本地数据模型

> 这是目标 schema，不在 7A 执行。所有表使用 TEXT UUID、UTC ISO8601 时间、外键开启。

### 5.1 课程/章节

```sql
subjects(
  id TEXT PK,                 -- 本地 UUID
  server_id TEXT UNIQUE,      -- 服务端 id，未同步为空
  owner_user_id TEXT,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  color TEXT, icon TEXT, sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  deleted_at TEXT,
  sync_state TEXT NOT NULL,   -- synced|pending_create|pending_update|pending_delete|conflict
  base_server_updated_at TEXT,
  server_updated_at TEXT,
  local_updated_at TEXT,
  version INTEGER NOT NULL DEFAULT 0
);

chapters(
  id TEXT PK, server_id TEXT UNIQUE, subject_id TEXT NOT NULL,
  parent_id TEXT, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0,
  source_document_id TEXT, source_slide INTEGER,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
  sync_state TEXT NOT NULL, base_server_updated_at TEXT,
  server_updated_at TEXT, local_updated_at TEXT, version INTEGER NOT NULL DEFAULT 0
);
```

### 5.2 文件与解析

```sql
documents(
  id TEXT PK, server_id TEXT UNIQUE,
  subject_id TEXT NOT NULL, chapter_id TEXT,
  name TEXT NOT NULL, original_filename TEXT NOT NULL,
  local_path TEXT,            -- App 私有相对路径
  mime_type TEXT NOT NULL, extension TEXT NOT NULL,
  size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
  status TEXT NOT NULL,       -- uploaded|parsing|parsed|failed|needs_ocr
  parse_error TEXT, parse_warnings TEXT,
  page_count INTEGER, slide_count INTEGER,
  uploaded_at TEXT NOT NULL, parsed_at TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  deleted_at TEXT, sync_state TEXT NOT NULL,
  base_server_updated_at TEXT, server_updated_at TEXT,
  local_updated_at TEXT, version INTEGER NOT NULL DEFAULT 0
);

document_chunks(
  id TEXT PK, server_id TEXT UNIQUE, document_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL, heading_path TEXT, heading_level INTEGER,
  content TEXT NOT NULL, page_start INTEGER, page_end INTEGER,
  slide_number INTEGER, char_start INTEGER, char_end INTEGER,
  block_start INTEGER, block_end INTEGER, location_label TEXT NOT NULL,
  created_at TEXT NOT NULL
);

file_assets(
  id TEXT PK, document_id TEXT NOT NULL,
  local_path TEXT NOT NULL, sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL, mime_type TEXT NOT NULL,
  state TEXT NOT NULL,        -- present|missing|deleted
  created_at TEXT NOT NULL
);

parse_jobs(
  id TEXT PK, document_id TEXT NOT NULL,
  remote_job_id TEXT,         -- 服务端 job
  kind TEXT NOT NULL,         -- parse|extract
  status TEXT NOT NULL, stage TEXT NOT NULL DEFAULT '',
  progress INTEGER NOT NULL DEFAULT 0, error TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, finished_at TEXT
);
```

### 5.3 知识点/题目

```sql
knowledge_points(
  id TEXT PK, server_id TEXT UNIQUE,
  subject_id TEXT NOT NULL, chapter_id TEXT, document_id TEXT,
  parent_id TEXT, duplicate_of_id TEXT,
  name TEXT NOT NULL, point_type TEXT NOT NULL,
  explanation TEXT NOT NULL DEFAULT '',
  core_points TEXT NOT NULL DEFAULT '[]',  -- JSON
  conditions TEXT, source_quote TEXT, source_quote_verified INTEGER NOT NULL DEFAULT 0,
  source_page INTEGER, source_page_end INTEGER, source_slide INTEGER,
  source_locator TEXT, source_chunk_id TEXT,
  importance TEXT, prerequisites TEXT, external_id TEXT,
  confidence REAL, review_note TEXT, needs_review INTEGER NOT NULL DEFAULT 1,
  origin TEXT NOT NULL, review_status TEXT NOT NULL,
  reviewed_at TEXT, published_at TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
  sync_state TEXT NOT NULL, base_server_updated_at TEXT,
  server_updated_at TEXT, local_updated_at TEXT, version INTEGER NOT NULL DEFAULT 0
);

questions(
  id TEXT PK, server_id TEXT UNIQUE,
  subject_id TEXT NOT NULL, chapter_id TEXT, source_document_id TEXT,
  type TEXT NOT NULL, stem TEXT NOT NULL,
  options TEXT NOT NULL DEFAULT '[]', answer TEXT NOT NULL DEFAULT '{}',
  grading_rule TEXT NOT NULL DEFAULT '{}', explanation TEXT NOT NULL DEFAULT '',
  difficulty TEXT NOT NULL, status TEXT NOT NULL, origin TEXT NOT NULL,
  source_locator TEXT, ai_provider TEXT, ai_model TEXT,
  confidence REAL, review_note TEXT, duplicate_of_id TEXT,
  score REAL, reviewed_at TEXT, published_at TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
  sync_state TEXT NOT NULL, base_server_updated_at TEXT,
  server_updated_at TEXT, local_updated_at TEXT, version INTEGER NOT NULL DEFAULT 0
);

question_knowledge_points(
  question_id TEXT NOT NULL, knowledge_point_id TEXT NOT NULL,
  PRIMARY KEY(question_id, knowledge_point_id)
);
```

### 5.4 练习

```sql
practice_sessions(
  id TEXT PK, server_id TEXT UNIQUE, user_id TEXT NOT NULL,
  subject_id TEXT NOT NULL, chapter_id TEXT,
  status TEXT NOT NULL, filters TEXT NOT NULL DEFAULT '{}',
  question_ids TEXT NOT NULL DEFAULT '[]',
  total_questions INTEGER, answered_count INTEGER, correct_count INTEGER,
  pending_manual_count INTEGER, score REAL,
  started_at TEXT NOT NULL, finished_at TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  sync_state TEXT NOT NULL, base_server_updated_at TEXT,
  server_updated_at TEXT, local_updated_at TEXT, version INTEGER NOT NULL DEFAULT 0
);

practice_answers(
  id TEXT PK, server_id TEXT UNIQUE, session_id TEXT NOT NULL,
  question_id TEXT, question_snapshot TEXT NOT NULL,
  user_answer TEXT NOT NULL, is_correct INTEGER, score REAL,
  max_score REAL NOT NULL DEFAULT 1, feedback TEXT, graded_by TEXT NOT NULL,
  answered_at TEXT NOT NULL, created_at TEXT NOT NULL,
  sync_state TEXT NOT NULL, base_server_updated_at TEXT,
  server_updated_at TEXT, local_updated_at TEXT, version INTEGER NOT NULL DEFAULT 0
);
```

### 5.5 同步元数据

```sql
sync_outbox(
  id TEXT PK, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
  operation TEXT NOT NULL,    -- create|update|delete
  payload TEXT NOT NULL,      -- JSON snapshot/patch
  idempotency_key TEXT NOT NULL UNIQUE,
  base_updated_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_retry_at TEXT,
  status TEXT NOT NULL,       -- pending|sending|failed|done
  last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

sync_cursor(
  scope TEXT PK,              -- owner_user_id
  cursor TEXT NOT NULL,
  last_pulled_at TEXT
);

sync_conflicts(
  id TEXT PK, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
  local_version TEXT NOT NULL, server_version TEXT NOT NULL,
  reason TEXT NOT NULL, resolved_at TEXT, resolution TEXT
);
```

### 5.6 关键设计决定

1. **本地 UUID 与服务端 ID 分离**：本地外键始终使用本地 UUID；同步后回填 `server_id`。
2. **服务端创建必须支持客户端幂等**：7C 给创建接口加 `Idempotency-Key`（或 `client_id`），
   服务端保存键→资源映射；否则断网重试会重复。
3. **删除用 tombstone**：本地 `deleted_at` + outbox；服务端需要软删除/同步日志；
   不能直接硬删除后让其他设备猜。
4. **时间用于展示，版本用于并发**：`version`/`base_server_updated_at` 做乐观并发；
   不用手机时钟做 last-write-wins。
5. **文件不存 BLOB**：SQLite 只存元数据/相对路径；文件在 App 私有目录。
6. **用户隔离**：本地表带 `user_id`/owner scope；登录切换清空/切换 DB，禁止跨账号。

---

## 六、7B–7F 实施顺序

### 7B：本地 SQLite 基础（只读）

- 引入 SQLite 插件、DB 版本 1、Repository 接口；
- `MOBILE_LOCAL_DB=off|read` feature flag；
- 从 `GET /sync/export`（或现有 API 汇总）导入只读快照；
- UI 仍可走远程；本地只读用于离线课程/知识库；
- **不写服务端、不迁移真实库**。

验收：飞行模式下重启 App，课程/章节/知识点可读；无本地写入；导出/导入校验通过；回滚关闭 flag。

### 7C：本地文件与 TXT/MD 解析

- 引入 Filesystem；选择文件后复制到私有目录、SHA-256、`file_assets`；
- `.txt/.md` 本地解析/chunk；PDF/DOCX/PPTX 只入队远程解析；
- 本地 `parse_jobs` 镜像远程状态；
- 重复按 SHA-256 + subject/chapter 去重；
- 失败保留文件和错误，支持重试；不伪造成功。

验收：杀进程/重启后文件仍在；TXT/MD 真解析；PDF 明确“需后端”；重复不新增记录。

### 7D：本地写与 outbox

- 课程/章节/知识点草稿/练习本地可写；
- 每次写事务 + outbox + `sync_state`；
- 冲突基础：base/server 版本比较；冲突进入 `sync_conflicts`，不静默覆盖；
- 仍保留远程 API 作为可选路径。

验收：离线新建/编辑/练习；重启不丢；恢复网络后 outbox 幂等推送；冲突可见。

### 7E：双向同步与电脑端数据导入

- 服务端新增 `change_seq`/tombstone/幂等创建/`/sync/*`；
- SyncEngine：pull cursor、push outbox、重试、删除 tombstone；
- 首次从电脑导出/导入（不含密钥）；真实数据迁移需单独批准；
- 电脑端继续使用旧 API，不破坏。

验收：两台设备/电脑三端一致；删除不复活；重复推送不重复；旧客户端可用；回滚恢复远程模式。

### 7F：本地规则与端侧 AI 评估

- 本地规则：标题/显式列表/定义句候选、简单填空/判断、选择判分；
- 候选一律 `pending`，不自动通过；
- 评估端侧模型（可选，不承诺打包）；
- 性能/安全/Release  hardening。

验收：规则候选质量基线、无自动审核、设备内存/电量可接受；不达标则不发布端侧 AI。

---

## 七、测试设计

### 7B

- 本地 schema migration 1→2→1（隔离库）；
- Repository CRUD/外键/级联；
- 导入导出 checksum；
- 飞行模式读、无写；
- 真实库不变。

### 7C

- SAF URI→私有文件复制、进程重启、URI 失效；
- 25MB/格式/重复 SHA；
- TXT/MD 解析 fixtures；PDF/Office 明确远程；
- 上传失败/恢复/重试不重复。

### 7D

- 离线写、outbox 事务、重启恢复；
- 冲突矩阵（本地改/远端改/双方改/删除）；
- 时钟偏移不影响版本判断。

### 7E

- 幂等创建、分页 cursor、tombstone、断点续传；
- 多端并发、删除/恢复、冲突 UI；
- 旧 API 回归（现有 117 后端测试）。

### 7F

- 规则候选准确率/覆盖率人工评估；
- 无自动审核；
- 端侧模型内存/热/耗电；
- Release HTTPS/签名不变。

---

## 八、风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 本地/服务端双写不一致 | 单 Repository、outbox、冲突表 | 关闭本地写 flag，恢复远程 |
| 迁移损坏 | 本地 DB 先备份/导出；版本化 migration | 删除本地 DB 重建，服务端不动 |
| 文件 URI 失效 | 立即复制到私有目录 | 删除本地文件，重新选择 |
| 同步重复 | idempotency key + SHA 去重 | 清空 outbox，服务端已有记录保留 |
| 删除复活 | tombstone + 版本 | 暂停同步，人工合并 |
| 插件兼容 | 固定版本、真机矩阵 | 移除插件，恢复缓存模式 |
| 安全 | DB 私有目录/可选加密、token Keystore | 清库/退出登录 |

**硬性约束**：任何真实库迁移、服务端 schema 变更、批量数据导入都必须单独批准；
7A 不执行。

---

## 九、结论

推荐路线是 **Capacitor SQLite + Filesystem + Repository + 可选 FastAPI 同步**，
而不是全原生重写。7B 先做只读本地库，7C 做私有文件与 TXT/MD，
7D 做本地写/outbox，7E 才做双向同步，7F 再评估规则/端侧 AI。

这样可以在不破坏电脑端、旧 API、签名与 HTTPS 策略的前提下，逐步把手机从
“远程客户端 + 只读缓存”升级为“本地优先、可同步”的主平台。
