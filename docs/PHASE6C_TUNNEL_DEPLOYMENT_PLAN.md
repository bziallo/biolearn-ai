# 阶段 6C：Cloudflare Tunnel 部署计划

状态：**条件检查未通过，未执行任何 DNS/Tunnel/公网配置。**
没有创建 URL、没有注册域名、没有安装 cloudflared、没有开放端口。

---

## 一、部署前条件检查

| 条件 | 实际状态 | 结论 |
| --- | --- | --- |
| Cloudflare 账户 | 未提供/未确认 | 阻塞 |
| 自有域名 | 未提供 | 阻塞 |
| 域名 NS 已接入 Cloudflare | 未确认 | 阻塞 |
| cloudflared | **未安装** | 阻塞 |
| Windows 能稳定访问 Cloudflare 出站 | 未验证 | 待验证 |
| 当前服务监听 | `0.0.0.0:8000`（LAN 模式） | **必须先改为 `127.0.0.1:8000`** |
| Windows 防火墙 | 未检查/未改 | 保持不放行入站 8000 |
| Windows 休眠/重启 | 未确认 | 需关闭休眠并设置自启 |
| 应用认证 | 共享口令，当前 `required=false` | **6B 未完成前不得上线** |
| 公网端口 | 未开放 | 保持关闭 |
| 数据库/上传目录 | 仅本机，不在静态目录 | 保持 |

**当前不具备部署条件。** 本文件只提供可执行计划，不能作为“已上线”证据。

---

## 二、目标架构

```
浏览器 / 签名 Android Release
        │  HTTPS (443, Cloudflare 边缘证书)
        ▼
Cloudflare（DNS + 可选 Access）
        ▲  出站 Tunnel（cloudflared 主动连接，无入站端口）
        │
Windows 主机
  cloudflared.exe（Windows 服务）
        │ http://127.0.0.1:8000
        ▼
FastAPI（只监听 loopback）
  ├─ /api/v1/*
  ├─ /assets/* + SPA
  └─ backend/data/{biolearn.db,uploads/}
```

- 不开放路由器 80/443/8000 入站。
- 公网只经过 Cloudflare；源站端口只对本机开放。
- Tunnel 只转发一个主机名到 loopback；未匹配 hostname 返回 404。
- Cloudflare Access **不默认套在所有 API**；先由 BioLearn 自身登录（6B）处理业务身份。
  Access 只用于 `/docs`、运维入口或额外防线，需单独验证 Android/浏览器兼容性。

---

## 三、前置改造（必须先完成）

1. 6B 邀请制身份/授权已实现并通过隔离测试。
2. FastAPI 只监听 `127.0.0.1:8000`：
   - 不使用 `start-lan.bat`；
   - 使用 `python scripts/run_backend.py --port 8000`（默认 loopback）；
   - 防火墙不为 8000 开放入站。
3. 生产配置：
   - `ACCESS_TOKEN` 不再作为身份（6B 切换后禁用）；
   - `CORS_EXTRA_ORIGINS=["https://<主机名>"]`（仅域名，不使用 `*`）；
   - 关闭 `/docs`、`/redoc`、`/openapi.json` 或仅允许 Owner/内网；
   - `SERVE_FRONTEND=true`，域名同源。
4. 6B 的登录页/邀请页必须能通过 HTTPS 域名访问；Android Release 只接受 HTTPS。
5. 备份/恢复脚本在 Windows 服务账户下可执行，备份目录权限受限。

---

## 四、条件满足后的执行步骤（需你确认后执行）

### 1. 安装 cloudflared

```powershell
winget install --id Cloudflare.cloudflared -e
cloudflared --version
```

（或用 Cloudflare 官方 MSI；记录版本，不使用来路不明二进制。）

### 2. 登录/创建命名 Tunnel

```powershell
cloudflared tunnel login
cloudflared tunnel create biolearn-prod
```

凭证默认在 `%USERPROFILE%\.cloudflared\<UUID>.json`：

- 不放入 Git；
- 限制为当前 Windows 用户可读；
- 备份到加密介质；
- 泄露时立即 `cloudflared tunnel token rotate`/重建 Tunnel。

### 3. 配置（示例，`<...>` 为占位符，不是真实地址）

`%USERPROFILE%\.cloudflared\config.yml`：

```yaml
tunnel: <TUNNEL_UUID>
credentials-file: C:\Users\<user>\.cloudflared\<TUNNEL_UUID>.json

ingress:
  - hostname: biolearn.<your-domain>
    service: http://127.0.0.1:8000
  - service: http_status:404
```

要求：

- 只允许一个明确 hostname；
- 不配置 `*` 通配；
- 不直接暴露 `backend/data` 或管理端口；
- `http_status:404` 兜底，未匹配 hostname 安全失败。

### 4. DNS 路由

```powershell
cloudflared tunnel route dns biolearn-prod biolearn.<your-domain>
```

- 创建 CNAME 到 `<UUID>.cfargotunnel.com`；
- 不手动添加 A 记录指向家庭 IP；
- 不修改根域名 NS 之外的其它记录；
- 执行前记录当前 DNS 快照，便于回滚。

### 5. Windows 服务/自启

```powershell
cloudflared service install
```

或使用 NSSM 包装；设置：

- 开机自启；
- 失败自动重启；
- 依赖网络可用；
- 电源计划关闭睡眠/休眠（`powercfg /change standby-timeout-ac 0` 等需管理员）；
- Windows Update 重启后自动恢复。

### 6. 启动顺序

