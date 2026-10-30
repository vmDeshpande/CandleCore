
'use client'

interface StatusBarProps {
  symbol: string
  timeframe: string
  connected: boolean
}

export function StatusBar({ symbol, timeframe, connected }: StatusBarProps) {
  return (
    <div className="flex items-center gap-4 text-sm text-gray-400">
      <span>{symbol} · {timeframe}</span>

      <span className="flex items-center gap-1">
        <span
          className={`w-2 h-2 rounded-full ${
            connected ? 'bg-green-500' : 'bg-red-500'
          }`}
        />
        {connected ? 'Live' : 'Disconnected'}
      </span>
    </div>
  )
}
