'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import { getProjects, type ProjectSummary } from '@/lib/api'

export default function HomePage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([])

  useEffect(() => {
    void getProjects().then(setProjects)
  }, [])

  return (
    <section data-testid="page-projects" className="max-w-6xl p-8">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Projects</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">All projects from <span className="mono">~/.kira-hq/projects.yaml</span></p>
        </div>
        <Link href="/tasks/new" className="rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-medium text-black">
          + New task
        </Link>
      </div>

      <div data-testid="project-grid" className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {projects.map((project) => (
          <Link
            key={project.name}
            href={`/projects/${project.name}`}
            data-testid="project-card"
            className="block rounded-lg border border-[var(--line)] bg-[var(--card)] p-4"
          >
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="font-semibold">{project.name}</div>
              <span className="mono text-xs text-[var(--muted)]">{project.progress_pct}%</span>
            </div>
            <div className="mono mb-3 text-xs text-[var(--muted)]">{project.root_path}</div>
            <div className="flex flex-wrap gap-3 text-xs">
              <span><span className="mono">{project.status_counts.done}</span> done</span>
              <span><span className="mono">{project.status_counts.in_progress}</span> in-progress</span>
              <span><span className="mono">{project.status_counts.blocked}</span> blocked</span>
              <span><span className="mono">{project.status_counts.pending}</span> pending</span>
            </div>
            <div className="mt-3 h-1 overflow-hidden rounded-full bg-[var(--line)]">
              <div className="h-full bg-[var(--ok)]" style={{ width: `${project.progress_pct}%` }} />
            </div>
          </Link>
        ))}
      </div>
    </section>
  )
}
