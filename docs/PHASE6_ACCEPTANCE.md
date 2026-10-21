# 阶段 6 验收状态：远程访问改造

日期：2026-10-21
基线：`930f279` / `v1.0.0-rc.1`
状态：**6A 完成；6B 仅设计；6C 条件阻塞；6D 未开始。未开放任何公网入口。**

---

## 一、阶段状态总表

| 阶段 | 状态 | 证据 |
| --- | --- | --- |
| 6A 只读审计 | ✅ 完成 | `docs/PHASE6A_REMOTE_ACCESS_AUDIT.md` |
| 6B 邀请制身份 | 📝 设计完成，**未实现** | `docs/PHASE6B_INVITATION_ACCESS_DESIGN.md` |
| 6C Cloudflare Tunnel | ⛔ 条件不满足，未执行 | `docs/PHASE6C_TUNNEL_DEPLOYMENT_PLAN.md` |
| 6D HTTPS/Release 验收 | ❌ 未开始 | 无域名/证书/Tunnel |
| 本地 RC 功能 | ✅ 已完成（阶段五/发布准备） | 110 backend / 30 frontend；真机闭环 |

---

## 二、6A 审计结论（摘要）

- 当前认证只有可选共享口令；无用户、邀请、会话、密码哈希、资源授权。
- `ACCESS_TOKEN` 为空时默认无认证；当前 `/api/v1/auth` 返回 `required=false`。
- 所有业务数据是全局单库；`subjects`/`practice_sessions`/任务均无 owner/user 字段。
- 持有共享口令即可读写全部学科/资料/知识点/题目/练习、改 AI Key、取消任何任务。
- `/docs`、`/openapi.json` 即使启用口令也公开。
- 上传文件不在静态目录；没有原始文件下载路由；这是正面项。
- Release APK 禁止明文 HTTP；只接受 HTTPS。
- 备份包含明文 `ai_config.json`（AI Key），备份目录未加密。

**结论：当前版本不能直接通过 Tunnel 提供给邀请用户。**

---

## 三、6B 设计结论（未实施）

拟采用：

- `users` + `sessions` + `invitations` + `subject_grants`；
- Owner 通过本地脚本初始化，不开放公网 setup；
- 邀请为一次性 token（哈希存储、7 天、单次）；
- Argon2id 密码哈希、登录限流/锁定、会话过期/撤销/轮换；
- 资源权限通过 subject 所有权/共享继承到章节、资料、知识点、题目；
- 练习记录归实际用户，默认 Owner 也不能读他人练习；
- AI 配置/出题默认仅 Owner；
- 迁移 `subjects.owner_id` / `practice_sessions.user_id` / 任务 `created_by`；
- 真实数据回填前必须单独审批，含 dry-run 与回滚。

**未写一行 6B 代码，未改真实数据。**

---

## 四、6C 条件检查

| 条件 | 状态 |
| --- | --- |
| Cloudflare 账户 | 未确认/未提供 |
| 自有域名 + NS 接入 | 未提供/未确认 |
| cloudflared | **未安装** |
| 当前监听 | `0.0.0.0:8000`（LAN 模式，Tunnel 前必须改 loopback） |
| 当前认证 | 共享口令，且当前 `required=false` |
| 公网入站端口 | 未开放（保持） |
| Windows 休眠/自启 | 未确认 |
| HTTPS 实际验证 | 未执行 |

**没有创建 Tunnel、DNS、证书或公网 URL；没有伪造地址。**

---

## 五、6D 验收（未执行）

以下项目全部标记 **未完成**，因为没有真实域名/HTTPS 服务：

- HTTPS API 连接与证书校验
- 登录/退出/会话失效（6B 未实现）
- 签名 Release 的远程上传/解析/AI/练习
- 电脑与手机跨网络一致性
- 断网恢复与 Windows 重启恢复
- 用户 A/B 权限隔离
- 远程备份恢复

已有本地证据（阶段五/发布准备）：

- 后端 **110 passed**，前端 **30 passed**，TypeScript/ESLint/构建通过；
- Debug 真机完成文件选择器上传→解析→知识点审核→AI 出题→题目审核→练习 100 分；
- 签名 RC1 安装、同签名原地升级（versionCode 2→3，firstInstallTime 不变）通过；
- 隔离库备份/恢复通过。

---

## 六、当前是否可以远程邀请用户

**不可以。**

原因：

1. 没有用户身份和资源授权（6B 未实现）；
2. 没有 HTTPS 域名/隧道（6C 未执行）；
3. 当前认证关闭，服务监听 `0.0.0.0:8000`；
4. 签名 Release 只接受 HTTPS，当前没有可用 HTTPS 地址。

如果现在直接开 Tunnel，会把“无认证的全局数据库”暴露到公网，属于严重安全事故。

---

## 七、需要你确认才能继续

1. Cloudflare 账户/域名是否已有？域名是什么？
2. 6B 默认权限：Invited User 只读+练习，还是允许上传/出题/审核？
3. Owner 是否允许查看他人的练习记录？（建议不允许）
4. 邀请方式：一次性复制链接（无邮件服务）是否可以？
5. 是否接受 Windows 关机即服务不可用？
6. 是否授权安装 cloudflared、设置 Windows 服务/自启/关闭休眠？
7. 6B 涉及真实数据归属回填，是否批准在备份后执行？

---

## 八、建议的下一步顺序

1. 你确认 6B 产品决策；
2. 在隔离库实现 6B（模型/迁移/认证/授权/测试），不改真实数据；
3. 先在 loopback + 本地反向代理做 HTTPS 模拟测试；
4. 条件满足后执行 6C（Tunnel），再用签名 Release 做 6D；
5. 6D 全部通过后才讨论正式 V1.0 发布。
