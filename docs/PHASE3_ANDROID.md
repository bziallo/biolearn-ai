# BioLearn AI 阶段三验收报告（Android APK / 移动端 / 数据同步）

日期：2026-10-21
基线提交：`4de4dd6`（阶段二）→ 本轮分阶段提交
结论：**APK 已实际构建成功并在实体手机（PA2553，`401F8S00Y90000H`）上安装失败于系统授权弹窗，需你在手机上点“允许”。**
除“手机端安装后运行 + 双端同步”外，其余项目均已实测。

---

## 一、先纠正一处描述

你的任务说明写的是 “React + TypeScript + Vite + **Tailwind CSS + shadcn/ui**”，实际项目：
**React 19 + TypeScript + Vite 8 + 手写 CSS（`frontend/src/styles.css`）**，没有 Tailwind，也没有 shadcn/ui。
本轮移动端适配按现有手写 CSS 增量完成，没有引入新 UI 框架（也就没有重写组件）。

---

## 二、分阶段完成情况

### 阶段一：统一 API Base URL 配置（已完成）

新增 `frontend/src/lib/api/connection.ts`，解析顺序：

1. **运行时**：用户在“连接设置”填写的地址（`localStorage: biolearn.api_base_url`）；
2. **构建时**：`VITE_API_BASE_URL` / `VITE_DEFAULT_API_BASE_URL`；
3. **同源**：浏览器由 FastAPI 托管时用 `location.origin + /api/v1`；
4. **Android 且未配置**：返回空，界面提示“尚未连接服务器”，**绝不回退到手机 localhost**。

四种环境对照：

| 环境 | API Base | 说明 |
| --- | --- | --- |
| 浏览器开发（Vite 5173） | `.env` 的 `VITE_API_BASE_URL`（当前 `http://127.0.0.1:8000/api/v1`） | `.env.example` 留空时同源 |
| 桌面生产（start.bat，单端口 8000） | 留空 → 同源 `/api/v1` | 不触发跨域 |
| Android 局域网测试 | 运行时填 `http://<电脑IP>:8000/api/v1` | 不会用 localhost |
| 未来远程部署 | 运行时填 `https://<域名>/api/v1` | 需 HTTPS + 访问口令 |

关于“`.env` 指向 `localhost:3000`”的疑问：**本仓库现在没有 3000 端口配置**。若某个旧副本如此，
那是 Vite 早期模板遗留；与后端 8000 不一致会导致开发页所有请求失败——这正是本轮把地址收敛到
“一处解析 + 运行时可改”的原因。

### 阶段二：CORS、局域网监听与安全（已完成，默认仍只监听本机）

- 新增配置：`ACCESS_TOKEN`（共享口令）、`ALLOW_LAN`（默认 false）、`CORS_EXTRA_ORIGINS`。
- CORS 现在放行：`https://localhost` / `capacitor://localhost`（APK 来源）、`http://localhost|127.0.0.1:任意端口`、
  以及 `CORS_ORIGINS` + `CORS_EXTRA_ORIGINS` 中显式列出的来源。**不放开任意来源。**
- 新增 `AccessTokenMiddleware`（`backend/app/core/security.py`）：
  - 未设置 `ACCESS_TOKEN` → 保持历史行为（不启用）；
  - 设置后，除 `/api/v1/health`、`/api/v1/auth`、静态资源与 OPTIONS 预检外全部要求
    `Authorization: Bearer <token>` 或 `X-BioLearn-Token`，比较用 `hmac.compare_digest`；
  - 401 返回 `auth_required`，前端提示“需要访问口令，请到连接设置填写”。
- 新增 `GET /api/v1/auth` 公开状态接口（只返回 `required/authenticated`，不回显口令）。
- 启动脚本：`scripts/run_backend.py --lan` 显式监听 `0.0.0.0`，并打印手机应填写的地址；
  未加 `--lan` 仍监听 `127.0.0.1`。新增 `start-lan.bat`（带醒目警告）。
- **没有**提供任何把 SQLite 暴露到网络的方案；数据只经 FastAPI 访问。

### 阶段三：移动端 UI 适配（已完成，桌面布局未改动）

- 新增底部导航 `.tab-bar`（≤760px 显示，6 个入口：首页/学科/导入/练习/题库/连接）。
- 安全区：`env(safe-area-inset-*)` 处理刘海、状态栏、底部手势条。
- 触控：按钮/输入/选项/树行最小 44px；输入框 16px 防止聚焦放大。
- 键盘遮挡：`.form-actions`、`.import-actions` 在窄屏改为 sticky 贴底；弹窗内容区独立滚动。
- 窄屏：`review-grid`/`question-generator-grid`/`practice-grid`/`import-grid` 改单列；
  宽表格与树在容器内横向滚动，不撑破页面。
- 横屏手机（高度 ≤480px）仍保留底部导航并压缩主区域边距。
- 桌面端：>760px 时底部导航 `display:none`，原顶部导航与布局完全不变。

### 阶段四：回归测试（已完成）

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 后端全量 | `pytest`（backend/，隔离临时库） | **86 passed**（新增 6 项访问口令/ CORS 测试） |
| 前端类型 | `tsc --noEmit` | 通过 |
| 前端 Lint | `eslint .`（已忽略 android/ 生成物） | 通过 |
| 前端单测 | `vitest run` | **12 文件 / 26 passed** |
| 前端构建 | `vite build` | 通过 |
| Android 构建 | `gradlew.bat assembleDebug` | **BUILD SUCCESSFUL** |

