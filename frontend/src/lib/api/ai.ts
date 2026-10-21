import { apiRequest } from './client'

export interface AIStatus {
  configured: boolean
  provider: string
  model: string
  api_base: string
  key_configured: boolean
  source: string
  message: string
}

export interface AIConnectionTest {
  ok: boolean
  message: string
  model: string | null
}

export interface AIConfigInput {
  provider: string
  api_base: string
  model: string
  api_key?: string
  clear_key?: boolean
  timeout_seconds?: number
  max_retries?: number
  temperature?: number
}

export function getAIStatus(signal?: AbortSignal): Promise<AIStatus> {
  return apiRequest<AIStatus>('/ai/status', { signal })
}

export function testAIConnection(): Promise<AIConnectionTest> {
  return apiRequest<AIConnectionTest>('/ai/test', { method: 'POST' })
}

export function saveAIConfig(input: AIConfigInput): Promise<AIStatus> {
  return apiRequest<AIStatus>('/ai/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function clearAIConfig(): Promise<AIStatus> {
  return apiRequest<AIStatus>('/ai/config', { method: 'DELETE' })
}
