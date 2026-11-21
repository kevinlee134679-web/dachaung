import type { JSX } from '@solidjs/web'

export function Spinner(): JSX.Element {
  return (
    <span aria-hidden="true" class="mr-2 icon-[heroicons--arrow-path] size-4 animate-spin motion-reduce:animate-none" />
  )
}
