import * as v from 'valibot'

export interface SupportSession {
  session_id: string
  status: 'active' | 'closed'
  ui_mode: 'normal' | 'simplified'
  turn_count: number
  opened_at: string
  meta: { revision: number }
}
export const supportSessionSchema: v.GenericSchema<unknown, SupportSession> = v.looseObject({
  session_id: v.string(),
  status: v.picklist(['active', 'closed']),
  ui_mode: v.picklist(['normal', 'simplified']),
  turn_count: v.number(),
  opened_at: v.string(),
  meta: v.looseObject({ revision: v.number() }),
})
export interface Message {
  role: 'user' | 'assistant'
  content: string
  generation_status:
    | 'accepted'
    | 'running'
    | 'failed'
    | 'outcome_unknown'
    | 'cancelled'
    | 'completed'
    | 'not_applicable'
  message_id: string
  generation_id: string
}
export const messageSchema: v.GenericSchema<unknown, Message> = v.looseObject({
  role: v.picklist(['user', 'assistant']),
  content: v.string(),
  generation_status: v.picklist([
    'accepted',
    'running',
    'failed',
    'outcome_unknown',
    'cancelled',
    'completed',
    'not_applicable',
  ]),
  message_id: v.string(),
  generation_id: v.string(),
})
interface Cue {
  label: string
  evidence: string
}
export const cueSchema: v.GenericSchema<unknown, Cue> = v.looseObject({ label: v.string(), evidence: v.string() })
export interface Output {
  business_output: {
    communication_strategy: (
      | 'reflection'
      | 'affirmation'
      | 'open_question'
      | 'autonomy_support'
      | 'permission_based_advice'
      | 'summary'
    )[]
    difficulty_cues: { label: string; evidence: string }[]
    knowledge_citations: { knowledge_id: string; version: string; quote: string }[]
    suggested_action: { description: string } | null
  }
  generation: {
    mode: 'mock' | 'real'
    session_id: string
    input_snapshot: { missing_items: { message: string }[] }
  }
}
export const outputSchema: v.GenericSchema<unknown, Output> = v.looseObject({
  business_output: v.looseObject({
    communication_strategy: v.array(
      v.picklist([
        'reflection',
        'affirmation',
        'open_question',
        'autonomy_support',
        'permission_based_advice',
        'summary',
      ]),
    ),
    difficulty_cues: v.array(cueSchema),
    knowledge_citations: v.array(v.looseObject({ knowledge_id: v.string(), version: v.string(), quote: v.string() })),
    suggested_action: v.nullable(v.looseObject({ description: v.string() })),
  }),
  generation: v.looseObject({
    mode: v.picklist(['mock', 'real']),
    session_id: v.string(),
    input_snapshot: v.looseObject({ missing_items: v.array(v.looseObject({ message: v.string() })) }),
  }),
})
export interface RefreshState {
  accountId: string | null
  patientId: string | null
  sessionId: string
  draft?: string
  output?: Output
  message?: string
}
export const pendingRefresh: { current: RefreshState | null } = { current: null }
export const generationState: Record<string, string> = {
  accepted: '等待生成',
  running: '生成中',
  failed: '生成失败',
  outcome_unknown: '结果未知，先核查原消息',
  cancelled: '生成已取消',
}
export const assessmentSource: Record<string, string> = {
  model_cues: '模型线索',
  self_report: '本人自评',
  context_summary: '上下文摘要',
}
export function supportPath(session: SupportSession, suffix = ''): string {
  return `/sessions/${encodeURIComponent(session.session_id)}${suffix}`
}
