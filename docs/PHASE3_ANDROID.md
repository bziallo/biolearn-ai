# 阶段三验收报告：Android APK、移动端适配与数据同步

日期：2026-10-21
基线：`4de4dd6`（阶段二）
结论：**APK 已在实体手机 PA2553（Android 16）上安装并运行；手机通过局域网 `http://10.61.232.199:8000/api/v1` 访问电脑后端，双端数据同步（学科双向、练习记录）已实测通过。**

---

## 一、先说明两处与任务描述不一致的地方

1. 任务书写的是 `React + TypeScript + Vite + Tailwind CSS + shadcn/ui`。实际项目是
   **React 19 + TypeScript + Vite 8 + 手写 CSS**，没有 Tailwind，也没有 shadcn/ui。
   本轮按现有手写 CSS 增量适配，没有引入 UI 框架，也没有重写组件。
2. 任务书怀疑 `.env` 指向 `localhost:3000`。实际仓库 `.env` 为
   `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1`，与后端 8000 一致；`.env.example` 留空（同源）。
   本轮另外发现并修复了一个真实问题：**根 `.env` 的开发地址会被打进 APK**，见第三节。

---

## 二、实际完成项

### 1. 统一 API Base 配置

新增 `frontend/src/lib/api/connection.ts`，解析顺序：

| 优先级 | 来源 | 适用环境 |
| --- | --- | --- |
| 1 | 运行时（`localStorage: biolearn.api_base_url`，连接设置页写入） | 手机、浏览器均可 |
| 2 | 构建时 `VITE_DEFAULT_API_BASE_URL` | 部署构建（可选） |
| 3 | 同源 `location.origin + /api/v1` | 桌面生产（FastAPI 托管 SPA） |
| 4 | 无 | APK 未配置时显示“尚未连接服务器”，**不回退 localhost** |

同时修复了三个真实缺陷：

- **Android 判定过早**：原实现依赖 `androidBridge`/`Capacitor` 注入，模块加载时桥未就绪，
  导致 APK 把 `https://localhost` 当同源并请求 `127.0.0.1:8000`。改为按
  `capacitor:` / `android-app:` / `https://localhost` 直接判定。
- **开发地址被打进 APK**：`VITE_API_BASE_URL` 来自根 `.env`，构建 APK 时会内联。
  现在 Android 只认 `VITE_DEFAULT_API_BASE_URL`，并新增 `.env.android`（清空两者）；
  `pnpm build:android` 使用 `vite build --mode android`。实测 APK 内**不含**
  `127.0.0.1:8000`、`10.61.232.199`。
- **超时提示不明确**：超时现在返回
  “连接超时：<地址> 在 8 秒内没有响应。请确认电脑端后端已启动、手机与电脑在同一 Wi-Fi，并检查局域网监听与防火墙设置。”

新增页面 `/settings/connection`（连接设置）：地址、访问口令、保存并测试、当前环境与来源。

### 2. 后端 CORS、局域网监听与访问控制

- 新增配置：`ACCESS_TOKEN`（共享口令，默认空）、`ALLOW_LAN`（默认 false）、
  `CORS_EXTRA_ORIGINS`（默认空）。
- CORS 放行 `https://localhost`、`capacitor://localhost`、本机回环任意端口，
  以及显式配置的额外来源；**不放开任意来源**。
- 新增 `AccessTokenMiddleware`：未设置口令时保持历史行为；设置后除
  `/api/v1/health`、`/api/v1/auth`、静态资源、OPTIONS 预检外均要求
  `Authorization: Bearer` 或 `X-BioLearn-Token`，比较使用 `hmac.compare_digest`。
- 新增公开接口 `GET /api/v1/auth`，只返回 `required/authenticated`，不回显口令。
- `scripts/run_backend.py --lan` 显式监听 `0.0.0.0` 并打印手机应填地址；
  不加 `--lan` 仍是 `127.0.0.1`。新增 `start-lan.bat`（带警告）。
