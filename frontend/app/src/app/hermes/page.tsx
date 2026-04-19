import { HERMES_URL } from '@/lib/api'

export default function HermesPage() {
  return (
    <section data-testid="page-hermes" className="max-w-6xl p-8">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Hermes</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">Embedded dashboard</p>
        </div>
        <a
          href={HERMES_URL}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="hermes-popout"
          className="mono rounded border border-[var(--line)] px-2 py-1 text-xs"
        >
          ⧉ Open in new window
        </a>
      </div>
      <div data-testid="hermes-iframe-wrapper" className="relative flex aspect-[16/9] w-full items-center justify-center overflow-hidden rounded-md border border-[var(--line)] bg-[var(--card)]">
        <iframe src={HERMES_URL} title="Hermes dashboard" className="h-full w-full border-0" />
      </div>
    </section>
  )
}
