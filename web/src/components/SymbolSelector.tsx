'use client'

const SYMBOLS = ['BTCUSD', 'ETHUSD', 'SOLUSD']

export function SymbolSelector({ value, onChange }: { value: string, onChange: (v: string) => void }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-[#1e2329] border border-[#2b3139] px-3 py-1 rounded"
    >
      {SYMBOLS.map(s => (
        <option key={s} value={s}>{s}</option>
      ))}
    </select>
  )
}