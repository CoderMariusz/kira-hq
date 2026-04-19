import { expect, test } from '@playwright/test'

import { installApiMocks } from './support'

test('blockers page shows blocked task rows', async ({ page }) => {
  await installApiMocks(page)

  await page.goto('/views/blockers')

  await expect(page.getByTestId('page-blockers')).toBeVisible()
  await expect(page.getByTestId('blockers-table')).toBeVisible()
  await expect(page.getByTestId('blocker-row')).toHaveCount(2)
  await expect(page.getByTestId('blocker-row').first()).toContainText('kira-hq')
})
