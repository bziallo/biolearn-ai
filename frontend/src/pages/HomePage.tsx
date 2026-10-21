import { useEffect, useState } from 'react'
import { Link, NavLink } from 'react-router-dom'

import { API_BASE_URL } from '../lib/api/client'
import { getHealth, type HealthResponse } from '../lib/api/health'

type HealthState =
  | { status: 'loading' }
  | { status: 'online'; data: HealthResponse; latencyMs: number }
  | { status: 'offline'; message: string }

const roadmap = [
  {
    phase: '阶段一',
    title: '工程底座',
    detail: '已完成：单仓库、健康检查、测试与迁移链路。',
    current: false,
  },
  {
    phase: '阶段二',
    title: '学科与章节',
    detail: '已完成：真实数据库、树形章节、排序与删除保护。',
    current: false,
  },
  {
    phase: '阶段三',
    title: '资料与 AI 知识点',
    detail: '上传解析、来源分块、AI 多阶段提取与人工审核。',
    current: true,
  },
  {
    phase: '下一阶段',
    title: '检索与学习',
    detail: '检索引用、问答、闪卡与复习进度。',
    current: false,
  },
]

export function HomePage() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    const startedAt = performance.now()

    getHealth(controller.signal)
      .then((data) => {
        setHealth({
          status: 'online',
          data,
          latencyMs: Math.round(performance.now() - startedAt),
        })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setHealth({
          status: 'offline',
          message: error instanceof Error ? error.message : '未知错误',
        })
      })

    return () => controller.abort()
  }, [])

  return (
    <div className="home">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">BioLearn AI · 阶段三</p>
          <h1>
            把生物医学资料，
            <span>变成真正学会的知识。</span>
          </h1>
          <p className="lede">
            面向医学生与生命科学学习者的本地优先知识工作台。资料可追溯，回答有出处，
            学习进度留在自己的数据库里。
          </p>
          <div className="hero-actions">
            <NavLink className="button button-primary" to="/subjects">
              进入学科管理
            </NavLink>
            <NavLink className="button button-ghost" to="/about">
              查看技术架构
            </NavLink>
          </div>
        </div>

        <aside className="status-card" aria-live="polite">
          <div className="status-card-head">
            <span className="status-title">后端连接</span>
            <span className={`status-dot status-${health.status}`} />
          </div>

          {health.status === 'loading' && (
            <p className="status-message">正在探测 API…</p>
          )}

          {health.status === 'online' && (
            <>
              <p className="status-message status-ok">服务在线</p>
              <dl className="status-grid">
                <div>
                  <dt>服务</dt>
                  <dd>{health.data.service}</dd>
                </div>
                <div>
                  <dt>版本</dt>
                  <dd>{health.data.version}</dd>
                </div>
                <div>
                  <dt>环境</dt>
                  <dd>{health.data.environment}</dd>
                </div>
                <div>
                  <dt>延迟</dt>
                  <dd>{health.latencyMs} ms</dd>
                </div>
              </dl>
            </>
          )}

          {health.status === 'offline' && (
            <>
              <p className="status-message status-error">无法连接后端</p>
              <p className="status-detail">{health.message}</p>
            </>
          )}

          <code className="endpoint">GET {API_BASE_URL}/health</code>
        </aside>
      </section>

      <section className="pillars" aria-label="产品方向">
        <article className="pillar">
          <span className="pillar-index">01</span>
          <h2>
            <Link className="pillar-heading-link" to="/subjects">
              学科结构
            </Link>
          </h2>
          <p>用学科与树形章节先搭好知识地图，后续资料才有归属。</p>
          <span className="pillar-tag pillar-tag-active">已上线</span>
        </article>
        <article className="pillar">
          <span className="pillar-index">02</span>
          <h2>资料进得去</h2>
          <p>PDF、Office、文本与 Markdown 解析为可追溯分块，AI 再构建知识点。</p>
          <span className="pillar-tag pillar-tag-active">已上线</span>
        </article>
        <article className="pillar">
          <span className="pillar-index">03</span>
          <h2>答案查得到</h2>
          <p>检索增强问答，每个关键结论都能指回原始段落。</p>
          <span className="pillar-tag">规划中</span>
        </article>
      </section>

      <section className="roadmap" id="roadmap">
        <div className="section-head">
          <p className="eyebrow">Roadmap</p>
          <h2>一次只交付一个可靠阶段</h2>
          <p>
            当前已打通资料解析、AI 知识点草稿与人工审核；检索与学习功能继续分阶段推进。
          </p>
        </div>

        <ol className="timeline">
          {roadmap.map((item) => (
            <li
              className={item.current ? 'timeline-item is-current' : 'timeline-item'}
              key={item.phase}
            >
              <span className="timeline-phase">{item.phase}</span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.detail}</p>
              </div>
              {item.current && <span className="timeline-badge">当前</span>}
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
