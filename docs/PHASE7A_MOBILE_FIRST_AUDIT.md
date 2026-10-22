# 阶段 7A：移动端优先架构审计

日期：2026-10-22
仓库：`C:\Users\bzlciallo\Documents\Codex\2026-10-19\biolearn-ai-git-python-node-js`
审计基线：`df94cf8`（阶段 6M 修复）
审计方式：只读代码、依赖、数据库结构检查；未修改真实库、标签、签名或网络配置。

---

## 一、基线核对

| 项 | 实际值 |
| --- | --- |
| `git HEAD` | `df94cf8` |
| 工作区 | 干净 |
| `v1.0.0-rc.1` | 仍指向 `930f279` |
| 前端框架 | React 19 + TypeScript 5.9 + Vite 8 + React Router 7 + 手写 CSS |
| Android | Capacitor 7.6.9，compile/target 35，minSdk 23，JDK 21 |
| 后端 | FastAPI + SQLAlchemy 2 + Alembic + SQLite |
| 真实库 | `0009_question_bank` |
| 真实数据 | 10 学科 / 6 章节 / 2 资料 / 117 分块 / 78 知识点 / 7 题 / 3 练习 / 6 作答 |
| 后端测试 | **117 passed** |
| 前端测试 | **35 passed / 14 files** |
| TypeScript / ESLint / 构建 | 通过 |
| Android Debug | 最近一次 `BUILD SUCCESSFUL`（阶段 6M） |

本次阶段只新增文档，不改业务代码、数据库、签名与标签。

---

## 二、当前移动端连接与存储

### 2.1 API Base

`frontend/src/lib/api/connection.ts`：

1. 运行时 `localStorage: biolearn.api_base_url`；
2. 构建时 `VITE_DEFAULT_API_BASE_URL`（Android 专用）；
3. 浏览器同源 `location.origin + /api/v1`；
4. Android 未配置时返回空字符串，界面提示“尚未连接服务器”，**不回退 localhost**。

`frontend/src/lib/api/client.ts`：

- `fetch` 请求，默认超时 8 秒，上传 120 秒；
- 认证头 `X-BioLearn-Token`（兼容 Bearer）；
- 401/403/网络错误有中文提示。

### 2.2 Android 网络

- `android/app/src/main/AndroidManifest.xml` 只有 `INTERNET` 权限；
- Debug Manifest 允许明文 HTTP（仅开发）；
- Release 主 Manifest 无 `usesCleartextTraffic`，Android 9+ 默认禁止明文；
- `capacitor.config.ts`：`androidScheme=https`、`allowMixedContent=true`（仅局域网 HTTP 调试有意义）；
- `MainActivity.java` 只处理 WebView 返回历史。

### 2.3 已有本地持久化

| 方案 | 现状 | 存什么 |
| --- | --- | --- |
| `localStorage` | 已有 | API Base、旧版共享口令（token 还写 sessionStorage） |
| `sessionStorage` | 已有 | 登录 token |
| IndexedDB | 已有（6M） | 课程列表、课程知识库只读快照 |
| localStorage 兜底 | 已有（6M） | 同上（IndexedDB 不可用时） |
| Capacitor SQLite | **未安装** | — |
| Capacitor Filesystem | **未安装** | — |
| Preferences/Keystore | **未安装** | — |
| Android Room/SQLite | **未实现** | — |

`frontend/package.json` 的 Capacitor 依赖只有 `@capacitor/core`、`@capacitor/android`；
`capacitor.build.gradle` 没有任何第三方 Capacitor 插件。

### 2.4 文件选择与文件生命周期

- 使用 WebView `<input type="file">`，由 Android 系统文件选择器返回临时 URI；
- WebView 把它读成 JS `File`，当前只在内存/表单中存在；
- `DocumentUploadCard` 直接 `FormData` → `POST /documents`；
- 没有把文件复制到 App 私有目录，没有本地 `local_path`，没有持久文件队列；
- 上传成功/失败后选择状态只在组件内存中；重新打开页面不能恢复“待上传文件”；
- Android 没有申请存储权限（SAF 不需要），这是正确方向。

---

## 三、页面/API 依赖清单

