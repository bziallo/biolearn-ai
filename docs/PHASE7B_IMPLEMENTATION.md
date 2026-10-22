# 阶段 7B：只读本地 SQLite 基础层实现

日期：2026-10-22
代码提交：`600582c`
基线：`df94cf8`（阶段 6M 修复）
状态：**本地只读 SQLite 基础层已实现并在 Android Debug 真机验证；未接入现有业务数据源，未写真实库。**

---

## 一、实施前核对

| 项 | 实际值 |
| --- | --- |
| 分支 | `main` |
| 实施前 HEAD | `df94cf8` |
| 实施后代码提交 | `600582c` |
| `v1.0.0-rc.1` | 仍指向 `930f279` |
| 真实库 | `0009_question_bank` |
| 真实数据 | 10 学科 / 6 章节 / 2 资料 / 78 知识点 / 7 题 |
| 后端测试 | 117 passed |
| 前端测试 | 43 passed / 17 files |
| 7A 文档 | 已阅读；插件/SQLite 缺口与本次实际一致 |

---

## 二、SQLite 插件与兼容性

### 2.1 精确版本

| 组件 | 版本 |
| --- | --- |
| `@capacitor/core` | `7.6.9` |
| `@capacitor/android` | `7.6.9` |
| `@capacitor-community/sqlite` | **`7.0.3`（精确锁定）** |
| `@capacitor/cli` | `7.6.9` |
| 测试用 `sql.js` | `1.13.0`（devDependency） |
| 测试用 `@types/sql.js` | `1.4.11`（devDependency） |

安装命令（项目包管理器 pnpm 11.25.0）：

```powershell
cd frontend
pnpm add @capacitor-community/sqlite@7.0.3 --save-exact
pnpm add -D sql.js@1.13.0 @types/sql.js@1.4.11 --save-exact
pnpm exec cap sync android
```

`package.json` 使用精确版本（不带 `^`）；`pnpm-lock.yaml` 已更新。

### 2.2 兼容性核对

- 插件 7.0.3 的 peerDependency：`@capacitor/core >=7.0.0`；
- 项目 Capacitor 7.6.9，匹配；
- 项目 `minSdk=23`、`compileSdk=35`、`targetSdk=35`；
- Java/JVM 21（`capacitor.build.gradle`），插件 Android 构建通过；
- 插件以 **SQLCipher 原生库**打包，APK 从约 4.3 MB 增至 **27,748,584 字节**；
  这是原生依赖成本，不是 JS 包体。
- 未通过升级 Capacitor/全部依赖来规避冲突。

### 2.3 插件加载

`cap sync android` 输出：

```
Found 1 Capacitor plugin for android:
@capacitor-community/sqlite@7.0.3
```

`android/capacitor.settings.gradle` 与 `app/capacitor.build.gradle` 已生成对应模块。
Debug APK 真机页面显示插件版本 7.0.3。

---

## 三、本地数据库

### 3.1 位置与安全

- 数据库名：`biolearn_local`；
- Android 实际文件：`/data/data/ai.biolearn.app/databases/biolearn_localSQLite.db`；
- `run-as` 实测权限：`-rw-------`（0600），仅 App 用户可读写；
- 不使用共享存储，不把 DB 放进 `assets` 或 Git；
- 未启用 SQLCipher 加密（插件支持，但 7B 未开启）；
- 未写入 API Key、访问 token、签名材料或真实课程数据。

### 3.2 Schema v2

移动端 schema 独立于服务端 SQLAlchemy/Alembic，文件：
`frontend/src/lib/local/schema.ts`。

表：

- `schema_migrations`、`local_meta`；
- `local_courses`、`local_chapters`；
- `local_documents`、`local_chunks`；
- `local_knowledge_points`；
- `local_questions`、`local_question_knowledge_points`；
- `local_practice_sessions`、`local_practice_answers`。

关键字段：

- 本地 `id TEXT PRIMARY KEY`；
- `server_id TEXT UNIQUE`：服务端 ID 映射（7B 合成数据为空）；
- `sync_state`、`version`：为 7D/7E 预留；
- 所有关联使用外键；
- `updated_at`/`created_at` 为 ISO8601 文本；
- 文档元数据含 `sha256`、`size_bytes`、`status`、`chunk_count`、`knowledge_point_count`。

### 3.3 迁移机制

- `schema_migrations(version, applied_at)` 记录已应用版本；
- `PRAGMA user_version` 记录当前版本；
- v1：完整初始 schema；
- v2：`ALTER TABLE local_documents ADD COLUMN local_path TEXT`；
- 迁移使用 `execute(..., transaction=true)`，由插件在事务内执行；
- 迁移失败会抛 `LocalDatabaseError`，不会静默创建伪造数据；
- 新库和旧库都通过同一 `applyMigrations()`。

