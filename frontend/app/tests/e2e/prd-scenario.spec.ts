import { expect, test } from '@playwright/test'

import { fixtureTaskList, installApiMocks } from './support'

test('PRD §6.15 scenario: 10 tasks visible, click first, refresh to 11 after add', async ({ page }) => {
  let currentTasks = [...fixtureTaskList]

  await installApiMocks(page)

  await page.route('**/api/projects/fixture/tasks', async (route) => {
    if (route.request().method() === 'POST') {
      currentTasks = [
        ...currentTasks,
        {
          id: '11',
          title: 'Fixture task 11',
          description: 'Added during PRD scenario',
          status: 'pending',
          priority: 'high',
          owner: 'fixture',
          updated_at: '2026-04-19T09:00:00Z',
        },
      ]

      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ id: '11' }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(currentTasks),
    })
  })

  await page.goto('/projects/fixture')

  await expect(page.getByTestId('task-card')).toHaveCount(10)
  await page.getByTestId('task-card').first().click()
  await expect(page.getByText(currentTasks[0].title, { exact: true }).first()).toBeVisible()

  await page.evaluate(async () => {
    await fetch('/api/projects/fixture/tasks', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        title: 'Fixture task 11',
        description: 'Added during PRD scenario',
        priority: 'high',
        parent_id: '10',
      }),
    })
  })

  await page.reload()
  await expect(page.getByTestId('task-card')).toHaveCount(11)
})