### 阶段五：设备与同步验证（部分完成，见下方“未通过/未验证”）

已完成：
- 后端以 `--lan` 启动，监听 `0.0.0.0:8000`；本机 `127.0.0.1` 与局域网 `10.61.232.199` 的
  `/api/v1/health` 均返回 200（实测）。
- APK 已签名并通过 `apksigner verify`；包内容审计无密钥、无数据库。

未完成（需你在手机上操作）：
- `adb install` 返回 `INSTALL_FAILED_ABORTED: User rejected permissions` —— 手机上出现了安装确认弹窗
  被取消（或系统安全设置拦截）。**这不是构建失败**，需要你在手机上点“允许安装”。

### 阶段六：本报告

---

## 三、APK 真实路径与构建命令

```
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

构建（Windows，已在本机实测）：

```powershell
$env:JAVA_HOME = "C:\Users\bzlciallo\android-toolchain\jdk-21.0.12.1+1"   # 必须 JDK 21，JDK 17 会报“无效的源发行版：21”
$env:ANDROID_HOME = "C:\Users\bzlciallo\android-toolchain\android-sdk"
cd frontend
pnpm build
pnpm exec cap sync android
cd android
gradlew.bat assembleDebug
```

`frontend/android/local.properties` 里的 `sdk.dir` 是本机路径，**已被 .gitignore 排除，必须本机生成**。
也可以通过 `pnpm android:apk`（新增脚本）一条命令完成 build → cap sync → assembleDebug。

已安装工具链：Temurin JDK 17 与 21、Android cmdline-tools、platform-tools、`platforms;android-35`、
`build-tools;35.0.0`、Gradle 8.11.1（手动放入 wrapper 缓存，因为自动下载被网络中断）。

---

## 四、局域网 / 跨网配置

### 场景 A：局域网（手机与电脑同一 Wi-Fi）

1. 电脑 `.env` 设置随机口令：
   ```
   ACCESS_TOKEN=<你生成的随机字符串>
   CORS_EXTRA_ORIGINS=[]
   ```
2. 双击 `start-lan.bat`（或 `python scripts/run_backend.py --lan --port 8000`）。
   启动日志会打印 `手机请填写：http://10.61.232.199:8000/api/v1`。
3. **Windows 防火墙**需放行 8000 入站（本轮未自动修改防火墙，建议只对专用网络放行：
   `netsh advfirewall firewall add rule name="BioLearn LAN" dir=in action=allow protocol=TCP localport=8000 profile=private`，
   需要管理员权限；是否执行请你自己决定）。
4. 手机安装 APK → 打开 App → “连接设置”填 `http://<电脑IP>:8000/api/v1` + 口令 → 保存并测试。

### 场景 B：跨网络（正式远程）

- 需要把后端部署到长期在线的服务器（或反向代理），**必须 HTTPS**，且**必须设置 `ACCESS_TOKEN`**；
  `SERVE_FRONTEND` 可保持 true 由后端托管前端，也可前置 Nginx。
- 不要把 `biolearn.db` 或上传目录暴露到公网；备份与迁移参考 `docs/RELEASE_NOTES_V1.0.md`。
- 本仓库没有提供云部署脚本，也没有实测远程访问——**未验证**。

---

## 五、数据同步架构

```
Android APK (WebView)  ─┐
                        ├─ HTTPS/HTTP + 可选 Bearer 口令 → FastAPI → SQLite(唯一权威) + uploads/
桌面浏览器 / start.bat ─┘
```

- 手机与电脑是**同一后端的两个客户端**，不存在“APK 自带数据库”。
- 所有写操作经 API 落库；另一端刷新即看到最新数据（在线同步）。
- 无离线编辑、无冲突合并（V1.1 规划）。
- 认证：单一共享口令，不做多用户隔离；口令只存在本机 `localStorage` 与服务端 `.env`。

---

## 六、测试数据与真实数据

- 本轮未创建任何业务测试数据；未重置、未迁移真实库（`backend/data/biolearn.db` 仍为阶段二结束时的状态）。
- 访问口令测试全部使用 pytest 隔离临时库（`tests/test_access_token.py`）。

---

## 七、未完成 / 未验证（必须如实标注）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| APK 安装到手机 | ❌ 未通过 | `adb install` 被手机端授权弹窗拒绝，需人工允许 |
| APK 启动与页面渲染 | ❌ 未验证 | 依赖上一项 |
| 手机 → 电脑后端连接 | ⚠️ 部分验证 | 电脑侧局域网地址可达（本机用 10.61.232.199 实测 200），手机侧未测 |
| 双端数据同步（手机改→电脑读） | ❌ 未验证 | 依赖安装与连接 |
| 远程 HTTPS 部署 | ❌ 未实现/未验证 | 仅文档方案 |
| Windows 防火墙放行 | ❌ 未执行 | 需管理员权限，等你确认 |
| 离线同步/冲突合并 | ❌ 未实现 | V1.1 |

---

## 八、下一步（需要你决定 / 操作）

1. 在手机上点“允许安装”（或先在开发者选项里关闭“外部来源安装验证”再重试），然后告诉我，我用
   `adb` 安装并抓取 logcat 验证启动与连接。
2. 是否要我执行防火墙放行命令（仅专用网络、仅 8000 端口）？
3. 是否需要我把 `ACCESS_TOKEN` 生成并写入你本机 `.env`（我不会提交它）？
