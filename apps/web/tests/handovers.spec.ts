import { test, expect, type Page, type Locator, type APIResponse } from '@playwright/test';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import type { Handover, HandoverItem } from '../src/features/handovers/types';

interface FixtureCase { incident: string; action: string | null; report: string; [key: string]: string | null }
interface Fixture { cases: Record<string, FixtureCase>; ids: Record<string, string> }
function fixture(): Fixture {
  if (!process.env.F3_BROWSER_FIXTURE) throw new Error('Real PostgreSQL F3 browser harness is required');
  return JSON.parse(readFileSync(process.env.F3_BROWSER_FIXTURE, 'utf8'));
}
async function control(operation: string) {
  if (!process.env.F3_BROWSER_CONTROLS) throw new Error('F3 harness controls are required');
  const path = join(process.env.F3_BROWSER_CONTROLS, operation);
  writeFileSync(path, operation);
  await expect.poll(() => existsSync(`${path}.done`), { timeout: 30000 }).toBe(true);
}
async function login(page: Page, account: string) {
  await page.getByLabel('데모 계정 전환').selectOption(account);
  await page.getByRole('button', { name: '전환', exact: true }).click();
  await expect.poll(async () => {
    const response = await page.request.get('/api/v1/me');
    return response.ok() ? (await response.json()).data.user_id : null;
  }).toBe(fixture().ids[account]);
  await expect(page.locator('.site-label')).toBeVisible();
}
async function readHandover(page: Page, id: string): Promise<Handover> {
  const response = await page.request.get(`/api/v1/handovers/${id}`);
  expect(response.status()).toBe(200);
  return (await response.json()).data;
}
function itemFor(data: Handover, incident: string) {
  const item = data.items.find(value => value.incident_id === incident);
  if (!item) throw new Error(`Missing handover item for ${incident}`);
  return item;
}
function card(page: Page, incident: string) { return page.locator(`article[data-incident-id="${incident}"]`); }
function ackButton(row: Locator) { return row.locator('.ack-controls button.primary'); }
async function createHandover(page: Page) {
  await page.goto('/incidents');
  await login(page, 'outgoing_supervisor');
  const ids = fixture().ids;
  await page.getByLabel('인계할 교대', { exact: true }).selectOption(`${ids.outgoing_shift}/${ids.incoming_shift}`);
  await page.getByRole('button', { name: '인계 생성 · 기존 인계 갱신', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/handovers\/[0-9a-f-]+$/);
  const id = page.url().split('/').at(-1)!;
  await expect(page.locator('.handover-overview')).toBeVisible();
  return { id, data: await readHandover(page, id) };
}
async function acknowledge(page: Page, id: string, incident: string) {
  const row = card(page, incident);
  await row.locator('.confirm-label input').check();
  await expect(ackButton(row)).toBeEnabled();
  await ackButton(row).focus();
  await expect(ackButton(row)).toBeFocused();
  await page.keyboard.press('Enter');
  await expect.poll(async () => itemFor(await readHandover(page, id), incident).ack_status).toBe('ACKNOWLEDGED');
  await expect(row.locator('.notice.success')).toContainText('인수를 저장했습니다');
  return itemFor(await readHandover(page, id), incident);
}
async function post(page: Page, path: string, body: unknown): Promise<APIResponse> {
  return page.request.post(`/api/v1${path}`, { data: body, headers: { Origin: new URL(page.url()).origin, 'Idempotency-Key': randomUUID() } });
}
async function note(page: Page, incident: string, expected_version: number, text: string) {
  const response = await post(page, `/incidents/${incident}/messages`, { text, expected_version, reply_to_request_id: null, observed_at: null, correction_of: null });
  expect(response.status(), await response.text()).toBe(202);
  return (await response.json()).data;
}
async function pausePolling(page: Page) {
  await page.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')); });
  await expect(page.getByRole('button', { name: '현재 상태 새로고침', exact: true })).toBeEnabled();
}
async function assertPreserved(page: Page, handover: string, incident: string, action: string | null, expected: HandoverItem) {
  const data = await readHandover(page, handover);
  const item = itemFor(data, incident);
  expect(item.id).toBe(expected.id);
  expect(item.snapshot_token).toBe(expected.snapshot_token);
  expect(item.snapshot).toEqual(expected.snapshot);
  expect(item.ack_status).toBe('ACKNOWLEDGED');
  expect(item.current_owner_id).toBe(fixture().ids.incoming_supervisor);
  expect(item.current_owner_shift_occurrence_id).toBe(fixture().ids.incoming_shift);
  expect(item.current_assignee_id).toBe(fixture().ids.maintainer);
  expect(item.current_incident_status).toBe('IN_PROGRESS');
  expect(item.snapshot.actions[0].id).toBe(action);
  expect(item.is_stale).toBe(false);
  return item;
}

test('AC-1 real F3 UI API PostgreSQL identity and restart persistence', async ({ page }, testInfo) => {
  const input = fixture();
  const { id, data } = await createHandover(page);
  expect(data.items).toHaveLength(6);
  const before = itemFor(data, input.cases.work.incident);
  await login(page, 'incoming_supervisor');
  const after = await acknowledge(page, id, input.cases.work.incident);
  expect(after.current_incident_version).toBe(before.snapshot_version + 1);
  expect(after.snapshot).toEqual(before.snapshot);
  expect(after.current_analysis_is_stale).toBe(true);
  await expect(card(page, input.cases.work.incident)).toContainText('인수 완료');
  await expect(card(page, input.cases.work.incident)).toContainText('AI 분석은 이전 업무 정보 기준입니다');
  await expect(card(page, input.cases.question.incident)).toContainText('인수 확인 대기');
  await card(page, input.cases.work.incident).getByRole('link', { name: '이 사건의 현재 상세와 업무 이력' }).click();
  await expect(page).toHaveURL(new RegExp(`/incidents/${input.cases.work.incident}$`));
  const summary = page.getByRole('region', { name: '교대 인수 요약', exact: true });
  await expect(summary).toContainText('인수 완료');
  await expect(summary).toContainText('수신 책임자');
  await expect(summary).toContainText('정비 담당자');
  await summary.getByRole('link', { name: '인계 내용과 변경 이력 확인' }).click();
  await expect(page).toHaveURL(new RegExp(`/handovers/${id}$`));
  await page.reload();
  await expect(card(page, input.cases.work.incident)).toContainText('인수 완료');
  await assertPreserved(page, id, input.cases.work.incident, input.cases.work.action, after);
  await control('restart');
  await page.reload();
  await expect(card(page, input.cases.work.incident)).toContainText('인수 완료');
  const persisted = await assertPreserved(page, id, input.cases.work.incident, input.cases.work.action, after);
  await page.setViewportSize({ width: 390, height: 844 });
  await card(page, input.cases.work.incident).scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('f3-mobile-persistent-handover.png') });
  await testInfo.attach('actual-f3-persistence.json', { body: JSON.stringify({ handover: id, incident: input.cases.work.incident, action: input.cases.work.action, before, persisted, apiRestarted: true }, null, 2), contentType: 'application/json' });
});