| 页面 | 主要 API | 是否必须后端 |
| --- | --- | --- |
| `HomePage` | `GET /health` | 是（连接状态） |
| `SubjectsPage` | `GET/POST /subjects`，编辑/删除 | 是 |
| `SubjectDetailPage` | subject/chapter CRUD、move | 是 |
| `SubjectKnowledgePage` | subject、chapters、documents、knowledge-points、questions | 读可缓存；写/新数据需后端 |
| `DocumentsPage` | `GET/POST /documents`、`retry-parse`、`extract`、`delete` | 是 |
| `ImportPage` | `/imports`、`/imports/preferences`、`/imports/{id}`、`confirm`、`retry` | 是 |
| `KnowledgeReviewPage` | document knowledge、知识点 CRUD/审核/合并、`/knowledge-jobs`、`/ai/status` | 是（AI 仍需外部模型） |
| `QuestionsPage` | questions CRUD/审核、`/questions/generate`、generation jobs | 是（AI 仍需外部模型） |
| `PracticePage` | start/list/submit/result、wrong-questions、manual grade | 是 |
| `AISettingsPage` | `/ai/status`、`/ai/config`、`/ai/test` | 是（Key 只在后端） |
| `AdminPage` | `/admin/users|invitations|grants` | 是 |
| `LoginPage` / `JoinPage` | `/auth/login`、`/auth/invitations/accept` | 是 |
| `ConnectionSettingsPage` | `/auth`、`/health` | 是 |
| `AboutPage` | 无 | 否 |

### 3.1 关键发现

1. **所有业务写操作仍必须 FastAPI**；手机没有本地写路径。
2. **课程知识库只读缓存**可用于离线浏览，但不是完整业务数据层。
3. **上传接口只接收文件，不接收本地文件路径/客户端 ID**；服务器生成 document/job ID。
4. **AI Key、数据库、上传目录只在后端**；APK 中没有任何服务端秘密。
5. **电脑端和手机端是同一后端的两个客户端**，不是双向同步的两份数据库。

---

## 四、数据模型与关联

### 4.1 真实 SQLite 表

`subjects`、`chapters`、`documents`、`document_chunks`、
`knowledge_extraction_jobs`、`knowledge_points`、`question_generation_jobs`、
`questions`、`question_knowledge_points`、`practice_sessions`、`practice_answers`、
`import_jobs`、`import_preferences`、`users`、`auth_sessions`、`invitations`、
`subject_grants`。

### 4.2 关联

```
subjects 1─N chapters
subjects 1─N documents
subjects 1─N knowledge_points
subjects 1─N questions
chapters 1─N chapters (parent_id)
documents 1─N document_chunks
documents 1─N knowledge_points
knowledge_points 1─N knowledge_points (parent_id)
questions N─N knowledge_points
subjects 1─N practice_sessions
practice_sessions 1─N practice_answers
practice_answers N─1 questions (可空，保存 question_snapshot)
```

### 4.3 ID/时间/删除

- 所有业务主键为 UUID 字符串（`String(36)`，服务端生成，`new_id()`）；
- 大多数表有 `created_at`/`updated_at`（SQLite 存 UTC，读取时可能是 naive datetime）；
- 知识点/题目有 `reviewed_at`、`published_at`；
- **没有 `deleted_at`/tombstone**：删除是硬删除；
- **没有 `version`/`change_seq`**：无法做增量同步游标；
- **没有 `client_id`/幂等键**：手机断网重试创建可能产生重复（现有文档上传有 SHA 去重，但不是通用幂等）；
- 阶段 6B 增加了 `subjects.owner_id`、`practice_sessions.user_id`、任务 `created_by`；
  这些是本地多用户隔离必须继承的字段。

### 4.4 数据迁移现状

- Alembic 当前真实库为 `0009`；`0010_users_auth` 已在代码中，但真实库未迁移；
- 0010 在本轮前修复了 SQLite 批量重建 subjects 导致章节级联删除的风险，改为 `ADD COLUMN`；
- 本地手机数据库不应直接复制服务端 Alembic，而应有独立的移动端 schema/版本。

---

## 五、解析器真实能力

`backend/app/services/parsing.py`：

| 格式 | 支持 | 实现/限制 |
| --- | --- | --- |
| `.pdf` | ✅ | pypdf 文本层；扫描 PDF 无 OCR，会标记 `needs_ocr` |
| `.docx` | ✅ | python-docx；段落/标题/表格 |
| `.pptx` | ✅ | python-pptx；幻灯片/标题/表格 |
| `.txt` | ✅ | UTF-8/GB18030/UTF-16 等文本解码 |
| `.md` / `.markdown` | ✅ | Markdown 标题/文本 |
| `.ppt` | ❌ | 明确提示另存 `.pptx` |
| 图片/扫描件 OCR | ❌ | 仅提示，不伪造文本 |
| 最大文件 | 25 MB | 前后端均有校验 |

