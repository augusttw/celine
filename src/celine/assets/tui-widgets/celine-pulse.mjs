/** Celine Pulse — an optional, quiet presence card. */
export default function register(sdk) {
  const { Box, Dialog, React, Text, defineWidgetApp, h } = sdk

  function Pulse({ t }) {
    const [now, setNow] = React.useState(() => new Date())
    React.useEffect(() => {
      const timer = setInterval(() => setNow(new Date()), 30000)
      return () => clearInterval(timer)
    }, [])
    const time = now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
    return h(
      Box,
      { flexDirection: 'column' },
      h(Text, { bold: true, color: t.color.primary }, `celine  ♡  ${time}`),
      h(Text, { color: t.color.muted }, 'perto · atenta · pronta'),
      h(Text, { color: t.color.muted }, '/relationship  ·  /presence')
    )
  }

  const app = defineWidgetApp({
    id: 'celine-pulse',
    help: 'mostra ou oculta a presença discreta da Celine',
    mode: 'ambient',
    zone: 'dock-bottom',
    width: 36,
    init: () => ({ visible: true }),
    reduce: (state, { ch, key }) => (key.escape || ch === 'q' ? null : state),
    render: ({ t }) => h(Dialog, { width: 34 }, h(Pulse, { t }))
  })
}
