# 阶段 6A：远程访问与身份权限只读审计

日期：2026-10-21
基线：`930f279`（`v1.0.0-rc.1`）
审计方式：只读代码/数据库结构检查；未修改真实数据、未注册域名、未配置隧道、未开放公网。

---

## 一、基线核实

| 项 | 实际值 |
| --- | --- |
| 分支 | `main` |
| HEAD | `930f279cb8aab161f263e4cdb167fb998580b5e0` |
| RC 标签 | `v1.0.0-rc.1`（指向 `930f279`） |
| 历史标签 | `v1.0.0`（旧阶段，未移动） |
| 工作区 | 干净（0 个未提交文件） |
| 远端 | `https://github.com/bziallo/biolearn-ai.git` |
| 数据库 | `backend/data/biolearn.db`，Alembic `0009_question_bank` |
| 上传目录 | `backend/data/uploads/`，当前 7 个文件 |
| 当前监听 | `0.0.0.0:8000`（以 `--lan` 启动） |
| 当前认证 | `GET /api/v1/auth` 返回 `{"required":false}` → **当前无口令保护** |
| cloudflared | 未安装 |
| 域名/Cloudflare 账户 | 未知/未提供 |

---

## 二、认证机制现状

### 2.1 唯一机制：可选共享口令

实现：`backend/app/core/security.py` 的 `AccessTokenMiddleware`。

- `ACCESS_TOKEN` 为空时，中间件直接放行 — **默认无认证**。
- 设置后，除以下路径外全部要求请求头：
  - `GET /api/v1/health`
  - `GET /api/v1/auth`
  - `/docs`、`/redoc`、`/openapi.json`
  - `/assets/` 静态资源
  - `OPTIONS` 预检
- 支持 `Authorization: Bearer <token>` 或 `X-BioLearn-Token`。
- 使用 `hmac.compare_digest` 比较，避免时序侧信道。
- `auth_required` 只表示“配置了口令”，**不表示请求有用户身份**。

### 2.2 没有的东西

- 没有用户表、邀请、角色、会话、密码哈希。
- 没有按用户隔离的数据字段；所有学科/资料/知识点/题目/练习是**全局单库**。
- 没有登录、退出、会话过期、刷新、撤销。
- 没有登录限流、失败锁定、审计日志。
- 没有 CSRF 令牌（但使用自定义 Header，当前无 Cookie 会话）。
- 没有服务端资源级授权；任何持有共享口令的客户端可读写全部资源。

### 2.3 前端保存方式

- `frontend/src/lib/api/connection.ts`：`TOKEN_KEY = 'biolearn.access_token'`，
  存在 `window.localStorage`。
- `frontend/src/lib/api/client.ts`：每个请求自动加 `X-BioLearn-Token`；
  401 显示“需要访问口令”。
- `ConnectionSettingsPage.tsx`：输入框保存口令；没有登录页/用户概念。
- Android Release 不启用 WebView 调试；但 localStorage 仍是明文存储，未使用 Android Keystore。

---

## 三、API 路由与权限现状

所有路由挂载在 `/api/v1`，**没有路由级 `Depends(require_user)` 或资源授权**。
设置 `ACCESS_TOKEN` 后，唯一的边界是“知道全局口令 / 不知道”。

### 3.1 公开路由（即使启用口令也公开）

| 方法 | 路径 | 说明 | 风险 |
| --- | --- | --- | --- |
| GET | `/api/v1/health` | 健康检查 | 低（信息有限） |
| GET | `/api/v1/auth` | 口令状态 | 低（不返回口令） |
| GET | `/docs` | Swagger UI | 中：暴露完整 API 结构 |
| GET | `/redoc` | ReDoc | 中：同上 |
| GET | `/openapi.json` | OpenAPI schema | 中：同上 |
| GET | `/assets/*` | 前端静态资源 | 低 |

### 3.2 业务路由（只受全局口令保护）

