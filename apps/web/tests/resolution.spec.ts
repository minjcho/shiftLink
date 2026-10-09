import { test, expect } from '@playwright/test';
import { existsSync, writeFileSync } from 'node:fs';
import { normalizeApiBasePath } from '../src/lib/api-base';
const base = normalizeApiBasePath(process.env.VITE_API_BASE_URL);
const targets = JSON.parse(process.env.SHIFTLINK_F4_TARGETS ?? '[]') as { incident_id: string; action_id: string; version: number }[];
const owner = process.env.SHIFTLINK_F4_OWNER ?? 'outgoing_supervisor';
test.skip(targets.length !== 2, 'Run scripts/f4_browser.py for isolated real prerequisites');

async function switchAccount(page: import('@playwright/test').Page, account: string) {
  await page.getByLabel('데모 계정 전환').selectOption(account);
  await page.getByRole('button', { name: '전환', exact: true }).click();
  await expect(page.getByRole('heading', { name: '최종 검증·해결 이력' })).toBeVisible();
}

test('F4 resolves with current owner, reads immutable case after API restart and reload', async ({ page }, testInfo) => {
  const target = targets[0];
  await page.goto(`/incidents/${target.incident_id}`);
  await switchAccount(page, 'maintainer');
  await expect(page.getByLabel('검토 사유 (필수)')).toHaveCount(0);
  if (owner === 'incoming_supervisor') {
    await switchAccount(page, 'outgoing_supervisor');
    await expect(page.getByLabel('검토 사유 (필수)')).toHaveCount(0);
  }
  await switchAccount(page, owner);
  await expect(page.getByRole('button', { name: '해결 확인', exact: true })).toBeDisabled();
  await page.getByLabel('검토 사유 (필수)').fill('승인된 범위, 결과 원문, 근거를 확인했습니다.');
  const saved = page.waitForResponse(r => r.url().endsWith('/verification') && r.request().method() === 'POST');
  await page.getByRole('button', { name: '해결 확인', exact: true }).click();
  const response = await saved; expect(response.status()).toBe(200);
  const result = (await response.json()).data;
  expect(result.incident_version).toBe(target.version + 1);
  await expect(page.getByRole('heading', { name: '해결 확인 기록', exact: true })).toBeVisible();
  if (owner === 'incoming_supervisor') {
    await expect(page.getByText('해결된 사건 · 과거 인계', { exact: true })).toBeVisible();
    await expect(page.getByText('이력은 조회할 수 있으며 새 인수는 할 수 없습니다.', { exact: false })).toBeVisible();
  }
  await page.getByText('해결 당시 기록 보기', { exact: true }).click();
  await expect(page.getByText(`Case ${result.case_id}`, { exact: false })).toBeVisible();
  const cases = await (await page.request.get(`${base}/cases?incident_id=${target.incident_id}`)).json();
  expect(cases.data.items).toHaveLength(1);
  await page.screenshot({ path: testInfo.outputPath('f4-resolved.png'), fullPage: true });
  const restart = process.env.SHIFTLINK_F4_RESTART!;
  writeFileSync(restart, 'restart');
  await expect.poll(() => existsSync(`${restart}.done`)).toBe(true);
  await page.reload();
  await expect(page.getByRole('heading', { name: '해결 확인 기록', exact: true })).toBeVisible();
  const after = await (await page.request.get(`${base}/cases?incident_id=${target.incident_id}`)).json();
  expect(after.data).toEqual(cases.data);
  const late = await page.request.post(`${base}/incidents/${target.incident_id}/messages`, {
    headers: { Origin: new URL(page.url()).origin, 'Idempotency-Key': crypto.randomUUID() },
    data: { text: '해결 후 늦은 원문', expected_version: target.version },
  });
  expect(late.status()).toBe(409);
  await testInfo.attach('resolution-evidence.json', { body: JSON.stringify({ target, result, case: after.data.items[0], model: 'fake deterministic decision', f3: owner === 'incoming_supervisor' }), contentType: 'application/json' });
});

test('F4 RETURN keeps completed result and records a review block', async ({ page }, testInfo) => {
  const target = targets[1];
  await page.goto(`/incidents/${target.incident_id}`);
  await switchAccount(page, owner);
  await page.getByLabel('검토 사유 (필수)').fill('결과에 대한 추가 검토가 필요합니다.');
  const saved = page.waitForResponse(r => r.url().endsWith('/verification') && r.request().method() === 'POST');
  await page.getByRole('button', { name: '검증 반려', exact: true }).click();
  expect((await saved).status()).toBe(200);
  await expect(page.getByRole('heading', { name: '검증 반려 기록', exact: true })).toBeVisible();
  await expect(page.getByLabel('검토 사유 (필수)')).toHaveCount(0);
  const detail = (await (await page.request.get(`${base}/incidents/${target.incident_id}`)).json()).data;
  expect(detail.status).toBe('INVESTIGATING'); expect(detail.review_required).toBe(true);
  expect(detail.actions[0].status).toBe('COMPLETED'); expect(detail.resolution.case).toBeNull();
  await page.reload();
  await expect(page.getByRole('heading', { name: '검증 반려 기록', exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('f4-return.png'), fullPage: true });
});
