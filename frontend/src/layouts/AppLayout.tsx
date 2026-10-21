import { NavLink, Outlet } from 'react-router-dom'

import { ToastProvider } from '../components/ToastProvider'

function navClassName({ isActive }: { isActive: boolean }) {
  return isActive ? 'nav-link is-active' : 'nav-link'
}

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
            <NavLink className={navClassName} to="/about">
              项目架构
            </NavLink>
          </nav>
        </header>

        <main className="site-main">
          <Outlet />
        </main>

        <footer className="site-footer">
          <span>BioLearn AI · 阶段三</span>
          <span>本地优先 · 可审计 · 按阶段交付</span>
        </footer>
      </div>
    </ToastProvider>
  )
}
