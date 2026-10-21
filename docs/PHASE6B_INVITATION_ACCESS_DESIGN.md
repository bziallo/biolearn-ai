# 阶段 6B：邀请制身份与权限设计

状态：**已按 2026-10-21 决策实现（隔离库与代码测试完成）；真实数据库未迁移，未开放公网。**
实现报告见 `docs/PHASE6B_IMPLEMENTATION.md`。本文件保留设计与取舍记录。

---

## 一、目标与边界

### 角色

| 角色 | 能力 |
| --- | --- |
| Owner | 管理自己的全部数据、邀请/停用用户、授权/撤销共享、AI 配置、备份；可读取自己的数据 |
| Invited User | 独立账号；只能访问被共享的学科/资料/题目，以及自己的练习记录 |
| Anonymous | 只能访问健康检查、登录/邀请接受页和静态前端；不能访问业务数据 |

### 明确不做

- 不把 Cloudflare Access 的交互式登录套在所有 API 前；应用自身负责业务认证。
- 不把 Service Token 或长期密钥写进 APK。
- 不允许前端隐藏按钮代替服务端授权。
- 不在本阶段自动把真实数据迁移给某个用户；迁移前单独审批。

---

## 二、身份模型（拟新增表）

### `users`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID/str PK | 用户 id |
| username | str unique | 登录名；大小写不敏感 |
| display_name | str | 显示名 |
| password_hash | str | **Argon2id** 编码串，不存明文 |
| role | str | `owner` / `user` |
| status | str | `active` / `disabled` |
| created_at / updated_at | datetime | 时间戳 |
| last_login_at | datetime nullable | 最近登录 |
| failed_login_count | int | 失败计数 |
| locked_until | datetime nullable | 锁定截止 |

约束：最多一个 `owner`（部分唯一索引）；`role`、`status` 用 CheckConstraint。

### `sessions`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | str PK | 会话 id |
| user_id | FK users | 所属用户 |
| token_hash | str unique | 32 字节随机 token 的 SHA-256；不存原文 |
| created_at / last_seen_at / expires_at | datetime | 绝对/空闲过期 |
| revoked_at | datetime nullable | 登出/撤销 |
| user_agent_hash / ip_hash | str nullable | 可选审计，哈希/截断，不存原始 IP |
| rotated_from | str nullable | 刷新令牌轮换链 |

策略建议：访问 token 15 分钟；刷新 token 30 天；空闲 12 小时过期；刷新时轮换并检测复用。

### `invitations`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | str PK | 邀请 id |
| token_hash | str unique | 一次性 token 的 SHA-256 |
| created_by | FK users | Owner |
| role | str | 固定 `user`（不可邀请 owner） |
| expires_at | datetime | 默认 7 天 |
| used_at / used_by | datetime/FK | 单次使用 |
| revoked_at | datetime nullable | 撤销 |
| note | str nullable | 备注（不含秘密） |

### `subject_grants`（资源授权）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | str PK | 授权 id |
| subject_id | FK subjects | 被共享学科 |
| grantee_user_id | FK users | 被授权用户 |
| permission | str | `read` / `practice` / `write`（默认 read） |
| created_by | FK users | Owner |
| created_at / revoked_at | datetime | 撤销时间 |

唯一约束：`(subject_id, grantee_user_id, revoked_at is null)`；撤销用时间戳，不删审计记录。

### 归属字段

- `subjects.owner_id`：现有 10 个学科迁移后归 Owner；新增学科默认当前 Owner。
- `practice_sessions.user_id`：每条练习归实际答题用户，**不是**学科所有者。
- `practice_answers` 通过 session 间接归属；不重复加 user_id。
- `documents/chapters/knowledge_points/questions` **不重复加 owner_id**，统一通过
  `subject.owner_id` + `subject_grants` 授权，避免多份真相。
- `import_jobs`、`knowledge_extraction_jobs`、`question_generation_jobs` 增加 `created_by`，
  用于任务归属/取消权限；AI 出题默认仅 Owner。
- `import_preferences` 增加 `user_id`（或改为 per-user key-value）；当前是全局单例。

---

## 三、认证流程

### Owner 初始化（不通过公网）

新增本地脚本 `scripts/create_owner.py`：

1. 检查 users 表无 owner；
2. 交互式 `getpass` 输入密码（最少 12 位，或生成随机初始密码一次显示）；
3. Argon2id 哈希入库；
4. 不打印密码到日志；不接受命令行明文密码参数。

