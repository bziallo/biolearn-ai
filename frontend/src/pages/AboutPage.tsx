import { NavLink } from 'react-router-dom'

const boundaries = [
  {
    module: 'frontend/',
    role: 'React 界面与 API 客户端',
    rule: '只通过版本化 HTTP API 读写数据，不直接接触数据库。',
  },
  {
    module: 'backend/app/api/',
    role: 'FastAPI 路由与请求/响应模型',
    rule: '处理参数校验、状态码与依赖注入，不写业务编排。',
  },
  {
    module: 'backend/app/services/',
    role: '解析、分块、AI 与知识点业务规则',
    rule: '文件安全、来源追踪、AI 输出校验、合并去重与审核保护。',
  },
  {
    module: 'backend/app/schemas/',
    role: 'Pydantic 请求与响应契约',
    rule: '约束必填字段、长度、颜色格式与嵌套树结构。',
  },
  {
    module: 'backend/app/models/',
    role: 'SQLAlchemy ORM 模型',
    rule: '保存持久化结构；结构变化必须通过 Alembic 迁移。',
  },
  {
    module: 'backend/app/db/',
    role: '引擎、会话与声明式基类',
    rule: '启用 SQLite 外键，统一管理连接生命周期，测试使用临时数据库。',
  },
]

export function AboutPage() {
  return (
    <div className="about">
      <header className="page-head">
        <p className="eyebrow">Architecture</p>
        <h1>先把边界划清楚，再长业务。</h1>
        <p className="lede">
          单仓库、前后端分离、SQLite 本地持久化。当前阶段已经接通资料上传、解析分块、
          AI 知识点草稿与人工审核，后续的检索与学习产物继续沿同一路径扩展。
        </p>
      </header>

      <section className="flow-panel" aria-label="请求链路">
        <div className="flow-node">
          <span>01</span>
          <strong>React + Vite</strong>
          <small>页面与交互</small>
        </div>
        <span className="flow-arrow" aria-hidden="true">
          →
        </span>
        <div className="flow-node">
          <span>02</span>
          <strong>API Client</strong>
          <small>typed fetch</small>
        </div>
        <span className="flow-arrow" aria-hidden="true">
          →
        </span>
        <div className="flow-node">
          <span>03</span>
          <strong>FastAPI</strong>
          <small>/api/v1</small>
        </div>
        <span className="flow-arrow" aria-hidden="true">
          →
        </span>
        <div className="flow-node">
          <span>04</span>
          <strong>SQLAlchemy</strong>
          <small>SQLite + Alembic</small>
        </div>
      </section>

      <section className="boundary-section">
        <div className="section-head">
          <p className="eyebrow">Module boundaries</p>
          <h2>每个目录只做一件事</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">目录</th>
                <th scope="col">职责</th>
                <th scope="col">约束</th>
              </tr>
            </thead>
            <tbody>
              {boundaries.map((item) => (
                <tr key={item.module}>
                  <td>
                    <code>{item.module}</code>
                  </td>
                  <td>{item.role}</td>
                  <td>{item.rule}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="principles">
        <h2>阶段三的三个约束</h2>
        <ul>
          <li>上传文件只保存到服务器磁盘，数据库保存元数据、分块和来源位置。</li>
          <li>AI 输出必须先通过结构化校验；没有配置模型时不会生成伪造结果。</li>
          <li>AI 结果进入待审核区，重新提取会保留已审核和人工知识点。</li>
        </ul>
        <NavLink className="text-link" to="/subjects">
          → 打开学科管理
        </NavLink>
      </section>
    </div>
  )
}