- **没有**任何把 SQLite 暴露到网络的实现；数据只经 FastAPI 访问。

### 3. 移动端 UI

- 底部主导航（≤860px 显示）：首页 / 学科 / 导入 / 练习 / 题库 / 连接。
- 安全区：`env(safe-area-inset-*)` 处理刘海、状态栏、底部手势条；`viewport-fit=cover`。
- 触控：按钮/输入/选项/树行最小 44px；输入框 16px 防止聚焦放大。
- 键盘：窄屏操作栏 sticky 贴底，弹窗内容区独立滚动。
- 窄屏：评审/出题/练习/导入栅格改单列；宽表格与树在容器内横向滚动。
- 横屏：保留底部导航并压缩主区域。
- 桌面：>860px 时底部导航隐藏，原顶部导航与布局不变（回归测试通过）。
- 断点从 760 调整为 860：该机 `1968px @ 400dpi ≈ 787 CSS px`，760 会漏掉。

### 4. Android 工程

- Capacitor 7.6.9：`@capacitor/core`、`@capacitor/android`、`@capacitor/cli`。
- `frontend/capacitor.config.ts`：`appId=ai.biolearn.app`、`appName=BioLearn AI`、
  `webDir=dist`、`androidScheme=https`、`allowMixedContent=true`。
- 新增 **仅 debug** 的 `android/app/src/debug/AndroidManifest.xml`：
  `usesCleartextTraffic=true`，用于局域网 HTTP 测试。
  **release APK 实测没有该属性**（默认禁止明文），正式远程必须 HTTPS。
- 图标/启动页使用 Capacitor 默认资源（未做品牌化设计，属未完成项）。

---

## 三、实体设备实测（关键证据）

设备：`PA2553`，Android 16（API 36），1968×2800，400dpi。
后端：`start-lan` 模式监听 `0.0.0.0:8000`，数据库为真实 `backend/data/biolearn.db`。

| 验证项 | 结果 |
| --- | --- |
| `adb install -r app-debug.apk` | **Success**，`pm list packages` 可见 `ai.biolearn.app` |
| 冷启动 | `MainActivity` 前台，页面正常渲染（非白屏） |
| 底部导航 | 6 个入口显示，符合安全区 |
| 连接真实局域网 | 首页显示“服务在线”，`GET http://10.61.232.199:8000/api/v1/health`，延迟 40–46ms |
| 手机读电脑数据 | 学科页显示 10 个学科、6 个章节（与服务器一致） |
| 手机写 → 电脑读 | 手机新建 `PHASE3-SYNC-PHONE`，桌面 API 立即查到（11 个学科） |
| 电脑写 → 手机读 | 桌面 API 新建 `PHASE3-SYNC-DESKTOP`，手机刷新后显示 12 个学科，两名称均可见 |
| 手机练习 → 电脑读 | 手机完成 4 题练习（得分 75，3/4 正确），桌面 `GET /practice/sessions/{id}/result` 返回同一 4 条作答 |
| 断网/错误提示 | 指向不可达端口时显示“无法连接后端”，超时文案包含地址与排查指引 |
| 恢复 | 改回局域网地址后重新在线 |

> 说明：`adb` 还建立过 `reverse tcp:8000`，用于早期验证；最终验证使用的是**真实局域网 IP**，
> 不依赖 USB 反向映射。

测试数据清理（先 dry-run，再 apply）：

- 删除合成学科 2 个（`PHASE3-SYNC-PHONE/DESKTOP`，cascade）。
- 删除合成练习会话 1 个及其 4 条作答（`scripts/cleanup_phase3_sync.py`）。
- 清理后数据库恢复：学科 10、章节 6、练习会话 3、作答 6、知识点 78、题目 7。
- 真实课件与知识点未被修改。

---

## 四、APK 产物

