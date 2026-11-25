import type { Page } from './session'
import * as v from 'valibot'
import { pageTabs } from '../app/pages'
import { notice } from '../notice/notice'
import { referenceKey, state, updateSession } from './session'

export function rememberPage(): void {
  if (state.patient) sessionStorage.setItem(referenceKey('page'), JSON.stringify({ page: state.page, tab: state.tab }))
}

export function restorePage(): boolean {
  if (!state.patient) return false
  const saved = sessionStorage.getItem(referenceKey('page'))
  if (saved === null) return false
  try {
    const { page, tab } = v.parse(
      v.object({ page: v.picklist(['home', 'medication', 'knowledge', 'support', 'profile']), tab: v.string() }),
      JSON.parse(saved),
    )
    if (!pageTabs(page).some(([key]) => key === tab)) return false
    navigate(page, tab)
    return true
  } catch {
    return false
  }
}

export function navigate(page: Page, tab = 'overview'): void {
  if (state.switchingPatient) return
  notice('')
  updateSession(draft => {
    draft.epoch++
    draft.page = page
    draft.tab = tab
    draft.draft = null
  })
}

export function changeTab(tab: string): void {
  if (state.switchingPatient) return
  notice('')
  updateSession(draft => {
    draft.epoch++
    draft.tab = tab
  })
}
