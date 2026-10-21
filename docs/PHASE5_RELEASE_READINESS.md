# V1.0 发布准备：封版、Release 签名与部署前检查

日期：2026-10-21
基线：`379aa64`（阶段五最终提交）
结论：**签名、安装与升级已验证；但由于没有 HTTPS 服务器/证书，签名 Release APK 在当前局域网 HTTP 环境下无法连接后端。**
因此：**内部测试可用 Debug APK；不得作为公开 V1.0 发布，需先完成 HTTPS 部署与 Release 联网验证。**

---

## 一、Release Candidate 的真实提交与标签

- 起始工作区：干净，`379aa64`。
- 本轮提交：签名配置、发布文档与部署方案（见文末 `git log`）。
- 标签：`v1.0.0-rc.1`（指向本轮封版提交；已有 `v1.0.0` 是历史阶段标签，未移动、未覆盖）。
- 未提交 `.env`、API Key、共享口令、真实数据库、上传文件、keystore、`keystore.properties`。

真实库在全部复测前后保持：学科 10、章节 6、资料 2、知识点 78、题目 7、练习 3、作答 6。

---

## 二、测试结果（重新执行）

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 后端全量 | `pytest`（backend/） | **110 passed** |
| 前端类型 | `tsc --noEmit` | 通过 |
| 前端 Lint | `eslint .` | 通过 |
| 前端单测 | `vitest run` | **13 文件 / 30 passed** |
| 前端构建 | `vite build` | 通过 |
| Android debug | `gradlew assembleDebug` | 通过 |
| Android release | `gradlew assembleRelease` | 通过（已签名） |

---

## 三、Release 签名状态与 APK 校验

### 签名方案

- 密钥文件：`frontend/android/keystore/biolearn-release.jks`（**gitignored**）。
- 本地配置：`frontend/android/keystore.properties`（**gitignored**，含随机口令；
  口令未打印、未写入源码或 Gradle 文件）。
- `app/build.gradle` 只从环境变量或该本地文件读取：
  `BIOLEARN_KEYSTORE`、`BIOLEARN_STORE_PASSWORD`、`BIOLEARN_KEY_ALIAS`、
  `BIOLEARN_KEY_PASSWORD`；不存在签名材料时 `assembleRelease` 仍产出未签名包，
  Debug 流程不受影响。
- 版本号通过 `BIOLEARN_VERSION_CODE` / `BIOLEARN_VERSION_NAME` 注入，
  避免把 RC 版本硬编码进源码。

> **必须离线备份 `biolearn-release.jks` 与 `keystore.properties`。** 丢失后无法对已发布
> APK 做同签名升级。不要提交、不要发群、不要放进网盘公开链接。

### 签名产物

```
outputs/release/BioLearnAI-1.0.0-rc.1-signed.apk
大小：3,296,782 字节
SHA-256：16b1f9215791590f6ecc649422be388ddb08ba3f9086984fc0cb35ec78626741
包名：ai.biolearn.app
versionCode：2
versionName：1.0.0-rc.1
minSdk：23
targetSdk：35
compileSdk：35
权限：仅 INTERNET（+ Android 内部 DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION）
签名证书 DN：CN=BioLearn AI, OU=Release, O=BioLearn, L=Local, ST=Local, C=CN
证书 SHA-256：9544ac6ceb1318bc1b19587403e4cf9640821caae371550c28496697ae7086ab
签名验证：apksigner verify 通过
```

正式构建/校验命令（PowerShell）：

```powershell
$env:JAVA_HOME = "C:\Users\bzlciallo\android-toolchain\jdk-21.0.12.1+1"
$env:ANDROID_HOME = "C:\Users\bzlciallo\android-toolchain\android-sdk"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
$env:BIOLEARN_VERSION_CODE = "2"
$env:BIOLEARN_VERSION_NAME = "1.0.0-rc.1"

cd frontend\android
.\gradlew.bat assembleRelease --no-daemon
.\gradlew.bat assembleDebug --no-daemon     # 保留 Debug 流程

cd ..\..
& "$env:ANDROID_HOME\build-tools\35.0.0\apksigner.bat" verify --print-certs `
  frontend\android\app\build\outputs\apk\release\app-release.apk
