import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HomePage } from './HomePage'

const healthPayload = {
  status: 'ok',
  service: 'BioLearn AI API',
  version: '0.1.0',
  environment: 'development',
}

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderHomePage() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  )
}

describe('HomePage', () => {
  it('renders the product headline and live health metadata', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(healthPayload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    renderHomePage()

    expect(
      screen.getByRole('heading', { level: 1 }),
    ).toHaveTextContent('把生物医学资料')
    expect(await screen.findByText('服务在线')).toBeInTheDocument()
    expect(screen.getByText('BioLearn AI API')).toBeInTheDocument()
  })

  it('shows an offline state when the backend is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('Failed to fetch')),
    )

    renderHomePage()

    expect(await screen.findByText('无法连接后端')).toBeInTheDocument()
    expect(screen.getByText('Failed to fetch')).toBeInTheDocument()
  })
})
