// E2E 公共辅助：登录后台。
// 测试账号统一用 config.py 里的 liumin / liumin123。
import { Page } from '@playwright/test';

export const ADMIN = { username: 'liumin', password: 'liumin123' };

export async function loginAsAdmin(page: Page) {
  await page.goto('/login');
  await page.fill('input[name="username"]', ADMIN.username);
  await page.fill('input[name="password"]', ADMIN.password);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/admin');
}
