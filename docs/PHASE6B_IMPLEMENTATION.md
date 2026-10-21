# 阶段 6B：邀请制身份与权限实现报告

日期：2026-10-21
基线：`v1.0.0-rc.1`（`930f279`）
状态：**代码与隔离库测试完成；真实数据库未迁移；未开放公网。**

本报告对应设计稿：`docs/PHASE6B_INVITATION_ACCESS_DESIGN.md`。

---

## 一、已实现的决策

| 决策 | 实现 |
| --- | --- |
| 朋友只读授权资源 + 练习 + 查看自己的记录 | 服务端只允许受邀用户 GET 共享学科/资料/知识点/题目，以及自己的练习 |
| Owner 不查看朋友练习 | 练习按 `practice_sessions.user_id` 隔离；Owner 读取他人 session 返回 404 |
| 一次性邀请链接 | 32 字节随机 token，数据库只存 SHA-256，7 天、单次 |
| 数据迁移先在隔离库演练 | 已做临时库升级/回滚/回填演练；真实库仍为 `0009` |
| 不安装 Tunnel/不开放公网 | 未执行；无 remote URL |
| 电脑关机不可用不接受 | 与当前 Windows 单机架构冲突；6C 暂不可部署（见验收报告） |

---

## 二、后端实现

### 2.1 数据模型与迁移

新增 `backend/app/models/auth.py`：

- `users`：用户名、显示名、Argon2id `password_hash`、角色（`owner/user`）、状态
  （`active/disabled`）、失败登录计数、锁定时间、最近登录。
- `auth_sessions`：`token_hash`（不存原文）、创建/最近使用/绝对过期/撤销时间。
- `invitations`：`token_hash`、创建者、过期、使用时间/使用者、撤销。
- `subject_grants`：学科、被授权用户、`read/practice/write`、撤销时间。

归属字段：

- `subjects.owner_id`；
- `practice_sessions.user_id`；
- `import_jobs.created_by`、`knowledge_extraction_jobs.created_by`、
  `question_generation_jobs.created_by`。

迁移：`backend/alembic/versions/0010_users_auth.py`。

- 所有新列均 nullable，不删除/重写旧数据；
- 已用临时库验证 `0009 -> 0010` 升级、`0010 -> 0009` 回滚、再升级；
- **真实数据库未执行该迁移**。

### 2.2 认证

`backend/app/services/auth.py`：

- Argon2id（64 MB、3 iterations、4 parallelism）密码哈希；
- 用户名规范化与长度校验；密码至少 10 位；
- 登录失败限流：同一 IP+用户名 15 分钟内最多 5 次，进程内计数；
- 会话 token：32 字节随机值，数据库只存 SHA-256；
- 会话 24 小时绝对过期、12 小时空闲过期；登出撤销；
- 邀请创建/接受；接受后直接建立会话；
- 授权/撤销、用户停用（同时撤销全部会话）、Owner 不可停用。

