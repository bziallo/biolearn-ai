# BioLearn AI 阶段二验收报告（数据库 / 学科 / 章节）

日期：2026-10-21
版本：V1.0（迁移 head：`0009_question_bank`）
结论：**阶段二的数据库、学科管理、章节管理功能在实际代码中已全部实现，本次为核查 + 修复 + 实测验证，未重写。**

---

## 一、先说结论：阶段二此前已经完成，不是从零开始

用户要求“第二阶段：数据库、学科管理与章节管理”。核查发现这些能力在 V1.0 中已经存在并通过测试：

| 需求 | 实际位置 | 状态 |
| --- | --- | --- |
| Subject 模型（id/name/description/color/icon/sort_order/时间戳） | `backend/app/models/subject.py` | 已实现 |
| Chapter 模型（含 parent_id、任意层级、时间戳） | `backend/app/models/chapter.py` | 已实现 |
| SQLite + SQLAlchemy + Alembic | `backend/app/db/`、`backend/alembic/versions/0001–0009` | 已实现 |
| 循环父级 / 跨学科父级保护 | `backend/app/services/chapters.py::_validate_parent` | 已实现（测试覆盖） |
| 10 个可编辑初始学科 | 迁移 `0003_seed_initial_subjects`（幂等，只执行一次） | 已实现 |
| 学科列表/新建/编辑/详情/删除确认/章节数/空状态/表单校验/加载/提示 | `frontend/src/pages/SubjectsPage.tsx`、`components/SubjectForm.tsx` | 已实现 |
| 章节树（≥3 级）、新建/编辑/删除/子章节/排序/详情/所属学科/删除保护 | `frontend/src/pages/SubjectDetailPage.tsx`、`components/ChapterTree.tsx`、`ChapterForm.tsx` | 已实现 |
| REST API（subjects/chapters/health） | `backend/app/api/v1/{subjects,chapters,health}.py` | 已实现，见第四节 |
| 前端全部调用真实 API，无假数据 | `frontend/src/lib/api/*` | 已确认 |

所以本次没有重复造模型、迁移或页面，只做**验证 + 修复真实缺陷 + 清理验收数据**。

---

## 二、本次实际修改的内容

### 1. 真实缺陷修复：无标题占位符的 PPTX 无法生成章节树

- 现象：手工制作的 PPTX（文本框排版、没有标题占位符）解析出的段落全部是
  `paragraph`，没有任何 `heading`；`build_outline` 因此回退到
  `filename` 来源，只能建 1 个“资料标题章节”，自动建章形同虚设。
- 原因：`backend/app/services/parsing.py::_parse_pptx` 只在
  `slide.shapes.title` 存在时输出 heading。
- 修复：没有标题占位符时，把该页**第一个非空文本框的第一行**作为该页 heading
  （`level=1`），其余段落保持 `paragraph`。有标题占位符时行为完全不变。
- 验证：新增 `backend/tests/test_parsing_pptx_headings.py`（3 项）：
  - 无标题占位符 → 每个非空页都有 heading，标题取首行；
  - 有标题占位符 → 仍然只有 1 个 heading，正文不被误升级；
  - heading/paragraph 类型保持正确。
- 端到端：修复后同一份合成 PPTX 经 `/api/v1/imports` 得到
  `outline_source=slide_titles`，自动创建 2 个章节（含子章节），
  修复前只能得到 `filename` + 1 个章节。

### 2. 前端测试改成单一事实来源

`frontend/src/components/DocumentUploadCard.test.tsx` 之前把
`http://127.0.0.1:8000/api/v1/documents` 写死。本机 `.env` 把
`VITE_API_BASE_URL` 配成 `http://localhost:3000/api/v1` 后该断言失败。
改为断言 `${API_BASE_URL}/documents`，与产品代码的配置机制一致。

### 3. 验收辅助脚本（新增）

| 文件 | 作用 |
| --- | --- |
| `scripts/make_acceptance_sample.py` | 生成合成 PPTX + `schema_version 1.0` 知识点 JSON，供无 AI 情况下验证全链路 |
| `scripts/cleanup_acceptance_data.py` | 按白名单标记清理本次验收产生的合成数据（默认 dry-run，`--apply` 才删除） |
| `scripts/publish_release.py`、`scripts/fix_release_asset.py`、`publish-release.bat`、`push-tag.bat` | 上一轮 GitHub Release 发布工具（顺带提交） |

---

## 三、数据库与存储

