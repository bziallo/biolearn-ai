# 阶段五验收报告：V1.0 发布候选与稳定性验证

日期：2026-10-21
基线：`eae81e1`（阶段四）
结论：**批量真实模型、HTTP 422 兼容、Android 真机完整闭环、移动端抽查、备份恢复均已完成；达到 V1.0 Release Candidate 条件，但仍有明确发布限制（见第九节）。**

---

## 一、Git 与工作区

- 开始状态：`eae81e1`，工作区干净。
- 本轮分阶段提交后推送 `main`；提交列表见文末或 `git log --oneline`。
- 未提交 `.env`、API Key、认证口令、真实数据库、上传文件、keystore 或 APK。
- 真实数据库在全部测试前后保持：学科 10、章节 6、资料 2、知识点 78、题目 7、练习会话 3、作答 6、出题任务 5。

---

## 二、任务一：AI 出题批量稳定性

### 计划（执行前已报告）

- 目标 20 题，4 个独立批次 × 5 题。
- 题型：`single+true_false`、`multiple+single`、`true_false+short_answer`、`single+multiple`。
- 6 个合成已审核知识点（膜运输、酶、DNA 复制、蛋白结构、动作电位）。
- 预计 6 次调用、7,200 输入 / 10,800 输出 tokens，**预计约 $0.0076**；
  本轮只做第一轮，不重复采样。

### 实际结果（真实模型，隔离 SQLite）

脚本：`scripts/evaluate_question_generation.py --live`
输出：`outputs/phase5_generation_eval.json`

| 批次 | 题型 | 目标 | 保存 | 跳过 | 失败 | 调用 | tokens (in/out) | 延迟 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | single + true_false | 5 | 5 | 0 | 0 | 1 | 651 / 1,751 | 8.15s |
| 2 | multiple + single | 5 | 5 | 0 | 0 | 1 | 667 / 2,370 | 10.64s |
| 3 | true_false + short_answer | 5 | 5 | 0 | 0 | 1 | 656 / 1,766 | 8.32s |
| 4 | single + multiple | 5 | 5 | 0 | 0 | 1 | 770 / 921 | 3.89s |
| **合计** | 4 批 | **20** | **20** | **0** | **0** | **4** | **2,744 / 6,808** | 均值 7.75s，最大 10.64s |

其他指标：

- 格式修复次数：**0**
- 错误类别：`none` × 4
- 完成批次：**4/4**
- 总 tokens：**9,552**（其中 reasoning tokens 3,896，按输出计费）
- **估算费用：$0.004496**（按 DeepSeek 非高峰列表价，输入 cache-miss $0.15/M、输出 $0.60/M；
  未计缓存命中折扣，实际账单以提供商为准）
- 单位成本：**约 $0.000225 / 题**（估算值）
- 分母说明：保存率 20/20（目标 20）；跳过率 0/20；批次失败率 0/4。

本轮没有出现格式修复或失败，所以“修复/跳过/整批失败”路径由确定性回归测试覆盖，
不与真实成功样本混报。

---

## 三、任务二：HTTP 422 与 JSON 模式兼容

### 修改

- 只有响应体同时包含 JSON 模式标识（`response_format` / `response format` / `json_object` /
  `json mode`）与明确拒绝语义（not supported / unsupported / not permitted / unknown 等，仅 400/422）时，才判定为“JSON 模式不支持”。
- 判定为不支持时：关闭 JSON 模式并**仅重试一次**；后续调用不再发送 `response_format`。
- 其他 400/422（如 `max_tokens`、消息格式）不降级，直接保留错误分类。
- `last_json_mode_fallback` 记录降级状态与原因；出题任务写入 `timings.json_mode_fallback`。
- 原有 timeout/network/auth/quota/rate_limit/server 分类保留。

### 测试（`backend/tests/test_ai_client.py`，13 passed）

