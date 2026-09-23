// 公众界面 E2E：无需登录即可浏览与报失。
import { test, expect } from '@playwright/test';

test.describe('公众界面', () => {
  test('首页展示医院品牌与导航', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/失物招领/);
    await expect(page.getByRole('link', { name: '我要报失' })).toBeVisible();
    await expect(page.getByRole('link', { name: /管理员入口/ })).toBeVisible();
  });

  test('筛选无结果时首页显示空态提示', async ({ page }) => {
    // 用无物品的类别筛选，确保与用例执行顺序无关（管理员用例会先登记物品）
    await page.goto('/?category=证件');
    await expect(page.locator('.public-empty')).toContainText('目前没有待认领的物品');
  });

  test('公众页不暴露任何电话等隐私信息', async ({ page }) => {
    await page.goto('/');
    const body = await page.textContent('body');
    expect(body).not.toMatch(/1[3-9]\d{9}/); // 手机号正则
  });

  test('我要报失：必填校验', async ({ page }) => {
    await page.goto('/report');
    await page.fill('input[name="owner_name"]', '');
    // 前端 HTML5 required 会拦截空提交；直接验证输入框存在且必填
    await expect(page.locator('input[name="owner_name"]')).toHaveAttribute('required', /.*/);
    await expect(page.locator('input[name="owner_phone"]')).toHaveAttribute('required', /.*/);
  });

  test('我要报失：提交成功并给出提示', async ({ page }) => {
    await page.goto('/report');
    await page.fill('input[name="owner_name"]', '测试失主');
    await page.fill('input[name="owner_phone"]', '13712345678');
    await page.fill('input[name="item_name"]', '黑色钱包');
    // 表单底部有「承诺信息真实」的必勾选框
    await page.check('.checkbox-row input[type="checkbox"]');
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/\/report/);
    await expect(page.locator('.flash, .alert, [class*="success"]').first()).toContainText('报失成功');
  });

  test('入口卡片面向失主，拾物提示引导去导医台', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.entry-card.entry-report')).toContainText('没找到？登记报失');
    await expect(page.locator('.finder-hint')).toContainText('导医台');
    // 不再出现让拾物者误解的文案
    await expect(page.locator('body')).not.toContainText('我捡到东西');
    // 快捷入口
    await expect(page.getByRole('link', { name: /查询我的报失/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /使用帮助/ })).toBeVisible();
  });

  test('查询我的报失：提交后可查进度', async ({ page }) => {
    // 1. 提交报失
    await page.goto('/report');
    await page.fill('input[name="owner_name"]', '进度查询测试');
    await page.fill('input[name="owner_phone"]', '13866668888');
    await page.fill('input[name="item_name"]', '老年卡');
    await page.check('.checkbox-row input[type="checkbox"]');
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.flash')).toContainText('报失成功');

    // 2. 查询进度
    await page.goto('/my_reports');
    await page.fill('input[name="phone"]', '13866668888');
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.report-card')).toContainText('老年卡');
    await expect(page.locator('.report-card')).toContainText('待查找');
  });

  test('帮助页：覆盖失主/导医/拾物者三种角色', async ({ page }) => {
    await page.goto('/help');
    await expect(page.locator('body')).toContainText('我是失主');
    await expect(page.locator('body')).toContainText('我是导医');
    await expect(page.locator('body')).toContainText('无需在网上登记');
    await expect(page.getByRole('link', { name: /失物招领首页/ })).toBeVisible();
  });

  test('移动端失物总表：表格可横向滚动而非挤压换行', async ({ page }) => {
    // 用窄视口模拟手机
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/login');
    await page.fill('input[name="username"]', 'liumin');
    await page.fill('input[name="password"]', 'liumin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/admin');
    await page.goto('/list');
    // 表格内容应比容器宽 → 出现横向滚动，而不是列被压成竖排
    const metrics = await page.evaluate(() => {
      const wrap = document.querySelector('.table-wrap');
      const table = wrap?.querySelector('table.data');
      return wrap && table
        ? { wrapW: wrap.clientWidth, tableW: table.scrollWidth }
        : null;
    });
    expect(metrics).not.toBeNull();
    expect(metrics!.tableW).toBeGreaterThan(metrics!.wrapW);
  });
});
