# 阶段 7B 验收记录：只读本地 SQLite 基础层

日期：2026-10-22
代码提交：`600582c`
验收状态：**自动化测试、Android Debug 构建与真机基础验证通过；未接入现有业务、未写真实库。**

---

## 一、测试命令与实际结果

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
| Vitest | **43 passed / 17 files** |
| 生产构建 | 通过 |
| 本地 SQLite 测试 | 5 passed |
| Repository/开关测试 | 3 passed |

新增测试覆盖：

- schema v2 与外键；
- 合成数据关联查询；
- 非法外键插入被拒绝；
- v1→v2 迁移保留数据；
- 导出 SHA-256、导入新库、篡改 checksum 拒绝；
- 关闭后重开记录仍存在；
- 默认 Repository 为 FastAPI；
- 开关默认关闭/运行时切换。

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
大小：**27,748,584 字节**
SHA-256：`82e228245b733baa6340a94755f895c84edc272aa79ffe291105cfbb05d47dce`

> 体积增加来自 SQLCipher 原生库；不是 JS 包。

---

## 二、真机验证（PA2553 / Android 16）

| 项 | 结果 | 证据 |
| --- | --- | --- |
| 安装 Debug APK | ✅ Success | `adb install -r` |
| 插件加载 | ✅ `@capacitor-community/sqlite 7.0.3` | `phase7b-enabled.png` |
| schema | ✅ 2 | 页面 |
| 外键 | ✅ ON | 页面 |
| 默认开关 | ✅ 关 | 初始页面 |
| 打开本地 DB | ✅ 成功 | 页面 |
| 写入合成数据 | ✅ counts：1/2/1/2/2/1/1 | `phase7b-export2.png` |
| 查询关联 | ✅ 合成课程 + 2 知识点 | 页面 |
| 导出 checksum | ✅ `891506d5...c4a0ae9`，SHA-256 | `phase7b-export2.png` |
| 关闭并重新打开 | ✅ 记录仍可查询 | 页面提示 |
| 进程重启 | ✅ counts 仍为 1/2/1/2/2/1/1 | `phase7b-process-restart.png` |
| 飞行模式 | ✅ 仍可查询本地数据 | `phase7b-airplane.png` |
| 关闭开关 | ✅ 页面回到 FastAPI 默认路径 | `phase7b-disabled.png` |
| 私有 DB | ✅ `databases/biolearn_localSQLite.db`，0600 | `run-as` |
| 现有业务页面 | ✅ 仍显示远程 FastAPI 缓存，不是本地合成课程 | 真机截图 |

> 真机测试使用 Debug APK 和私有合成数据库；没有导入真实课程，没有修改真实 SQLite。

---

## 三、未验证/未完成

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 真机 v1→v2 原生迁移 | ❌ 未单独验证 | sql.js 自动化测试已覆盖；真机新库直接 v2 |
| 真机导入 JSON | ❌ 未验证 | 自动化覆盖；诊断页仅显示导出摘要 |
| 浏览器/桌面本地 SQLite | ❌ 不支持 | 原生插件只在 Android 可用 |
| 本地业务写入/同步 | ❌ 未实现 | 7D/7E |
| 文件持久化/本地解析 | ❌ 未实现 | 7C |
| SQLCipher 加密 | ❌ 未启用 | 当前 DB 私有目录 0600，未加密 |
| 用户隔离 | ❌ 未实现 | 仅合成数据，未接账号 |
| 真实数据导入 | ❌ 未执行 | 明确禁止 |
| 签名 Release/HTTPS | ❌ 未验证 | 7B 未改 Release |

---

## 四、数据库与安全核对

| 项 | 结果 |
| --- | --- |
| 真实库 Alembic | `0009_question_bank` |
| 真实库写入 | 无 |
| 真实库数据 | 10 学科 / 6 章节 / 2 资料 / 78 知识点 / 7 题 |
| `v1.0.0-rc.1` | 仍为 `930f279` |
| 签名/Release 配置 | 未修改 |
| Tunnel/DNS/公网端口 | 未操作 |
| APK 秘密 | 无 AI Key、DB 口令、token、签名材料 |
| 导出内容 | 仅合成课程/章节/文档元数据/知识点/题目/练习/答题；无文件/Key/token |

---

## 五、功能开关与回滚

默认：

- `VITE_MOBILE_LOCAL_DB=false`；
- 运行时未设置 `biolearn.mobile_local_db`；
- Repository 选择 `remote`；
- 现有页面继续 FastAPI。

回滚：

1. 打开 `/settings/local-db`，点击“关闭本地数据库”；
2. 或移除运行时 key/设置 `VITE_MOBILE_LOCAL_DB=false` 后重新构建；
3. 不删除真实服务端数据库；
4. 常规回滚不依赖删除本地数据库；合成测试库可保留或由后续隔离清理脚本处理。

---

## 六、Git

- 7B 代码提交：`600582c`
- 基线：`42e9293`（阶段 7A）
- 工作区：提交后干净
- 变更：插件精确版本、lockfile、本地 schema/数据库/仓库/诊断页、测试、证据截图、文档

---

## 七、结论

7B 的**只读本地 SQLite 基础层**已实现并通过自动化与真机基础验证：

- 插件 7.0.3 可加载；
- 私有 DB 可创建、迁移、外键、关闭/重开；
- 合成数据可查询、导出/校验；
- 飞行模式可读；
- 默认仍为 FastAPI，功能开关可回滚；
- 真实库、标签、签名、HTTPS 策略未被改动。

但手机业务仍没有切换到本地数据源；本地写、文件、同步、真实数据导入均未实现，
因此不能宣称“手机已完全离线可用”。
