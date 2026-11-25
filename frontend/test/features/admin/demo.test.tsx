import { cleanup, render, screen } from '@solidjs/testing-library'
import { afterEach, expect, it, vi } from 'vitest'
import { DemoPage } from '../../../src/features/admin/demo-page'
import { updateSession } from '../../../src/session/session'
import { choose } from '../../support'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('ordinary patient cannot render management actions or execute a task by entering the console page', () => {
  choose({ account: 'account-a' })
  updateSession(draft => {
    draft.epoch++
  })
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  render(() => <DemoPage />)
  expect(screen.getByText(/仅对受控演示管理员开放/)).toBeTruthy()
  expect(screen.queryByRole('button')).toBeNull()
  expect(fetch).not.toHaveBeenCalled()
})

it('registered demo administrator can open the console without a transferable management scope', () => {
  choose({ account: 'demo-admin' })
  updateSession(draft => {
    draft.epoch++
  })
  const fetch = vi.fn()
  vi.stubGlobal('fetch', fetch)
  render(() => <DemoPage />)
  expect(screen.getByText('显式执行此任务一次')).toBeTruthy()
  expect(screen.getByText('发送一次模拟事件')).toBeTruthy()
  expect(fetch).not.toHaveBeenCalled()
})
