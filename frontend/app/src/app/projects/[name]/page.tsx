'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'

import { getProject, titleize, type ProjectDetail, type ProjectTask, type Status } from '@/lib/api'

const columns: Array<{ key: Status; label: string }> = [
  { key: 'pending', label: 'Pending' },
  { key: 'in-progress', label: 'In progress' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'done', label: 'Done' },
]

export default function ProjectDetailPage() {
  const params = useParams<{ name: string }>()
  const name = typeof params?.name === 'string' ? params.name : ''
  const [detail, setDetail] = useState<ProjectDetail | null>(null)
  const [selected, setSelected] = useState<ProjectTask | null>(null)

  useEffect(() => {
    if (!name) return
    void getProject(name).then((data) => {
      setDetail(data)
      setSelected(null)
    })
  }, [name])

  const groups = useMemo(() => {
    const tasks = detail?.tasks ?? []
    return Object.fromEntries(columns.map((column) => [column.key, tasks.filter((task) => task.status === column.key)])) as Record<Status, ProjectTask[]>
  }, [detail])

  const project = detail?.project ?? { name, title: titleize(name), root_path: `~/Projects/${name}` }

  return (
    <section data-testid="page-project-detail" className="max-w-7xl p-8">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <div className="mono mb-1 text-xs text-[var(--muted)]"><Link href="/">projects</Link> / {project.name}</div>
          <h1 className="text-2xl font-semibold">{project.title || titleize(project.name)}</h1>
          <div className="mono mt-1 text-xs text-[var(--muted)]">{project.root_path}</div>
        </div>
        <Link href="/tasks/new" className="rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-medium text-black">+ New task</Link>
      </div>

      {selected ? <div className="mb-4 rounded-md border border-[var(--line)] bg-[var(--panel)] p-3 text-sm">{selected.title}</div> : null}

      <div data-testid="kanban" className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        {columns.map((column) => (
          <div key={column.key} data-testid="kanban-col" data-col={column.key}>
            <div className="mb-2 text-sm font-medium">{column.label} <span className="mono text-xs text-[var(--muted)]">{groups[column.key]?.length ?? 0}</span></div>
            <div className="flex flex-col gap-2">
              {(groups[column.key] ?? []).length ? groups[column.key].map((task) => (
                <article
                  key={task.id}
                  data-testid="task-card"
                  onClick={() => setSelected(task)}
                  className="cursor-pointer rounded-md border border-[var(--line)] bg-[var(--card)] p-3"
                  >
                  <div className="mb-1 flex items-center justify-between gap-3">
                    <span className="mono text-[10px] text-[var(--muted)]">T-{task.id}</span>
                    <span className="mono text-[10px] uppercase text-[var(--muted)]">{task.priority}</span>
                  </div>
                  <div className="text-sm leading-snug">{task.title}</div>
                  <div className="mono mt-1 text-[10px] text-[var(--muted)]">owner: {task.owner}</div>
                </article>
              )) : <div className="text-xs italic text-[var(--muted)]">—</div>}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
