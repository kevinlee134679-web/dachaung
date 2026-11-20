import { state } from '../session/session'

export function localDateTime(value: string = new Date().toISOString()): string {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  })
    .format(new Date(value))
    .replace(' ', 'T')
}

export function inputDateTime(value: string): string {
  if (!value) throw new Error('请明确填写北京时间。')
  const date = new Date(`${value + (value.length === 16 ? ':00' : '')}+08:00`)
  if (!Number.isFinite(date.getTime())) throw new TypeError('时间格式不正确。')
  return date.toISOString()
}

export function today(): string {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

export function dateText(value: string | number | Date): string {
  const timezone = state.patient?.patient.timezone
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: timezone === undefined || timezone === '' ? 'Asia/Shanghai' : timezone,
  }).format(new Date(value))
}
