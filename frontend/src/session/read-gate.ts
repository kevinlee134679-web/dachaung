import { captureView, requireCurrentView, ViewChanged } from './session'

export function readGate(): () => () => void {
  let serial = 0
  return () => {
    const turn = ++serial
    const view = captureView()
    return () => {
      requireCurrentView(view)
      if (turn !== serial) throw new ViewChanged()
    }
  }
}