1. 启动 BioLearn 后端（loopback）；
2. 确认 `/api/v1/health` 本机 200；
3. 启动 cloudflared 服务；
4. `cloudflared tunnel info biolearn-prod` 查看连接；
5. 外部 HTTPS 验证。

### 7. 验证清单（必须实际执行）

| 检查 | 方法 | 通过标准 |
| --- | --- | --- |
| Tunnel 状态 | `cloudflared tunnel info` | 至少一个连接器 healthy |
| DNS | `Resolve-DnsName biolearn.<domain>` | CNAME 指向 cfargotunnel |
| 证书 | 浏览器/`curl -v https://...` | 公共 CA 有效、TLS 1.2+ |
| 健康检查 | `GET https://<domain>/api/v1/health` | 200，最小信息 |
| 匿名业务 | `GET https://<domain>/api/v1/subjects` | 401（6B 后） |
| 登录 | 浏览器/签名 APK | 成功，Cookie/令牌正确 |
| 上传 | 签名 APK | 文件落盘、解析、权限正确 |
| AI/练习 | 签名 APK | 完整闭环 |
| 未匹配 host | 另一个 hostname | 404，不落到应用 |
| 关闭主机 | 关机后访问 | 连接失败（预期） |
| 重启恢复 | 重启 Windows | 服务/Tunnel 自动恢复 |

**Tunnel healthy ≠ 业务验收通过。** 必须完成应用登录、权限、上传、AI、练习、备份测试。

---

## 五、Cloudflare Access 的职责边界

- 可选的运维层：只保护 `/docs`、`/openapi.json`、管理入口；
- 不作为所有 API 的默认前置交互式登录，除非已验证：
  - Android WebView 能完成 IdP 登录/回调；
  - 会话在重启后仍可用；
  - API 的非浏览器客户端能携带正确凭证；
- 不使用静态 Service Token 打包进 APK；
- 业务身份仍由 BioLearn 6B 负责；Access 仅额外防线。

---

## 六、安全风险

| 风险 | 说明 | 缓解 |
| --- | --- | --- |
| 家庭主机可用性 | 关机/断网/休眠即不可用 | 明确 SLA；电源设置；监控 |
| 源站被绕过 | 若路由器仍开放 8000 | 关闭入站；只监听 loopback；防火墙 |
| Tunnel token 泄露 | 可接管隧道 | 文件 ACL、加密备份、轮换、最小权限 |
| Cloudflare 账户接管 | 可改 DNS/Access | MFA、最小 API Token、审计 |
| 共享口令/弱认证 | 6B 前全库暴露 | 6B 完成前不上线 |
| DNS 配置错误 | 暴露错误服务/404 | 单 hostname、快照、验证、回滚 |
| Windows 日志含敏感信息 | 请求头/上传名 | 脱敏、限制日志读取 |
| 证书/域名过期 | 服务不可用 | Cloudflare 托管证书 + 到期监控 |
| 备份泄露 | 含 AI Key/全部数据 | 加密、ACL、异地、离线 |

---

## 七、回滚

1. `cloudflared tunnel cleanup` / 停止并卸载服务；
2. 删除 CNAME（按执行前快照恢复 DNS）；
3. `cloudflared tunnel delete biolearn-prod`（确认不再需要凭证）；
4. 撤销 Cloudflare API Token/Access 应用；
5. 关闭 Windows 防火墙临时规则（如有）；
6. 应用回退到 `v1.0.0-rc.1`/上一个提交；数据库按备份恢复；
7. 保留本地 loopback 使用，不依赖公网。

---

## 八、需要你提供/确认

1. 是否已有 Cloudflare 账户？
2. 域名是什么？是否已把 NS 接入 Cloudflare 并处于 Active？
3. 是否接受“Windows 关机=服务不可用”的可用性？
4. 是否允许安装 cloudflared Windows 服务、设置开机自启和关闭睡眠？
5. 6B 默认权限：Invited User 只读+练习，还是允许写/出题？
6. 邀请方式：复制一次性链接（无需邮件）是否可接受？

在以上确认前，**不执行** `cloudflared login/create/service install`、DNS 修改或任何公网开放操作。

---

## 九、2026-10-21 决策回写：当前无法部署

用户已确认：

- 尚无 Cloudflare 账户；
- 域名/DNS 之后确认；
- **不接受电脑关机/断网时服务不可用**；
- **暂不允许安装 cloudflared、不允许开机自启**；
- 数据迁移仅做隔离库演练。

因此本计划的 6C 不能执行：

1. 没有账户/域名，无法创建 Tunnel、DNS、证书；
2. 不允许安装 cloudflared，无法建立出站 Tunnel；
3. 最关键的可用性要求与“Windows 电脑作为唯一主机”冲突——任何家用 Windows
   在关机、休眠、断网、系统更新时都会不可用；
4. 在 6B 未迁移真实库、未完成 HTTPS 验收前，也不能对外提供登录服务。

### 要满足“关机/断网仍可用”需要的新前提

必须选择以下之一，并单独确认：

- 一台**始终在线的独立主机**（云服务器/托管主机/常开 NAS），运行 FastAPI；
- 或把服务部署到托管平台，Cloudflare 只做 DNS/TLS/访问层；
- 或接受“家用 Windows 可用性有限”，但这与当前决策 3 冲突。

在这些前提满足前：

- 不注册域名、不修改 DNS、不安装 cloudflared、不创建公网路由；
- 不发布正式版；
- 本地/隔离库的 6B 验收仍可继续。