```
frontend/android/app/build/outputs/apk/debug/app-debug.apk
大小：4,339,441 字节
SHA-256：66d3811f183b94caf32bebef8cbb9956623dbff342d3bba8ee423423326b554d
包名：ai.biolearn.app   应用名：BioLearn AI   versionCode=1 versionName=1.0
minSdk=23  targetSdk=35  compileSdk=35
签名：Android Debug 证书（SHA-256 db5b141d…57cbd），apksigner verify 通过
权限：仅 INTERNET
```

APK 内容审计：无 `.env`、无 AI Key、无 `ACCESS_TOKEN`、无 SQLite 数据库、无上传文件、
无开发机地址（`127.0.0.1:8000` / `10.61.232.199` 均未命中）。

> 这是 **debug** APK：可侧载，不可上架。正式发布需要自己的 keystore，见第六节。

`assembleRelease` 也已实测成功，产物为
`frontend/android/app/build/outputs/apk/release/app-release-unsigned.apk`（3,250,206 字节，未签名）。

---

## 五、构建命令与环境

本机已安装（均在 `C:\Users\bzlciallo\android-toolchain`）：

| 工具 | 版本/路径 |
| --- | --- |
| JDK 21（构建用） | `jdk-21.0.12.1+1` |
| JDK 17（备用） | `jdk-17.0.20.1+1` |
| Android cmdline-tools | `android-sdk\cmdline-tools\latest` |
| platforms / build-tools | `android-35` / `35.0.0` |
| Gradle | 8.11.1（已放入 wrapper 缓存） |

> **必须用 JDK 21**。JDK 17 编译 Capacitor 7 会报
> “无效的源发行版：21”。JDK 17 仅用于其他旧工具链。

可重复命令：

```powershell
$env:JAVA_HOME = "C:\Users\bzlciallo\android-toolchain\jdk-21.0.12.1+1"
$env:ANDROID_HOME = "C:\Users\bzlciallo\android-toolchain\android-sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"

cd frontend
pnpm build:android                 # tsc + vite build --mode android（不内联开发地址）
pnpm exec cap sync android
cd android
gradlew.bat assembleDebug          # 产物：app/build/outputs/apk/debug/app-debug.apk
```

一条命令（需本机 `npm`/`pnpm` 可用）：

```powershell
cd frontend
pnpm android:apk
```

`frontend/android/local.properties` 含本机 SDK 路径，已被 `.gitignore` 排除，需本机生成。

---

## 六、正式 Release 签名步骤

```powershell
# 1. 生成 keystore（只做一次，务必备份，不要提交到 Git）
& "$env:JAVA_HOME\bin\keytool.exe" -genkeypair -v `
  -keystore C:\secure\biolearn-release.jks -alias biolearn `
  -keyalg RSA -keysize 4096 -validity 10000

# 2. 在 frontend/android/app/build.gradle 的 android {} 中加入 signingConfigs
#    （口令建议放 ~/.gradle/gradle.properties 或环境变量，不要写进仓库）
#    signingConfigs { release { storeFile file(System.getenv("BIOLEARN_KEYSTORE"))
#      storePassword System.getenv("BIOLEARN_STORE_PASSWORD")
#      keyAlias System.getenv("BIOLEARN_KEY_ALIAS")
#      keyPassword System.getenv("BIOLEARN_KEY_PASSWORD") } }
#    buildTypes { release { signingConfig signingConfigs.release } }

# 3. 构建
cd frontend\android
gradlew.bat assembleRelease
# 产物：app/build/outputs/apk/release/app-release.apk（已签名）

# 4. 校验
& "$env:ANDROID_HOME\build-tools\35.0.0\apksigner.bat" verify --print-certs `
  app\build\outputs\apk\release\app-release.apk

