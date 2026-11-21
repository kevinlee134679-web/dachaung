import type { JSX } from '@solidjs/web'
import * as v from 'valibot'
import { api } from '../../api/api'
import { notice } from '../../notice/notice'
import { navigate } from '../../session/navigation'
import { loadContext } from '../../session/session'
import { Brand } from '../../ui/brand'
import { Button } from '../../ui/button'
import { Card } from '../../ui/card'
import { Field, Select } from '../../ui/form'
import { Heading, Text } from '../../ui/typography'
import { resolveOnboarding } from '../onboarding/onboarding'

export function LoginPage(): JSX.Element {
  let chooser!: HTMLSelectElement
  async function enter(family: boolean): Promise<void> {
    await api('/auth/demo-session', v.unknown(), 'POST', { demo_account_id: chooser.value })
    await loadContext()
    navigate(family ? 'profile' : 'home', family ? 'family' : 'overview')
    if (!family) await resolveOnboarding()
    notice('已进入演示，当前对象显示在页面上方。')
  }
  return (
    <div class="w-full max-w-md space-y-6">
      <Brand />
      <Card>
        <div class="space-y-6">
          <div class="space-y-2">
            <Heading>从自己的安排开始，也可以帮助家人</Heading>
            <Text>同一账号可以管理自己和已获授权的家人。演示身份不代表真实认证。</Text>
          </div>
          <Field label="选择虚构身份">
            <Select ref={chooser}>
              <option value="demo-patient-a">演示患者甲</option>
              <option value="demo-patient-b">演示患者乙</option>
              <option value="demo-family">演示家人（也可管理自己）</option>
              <option value="demo-admin">演示管理员</option>
            </Select>
          </Field>
          <div class="flex flex-wrap gap-3">
            <Button variant="primary" onAction={() => enter(false)}>
              管理自己的用药
            </Button>
            <Button onAction={() => enter(true)}>帮助家人管理用药</Button>
          </div>
        </div>
      </Card>
      <Text class="text-xs">首次使用需先按运行说明显式初始化数据库及演示身份；启动不会自动建立账号。</Text>
    </div>
  )
}
