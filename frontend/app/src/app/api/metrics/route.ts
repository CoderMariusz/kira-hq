import { proxyToBackend } from '@/lib/server-api'

export const dynamic = 'force-dynamic'

export async function GET() {
  return proxyToBackend('/metrics')
}
