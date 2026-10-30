'use client'

export function StatusBar({ connected, symbol, timeframe }: { connected: boolean, symbol: string, timeframe: string }) {
  return (
    <div className="flex items-center gap-4 text-sm text-gray-400">
      <span>{symbol} · {timeframe}</span>
      <span className={lex items-center gap-1 }>
        <span className="w-2 h-2 rounded-full "></span>
        {connected ? 'Live' : 'Disconnected'}
      </span>
    </div>
  )
}