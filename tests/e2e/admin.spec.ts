// 管理员后台 E2E：登录 → 拾物登记 → 认领登记 全链路。
// 服务器由 playwright.config.ts 的 webServer 自动拉起（临时数据库）。
import { test, expect, Page } from '@playwright/test';
import { loginAsAdmin } from './helpers';

/** 1x1 红色 PNG，用于照片上传测试。 */
const TEST_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64'
);

/** 在登记页提交一件物品，返回页面提示里的失物编号。 */
async function registerItem(
  page: Page,
  name: string,
  opts: { category?: string; withPhoto?: boolean } = {}
): Promise<string> {
  const category = opts.category ?? '水杯/雨伞';
  await page.goto('/register');
  await page.fill('input[name="name"]', name);
  await page.selectOption('select[name="category"]', { label: category });
  await page.fill('input[name="storage_location"]', '导诊台1号抽屉');
  await page.fill('textarea[name="description"]', 'E2E 自动登记');
  if (opts.withPhoto) {
    // 切到「上传图片」页签再传文件
    await page.click('button[data-tab="upload"][data-tab-group="photo"]');
    await page.setInputFiles('input[name="photo_file"]', {
      name: 'e2e.png', mimeType: 'image/png', buffer: TEST_PNG,
    });
  }
  await page.click('button[type="submit"]');
  // 传统整页提交成功后重定向回 /register 并带 flash
  await expect(page).toHaveURL(/\/register/);
  const flash = page.locator('.flash, .alert, [class*="success"]').first();
  await expect(flash).toContainText('登记成功');
  const text = await flash.textContent() || '';
  const m = text.match(/\d{8}-\d{3}/);
  if (!m) throw new Error(`未从提示中提取到失物编号: ${text}`);
  return m[0];
}

test.describe('管理员后台', () => {
  test('错误密码登录被拒绝', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="username"]', 'liumin');
    await page.fill('input[name="password"]', 'wrong-pass');
    await page.click('button[type="submit"]');
    await expect(page.locator('body')).toContainText('账号或密码错误');
  });

  test('未登录访问后台被重定向到登录页', async ({ page }) => {
    await page.goto('/admin');
    await expect(page).toHaveURL(/\/login/);
  });

  test('登录后进入工作台', async ({ page }) => {
    await loginAsAdmin(page);
    await expect(page).toHaveURL(/\/admin/);
  });

  test('登记 → 总表可见 → 完成认领 全链路', async ({ page }) => {
    test.slow();
    await loginAsAdmin(page);

    // 1. 登记
    const code = await registerItem(page, 'E2E保温杯');

    // 2. 失物总表能搜到、状态待认领
    await page.goto('/list');
    await expect(page.locator('body')).toContainText(code);
    await expect(page.locator('body')).toContainText('待认领');

    // 3. 认领：先按编号定位，再核对特征、填认领人
    page.once('dialog', (d) => d.accept());
    await page.goto(`/claim?code=${code}`);
    await expect(page.locator('input[name="item_id"]')).toHaveCount(1);
    await page.fill('input[name="claimer_name"]', 'E2E认领人');
    await page.fill('input[name="claimer_phone"]', '13511112222');
    await page.check('input[name="feature_verified"]');
    await page.click('button[type="submit"]');

    // 4. 回到工作台/总表验证状态已变
    await page.goto('/list');
    await expect(page.locator('body')).toContainText('已认领');
  });

  test('认领必须勾选特征核对', async ({ page }) => {
    await loginAsAdmin(page);
    const code = await registerItem(page, 'E2E雨伞');

    page.once('dialog', (d) => d.accept());
    await page.goto(`/claim?code=${code}`);
    await page.fill('input[name="claimer_name"]', '测试人');
    await page.fill('input[name="claimer_phone"]', '13533334444');
    // 不勾选 feature_verified 直接提交（绕过 required 用 JS 点击亦可）
    await page.click('button[type="submit"]');
    // 后端应拒绝：页面回到认领页并提示需核对特征
    await expect(page.locator('body')).toContainText('核对');
  });

  test('P3：已登录访问 /login 直接跳回工作台', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto('/login');
    await expect(page).toHaveURL(/\/admin/);
  });

  test('P2：编辑弹窗可修改照片可见性，公众端即时生效', async ({ page }) => {
    test.slow();
    await loginAsAdmin(page);

    // 1. 登记一件带照片的物品（名称无脱敏词，公众页可直接按名称定位卡片）
    const code = await registerItem(page, 'E2E照片测试物', { category: '其他', withPhoto: true });

    // 2. 公众首页：该物品显示照片（📦 图标仅在无照片占位时出现，不能用来定位有照片的卡片）
    await page.goto('/');
    const cardWithPhoto = page.locator('.goods-card', { hasText: 'E2E照片测试物' });
    await expect(cardWithPhoto.locator('.goods-photo img')).toHaveCount(1);

    // 3. 总表打开编辑弹窗，勾选「对公众隐藏」
    await page.goto('/list');
    const row = page.locator('tr', { hasText: code });
    await row.getByTitle('编辑物品信息').click();
    const hideBox = page.locator('.ei_hidephoto').first();
    await expect(hideBox).toBeVisible();
    await hideBox.check();
    await page.locator('.modal-overlay button[type="submit"]').click();
    await expect(page.locator('body')).toContainText('物品信息已更新');

    // 4. 公众首页：照片消失，只剩占位图标（此时卡片里才有 📦）
    await page.goto('/');
    const cardHidden = page.locator('.goods-card', { hasText: 'E2E照片测试物' });
    await expect(cardHidden.locator('.goods-photo img')).toHaveCount(0);
    await expect(cardHidden.locator('.goods-photo-placeholder')).toHaveCount(1);
  });

  test('存储型 XSS：恶意报失字段在管理端所有渲染点都不执行', async ({ page }) => {
    test.slow();
    // 1. 攻击者提交带 XSS 载荷的报失（名称+描述都埋 onerror/onload）
    await page.goto('/report');
    await page.fill('input[name="owner_name"]', '攻击者');
    await page.fill('input[name="owner_phone"]', '13800007777');
    await page.fill('input[name="item_name"]', 'XSS<img src=x onerror="window.__xss=1">');
    await page.fill('textarea[name="description"]', '<svg onload="window.__xss=1">');
    await page.check('.checkbox-row input[type="checkbox"]');
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.flash')).toContainText('报失成功');

    // 2. 管理员登录并查看报失处理页（Jinja 自动转义渲染）
    await loginAsAdmin(page);
    await page.goto('/reports?status=待查找');
    await expect(page.locator('.report-card', { hasText: 'XSS' })).toBeVisible();
    expect(await page.evaluate(() => (window as any).__xss)).toBeUndefined();

    // 3. 一键转入总表（恶意内容原样入库）
    page.once('dialog', (d) => d.accept());
    await page.locator('.report-card', { hasText: 'XSS' })
      .getByRole('button', { name: /登记入总表/ }).click();
    await expect(page.locator('.flash')).toContainText('已登记入失物总表');

    // 4. 总表：打开认领抽屉（JS innerHTML 渲染，必须转义）
    await page.goto('/list');
    const row = page.locator('tr', { hasText: 'XSS' });
    await expect(row).toHaveCount(1);
    await row.getByRole('button', { name: '认领' }).click();
    await expect(page.locator('#listClaimDetail')).toContainText('window.__xss=1');
    expect(await page.evaluate(() => (window as any).__xss)).toBeUndefined();

    // 5. 工作台等其他管理页也不执行
    await page.goto('/admin');
    expect(await page.evaluate(() => (window as any).__xss)).toBeUndefined();
  });
});
