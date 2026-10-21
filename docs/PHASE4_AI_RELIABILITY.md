# 阶段四验收报告：AI 出题可靠性与核心学习闭环

日期：2026-10-21
基线：`9bd055f`（阶段三）
结论：**已复现真实模型失败并修复根因；真实模型在隔离库完成“上传→归档→知识点提取→审核→出题→保存→练习→结果”全链路，得分 100。**

---

## 一、根因（先复现，再修改）

### 1. 真实失败样例

模型：`deepseek-flash`（`https://api.deepseek.com`，运行时配置）
知识点：真实已审核知识点「β-转角（β-turn，β-回折）」
请求：题型 `single_choice,true_false`，数量 2，提示词与线上完全一致。

模型原始返回（节选）：

```json
{"questions":[
  {"type":"single_choice", "...":"...", "answer":{"choices":["A"]}},
  {"type":"true_false", "...":"...", "answer":true}
]}
```

`GeneratedQuestionBatch` 要求 `answer` 是对象，Pydantic 报：

```
questions.1.answer: Input should be an object [dict_type]
```

整单因此失败，任务只显示「AI 出题返回格式不符合要求」。

### 2. 为什么只加 JSON 模式不行

同一提示词加 `response_format={"type":"json_object"}` 后，DeepSeek 接受该参数并返回纯 JSON，
但判断题仍然是 `"answer": true`。所以：

- 不是 API Key 问题；
- 不是网络/超时；
- 不是 Markdown 围栏；
- 是**模型自然输出与 Schema 的字段形状不一致**，缺少归一化层。
- 旧提示词写“判断题 answer 使用 boolean”，模型合理理解为标量布尔。

历史上失败任务（真实库只读查询）：

| job | 请求 | 结果 |
| --- | --- | --- |
| `d9a7d2f4…` | 1 个知识点，single+true_false，2 题 | failed，泛化格式错误 |
| `77830c23…` | 同上 | failed |
| `2ed4513a…` | 5 个知识点，4 种题型 | failed |
| `fd55177d…` | 3 个知识点，4 种题型 | failed |

### 3. 复现方式（不调用真实 Key）

确定性回归测试：
`backend/tests/test_questions.py::test_generation_normalizes_scalar_true_false_answer`
伪造的模型响应就是上面的 `"answer": true`；修复前该测试会失败，修复后题目保存为 `{"boolean": true}`。

真实模型复现脚本（工作区，未提交，读只读库 + 真实配置）：
`phase4_e2e.py` / `phase4_full_loop.py`，均只使用临时 SQLite，不写真实库。

### 4. 次要缺陷

