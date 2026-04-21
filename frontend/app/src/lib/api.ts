export const HERMES_URL = process.env.NEXT_PUBLIC_HERMES_URL ?? 'http://localhost:4000'
export const USE_MOCK = process.env.NEXT_PUBLIC_MOCK === '1'

const FRONTEND_API_BASE = '/api'

export type Status = 'pending' | 'in-progress' | 'blocked' | 'done'
export type Priority = 'low' | 'medium' | 'high'

export type ProjectSummary = {
  name: string
  title: string
  root_path: string
  status_counts: {
    pending: number
    in_progress: number
    blocked: number
    done: number
  }
  progress_pct: number
}

export type ProjectTask = {
  id: string
  title: string
  description: string
  status: Status
  priority: Priority
  owner: string
  updated_at: string
}

export type ProjectDetail = {
  project: {
    name: string
    title: string
    root_path: string
  }
  tasks: ProjectTask[]
}

export type AttentionItem = {
  project: string
  title: string
  age_h?: number
}

export type NeedsAttention = {
  blocked_gt_48h: AttentionItem[]
  stale_gt_72h: AttentionItem[]
  needs_human: AttentionItem[]
  failed_crons: AttentionItem[]
  budget: AttentionItem[]
}

export type Blocker = {
  project: string
  task_id: string
  title: string
  reason: string
}

type BackendProjectSummary = {
  name: string
  path: string
  status?: string
  priority?: string
  tasks_summary?: Record<string, number>
}

type BackendTask = {
  id?: string | number
  title?: string
  description?: string
  status?: string
  priority?: string
  owner?: string
  updated_at?: string
}

const mockProjects: ProjectSummary[] = [
  {
    name: 'kira-hq',
    title: 'Kira HQ',
    root_path: '~/Projects/kira-hq',
    status_counts: { pending: 8, in_progress: 2, blocked: 1, done: 17 },
    progress_pct: 68,
  },
  {
    name: 'monopilot',
    title: 'Monopilot',
    root_path: '~/Projects/monopilot',
    status_counts: { pending: 6, in_progress: 1, blocked: 2, done: 9 },
    progress_pct: 50,
  },
  {
    name: 'sandbox',
    title: 'Sandbox',
    root_path: '~/Projects/sandbox',
    status_counts: { pending: 4, in_progress: 0, blocked: 0, done: 3 },
    progress_pct: 43,
  },
]

const mockProjectDetails: Record<string, ProjectDetail> = {
  'kira-hq': {
    project: {
      name: 'kira-hq',
      title: 'Kira HQ',
      root_path: '~/Projects/kira-hq',
    },
    tasks: [
      { id: '18', title: 'Module 3 frontend', description: 'Build dashboard UI', status: 'pending', priority: 'high', owner: 'qwen', updated_at: '2026-04-19T08:00:00Z' },
      { id: '19', title: 'Project view polish', description: 'Refine detail page', status: 'pending', priority: 'medium', owner: 'qwen', updated_at: '2026-04-19T08:00:00Z' },
      { id: '20', title: 'Hermes integration', description: 'Wire Hermes entrypoints', status: 'in-progress', priority: 'high', owner: 'hermes', updated_at: '2026-04-19T08:10:00Z' },
      { id: '21', title: 'Blocked task', description: 'Waiting for human input', status: 'blocked', priority: 'high', owner: 'human', updated_at: '2026-04-19T07:00:00Z' },
      { id: '16', title: 'FastAPI backend', description: 'App factory + endpoints', status: 'done', priority: 'high', owner: 'opus', updated_at: '2026-04-19T06:00:00Z' },
      { id: '17', title: 'HTTP Basic auth', description: 'Protect business routes', status: 'done', priority: 'high', owner: 'opus', updated_at: '2026-04-19T06:30:00Z' },
    ],
  },
}

const mockNeedsAttention: NeedsAttention = {
  blocked_gt_48h: [
    { project: 'kira-hq', title: 'Hermes iframe embed blocked', age_h: 54 },
    { project: 'monopilot', title: 'Task sync broken', age_h: 72 },
  ],
  stale_gt_72h: [{ project: 'monopilot', title: 'Review queue stale', age_h: 80 }],
  needs_human: [{ project: 'kira-hq', title: 'Approve prototype layout' }],
  failed_crons: [{ project: 'sandbox', title: 'nightly render failed' }],
  budget: [{ project: 'kira-hq', title: 'OpenRouter budget > 80%' }],
}

