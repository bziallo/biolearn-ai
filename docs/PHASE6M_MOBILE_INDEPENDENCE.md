# 阶段 6M：手机端独立使用与课程知识库导航

日期：2026-10-22
基线：`f1b93c7`（阶段 6B 实现提交）
范围：现有 React + TypeScript + Vite、FastAPI、SQLite、Capacitor Android 的增量改造。
未修改数据库结构，未迁移真实库，未创建任何公网入口。

---

## 一、先给结论

### 已实现

- 课程卡片主区域/课程名称点击进入**课程知识库**（`/subjects/:subjectId/knowledge`），使用稳定课程 ID。
- 课程知识库加载并展示：课程名称、章节、课件及解析状态、知识点列表/详情、题目。
- 课程切换时先清空旧快照，再按新 `subjectId` 加载；客户端还会按 `subject_id` 二次过滤，避免串课。
- 离线只读缓存：课程列表与课程知识库快照可离线浏览，明确显示缓存时间和“离线缓存”。
- 全局离线提示：离线时明确告知上传/解析/AI 必须连接后端。
- 手机端课件导入：
  - Android 系统文件选择器（WebView `input[type=file]`）；
  - 支持格式按后端解析器实际能力：PDF、DOCX、PPTX、TXT、MD/Markdown；
  - 25 MB 前端预检；
  - 上传前显示文件名/大小/状态；失败保留文件并显示重试；
  - 重复文件仍使用后端 SHA-256 去重与 `duplicate_document` 提示，不产生重复记录；
  - 离线时不上传，不伪造成功。
- 课程知识库中小屏布局、触控尺寸、加载/空状态、失败重试。
- 原有电脑端 Agent/学科/资料/知识点/题目/练习逻辑未改。

### 未实现 / 必须明确

- **电脑关机或后端不可达时，手机不能完成真实课件解析或 AI 分析。**
  本机没有在手机上部署 PDF/Office 解析器或本地 AI 模型；这些能力仍在 FastAPI + 外部 AI。
- 没有离线写入队列与冲突合并。离线只读；上传必须在线。
- 没有独立远程后端、HTTPS 域名或 Tunnel；签名 Release 的远程场景仍未验收。
- 没有把 API Key、数据库口令、签名材料写入 APK。

---

## 二、架构审计

### 2.1 Android API Base 与网络

| 项 | 现状 |
| --- | --- |
| API 地址解析 | 运行时 `localStorage: biolearn.api_base_url` → 构建时 `VITE_DEFAULT_API_BASE_URL` → 浏览器同源；Android 不回退 localhost |
| Android 默认 | APK 未配置时显示“尚未连接服务器”，连接设置页填写电脑/远程地址 |
| 连接设置 | `/settings/connection`：地址、登录 token、保存并测试 |
| 传输 | `fetch`，默认 `X-BioLearn-Token`（也兼容 Bearer）；API 前缀 `/api/v1` |
| Debug | `android/app/src/debug/AndroidManifest.xml` 允许明文 HTTP，仅用于局域网 |
| Release | 主 Manifest 不包含 `usesCleartextTraffic`，只接受 HTTPS |
| 权限 | 仅 `INTERNET`；文件选择使用 Android SAF，不申请存储权限 |
| 文件选择 | Capacitor WebView 的 `<input type=file>`；系统文件选择器返回临时 URI，由 WebView 读取为 `File` |
| 秘密 | 无 AI Key、DB 口令、keystore、Service Token 写入 APK |

### 2.2 课件导入/分析调用链

```
Android 文件选择器
  → <input type=file> / ImportPage 拖拽区
  → POST /api/v1/imports (multipart: file, subject_id, mode, chapter_id, ...)
  → FastAPI 保存到 UPLOAD_DIR
  → BackgroundTasks: 解析 → 结构识别 → 归档
  → 可选 POST /knowledge-jobs（AI 提取）
  → GET /imports/{id} 轮询状态
  → GET /documents/{id}/knowledge-points 查看知识点
```

另有直接上传接口：

```
POST /api/v1/documents (multipart)
  → 资料记录 + 后台解析
  → GET /documents?subject_id=...
  → GET /documents/{id}/chunks
  → POST /documents/{id}/retry-parse
  → POST /documents/{id}/extract
```

AI 相关：

- 知识点提取：`POST /documents/{id}/extract` → `GET /knowledge-jobs/{id}`；
- 出题：`POST /questions/generate` → `GET /questions/generation-jobs/{id}`；
- 两者都依赖后端配置的 AI Provider（当前为 OpenAI-compatible，Key 只在服务端）。

### 2.3 功能分层

