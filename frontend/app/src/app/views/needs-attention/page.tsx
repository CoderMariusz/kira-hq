'use client'

import { useEffect, useState } from 'react'

import { getNeedsAttention, type AttentionItem, type NeedsAttention } from '@/lib/api'

function AttentionRows({ items, suffix }: { items: AttentionItem[]; suffix?: string }) {
  if (!items.length) {
    return <div className="rounded-md border border-[var(--line)] bg-[var(--card)] p-3 text-xs italic text-[var(--muted)]">None</div>
  }

  return (
    <div className="rounded-md border border-[var(--line)] bg-[var(--card)]">
      {items.map((item, index) => (
        <div key={`${item.project}-${item.title}-${index}`} data-testid="attention-item" className="flex gap-3 border-b border-[var(--line)] p-3 last:border-b-0">
          <span className="mono w-24 text-xs text-[var(--muted)]">{item.project}</span>
          <span className="flex-1 text-sm">{item.title}</span>
          {suffix ? <span className="mono text-xs text-[var(--muted)]">{suffix}</span> : item.age_h != null ? <span className="mono text-xs text-[var(--muted)]">{item.age_h}h</span> : null}
        </div>
      ))}
    </div>
  )
}

export default function NeedsAttentionPage() {
  const [data, setData] = useState<NeedsAttention | null>(null)

  useEffect(() => {
    void getNeedsAttention().then(setData)
  }, [])

  const model = data ?? { blocked_gt_48h: [], stale_gt_72h: [], needs_human: [], failed_crons: [], budget: [] }

  return (
    <section data-testid="page-needs-attention" className="max-w-5xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Needs Attention</h1>
      <div className="space-y-6">
        <div data-testid="section-blocked">
          <h2 className="mb-2 text-sm font-medium">Blocked &gt; 48h</h2>
          <AttentionRows items={model.blocked_gt_48h} />
        </div>
        <div data-testid="section-stale">
          <h2 className="mb-2 text-sm font-medium">High-prio stale &gt; 72h</h2>
          <AttentionRows items={model.stale_gt_72h} />
        </div>
        <div>
          <h2 className="mb-2 text-sm font-medium">Needs human</h2>
          <AttentionRows items={model.needs_human} />
        </div>
        <div data-testid="section-failed">
          <h2 className="mb-2 text-sm font-medium">Failed crons &lt; 24h</h2>
          <AttentionRows items={model.failed_crons} />
        </div>
        <div data-testid="section-budget">
          <h2 className="mb-2 text-sm font-medium">Budget exceeded</h2>
          <AttentionRows items={model.budget} />
        </div>
      </div>
    </section>
  )
}
