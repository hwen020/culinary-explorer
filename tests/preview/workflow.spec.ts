import {expect, test} from '@playwright/test'

test('public guest uses fictional search, map, CSV, and isolated history', async ({page, browser, baseURL}) => {
  const external: string[] = []
  page.on('request', request => {
    if (request.url().startsWith('http') && new URL(request.url()).origin !== new URL(baseURL!).origin) {
      external.push(request.url())
    }
  })
  await page.goto('/explore', {waitUntil: 'domcontentloaded', timeout: 100000})
  await expect(page.getByText(/Public preview. Use fictional information only/)).toBeVisible()
  const health = await page.request.get('/api/health')
  expect(await health.json()).toMatchObject({status:'ok', mode:'demo', preview:true, providers:['search'], maps_key:''})
  await page.getByRole('button', {name:'Try as guest'}).click()
  await expect(page.getByRole('heading', {name:'Explore restaurants'})).toBeVisible()
  await page.getByLabel('Cuisine or name').fill('Chinese')
  await page.getByLabel('Minimum rating').selectOption('4.5')
  await page.getByRole('button', {name:'Find restaurants'}).click()
  await expect(page.getByRole('heading', {name:'1 restaurants'})).toBeVisible()
  await page.getByRole('button', {name:'Save Sample Noodle House'}).click()
  await expect(page.getByRole('button', {name:'Unsave Sample Noodle House'})).toBeVisible()
  const csv = page.waitForEvent('download')
  await page.getByRole('button', {name:'Download CSV'}).click()
  expect((await csv).suggestedFilename()).toBe('restaurants.csv')
  await page.getByRole('button', {name:'Map', exact:true}).click()
  await page.getByLabel('Illustrative demo map').getByRole('button', {name:'Sample Noodle House'}).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('link', {name:'Directions to illustrative coordinates'})).toHaveCount(0)
  await page.getByRole('button', {name:'Close details'}).click()
  await page.getByRole('button', {name:'Chat', exact:true}).click()
  await page.getByLabel('Your question').fill('Chinese restaurants above 4.5?')
  await page.getByRole('button', {name:'Ask', exact:true}).click()
  await expect(page.getByText(/No AI model generated this answer/)).toBeVisible()
  const sessions = await (await page.request.get('/api/conversations')).json()
  expect(sessions).toHaveLength(1)
  await page.reload()
  await page.getByRole('button', {name:'Explore', exact:true}).click()
  await page.getByRole('button', {name:'Chinese restaurants above 4.5?'}).click()
  await expect(page.getByText(/Matching options: Sample Noodle House/)).toBeVisible()
  await page.getByRole('button', {name:'Saved', exact:true}).click()
  await expect(page.getByRole('heading', {name:'Sample Noodle House'})).toBeVisible()

  const second = await browser.newContext({baseURL})
  try {
    const headers = {Origin: new URL(baseURL!).origin}
    expect((await second.request.post('/api/preview/guest', {headers})).status()).toBe(201)
    expect(await (await second.request.get('/api/favorites')).json()).toEqual([])
    expect((await second.request.get('/api/conversations/' + sessions[0].id)).status()).toBe(404)
    for (const path of ['/api/admin/import', '/api/billing/checkout', '/api/auth/register', '/api/auth/password/request']) {
      expect((await second.request.post(path, {headers, data:{}})).status()).toBe(404)
    }
    expect((await second.request.post('/api/search', {headers:{Origin:'https://foreign.example.test'}, data:{}})).status()).toBe(403)
    expect((await second.request.post('/api/search', {headers, data:{location:'x'.repeat(5000)}})).status()).toBe(413)
    expect((await second.request.post('/api/preview/leave', {headers})).ok()).toBe(true)
  } finally {
    await second.close()
  }
  await page.getByRole('button', {name:'Guest session'}).click()
  await expect(page.getByRole('button', {name:'End guest session'})).toBeVisible()
  await page.getByRole('button', {name:'End guest session'}).click()
  await expect(page.getByRole('button', {name:'Try as guest'})).toBeVisible()
  expect(external).toEqual([])
})

test('public preview fits a mobile viewport', async ({page}) => {
  await page.setViewportSize({width:375,height:800})
  await page.goto('/', {waitUntil:'domcontentloaded',timeout:100000})
  await expect(page.getByRole('button',{name:'Try as guest'})).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(375)
})