接口：

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/invitations/accept`
- `GET /api/v1/auth`（状态，公开）
- Owner 管理：
  - `GET/PATCH /api/v1/admin/users`
  - `GET/POST/DELETE /api/v1/admin/invitations`
  - `GET/POST/DELETE /api/v1/admin/grants`

Owner 初始化不通过公网接口，使用本地脚本：

```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe ..\scripts\create_owner.py --username owner
.venv\Scripts\python.exe ..\scripts\backfill_owner.py --dry-run
# 确认后
.venv\Scripts\python.exe ..\scripts\backfill_owner.py --apply
```

`prepare_env.py` 已增加保护：从 `0009` 升级到 `0010` 时，若没有设置
`BIOLEARN_APPROVE_AUTH_MIGRATION=1`，会**停止并提示，不修改真实数据库**。

### 2.3 服务端授权

`backend/app/core/authz.py` 提供：

- `Principal`（legacy / owner / invited user）；
- `accessible_subject_ids`：受邀用户只返回有效 `subject_grants` 的学科；
- `ensure_subject_access`：按 subject 检查读/写；
- `ensure_practice_session_access`：练习 session 只能属于当前用户；
- `ensure_owner`。

`backend/app/core/security.py` 的中间件：

- 无用户时保留旧共享口令/本机模式（兼容旧库和现有测试）；
- 有用户后：
  - 所有 `/api/v1/*` 业务请求需要 Bearer session；
  - SPA 静态文件和登录/健康接口公开；
  - 受邀用户仅允许：
    - GET 学科、章节、资料、知识点、题目、练习、`/auth/me`；
    - POST 开始练习、提交练习、登出；
  - 其余写操作、AI、导入、知识点任务、出题任务、管理接口一律 403；
- 未迁移数据库时，受保护 API 返回 `503 database_migration_required`，避免 500。

资源级检查已接入：

- 学科列表按授权过滤；学科读/写检查；
- 章节读/写；
- 资料列表、详情、chunks、解析/删除；
- 知识点列表、详情、审核、合并、删除；
- 题目列表、详情、编辑、审核、重新生成；
- 练习开始、提交、结果、人工评分、错题、列表；
- 练习记录按 `user_id` 过滤，Owner 也不能读他人记录。

### 2.4 数据迁移脚本

`scripts/backfill_owner.py`：

- 默认 dry-run，只打印待回填计数；
- `--apply` 才写入；
- 回填 `subjects.owner_id`、`practice_sessions.user_id`、三类任务的 `created_by`。

已在临时库验证：dry-run 不改数据，apply 后归属正确。

---

## 三、前端实现

- `LoginPage`：用户名/密码登录；
- `JoinPage`：一次性邀请 token + 设置用户名/密码；
- `AdminPage`：邀请、复制链接、撤销邀请、成员停用/启用、按学科授权、撤销授权；
- 路由：`/login`、`/join`、`/admin`；
- Connection 页面增加“登录账号”“成员与共享”入口；
- 会话 token 改存 `sessionStorage`，不再写入长期 `localStorage`；
- 401 提示改为“需要登录”，403 由服务端返回权限提示。

未做：Android 原生 Keystore 插件；当前依赖 WebView 会话存储。此项列为 6D 前需要补强的安全项。

---

## 四、隔离库测试证据

### 自动化测试

| 项 | 结果 |
| --- | --- |
| 后端完整测试 | **116 passed**（原 110 + 新增 6 个账户/权限测试） |
| 前端测试 | **30 passed / 13 files** |
| 前端 TypeScript | 通过 |
| 前端 ESLint | 通过 |
| 前端生产构建 | 通过 |
| Android Debug 构建 | `BUILD SUCCESSFUL` |

### 新增权限测试覆盖

- 匿名访问业务 API → 401；
- Owner 登录、错误密码、密码哈希非明文；
- 邀请创建/接受、单次使用、重复使用失败；
- 受邀用户授权前看不到学科，授权后只看到指定学科；
- 受邀用户不能创建学科、不能访问 AI/导入/管理；
- 受邀用户可开始/提交自己的练习；
- Owner 读取受邀用户练习详情/结果 → 404，列表不包含；
- 两个受邀用户 A/B 只能看到各自被授权的学科，跨用户读取 → 404；
- 登出后旧 token → 401；
- 停用用户后旧 token → 401，重新登录 → 403。

### 迁移演练

临时库执行：

1. `alembic upgrade head`（含 0010）；
2. 创建 Owner；
3. 插入遗留 subject/practice session；
4. `backfill_owner.py --dry-run`（不修改）；
5. `backfill_owner.py --apply`（归属正确）；
6. `alembic downgrade 0009_question_bank`；
7. 再 `upgrade head`。

全部通过。真实库当前仍为：

- Alembic `0009_question_bank`；
- 10 学科 / 6 章节 / 2 资料 / 78 知识点 / 7 题 / 3 练习 / 6 作答；
- 无 `users` 表。

---

## 五、当前限制与未完成项

1. **真实库未迁移**：需要你单独批准后执行 0010 + Owner/回填。
2. **没有 HTTPS/域名/Tunnel**：签名 Release 仍无法远程登录。
3. **Android 未做原生安全存储**：token 在 WebView `sessionStorage`，应用重启后可能需重新登录；
   未使用 Android Keystore。
4. **无刷新 token**：24 小时绝对过期，过期后重新登录。
5. **登录限流是进程内内存**：重启清零，多进程不共享；单机单进程当前可接受。
6. **没有审计日志表/邮件找回**：Owner 重置密码需后续补。
7. **`/docs`、`/openapi.json` 在账户模式下仍公开**：生产应关闭或仅 Owner/内网。
8. **未做 Android 真机登录/邀请流程**：只完成 Debug 构建；无 HTTPS Release 环境。

这些限制不影响“隔离库中 Owner/受邀用户权限隔离”已通过的结论，但阻止正式远程发布。

---

## 六、回滚

- 应用：回退到 `v1.0.0-rc.1`（`930f279`）；
- 数据库：恢复迁移前备份；或 `alembic downgrade 0009_question_bank`
  （仅在新表无保留数据时）；
- 关闭账户模式：回退代码即可恢复旧共享口令模式；不建议在真实用户数据产生后回退；
- 若未来已开 Tunnel：先停 Tunnel、撤销 DNS/Token，再回滚应用。

---

## 七、结论

阶段 6B 的**代码、隔离库迁移与权限测试已完成**，满足“Owner + 一次性邀请 + 只读共享 + 练习隔离 + Owner 不看朋友练习”的已确认决策。

但**不能据此开放公网**：真实库未迁移、无 HTTPS、无 Android Release 验证；且“电脑关机不可用不接受”与当前 Windows 单机 + 禁用 Tunnel 的条件直接冲突。下一步应先决定始终在线的主机方案，再进入 6C/6D。
