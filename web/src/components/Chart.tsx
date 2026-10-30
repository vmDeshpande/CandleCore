'use client'

import { useEffect, useRef, useState } from 'react'
import { createChart, IChartApi, ISeriesApi, UTCTimestamp } from 'lightweight-charts'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'
const WS_BASE = process.env.NEXT_PUBLIC_WS_BASE || 'ws://localhost:8000'

export function Chart({ symbol, timeframe, onConnectionChange }: { symbol: string, timeframe: string, onConnectionChange: (v: boolean) => void }) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!chartContainerRef.current) return
    const chart = createChart(chartContainerRef.current, {
      layout: { background: { color: '#0b0e11' }, textColor: '#d1d4dc' },
      grid: { vertLines: { color: '#2b3139' }, horzLines: { color: '#2b3139' } },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      timeScale: { timeVisible: true, secondsVisible: false },
    })
    chartRef.current = chart
    candleSeriesRef.current = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    })
    volumeSeriesRef.current = chart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    })
    chart.priceScale('').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(${API_BASE}/api/v1/market/candles?symbol=&timeframe=&limit=500)
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          setError(data.error)
          setLoading(false)
          return
        }
        const candles = (data.candles || []).map((c: any) => ({
          time: Math.floor(new Date(c.candle_open_time).getTime() / 1000) as UTCTimestamp,
          open: parseFloat(c.open),
          high: parseFloat(c.high),
          low: parseFloat(c.low),
          close: parseFloat(c.close),
        }))
        const volumes = (data.candles || []).map((c: any) => ({
          time: Math.floor(new Date(c.candle_open_time).getTime() / 1000) as UTCTimestamp,
          value: c.volume ? parseFloat(c.volume) : 0,
          color: parseFloat(c.close) >= parseFloat(c.open) ? '#26a69a80' : '#ef535080',
        }))
        candleSeriesRef.current?.setData(candles)
        volumeSeriesRef.current?.setData(volumes)
        setLoading(false)
      })
      .catch(e => {
        setError(e.message)
        setLoading(false)
      })
  }, [symbol, timeframe])

  useEffect(() => {
    const ws = new WebSocket(${WS_BASE}/api/v1/stream/market)
    wsRef.current = ws
    ws.onopen = () => {
      onConnectionChange(true)
      ws.send(JSON.stringify({ type: 'subscribe', symbol, timeframe }))
    }
    ws.onclose = () => onConnectionChange(false)
    ws.onerror = () => onConnectionChange(false)
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'candle' && msg.symbol === symbol && msg.timeframe === timeframe) {
          const candle = {
            time: Math.floor(new Date(msg.candle_open_time).getTime() / 1000) as UTCTimestamp,
            open: parseFloat(msg.open),
            high: parseFloat(msg.high),
            low: parseFloat(msg.low),
            close: parseFloat(msg.close),
          }
          candleSeriesRef.current?.update(candle)
          volumeSeriesRef.current?.update({
            time: candle.time,
            value: msg.volume ? parseFloat(msg.volume) : 0,
            color: parseFloat(msg.close) >= parseFloat(msg.open) ? '#26a69a80' : '#ef535080',
          })
        }
      } catch {}
    }
    return () => {
      ws.close()
    }
  }, [symbol, timeframe, onConnectionChange])

  return (
    <div className="w-full">
      <div ref={chartContainerRef} className="w-full h-[400px]" />
      {loading && <div className="text-center text-gray-400 py-4">Loading...</div>}
      {error && <div className="text-center text-red-400 py-4">{error}</div>}
    </div>
  )
}