import { chromium } from 'playwright';
import fs from 'node:fs/promises';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
await page.addInitScript(() => localStorage.setItem('token', 'isolated-fixture'));
await page.route('**/api/v1/**', async route => {
  let data = {};
  if (route.request().url().endsWith('/messages')) data = {
    items: [
      { role: 'interviewer', content: '请介绍一次招聘实践。', question_index: 0 },
      { role: 'candidate', content: '我在课程中整理过岗位需求。', question_index: 0, score: 7, feedback: '请结合岗位需求提供具体行动、评价依据与改进结果。'.repeat(12) },
      { role: 'interviewer', content: '请说明如何评估筛选效果。', question_index: 1 }
    ], status: 'in_progress', total_questions: 5, current_question_index: 1, difficulty: 'easy'
  };
  await route.fulfill({ json: { code: 200, data } });
});
await page.goto('http://127.0.0.1:3019/interview/1');
await page.locator('.input-area textarea').waitFor();
const results = [];
for (const height of [844, 460]) {
  await page.setViewportSize({ width: 390, height });
  for (const expanded of [false, true]) {
    if (expanded) await page.getByRole('button', { name: '查看详情', exact: true }).click();
    const input = await page.locator('.input-area textarea').boundingBox();
    const send = await page.locator('.input-actions button').last().boundingBox();
    results.push({ height, expanded, input, send, pass: input.y >= 0 && send.y + send.height <= height + 1 });
    if (expanded) await page.getByRole('button', { name: '收起详情', exact: true }).click();
  }
}
await page.screenshot({ path: 'interview-keyboard-feedback.png' });
await browser.close();
await fs.writeFile('interview-keyboard-results.json', JSON.stringify(results, null, 2));
console.log(JSON.stringify(results));
if (results.some(r => !r.pass)) process.exitCode = 1;
