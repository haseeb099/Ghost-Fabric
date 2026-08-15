import { expect, test } from '@playwright/test'

const ONBOARDING_KEY = 'ghost-fabric.onboarding-v1'

test.describe('console with onboarding dismissed', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript((key) => {
      localStorage.setItem(key, 'seen')
    }, ONBOARDING_KEY)
  })

  test('renders the live simulation console and audit controls', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('heading', { name: /ghost fabric/i })).toBeVisible()
    await expect(page.getByRole('region', { name: 'CHAMELEON' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'PROPHET' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'PHOENIX' })).toBeVisible()
    await expect(page.getByRole('region', { name: /guided fictional exercise phase/i })).toBeVisible()
    await expect(page.getByRole('region', { name: /simulation situation brief/i })).toContainText(/safe next step/i)
    await expect(page.getByRole('region', { name: /simulation situation brief/i })).toContainText(/test data provenance/i)
    await expect(page.getByRole('button', { name: /set scenario speed to 2 times/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /export/i })).toBeVisible()
    await expect(page.getByLabel(/operator session controls/i)).toContainText(/session/i)
    await expect(page.getByRole('button', { name: /what is this/i })).toBeVisible()
  })

  test('supports keyboard skip navigation', async ({ page }) => {
    await page.goto('/')
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: /skip to simulation controls/i })).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.locator('#main-console')).toBeFocused()
  })

  test('golden path: fail, branch, approve, export', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /ghost fabric/i })).toBeVisible()
    await page.getByRole('button', { name: /local optional/i }).click()
    await expect(page.getByText('API LIVE')).toBeVisible({ timeout: 30000 })

    const reset = page.getByRole('button', { name: 'Reset scenario', exact: true })
    await expect(reset).toBeEnabled({ timeout: 15000 })
    page.once('dialog', (dialog) => dialog.accept())
    await reset.click()
    await expect(page.getByRole('button', { name: /inject node loss/i })).toBeEnabled({ timeout: 15000 })

    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /inject node loss/i }).click()
    await expect(page.getByRole('region', { name: 'CHAMELEON' })).toContainText(/atlas/i)

    await page.getByRole('button', { name: /civil bridge review/i }).click()
    await expect(page.getByText(/tabletop branch review completed/i)).toBeVisible()

    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /human approval required/i }).click()
    await expect(page.getByRole('button', { name: /workflow restored/i })).toBeVisible({ timeout: 15000 })

    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: /export/i }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toMatch(/ghost-fabric-audit-/)
  })

  test('citizen grid requires corroboration and falls back when a channel is jammed', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /local optional/i }).click()
    await expect(page.getByText('API LIVE')).toBeVisible({ timeout: 30000 })

    const reset = page.getByRole('button', { name: 'Reset scenario', exact: true })
    await expect(reset).toBeEnabled({ timeout: 15000 })
    page.once('dialog', (dialog) => dialog.accept())
    await reset.click()

    const grid = page.getByRole('region', { name: 'CITIZEN' })
    await expect(grid).toBeVisible()
    await expect(grid).toContainText(/0\/3 districts/i)
    const advise = page.getByRole('button', { name: /approve civilian advisory/i })
    await expect(advise).toBeDisabled()

    const detect = page.getByRole('button', { name: /add district detection/i })
    await expect(detect).toBeEnabled({ timeout: 15000 })
    for (let index = 0; index < 7; index += 1) {
      await detect.click()
      await expect(detect).toBeEnabled({ timeout: 15000 })
    }
    await expect(grid).toContainText(/confirmed/i)

    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: /jam active channel/i }).click()
    await expect(grid).toContainText(/community fm relay/i)

    await expect(advise).toBeEnabled({ timeout: 15000 })
    page.once('dialog', (dialog) => dialog.accept())
    await advise.click()
    await expect(page.getByRole('button', { name: /advisory recorded/i })).toBeVisible({ timeout: 15000 })
  })

  test('viewer token cannot mutate the guided scenario', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /viewer token/i }).click()
    await expect(page.getByLabel(/operator session controls/i)).toContainText(/read-only viewer/i)
    await expect(page.getByRole('button', { name: /inject node loss/i })).toBeDisabled()
  })

  test('what is this reopens the operator guide without blocking controls after dismiss', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: /what is this/i }).click()
    await expect(page.getByRole('dialog', { name: /what ghost fabric actually does/i })).toBeVisible()
    await page.getByRole('button', { name: /enter simulation/i }).click()
    await expect(page.getByRole('dialog', { name: /what ghost fabric actually does/i })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /inject node loss/i })).toBeVisible()
  })
})

test.describe('first-run operator guide', () => {
  test('shows purpose, layers, and golden path then persists dismissal', async ({ page }) => {
    await page.goto('/')
    await page.evaluate((key) => localStorage.removeItem(key), ONBOARDING_KEY)
    await page.reload()

    const guide = page.getByRole('dialog', { name: /what ghost fabric actually does/i })
    await expect(guide).toBeVisible()
    await expect(guide).toContainText(/eastern europe civil continuity/i)
    await expect(guide).toContainText(/training only/i)
    await expect(guide).toContainText(/chameleon/i)
    await expect(guide).toContainText(/prophet/i)
    await expect(guide).toContainText(/mirror/i)
    await expect(guide).toContainText(/phoenix/i)
    await expect(guide).toContainText(/choose local optional or operator token/i)

    await page.getByRole('button', { name: /enter simulation/i }).click()
    await expect(guide).toHaveCount(0)
    await expect
      .poll(async () => page.evaluate((key) => localStorage.getItem(key), ONBOARDING_KEY))
      .toBe('seen')

    await page.reload()
    await expect(page.getByRole('dialog', { name: /what ghost fabric actually does/i })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /what is this/i })).toBeVisible()
  })

  test('dismisses with escape without authorizing action', async ({ page }) => {
    await page.goto('/')
    await page.evaluate((key) => localStorage.removeItem(key), ONBOARDING_KEY)
    await page.reload()

    await expect(page.getByRole('dialog', { name: /what ghost fabric actually does/i })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog', { name: /what ghost fabric actually does/i })).toHaveCount(0)
    await expect(page.getByText(/autonomous action disabled/i)).toBeVisible()
  })
})