const mockBlockers: Blocker[] = [
  { project: 'kira-hq', task_id: '21', title: 'Blocked task', reason: 'Waiting for human input' },
  { project: 'monopilot', task_id: '14', title: 'Task sync broken', reason: 'External API outage' },
]

async function getJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${FRONTEND_API_BASE}${path}`, { cache: 'no-store' })
    if (!response.ok) throw new Error(`Request failed: ${path}`)
    return (await response.json()) as T
  } catch (error) {
    if (USE_MOCK) return fallback
    throw error
  }
}

export async function getProjects() {
  const projects = await getJson<BackendProjectSummary[]>('/projects', mockProjects as never)
  return projects.map(mapProjectSummary)
}

export async function getProject(name: string) {
  const mockDetail = mockProjectDetails[name] ?? {
    project: { name, title: titleize(name), root_path: `~/Projects/${name}` },
    tasks: [],
  }

  const [projects, tasks] = await Promise.all([
    getJson<BackendProjectSummary[]>('/projects', [
      {
        name: mockDetail.project.name,
        path: mockDetail.project.root_path,
        tasks_summary: summarizeMockTasks(mockDetail.tasks),
      },
    ]),
    getJson<BackendTask[]>(`/projects/${encodeURIComponent(name)}/tasks`, mockDetail.tasks),
  ])

  const project = projects.find((entry) => entry.name === name)

  return {
    project: {
      name,
      title: titleize(name),
      root_path: project?.path ?? `~/Projects/${name}`,
    },
    tasks: tasks.map(mapProjectTask),
  } satisfies ProjectDetail
}

export function getNeedsAttention() {
  return getJson('/views/needs-attention', mockNeedsAttention)
}

export function getBlockers() {
  return getJson('/views/blockers', mockBlockers)
}

export async function createTask(payload: {
  project: string
  title: string
  description: string
  priority: Priority
  parent_id?: string
}) {
  const response = await fetch(`${FRONTEND_API_BASE}/projects/${encodeURIComponent(payload.project)}/tasks`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      title: payload.title,
      description: payload.description,
      priority: payload.priority,
      parent_id: payload.parent_id,
    }),
  })

  if (!response.ok) throw new Error('Failed to create task')
  return response.json().catch(() => null)
}

function mapProjectSummary(project: BackendProjectSummary): ProjectSummary {
  const pending = countSummary(project.tasks_summary, 'pending')
  const inProgress = countSummary(project.tasks_summary, 'in-progress', 'in_progress')
  const blocked = countSummary(project.tasks_summary, 'blocked')
  const done = countSummary(project.tasks_summary, 'done')
  const total = countSummary(project.tasks_summary, 'total') || pending + inProgress + blocked + done

  return {
    name: project.name,
    title: titleize(project.name),
    root_path: project.path,
    status_counts: {
      pending,
      in_progress: inProgress,
      blocked,
      done,
    },
    progress_pct: total > 0 ? Math.round((done / total) * 100) : 0,
  }
}

function mapProjectTask(task: BackendTask): ProjectTask {
  const rawStatus = String(task.status ?? 'pending')
  const status = normalizeStatus(rawStatus)
  const priority = normalizePriority(String(task.priority ?? 'medium'))

  return {
    id: String(task.id ?? '').replace(/^T-/, ''),
    title: task.title?.trim() || `Task ${task.id ?? ''}`.trim(),
    description: task.description ?? '',
    status,
    priority,
    owner: task.owner?.trim() || 'unassigned',
    updated_at: task.updated_at ?? '',
  }
}

function countSummary(summary: Record<string, number> | undefined, ...keys: string[]) {
  for (const key of keys) {
    const value = summary?.[key]
    if (typeof value === 'number') return value
  }

  return 0
}

function normalizeStatus(value: string): Status {
  switch (value) {
    case 'in_progress':
      return 'in-progress'
    case 'blocked':
    case 'done':
    case 'in-progress':
    case 'pending':
      return value
    default:
      return 'pending'
  }
}

function normalizePriority(value: string): Priority {
  switch (value) {
    case 'low':
    case 'high':
    case 'medium':
      return value
    default:
      return 'medium'
  }
}

function summarizeMockTasks(tasks: ProjectTask[]) {
  return tasks.reduce<Record<string, number>>((summary, task) => {
    summary.total = (summary.total ?? 0) + 1
    summary[task.status] = (summary[task.status] ?? 0) + 1
    return summary
  }, {})
}

export function titleize(value: string) {
  return value
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}
