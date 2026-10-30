'use client'

const TIMEFRAMES = ['3m']

export function TimeframeSelector({ value, onChange }: { value: string, onChange: (v: string) => void }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-[#1e2329] border border-[#2b3139] px-3 py-1 rounded"
      title="Only 3m available from backend"
    >
      {TIMEFRAMES.map(t => (
        <option key={t} value={t}>{t}</option>
      ))}
    </select>
  )
}