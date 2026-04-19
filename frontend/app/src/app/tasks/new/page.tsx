'use client'

import { useState } from 'react'

import { createTask } from '@/lib/api'

const projects = ['kira-hq', 'monopilot', 'sandbox', 'fixture']

export default function AddTaskPage() {
  const [project, setProject] = useState('kira-hq')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<'low' | 'medium' | 'high'>('medium')
  const [parentId, setParentId] = useState('')
  const [status, setStatus] = useState('')

  async function onSubmit() {
    setStatus('Submitting…')
    await createTask({
      project,
      title,
      description,
      priority,
      parent_id: parentId || undefined,
    })
    setStatus('Created')
  }

  return (
    <section data-testid="page-add" className="max-w-2xl p-8">
      <h1 className="mb-6 text-2xl font-semibold">Add Task</h1>
      <form data-testid="add-form" className="space-y-4 rounded-md border border-[var(--line)] bg-[var(--card)] p-5" onSubmit={(event) => {
        event.preventDefault()
        void onSubmit()
      }}>
        <div>
          <label className="mono mb-1 block text-xs text-[var(--muted)]" htmlFor="project">Project</label>
          <select id="project" data-testid="f-project" value={project} onChange={(event) => setProject(event.target.value)} className="w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm">
            {projects.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </div>
        <div>
          <label className="mono mb-1 block text-xs text-[var(--muted)]" htmlFor="title">Title</label>
          <input id="title" data-testid="f-title" value={title} onChange={(event) => setTitle(event.target.value)} className="w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="mono mb-1 block text-xs text-[var(--muted)]" htmlFor="description">Description</label>
          <textarea id="description" data-testid="f-desc" value={description} onChange={(event) => setDescription(event.target.value)} rows={4} className="w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mono mb-1 block text-xs text-[var(--muted)]" htmlFor="priority">Priority</label>
            <select id="priority" data-testid="f-priority" value={priority} onChange={(event) => setPriority(event.target.value as 'low' | 'medium' | 'high')} className="w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm">
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
          </div>
          <div>
            <label className="mono mb-1 block text-xs text-[var(--muted)]" htmlFor="parent">Parent task (optional)</label>
            <input id="parent" data-testid="f-parent" value={parentId} onChange={(event) => setParentId(event.target.value)} className="w-full rounded-md border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm" />
          </div>
        </div>
        <div className="flex items-center justify-end gap-3 pt-2">
          {status ? <div className="text-sm text-[var(--muted)]">{status}</div> : null}
          <button type="submit" data-testid="f-submit" className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-black">Create</button>
        </div>
      </form>
    </section>
  )
}
