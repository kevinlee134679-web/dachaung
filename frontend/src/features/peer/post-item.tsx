import type { PeerPost } from './peer'
import type { JSX } from '@solidjs/web'
import { dateText } from '../../date/date'
import { Badge } from '../../ui/badge'
import { statusTone } from '../../ui/labels'

const peerReviewStatus = { pending: '待审', visible: '已公开', hidden: '已隐藏' }

export function PeerPostItem(props: { post: PeerPost }): JSX.Element {
  return (
    <article class="space-y-2">
      <p class="text-sm/6 font-medium text-zinc-950 dark:text-white">
        {props.post.author_alias} ·{' '}
        <Badge tone={statusTone(props.post.moderation_status)}>{peerReviewStatus[props.post.moderation_status]}</Badge>
      </p>
      <p>{props.post.content}</p>
      <p class="text-sm/6 text-zinc-500 dark:text-zinc-400">{dateText(props.post.created_at)}</p>
    </article>
  )
}
