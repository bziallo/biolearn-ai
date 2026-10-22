import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'

import type { ChapterNode } from '../lib/api/chapters'
import {
  getErrorDetail,
  getErrorMessage,
  uploadDocument,
  type DocumentSummary,
} from '../lib/api'
import { flattenTree } from '../lib/chapterTree'
import { formatBytes } from '../lib/format'
import { isOfflineError, useOnlineStatus } from '../lib/offline/network'
import { useToast } from '../lib/useToast'
import { Notice } from './Notice'

interface DocumentUploadCardProps {
  subjectId: string
  tree: ChapterNode[]
  onUploaded: (document: DocumentSummary) => void
}

export function DocumentUploadCard({
  subjectId,
  tree,
  onUploaded,
}: DocumentUploadCardProps) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [chapterId, setChapterId] = useState('')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [duplicateName, setDuplicateName] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { notify } = useToast()
  const online = useOnlineStatus()
  const [statusMessage, setStatusMessage] = useState('')

  const maxBytes = 25 * 1024 * 1024
  const supportedExtension = /\.(pdf|docx|pptx|txt|md|markdown)$/i

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] ?? null
    setError('')
    setDuplicateName('')
    setStatusMessage('')
    if (!nextFile) {
      setFile(null)
      return
    }
    if (!supportedExtension.test(nextFile.name)) {
      setFile(null)
      event.target.value = ''
      setError('不支持该文件格式；当前支持 PDF、DOCX、PPTX、TXT、MD。旧版 .ppt 请先另存为 .pptx。')
      return
    }
    if (nextFile.size > maxBytes) {
      setFile(null)
      event.target.value = ''
      setError(`文件超过 25 MB 限制（当前 ${formatBytes(nextFile.size)}）。`)
      return
    }
    setFile(nextFile)
    if (!name.trim()) {
      setName(nextFile.name.replace(/\.[^.]+$/, ''))
    }
  }

  async function submit(force = false) {
    if (!file) {
      setError('请选择要上传的文件')
      return
    }
    if (!online) {
      setError('当前离线，无法上传。文件已保留；连接后端后点击“重试上传”。')
      return
    }
    if (file.size > maxBytes) {
      setError('文件超过 25 MB 限制。')
      return
    }
    setUploading(true)
    setError('')
    setStatusMessage('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('subject_id', subjectId)
      formData.append('name', name.trim() || file.name.replace(/\.[^.]+$/, ''))
      if (chapterId) {
        formData.append('chapter_id', chapterId)
      }
      if (force) {
        formData.append('force', 'true')
      }
      const document = await uploadDocument(formData)
      onUploaded(document)
      notify('success', '资料已上传，正在后台解析')
      setStatusMessage('上传成功，资料已进入后端解析队列。')
      setFile(null)
      setName('')
      setChapterId('')
      setDuplicateName('')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (uploadError) {
      const detail = getErrorDetail(uploadError)
      if (detail?.code === 'duplicate_document') {
        setDuplicateName(String(detail.existing_document_name ?? '已有资料'))
        setError('检测到同一章节下已有相同内容的资料')
      } else if (isOfflineError(uploadError)) {
        setError(
          '网络中断，文件仍保留且尚未确认上传成功。恢复连接后请重试；若提示重复，请到资料库确认，避免重复记录。',
        )
      } else {
        setError(getErrorMessage(uploadError))
      }
    } finally {
      setUploading(false)
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void submit(false)
  }

  return (
    <form className="upload-card" onSubmit={handleSubmit}>
      <div className="upload-card-head">
        <div>
          <p className="eyebrow">Import material</p>
          <h2>导入学习资料</h2>
        </div>
        <span className="upload-badge">PDF · DOCX · PPTX · TXT · MD</span>
      </div>

      <div className="upload-grid">
        <div className="field">
          <label htmlFor="document-file">选择文件</label>
          <input
            ref={fileInputRef}
            id="document-file"
            type="file"
            accept=".pdf,.docx,.pptx,.txt,.md,.markdown"
            onChange={handleFileChange}
          />
        </div>
        <div className="field">
          <label htmlFor="document-name">资料名称</label>
          <input
            id="document-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={240}
            placeholder="例如：第二章 蛋白质结构"
          />
        </div>
        <div className="field">
          <label htmlFor="document-chapter">所属章节</label>
          <select
            id="document-chapter"
            value={chapterId}
            onChange={(event) => setChapterId(event.target.value)}
          >
            <option value="">未指定章节</option>
            {flattenTree(tree).map(({ node, depth }) => (
              <option value={node.id} key={node.id}>
                {'— '.repeat(depth)}
                {node.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <p className="form-hint">
        单个文件最大 25 MB。旧版 .ppt 请先另存为 .pptx；扫描版 PDF 当前没有 OCR，会明确提示无法可靠提取。
      </p>

      {file && (
        <p className="form-hint" aria-live="polite">
          已选择：{file.name} · {formatBytes(file.size)}。上传成功后才进入后端解析队列。
        </p>
      )}
      {!online && (
        <Notice kind="info">
          当前离线。文件选择仍可用，但上传需要连接后端；恢复网络后可继续。
        </Notice>
      )}
      {statusMessage && <Notice kind="success">{statusMessage}</Notice>}
      {error && <Notice kind="error">{error}</Notice>}
      {duplicateName && (
        <Notice kind="info">
          <span>已有资料：{duplicateName}。如果确实要保留重复资料：</span>
          <button
            type="button"
            className="text-button"
            onClick={() => void submit(true)}
            disabled={uploading}
          >
            仍然上传
          </button>
        </Notice>
      )}

      <div className="form-actions">
        <button
          type="submit"
          className="button button-primary"
          disabled={uploading || !online}
        >
          {uploading
            ? '上传中…'
            : error && file
              ? '重试上传'
              : '上传并解析'}
        </button>
      </div>
    </form>
  )
}