| 功能 | 本地 UI | FastAPI | 外部 AI | 说明 |
| --- | --- | --- | --- | --- |
| 课程列表/课程知识库浏览 | ✅ | ✅（在线） | ❌ | 离线用已缓存快照 |
| 章节树浏览 | ✅ | ✅ | ❌ | 缓存包含章节 |
| 课件选择/文件名/大小 | ✅ | ❌ | ❌ | 纯前端 |
| 课件上传 | ✅ | ✅ | ❌ | 必须后端在线 |
| 课件解析/分块 | ❌ | ✅ | ❌ | 后端 Python 解析器 |
| AI 知识点提取 | ❌ | ✅ | ✅ | 后端调用外部模型 |
| 知识点浏览/详情 | ✅ | ✅ | ❌ | 可缓存只读 |
| 知识点审核/编辑 | ✅ | ✅ | ❌ | 必须在线；保留原审核规则 |
| AI 出题 | ❌ | ✅ | ✅ | 后端调用外部模型 |
| 练习 | ✅ | ✅ | ❌ | 在线提交；现有规则不变 |

### 2.4 路由与页面

| 路由 | 页面 | 作用 |
| --- | --- | --- |
| `/subjects` | `SubjectsPage` | 课程/学科选择 |
| `/subjects/:subjectId` | `SubjectDetailPage` | 章节管理（原有） |
| `/subjects/:subjectId/knowledge` | `SubjectKnowledgePage` | **本次新增课程知识库** |
| `/subjects/:subjectId/documents` | `DocumentsPage` | 资料库、上传、解析状态、AI 建知识点 |
| `/documents/:documentId/review` | `KnowledgeReviewPage` | 知识点审核/详情/重试 |
| `/import` | `ImportPage` | 智能导入 |
| `/questions` | `QuestionsPage` | 题库 |
| `/practice` | `PracticePage` | 练习 |
| `/settings/connection` | `ConnectionSettingsPage` | API 地址/登录 |

课程选择页的课程名称与卡片主区域现在进入 `/subjects/:id/knowledge`；“章节管理”仍进入原 `/subjects/:id`，没有破坏原有编辑/删除。

### 2.5 数据关系（真实结构）

- “课程”在当前模型中就是 `subjects`；
- `subjects` 1→N `chapters`、`documents`、`knowledge_points`、`questions`；
- `documents` 归属 `subject_id` + 可选 `chapter_id`，解析为 `document_chunks`；
- `knowledge_points` 归属 `subject_id`/`document_id`/`chapter_id`，可树形 `parent_id`；
- `questions` 归属 `subject_id`/`chapter_id`，与 `knowledge_points` 多对多；
- `practice_sessions`/`practice_answers` 保存练习与作答；阶段 6B 后还按 `user_id` 隔离；
- 知识点/题目都有审核状态，只有 `approved` 题目可被练习抽取。

本次没有新增表、没有迁移，真实库仍为 `0009_question_bank`。

### 2.6 同步机制与限制

- 手机和电脑都是同一 FastAPI 后端的客户端；没有手机内 SQLite 副本。
- 在线写操作立即进入同一个 SQLite，另一端重新请求即可见；这是现有“同步”的全部含义。
- 没有离线写队列、冲突合并、增量同步或后台同步协议。
- 本次新增的离线缓存只存**只读快照**（课程/章节/课件元数据/知识点/题目），不存上传文件、不存写操作。
- 缓存会在登录/退出时清空，避免同一设备不同账号之间的缓存串用。
- 由于没有独立远程后端，电脑关机/断网时手机只能读缓存，不能导入/解析/AI。

---

## 三、本次实际改动

### 3.1 课程知识库

新增 `frontend/src/pages/SubjectKnowledgePage.tsx`：

- 并行加载 `GET /subjects/{id}`、`/subjects/{id}/chapters`、`/documents?subject_id=`、
  `/knowledge-points?subject_id=&limit=2000`、`/questions?subject_id=&limit=200`；
- 客户端按 `subject_id` 过滤，防止后端/缓存串数据；
- 课程头部显示章节/课件/知识点/题目数量；
- 按章节筛选，展示课件解析状态、失败原因、重试解析；
- 知识点搜索/列表/详情（解释、核心要点、条件、来源）；
- 题目列表；
- 空状态分别提供“添加课件/去资料库/去题库”；
- 返回课程列表链接；
- 小屏单列、触控区域 ≥44px。

### 3.2 课程点击

`SubjectsPage`：

- 课程卡片主区域改为链接到 `/subjects/{id}/knowledge`；
- 新增“进入知识库”按钮；
- 保留“章节管理/编辑/删除”；
- 不改变原有创建/更新/删除 API 与行为。

`SubjectDetailPage` 增加“知识库”入口，保留原章节管理。

### 3.3 离线缓存

新增：

- `frontend/src/lib/offline/cache.ts`：IndexedDB（浏览器/Android WebView）为主，localStorage 兜底；
- `frontend/src/lib/offline/network.ts`：网络错误判断、在线状态 Hook；
- `frontend/src/components/OfflineBanner.tsx`：全局离线提示。

策略：

