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
});