Get-FileHash frontend\android\app\build\outputs\apk\release\app-release.apk -Algorithm SHA256
```

### 安装与升级

| 验证 | 结果 |
| --- | --- |
| 签名 APK 全新安装（先卸载 debug） | Success，`versionCode=2`、`versionName=1.0.0-rc.1` |
| 同签名升级包（versionCode 3）`adb install -r` | Success，`versionCode=3` |
| 升级前后 `firstInstallTime` | 同为 `2026-10-21 19:46:12`（原地升级，非重装） |
| 升级后 `lastUpdateTime` | 变为 `19:47:42` |
| 升级后应用数据保留 | 设备级安装记录保持；后端数据未受安装/升级影响 |

> 升级测试包 versionCode 3 仅用于验证升级路径，不是交付包；交付包为 versionCode 2 的
> `outputs/release/BioLearnAI-1.0.0-rc.1-signed.apk`。

### 重要发现：Release APK 阻止明文 HTTP

签名 Release APK 实测无法连接 `http://10.61.232.199:8000/api/v1`，因为 release manifest
没有 `usesCleartextTraffic`（与 Debug 不同）。这是 **Android 9+ 的安全默认值**，不是网络故障：

- Debug APK：允许局域网 HTTP，用于本地测试。
- Release APK：**只允许 HTTPS**。在尚无 HTTPS 服务的情况下，签名包无法连接当前后端。
- 因此不能把“已安装签名包”误报成“签名包已完成联网验证”。

---

## 四、发布前功能复测（Debug APK，局域网）

签名包无法走 HTTP，以下功能复测使用同一代码的 Debug APK（真机 PA2553 / Android 16）：

| 项目 | 实际结果 |
| --- | --- |
| Android 文件选择器上传 | 通过系统文件选择器选择 `phase6-synthetic.txt`（171 B），页面显示已选文件 |
| 课件解析 | 上传成功，解析完成，归档到 `phase6-synthetic` 章节 |
| AI 知识点生成 | 生成 2 条知识点（主动运输、细胞膜选择透过性） |
| 知识点审核 | 在手机审核页逐条“通过并入库”，2 条均 approved |
| AI 出题 | 手机选择该学科/章节/2 个知识点，单选+判断，生成 2 题 |
| 题目审核 | 手机逐题“通过”，2 题 approved |
| 练习与结果 | 作答 B / 正确，提交后 **得分 100，正确 2/2** |
| 电脑端确认 | 同一 2 题（approved）与同一练习会话（completed 100 分、2 条作答） |
| 双向同步 | 学科由电脑创建、手机使用；手机生成的知识点/题目/练习电脑端可见 |
| 断网错误 | 指向不可达端口显示“连接超时…”，恢复 LAN 地址后“服务在线” |
| 数据清理 | 先 dry-run 再 apply，删除合成学科/资料/章节/知识点/题目/练习/作答/任务及上传文件 |

真实库复测后恢复：学科 10、章节 6、资料 2、知识点 78、题目 7、练习 3、作答 6。

### 备份与恢复（隔离目录复测）

临时库（Alembic `0009`）+ 合成学科/资料/知识点/上传文件：

1. 备份成功；
2. 删除学科与上传文件；
3. 恢复 `--data-dir --force --port 0` 成功；
4. 验证学科 1、知识点 1、上传文件内容恢复、Alembic `0009`、旧数据在 `_restore_previous_*`。

---

## 五、HTTPS 与远程访问方案（设计，未实施）

> 当前没有服务器、域名或证书，因此**远程部署状态为未完成、未验证**；没有使用虚构地址。

### 目标拓扑

```
Android Release APK ─┐
                     ├─ HTTPS (443) → 反向代理（Caddy/Nginx）
桌面浏览器 ──────────┘                     ↓
                                   FastAPI（仅内网/本机监听）
                                     ↓
                         SQLite + uploads（持久化磁盘）
```

### 1. 部署环境与持久化

- 一台长期在线的 Linux 主机（或云主机）；FastAPI 以 systemd 服务运行，只监听
  `127.0.0.1:8000`，由 Caddy/Nginx 反向代理。
- `backend/data/`（SQLite、上传文件、日志）放在持久化磁盘/云盘，定期快照。
- 不建议把 SQLite 放到 NFS；单写者模型下保持本地磁盘。
- 禁止把 8000 端口直接暴露公网，禁止直接下载 `.db` 文件。

### 2. HTTPS 证书与续期