- 数据库：SQLite，`backend/data/biolearn.db`（相对路径按 `backend/` 解析）。
- 迁移：`backend/alembic/versions/`，head 为 `0009_question_bank`；`alembic/env.py` 使用规范化后的绝对路径。
- 上传文件：`backend/data/uploads/`（`UPLOAD_DIR`）。
- 外键：`PRAGMA foreign_keys=ON`（`app/db/session.py`），`chapters.subject_id` 级联删除、`chapters.parent_id` 自关联（`ondelete` 由服务层保证子树一致）。
- 初始 10 个学科由迁移 `0003` 插入，带固定 UUID（`uuid5`），重复执行不会重复插入；可在页面随意编辑或删除。

### 本次实测的持久化证据（跨进程）

用独立临时库 `s2_persist/persist.db`（不触碰真实库）：

```
进程 1: create_subject(持久化验证学科) -> create_chapter(第一章) -> create_chapter(第一节, parent=第一章)
进程 2（新进程，直接重连库）: list_subjects -> [('持久化验证学科', 2)]
                              list_chapter_tree -> 第一章 > 第一节
```

结论：学科与章节确实落盘，重启进程后仍可读取，父子关系由稳定 UUID 保持。

---

## 四、后端 API（真实地址与职责）

服务运行在 `http://127.0.0.1:8000`，API 前缀 `/api/v1`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查，返回 status/version/environment |
| GET | `/api/v1/subjects` | 学科列表（含 `chapter_count`，按 sort_order 排序） |
| POST | `/api/v1/subjects` | 新建学科（name 必填，color 需 `#rgb`/`#rrggbb`，sort_order 自动 +10） |
| GET | `/api/v1/subjects/{id}` | 学科详情 |
| PATCH | `/api/v1/subjects/{id}` | 局部更新 |
| DELETE | `/api/v1/subjects/{id}?cascade=true` | 删除；有章节时返回 409 `subject_has_chapters`，需显式 cascade |
| GET | `/api/v1/subjects/{id}/chapters` | 章节树（嵌套 `children`） |
| POST | `/api/v1/subjects/{id}/chapters` | 新建章节（可选 parent_id） |
| GET | `/api/v1/chapters/{id}` | 章节详情（含学科、父章节、路径、后代数） |
| PATCH | `/api/v1/chapters/{id}` | 更新名称/简介/父级 |
| DELETE | `/api/v1/chapters/{id}?cascade=true` | 删除；有子章节时返回 409 `chapter_has_children` |
| POST | `/api/v1/chapters/{id}/move` | 调整同级顺序（up/down） |

错误统一返回 `{"detail": {"code": "...", "message": "...", ...}}`。

本次实测（真实服务）：

- `GET /api/v1/health` → 200 `{"status":"ok", ...}`
- `GET /api/v1/subjects` → 200，10 个学科，`chapter_count` 与数据库一致
- `GET /api/v1/subjects/{id}/chapters` → 200，三级树结构正确（`阶段二验收外部JSON > 阶段二验收章节 > 验收子章节`）

---

## 五、如何启动

### 电脑端（生产，单端口）

```
双击 start.bat
浏览器访问 http://127.0.0.1:8000/
```

### 开发模式（前端 5173 + 后端 8000）

```
双击 start-dev.bat
浏览器访问 http://127.0.0.1:5173/
```

注意：本机 `.env` 目前把 `VITE_API_BASE_URL` 指向
`http://localhost:3000/api/v1`（疑似旧配置）。若开发模式下请求失败，
请把它改成 `http://127.0.0.1:8000/api/v1` 或留空（留空时前端按同源
`/api/v1` 访问）。我没有擅自改动你的 `.env`。

---

## 六、测试执行结果（实际运行）

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 学科/章节/迁移 | `pytest tests/test_subjects.py tests/test_chapters.py tests/test_migrations.py` | **12 passed** |
| 解析与导入回归 | `pytest tests/test_parsing_pptx_headings.py tests/test_parsing.py tests/test_imports.py` | **27 passed** |
| 后端全量 | `pytest`（`backend/`，隔离临时库） | **80 passed** |
| 前端类型检查 | `tsc --noEmit` | 通过 |
| 前端 ESLint | `eslint .` | 通过 |
| 前端 Vitest | `vitest run` | **12 个文件 / 26 passed** |
| 前端生产构建 | `vite build` | 通过（62 模块） |

测试覆盖的学科/章节要点（已有测试 + 本次新增）：

1. 学科 CRUD（`test_subject_crud_counts_and_cascade_confirmation`）
2. 章节 CRUD 与三级树（`test_chapter_crud_three_level_tree_and_detail`）
3. 必填字段校验：空白名称 422、非法颜色 422、PATCH name=null 422
4. 不存在的学科/章节 404 `subject_not_found` / `chapter_not_found`
5. 非法父章节 422 `parent_not_found`
6. 循环引用 422 `chapter_cycle`（自己→自己、祖先→后代）
7. 跨学科父级 422 `parent_subject_mismatch`
8. 外键与删除策略：409 `subject_has_chapters` / `chapter_has_children`，cascade 后计数归零
9. 数据持久化：本次跨进程实测（第三节）
10. API 错误响应结构 `detail.code/message`

