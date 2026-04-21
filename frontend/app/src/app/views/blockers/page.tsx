'use client'

import { useEffect, useState } from 'react'

import { getBlockers, type Blocker } from '@/lib/api'

export default function BlockersPage() {
  const [rows, setRows] = useState<Blocker[]>([])

  useEffect(() => {
    void getBlockers().then(setRows)
  }, [])

  return (
    <section data-testid="page-blockers" className="max-w-5xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Blockers</h1>
      <div className="overflow-hidden rounded-md border border-[var(--line)] bg-[var(--card)]">
        <table data-testid="blockers-table" className="w-full text-sm">
          <thead className="bg-[var(--panel)] text-left text-xs uppercase text-[var(--muted)]">
            <tr>
              <th className="px-3 py-2">Project</th>
              <th className="px-3 py-2">ID</th>
              <th className="px-3 py-2">Title</th>
              <th className="px-3 py-2">Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.project}-${row.task_id}`} data-testid="blocker-row" className="border-t border-[var(--line)]">
                <td className="px-3 py-2 mono text-xs">{row.project}</td>
                <td className="px-3 py-2 mono text-xs">T-{row.task_id}</td>
                <td className="px-3 py-2">{row.title}</td>
                <td className="px-3 py-2">{row.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