- `chat_json` 只处理“以 ``` 开头”的围栏，前后有解释文字时直接失败。
- 格式错误没有有限修复；一次字段错误整单失败。
- 任一题不合格会拖垮整批。
- API 错误只有少数几种提示，超时/网络混在一起，未覆盖 402 余额不足。
- `run_generation` 的未知异常只显示“请查看日志”，没有错误类别。
- 上传根目录未 `resolve()`，在 8.3 短路径（如 `C:\Users\BZLCIA~1\...`）下会误报
  `unsafe_storage_path`（本轮全链路测试发现并修复）。

---

## 二、修改内容

| 文件 | 修改原因 |
| --- | --- |
| `backend/app/services/ai_client.py` | JSON 模式（400/422 明确不支持时自动降级）；稳健 JSON 提取；错误分类（timeout/network/auth/quota/rate_limit/server/bad_request/invalid_json/bad_shape）；提供商错误只读 code/type，不回显原文 |
| `backend/app/services/question_generation.py` | 题目输出归一化；逐题校验/跳过；格式修复 1 次；错误类别与 warnings 写入 timings；DB 写入失败单独提示 |
| `backend/app/core/config.py` | 新增 `AI_JSON_MODE`（默认 true） |
| `backend/app/services/ai_config.py` | 运行时配置支持 `json_mode` |
| `backend/app/services/documents.py` | 上传根路径 `resolve()`，修复短路径误判 |
| `backend/app/services/external_import.py` | 同样修复外部 JSON 存储根路径 |
| `.env.example` | 增加 `AI_JSON_MODE=true` 与说明 |
| `backend/tests/test_questions.py` | 新增 8 个可靠性/闭环测试 |
| `backend/tests/test_ai_client.py` | 新增 3 个客户端测试（JSON 模式、降级、围栏提取） |
| `README.md` | 更新 AI 出题流程、错误分类、已知限制 |

### 归一化规则（只做等价转换，不伪造字段）

- `answer`：
  - 判断题：`true` / `"true"` / `"正确"` / `"T"` / `1` → `{"boolean": true}`；
  - 选择题：`["A","C"]` / `"A,C"` / `"A"` → `{"choices": [...]}`；
  - 简答题：字符串 → `{"text": "..."}`；
  - 已是对象则读取 `choices/choice_keys/keys/boolean/value/text/answer`。
- `options`：列表、`{"A": "文本"}` 字典、纯字符串列表均可；选项超过 8 个截断。
- `type`：`single_choice` / `single-choice` / `single` / `单选题` 等同义词。
- `difficulty`：`easy/简单/基础` 等映射；未知值回落 `medium`。
- `knowledge_point_ids`：字符串转列表；只有一个候选知识点时允许模型省略并补齐。
- 缺 `stem` / `explanation` / 正确答案等**不可推断字段**：该题跳过，不生成假题。
- 判断题选项不是规范 T/F 时丢弃，由数据库补标准「正确/错误」。

### 修复/重试预算

- 字段/JSON 解析失败：最多修复 1 次（`timings.format_repairs`）。
- 总模型调用仍受 `MAX_MODEL_CALLS=4` 限制。
- 修复后仍失败：任务 failed，`error` 包含字段位置/原因，`timings.error_kind` 记录类别。
- 单题语义不合格：跳过并写 `timings.warnings` / `skipped_count`；整批都不合格才失败。

---

## 三、错误分类与提示

| 场景 | `error_kind` | 用户可见提示（示例） |
| --- | --- | --- |
| 超时 | `timeout` | AI 请求超时（超过 90 秒），请稍后重试或减少知识点/题目数量 |
| 网络不可达 | `network` | 无法连接 AI 服务（网络错误），请检查网络、代理或 AI_API_BASE |
| 401/403 | `auth` | AI 认证失败，请检查 AI_API_KEY 是否有效 |
| 402/额度 | `quota` | AI 账户余额不足或额度已用尽（HTTP 402），请充值或更换 Key |
| 429 | `rate_limit` | AI 服务触发速率限制（HTTP 429），请稍后重试 |
| 5xx | `server` | AI 服务暂时不可用（HTTP 5xx），可稍后重试 |
| 上下文过长 | `bad_request` | AI 上下文超过模型上限，请减少一次生成的知识点/题目数量 |
| JSON 无法解析 | `invalid_json` | AI 返回内容不是有效 JSON（已尝试提取代码块/前后文本） |
| 字段形状错误 | `bad_shape` | AI 返回的 N 道题均未通过字段校验（字段: 原因） |
| 数据库写入 | `database` | 题目已生成但保存到数据库失败，请查看服务日志后重试 |

任务 `timings` 还会记录 `http_status`、`error_code`、`warnings`、`format_repairs`，不包含 Key、提示词或原文。

---

## 四、测试结果（实际执行）

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 后端全量 | `pytest`（`backend/`） | **97 passed** |
| 前端类型 | `tsc --noEmit` | 通过 |
| 前端 Lint | `eslint .` | 通过 |
| 前端单测 | `vitest run` | **30 passed（13 文件）** |
| 前端构建 | `vite build` | 通过 |
| Android 回归 | 真机 PA2553 启动 App | 显示“服务在线”（新后端） |

新增测试覆盖：

1. 真实模型标量 `answer: true` → `{"boolean": true}`，选项补 T/F。
2. 首次字段缺失 → 修复 1 次 → 成功，`format_repairs=1`。
3. 连续两次字段错误 → failed，错误含“字段校验”，无半成品，调用次数恰好 2。
4. 一批中 1 题非法题型 + 1 题合法 → 合法题保存，`skipped_count=1`，warning 可见。
5. 超时错误 → failed，`error_kind=timeout`。
6. 数据库写入失败 → failed，提示“保存到数据库失败”，`error_kind=database`，无题目。
7. JSON 提取：代码围栏、前后解释文字、嵌套对象、非法文本。
8. 提供商错误：402 余额、429 限流、401 认证、503 服务端、400 上下文。
9. JSON 模式请求体包含 `response_format`；400/422 明确不支持时降级一次，后续不再重复发送 response_format。

---

## 五、真实模型实测

### A. 隔离库完整闭环（真实 AI）

脚本：`phase4_full_loop.py`（临时 SQLite + 临时上传目录，真实 `deepseek-flash`）

```text
upload: 201
import status: completed stage: 资料已归档，AI 知识点草稿已生成
extracted knowledge points: 1
approved knowledge points: 1
generation: completed generated=2 skipped=0
saved questions: 2
practice start: 200
practice submit: 200
practice result: completed answered=1 score=100.0 records=1
```

流程覆盖：TXT 上传 → 自动归档 → AI 知识点提取 → 审核通过 → 真实 AI 出题 → 保存 →
练习抽题 → 提交答案 → 查看结果。**真实数据库与真实上传目录未被读写。**

### B. 真实模型出题单测（隔离库）

```text
model: deepseek-flash json_mode: True
status: completed
generated: 2
- single_choice answer={'choices': ['B']} options=4 kp=1
- true_false answer={'boolean': True} options=2 kp=1
```

### C. 修复前后对比

| 项 | 修复前 | 修复后 |
| --- | --- | --- |
| 判断题 `answer: true` | 整单 failed | 归一化为 `{"boolean": true}` 并保存 |
| JSON 前后有解释文字 | 直接失败 | 提取对象 |
| 单题非法 | 整单 failed | 跳过该题并记录，其他题保存 |
| 字段错误 | 无重试 | 最多修复 1 次 |
| 错误提示 | 统一“格式不符合要求” | 超时/网络/认证/余额/限流/5xx/字段/数据库分类 |
| 真实模型闭环 | 多次 failed | completed，2 题入库，练习 100 分 |

---

## 六、未解决 / 建议

1. **语义正确性仍靠人工审核**：结构校验不能证明题干、答案、解析在事实上绝对正确；
   生成题目仍全部是 `pending`。
2. **修复次数为 1**：极少数模型连续两次输出异常时会失败，需要用户重试；这是成本与稳定性的取舍。
3. **未做真机上的出题全流程**：手机端通过同一 API 已验证在线与同步；本轮出题闭环在隔离库用 HTTP 完成，
   未在手机上实际点“生成题目”（生成任务耗时较长，手机仅验证读写与练习）。
4. **未覆盖所有 OpenAI 兼容网关**：JSON 模式降级逻辑现覆盖 400/422 明确表明 response_format 不支持的响应；
   其他 400/422 参数错误不会降级。真实 422 网关尚未实测。
5. **未做真实模型批量稳定性统计**：本轮只做了小样本真实调用，未统计 20 题/多知识点的失败率与成本。
6. 建议后续：加入“修复提示包含上一次错误但不包含原文”的脱敏审计；对 20 题批量做 10 次采样统计；
   把出题失败类别展示在任务卡片上（目前已在 `error`/`timings`，前端只显示 error 文本）。

---

## 七、提交说明

本轮提交只包含代码、测试、文档和 `.env.example`：
不包含 `backend/data/ai_config.json`、`.env`、真实数据库、上传文件、日志、Key 或令牌。
真实数据库在测试前后保持：学科 10、章节 6、资料 2、知识点 78、题目 7、练习 3/6。
