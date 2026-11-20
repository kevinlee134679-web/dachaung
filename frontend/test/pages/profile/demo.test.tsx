import { cleanup, render, screen } from '@solidjs/testing-library'
import { afterEach, expect, it, vi } from 'vitest'
import { DemoPage } from '../../../src/pages/profile/demo-page'
import { updateSession } from '../../../src/session/session'

function choose(account: string) {
  updateSession(draft => {
    draft.epoch++
    draft.context = {
      account: { account_id: account, display_name: account, is_simulated: true },
      csrf_token: 'csrf',
      current_patient_id: 'pa',
      patients: [],
    }
    draft.patient = {
      patient: { patient_id: 'pa', display_name: '甲', timezone: 'Asia/Shanghai' },
      relationship: 'self',
      effective_scopes: [],
    }
  })
}
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('ordinary patient cannot render management actions or execute a task by entering the console page', () => {
  choose('account-a')
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  render(() => <DemoPage />)
  expect(screen.getByText(/仅对受控演示管理员开放/)).toBeTruthy()
  expect(screen.queryByRole('button')).toBeNull()
  expect(fetch).not.toHaveBeenCalled()
})

it('registered demo administrator can open the console without a transferable management scope', () => {
  choose('demo-admin')
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  render(() => <DemoPage />)
  expect(screen.getByText('显式执行此任务一次')).toBeTruthy()
  expect(screen.getByText('发送一次模拟事件')).toBeTruthy()
  expect(fetch).not.toHaveBeenCalled()
})
