import { apiRequest } from './client'

export interface HealthResponse {
  status: string
  service: string
  version: string
  environment: string
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health', { signal })
}