| 模块 | 方法/路径 | 当前授权 |
| --- | --- | --- |
| 学科 | `GET/POST /subjects`, `GET/PATCH/DELETE /subjects/{id}`, `GET/POST /subjects/{id}/chapters` | 全局口令 |
| 章节 | `GET/PATCH/DELETE /chapters/{id}`, `POST /chapters/{id}/move` | 全局口令 |
| 资料 | `POST/GET /documents`, `GET/PATCH/DELETE /documents/{id}`, `GET /documents/{id}/chunks`, `POST /documents/{id}/retry-parse`, `POST /documents/{id}/extract`, `GET /documents/{id}/jobs`, `GET /documents/{id}/knowledge-points` | 全局口令 |
| 导入 | `GET/PUT /imports/preferences`, `GET/POST /imports`, `GET /imports/external/template`, `POST /imports/external`, `GET /imports/{id}`, `POST /imports/{id}/confirm`, `POST /imports/{id}/retry` | 全局口令 |
| 知识点 | `GET/POST /knowledge-points`, `POST /knowledge-points/bulk-review`, `POST /knowledge-points/merge`, `GET/PATCH/DELETE /knowledge-points/{id}`, `GET/POST /knowledge-jobs`, `GET /knowledge-jobs/{id}`, `POST /knowledge-jobs/{id}/cancel` | 全局口令 |
| 题库 | `GET/POST /questions`, `POST /questions/generate`, `GET/POST /questions/generation-jobs/{id}`, `POST /questions/generation-jobs/{id}/retry`, `POST /questions/generation-jobs/{id}/cancel`, `POST /questions/bulk-review`, `POST /questions/{id}/regenerate`, `GET/PATCH /questions/{id}`, `POST /questions/{id}/review` | 全局口令 |
| 练习 | `POST/GET /practice/sessions`, `GET /practice/wrong-questions`, `GET /practice/sessions/{id}`, `POST /practice/sessions/{id}/submit`, `GET /practice/sessions/{id}/result`, `POST /practice/answers/{id}/grade` | 全局口令 |
| AI 配置 | `GET /ai/status`, `GET/PUT/DELETE /ai/config`, `POST /ai/test` | 全局口令（**含写 Key**） |

路由来源：`backend/app/api/v1/router.py` 及 `subjects.py`、`chapters.py`、`documents.py`、
`imports.py`、`knowledge.py`、`questions.py`、`practice.py`、`ai.py`。

---

## 四、数据模型与关联（真实结构）

当前表：`subjects`、`chapters`、`documents`、`document_chunks`、`import_jobs`、
`import_preferences`、`knowledge_extraction_jobs`、`knowledge_points`、`questions`、
`question_knowledge_points`、`question_generation_jobs`、`practice_sessions`、`practice_answers`。

| 实体 | 关键关联 | 用户/所有者字段 |
| --- | --- | --- |
| Subject | 1→N Chapter/Document/KnowledgePoint/Question | **无** |
| Chapter | subject_id、parent_id | **无** |
| Document | subject_id、chapter_id、storage_name | **无** |
| DocumentChunk | document_id | **无** |
| KnowledgePoint | subject_id、document_id、chapter_id | **无** |
| Question | subject_id、chapter_id、source_document_id、generation_job_id | **无** |
| PracticeSession | subject_id、chapter_id、question_ids | **无 user_id** |
| PracticeAnswer | session_id、question_id、question_snapshot | **无 user_id** |
| ImportJob | document_id | **无 user_id** |
| KnowledgeExtractionJob | document_id | **无 user_id** |
| QuestionGenerationJob | subject_id、chapter_id | **无 user_id** |
| ImportPreferences | 全局单例（default_subject_id 等） | **无** |

**结论：当前没有“谁拥有什么”的概念。** 即使给 API 加登录，也不能仅靠前端隐藏按钮实现隔离；
必须在服务端增加所有权/授权并在查询层过滤。

### 数据关联的实际含义

- 删除学科会级联章节，文档/知识点/题目通过外键/服务层级联或置空；
- 资料解析为 chunk，知识点引用 document/chapter；
- 题目引用 subject/chapter/document/knowledge_points；
- 练习会话保存题目快照与作答，**目前所有练习记录属于全局单库**；
- 导入/提取/出题任务是进程内 BackgroundTasks，任务记录无所有者；
- 备份脚本复制整个 SQLite 与 uploads，不区分用户。

