"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  IChartApi,
  ISeriesApi,
  UTCTimestamp,
} from "lightweight-charts";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const WS_BASE = process.env.NEXT_PUBLIC_WS_BASE || "ws://localhost:8000";

export function Chart({
  symbol,
  timeframe,
  onConnectionChange,
}: {
  symbol: string;
  timeframe: string;
  onConnectionChange: (v: boolean) => void;
}) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState(false);

  useEffect(() => {
    if (!chartContainerRef.current) return;
    const chart = createChart(chartContainerRef.current, {
      layout: { background: { color: "#0b0e11" }, textColor: "#d1d4dc" },
      grid: {
        vertLines: { color: "#2b3139" },
        horzLines: { color: "#2b3139" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    chartRef.current = chart;
    candleSeriesRef.current = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });

    volumeSeriesRef.current = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "",
    });
    chart.priceScale("").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    setLoading(true);
    setError(null);
    setEmpty(false);

    const loadHistory = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/v1/market/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}&limit=500`,
          { cache: "no-store" },
        );
        if (!response.ok) {
          throw new Error(`History request failed: HTTP ${response.status}`);
        }
        const data = await response.json();
        if (cancelled) return;
        if (data.error) throw new Error(data.error);

        const rows = Array.isArray(data.candles) ? data.candles : [];
        const candles = rows.map((c: any) => ({
          time: Math.floor(new Date(c.candle_open_time).getTime() / 1000) as UTCTimestamp,
          open: Number(c.open),
          high: Number(c.high),
          low: Number(c.low),
          close: Number(c.close),
        }));
        const volumes = rows.map((c: any) => ({
          time: Math.floor(new Date(c.candle_open_time).getTime() / 1000) as UTCTimestamp,
          value: c.volume == null ? 0 : Number(c.volume),
          color: Number(c.close) >= Number(c.open) ? "#26a69a80" : "#ef535080",
        }));

        candleSeriesRef.current?.setData(candles);
        volumeSeriesRef.current?.setData(volumes);
        setEmpty(candles.length === 0);
        setError(null);
        setLoading(false);

        // The API can be queried before the startup backfill has committed.
        // Retry empty history until the first persisted candles are available.
        if (candles.length === 0 && !cancelled) {
          retryTimer = setTimeout(loadHistory, 3000);
        }
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Unable to load candle history");
        setLoading(false);
        retryTimer = setTimeout(loadHistory, 5000);
      }
    };

    void loadHistory();
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [symbol, timeframe]);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/api/v1/stream/market`);
    wsRef.current = ws;
    ws.onopen = () => {
      onConnectionChange(true);
      ws.send(JSON.stringify({ type: "subscribe", symbol, timeframe }));
    };
    ws.onclose = () => onConnectionChange(false);
    ws.onerror = () => onConnectionChange(false);
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (
          msg.type === "candle" &&
          msg.symbol === symbol &&
          msg.timeframe === timeframe
        ) {
          const candle = {
            time: Math.floor(
              new Date(msg.candle_open_time).getTime() / 1000,
            ) as UTCTimestamp,
            open: parseFloat(msg.open),
            high: parseFloat(msg.high),
            low: parseFloat(msg.low),
            close: parseFloat(msg.close),
          };
          candleSeriesRef.current?.update(candle);
          volumeSeriesRef.current?.update({
            time: candle.time,
            value: msg.volume ? parseFloat(msg.volume) : 0,
            color:
              parseFloat(msg.close) >= parseFloat(msg.open)
                ? "#26a69a80"
                : "#ef535080",
          });
        }
      } catch {}
    };
    return () => {
      ws.close();
    };
  }, [symbol, timeframe, onConnectionChange]);

  return (
    <div className="w-full">
      <div ref={chartContainerRef} className="w-full h-[400px]" />
      {loading && (
        <div className="text-center text-gray-400 py-4">Loading...</div>
      )}
      {error && <div className="text-center text-red-400 py-4">{error} · Retrying…</div>}
      {empty && !loading && !error && (
        <div className="text-center text-gray-400 py-4">Waiting for historical candles to be stored…</div>
      )}
    </div>
  );
}
