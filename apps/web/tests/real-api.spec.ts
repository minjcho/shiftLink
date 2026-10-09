import { test, expect } from '@playwright/test';
import { existsSync, writeFileSync } from 'node:fs';
import { normalizeApiBasePath } from '../src/lib/api-base';

const apiBase = normalizeApiBasePath(process.env.VITE_API_BASE_URL);

test('AC33 real UI -> HTTP -> PostgreSQL survives API/worker restart and designated reply', async ({ page }, testInfo) => {
  const raw = `CV-03에서 평소와 다른 소리와 진동을 느꼈어요. 정비팀이 초기 점검을 완료했다고 들었어요. ${Date.now()}`;
  const reply = '외관만 확인했습니다. 추가 점검 결과는 없습니다.';
  const writes: { path: string; status: number; body: unknown }[] = [];
  page.on('response', async r => { if (r.request().method() === 'POST' && !r.url().includes('/demo/session')) { try { writes.push({ path: new URL(r.url()).pathname, status: r.status(), body: await r.json() }); } catch { /* Transport failure is asserted through UI. */ } } });
  await page.goto('/incidents');
  await page.getByLabel('데모 계정 전환').selectOption('reporter'); await page.getByRole('button', { name: '전환', exact: true }).click();
  await page.getByLabel('설비', { exact: true }).selectOption('00000000-0000-4000-8000-000000000103');
  await page.getByLabel('제보 원문', { exact: true }).fill(raw);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: '제보 저장', exact: true }).focus(); await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/incidents\/[0-9a-f-]+$/);
  const incidentUrl = page.url(); const incidentId = incidentUrl.split('/').at(-1)!;
  await expect(page.locator('.timeline')).toContainText(raw);
  await expect(page.locator('.question-card').first()).toBeVisible({ timeout: 30000 });
  let before = (await (await page.request.get(`${apiBase}/incidents/${incidentId}`)).json()).data;
  const request = before.requests.find((r: { status: string }) => r.status === 'OPEN');
  expect(request.is_required).toBe(true); expect(request.target_user_id).toBe('00000000-0000-4000-8000-000000000202');
  expect(await page.getByLabel('이 질문에 대한 답변').count()).toBe(0);
  const firstJobId = before.latest_job.id;
  const firstRunId = (await (await page.request.get(`${apiBase}/jobs/${firstJobId}`)).json()).data.latest_run_id;
  const sentinel = process.env.SHIFTLINK_RESTART_REQUEST;
  if (!sentinel) throw new Error('AC33 requires the PostgreSQL API/worker restart harness sentinel');
  if (sentinel) { writeFileSync(sentinel, 'restart'); await expect.poll(() => existsSync(`${sentinel}.done`), { timeout: 30000 }).toBe(true); }
  await page.reload(); await expect(page.locator('.timeline')).toContainText(raw); await expect(page.locator('.question-card').filter({ hasText: request.id })).toBeVisible();
  await page.getByLabel('데모 계정 전환').selectOption('maintainer'); await page.getByRole('button', { name: '전환', exact: true }).click();
  const card = page.locator('.question-card').filter({ hasText: request.id }); await card.getByLabel('이 질문에 대한 답변').fill(reply); await card.getByRole('button', { name: '답변 저장', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: '답변 저장됨' })).toBeVisible();
  await page.reload(); await expect(page.locator('.timeline')).toContainText(raw); await expect(page.locator('.timeline')).toContainText(reply); await expect(card).toContainText('답변 완료');
  const after = (await (await page.request.get(`${apiBase}/incidents/${incidentId}`)).json()).data;
  const sameRequest = after.requests.find((r: { id: string }) => r.id === request.id);
  expect(sameRequest.status).toBe('ANSWERED'); expect(after.latest_job.id).not.toBe(firstJobId);
  await expect.poll(async () => (await (await page.request.get(`${apiBase}/jobs/${after.latest_job.id}`)).json()).data.latest_run_id, { timeout: 30000 }).not.toBeNull();
  const newJob = (await (await page.request.get(`${apiBase}/jobs/${after.latest_job.id}`)).json()).data;
  expect(newJob.latest_run_id).not.toBe(firstRunId); expect(newJob.mode).toBe('fake');
  await testInfo.attach('actual-f1-boundary-ids.json', { body: JSON.stringify({ incidentId, requestId: request.id, firstJobId, firstRunId, nextJobId: newJob.id, nextRunId: newJob.latest_run_id, mode: newJob.mode, restarted: !!sentinel, writes }, null, 2), contentType: 'application/json' });
  await page.screenshot({ path: testInfo.outputPath('f1-mobile-persistent-reply.png'), fullPage: true });
});

