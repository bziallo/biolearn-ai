# BioLearn AI V1.0 发布说明

版本：V1.0（功能冻结）
日期：2026-10-21
迁移版本：`0009_question_bank`

## 一、V1.0 实际完成的功能

| 模块 | 功能 | 状态 |
| --- | --- | --- |
| 学科/章节 | 学科与任意层级章节的增删改查 | 完成 |
| 资料导入 | PDF / DOCX / PPTX / TXT / Markdown 上传、签名校验、去重、解析、分块 | 完成 |
| 智能导入 | 预设章节、自动建章、智能归档三种模式；预览确认；导入偏好 | 完成 |
| AI 知识点提取 | 整章分析 → 分块并发提取 → 合并去重 → 待审核草稿；取消/重试/计时 | 完成 |
| 外部 AI JSON 知识点 | `schema_version 1.0` 校验、预览、章节匹配、重复策略、原始文件留档、模板下载 | 完成 |
| 知识点审核 | 树/详情/编辑/逐题与批量审核/合并/删除保护/搜索筛选；编辑后自动重审 | 完成 |
| 题库管理 | 手动建题、结构化选项/答案/评分规则、搜索筛选、审核、批量审核、重复提示、重新生成 | 完成 |
| AI 出题 | 仅用 approved 知识点、结构校验、题型/知识点归属校验、去重、取消、失败重试、最多 4 次模型调用 | 代码完成；**真实模型连续失败，质量未验证** |
| 练习 | 从 approved 题库抽题、自动判分（单选/多选/判断）、简答人工评分、全部选项复盘、错题本、错题再练 | 完成 |
| 部署 | 单端口本地 Web 部署、一键脚本、迁移前自动备份、备份/恢复脚本 | 完成 |
| 外部题目导入 | 题目 JSON 批量导入 | **未实现**（V1.1） |
| 学习分析 | 掌握度、间隔复习、自适应 | **未实现**（V1.1） |

## 二、端到端测试与构建结果

### 自动化测试

| 项目 | 结果 |
| --- | --- |
| 后端 pytest | **77 passed**（隔离临时库） |
| 前端 Vitest | **26 passed**（12 个文件） |
| 前端 TypeScript | 通过 |
| 前端 ESLint | 通过 |
| 前端生产构建 | 通过（62 个模块） |
| 迁移 | 空库 upgrade/downgrade/upgrade 通过；真实库副本 `0008→0009→0008→0009` 通过 |

### 真实环境验收（`start.bat` 启动，端口 8000）

| 验收项 | 结果 |
| --- | --- |
| 单端口首页 / 深链 / 静态资源 | `/`、`/practice`、`/questions` 200；`/assets/*.js` 200 |
| API 与 SPA 分离 | `/api/v1/nope` 返回 JSON 404；`/health` 不被 SPA 吞掉 |
| 重复上传课件 | 复用原资料，`duplicate=true`，不重复建章 |
| 外部 JSON 新导入 | 预览 → 确认 → 建 2 章节 + 1 条 pending 知识点 |
| 外部 JSON 重复导入 | 识别重复文件与重复知识点 |
| 知识点审核 | pending→approved；编辑后回 pending；重新 approved |
| 题目去重与校验 | 重复题干标记 `duplicate_of_id`；非法答案 422 |
| 练习判分 | 判断题答错 → `is_correct=false`、0 分；重复提交 409 |
| 重启前后端 | 数据（学科/知识点/题目/练习/错题/导入）全部保留 |
| 备份 → 恢复 | 完整性检查通过，数据完整，自动迁移 |
| 端口占用 | `start.bat` 给出明确错误并退出 |
| AI 出题（真实模型） | **失败**：结构校验未通过（两次），错误信息已增强 |

## 三、Windows 本地部署与启动步骤

前置：Windows 10/11、Python 3.12+（加入 PATH）、Node.js 20.19+（仅构建前端时需要）。