- 422 明确 `response_format is not supported` → 降级一次并成功；
- 422 `unsupported parameter: response_format` → 降级一次；
- 422 其他参数错误 → 不降级，仅 1 次调用；
- 400 其他参数错误 → 不降级；
- 400 明确 `response_format` → 降级；
- 500 提到 response_format → 不降级（非参数错误）；
- 成功响应记录 `usage`（prompt/completion/total/reasoning）；
- 既有 JSON 围栏/前后解释提取测试仍通过。

**限制**：没有可用的真实 422 网关，以上为按提供商错误体构造的回归测试；
没有声称已在真实 422 服务上验证。

---

## 四、任务三：Android 真机完整闭环

设备：`PA2553`，Android 16（API 36），1968×2800，400dpi。
App：`ai.biolearn.app`，debug APK，连接 `http://10.61.232.199:8000/api/v1`。

实际步骤与结果：

| 步骤 | 结果 |
| --- | --- |
| 1. 连接后端 | 首页显示“服务在线”，LAN 地址直连 |
| 2. 准备合成数据 | 电脑 API 创建“阶段五真机合成学科”，外部 JSON 导入 2 个知识点并审核通过 |
| 3. 手机触发 AI 出题 | 手机“题库 → AI 出题”，选择该学科/章节/2 个知识点，题型单选+判断，题量 2，点击“开始生成” |
| 4. 任务状态 | 手机显示“题目草稿已生成，等待审核”“已生成 2 · 跳过重复 0” |
| 5. 审核 | 在手机题目详情中逐题点“通过”，两题变为已通过 |
| 6. 练习 | 手机练习页选该学科，抽到 2 题 |
| 7. 提交与结果 | 选择 A / 正确，提交后显示 **得分 100，正确 2/2**，解析与知识点正常 |
| 8. 电脑端确认 | 桌面 API 查到同 2 题（approved）与同一练习会话（completed，100 分，2 条作答） |

证据（截图，未提交仓库）：
`outputs/phase5_evidence/android-generated.png`、`android-result.png`。
清理：先 `--dry-run` 再 `--apply`，删除合成学科/资料/章节/知识点/题目/练习/作答/任务，
并删除合成上传文件；真实库计数恢复为 10/6/2/78/7/3/6/5。

> 说明：手机端确实有 AI 出题入口（题库页“AI 出题”），无需新增入口。

---

## 五、任务四：移动端抽查与修复

在真机 787 CSS px 宽度下逐路由检查：`/`、`/subjects`、学科详情、资料页、
`/questions`、`/practice`、`/import`、`/settings/connection`、`/settings/ai`、`/about`。

| 检查项 | 结果 |
| --- | --- |
| 横向溢出 | 10 个路由均 `scrollWidth == innerWidth`，无溢出 |
| 底部导航 | 全部路由显示，桌面宽度隐藏 |
| 触控尺寸 | 修复后所有可见按钮最小边 ≥44px（学科详情曾出现 28–36px 的 ↑/↓/编辑/删除） |
| 软键盘 | 连接设置聚焦输入框后键盘弹出，输入框与“保存并测试”仍在可视区 |
| 网络错误/恢复 | 指向不可达端口显示“连接超时…”，改回 LAN 后恢复“服务在线” |
| 长文本 | 题干、解析、来源在窄屏正常换行；无横向溢出 |
| 重复提交 | 出题按钮 `genBusy` 时禁用；后端并发任务返回 409；新增测试证明只保留 1 个任务 |
| 空/加载/失败 | 各页沿用现有 loading/Notice/空状态；未发现白屏 |

实际修复：

1. `AISettingsPage` 返回链接从错误的“← 返回学科列表”改为“← 返回首页”。
2. 移动端所有 `button` / `.mini-button` 最小 44×44；`.text-button`、`.tree-toggle`、
   `.chapter-select` 同样提升到 44px；避免密集操作误触。

未做与验收无关的大规模 UI 重构。

---

## 六、任务五：备份与恢复

### 改进

