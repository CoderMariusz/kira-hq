import { expect, test } from '@playwright/test'

import { fixtureTaskList, installApiMocks } from './support'

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3100'

test('PRD §6.15 scenario: 10 tasks visible, click first, refresh to 11 after add', async ({ page }) => {
  let currentTasks = [...fixtureTaskList]

  await installApiMocks(page)

  await page.route(`${apiUrl}/projects/fixture`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        project: { name: 'fixture', title: 'Fixture Project', root_path: '~/Projects/fixture' },
        tasks: currentTasks,
      }),
    })
  })

  await page.route(`${apiUrl}/tasks`, async (route) => {
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
  })

  await page.goto('/projects/fixture')

  await expect(page.getByTestId('task-card')).toHaveCount(10)
  await page.getByTestId('task-card').first().click()
  await expect(page.getByText(currentTasks[0].title)).toBeVisible()

  await page.evaluate(async ({ apiUrl, authorization }) => {
    await fetch(`${apiUrl}/tasks`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        authorization,
      },
      body: JSON.stringify({
        project: 'fixture',
        title: 'Fixture task 11',
        description: 'Added during PRD scenario',
        priority: 'high',
        parent_id: '10',
      }),
    })
  }, {
    apiUrl,
    authorization: `Basic ${Buffer.from('admin:admin').toString('base64')}`,
  })

  await page.reload()
  await expect(page.getByTestId('task-card')).toHaveCount(11)
})