---

## 七、端到端实测（用合成样例，不污染真实内容）

因为本机 AI 配置在出题时返回格式错误，本次不依赖 AI，使用
`scripts/make_acceptance_sample.py` 生成合成 PPTX 与知识点 JSON：

| 步骤 | 结果 |
| --- | --- |
| 上传合成 PPTX（auto_create） | 201 → `completed`；修复后识别 `outline_source=slide_titles`，自动建 2 个章节 |
| 重复上传同一文件 | 201，复用原资料，`duplicate=true`，不重复建章节 |
| 上传合成外部 JSON（`schema_version 1.0`） | 201 `awaiting_confirmation`，预览 1 条知识点、0 重复 |
| 非法版本 / 语法错误 JSON | 422 `external_json_invalid` / `invalid_json` |
| 确认归档 | 200 `completed`，建 2 个章节 + 1 条 `pending` 知识点（`source_quote_verified=false`） |
| 知识点审核 | `pending → approved`；编辑后自动回 `pending` 且清空 `published_at`；重新通过 |
| 清理 | 删除合成资料 5 份、章节 7 个、知识点 1 条；真实资料 2 份、知识点 78 条（39 approved + 38 pending + 1 needs_revision）、题目 7 道、答题记录 6 条保持不变 |

---

## 八、如何手动验证学科与章节

1. `start.bat` 启动，打开 `http://127.0.0.1:8000/`。
2. 顶部导航“学科” → 点“新建学科”，填写名称/简介/颜色 → 列表出现新学科，`章节 0`。
3. 点进该学科 → “新建章节” → 输入“第一章” → 树中出现根章节。
4. 选中“第一章” → “新建子章节” → 输入“第一节”；再对“第一节”新建“1.1”——形成三级树。
5. 用上下箭头调整同级顺序，刷新页面顺序保持。
6. 选中章节 → 右侧显示所属学科、父章节路径、后代数量。
7. 删除含子章节的章节 → 提示“仍有 N 个后代”，需确认后级联删除。
8. 删除含章节的学科 → 提示章节数量，需确认后级联删除。
9. 直接访问 `http://127.0.0.1:8000/api/v1/subjects` 可与页面数据对照，确认来自同一数据库。

---

## 九、尚未解决的问题与风险

1. **开发模式 API 地址**：本机 `.env` 的 `VITE_API_BASE_URL` 指向
   `http://localhost:3000/api/v1`，与后端 8000 不一致；若使用 5173 开发页面，
   请改为 8000 或留空。生产单端口模式不受影响。
2. **无标题占位符 PPT 的启发式**：现在把每页首个文本框首行当标题。
   若某页首行其实是正文，会多出一个章节候选；导入页仍可预览/取消。后续可增加
   “字号/是否独占一行”判断提高准确率。
3. **AI 功能**：本轮验收中真实模型出题返回格式错误（与阶段二无关，已在 V1.0 已知问题中记录）；
   知识点 AI 提取需要配置可用模型。
4. **中文文件名上传乱码**：本轮用 curl/bridge 上传中文文件名时，服务端记录为乱码
   （`½×¶ÎÑéÊÕ…`）。通过浏览器上传不受影响（浏览器按 UTF-8 multipart 提交），
   但从第三方脚本上传时建议使用 ASCII 文件名；后续可在后端对 `filename*` 做兼容解码。
5. **未提交 Git**：本轮改动（`parsing.py` 修复、新测试、验收脚本）尚未 commit，等你确认后再提交。
   你本地的 `work/`（469 MB）和 `outputs/` 未纳入版本库。

---

## 十、本次修改文件清单

```
M backend/app/services/parsing.py                     # 无标题占位符 PPTX 兜底标题
M frontend/src/components/DocumentUploadCard.test.tsx # 断言改用 API_BASE_URL
A backend/tests/test_parsing_pptx_headings.py         # 3 项新增测试
A scripts/make_acceptance_sample.py                   # 合成样例生成
A scripts/cleanup_acceptance_data.py                  # 验收数据清理（白名单 + dry-run）
A scripts/publish_release.py                          # GitHub Release（上一轮遗留）
A scripts/fix_release_asset.py                        # Release 附件修复（上一轮遗留）
A publish-release.bat / push-tag.bat                  # 上一轮遗留启动脚本
A docs/PHASE2_ACCEPTANCE.md                           # 本报告
```
