import './globals.css'

export const metadata = {
  title: 'CandleCore - Market Observation',
  description: 'Read-only market data visualization',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}