### 3.4 外键与异常恢复

- 打开连接后执行 `PRAGMA foreign_keys = ON`，并查询 `PRAGMA foreign_keys` 验证为 1；
- 迁移与 seed/import 使用显式事务；
- 关闭时 `db.close()` + `sqlite.closeConnection()`；
- 重新打开会重新检查 schema、schema_migrations、user_version；
- 迁移/seed 失败保留明确错误，页面显示错误，不回退到假数据。

### 3.5 一个真实插件坑

`@capacitor-community/sqlite` 的 `run()` 默认 `transaction=true`。
如果外层已经 `beginTransaction()`，逐条 `run()` 会再次 BEGIN，真机报：

```
Failed in beginTransactionAlready in transaction
```

修复：`CapacitorSqliteDriver.run()` 显式传 `transaction=false`，由 seed/import 自己管理事务。
另外在 BEGIN 前无条件尝试 `ROLLBACK` 并忽略“无事务”错误，清理异常中断留下的活动事务。
该问题先在真机复现，再修复并重新安装验证。

---

## 四、Repository 抽象

`frontend/src/lib/local/repositories.ts`：

```ts
LocalRepositoryBundle {
  mode: 'local' | 'remote'
  courses.list/get/chapters
  documents.listByCourse
  knowledgePoints.listByCourse/listByDocument
  questions.listByCourse
  practice.sessionsByCourse/answers
}
```

### 4.1 本地数据源

- `localBundle(database)`：从 SQLite 读取并映射为本地 DTO；
- 只读，不提供 create/update/delete；
- 用于 7B 诊断页和测试。

### 4.2 FastAPI 数据源

- `remoteBundle()`：复用现有 `listSubjects/getSubject/listSubjectChapters/
  listDocuments/listKnowledgePoints/listQuestions/listPracticeSessions/
  getPracticeResult`；
- 映射为同一组本地 DTO；
- 没有新增/替换任何服务端 API。

### 4.3 功能开关

- 默认：**关闭**（`mode='remote'`，所有现有页面仍走 FastAPI）；
- 构建时：`VITE_MOBILE_LOCAL_DB=false`（`.env.example`）；
- 运行时：`localStorage['biolearn.mobile_local_db']='1'|'0'`；
- `createRepositoryBundle()` 根据开关选 local/remote；
- 现有 `SubjectsPage`、`SubjectKnowledgePage`、`DocumentsPage`、`ImportPage` 等
  **没有**改为调用该 factory，所以 7B 不会自动改变生产数据源；
- 仅 `/settings/local-db` 诊断页使用 local bundle。

这样满足“开关选择数据源”的基础能力，同时保持旧 FastAPI 路径为默认行为。

---

## 五、合成数据与导入导出

### 5.1 合成数据

`frontend/src/lib/local/syntheticSeed.ts`：

- 1 门课程“本地合成课程：生物化学”；
- 2 个章节；
- 1 份文档元数据（无真实文件）；
- 2 个知识点；
- 2 道题；
- 1 个练习会话 + 1 条答题；
- 全部标记 `sync_state='local_only'`，不是真实数据；
- 显示在诊断页，不进入课程/题库页面。

### 5.2 导出格式

```json
{
  "format": "biolearn.localdb.export",
  "schemaVersion": 2,
  "exportedAt": "...",
  "syntheticOnly": true,
  "checksumAlgorithm": "SHA-256",
  "checksum": "...",
  "data": {
    "courses": [],
    "chapters": [],
    "documents": [],
    "knowledgePoints": [],
    "questions": [],
    "practiceSessions": [],
    "practiceAnswers": []
  }
}
```

- checksum 对规范化 JSON（键排序）做 SHA-256；
- 不包含文件二进制、AI Key、访问 token、服务端配置；
- `local_chunks` 目前不导出（7B 只需元数据/关联；7C 再设计文件与 chunk 导出）；
- 导入前校验 format/schema/checksum；
- 导入只接受 `syntheticOnly=true`；真实导出/合并需要后续阶段；
- 导入在事务内清空并重建本地业务表，失败回滚。

---

## 六、功能开关与回滚

### 默认

- 关闭；业务继续 FastAPI；
- 启动不会自动创建/打开本地 DB；
- 只有进入诊断页并点击“开启”才打开。

### 开启

- 写入 `biolearn.mobile_local_db=1`；
- 打开私有 SQLite；
- 诊断页可初始化合成数据、查询、导出摘要、关闭/重开、飞行模式查询。

### 关闭

