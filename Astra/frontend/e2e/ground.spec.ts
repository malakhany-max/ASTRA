import { expect, test } from '@playwright/test'

test('Ground Station opens without sign-in and the command log works', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByLabel('Username')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Crew overview' })).toBeVisible()
  await expect(page.locator('.crew-card')).toHaveCount(3)

  await page.getByRole('link', { name: 'Commands' }).click()
  await expect(page.getByRole('heading', { name: 'Change the plan, keep the trail' })).toBeVisible()
  await page.getByRole('button', { name: 'Send command' }).click()
  await expect(page.locator('.command-card').first()).toBeVisible()
})

test('Astronaut detail sections share one grid and alerts open on demand', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/crew/ast-zain')

  const alerts = page.locator('details.alert-band')
  const summary = alerts.locator('summary')
  const body = alerts.locator('.alert-band__body')
  await expect(summary.locator('.badge')).toHaveText(/^\d+ open$/)
  await expect(alerts).toHaveJSProperty('open', false)
  await expect(body).not.toBeVisible()

  await summary.click()
  await expect(alerts).toHaveJSProperty('open', true)
  await expect(body).toBeVisible()
  const count = Number((await summary.locator('.badge').innerText()).split(' ')[0])
  await expect(alerts.locator('.alert')).toHaveCount(count)
  await expect(page.getByRole('button', { name: /Show all|Show less/ })).toHaveCount(0)

  await summary.press('Enter')
  await expect(alerts).toHaveJSProperty('open', false)
  await summary.press('Space')
  await expect(body).toBeVisible()

  expect(await alerts.evaluate((node) => node.getBoundingClientRect().width)).toBeCloseTo(await page.locator('.detail-grid').evaluate((node) => node.getBoundingClientRect().width), 0)
  await summary.click()
  const cards = page.locator('.detail-grid > .panel')
  await expect(cards).toHaveCount(8)
  for (const title of ['Open alerts', 'Radiation', 'Exposure follow-up', 'Plan progress', 'Companion context', 'New command', 'Check-ins', 'Medical notes']) {
    await expect(cards.filter({ has: page.getByText(title, { exact: true }) })).toHaveCount(1)
  }
  for (const [width, rowCount] of [[1440, 4], [1024, 5], [390, 8]]) {
    await page.setViewportSize({ width, height: 900 })
    const grid = await page.locator('.detail-grid').evaluate((node) => node.getBoundingClientRect().toJSON())
    const boxes = await cards.evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().toJSON()))
    const rows = new Map<number, Array<{ left: number; right: number }>>()
    for (const box of boxes) rows.set(box.top, [...(rows.get(box.top) ?? []), box])
    expect(rows.size).toBe(rowCount)
    for (const row of rows.values()) {
      expect(Math.min(...row.map((box) => box.left))).toBeCloseTo(grid.left, 0)
      expect(Math.max(...row.map((box) => box.right))).toBeCloseTo(grid.right, 0)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
  }
  await summary.click()

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(summary).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await summary.click()
  await expect(body).not.toBeVisible()
  expect(await alerts.evaluate((node) => node.getBoundingClientRect().height)).toBeLessThan(90)
})
