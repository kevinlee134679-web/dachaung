import type { Page } from './session'
import { notice } from '../notice/notice'
import { state, updateSession } from './session'

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
