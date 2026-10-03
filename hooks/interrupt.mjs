export function register(on) {
  on('turn.complete', async ($, e, next) => {
    if (e.isAborted && !e.agentId) {
      const root = typeof $.plugin.root === 'function' ? await $.plugin.root() : $.plugin.root
      try {
        await $.process.run([`${root}/bin/speak`, 'stop'])
      } catch {}
    }
    return next(e)
  })
}