不在 Web 暴露 `/auth/setup` 公网接口，避免抢注。

### 邀请

1. Owner 登录 → `POST /api/v1/admin/invitations`；
2. 服务端生成 32 字节随机 token，返回一次性邀请链接（仅在响应中出现一次）；
3. 数据库只存 SHA-256；默认 7 天、单次；
4. 被邀请者打开 `/join?token=...` → 设置用户名/密码 → 创建 `user`；
5. 邀请标记 used；重复使用/过期/撤销均失败。

### 登录

`POST /api/v1/auth/login`：

- 输入 username/password；
- 统一错误“用户名或密码错误”，不泄露账号是否存在；
- 失败计数 + 指数退避/锁定（如 5 次/15 分钟）；
- 成功返回 access + refresh（refresh 仅一次）；
- 审计 `login_success` / `login_failed` / `locked`。

### 会话与传输

- API 使用 `Authorization: Bearer <access_token>`；服务端只存 token hash。
- 浏览器：access 在内存；refresh 放 `HttpOnly; Secure; SameSite=Strict` Cookie（同源部署）。
- Android：access 在内存；refresh 通过原生插件存 Android Keystore（不使用 localStorage 长期保存）。
- 刷新：`POST /auth/refresh` 轮换 refresh；旧 token 复用 → 撤销整个会话链。
- 登出：撤销当前 session；`POST /auth/logout-all` 撤销该用户全部 session。
- 401 = 未认证；403 = 已认证但无资源权限；两者前端区分提示。

---

## 四、授权规则

### 资源可见性

| 资源 | Owner | Invited User |
| --- | --- | --- |
| Subject | 自己拥有的全部 | 仅 `subject_grants` 中 read/practice/write |
| Chapter/Document/Chunk/KnowledgePoint/Question | 通过 subject 继承 | 通过 subject 继承；默认只读已发布内容 |
| PracticeSession/Answer | 自己的 | 自己的；**不能读别人的** |
| Import/Extraction/Generation Job | 自己创建的 | 自己创建的（若允许）；默认无 |
| AI 配置 | 读写 | 不可见/不可写 |
| 邀请/用户管理 | 全部 | 不可见 |
| 备份/恢复 | 本地 Owner 工具 | 不可用 |

### 写操作

- 默认只有 Owner 能上传、提取、审核、出题、修改/删除内容。
- 如未来允许 Invited User 写，必须由 Owner 显式授予 `write`，并在每次写操作校验；
  本阶段默认不开放写，降低误操作与费用风险。
- `POST /questions/generate`、`POST /knowledge-jobs` 等 AI 操作仅 Owner（或明确授权），
  避免邀请用户消耗 Owner 额度。

### 服务端强制点

每个请求：

1. 认证依赖解析 Bearer → session → user（active，未过期）；
2. 资源依赖从 path/body 取 id → 查询资源 → 检查 owner/subject grant；
3. 列表查询在 SQL 层 join/filter，不先查全量再在 Python 过滤；
4. 404 与 403 的选择：对无权资源返回 404 可减少枚举，但需统一策略并测试；
5. 任务查询/取消/重试、练习读取、上传、chunks、知识点、题目、AI 配置全部覆盖。

### 具体 API 改造

- 所有现有业务路由加 `Depends(require_user)`；
- 学科：`require_subject_read/write`；
- 章节/资料/知识点/题目：先解析所属 subject，再检查；
- 练习：`user_id == current_user.id`；Owner 也不能默认读他人练习；
- 任务：`created_by == current_user.id`；
- `/ai/*`：`require_owner`；
- 管理路由：`/admin/users`、`/admin/invitations`、`/admin/grants` 全部 `require_owner`；
- `/docs`、`/openapi.json`：生产环境关闭，或仅 Owner + 内网；
- `/health` 保持匿名但只返回最少信息。

---

## 五、密码、限流与审计

- 密码哈希：`argon2-cffi` 的 Argon2id（memory 64MB、iterations 3、parallelism 4 起，
  按服务器性能压测调整）；不存明文、不 log。
- 登录限流：按 IP + username 双维度，5 次/15 分钟，指数退避；成功登录清零。
- 邀请接受限流：按 IP，防枚举。
- 审计事件表 `audit_events`（可选第一阶段）：actor_user_id、action、resource_type/id、
  result、ip_hash、created_at；不记录密码/token/Key。