---

## 五、上传、下载、AI、后台任务与备份

### 上传

- `POST /documents` 和 `POST /imports` 接收 multipart 文件，写入
  `backend/data/uploads/<uuid>.<ext>`；最大 25 MB（`max_upload_bytes`）。
- 有文件名清洗和路径逃逸检查（`documents.py`）。
- **没有用户级配额、没有所有者检查**；任何持有口令者可向任意学科上传并触发磁盘/解析消耗。

### 下载

- 没有原始文件下载路由；`GET /documents/{id}/chunks` 返回解析文本，`GET /documents/{id}`
  返回元数据。
- `backend/data/uploads/` 未作为静态目录挂载；这是优点。
- 但 chunks/知识点 API 仍会暴露全文内容，需要资源级授权。

### AI

- `POST /documents/{id}/extract`、`POST /questions/generate`、
  `POST /questions/{id}/regenerate` 都会调用付费模型。
- `GET/PUT/DELETE /ai/config`、`POST /ai/test` 可查看/修改服务端 AI 配置；
  真实 Key 只保存在后端，但任何持有共享口令者可改 Key 或消耗额度。
- AI 生成任务无所有者；任何客户端可按 job id 查询/取消/重试。

### 后台任务

- FastAPI `BackgroundTasks` + 进程内 `job_control` 注册表；
- 服务重启会把未完成任务标记失败；
- 没有持久队列、没有 worker 身份、没有按用户配额/取消权限。

### 备份/恢复

- `scripts/backup_data.py` 备份 SQLite、uploads、`ai_config.json`（含 Key）、`.env.example`；
- `scripts/restore_data.py` 停止端口检查、旧数据移到 `_restore_previous_*`、Alembic 升级；
- 备份**不含用户身份**（当前也没有），恢复会恢复全局数据；
- 备份目录未加密；`ai_config.json` 是明文 Key，必须视为高敏感文件。

---

## 六、Android 与 Release 策略

- API Base：运行时 localStorage 覆盖 > 构建时 `VITE_DEFAULT_API_BASE_URL` > 同源；
  Android 不回退 localhost。
- Release manifest **没有 `usesCleartextTraffic`**，只允许 HTTPS；Debug manifest 才有明文。
- 证书校验使用系统 WebView 默认信任链；没有证书 pinning。
- 共享口令存入 localStorage（明文、无 Keystore）；Release 关闭 WebView 调试。
- `capacitor.config.ts`：`androidScheme=https`、`allowMixedContent=true`（仅为局域网 HTTP 调试；
  HTTPS 下不生效）。
- 签名 Release `outputs/release/BioLearnAI-1.0.0-rc.1-signed.apk`（versionCode 2）已验证安装/升级，
  但当前无 HTTPS 服务，无法完成 Release 联网验收。

---

## 七、SQLite、迁移与敏感文件

- SQLite 位于 `backend/data/biolearn.db`；上传目录同层 `uploads/`。
- Alembic 当前 head：`0009_question_bank`。
- 数据库与 uploads 均不在 Git；`.gitignore` 覆盖 `backend/data/*`、uploads、`.env`、
  Android keystore、`keystore.properties`、APK。
- 审计 `git ls-files`：未发现 `.env`、真实数据库、APK、keystore、`ai_config.json`。
- `backend/app/services/ai_config.py` 被 grep 命中只是源码文件名，不是运行时配置。
- 当前真实数据：10 学科 / 6 章节 / 2 资料 / 78 知识点 / 7 题 / 3 练习 / 6 作答。

---

## 八、风险登记（按优先级）