- 成功加载课程列表/课程知识库后写入快照；
- 网络不可达（无 HTTP 状态，DNS/拒绝/超时）时读取缓存；
- 缓存页面明确显示“离线缓存 + 时间”，不伪造实时结果；
- 联网后自动重新加载（课程页/课程列表）；
- 登录/退出时清空缓存。

### 3.4 手机端导入强化

`DocumentUploadCard`：

- 前端格式白名单与 25 MB 限制；
- 显示文件名/大小；
- 离线时禁止上传并保留文件；
- 网络失败保留文件，按钮变为“重试上传”；
- 成功后显示“已上传，等待后端解析”；
- 重复内容仍走后端 `duplicate_document`，不会重复建记录。

`ImportPage`：

- 同样的格式/大小预检；
- 离线提示与提交禁用；
- 网络失败保留文件，恢复后重试；
- 原有 `ImportJob` 状态轮询、失败重试、重复策略不变。

### 3.5 Android 返回

`MainActivity.java` 覆盖 `onBackPressed()`：WebView `canGoBack()` 时调用
`webView.goBack()`，否则交给 Capacitor 默认行为。真机实测从课程知识库返回课程列表，
不再直接退出 App。

### 3.6 未改

- 后端 API、数据库、迁移；
- 知识点审核规则、AI 调用逻辑；
- Android Manifest、签名、Release 明文策略；
- 电脑端原有业务页面（除课程入口与知识库新增）。

---

## 四、运行条件

### 场景 A：手机与电脑同一局域网

- Debug APK 可以访问 `http://<电脑IP>:8000/api/v1`；
- 需要电脑后端 `--lan` 监听，必要时放行防火墙；
- 真机主流程已用 **临时副本数据库 + `adb reverse`** 验证：安装、连接、课程点击、
  知识库/知识点、文件选择、导入/解析、Android 返回、离线缓存与恢复均通过。
- **同 Wi-Fi 局域网与互联网 HTTPS 仍未验证**；`adb reverse` 不能替代局域网验收。

### 场景 B：互联网 HTTPS

- 需要独立远程后端、HTTPS 域名反向代理；
- 签名 Release 只接受 HTTPS；当前没有部署；
- 本次未创建 Tunnel/DNS/公网端口。

### 场景 C：离线

- 可以浏览本机已缓存的课程/知识库；
- 不能上传、解析、AI 分析、审核或提交练习；
- 页面明确提示，不显示模拟结果；
- 缓存没有实时一致性保证，联网后自动刷新。

---

## 五、真正“电脑关机仍可导入/AI”的方案与限制

现有项目不具备以下任一条件：

1. 手机本地 PDF/Office 解析器；
2. 手机本地 AI 模型；
3. 独立远程后端。

因此当前正确方案只能是：

- **推荐**：始终在线的远程 FastAPI + HTTPS（云主机/常开主机），手机通过 HTTPS 访问同一后端；
- 或：自建/集成手机端解析与本地模型（需单独评估包体、性能、准确率和维护成本）；
- 本次不擅自购买服务、注册域名、开公网端口。

在不具备上述条件时，手机离线只能读缓存，不能“完成真实分析”。

---

## 六、安全与数据

- 未迁移真实数据库；真实库仍为 `0009_question_bank`（10 学科/2 资料/78 知识点/7 题/3 练习）。
- 隔离库测试发现并修复了 `0010_users_auth` 迁移的 SQLite 重建风险：原
  `batch_alter_table("subjects")` 会级联删除章节等子表；已改为直接 `ADD COLUMN`，
  并新增“0009 有章节 → 0010 后章节仍存在”的迁移测试。
- 未修改 `v1.0.0-rc.1` 标签。
- APK 不包含 AI Key、DB 口令、keystore、Service Token。
- Debug 允许 HTTP 仅用于局域网；Release 仍禁止明文。
- 缓存只读、无秘密；登录/退出清空。
- 未创建 Tunnel、未改 DNS、未开公网端口。

---

## 七、代码索引

- `frontend/src/pages/SubjectKnowledgePage.tsx`
- `frontend/src/pages/SubjectsPage.tsx`
- `frontend/src/pages/SubjectDetailPage.tsx`
- `frontend/src/components/DocumentUploadCard.tsx`
- `frontend/src/pages/ImportPage.tsx`
- `frontend/src/lib/offline/cache.ts`
- `frontend/src/lib/offline/network.ts`
- `frontend/src/components/OfflineBanner.tsx`
- `frontend/src/router.tsx`
- `frontend/src/styles.css`
- `frontend/android/app/src/main/java/ai/biolearn/app/MainActivity.java`
- `backend/alembic/versions/0010_users_auth.py`（迁移数据保全修复）
- `frontend/src/pages/SubjectKnowledgePage.test.tsx`
- `frontend/src/pages/SubjectsPage.test.tsx`
- `frontend/src/components/DocumentUploadCard.test.tsx`