# 5. 上架前改 versionCode / versionName（android/app/build.gradle）
```

正式版必须把 API 指向 HTTPS 域名，并设置 `ACCESS_TOKEN`。release 构建默认禁止明文 HTTP。

---

## 七、局域网与跨网部署

### 场景 A：局域网（已实测）

1. 电脑 `.env`：
   ```
   ACCESS_TOKEN=<随机口令>
   CORS_EXTRA_ORIGINS=["http://10.61.232.199:8000"]
   ```
2. 双击 `start-lan.bat`（或 `python scripts/run_backend.py --lan --port 8000`）。
   日志会打印 `手机请填写：http://<IPv4>:8000/api/v1`。
3. 手机与电脑同一 Wi-Fi，APK 的“连接设置”填该地址与口令。
4. 若手机连不上：检查 Windows 防火墙是否放行 8000/TCP（专用网络），
   并确认路由器未开启 AP 隔离。

### 场景 B：跨网络（未实现、未验证）

- 需要长期在线的服务器 + HTTPS 反向代理；必须设置 `ACCESS_TOKEN`。
- 不要把 SQLite 或 `uploads/` 暴露到公网。
- 本轮没有云部署脚本，也没有实测远程访问。

---

## 八、数据同步架构

```
Android APK (WebView, https://localhost) ─┐
                                          ├─ HTTP(S) + 可选 Bearer 口令
桌面浏览器 / start.bat (同源 /api/v1) ────┘
                     ↓
              FastAPI（唯一写入入口）
                     ↓
        SQLite backend/data/biolearn.db + uploads/
```

- 手机与电脑是同一后端的两个客户端，APK 内没有数据库副本。
- 在线同步：写操作立即落库，另一端重新请求即可见。
- 无离线编辑、无冲突合并（V1.1）。
- 访问控制是单一共享口令，不做多用户隔离；后端默认只监听本机。

---

## 九、回归测试（实际执行）

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 后端全量 | `pytest`（backend/，隔离临时库） | **86 passed**（新增 6 项口令/CORS） |
| 前端类型 | `tsc --noEmit` | 通过 |
| 前端 Lint | `eslint .` | 通过 |
| 前端单测 | `vitest run` | **13 文件 / 30 passed**（新增 4 项连接配置） |
| 前端构建 | `vite build` | 通过 |
| Android debug | `gradlew assembleDebug` | **BUILD SUCCESSFUL** |
| Android release | `gradlew assembleRelease` | **BUILD SUCCESSFUL**（未签名） |
| 桌面端回归 | 原有学科/章节/导入/审核页面 | 后端 86 项 + 前端 30 项覆盖；页面未改动业务逻辑 |

---

## 十、未完成 / 未验证

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 多用户登录与数据隔离 | ❌ 未实现 | 仅共享口令；不满足多用户场景 |
| 远程 HTTPS 部署 | ❌ 未实现/未验证 | 只有方案，没有服务器 |
| 离线编辑与冲突合并 | ❌ 未实现 | V1.1 |
| 应用图标/启动页品牌化 | ❌ 未做 | 使用 Capacitor 默认资源 |
| 自动化 Android UI 测试 | ❌ 未做 | 本轮为 adb + 截图 + CDP 手工验证 |
| iOS | ❌ 未做 | 只做 Android |
| 大文件上传在手机端的进度/取消 | ⚠️ 未在手机实测 | 组件复用桌面逻辑，未做设备验证 |
| 键盘遮挡长表单 | ⚠️ 部分验证 | 已加 sticky 操作栏，未逐页实测 |

---

## 十一、已知限制与下一步

1. **认证是单口令**：知道口令即可读写全部数据。若要多用户，需要用户表、会话与按用户过滤，
   属于下一阶段工作；在此之前不要把服务直接暴露公网。
2. **HTTP 仅限局域网**：release 禁止明文，远程必须 HTTPS；调试包的 `usesCleartextTraffic`
   不会进入 release。
3. **无离线能力**：断网时只能读已渲染页面，刷新即失败；这是第一版的明确取舍。
4. **未做真机自动化**：后续可加 Detox/Appium 或 Playwright + 模拟器。
5. **图标与启动页**：需要品牌素材后替换 `android/app/src/main/res/mipmap-*` 与 splash。
