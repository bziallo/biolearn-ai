import { useOnlineStatus } from '../lib/offline/network'

export function OfflineBanner() {
  const online = useOnlineStatus()
  if (online) {
    return null
  }
  return (
    <div className="offline-banner" role="status" aria-live="polite">
      <strong>离线模式</strong>
      <span>
        当前只能浏览已缓存内容；上传、解析和 AI 分析需要连接 BioLearn 后端。
      </span>
    </div>
  )
}
