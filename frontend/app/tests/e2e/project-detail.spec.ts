import { expect, test } from '@playwright/test'

import { installApiMocks } from './support'

test('project detail page shows 4-column kanban for kira-hq', async ({ page }) => {
  await installApiMocks(page)

  await page.goto('/projects/kira-hq')

  await expect(page.getByTestId('page-project-detail')).toBeVisible()
  await expect(page.getByTestId('kanban')).toBeVisible()
  await expect(page.getByTestId('kanban-col')).toHaveCount(4)
  await expect(page.locator('[data-testid="kanban-col"][data-col="pending"]')).toHaveCount(1)
  await expect(page.locator('[data-testid="kanban-col"][data-col="in-progress"]')).toHaveCount(1)
  await expect(page.locator('[data-testid="kanban-col"][data-col="blocked"]')).toHaveCount(1)
  await expect(page.locator('[data-testid="kanban-col"][data-col="done"]')).toHaveCount(1)
  await expect(page.getByTestId('task-card')).toHaveCount(6)
})
