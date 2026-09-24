// Playwright E2E 配置：自动拉起一个用「临时数据库」的 Flask 测试服务器，
// 绝不触碰项目根目录的真实 lostfound.db / uploads/。
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  // 单个测试最长 30 秒；CI 上整体重试 1 次
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  outputDir: 'test-results',
  use: {
    baseURL: 'http://127.0.0.1:8765',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    locale: 'zh-CN',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    // 由测试专用脚本启动 Flask（临时库），就绪探测 /login
    command: './.venv/bin/python tests/e2e/run_test_server.py',
    url: 'http://127.0.0.1:8765/login',
    // 默认绝不复用已有进程：本地 8765 一旦有残留/旧代码/脏库的服务器，
    // 复用会让测试打偏（出现过成批假失败）。需要 --ui 连调时显式 REUSE_SERVER=1。
    reuseExistingServer: process.env.REUSE_SERVER === '1',
    timeout: 30_000,
  },
});
