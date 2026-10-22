# 阶段 7C：Android 私有文件存储与 TXT/MD 离线处理

日期：2026-10-22
代码提交：`77ebb3b`
基线：`74796ba`（7B 文档）
状态：**私有文件复制、Schema v3、TXT/MD 本地解析、待上传队列基础已完成；Android Debug 真机验证通过。未实现自动上传或双向同步。**

---

## 一、实施前核对

| 项 | 实际值 |
| --- | --- |
| 分支 | `main` |
| 实施前 HEAD | `74796ba` |
| 7C 代码提交 | `77ebb3b` |
| `v1.0.0-rc.1` | 仍指向 `930f279` |
| 真实库 | `0009_question_bank` |
| 真实库修改 | 无 |
| 7B 本地库 | 已有 v2 合成数据，升级后保留 |
| 默认开关 | 关闭（FastAPI） |

---

## 二、Filesystem 插件

### 2.1 精确版本

| 组件 | 版本 |
| --- | --- |
| `@capacitor/core` / `@capacitor/android` | `7.6.9` |
| `@capacitor-community/sqlite` | `7.0.3`（保持不变） |
| `@capacitor/filesystem` | **`7.1.9`（精确锁定）** |

安装：

```powershell
cd frontend
pnpm add @capacitor/filesystem@7.1.9 --save-exact
pnpm exec cap sync android
```

### 2.2 兼容性依据

- `@capacitor/filesystem@7.1.9` 的 peerDependency：`@capacitor/core >=7.0.0`；
- 项目 Capacitor 7.6.9，符合；
- 7.1.9 是 7.x 系列当前版本，不是 8.x；
- 使用 `Directory.Data`（App 私有数据目录）；
- Android Debug 构建与真机文件选择/读取通过；
- 没有使用 `Directory.External`/公共媒体目录。

Android 构建仍使用 `minSdk 23`、`compileSdk/targetSdk 35`、JDK 21。

### 2.3 APK 体积

7C 最终 Debug APK：**27,749,064 字节**；主要体积仍来自 SQLCipher 原生库，Filesystem 增量很小。

---

## 三、文件存储实现

文件服务：`frontend/src/lib/local/fileStore.ts`

### 3.1 私有路径

- 根目录：`biolearn/files/`，相对 `Directory.Data`；
- 实际 Android 路径：`/data/data/ai.biolearn.app/files/biolearn/files/`；
- 文件名：UUID + 原扩展名（`.txt`/`.md`）；
- 数据库只保存相对路径，例如 `biolearn/files/<uuid>.md`；
- 禁止绝对路径、`..`、任意拼接；`validateLocalRelativePath()` 统一校验。

### 3.2 复制流程

1. Android 系统文件选择器返回临时 `File`（SAF URI 只在本次选择内使用）；
2. 校验扩展名：仅 `.txt/.md/.markdown`；
3. 校验大小：空文件拒绝，超过 **5 MiB** 拒绝；
4. `file.arrayBuffer()` 读取一次，计算 SHA-256；
5. 写入 `biolearn/files/<uuid>.<ext>.part`；
6. `Filesystem.stat` 校验大小；
7. `Filesystem.rename` 原子重命名为最终文件；
8. 返回文件 ID、相对路径、原文件名、MIME、大小、SHA-256；
9. 数据库事务写入文档、文件记录、解析任务、上传任务。

### 3.3 崩溃/中断

- 只有 `.part` 写入完成且 `stat` 大小一致才 rename；
- rename 前中断不会出现“完整路径”的残缺文件；
- `.part` 不会写入数据库；
- 页面提供“清理 .part 临时文件”，只删除该私有根目录下的 `.part`；
- 若 rename 后、数据库事务前进程被杀，可能出现未被引用的完整文件；
  它不会被标记为完成，7D 需补孤文件清理；
- 复制失败会删除 `.part`/最终文件，不写记录。

### 3.4 限制

- 5 MiB 上限是内存/稳定性保护；更大的 TXT/MD 或 PDF/DOCX/PPTX 继续走 FastAPI；
- 当前一次只处理一个文件；
- 没有后台复制/断点续传；
- 文件不暴露到公共媒体库。

---

## 四、Schema v3

`frontend/src/lib/local/schema.ts`：

- `LOCAL_DB_SCHEMA_VERSION = 3`
- `LOCAL_MIGRATIONS` 增加 v3
- 保留 `schema_migrations` 与 `PRAGMA user_version`
- v3 在事务内执行；失败回滚

### 4.1 新表

```sql
local_files (
  id, document_id UNIQUE, relative_path UNIQUE, original_filename,
  mime_type, size_bytes, sha256, status, error, created_at
)

local_parse_jobs (
  id, document_id, status, error, created_at, updated_at, finished_at
)

local_upload_jobs (
  id, document_id, file_id, status, attempts, last_error,
  created_at, updated_at, next_retry_at, remote_document_id,
  UNIQUE(document_id, file_id)
)
```

### 4.2 状态约束

- `local_files.status`：
  `selected | copying | stored | failed | deleted`
