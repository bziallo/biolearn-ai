import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section className="not-found">
      <p className="eyebrow">404</p>
      <h1>这条通路还没长出来。</h1>
      <p>页面不存在，后端服务本身可能仍然健在。</p>
      <Link className="button button-primary" to="/">
        回到首页
      </Link>
    </section>
  )
}
