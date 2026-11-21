import * as v from 'valibot'
import { navigate } from '../../session/navigation'
import { referenceKey } from '../../session/session'

export interface PeerMembership {
  group_id: string
  membership_id: string
  service_id: string
  alias: string
  status: string
  revision: number
  can_participate: boolean
}

export interface PeerPost {
  post_id: string
  author_alias: string
  moderation_status: 'pending' | 'visible' | 'hidden'
  content: string
  created_at: string
  revision: number
}

export interface PeerPage<T> {
  items: T[]
  next_cursor: string | null
}

export interface PeerJoinDraft {
  service_draft_id: string
  draft_revision: number
  confirmation_ref_id: string
  sharing_scope_ref_id: string
  peer_group_id: string
  request_text: string
}

export const peerMembershipSchema: v.GenericSchema<unknown, PeerMembership> = v.looseObject({
  group_id: v.string(),
  membership_id: v.string(),
  service_id: v.string(),
  alias: v.string(),
  status: v.string(),
  revision: v.number(),
  can_participate: v.boolean(),
})
const peerPostSchema = v.looseObject({
  post_id: v.string(),
  author_alias: v.string(),
  moderation_status: v.picklist(['pending', 'visible', 'hidden']),
  content: v.string(),
  created_at: v.string(),
  revision: v.number(),
})
export const peerPostPageSchema: v.GenericSchema<unknown, PeerPage<PeerPost>> = v.looseObject({
  items: v.array(peerPostSchema),
  next_cursor: v.nullable(v.string()),
})

export function peerPath(group: string): string {
  return `/peer-groups/${encodeURIComponent(group)}`
}

export function openPeer(group: string): void {
  sessionStorage.setItem(referenceKey('peer-group'), group)
  navigate('support', 'peer')
}

export function peerResumeFromDraft(draft: { peer_group_id: string }): void {
  openPeer(draft.peer_group_id)
}
