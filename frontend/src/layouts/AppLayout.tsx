import { NavLink, Outlet } from 'react-router-dom'

import { ToastProvider } from '../components/ToastProvider'

function navClassName({ isActive }: { isActive: boolean }) {
  return isActive ? 'nav-link is-active' : 'nav-link'
}

function tabClassName({ isActive }: { isActive: boolean }) {
  return isActive ? 'tab-bar-link is-active' : 'tab-bar-link'
}

const PRIMARY_LINKS = [
  { to: '/', label: '首页', icon: '🏠', end: true },
  { to: '/subjects', label: '学科', icon: '📚', end: false },
  { to: '/import', label: '导入', icon: '⬆', end: false },
  { to: '/practice', label: '练习', icon: '✎', end: false },
  { to: '/questions', label: '题库', icon: '▤', end: false },
  { to: '/settings/connection', label: '连接', icon: '⚙', end: false },
]

export function AppLayout() {
  return (
    <ToastProvider>
      <div className="app-shell">
        <header className="site-header">
          <NavLink className="brand" to="/" aria-label="BioLearn AI 首页">
            <span className="brand-mark" aria-hidden="true">
              B
            </span>
            <span className="brand-text">
              BioLearn <strong>AI</strong>
            </span>
          </NavLink>

          <nav className="site-nav" aria-label="主导航">
            <NavLink className={navClassName} to="/" end>
              首页
            </NavLink>
            <NavLink className={navClassName} to="/subjects">
              学科
            </NavLink>
            <NavLink className={navClassName} to="/import">
              智能导入
            </NavLink>
            <NavLink className={navClassName} to="/questions">
              题库
            </NavLink>
            <NavLink className={navClassName} to="/practice">
              练习
            </NavLink>
            <NavLink className={navClassName} to="/settings/ai">
              AI 设置
            </NavLink>
            <NavLink className={navClassName} to="/settings/connection">
              连接设置
            </NavLink>
            <NavLink className={navClassName} to="/admin">
              成员
            </NavLink>
            <NavLink className={navClassName} to="/login">
              登录
            </NavLink>
            <NavLink className={navClassName} to="/about">
              项目架构
            </NavLink>
          </nav>
        </header>

        <main className="site-main">
          <Outlet />
        </main>

        <footer className="site-footer">
          <span>BioLearn AI · V1.0</span>
          <span>本地优先 · 可审计 · 按阶段交付</span>
        </footer>

        {/* Mobile-only primary navigation (hidden on wide screens via CSS). */}
        <nav className="tab-bar" aria-label="底部导航">
          {PRIMARY_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={tabClassName}
            >
              <span className="tab-bar-icon" aria-hidden="true">
                {link.icon}
              </span>
              <span className="tab-bar-label">{link.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </ToastProvider>
  )
}
