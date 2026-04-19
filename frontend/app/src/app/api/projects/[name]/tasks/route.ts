import { proxyToBackend } from '@/lib/server-api'

export const dynamic = 'force-dynamic'

export async function GET(_request: Request, context: RouteContext<'/api/projects/[name]/tasks'>) {
  const { name } = await context.params
  return proxyToBackend(`/projects/${encodeURIComponent(name)}/tasks`)
}

export async function POST(request: Request, context: RouteContext<'/api/projects/[name]/tasks'>) {
  const { name } = await context.params

  return proxyToBackend(`/projects/${encodeURIComponent(name)}/tasks`, {
    method: 'POST',
    headers: {
      'content-type': request.headers.get('content-type') ?? 'application/json',
    },
    body: await request.text(),
  })
}
