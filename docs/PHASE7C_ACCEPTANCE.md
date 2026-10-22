# 阶段 7C 验收记录：私有文件与 TXT/MD 离线处理

日期：2026-10-22
代码提交：`77ebb3b`
验收状态：**自动化、Android Debug 构建、真机文件选择/复制/重启/飞行模式验证通过；上传执行未实现。**

---

## 一、测试命令与结果

### 后端

```powershell
cd backend
.venv/Scripts/python.exe -m pytest -q
```

结果：**117 passed**。

### 前端

```powershell
cd frontend
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js .
node node_modules/vitest/vitest.mjs run
node node_modules/vite/bin/vite.js build
```

| 项 | 结果 |
| --- | --- |
| TypeScript | 通过 |
| ESLint | 通过 |
| Vitest | **59 passed / 20 files** |
| 生产构建 | 通过 |
| 7C 本地测试 | 24 passed / 6 files |

7C 覆盖：

- v2→v3 成功迁移、重复迁移、v3 失败回滚；
- 外键、唯一约束、状态机；
- 文件复制临时路径、大小校验、rename、SHA；
- 空/超大/不支持类型/路径穿越/复制失败清理；
- UTF-8 BOM、CRLF、GB18030、Markdown、长文本、空文件；
- 浏览器能力降级；
- 默认 FastAPI 与关闭开关回归。

### Android Debug

```powershell
cd frontend
node node_modules/vite/bin/vite.js build --mode android
node node_modules/@capacitor/cli/bin/capacitor sync android
cd android
$env:JAVA_HOME="C:\Users\bzlciallo\android-toolchain\jdk-21.0.12.1+1"
./gradlew.bat --no-daemon assembleDebug
```

结果：`BUILD SUCCESSFUL`。

APK：`frontend/android/app/build/outputs/apk/debug/app-debug.apk`
大小：**27,749,064 字节**
SHA-256：`601976a90ab729f71e86669f108e019263f7a7a77dcc8921a30565a6f35dc83a`

---

## 二、真机验收（PA2553 / Android 16）

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 安装 Debug APK | ✅ Success | `adb install -r` |
| v2→v3 迁移 | ✅ schema 3，原 7B 数据保留 | `phase7c-v3.png` |
| 外键 | ✅ ON | 页面 |
| 系统文件选择器 | ✅ 选择 `phase7c-note.md` | 真机 |
| 复制到私有目录 | ✅ 109 B | `phase7c-parsed.png` |
| SHA-256 | ✅ `155d63b6a14224058184758964e71d14559b401632a182972b62cc6f351e9e74` | 页面 + `run-as sha256sum` |
| 本地解析 | ✅ 1 片段、48 字符、utf-8 | `phase7c-parsed.png` |
| Markdown 标题 | ✅ `阶段7C 离线笔记`、`蛋白质`、`酶` | 预览 |
| 进程重启 | ✅ 文件记录/任务仍在 | `phase7c-restart.png` |
| 飞行模式读取 | ✅ 重新读取并解析 | `phase7c-airplane-preview.png` |
| 私有文件权限 | ✅ `-rw-------` | `run-as ls -l` |
| 待上传队列 | ✅ 1 条 `queued`，attempts 0 | `phase7c-jobs.png` |
| 未标记上传成功 | ✅ 没有 `uploaded` | 页面 |
| 关闭开关 | ✅ 学科页仍 FastAPI/远程缓存 | `phase7c-fastapi-off.png` |

### 命令证据

```text
$ adb shell run-as ai.biolearn.app ls -l files/biolearn/files
-rw------- 1 u0_a265 u0_a265 109 ... 25299aa0-f9d6-486f-9d35-692e8fb85f5d.md

$ adb shell run-as ai.biolearn.app sha256sum files/biolearn/files/25299aa0-...md
155d63b6a14224058184758964e71d14559b401632a182972b62cc6f351e9e74
```

页面显示的 SHA-256 与命令输出一致。

---

## 三、未验证/未完成

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 实际 HTTP 上传 | ❌ 未实现 | 服务端无幂等键；7C 只排队 |
| 上传成功/失败/超时状态 | ❌ 未执行 | 状态机已定义，网络路径未接 |
| 自动重试/退避 | ❌ 未实现 | 7D |
| 真机 GB18030 | ❌ 未单独验证 | 自动化覆盖 |
| 真机超大/空文件拒绝 | ❌ 未单独验证 | 自动化覆盖 |
| 真机磁盘写满/复制中杀进程 | ❌ 未验证 | 代码有 .part/清理保护；未做破坏性测试 |
| 原生 v3 迁移失败回滚 | ❌ 未注入验证 | 自动化 sql.js 覆盖 |
| SQLCipher | ❌ 未启用 | 私有目录 0600，未加密 |
| `allowBackup` | ❌ 未修改 | 仍为 true，风险已记录 |
| 浏览器本地文件 | ❌ 不支持 | 明确降级提示 |
| 双向同步/删除同步 | ❌ 未实现 | 7E |

---

## 四、安全核对

| 项 | 结果 |
| --- | --- |
| 真实库 | `0009_question_bank`，无写入 |
| 真实资料导入 | 无；仅合成 TXT/MD |
| 原文件删除 | 无 |
| 公共媒体目录 | 未使用 |
| 文件路径 | 只有受控相对路径 |
| 日志正文/token | 未输出 |
| API Key | 未加入客户端 |
| `v1.0.0-rc.1` | 仍 `930f279` |
| 签名/包名/HTTPS | 未修改 |
| Tunnel/DNS/端口 | 未操作 |

---

## 五、功能回滚

1. `/settings/local-db` 关闭本地数据库；
2. 或设置 `VITE_MOBILE_LOCAL_DB=false` 重新构建；
3. 现有课程/资料/上传继续 FastAPI；
4. 文件保留在私有目录，但不被 UI 使用；
5. 不删除数据库、不删除原文件；
6. 不修改服务端 Alembic 或真实库。

---

## 六、Git

- 7C 代码提交：`77ebb3b`
- 基线：`74796ba`（7B 文档）
- 文档提交：7C 文档提交（HEAD）
- 工作区：提交后干净

---

## 七、结论

7C 已实现并验证：

- Android 系统文件选择 → App 私有目录复制；
- 临时文件 + rename + 大小/SHA 校验；
- schema v3 事务迁移；
- TXT/MD 本地编码/换行/Markdown 解析与稳定分段；
- 进程重启和飞行模式仍可读取；
- 待上传任务持久化、状态展示、重复任务唯一约束；
- 关闭开关回到 FastAPI。

但**没有执行真实上传**，`allowBackup` 与加密风险未解决，不能宣称端到端上传幂等或完整离线资料库。
