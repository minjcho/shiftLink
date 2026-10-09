import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import IncidentDetailPage from './IncidentDetailPage.vue'
import HandoverPage from './HandoverPage.vue'
import { routes } from '../router'

it('provides the three shared routes and feature panel slots', () => {
  expect(routes.map(r => r.path)).toEqual(['/', '/incidents', '/incidents/:id', '/handovers/:id?'])
  const page = mount(IncidentDetailPage, { props: { id: 'incident-real-id' }, slots: {
    intake: '<p>질문 패널</p>', actions: '<p>작업 패널</p>', resolution: '<p>검증 패널</p>', history: '<p>이력 패널</p>' } })
  expect(page.text()).toContain('incident-real-id')
  for (const text of ['질문 패널', '작업 패널', '검증 패널', '이력 패널']) expect(page.text()).toContain(text)
})

it('does not fabricate a handover or completed work', () => {
  const page = mount(HandoverPage)
  expect(page.text()).toContain('준비 중')
  expect(page.find('button').exists()).toBe(false)
})
