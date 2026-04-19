import { expect, test } from '@playwright/test'

import { expectBasicAuthHeader, installApiMocks, interceptTaskCreate } from './support'

test('add-task form posts TaskCreate payload with Basic auth', async ({ page }) => {
  await installApiMocks(page)
  const posts = await interceptTaskCreate(page)

  await page.goto('/tasks/new')

  await expect(page.getByTestId('page-add')).toBeVisible()
  await expect(page.getByTestId('add-form')).toBeVisible()
  await expect(page.getByTestId('f-project')).toBeVisible()
  await expect(page.getByTestId('f-title')).toBeVisible()
  await expect(page.getByTestId('f-desc')).toBeVisible()
  await expect(page.getByTestId('f-priority')).toBeVisible()
  await expect(page.getByTestId('f-parent')).toBeVisible()

  await page.getByTestId('f-project').selectOption('kira-hq')
  await page.getByTestId('f-title').fill('11th task created')
  await page.getByTestId('f-desc').fill('Created from Playwright RED spec')
  await page.getByTestId('f-priority').selectOption('high')
  await page.getByTestId('f-parent').fill('10')
  await page.getByTestId('f-submit').click()

  await expect.poll(() => posts.length).toBe(1)
  expectBasicAuthHeader(posts[0].headers)
  await expect(posts[0].body ?? '').toContain('11th task created')
})
