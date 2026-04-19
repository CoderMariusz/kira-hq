import { expect, test } from '@playwright/test'

import { installApiMocks } from './support'

test('needs-attention page shows all 5 trigger sections', async ({ page }) => {
  await installApiMocks(page)

  await page.goto('/views/needs-attention')

  await expect(page.getByTestId('page-needs-attention')).toBeVisible()
  await expect(page.getByTestId('section-blocked')).toBeVisible()
  await expect(page.getByTestId('section-stale')).toBeVisible()
  await expect(page.getByTestId('section-failed')).toBeVisible()
  await expect(page.getByTestId('section-budget')).toBeVisible()
  await expect(page.getByText(/needs human/i)).toBeVisible()
  await expect(page.getByTestId('attention-item')).toHaveCount(6)
})
