import { expect, Page, Route } from '@playwright/test'

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
  status: 'pending' | 'in-progress' | 'blocked' | 'done'
  priority: 'low' | 'medium' | 'high'
  owner: string
  updated_at: string
}

export const defaultProjectSummaries: ProjectSummary[] = [
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

export const defaultProjectDetail = {
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
  ] satisfies ProjectTask[],
}

export const defaultNeedsAttention = {
  blocked_gt_48h: [
    { project: 'kira-hq', title: 'Hermes iframe embed blocked', age_h: 54 },
    { project: 'monopilot', title: 'Task sync broken', age_h: 72 },
  ],
  stale_gt_72h: [
    { project: 'monopilot', title: 'Review queue stale', age_h: 80 },
  ],
  needs_human: [
    { project: 'kira-hq', title: 'Approve prototype layout' },
  ],
  failed_crons: [
    { project: 'sandbox', title: 'nightly render failed' },
  ],
  budget: [
    { project: 'kira-hq', title: 'OpenRouter budget > 80%' },
  ],
}

export const defaultBlockers = [
  { project: 'kira-hq', task_id: '21', title: 'Blocked task', reason: 'Waiting for human input' },
  { project: 'monopilot', task_id: '14', title: 'Task sync broken', reason: 'External API outage' },
]

export const fixtureTaskList: ProjectTask[] = Array.from({ length: 10 }, (_, index) => ({
  id: String(index + 1),
  title: `Fixture task ${index + 1}`,
  description: `Fixture task ${index + 1} description`,
  status: index < 3 ? 'pending' : index < 5 ? 'in-progress' : index < 7 ? 'blocked' : 'done',
  priority: 'high',
  owner: 'fixture',
  updated_at: '2026-04-19T08:00:00Z',
}))

export async function installApiMocks(page: Page) {
  await page.route('**/projects', async (route) => {
    await fulfillJson(route, defaultProjectSummaries)
  })

  await page.route('**/projects/kira-hq', async (route) => {
    await fulfillJson(route, defaultProjectDetail)
  })

  await page.route('**/projects/fixture', async (route) => {
    await fulfillJson(route, {
      project: { name: 'fixture', title: 'Fixture Project', root_path: '~/Projects/fixture' },
      tasks: fixtureTaskList,
    })
  })

  await page.route('**/views/needs-attention', async (route) => {
    await fulfillJson(route, defaultNeedsAttention)
  })

  await page.route('**/views/blockers', async (route) => {
    await fulfillJson(route, defaultBlockers)
  })

  await page.route('**/metrics', async (route) => {
    await fulfillJson(route, { projects: 3, tasks: 28, blocked: 2 })
  })
}

export async function expectProjectCardCounters(page: Page, name: string, counts: ProjectSummary['status_counts']) {
  const card = page.getByTestId('project-card').filter({ hasText: name }).first()
  await expect(card).toContainText(String(counts.pending))
  await expect(card).toContainText(String(counts.in_progress))
  await expect(card).toContainText(String(counts.blocked))
  await expect(card).toContainText(String(counts.done))
}

export async function interceptTaskCreate(page: Page) {
  const seen: Array<{ headers: Record<string, string>; body: string | null }> = []

  await page.route('**/tasks', async (route) => {
    const request = route.request()
    seen.push({
      headers: request.headers(),
      body: request.postData(),
    })
    await fulfillJson(route, { id: '11', title: '11th task created' }, 201)
  })

  return seen
}

export function expectBasicAuthHeader(headers: Record<string, string>) {
  const authorization = headers['authorization']
  expect(authorization, 'expected Basic auth header on POST /tasks').toBeTruthy()
  expect(authorization?.startsWith('Basic ')).toBeTruthy()
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}