```text
1. 解压/复制项目到本地目录（建议非中文路径）
2. 双击 install.bat      # 创建 backend\.venv 并安装依赖；必要时构建前端
3. 双击 start.bat        # 初始化/升级数据库 → 启动 → 自动打开浏览器
4. 浏览器访问 http://127.0.0.1:8000/
5. 需要 AI 时：进入“AI 设置”填写 API Base / Key / 模型（只存后端）
```

停止：关闭窗口或双击 `stop.bat`。

脚本说明：

| 脚本 | 说明 |
| --- | --- |
| `install.bat` | 安装依赖，缺前端构建时调用 `build_frontend.bat` |
| `build_frontend.bat` | `pnpm`/`npm` 安装并构建到 `frontend/dist` |
| `start.bat` | 端口检查 → `scripts/prepare_env.py` → `scripts/run_backend.py` |
| `stop.bat` | `scripts/stop_services.py` 结束 8000 端口进程 |
| `backup.bat` | `scripts/backup_data.py` |
| `restore.bat` | `scripts/restore_data.py` |
| `start-dev.bat` | 后端 `--reload` + Vite 5173（开发用） |

## 四、数据备份与恢复

### 备份

```powershell
stop.bat
backend\.venv\Scripts\python.exe scripts\backup_data.py --output-dir D:\BioLearnBackup
```

产出：`<输出目录>/<时间戳>/biolearn.db`（在线备份 + integrity_check）、`uploads/`、`ai_config.json`、`.env.example`。
不自动复制 `.env`（避免密钥外泄）。

### 恢复

```powershell
stop.bat
restore.bat        # 拖入备份目录 → 自动校验 → 移开旧数据 → 恢复 → 迁移
start.bat
```

旧数据保留在 `backend/data/_restore_previous_<时间>/`，可回退。

### 升级

- 更新程序后直接 `start.bat`：发现迁移差异会先备份到 `backend/data/pre_migration_backups/<时间>`。
- 迁移只新增表/列，不删除既有资料、知识点、题目、答题记录。
- 已实测：备份 → 恢复 → 重启后数据完整。

## 五、配置文件说明（`.env`）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `APP_ENV` / `DEBUG` | production / false | 运行环境 |
| `DATABASE_URL` | `sqlite:///./data/biolearn.db` | 相对路径按 `backend/` 解析 |
| `CORS_ORIGINS` | 本地 8000/5173 | 跨域白名单（另允许 `127.0.0.1`/`localhost` 任意端口） |
| `VITE_API_BASE_URL` | 空 | 空 = 同源 `/api/v1`；开发模式填 `http://127.0.0.1:8000/api/v1` |
| `SERVE_FRONTEND` | true | 后端是否托管 `frontend/dist` |
| `FRONTEND_DIST_DIR` | `./frontend/dist` | 前端构建产物目录 |
| `LOG_DIR` | `./data/logs` | 日志目录 |
| `UPLOAD_DIR` | `./data/uploads` | 资料存储 |
| `MAX_UPLOAD_BYTES` | 26214400 | 单文件上限 |
| `AI_PROVIDER` / `AI_API_BASE` / `AI_MODEL` | — | AI 服务（也可在页面配置） |
| `AI_API_KEY` | 空 | 仅后端保存，不入前端 |
| `AI_CONFIG_PATH` | `./data/ai_config.json` | 页面保存的运行时配置 |
| `AI_TIMEOUT_SECONDS` / `AI_MAX_RETRIES` | 90 / 2 | 超时与重试 |
| `AI_EXTRACTION_CONCURRENCY` | 3 | 知识点提取并发 |
| `AI_MERGE_BATCH_SIZE` / `AI_OUTLINE_MAX_CHARS` | 40 / 15000 | 合并与提纲限制 |

安全：`.env`、`ai_config.json`、数据库、上传文件、日志、`dist/` 均被 `.gitignore` 排除，`git check-ignore` 已实测。

## 六、已知问题与未验证事项

### 已知问题

