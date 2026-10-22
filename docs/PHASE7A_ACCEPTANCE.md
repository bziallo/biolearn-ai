# 阶段 7A 验收记录：审计、架构与测试设计

日期：2026-10-22
基线：`df94cf8`
状态：**7A 只完成审计/架构/测试设计；没有实现本地数据库、文件存储或同步。**

---

## 一、基线核对（实际执行）

| 检查 | 结果 |
| --- | --- |
| `git HEAD` | `df94cf8` |
| 工作区 | 干净（7A 文档提交前） |
| `v1.0.0-rc.1` | `930f279`，未修改 |
| 真实库 | `0009_question_bank` |
| 学科/章节/资料/分块 | 10 / 6 / 2 / 117 |
| 知识点/题目/练习/作答 | 78 / 7 / 3 / 6 |
| 后端完整测试 | **117 passed** |
| 前端测试 | **35 passed / 14 files** |
| TypeScript | 通过 |
| ESLint | 通过 |
| 生产构建 | 通过 |
| Android Debug | 阶段 6M 最近一次 `BUILD SUCCESSFUL`；7A 未改 Android 代码 |

7A 没有修改真实数据库、上传文件、标签、签名、Android Manifest 或网络配置。

---

## 二、审计结论（摘要）

### 已实现且已验证（阶段 6M）

| 能力 | 证据 |
| --- | --- |
| Android 课程列表 → 课程知识库 | 真机点击课程标题/主区域进入 |
| 课程知识库章节/资料/知识点/题目 | 真机 2 根章节 / 3 课件 / 78 知识点 / 7 题 |
| Android 系统文件选择器 | 真机选择 `phase6-synthetic.txt` |
| 课件上传/解析状态 | 真机“资料已归档”、审核页“资料已解析” |
| 已缓存课程离线浏览 | 后端停止后显示“离线缓存 + 时间” |
| 后端不可达/未缓存提示 | 第二门未缓存课程显示明确错误，不串课 |
| 后端恢复 | 重启后重新加载恢复 |
| Android 返回 | 原生 `onBackPressed` 回退 WebView 历史 |
| 0010 迁移数据保全 | 临时库升级后 6 章节/2 资料/78 知识点保留 |

### 已实现但仍依赖后端

| 能力 | 依赖 |
| --- | --- |
| 课件上传 | FastAPI `/documents` / `/imports` |
| PDF/DOCX/PPTX 解析 | Python pypdf/python-docx/python-pptx |
| AI 知识点提取 | FastAPI + 外部 OpenAI-compatible 模型 |
| AI 出题 | FastAPI + 外部模型 |
| 知识点审核/编辑 | FastAPI |
| 练习开始/提交/结果 | FastAPI |
| 账号/邀请/共享 | FastAPI 用户与会话 |

### 仅设计、未实现

- 手机本地 SQLite（无 SQLite 插件）；
- 私有文件持久化（无 Filesystem 插件）；
- 本地 TXT/MD 解析；
- 本地写与 outbox；
- 双向增量同步、tombstone、幂等创建；
- 端侧规则提取/端侧 AI；
- Android Keystore token。

### 未验证

- 真实 Wi-Fi 局域网（6M 用 `adb reverse`；ICMP 100% 丢包）；
- HTTPS/远程后端；
- 签名 Release 新流程；
- 真实 AI 提取（临时后端未配置 Key）。

---

## 三、测试设计（7B–7F 门槛）

| 阶段 | 必测 | 通过标准 |
| --- | --- | --- |
| 7B | 本地 migration 1→2→1、CRUD/外键、导入导出 checksum、飞行模式读 | 离线可读课程/KP；无本地写；真实库不变 |
| 7C | SAF→私有文件、进程重启、25MB/格式/重复 SHA、TXT/MD 解析、远程队列 | 重启文件仍在；TXT/MD 真解析；PDF 明确需后端；重复不新增 |
| 7D | 离线写、outbox 事务、重启恢复、冲突矩阵 | 不丢数据；冲突可见；不静默覆盖 |
| 7E | 幂等创建、cursor、tombstone、多端并发、旧 API 回归 | 三端一致；删除不复活；旧客户端可用 |
| 7F | 规则候选准确率/覆盖率、无自动审核、内存/热/耗电 | 质量达标才发布；不达标不做端侧 AI |

每次迁移必须在隔离库先执行 upgrade/downgrade/再 upgrade；真实库迁移单独批准。

---

## 四、7B–7F 验收与回滚摘要

| 阶段 | 交付 | 回滚 |
| --- | --- | --- |
| 7B | 只读本地 SQLite + Repository + 导入 | 关闭 `MOBILE_LOCAL_DB`；删除本地 DB |
| 7C | 私有文件 + TXT/MD 解析 + 上传队列 | 关闭本地文件 flag；删除本地文件；服务端不动 |
| 7D | 本地写 + outbox + 冲突表 | 关闭本地写；清空 outbox；恢复远程 |
| 7E | 双向同步 + 电脑数据导入 | 暂停同步；从导出包重建本地；服务端备份恢复 |
| 7F | 规则/端侧 AI 评估 | 关闭本地规则；只保留人工/远程 AI |

硬性约束：7A 不执行真实库迁移、不安装 SQLite/Filesystem 插件、不开放公网、不改标签/签名。

---

## 五、未解决问题

1. 本地 SQLite 插件与 Capacitor 7 的精确兼容版本需在 7B 实机验证。
2. 现有服务端无 `change_seq`/tombstone/幂等键；7E 需要新增迁移和 API。
3. 现有文件只是 WebView 临时 `File`，需要 7C 私有复制与生命周期处理。
4. 真实 Wi-Fi 与 HTTPS 仍未验证；不能把 `adb reverse` 当远程验收。
5. Android token 仍未接 Keystore；本地 DB 是否启用 SQLCipher 需单独评估。
6. 本地 AI 质量/性能未评估；不应作为 7B–7E 的承诺。

---

## 六、结论

7A 的审计与设计完成，推荐 **Capacitor SQLite + Filesystem + Repository + 可选 FastAPI 同步**，
分 7B 只读本地库 → 7C 文件/TXT-MD → 7D 本地写/outbox → 7E 双向同步 → 7F 规则/端侧 AI 评估。

当前仍不能宣称“手机可完全离线导入并进行真实 AI 分析”。