test('review fix: committed intake with a lost response survives failed/successful reads and replays one receipt', async ({ page }, testInfo) => {
  await page.goto('/incidents');
  await page.getByLabel('데모 계정 전환').selectOption('reporter');
  await page.getByRole('button', { name: '전환', exact: true }).click();
  await expect(page.getByLabel('제보 원문', { exact: true })).toBeEnabled();
  const before = (await (await page.request.get(`${apiBase}/incidents?scope=all`)).json()).data.items;
  const original = `응답 유실 후 같은 접수 확인 ${Date.now()}`;
  const posts: { key: string | undefined; body: string | null; result: Record<string, string>; replayed: string | undefined }[] = [];
  let failReads = false;
  await page.route(`**${apiBase}/incidents*`, async route => {
    const request = route.request();
    if (new URL(request.url()).pathname !== `${apiBase}/incidents`) return route.continue();
    if (request.method() === 'GET') return failReads ? route.abort('failed') : route.continue();
    if (request.method() !== 'POST') return route.continue();
    // Let the real API commit first; only the first browser response is lost.
    const response = await route.fetch();
    expect(response.status()).toBe(202);
    posts.push({ key: request.headers()['idempotency-key'], body: request.postData(),
      result: (await response.json()).data, replayed: response.headers()['idempotent-replayed'] });
    if (posts.length === 1) await route.abort('failed');
    else await route.fulfill({ response });
  });
  await page.getByLabel('제보 원문', { exact: true }).fill(original);
  await page.getByRole('button', { name: '제보 저장', exact: true }).click();
  const retry = page.getByRole('button', { name: '같은 요청 결과 확인', exact: true });
  await expect(retry).toBeVisible();
  expect(posts).toHaveLength(1);
  await expect(page.getByRole('button', { name: '최신 내용 조회 · 새 요청 준비', exact: true })).toHaveCount(0);
  failReads = true;
  await page.getByRole('button', { name: '새로고침', exact: true }).click();
  await expect(page.locator('.incidents-section [role="alert"]')).toBeVisible();
  await expect(page.getByLabel('제보 원문', { exact: true })).toHaveValue(original);
  await expect(page.getByRole('button', { name: '제보 저장', exact: true })).toBeDisabled();
  failReads = false;
  await page.getByRole('button', { name: '새로고침', exact: true }).click();
  await expect(page.locator('.incidents-section [role="alert"]')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '제보 저장', exact: true })).toBeDisabled();
  await expect(retry).toBeVisible();
  expect(posts).toHaveLength(1);
  await retry.click();
  await expect(page).toHaveURL(new RegExp(`/incidents/${posts[0].result.incident_id}$`));
  await expect(page.locator('.timeline')).toContainText(original);
  expect(posts).toHaveLength(2);
  expect(posts[0].key).toBeTruthy();
  expect(posts[1].key).toBe(posts[0].key);
  expect(posts[1].body).toBe(posts[0].body);
  expect(posts[1].result).toEqual(posts[0].result);
  expect(posts[1].replayed).toBe('true');
  const after = (await (await page.request.get(`${apiBase}/incidents?scope=all`)).json()).data.items;
  expect(after).toHaveLength(before.length + 1);
  const incident = (await (await page.request.get(`${apiBase}/incidents/${posts[0].result.incident_id}`)).json()).data;
  expect(incident.messages.filter((m: { text: string }) => m.text === original)).toHaveLength(1);
  expect(incident.latest_job.id).toBe(posts[0].result.job_id);
  await testInfo.attach('review-receipt-recovery.json', { body: JSON.stringify({ apiBase, posts, before: before.length, after: after.length }, null, 2), contentType: 'application/json' });
});

test('review fix: real cursor pages remain visible after list polling', async ({ page }) => {
  await page.goto('/incidents');
  await page.getByLabel('데모 계정 전환').selectOption('reporter');
  await page.getByRole('button', { name: '전환', exact: true }).click();
  await expect(page.getByLabel('제보 원문', { exact: true })).toBeEnabled();
  const jobs: string[] = [];
  for (let index = 0; index < 22; index += 1) {
    const response = await page.request.post(`${apiBase}/incidents`, {
      headers: { Origin: new URL(page.url()).origin, 'Idempotency-Key': crypto.randomUUID() },
      data: { equipment_id: '00000000-0000-4000-8000-000000000103', text: `페이지 유지 확인 ${index}`, observed_at: null },
    });
    expect(response.status()).toBe(202);
    jobs.push((await response.json()).data.job_id);
  }
  // Let the real worker finish so changes in updated_at do not move the cursor window.
  await expect.poll(async () => {
    const states = await Promise.all(jobs.map(async id => (await (await page.request.get(`${apiBase}/jobs/${id}`)).json()).data.status));
    return states.every(state => state === 'SUCCEEDED');
  }, { timeout: 30000 }).toBe(true);
  const expected = (await (await page.request.get(`${apiBase}/incidents?scope=all&limit=100`)).json()).data.items;
  expect(expected.length).toBeGreaterThan(20);
  expect(expected.length).toBeLessThanOrEqual(40);
  await page.reload();
  await expect(page.locator('.incident-list > li')).toHaveCount(20);
  await page.getByRole('button', { name: '다음 사건 보기', exact: true }).click();
  await expect(page.locator('.incident-list > li')).toHaveCount(expected.length);
  const freshness = page.locator('.incidents-section .freshness');
  const previousSuccess = await freshness.textContent();
  const refreshedPage = await page.waitForResponse(response => {
    const url = new URL(response.url());
    return response.request().method() === 'GET' && url.pathname === `${apiBase}/incidents` && url.searchParams.has('cursor');
  });
  expect(refreshedPage.status()).toBe(200);
  await refreshedPage.finished();
  await expect(freshness).not.toHaveText(previousSuccess!);
  await expect(page.locator('.incident-list > li')).toHaveCount(expected.length);
  await expect(page.locator('.incident-list .identifier')).toHaveText(expected.map((item: { display_id: string }) => item.display_id));
});