| ID | 风险 | 等级 | 证据 | 影响 | 修复方向 |
| --- | --- | --- | --- | --- | --- |
| R1 | 默认无认证；LAN 模式可被同网段任意访问 | **严重** | `ACCESS_TOKEN` 空；`/auth` required=false；监听 0.0.0.0:8000 | 任意同网段者可读写全部数据、改 AI Key、消耗额度 | 默认绑定 loopback；远程必须启用认证；6B 用户体系 |
| R2 | 共享口令 = 全库全权限，无用户隔离 | **严重** | 中间件只比较单一 token；模型无 owner_id | 邀请一个用户等于给全部数据；无法撤销单个用户 | 6B Owner/InvitedUser + 资源授权 |
| R3 | 无会话/过期/撤销；token 长期有效 | **高** | 无 session 表；localStorage 持久保存 | 泄露后长期可用；无法强制下线 | 服务端会话、过期、轮换、登出撤销 |
| R4 | 无登录限流/锁定 | **高** | 无 rate limit 代码 | 口令/密码可被暴力尝试 | 登录限流、失败锁定、审计 |
| R5 | 练习记录无 user_id，任何人可读任意 session | **高** | `practice_sessions` 无 user_id；`GET /practice/sessions/{id}` 仅按 id | 隐私泄露/越权 | 增加 user_id + 查询过滤 |
| R6 | 资料/知识点/题目按全局 ID 可读；无资源授权 | **高** | 服务层按 id 直接 `db.get`，无 owner 检查 | 知道/猜到 UUID 即可读取 | 所有权 + subject grant 检查 |
| R7 | AI 配置写接口仅受共享口令保护 | **高** | `PUT/DELETE /ai/config` 无角色检查 | 任意口令持有者可改 Key、消耗费用 | 仅 Owner 可写；审计；掩码 |
| R8 | 上传无配额/所有者，可磁盘耗尽 | **中高** | 全局 25MB 限制；无 per-user quota | 邀请用户可反复上传 | 配额、所有者、清理策略 |
| R9 | 后台任务无所有者，可查询/取消 | **中高** | job id 全局；无 user_id | 越权取消/读取任务 | 任务 owner_id + 授权 |
| R10 | `/docs`、`/openapi.json` 即使有口令也公开 | **中** | `PUBLIC_PREFIXES` 固定放行 | API 结构泄露，增加攻击面 | 生产禁用/仅 Owner/内网 |
| R11 | 备份含明文 AI Key，备份目录未加密 | **高** | `backup_data.py` 复制 `ai_config.json` | 备份泄露导致 Key 泄露 | 加密备份/密钥分离/权限 |
| R12 | Token 存 localStorage，无 Keystore | **中** | `connection.ts` | 设备被攻破时可读；XSS 风险 | Android Keystore/短会话；CSP |
| R13 | 无审计日志（谁改了什么） | **中** | 无 auth 事件/操作日志 | 无法追责/发现异常 | 审计表/结构化日志 |
| R14 | CORS 未包含未来远程域名 | **中** | `cors_extra_origins` 默认空 | 浏览器跨域失败；若放开过宽有风险 | 显式配置域名，不使用 `*` |
| R15 | 远程 TLS/隧道未验证 | **高（部署）** | cloudflared 未安装；无域名/证书 | 无法对外提供 HTTPS | 6C 计划 + 实际验收 |
| R16 | 无原始文件下载接口 | 低（安全正面） | 路由清单无 download | 功能限制，非漏洞 | 若增加下载必须鉴权 |

---

## 九、必须修改的代码范围（6B，不是本轮实施）

1. 新模型/迁移：
   - `users`（role/status/password_hash）、`sessions`、`invitations`、`resource_grants`；
   - `subjects.owner_id`；`practice_sessions.user_id`；
   - 需要 owner 的任务/导入记录外键或 `created_by`；
   - 对现有 10 个学科/3 个练习的所有权迁移（**先提交迁移+回滚计划并等待批准**）。
2. 认证：
   - Argon2id 密码哈希；登录/登出；邀请接受；会话过期与撤销；
   - 登录限流/失败锁定；审计事件；敏感字段日志脱敏。
3. 授权：
   - `require_user`、`require_owner`、`require_subject_read/write` 依赖；
   - 所有 subject 派生资源在查询层 join/filter；练习按 `user_id`；任务按 owner；
   - 上传、chunks、知识点、题目、生成、取消、重试、AI 配置逐一加检查。
4. 配置：
   - `AUTH_MODE`（legacy/accounts）、`SESSION_TTL`、`INVITE_TTL`、`TRUSTED_HOSTS`、
     `CORS_ORIGINS` 远程域名；生产关闭 `/docs`/`openapi.json` 或仅 Owner。
