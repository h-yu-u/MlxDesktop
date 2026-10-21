import { describe, expect, it } from 'vitest'
import { router } from './router'
describe('settings deep-link compatibility', () => {
  it.each(['skills', 'mcp', 'builtin'])('passes the actual %s tab and preserves queries', (tab) => {
    const route = router.resolve(`/settings/extensions/${tab}?from=old-link#section`)
    expect(route.matched.at(-1)?.props.default).toEqual({ tab })
    expect(route.meta.navKey).toBe('settings')
    expect(route.query.from).toBe('old-link')
    expect(route.hash).toBe('#section')
  })
  it.each(['/settings', '/settings/coding', '/settings/runtime', '/settings/privacy'])(
    'keeps %s under the settings navigation',
    (path) => {
      expect(router.resolve(path).meta.navKey).toBe('settings')
    },
  )
})
