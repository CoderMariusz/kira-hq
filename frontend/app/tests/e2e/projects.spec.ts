import { expect, test } from '@playwright/test'

import { defaultProjectSummaries, expectProjectCardCounters, installApiMocks } from './support'

test('projects page shows project cards with progress and status counters', async ({ page }) => {
  await installApiMocks(page)

  await page.goto('/')

  await expect(page.getByTestId('page-projects')).toBeVisible()
  await expect(page.getByTestId('project-grid')).toBeVisible()
  await expect(page.getByTestId('project-card')).toHaveCount(defaultProjectSummaries.length)
  await expectProjectCardCounters(page, 'kira-hq', defaultProjectSummaries[0].status_counts)
  await expect(page.getByTestId('project-card').first()).toContainText(`${defaultProjectSummaries[0].progress_pct}%`)
})