- `local_parse_jobs.status`：
  `queued | parsing | parsed | failed`
- `local_upload_jobs.status`：
  `queued | uploading | uploaded | failed | needs_verification`
- SQL `CHECK` 约束拒绝非法状态；
- `local_upload_jobs(document_id, file_id)` 唯一，避免同一文件重复任务；
- 外键：文件/任务 → `local_documents`；上传任务 → `local_files`；
- 索引：`local_files(sha256)`、`local_files(status)`、`local_parse_jobs(document_id)`、`local_upload_jobs(status)`。

### 4.3 状态机

`frontend/src/lib/local/stateMachines.ts`：

| 状态机 | 合法转换 |
| --- | --- |
| 文件 | `selected → copying → stored`；copying/selected → failed；stored/failed → deleted |
| 解析 | `queued → parsing → parsed`；queued/parsing → failed；failed → queued |
| 上传 | `queued → uploading`；uploading → uploaded/failed/needs_verification；failed → queued；needs_verification → queued/uploaded |

`uploaded` 不允许回退为 `queued`；`requeueUploadJob()` 使用状态机校验。

### 4.4 实际迁移

真机上 7B 已有 v2 数据库（schema 2、7B 合成数据）；安装 7C 后开启本地库：

- 页面显示 schema **3**；
- 外键仍为 ON；
- 原 7B 合成课程/章节/文档/知识点/题目/练习记录保留；
- 新表 files/parse_jobs/upload_jobs 计数为 0，导入后各为 1。

这验证了真实 v2→v3 迁移，不是新建空库。

---

## 五、TXT/MD 本地解析

文件：`frontend/src/lib/local/textParser.ts`

### 5.1 编码与换行

- 支持 UTF-8、UTF-8 BOM；
- UTF-8 失败时回退 GB18030（中文旧文本）；
- 统一 CRLF/CR → LF；
- 空文件/纯空白拒绝；
- 超过 1,000,000 字符拒绝；
- 编码无法识别时报明确错误，不静默丢内容。

### 5.2 Markdown

- 识别 `#` 到 `######` 标题；
- 构建 `headingPath`（如“蛋白质 > 一级结构”）；
- 标题行保留在 chunk 内容中；
- 非 Markdown 文本按普通段落处理；
- 标题用首个 H1，否则用文件名。

### 5.3 分段

- 最大 chunk 长度 2,000 字符；
- 段落/空行边界优先；
- 超长单行硬切；
- chunk 记录 `charStart/charEnd`、`locationLabel`、`headingLevel`；
- chunk ID：
  `chunk-<documentId>-<index>-<content SHA-256 前 12 位>`；
- 相同文档、相同内容重复解析得到相同 ID；
- 结果只写 `local_documents`/`local_chunks`，**不写知识点、不生成题目、不调用 AI**。

### 5.4 UI 区分

页面明确显示：

> “本地文本解析完成（N 个片段）。这不是 AI 知识点提取；未写入正式知识库、未自动批准知识点。”

导入后仅显示本地文本/片段；没有“AI 提取完成”字样。

---

## 六、待上传队列

`local_upload_jobs` 在文件保存后创建：

- 稳定任务 ID：`upload-<documentId>`；
- 初始 `queued`，`attempts=0`；
- 应用重启后仍存在；
- 页面展示状态、尝试次数、最近错误；
- 仅允许 `failed/needs_verification` 重新排队（UI 按钮明确“不执行上传”）；
- **7C 不调用 FastAPI 上传接口**，不自动上传；
- `uploaded` 只能由未来服务端明确成功响应后设置，7C 没有该路径。

### 为什么不上传

现有 `POST /api/v1/documents`：

- 接收 `file/subject_id/chapter_id/name/force`；
- 无 `Idempotency-Key`，无 `client_id`；
- 不能安全区分“客户端超时但服务端已成功”和“真正失败”；
- 盲目重试可能创建重复文档；
- 本地合成课程也没有服务端 subject/chapter 映射。

因此 7C 只做客户端队列和接口边界设计，自动上传留待服务端幂等键完成后的阶段。

---

## 七、功能开关与兼容性

- 继续使用 `biolearn.mobile_local_db`；
- 构建默认 `VITE_MOBILE_LOCAL_DB=false`；
- 关闭时现有页面/上传继续 FastAPI；
- 文件功能只在 `enabled && Capacitor.isNativePlatform()` 时可用；
- 浏览器显示明确降级提示，不调用原生 SQLite/Filesystem；
- 关闭开关即关闭 DB，文件保留但 UI 不打开；不要求删除 DB；
- 没有新增独立开关，避免双重回滚复杂度。

---

## 八、安全与数据保护

| 项 | 实际 |
| --- | --- |
| 文件位置 | App 私有目录，非公共媒体 |
| 文件权限 | 真机 `-rw-------`（0600） |
| 数据库权限 | 0600 |
| 日志 | 不输出正文、token、Key、文件内容 |
| API Key | 未加入客户端 |
| 真实数据 | 未导入；只使用合成 TXT/MD |
| 原文件 | 不删除、不移动用户原文件 |
| `allowBackup` | **仍为 `true`**，未修改 |
| SQLCipher | 未启用；插件虽带 SQLCipher 库，但连接为 no-encryption |

