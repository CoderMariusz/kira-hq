import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import Link from 'next/link'
import './globals.css'

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'Kira-HQ',
  description: 'Minimal Module 3 dashboard',
}

const navItems = [
  { href: '/', label: 'Projects' },
  { href: '/views/needs-attention', label: 'Needs Attention' },
  { href: '/views/blockers', label: 'Blockers' },
  { href: '/tasks/new', label: 'Add Task' },
  { href: '/hermes', label: 'Hermes' },
]

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="min-h-full bg-background text-foreground">
        <div className="flex min-h-screen">
          <aside className="w-60 shrink-0 border-r border-[var(--line)] bg-[var(--panel)] px-5 py-4">
            <div className="border-b border-[var(--line)] pb-4">
              <div className="mono text-xs text-[var(--muted)]">kira-hq v0.2</div>
              <div className="text-lg font-semibold tracking-tight">Kira-HQ</div>
            </div>
            <nav className="flex flex-col gap-1 py-4 text-sm">
              {navItems.map((item) => (
                <Link key={item.href} href={item.href} className="rounded-md px-3 py-2 hover:bg-[var(--card)]">
                  {item.label}
                </Link>
              ))}
            </nav>
          </aside>
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </body>
    </html>
  )
}
