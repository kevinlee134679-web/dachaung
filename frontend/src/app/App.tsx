import type { JSX } from '@solidjs/web'
import { createSignal, onSettled, Show } from 'solid-js'
import * as v from 'valibot'
import { LoginPage } from '../features/login/login-page'
import { resolveOnboarding } from '../features/onboarding/onboarding'
import { OnboardingLayout } from '../features/onboarding/onboarding-layout'
import { restoreMedicationPage } from '../features/plan-drafts/navigation'
import { restoreServicePage } from '../features/services/navigation'
import { actionError } from '../notice/notice'
import { Notice } from '../notice/notice-view'
import { captureView, isCurrentView, loadContext, resetSession, state, ViewChanged } from '../session/session'
import { Badge } from '../ui/badge'
import { Brand } from '../ui/brand'
import { ConfirmHost } from '../ui/confirm'
import { Spinner } from '../ui/spinner'
import { Text } from '../ui/typography'
import { HealthFooter } from './health-footer'
import { Identity } from './identity'
import { Navbar } from './navbar'
import { PageContent } from './page-content'

const healthEnvelopeSchema = v.looseObject({ status: v.string() })

export function App(): JSX.Element {
  const [health, setHealth] = createSignal('正在检查基础服务…')
  const [checking, setChecking] = createSignal(false)
  const [ready, setReady] = createSignal(false)
  const [serviceReady, setServiceReady] = createSignal(false)
  async function checkHealth(): Promise<void> {
    setChecking(true)
    try {
      const response = await fetch('/api/v1/health', { cache: 'no-store' })
      const result = v.parse(healthEnvelopeSchema, await response.json())
      setServiceReady(response.ok && result.status === 'success')
      setHealth(
        response.ok && result.status === 'success'
          ? '基础存储已就绪；功能以各页面实际状态为准。'
          : '基础服务尚未就绪，请查看初始化或迁移说明。',
      )
    } catch {
      setServiceReady(false)
      setHealth('无法连接本地服务，请确认已启动后重新检查。')
    } finally {
      setChecking(false)
    }
  }
  onSettled(() => {
    void (async () => {
      await checkHealth()
      try {
        await loadContext()
      } catch {
        resetSession()
      }
      const medicationRestored = restoreMedicationPage()
      if (state.context && !medicationRestored) {
        const view = captureView()
        try {
          await resolveOnboarding(view)
        } catch (error) {
          if (!(error instanceof ViewChanged) && isCurrentView(view)) actionError(error, view)
        }
      }
      if (!medicationRestored) await restoreServicePage()
      setReady(true)
    })()
  })
  return (
    <Show
      when={ready()}
      fallback={
        <div class="grid min-h-dvh place-items-center">
          <Text>
            <Spinner />
            正在读取本地状态…
          </Text>
        </div>
      }
    >
      <ConfirmHost />
      <Show
        when={state.context}
        fallback={
          <div class="grid min-h-dvh place-items-center p-6">
            <div class="w-full max-w-md space-y-6">
              <Notice />
              <LoginPage />
            </div>
          </div>
        }
      >
        <Show
          when={state.onboarding}
          keyed
          fallback={
            <>
              <Show when={state.context?.csrf_token} keyed>
                <aside class="fixed inset-x-0 bottom-0 z-20 border-t border-zinc-950/5 bg-white pb-[env(safe-area-inset-bottom)] lg:inset-y-0 lg:right-auto lg:flex lg:w-64 lg:flex-col lg:gap-6 lg:border-t-0 lg:border-r lg:p-4 dark:border-white/10 dark:bg-zinc-900">
                  <div class="hidden items-center justify-between gap-2 lg:flex">
                    <Brand />
                    <Badge>虚构演示</Badge>
                  </div>
                  <Navbar />
                </aside>
                <header class="sticky top-0 z-10 flex h-14 items-center justify-between gap-3 border-b border-zinc-950/5 bg-white/80 px-4 backdrop-blur lg:ml-64 lg:justify-end lg:px-10 dark:border-white/10 dark:bg-zinc-900/80">
                  <div class="lg:hidden">
                    <Brand />
                  </div>
                  <Identity />
                </header>
              </Show>
              <div class="lg:pl-64">
                <main class="mx-auto max-w-5xl space-y-6 px-4 py-6 pb-24 sm:px-6 lg:px-10 lg:py-10 lg:pb-8">
                  <Notice />
                  <Show
                    when={state.switchingPatient}
                    fallback={
                      <Show when={state.epoch + 1} keyed>
                        <PageContent />
                      </Show>
                    }
                  >
                    <Text>
                      <Spinner />
                      正在切换管理对象…
                    </Text>
                  </Show>
                  <HealthFooter
                    ready={serviceReady()}
                    message={health()}
                    checking={checking()}
                    onRecheck={checkHealth}
                  />
                </main>
              </div>
            </>
          }
        >
          {step => <OnboardingLayout step={step} />}
        </Show>
      </Show>
    </Show>
  )
}
