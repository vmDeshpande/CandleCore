'use client'

import { useEffect, useState } from 'react'
import { Chart } from '@/components/Chart'
import { SymbolSelector } from '@/components/SymbolSelector'
import { TimeframeSelector } from '@/components/TimeframeSelector'
import { StatusBar } from '@/components/StatusBar'

export default function Home() {
  const [symbol, setSymbol] = useState('BTCUSD')
  const [timeframe, setTimeframe] = useState('3m')
  const [connected, setConnected] = useState(false)

  return (
    <main className="min-h-screen bg-[#0b0e11] text-[#eaecef]">
      <header className="border-b border-[#2b3139] p-4 flex items-center gap-4">
        <h1 className="text-xl font-bold">CandleCore</h1>
        <SymbolSelector value={symbol} onChange={setSymbol} />
        <TimeframeSelector value={timeframe} onChange={setTimeframe} />
        <StatusBar connected={connected} symbol={symbol} timeframe={timeframe} />
      </header>
      <div className="p-4">
        <Chart symbol={symbol} timeframe={timeframe} onConnectionChange={setConnected} />
        <footer className="mt-4 text-xs text-gray-500">
          Powered by TradingView Lightweight Charts™
        </footer>
      </div>
    </main>
  )
}