- 日志脱敏：Authorization、X-BioLearn-Token、Cookie、密码字段永不记录；
  `ai_config` Key 只显示 `configured=true`。

---

## 六、迁移与回滚计划（需批准后执行）

### 迁移步骤

1. **备份**真实库 + uploads；记录 `alembic current`。
2. 新迁移 `0010_users_auth`：创建 users/sessions/invitations/subject_grants；
   给 subjects/practice_sessions/jobs 加 nullable 字段；不改旧数据。
3. 本地运行 `create_owner.py` 创建 Owner（密码不入 Git/日志）。
4. **归属回填**（单独审批）：
   - 所有现有 subjects.owner_id = Owner；
   - 现有 practice_sessions.user_id = Owner（历史练习归 Owner）；
   - 现有 jobs.created_by = Owner；
   - 先跑 dry-run 计数：10 subjects、3 sessions、5 generation jobs、4 import jobs 等；
   - 回填后加 NOT NULL 与外键/索引。
5. 切换 `AUTH_MODE=accounts`；停止使用共享 `ACCESS_TOKEN`。
6. 回归：匿名 401、Owner 全量、Invited 仅授权、越权 403、练习隔离、上传/任务/AI 权限。
7. 备份恢复演练；更新发布文档。

### 回滚

- 应用：回退到 `v1.0.0-rc.1` 镜像/提交；
- 数据库：停服务 → 恢复迁移前备份；`alembic downgrade 0009_question_bank` 仅在
  确认新表无保留数据后执行；旧数据在 `_restore_previous_*`；
- 配置：恢复 `AUTH_MODE=legacy` / 旧 `ACCESS_TOKEN`；
- 域名/隧道：若已上线，先停 Tunnel、撤销 DNS 路由与 token。

**未得到批准前，不执行步骤 4 及任何真实数据写入。**

---

## 七、测试清单（隔离库 + 合成数据）

1. 无用户：匿名访问业务路由 401。
2. 创建 Owner；密码哈希非明文；错误密码失败；5 次锁定。
3. 邀请：单次、过期、撤销、重复使用、邀请不可创建 Owner。
4. 会话：过期、登出、logout-all、刷新轮换、旧 refresh 复用检测。
5. 数据隔离：A、B 各建学科/资料/知识点/题目；A 不能读/改/删 B；列表不泄露。
6. 共享：Owner 授权 A read，A 可见但不可写；撤销后立即 403/404。
7. 练习：A 的 session/answer 仅 A 可读；Owner 不能默认读 A 的练习。
8. 任务：A 不能取消 B 的 import/extraction/generation job。
9. 上传：无权限不能上传到未授权学科；大小/类型校验仍生效。
10. AI：Invited 不能读/写 `/ai/config`，不能触发付费生成（默认）。
11. 迁移：0009→0010 升级、回填 dry-run、回滚到 0009（隔离库）。
12. 前端：登录/邀请/退出/401/403；Android Release HTTPS 下会话保持与退出清理。
13. 备份恢复：迁移后备份→恢复→权限关系仍正确。

---

## 八、实施顺序（等待批准）

1. 你确认角色/默认权限/邀请方式/是否允许 Invited 写。
2. 实现模型与迁移（nullable，不动真实数据）+ 隔离测试。
3. 实现认证/会话/邀请/管理 API + 测试。
4. 实现资源授权改造（全路由矩阵）+ 越权测试。
5. 前端登录/邀请/管理页面 + Android 安全存储 + Release HTTPS 复测。
6. 在隔离库演练归属回填与回滚。
7. 经你批准后，备份真实库并执行回填/迁移。
8. 6C 隧道部署（条件满足后）→ 6D Release HTTPS 验收。

---

## 九、需要你确认的产品决策

1. Invited User 默认只能**只读 + 练习**，还是允许上传/出题/审核？
   （建议默认只读，Owner 显式授予 `write`。）
2. Owner 是否可以查看 Invited User 的练习记录？
   （建议默认不能，保护用户隐私；如需管理报表单独设计。）
3. 邀请通过复制链接，还是需要邮件发送？
   （当前没有邮件服务；建议先复制一次性链接。）
4. 是否允许用户名+密码；是否需要邮箱找回？
   （第一版建议无邮件找回，Owner 可重置用户密码。）
5. Android 是否接受引入原生安全存储插件？
   （建议接受；否则 refresh token 只能短期驻留内存。）
