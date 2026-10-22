# 阶段 6M 验收记录

日期：2026-10-22
基线：`f1b93c7` + 阶段 6M 提交
状态：**代码、自动化测试、构建和真机主流程已验证；同 Wi-Fi 与 HTTPS 远程仍未验证。**

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
| 生产构建 | 通过 |
| Android web build | 通过 |

新增覆盖：课程卡主区域链接、知识库真实数据、课程切换不串数据、离线缓存、
文件格式/25 MB 拒绝、上传网络失败保留文件并重试。

### 后端

```powershell
cd backend
.venv/Scripts/python.exe -m pytest -q
```

结果：**117 passed**（新增 0010 迁移数据保全测试）。

> 本轮发现并修复了阶段 6B `0010_users_auth` 迁移的一个真实风险：
> 原实现用 `batch_alter_table` 重建 `subjects`，在 SQLite 外键开启时会级联删除章节等子表。
> 已改为直接 `ADD COLUMN`，并新增测试：0009 存在章节时升级到 0010 后章节仍存在。
> 真实库未执行该迁移，因此未受影响。

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
SHA-256：`8677ad5c6cad81bf036baefd18f1754b4f777da98d899263e11a8ce6442bdaba`

---

## 二、真机验证（PA2553，Android 16）

设备：`401F8S00Y90000H`，1968×2800，400dpi。

测试后端：**临时副本数据库**（复制真实库 + 在临时目录执行 0010 迁移），
通过 `adb reverse tcp:8000 tcp:8000` 连接；未使用真实数据库写入。

| 项目 | 结果 | 证据/说明 |
| --- | --- | --- |
| 安装 Debug APK | ✅ 成功 | 用户解锁后 `adb install -r` Success |
| 连接后端 | ✅ 成功 | 连接设置保存后显示“连接成功，可以正常读写数据” |
| 课程列表 | ✅ 10 学科 / 6 章节 | 与临时副本一致 |
| 点击课程名称/主区域 | ✅ 进入知识库 | 点击“生物化学”标题进入 `/subjects/.../knowledge` |
| 知识库数据 | ✅ 2 根章节 / 3 课件 / 78 知识点 / 7 题 | 课件解析状态、知识点列表/详情均来自 API |
| 知识点详情 | ✅ | 显示解释、核心要点、来源引用、审核状态 |
| Android 返回键 | ✅ | 从课程知识库返回课程列表，不再直接退出 App |
| 系统文件选择器 | ✅ | 打开 Android 文件选择器并选择 `phase6-synthetic.txt` |
| 手机导入课件 | ✅ | 页面显示“文件已上传，正在解析和识别结构”→“资料已归档” |
| 解析状态 | ✅ | 知识审核页显示“资料已解析”；临时库新增 1 份资料 |
| AI 未配置提示 | ✅ | 临时后端无 AI Key，页面明确显示“AI 未配置”，未生成伪造结果 |
| 后端不可达 | ✅ | 已缓存课程显示“当前显示离线缓存 + 时间”；未缓存课程显示明确错误，不串课 |
| 后端恢复 | ✅ | 重启临时后端后点击“重新加载”，课程数据恢复 |
| 小屏/竖屏 | ✅ | 旋转竖屏后课程知识库单列布局、底部导航正常；触控区域可用 |
| 同 Wi-Fi 局域网 | ❌ 未验证 | 设备 `ping 10.61.120.64` 100% packet loss；本轮用 `adb reverse` |
| HTTPS/签名 Release | ❌ 未验证 | 无远程部署；Release 未重新构建 |

> 说明：`adb reverse` 只能证明 WebView 网络栈、文件选择和业务页面可用，
> **不能**替代真实 Wi-Fi 局域网或互联网 HTTPS 验收。

---

## 三、数据库与安全核对

| 项 | 结果 |
| --- | --- |
| 真实库 Alembic | `0009_question_bank`（未迁移） |
| 真实库数据 | 10 学科 / 2 资料 / 78 知识点 / 7 题 / 3 练习 |
| 真实库写入 | 无 |
| 临时库 | 真实库副本；执行 0010；测试后已停止服务并删除临时目录 |
| `v1.0.0-rc.1` | 未修改，仍指向 `930f279` |
| Tunnel/DNS/公网端口 | 未创建/未修改 |
| APK 秘密 | 无 AI Key、DB 口令、签名材料 |

---

## 四、未完成/未验证

| 项 | 状态 |
| --- | --- |
| 同 Wi-Fi 真实局域网 | ❌ 未验证（ICMP 不通） |
| 互联网 HTTPS/远程后端 | ❌ 未部署/未验证 |
| 签名 Release 登录/导入 | ❌ 未验证 |
| 真实 AI 知识点提取 | ❌ 临时后端未配置 Key，仅验证“未配置提示” |
| 断网/恢复的系统级网络切换 | ⚠️ 只验证后端不可达与恢复；未切换 Wi-Fi/飞行模式 |
| 手机本地解析/本地 AI | ❌ 未实现 |
| 离线写队列/冲突合并 | ❌ 未实现（只读缓存） |
| Android Keystore 登录令牌 | ❌ 仍为 WebView sessionStorage |

---

## 五、结论

- 课程导航、课程知识库、知识点浏览、手机系统文件选择与导入、Android 返回、
  离线只读缓存、后端不可达提示与恢复，已在真机跑通。
- 手机导入/解析仍依赖后端；电脑关机时只能读缓存，不能完成真实分析。
- 正式远程使用仍需独立 HTTPS 后端；本轮没有创建公网入口。
- 0010 迁移的数据保全风险已修复并测试；真实库仍未迁移。
