# BioLearn AI 开发规则

## 1. 基本原则

- 增量开发，不重建项目，不覆盖用户已有代码/数据。
- 先读现有实现和测试，再修改。
- 不确定就记录假设，不伪造完成状态。
- 任何可能删除用户资料、数据库、上传文件或 Git 历史的操作，必须先确认。
- 当前有活跃 AI 任务时，禁止重启后端或运行会触发应用 lifespan 的测试。

## 2. 编码规范

### Python

- Python 3.12，类型标注优先。
- 业务规则放 `app/services`；路由只做 HTTP 适配。
- Pydantic schema 放 `app/schemas`；ORM 放 `app/models`。
- 不在路由里写复杂 SQL；不在 service 里拼 HTTP 响应。
- 时间使用 `app.db.base.utc_now`；不要用本地 `datetime.now()` 取代。
- 使用明确的错误码与中文用户消息，错误通过 `DomainError`/HTTP 处理器输出。

### TypeScript / React

- 保持 `strict`，不引入 `any` 逃避类型。
- 页面负责交互状态；API 调用集中在 `src/lib/api`。
- 保持现有深色生物绿视觉和组件风格。
- 表单必须可触屏、有标签、加载态和错误态。
- 不允许用前端数组模拟后端数据；失败时显示真实错误。

## 3. API 约定

- 基础前缀：`/api/v1`。
- 创建返回 `201`；删除返回 `204`；资源不存在 `404`；业务冲突 `409`；字段/父级关系 `422`。
- 错误体：

```json
{"detail":{"code":"...","message":"...","extra":...}}
```

- 上传使用 multipart：`file`、`subject_id`、`chapter_id`、`name`、`force`。
- 所有列表/详情响应必须显式定义 Pydantic response model。
- 不允许在 API 响应中返回 API Key、密码或密文。
- 资料/知识点删除必须保留默认保护，确认后才允许级联。

## 4. 数据库变更原则

- 只通过 Alembic 迁移修改结构；运行时禁止 `Base.metadata.create_all()`。
- 新迁移必须能从空库 upgrade；尽量验证 upgrade → downgrade → upgrade。
- 现有迁移不要改写；新增 revision。
- UUID 主键、UTC 时间戳、外键 `ON DELETE` 策略必须明确。
- 删除学科/章节/资料/知识点的策略必须在迁移和服务层同时考虑。
- 测试数据库使用临时 SQLite；不得对真实 `backend/data/biolearn.db` 执行破坏性测试。
- 未完成迁移/数据修复前，不直接改真实数据库状态。

## 5. 文件与安全

- 上传目录由 `UPLOAD_DIR` 配置，默认 `backend/data/uploads`。
- 数据库只存元数据/分块，不存文件二进制。
- 文件名必须清理，存储名由服务端 UUID 生成。
- 校验扩展名、实际内容签名、大小、空文件、路径穿越。
- `.env`、`backend/data/ai_config.json`、数据库、上传文件、日志、临时文件不得提交。
- 不允许在日志中记录 API Key、完整 prompt 或敏感文档正文。
- API Key 只能存在后端配置或 DSH secret 中；前端只显示是否配置。

## 6. AI 规则

- 先检查 AI 是否配置；未配置时返回明确错误，不生成假结果。
- 所有模型输出必须经过 Pydantic 结构校验。
- 页码/幻灯片/来源 chunk 由服务端注入，不信任模型给出的位置。
- 引文必须能在原文中匹配；不匹配就丢弃并标记待确认。
- 合并结果必须引用已有来源 ID，不得新增无来源事实。
- 重新提取时只替换未审核 AI 草稿，保留已审核/人工知识点。
- 低置信度只是辅助信号，不能作为正确性证明。
- mock 测试要明确标记；没有真实 Key 时不得声称完成真实模型联调。

## 7. 测试要求

- 后端：pytest + 临时 SQLite/临时上传目录；覆盖 CRUD、校验、状态、失败、来源、审核、迁移。
- 前端：Vitest + Testing Library；至少覆盖关键页面成功/空/错误/交互。
- 每次交付运行：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest

cd ..\frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

- **例外**：如果真实库存在运行中的解析/AI 任务，不要运行后端 TestClient/pytest；先保存现场或使用隔离环境。
- 真实文件解析需记录文件名、页数/分块数、失败原因；不要把未验证格式写成完成。

## 8. Git 与交接规则

- 禁止 `git reset --hard`、`git clean -fd`、强制 push、删除用户修改。
- 当前仓库没有 commits；在用户确认前不要擅自提交全部文件。
- 提交前检查：

```powershell
git status --porcelain -uall
git check-ignore -v .env backend\data\biolearn.db backend\data\uploads frontend\node_modules
```

- 只暂存源码、测试、文档和示例配置；不要提交 `.env`、数据库、上传 PDF/Office 文件、AI 配置 Key、日志、`work/`。
- 数据库和上传目录备份到加密/受控位置；`ai_config.json` 含密钥，必须特别保护。
- 交接文档必须反映实际状态，特别是未完成任务、模型是 mock 还是真实、哪些格式未验证。