test('AC-16 revisions historical content pending additions and fixed cutoff in real UI', async ({ page }, testInfo) => {
  const input = fixture();
  const { id, data } = await createHandover(page);
  const cutoff = data.cutoff_at;
  await expect(card(page, input.cases.verification.incident)).toContainText('결과 제출 완료');
  await expect(card(page, input.cases.review.incident)).toContainText('승인 반려');
  await expect(card(page, input.cases.review.incident)).toContainText('후속 검토 필요');
  await login(page, 'incoming_supervisor');
  const first = await acknowledge(page, id, input.cases.work.incident);
  const text = `인수 뒤 새로 확인한 합성 원문 ${randomUUID()}`;
  await note(page, input.cases.work.incident, first.current_incident_version, text);
  const row = card(page, input.cases.work.incident);
  await expect(row.getByRole('button', { name: '최신 내용 확인 · revision 2', exact: true })).toBeVisible();
  await expect(row.locator('.handover-snapshot')).not.toContainText(text);
  await expect(row).toContainText('표시 중인 revision 1 / 최신 2');
  await expect(ackButton(row)).toBeDisabled();
  await row.getByRole('button', { name: '최신 내용 확인 · revision 2', exact: true }).click();
  await expect(row.locator('.handover-snapshot')).toContainText(text);
  await expect(row.locator('.confirm-label input')).not.toBeChecked();
  const second = await acknowledge(page, id, input.cases.work.incident);
  expect(second.revision).toBe(2);
  expect(second.current_assignee_id).toBe(first.current_assignee_id);
  await row.getByLabel('조회할 내용 revision').fill('1');
  await row.getByRole('button', { name: '선택한 revision 조회', exact: true }).click();
  await expect(row).toContainText('표시 중인 revision 1 / 최신 2');
  await expect(row.locator('.handover-snapshot')).not.toContainText(text);
  await expect(row.locator('.handover-snapshot')).toContainText('출발 책임자');
  await expect(ackButton(row)).toBeDisabled();
  const past = await page.request.get(`/api/v1/handovers/${id}?item_id=${first.id}&revision=1`);
  expect((await past.json()).data.items[0].snapshot).toEqual(first.snapshot);
  const additionText = `cutoff 이후 새 사건 ${randomUUID()}`;
  const created = await post(page, '/incidents', { equipment_id: input.ids.equipment, text: additionText, observed_at: null });
  expect(created.status(), await created.text()).toBe(202);
  const addedId = (await created.json()).data.incident_id as string;
  await expect(page.locator('.pending-additions')).toContainText('아직 snapshot에 포함되지 않은 사건');
  await expect.poll(async () => (await readHandover(page, id)).pending_additions.some(value => value.incident_id === addedId)).toBe(true);
  expect((await readHandover(page, id)).items.some(value => value.incident_id === addedId)).toBe(false);
  await expect(card(page, addedId)).toHaveCount(0);
  await login(page, 'outgoing_supervisor');
  await page.getByRole('button', { name: '추가 사건을 인계 snapshot에 포함', exact: true }).click();
  await expect(card(page, addedId)).toBeVisible();
  let updated = await readHandover(page, id);
  expect(updated.cutoff_at).toBe(cutoff);
  expect(itemFor(updated, addedId).added_since_cutoff).toBe(true);
  expect(itemFor(updated, addedId).ack_status).toBe('PENDING');
  await login(page, 'incoming_supervisor');
  await acknowledge(page, id, addedId);
  await expect(card(page, addedId)).toContainText('최초 인계 이후 추가됨');
  updated = await readHandover(page, id);
  expect(updated.cutoff_at).toBe(cutoff);
  expect(itemFor(updated, addedId).added_since_cutoff).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('f3-revision-and-added-incident.png') });
  await testInfo.attach('actual-f3-revisions.json', { body: JSON.stringify({ handover: id, cutoff, first, second, addedIncident: addedId, added: itemFor(updated, addedId) }, null, 2), contentType: 'application/json' });
});

