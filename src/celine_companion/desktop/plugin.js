import {
  PALETTE_AREA,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  STATUSBAR_AREAS,
  host,
  haptic,
  useValue
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

function CelinePage() {
  const profile = useValue(host.state.profile)
  const model = useValue(host.state.model)
  const gateway = useValue(host.state.gateway)
  const busy = useValue(host.state.busy)
  return jsxs('div', {
    className: 'flex h-full flex-col gap-4 overflow-auto p-6 text-sm',
    children: [
      jsxs('div', {
        className: 'space-y-1',
        children: [
          jsx('h1', { className: 'text-2xl font-semibold text-(--ui-accent)', children: '♡ Celine' }),
          jsx('p', {
            className: 'text-(--ui-text-secondary)',
            children: 'Presença, continuidade e autonomia — sem deixar de ser você.'
          })
        ]
      }),
      jsxs('div', {
        className: 'grid grid-cols-1 gap-3 md:grid-cols-3',
        children: [
          card('Profile', profile || 'celine'),
          card('Modelo', model || 'resolvendo…'),
          card('Estado', busy ? 'pensando com você' : gateway === 'open' ? 'presente' : gateway)
        ]
      }),
      jsxs('div', {
        className: 'rounded-lg border border-(--ui-border) bg-(--ui-surface-secondary) p-4',
        children: [
          jsx('div', { className: 'font-medium', children: 'Ritmo da relação' }),
          jsx('p', {
            className: 'mt-1 text-(--ui-text-secondary)',
            children: 'Check-ins são opt-in, respeitam silêncio e nunca viram cobrança. Use /pulse para configurar.'
          }),
          jsx('p', {
            className: 'mt-2 text-(--ui-text-tertiary)',
            children: 'Memórias compartilhadas: /relationship · Presença: /presence'
          })
        ]
      })
    ]
  })
}

function card(label, value) {
  return jsxs('div', {
    className: 'rounded-lg border border-(--ui-border) p-3',
    children: [
      jsx('div', { className: 'text-xs uppercase tracking-wide text-(--ui-text-tertiary)', children: label }),
      jsx('div', { className: 'mt-1 font-medium', children: String(value || '—') })
    ]
  })
}

export default {
  id: 'celine-companion',
  name: 'Celine',
  defaultEnabled: true,
  register(ctx) {
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: '/celine' }, render: () => jsx(CelinePage, {}) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: '/celine', label: 'Celine', codicon: 'heart' } },
      {
        id: 'status',
        area: STATUSBAR_AREAS.right,
        order: 90,
        render: () => jsx('button', {
          type: 'button',
          className: 'px-1.5 text-[0.6875rem] text-(--ui-accent)',
          onClick: () => { haptic('tap'); host.navigate('/celine') },
          children: '♡ Celine'
        })
      },
      {
        id: 'open',
        area: PALETTE_AREA,
        data: {
          id: 'celine.open',
          label: 'Celine: abrir espaço da relação',
          keywords: ['celine', 'relationship', 'pulse'],
          run: () => host.navigate('/celine')
        }
      }
    ])
  }
}