5. 前端：
   - 登录/邀请/退出 UI；会话存储（浏览器 sessionStorage/Android Keystore）；
   - 401/403 区分“未登录/无权限”；不再把共享口令当用户身份；
   - Owner 管理页（邀请、停用、授权、撤销）。
6. Android：
   - 登录页/令牌刷新；不打包任何 Service Token；Release 继续只允许 HTTPS；
   - 证书校验保持系统信任链（可评估 pinning，不默认启用）。
7. 测试：
   - 用户 A/B 越权、邀请过期/单次、会话过期/撤销、限流、上传/资料/知识点/题目/练习/任务
     全路由 403 测试、迁移回滚、备份恢复、Android Release HTTPS。

---

## 十、外部条件（需要你确认/提供）

| 条件 | 当前状态 | 需要你做什么 |
| --- | --- | --- |
| Cloudflare 账户 | 未确认 | 告知是否已有；没有则先注册 |
| 自有域名 | 未提供 | 提供域名；确认可修改 NS |
| 域名已接入 Cloudflare | 未确认 | 在 Cloudflare 添加站点并等待 Active |
| Windows 常开/休眠 | 未确认 | 关闭睡眠/休眠，设置通电自启；确认可接受关机即不可用 |
| 网络出口 | 未验证 | 确认可稳定访问 Cloudflare（cloudflared 出站 7844/UDP+TCP） |
| 公网入站 | 当前未开放 | 保持不开放；只用 Tunnel 出站 |
| 当前服务监听 | `0.0.0.0:8000` | Tunnel 前改为 `127.0.0.1:8000`，并启用认证 |
| Cloudflare Access | 未配置 | 仅用于 `/docs`/运维入口，不默认拦所有 API |

---

## 十一、只读审计结论

**当前版本不能直接暴露到公网或通过 Tunnel 提供给邀请用户。**
主要不是 TLS 问题，而是：

1. 默认无认证；
2. 唯一认证是全局共享口令，没有用户身份；
3. 数据模型没有所有权/授权，无法做用户隔离；
4. 练习、任务、AI 配置均是全局可访问；
5. 备份含明文 AI Key。

在 6B 完成前，任何“邀请用户”方案都会等价于“把全部数据交给对方”。因此下一步应
先实现 6B 身份与授权，并通过隔离库测试；6C 只能做计划与条件检查，不得直接启动隧道
对外服务。

---

## 十二、6B 修复状态（2026-10-21 追加）

本审计完成后的 6B 实现已覆盖部分风险；详细证据见
`docs/PHASE6B_IMPLEMENTATION.md`。

| 风险 | 状态 |
| --- | --- |
| R1 默认无认证 | 创建 Owner 后由中间件强制登录；未迁移/未建 Owner 的旧库仍保留 legacy 兼容 |
| R2 共享口令全权限 | 已由用户/会话/学科授权替代；Owner 单点管理 |
| R3 无会话/撤销 | 已实现 24h/12h 过期、登出、停用撤销 |
| R4 无限流 | 已实现进程内 5 次/15 分钟限流；多进程共享未实现 |
| R5 练习记录无 user_id | 已增加并强制隔离；Owner 不能读他人记录 |
| R6 资源无授权 | 学科/章节/资料/知识点/题目已加 read/write 检查 |
| R7 AI 配置无角色 | 受邀用户访问 `/ai/*` 为 403；仅 Owner |
| R8 上传无配额 | 未解决（受邀用户禁止上传；Owner 配额仍无） |
| R9 任务无 owner | 任务已加 `created_by`；受邀用户禁止任务接口 |
| R10 docs 公开 | **仍未解决**；账户模式 `/docs`、`/openapi.json` 仍公开 |
| R11 备份含明文 Key | **仍未解决**；备份脚本仍复制 `ai_config.json` |
| R12 token localStorage | 已改 `sessionStorage`；Android 原生 Keystore 未实现 |
| R13 无审计日志 | 未实现审计表；仅服务端日志 |
| R14 CORS 域名 | 仍需部署时显式配置远程域名 |
| R15 TLS/隧道 | 未部署；6C 阻塞 |