test('AC-17 empty failed stale reads manual conflicts uncertain retries and session boundary', async ({ page }, testInfo) => {
  const { id, data } = await createHandover(page);
  expect(data.items).toHaveLength(0);
  await expect(page.getByRole('status').filter({ hasText: '이 교대 범위의 미해결 인계 항목이 없습니다' })).toBeVisible();
  await control('seed');
  const input = fixture();
  await page.getByRole('button', { name: '추가 사건을 인계 snapshot에 포함', exact: true }).click();
  await expect(card(page, input.cases.work.incident)).toBeVisible();
  await login(page, 'incoming_supervisor');
  const row = card(page, input.cases.work.incident);
  await row.locator('.confirm-label input').check();
  await control('db-fail');
  await expect(page.getByRole('alert').filter({ hasText: '최신 조회가 성공할 때까지 인수할 수 없습니다' })).toBeVisible();
  await expect(row).toContainText('작업자가 흔들림을 관찰했다고 보고함');
  await expect(ackButton(row)).toBeDisabled();
  await expect(row.locator('.confirm-label input')).toBeDisabled();
  await page.screenshot({ path: testInfo.outputPath('f3-actual-database-read-failure.png') });
  await control('db-restore');
  await page.getByRole('button', { name: '현재 상태 새로고침', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: '최신 조회가 성공할 때까지 인수할 수 없습니다' })).toHaveCount(0);
  await pausePolling(page);
  const before = itemFor(await readHandover(page, id), input.cases.work.incident);
  const newText = `오래된 확인 화면과 경합한 새 정보 ${randomUUID()}`;
  await note(page, input.cases.work.incident, before.current_incident_version, newText);
  const ackPath = `/api/v1/handovers/${id}/items/${before.id}/ack`;
  const writes: { body: string | null; key: string | undefined; status: number }[] = [];
  page.on('response', response => { if (new URL(response.url()).pathname === ackPath && response.request().method() === 'POST') writes.push({ body: response.request().postData(), key: response.request().headers()['idempotency-key'], status: response.status() }); });
  const conflict = page.waitForResponse(response => new URL(response.url()).pathname === ackPath);
  await ackButton(row).click();
  expect((await conflict).status()).toBe(409);
  await expect(row.getByRole('alert')).toContainText('HANDOVER_STALE');
  await expect(row.locator('.confirm-label input')).toBeChecked();
  await expect(row.locator('.handover-snapshot')).not.toContainText(newText);
  expect(writes).toHaveLength(1);
  await row.getByRole('button', { name: '최신 내용 조회 · 새 요청 준비', exact: true }).click();
  await expect(row.locator('.handover-snapshot')).toContainText(newText);
  await expect(row.locator('.confirm-label input')).not.toBeChecked();
  expect(writes).toHaveLength(1);
  await acknowledge(page, id, input.cases.work.incident);
  expect(writes).toHaveLength(2);
  expect(writes[1].key).not.toBe(writes[0].key);
  expect(JSON.parse(writes[1].body!).expected_version).toBe(before.current_incident_version + 1);
  const question = itemFor(await readHandover(page, id), input.cases.question.incident);
  const uncertainPath = `/api/v1/handovers/${id}/items/${question.id}/ack`;
  const uncertainRequests: { body: string | null; key: string | undefined }[] = [];
  let lost = false;
  await page.route(`**${uncertainPath}`, async route => {
    uncertainRequests.push({ body: route.request().postData(), key: route.request().headers()['idempotency-key'] });
    if (!lost) { lost = true; const response = await route.fetch(); expect(response.status()).toBe(200); await route.abort('failed'); }
    else await route.continue();
  });
  const uncertainRow = card(page, input.cases.question.incident);
  await uncertainRow.locator('.confirm-label input').check();
  await ackButton(uncertainRow).click();
  await expect(uncertainRow.getByRole('button', { name: '같은 인수 요청 결과 확인', exact: true })).toBeVisible();
  const committed = itemFor(await readHandover(page, id), input.cases.question.incident);
  expect(committed.ack_status).toBe('ACKNOWLEDGED');
  const replay = page.waitForResponse(response => new URL(response.url()).pathname === uncertainPath);
  await uncertainRow.getByRole('button', { name: '같은 인수 요청 결과 확인', exact: true }).click();
  const replayResponse = await replay;
  expect(replayResponse.status()).toBe(200);
  expect(replayResponse.headers()['idempotent-replayed']).toBe('true');
  await expect(uncertainRow.locator('.notice.success')).toBeVisible();
  expect(uncertainRequests).toHaveLength(2);
  expect(uncertainRequests[1]).toEqual(uncertainRequests[0]);
  expect(itemFor(await readHandover(page, id), input.cases.question.incident).current_incident_version).toBe(committed.current_incident_version);
  await page.unroute(`**${uncertainPath}`);
  const approval = itemFor(await readHandover(page, id), input.cases.approval.incident);
  const pendingPath = `/api/v1/handovers/${id}/items/${approval.id}/ack`;
  let pendingRequests = 0;
  await page.route(`**${pendingPath}`, async route => { pendingRequests += 1; await route.abort('failed'); });
  const pendingRow = card(page, input.cases.approval.incident);
  await pendingRow.locator('.confirm-label input').check();
  await ackButton(pendingRow).click();
  await expect(pendingRow.getByRole('button', { name: '같은 인수 요청 결과 확인', exact: true })).toBeVisible();
  await login(page, 'outgoing_supervisor');
  await expect(page.getByText('이전 계정의 재전송 대기를 정리했습니다', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: '같은 인수 요청 결과 확인', exact: true })).toHaveCount(0);
  await login(page, 'incoming_supervisor');
  await expect(pendingRow.locator('.confirm-label input')).not.toBeChecked();
  expect(pendingRequests).toBe(1);
  expect(itemFor(await readHandover(page, id), input.cases.approval.incident).ack_status).toBe('PENDING');
  await page.unroute(`**${pendingPath}`);
  await testInfo.attach('actual-f3-errors-and-retries.json', { body: JSON.stringify({ handover: id, databaseReadFailed: true, emptyObserved: true, staleWrites: writes, uncertainRequests, committed, pendingRequestsAfterSessionSwitch: pendingRequests }, null, 2), contentType: 'application/json' });
});
