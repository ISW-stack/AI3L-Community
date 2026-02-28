import { test, expect } from '@playwright/test'

test('home page loads and shows title', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('h1')).toContainText('AI3L Community')
})

test('home page shows stack status section', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('text=Stack Status')).toBeVisible()
})