解析输出：`ParsedDocument`（标题、blocks、页/幻灯片数、warnings、needs_ocr）→
chunking → 自动章节建议 / 归档 → AI 提取。

**这些实现全部在 Python 后端**，Android 端没有等价解析器。

---

## 六、AI 功能与可本地化程度

| 功能 | 当前实现 | 可本地规则化 | 必须模型 |
| --- | --- | --- | --- |
| 文件格式校验/文本解码 | Python 规则 | 部分可移植（TXT/MD 容易） | 否 |
| PDF/DOCX/PPTX 文本提取 | pypdf/python-docx/python-pptx | 可移植但成本高、质量差异大 | 否 |
| 标题/页码/分块 | 规则 | ✅ 可移植 | 否 |
| 结构识别/自动建章 | 规则 + AI 结构分析 | 部分规则；复杂版式需模型 | 部分 |
| 知识点提取/合并/去重 | LLM 分析→逐块提取→合并 | 只能做标题/术语/显式列表等低质量候选 | **是** |
| 知识点审核 | 人工规则 | ✅ 本地可做 | 否 |
| 题目生成 | LLM，结构化校验 | 可做简单填空/判断，质量和答案正确性风险高 | **是（推荐）** |
| 选择题自动判分 | 规则 | ✅ 可完全本地 | 否 |
| 简答题评分 | 人工/未来 AI | 规则不可靠 | 模型或人工 |

结论：**本地可做“解析、分块、简单规则候选、选择/判断题判分”；高质量知识点提取、合并、出题仍需模型服务。**

---

## 七、现有同步机制及限制

- 手机与电脑共用同一 FastAPI + SQLite；没有手机 SQLite；
- 在线写立即落库，另一端刷新可见；
- 没有离线写队列、增量游标、tombstone、冲突合并；
- 阶段 6M 的 IndexedDB 缓存只读，且登录/退出清空；
- 手机上传文件只存在后端 `UPLOAD_DIR`，手机不保留副本；
- 因此“电脑关机 + 手机导入/真实分析”目前**不可能**；
- 若要电脑关机仍可用，必须有本地数据库 + 本地文件/解析，或独立远程后端。

---

## 八、风险清单

| 风险 | 等级 | 说明 |
| --- | --- | --- |
| 双份真相（本地 SQLite + 服务端 SQLite） | 高 | 无同步协议会分叉 |
| 通用写操作无幂等键 | 高 | 断网重试创建可能重复 |
| 服务端硬删除无 tombstone | 高 | 本地无法知道删除 |
| 本地文件 URI 失效 | 高 | SAF 临时 URI 不能长期保存 |
| 本地 DB 安全 | 高 | 未加密、allowBackup、token 未 Keystore |
| SQLite 插件与 Capacitor 7 版本兼容 | 中 | 需固定版本并在真机验证 |
| 解析器移植质量差异 | 中 | PDF/Office 在端侧不等于后端结果 |
| 本地 AI 质量/性能 | 高 | 设备内存、热、模型质量 |
| 真实数据导入 | 高 | 不可在未批准时迁移 |
| 现有 API 兼容 | 中 | 同步接口必须新增、不能破坏旧客户端 |

---

## 九、审计结论

1. 当前移动端是“**远程 API 客户端 + 只读缓存**”，不是本地优先应用。
2. 课程/知识库导航和文件选择已完成，但文件没有落到手机私有存储，业务写操作全部依赖后端。
3. 已具备做本地 SQLite 的 UI/路由基础，但**没有任何 Capacitor SQLite/Filesystem 插件**。
4. 最佳增量路线是：**Capacitor + 本地 SQLite + 私有文件存储 + Repository 抽象 + 可选 FastAPI 同步**；
   不建议本阶段直接改用全原生重写。
5. 解析/AI 必须分层：TXT/MD/基础规则可先本地；PDF/Office 高质量解析和 AI 仍走服务端/未来端侧模型。
6. 本阶段只做审计/设计；真实库、标签、签名、HTTPS 策略均不改。
