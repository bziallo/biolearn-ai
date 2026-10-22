# 阶段 6M 验收记录

日期：2026-10-22
基线：`f1b93c7`
状态：**代码/自动化测试/构建完成；真机 UI 验证未完成；未开放远程服务。**

---

## 一、测试命令与结果

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
| Vitest | **14 files / 35 passed** |
| 生产构建 | 通过（68 modules） |
| Android web build | 通过 |

新增覆盖：

- 课程卡主区域链接到 `/subjects/s1/knowledge`；
- 课程知识库真实加载课程/章节/课件/知识点/题目；
- 课程切换后旧课程内容消失；
- 后端不可达时读取离线缓存并显示“离线缓存”；
- 文件格式/25 MB 前端拒绝；
- 上传网络失败后保留文件并显示“重试上传”。

### 后端

```powershell
cd backend
.venv/Scripts/python.exe -m pytest -q
```

结果：**116 passed**。本次没有修改后端，回归通过。

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

产物：`frontend/android/app/build/outputs/apk/debug/app-debug.apk`
大小：4,347,776 字节
SHA-256：`9b3de2d0f496df3ceed74f30d81b840d889370aa5618d626bf6034edec33cb50`

---

## 二、真机验证

设备：`401F8S00Y90000H`（PA2553，Android 16，1968×2800，400dpi）。

实际结果：

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| `adb devices` | 已连接 | 设备处于 `device` 状态 |
| 安装新版 Debug APK | **失败** | `INSTALL_FAILED_ABORTED: User rejected permissions` |
| 解锁设备 | **失败** | 设备停留在安全锁屏；`mDreamingLockscreen=true`，无法在无人操作下解锁 |
| 文件选择器 | **未验证** | 需要先完成安装/解锁 |
| 手机导入课件 | **未验证** | 同上 |
| 手机解析/知识点浏览 | **未验证** | 同上 |
| 手机课程点击/返回 | **未验证** | 同上 |
| 手机断网/恢复 | **未验证** | 同上 |

因此**不能**声称“真机文件选择和课件导入已通过”。本轮只完成了 Debug 构建和自动化/浏览器侧验证。

另外：

- `adb shell ping 10.61.120.64` 返回 100% packet loss；同一 Wi-Fi 的局域网连通性本轮未验证。
- 未使用 `adb reverse` 作为“局域网通过”的证据。

---

## 三、未执行/未验证

| 项 | 状态 |
| --- | --- |
| 真实 Android 文件选择器 | ❌ 未验证（设备锁屏/安装被拒） |
| 真实 Android 课件上传/解析 | ❌ 未验证 |
| 真实 Android 知识点浏览/详情 | ❌ 未验证 |
| Android 返回键/深链刷新 | ❌ 未验证 |
| 同 Wi-Fi 真实局域网 | ❌ 未验证 |
| 互联网 HTTPS | ❌ 未部署/未验证 |
| 签名 Release 登录/导入 | ❌ 未验证 |
| 离线写入/冲突合并 | ❌ 未实现（只读缓存） |
| 手机本地解析/AI | ❌ 未实现 |

---

## 四、数据库与安全核对

| 项 | 结果 |
| --- | --- |
| Alembic | `0009_question_bank`（未迁移） |
| 学科 | 10 |
| 资料 | 2 |
| 知识点 | 78 |
| 题目 | 7 |
| 练习会话 | 3 |
| 真实数据库修改 | 无 |
| `v1.0.0-rc.1` 标签 | 未修改 |
| Tunnel/DNS/公网端口 | 未创建/未修改 |
| API Key/签名材料入库 | 否 |

说明：为真机测试准备过**临时副本数据库**（复制真实库到临时目录并执行 0010 迁移），
未对 `backend/data/biolearn.db` 执行迁移或写入。

---

## 五、当前可用性结论

| 场景 | 结论 |
| --- | --- |
| 电脑后端在线 + 浏览器 | 课程知识库/导航/导入代码可用，自动化覆盖 |
| 电脑后端在线 + Debug APK | 构建成功，但本轮真机验证未完成 |
| 手机离线 | 可浏览已缓存课程/知识库；不能导入/解析/AI |
| 电脑关机 + 需要真实解析/AI | **不可用**；需要始终在线后端或本地处理能力 |
| 签名 Release + 远程 | **未验收**；无 HTTPS 部署 |

---

## 六、未解决问题

1. 需要用户在真机上解锁并允许安装 Debug APK，才能补做文件选择器、导入、解析、
   课程切换、Android 返回键、断网恢复验证。
2. 需要决定是否部署始终在线的远程后端；本次未购买服务/未开公网。
3. 若要求“电脑关机仍可真实分析”，需要另立阶段评估远程后端或手机本地解析/AI，
   不能把当前只读缓存当作已完成。
4. Android 登录 token 仍在 WebView `sessionStorage`，未接 Android Keystore；
   这是既有阶段 6B 的遗留安全项。