### allowBackup 评估

`AndroidManifest.xml` 当前 `android:allowBackup="true"`，且未配置 `fullBackupContent` / `dataExtractionRules`。
这意味着 Android Auto Backup 可能把私有 DB 和 `files/biolearn/files` 纳入云备份（取决于系统/设备策略）。

7C **没有擅自修改**备份策略；风险记录如下：

- 对合成测试数据影响有限；
- 对真实学习资料/隐私有潜在泄露面；
- 7D 前必须决定：关闭备份、限定 backup rules，或对 DB/文件加密；
- 不能以“私有目录”等同于“已加密”。

### SQLCipher/Keystore

- 未引入密钥迁移或破坏性 DB 重建；
- 当前依赖 Android 文件权限（0600）；
- 后续若启用 SQLCipher，需要迁移方案、密钥托管、备份/恢复与忘记密钥处理；
- APK 已因 SQLCipher 原生库较大，加密不会显著再增体积，但密钥管理是主要成本。

---

## 九、测试

### 自动化

| 项 | 结果 |
| --- | --- |
| 后端 | **117 passed** |
| 前端 | **59 passed / 20 files** |
| TypeScript | 通过 |
| ESLint | 通过 |
| 生产构建 | 通过 |
| Android Debug | `BUILD SUCCESSFUL` |

新增覆盖：

- v2→v3 成功迁移、重复迁移、v3 失败回滚；
- 文件/解析/上传状态机；
- 外键、唯一约束、非法状态；
- 文件复制临时路径 + size 校验 + rename + SHA；
- 复制失败清理 `.part`；
- 超大/空/不支持类型/路径穿越；
- UTF-8 BOM、CRLF、Markdown 标题、GB18030、空文件、长文本分段、稳定 ID；
- 浏览器（非原生）能力降级；
- 关闭开关默认 remote 回归。

### 真机

设备 PA2553 / Android 16，Debug APK。

| 项 | 结果 |
| --- | --- |
| v2→v3 | ✅ schema 3，7B 数据保留 |
| 系统文件选择器 | ✅ 选择 `phase7c-note.md` |
| 复制到私有目录 | ✅ 109 B |
| SHA-256 | ✅ `155d63b6...351e9e74`，与实际文件一致 |
| 本地解析 | ✅ 1 片段，48 字符，utf-8 |
| 进程重启 | ✅ 文件/任务仍存在 |
| 飞行模式 | ✅ 重新读取并解析成功 |
| 私有文件权限 | ✅ `-rw-------`，109 B |
| 上传队列 | ✅ 1 条 `queued`，未标记 uploaded |
| 关闭开关 | ✅ 学科页仍走 FastAPI/远程缓存 |

证据：

- `outputs/phase7c-v3.png`
- `outputs/phase7c-parsed.png`
- `outputs/phase7c-restart.png`
- `outputs/phase7c-airplane-preview.png`
- `outputs/phase7c-jobs.png`
- `outputs/phase7c-fastapi-off.png`

---

## 十、已知限制

1. 自动上传、实际 HTTP 上传、幂等键、重试退避均未实现。
2. 本地合成课程没有服务端 subject/chapter 映射；真实上传需要映射。
3. 只支持单个 TXT/MD，上限 5 MiB；PDF/DOCX/PPTX 不在本阶段。
4. 无后台复制/断点续传；复制中断只保证不把 `.part` 当完整文件。
5. 无未引用完整文件的自动清理。
6. SQLCipher 未启用；`allowBackup=true` 风险未处理。
7. 浏览器无 Filesystem/SQLite 能力，只有明确降级提示。
8. 真实设备未做 GB18030/超大文本/磁盘写满测试（自动化部分覆盖）。
9. 本地文件/任务未纳入 7B 导出格式；7B 导出仍是文档元数据/知识点/题目等。
10. 7C 不改 Release 签名、包名、HTTPS、标签。

---

## 十一、进入 7D 前

1. 服务端增加 `Idempotency-Key`/`client_id` 与唯一约束；
2. 明确 local course/chapter → server subject/chapter 映射；
3. 实现上传任务状态到 `uploading → uploaded/needs_verification/failed`；
4. 超时保留 `needs_verification`，提供人工核验入口；
5. 处理重复文档/force 语义；
6. 未引用文件清理与备份策略；
7. SQLCipher/Keystore 决策；
8. 真机断网重试、进程被杀、磁盘写满测试；
9. 再考虑双向同步/删除同步/冲突解决（7E）。

---

## 十二、结论

7C 完成了 Android 私有文件复制、v3 数据模型、TXT/MD 离线解析和持久化待上传队列。
文件与记录在进程重启后仍有效，飞行模式下可重新读取解析；关闭开关后现有 FastAPI 流程不变。
但上传仍未执行，安全备份/加密和自动同步仍未解决，不能宣称“完整离线资料库”或“上传幂等已完成”。
