import { expect, test } from '@playwright/test'

test('astronaut home loads and the body model responds', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { level: 1 })).toContainText('Zain')
  await expect(page.getByRole('link', { name: 'Body' })).toBeVisible()

  await page.getByRole('link', { name: 'Body' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toContainText('body model')
  await expect(page.locator('.organ-hotspot')).toHaveCount(4)

  await page.locator('.organ-hotspot').filter({ hasText: 'Brain' }).click()
  await expect(page.locator('.organ-detail__title')).toContainText('Brain')
})
