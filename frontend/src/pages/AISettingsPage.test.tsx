import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider } from '../components/ToastProvider'
import { AISettingsPage } from './AISettingsPage'

function jsonResponse(data: unknown) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AISettingsPage', () => {
  it('saves provider, base, model and key without echoing the key', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/ai/status')) {
        return Promise.resolve(
          jsonResponse({
            configured: false,
            provider: 'openai-compatible',
            model: '',
            api_base: '',
            key_configured: false,
            source: 'unconfigured',
            message: 'AI 未配置',
          }),
        )
      }
      if (url.endsWith('/ai/config') && init?.method === 'PUT') {
        return Promise.resolve(
          jsonResponse({
            configured: true,
            provider: 'openai-compatible',
            model: 'example-model',
            api_base: 'http://ai.example/v1',
            key_configured: true,
            source: 'runtime',
            message: 'AI 已配置',
          }),
        )
      }
      return Promise.resolve(jsonResponse({}))
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <MemoryRouter>
        <ToastProvider>
          <AISettingsPage />
        </ToastProvider>
      </MemoryRouter>,
    )

    expect((await screen.findAllByText('AI 未配置')).length).toBeGreaterThan(0)
    fireEvent.change(screen.getByLabelText('API Base URL'), {
      target: { value: 'http://ai.example/v1' },
    })
    fireEvent.change(screen.getByLabelText('模型名称'), {
      target: { value: 'example-model' },
    })
    fireEvent.change(screen.getByLabelText('API Key'), {
      target: { value: 'secret-key' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存 AI 配置' }))

    expect((await screen.findAllByText('AI 已配置')).length).toBeGreaterThan(0)
    const putCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith('/ai/config') &&
        (init as RequestInit)?.method === 'PUT',
    )
    expect(putCall).toBeTruthy()
    const body = JSON.parse((putCall?.[1] as RequestInit).body as string)
    expect(body.api_base).toBe('http://ai.example/v1')
    expect(body.model).toBe('example-model')
    expect(body.api_key).toBe('secret-key')
    await waitFor(() =>
      expect(screen.queryByDisplayValue('secret-key')).not.toBeInTheDocument(),
    )
  })
})