- 写入 `biolearn.mobile_local_db=0`；
- `closeLocalDatabase()` 关闭连接；
- 页面清空状态；
- 现有业务页面继续 FastAPI，无强制本地依赖。

### 回滚

1. 在诊断页关闭开关；
2. 如需完全卸载：回退代码/移除插件后重新构建；
3. **不要通过删除本地数据库完成常规回滚**；测试数据只在隔离测试/私有合成库中清理；
4. 真实服务端 SQLite 不参与回滚，始终不受 7B 影响。

---

## 七、测试

### 自动化

| 项 | 结果 |
| --- | --- |
| 后端完整 | **117 passed** |
| 前端完整 | **43 passed / 17 files** |
| TypeScript | 通过 |
| ESLint | 通过 |
| 生产构建 | 通过 |
| Android Debug | `BUILD SUCCESSFUL` |

新增前端测试：

- schema v2、`PRAGMA foreign_keys=1`、合成数据关联；
- 外键约束拒绝无效章节；
- v1→v2 迁移保留课程；
- 导出 SHA-256、导入新库、篡改 checksum 拒绝；
- 关闭后用 SQLite bytes 重新打开，记录仍在；
- 默认 Repository 为 remote（mock FastAPI），映射正确；
- 功能开关默认/运行时切换。

测试驱动：`sql.js`（仅 devDependency）在隔离内存库执行同一 SQL schema；
生产构建不包含 `sql.js` 运行时依赖。

### 真机

设备：PA2553 / Android 16，Debug APK。

| 项 | 结果 |
| --- | --- |
| 安装 APK | Success |
| 插件加载 | 页面显示 `@capacitor-community/sqlite 7.0.3` |
| schema | 2 |
| 外键 | ON |
| 首次开启 | 成功，初始 counts 0 |
| 写入合成数据 | 成功：courses 1 / chapters 2 / documents 1 / knowledge_points 2 / questions 2 / practice_sessions 1 / practice_answers 1 |
| 查询 | 显示合成课程、2 个知识点 |
| 导出 | checksum `891506d533cf83790d4111fe6758dc2177df30b96efc5c1aa56844763c4a0ae9`，schema 2，syntheticOnly=true |
| 关闭并重新打开 | 成功，记录仍可查询 |
| 进程重启 | 成功，counts 仍为 1/2/1/2/2/1/1 |
| 飞行模式 | 成功，仍可查询本地 counts |
| 关闭开关 | 成功，页面回到“关”，业务恢复 FastAPI |
| 私有 DB | `databases/biolearn_localSQLite.db`，0600 |
| 现有业务页面 | 仍走 FastAPI；本地开关开启时学科页仍显示远程缓存，不是合成课程 |

证据截图：

- `outputs/phase7b-enabled.png`
- `outputs/phase7b-export2.png`
- `outputs/phase7b-process-restart.png`
- `outputs/phase7b-airplane.png`
- `outputs/phase7b-disabled.png`

---

## 八、当前限制

1. 只读；没有本地业务写入/同步/outbox。
2. 合成数据只存在本地；没有导入真实课程。
3. 浏览器/桌面无法使用原生 SQLite；诊断页只在 Android 原生可用。
4. 未启用 SQLCipher 加密；`allowBackup=true` 仍是未来要评估的风险。
5. 本地 DB 尚未按用户隔离；7B 只有合成数据。
6. 导出不含文件/chunks；7C 才处理私有文件。
7. 真实设备上未单独执行 v1→v2 原生迁移（自动化 sql.js 已覆盖）；
   未在真机执行导入（自动化覆盖）。
8. APK 因 SQLCipher 原生库增至 27.7 MB；后续需评估 ABI 拆分/体积。

---

## 九、进入 7C 的前置条件

1. 确认 `@capacitor/filesystem` 精确版本与 Capacitor 7 兼容；
2. 设计 SAF URI → App 私有文件目录的复制与清理；
3. 本地 schema v3：`local_path` 已预留，增加文件生命周期/解析任务字段；
4. 本地 TXT/MD 解析器与 fixtures；
5. PDF/DOCX/PPTX 仍走远程，不能宣称离线解析；
6. 给上传接口加幂等键/客户端 ID，避免断网重试重复；
7. 真机验证文件在进程重启后仍可读、飞行模式下只读、恢复网络后上传；
8. 评估 SQLCipher/Keystore 与 `allowBackup`。

---

## 十、结论

7B 建立了独立、私有、可迁移、可校验的本地 SQLite 基础层，并通过 Repository + 功能开关
保持 FastAPI 为默认数据源。当前只读、仅合成数据，不改变真实业务和真实库。
