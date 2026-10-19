import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on('pageerror', e => errors.push(e.message));
await page.addInitScript(() => {
  localStorage.setItem('admin_token', 'isolated-admin-fixture');
  localStorage.setItem('admin_id', '3');
  localStorage.setItem('admin_can_manage_admins', 'true');
});
const item = { id: 1, user_id: 17, title: '手机输入反馈', content: '输入框体验建议', category: 'issue', status: 'pending', reply: null, created_at: '2026-10-19T09:00:00+08:00' };
let failNext = false;
await page.route('**/api/v1/backoffice/**', async route => {
  const url = new URL(route.request().url());
  let data = {};
  if (url.pathname.endsWith('/auth/me')) {
    data = { id: 3, email: 'admin@example.test', can_manage_admins: true };
  } else if (route.request().method() === 'PATCH') {
    if (failNext) {
      failNext = false;
      return route.fulfill({ status: 500, json: { message: '测试保存失败' } });
    }
    Object.assign(item, route.request().postDataJSON());
    data = item;
  } else if (url.pathname.endsWith('/feedback')) {
    data = { items: !url.searchParams.get('status') || url.searchParams.get('status') === item.status ? [item] : [], has_more: false };
  }
  await route.fulfill({ json: { code: 200, data } });
});
await page.goto('http://127.0.0.1:3020/feedback');
await page.getByLabel('回复内容').fill('已记录，将优化输入体验。');
failNext = true;
await page.getByRole('button', { name: '保存回复', exact: true }).click();
await page.getByRole('alert').filter({ hasText: '测试保存失败' }).waitFor();
assert.equal(await page.getByLabel('回复内容').inputValue(), '已记录，将优化输入体验。');
await page.getByRole('button', { name: '保存回复', exact: true }).click();
await page.getByRole('status').filter({ hasText: '处理结果已保存' }).waitFor();
assert.equal(item.status, 'replied');
await page.reload();
await page.getByLabel('回复内容').waitFor();
assert.equal(await page.getByLabel('回复内容').inputValue(), '已记录，将优化输入体验。');
await page.getByLabel('处理状态').selectOption('pending');
await page.getByText('当前没有符合条件的留言。').waitFor();
await page.getByLabel('处理状态').selectOption('replied');
await page.getByLabel('回复内容').waitFor();
await page.getByRole('button', { name: '关闭留言', exact: true }).click();
await page.getByText('当前没有符合条件的留言。').waitFor();
await page.getByLabel('处理状态').selectOption('closed');
await page.getByLabel('回复内容').waitFor();
assert.equal(item.status, 'closed');
await page.screenshot({ path: 'actual-admin-feedback.png', fullPage: true });
assert.deepEqual(errors, []);
await fs.writeFile('admin-feedback-results.json', JSON.stringify({ mode: 'isolated API fixtures', passed: ['failure preserves draft', 'reply saves', 'reload shows reply', 'pending filter', 'closed filter', 'filter refresh after update'], errors }, null, 2));
console.log('Admin feedback: 6 interaction checks passed.');
await browser.close();
