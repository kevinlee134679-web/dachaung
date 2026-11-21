import type { View } from '../../session/session'
import type { ServiceDraft } from './draft-data'
import type { JSX } from '@solidjs/web'
import { Show } from 'solid-js'
import { PeerJoinControls } from '../peer/join-controls'

export function ServicePeerJoinControls(props: {
  draft: ServiceDraft
  textArea: HTMLTextAreaElement
  view: View
  fallback: JSX.Element
}): JSX.Element {
  return (
    <Show when={props.draft.peer_group_id} fallback={props.fallback}>
      {peerGroupId => (
        <Show when={props.draft.confirmation_ref_id}>
          {confirmationRefId => (
            <Show when={props.draft.sharing_scope_ref_id}>
              {sharingScopeRefId => (
                <PeerJoinControls
                  draft={{
                    ...props.draft,
                    peer_group_id: peerGroupId(),
                    confirmation_ref_id: confirmationRefId(),
                    sharing_scope_ref_id: sharingScopeRefId(),
                  }}
                  textArea={props.textArea}
                  view={props.view}
                />
              )}
            </Show>
          )}
        </Show>
      )}
    </Show>
  )
}