- 域名 A/AAAA 指向服务器；Caddy 自动申请 Let's Encrypt，或 Nginx + certbot。
- 强制 80→443 跳转、HSTS；证书到期前自动续期并监控。
- Android Release 只信任公共 CA；自签名证书需要额外信任配置，不推荐生产使用。

### 3. 认证与授权

- 当前只有**单一共享访问口令**（`ACCESS_TOKEN`），不是多用户账号体系：
  - 知道口令即可读写全部数据；
  - 无法按用户隔离学习记录；
  - 口令泄露只能全量更换。
- 远程最低要求：HTTPS + 长随机口令 + 反向代理限流/失败封禁 + IP 允许列表或 VPN。
- 推荐替代：接入 OAuth2/OIDC 反向代理（Authelia、Authentik、Cloudflare Access）或
  在 V1.1 实现用户表、会话、RBAC 与按用户数据隔离。
- 在完成用户隔离前，不应把服务开放给不受信任的公网用户。

### 4. 数据备份、恢复与访问日志

- 每日定时备份数据库与 uploads；备份加密后存到异地。
- 备份恢复沿用 `backup_data.py` / `restore_data.py`；恢复前停服务。
- 反向代理记录访问日志（脱敏，不记录 Authorization）；应用记录任务失败类别，
  不记录 Key、提示词或原文。
- 建议监控：磁盘、备份新鲜度、5xx、429、登录失败。

### 5. Android Release 的 API 地址

- Release 不写死后端地址；安装在“连接设置”中填写 `https://<域名>/api/v1`。
- 若做受控分发，可在构建时设置 `VITE_DEFAULT_API_BASE_URL=https://...`，但仍允许用户修改。
- Release 只允许 HTTPS；`http://` 局域网地址只适用于 Debug 构建。
- 证书必须由公共 CA 签发，否则 WebView 会拒绝连接。

### 6. 数据库与上传文件保护

- 文件系统权限仅服务账号可读；备份目录加密。
- 上传文件通过 API 鉴权访问，不做静态目录公开暴露。
- 数据库不进 Git、不进 APK、不通过 HTTP 直接下载。

### 7. 远程部署状态

| 项 | 状态 |
| --- | --- |
| 服务器/域名/证书 | ❌ 没有 |
| HTTPS 反向代理 | ❌ 未实施 |
| 远程 Release 联网验证 | ❌ 未验证 |
| 共享口令以外认证 | ❌ 未实现 |
| Android Release 局域网 HTTP | ❌ 被系统安全策略阻止（预期） |

---

## 六、已知限制与风险

1. **签名 Release 当前不能连接局域网 HTTP**；没有 HTTPS 服务 → 签名包无法完成联网功能验证。
   这是发布前最高优先级阻塞项。
2. **没有公开部署**：无域名、证书、服务器；HTTPS 章节只是设计，不是已验证实现。
3. **认证是单口令**：无用户隔离、无审计、无细粒度授权；不适合公开多用户。
4. **Release keystore 只在本地**：`keystore.properties` 含口令，必须离线备份；
   丢失将无法升级已安装包。
5. **AI 语义正确性仍需人工审核**；签名不改变内容质量。
6. **真实 422 网关未验证**；只有错误体回归测试。
7. **手机原生文件选择器已复测**（Debug）；但 Release 因 HTTP 阻断未能复测同一流程。
8. **备份默认不复制 `.env`**；自定义环境变量需手动备份。
9. **SQLite 并发/备份一致性**适合单机；远程多用户前应评估迁移 PostgreSQL。
10. **没有 Play/应用商店签名策略**；当前是本地侧载 APK，不是商店包。

---

## 七、发布结论

| 结论 | 判定 |
| --- | --- |
| 公开 V1.0 发布 | **❌ 阻止**：无 HTTPS、签名 Release 无法联网验证、认证仅单口令 |
| 内部测试（Debug APK，局域网） | **✅ 可用**：功能闭环已完整复测 |
| 签名 Release APK | **⚠️ 仅完成签名/安装/升级验证**，联网功能需 HTTPS 后才可验收 |
| 代码封版 | **✅ 可标记 `v1.0.0-rc.1`**，作为内部 RC 基线 |

下一步必须先完成：HTTPS 部署（域名 + 证书 + 反向代理）→ 用签名 Release 连接
`https://<域名>/api/v1` → 复测文件上传/AI/练习/同步 → 再决定是否发布 V1.0.0。
