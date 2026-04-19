import { expect, test } from '@playwright/test'

import { installApiMocks } from './support'

const hermesUrl = process.env.NEXT_PUBLIC_HERMES_URL ?? 'http://localhost:4000'

test('hermes page renders iframe wrapper and persistent popout link', async ({ page }) => {
  await installApiMocks(page)

  await page.goto('/hermes')

  await expect(page.getByTestId('page-hermes')).toBeVisible()
  await expect(page.getByTestId('hermes-iframe-wrapper')).toBeVisible()
  const popout = page.getByTestId('hermes-popout')
  await expect(popout).toBeVisible()
  await expect(popout).toHaveAttribute('target', '_blank')
  await expect(popout).toHaveAttribute('rel', /noopener/)
  await expect(popout).toHaveAttribute('href', hermesUrl)
  await expect(page.locator(`iframe[src="${hermesUrl}"]`)).toHaveCount(1)
})