1. **AI 出题真实模型失败**：2026-10-21 两次调用均返回“AI 出题返回格式不符合要求”，任务正确标记失败且无半成品；已增强错误信息（最多 3 个 Schema 错误位置）。
2. 外部题目导入未实现，只有知识点 JSON 导入。
3. 无用户认证，仅适合本机单用户；服务默认只监听 `127.0.0.1`。
4. 简答题只有人工评分，无自动评分。
5. 练习章节过滤是精确匹配，不含子章节。
6. 没有掌握度、间隔复习、自适应推荐。
7. 任务使用 FastAPI BackgroundTasks，无持久队列；重启会把运行中任务标记失败。
8. 停止 AI 为协作式，最长等待一次模型超时（默认 90 秒）。
9. 结构化输出依赖模型遵循 JSON；未接入 JSON Schema / 结构化输出模式。

### 未验证事项

- `install.bat` 未在全新机器上从零执行（本机已有 `.venv` 与 `dist`）。
- 全新课件文件的首解析 → 建章 → AI 提取链路本轮未执行。
- 前端浏览器交互回归只有组件测试，没有自动化 E2E。
- 远程主机访问、防火墙、多用户并发未验证。
- AI 知识点提取与出题的真实质量、成本、失败率未系统评估。

### 验收遗留数据（保留，未删除）

- 章节：`验收临时外部JSON`、`验收临时章节`
- 知识点：`验收临时知识点`（approved）
- 资料：`验收临时外部JSON`
- 题目：2 道 `验收临时题…`（rejected）
- 练习：1 个验收会话
- 如需清理，请在界面中删除或从备份恢复；脚本没有自动删除。

## 七、V1.1 建议任务

1. **修复 AI 出题**：接入 JSON Schema 结构化输出或更强的解析/重试；复现并记录失败样例。
2. 外部题目 JSON 导入（与知识点导入一致的预览/重复/审核流程）。
3. 学习分析：掌握度、错题重练计划、间隔复习（基于 `practice_answers`）。
4. 简答题 AI 辅助评分 + 人工复核（明确标注为辅助）。
5. 题目版本与变更历史、重复题目合并。
6. 练习按章节子树抽题、按知识点权重组卷。
7. 持久任务队列（可选 Redis/RQ），多进程部署。
8. 可选用户认证与本机多用户隔离。
9. 自动化 E2E（Playwright）覆盖导入→审核→出题→练习。
10. 纯视觉升级（统一组件样式、移动端细节）。
11. 安装包/便携包（内嵌 Python 运行时与前端构建产物）。
12. DSF1017 真实联调与用量/成本统计。

## 八、本次修改文件清单

新增：

- `install.bat`、`build_frontend.bat`、`start.bat`、`stop.bat`、`backup.bat`、`restore.bat`、`start-dev.bat`
- `scripts/run_backend.py`、`scripts/prepare_env.py`、`scripts/stop_services.py`、`scripts/backup_data.py`、`scripts/restore_data.py`
- `backend/tests/test_static_hosting.py`
- `docs/RELEASE_NOTES_V1.0.md`（本文件）

修改：

- `backend/app/main.py`：SPA 托管与回退、CORS 本地正则
- `backend/app/core/config.py`：`serve_frontend`、`frontend_dist_dir`、`log_level`、`log_dir`、`resolved()`
- `backend/app/db/session.py`：`normalize_database_url`、`resolve_sqlite_path`，相对路径按 `backend/` 解析
- `backend/alembic/env.py`：迁移使用规范化数据库 URL
- `backend/app/services/documents.py`、`backend/app/services/external_import.py`、`backend/app/services/ai_config.py`：统一路径解析
- `backend/app/services/question_generation.py`：出题失败信息包含 Schema 错误摘要
- `frontend/src/lib/api/client.ts`：生产同源 API 地址
- `.env.example`：V1.0 配置模板（新增托管/日志/同源说明）
- `.gitignore`：新增 `backups/`、本地启动日志
- `README.md`、`docs/DEVELOPMENT_STATUS.md`、`docs/AI_HANDOFF.md`
