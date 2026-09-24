// UI 巡检截图：桌面 + 手机视口，覆盖公众页与管理员主要页面。
// 用法：先启动测试服务器（./.venv/bin/python tests/e2e/run_test_server.py &），再 node shots.mjs
// 输出到 shots/ 目录。可用环境变量 SKIP_SEED=1 跳过造数据。
import { chromium } from '@playwright/test';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8765';
const browser = await chromium.launch();

async function adminLogin(page) {
  await page.goto(BASE + '/login');
  await page.fill('input[name="username"]', 'liumin');
  await page.fill('input[name="password"]', 'liumin123');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/admin');
}

// ---- 造数据（2 条报失 + 2 件物品，其中一件随后被认领）----
if (!process.env.SKIP_SEED) {
  const seed = await browser.newContext();
  const p = await seed.newPage();
  await p.goto(BASE + '/login');
  await p.fill('input[name="username"]', 'liumin');
  await p.fill('input[name="password"]', 'liumin123');
  await p.click('button[type="submit"]');
  await p.waitForURL('**/admin');
  for (let i = 1; i <= 2; i++) {
    await p.goto(BASE + '/report');
    await p.fill('input[name="owner_name"]', `测试失主${i}`);
    await p.fill('input[name="owner_phone"]', `1370000000${i}`);
    await p.fill('input[name="item_name"]', `黑色钱包${i}`);
    await p.selectOption('select[name="item_category"]', '钱包');
    await p.check('.checkbox-row input[type="checkbox"]');
    await p.locator('button[type="submit"]').click();
  }
  for (const [name, cat] of [['黑色保温杯', '水杯/雨伞'], ['身份证', '证件']]) {
    await p.goto(BASE + '/register');
    await p.fill('input[name="name"]', name);
    await p.selectOption('select[name="category"]', { label: cat });
    await p.fill('input[name="storage_location"]', '导诊台1号抽屉');
    await p.locator('button[type="submit"]').click();
  }
  // 认领其中一件 → 已认领状态也能入镜
  await p.goto(BASE + '/claim?code=');
  await p.goto(BASE + '/claim');
  await p.fill('input[name="q"]', '保温杯');
  await p.locator('button:has-text("搜索")').click();
  await p.waitForTimeout(500);
  await seed.close();
}

// ---- 桌面视口 ----
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'zh-CN' });
const page = await ctx.newPage();
for (const [r, name] of [
  ['/', 'd_index'], ['/report', 'd_report'], ['/my_reports', 'd_my_reports'],
  ['/help', 'd_help'], ['/login', 'd_login'],
]) {
  await page.goto(BASE + r);
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `shots/${name}.png` });
}
await adminLogin(page);
for (const [r, name] of [
  ['/admin', 'd_admin'], ['/register', 'd_register'], ['/list', 'd_list'],
  ['/claim', 'd_claim'], ['/reports', 'd_reports'], ['/stats', 'd_stats'],
]) {
  await page.goto(BASE + r);
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: `shots/${name}.png`, fullPage: true });
}

// ---- 手机视口 ----
const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'zh-CN', isMobile: true });
const mp = await mctx.newPage();
for (const [r, name] of [['/', 'm_index'], ['/report', 'm_report'], ['/my_reports', 'm_my_reports'], ['/help', 'm_help']]) {
  await mp.goto(BASE + r);
  await mp.waitForLoadState('networkidle');
  await mp.screenshot({ path: `shots/${name}.png` });
}
await adminLogin(mp);
for (const [r, name] of [['/admin', 'm_admin'], ['/list', 'm_list'], ['/reports', 'm_reports'], ['/stats', 'm_stats']]) {
  await mp.goto(BASE + r);
  await mp.waitForLoadState('networkidle');
  await mp.screenshot({ path: `shots/${name}.png`, fullPage: true });
}

await browser.close();
console.log('截图完成 → shots/');