- `scripts/backup_data.py` 新增 `--data-dir`；`scripts/restore_data.py` 新增 `--data-dir`，
  并支持 `--port 0` 跳过端口检查（仅隔离测试用）。
- 恢复时若指定 `--data-dir`，Alembic 迁移指向该临时库，避免误升级真实库。
- 默认行为不变（仍为 `backend/data`，仍要求端口 8000 已停止）。

### 隔离测试（临时目录）

1. 临时库用 Alembic 升级到 `0009_question_bank`；
2. 写入 1 个合成学科、1 个资料、1 个知识点，并写入 `uploads/backup.txt`；
3. `backup_data.py --data-dir <temp> --output-dir <temp-backup>` → 成功，数据库完整性 ok；
4. 删除学科、删除上传文件（模拟丢失）；
5. `restore_data.py <backup> --data-dir <temp> --force --port 0` → 成功；
6. 验证：学科 1、知识点 1、`uploads/backup.txt` 内容恢复、Alembic `0009_question_bank`、
   旧数据移动到 `_restore_previous_*`。

**结果：通过。**

另外对真实库做了一次只读备份验证：10 学科、7 题、78 知识点、7 个上传文件、integrity ok；
备份目录含 `ai_config.json`（含密钥），已在使用后立即删除，未提交。

---

## 七、回归测试（实际执行）

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 后端全量 | `pytest`（backend/） | **110 passed** |
| 前端类型 | `tsc --noEmit` | 通过 |
| 前端 Lint | `eslint .` | 通过 |
| 前端单测 | `vitest run` | **30 passed（13 文件）** |
| 前端构建 | `vite build` | 通过 |
| Android debug | `gradlew assembleDebug` | **BUILD SUCCESSFUL** |
| Android release | `gradlew assembleRelease` | **BUILD SUCCESSFUL**（未签名） |
| 真机回归 | 安装 debug APK + 启动 | 服务在线，AI 出题/审核/练习全流程通过 |

APK：

```
frontend/android/app/build/outputs/apk/debug/app-debug.apk
4,339,458 字节
SHA-256 b18c3bcc73ec4a3725383f772893f8e9700b43978d92a862b6ae20a82a991865
```

release 未签名产物：`app-release-unsigned.apk`（3,250,262 字节），正式分发仍需自有 keystore。

---

## 八、真实统计的费用说明

- tokens 来自提供商 `usage`，不是估算。
- 费用是按 DeepSeek 非高峰列表价的**估算**：输入 $0.15/M（cache miss）、输出 $0.60/M；
  未使用缓存命中价，也未读取真实账单。实际费用可能更低。
- 本轮总费用估算 **$0.004496**；没有重复采样，没有额外批量消耗。
- 未做 20 题 × 多次采样的稳定性分布；如需重复 10 轮，按本轮均值估算约 **$0.045**，
  但必须先确认预算。

---

## 九、未解决问题、风险与发布建议

1. **语义正确性仍靠人工审核**：本轮 20 题均保存为 `pending`，未自动设为 approved。
2. **样本量有限**：4 批 / 20 题全部成功，不能证明长期失败率为 0；需更多轮次。
3. **真实 422 网关未验证**：只有按错误体构造的回归测试。
4. **手机端出题等待体验**：生成约 4–11 秒，手机页面轮询正常；未做大并发/弱网压测。
5. **备份默认不复制 `.env`**：这是安全设计，自定义环境变量需手动备份。
6. **debug APK 不能上架**：正式发布需 release keystore；release 禁止明文 HTTP，远程必须 HTTPS。
7. **未在手机上测试文件上传/导入预览的完整选择器流程**：页面布局抽查通过，原生文件选择器未在本轮重测。

**发布建议**：可以作为 **V1.0 Release Candidate（debug/局域网场景）** 交付内部验收；
面向外部用户发布前，至少完成 release 签名、HTTPS 部署、备份演练和多轮批量采样。
