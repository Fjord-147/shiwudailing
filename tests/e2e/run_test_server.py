# -*- coding: utf-8 -*-
"""E2E 测试专用 Flask 服务器。

用法（一般由 playwright.config.ts 的 webServer 自动调起）：
    ./.venv/bin/python tests/e2e/run_test_server.py

关键点：把 config.DB_PATH / config.UPLOAD_FOLDER 指到 tests/e2e/.e2e-tmp/ 下的
临时位置再 init_db()，确保 E2E 测试完全不碰真实的 lostfound.db 和 uploads/。
"""
import os
import shutil
import sys

# 让 import app / config 能找到项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

TMP_DIR = os.path.join(PROJECT_ROOT, "tests", "e2e", ".e2e-tmp")

import config  # noqa: E402

# 每次启动都从干净的临时库开始，保证用例间、多次运行间状态可复现
shutil.rmtree(TMP_DIR, ignore_errors=True)
config.DB_PATH = os.path.join(TMP_DIR, "e2e.db")
config.UPLOAD_FOLDER = os.path.join(TMP_DIR, "uploads")
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

import app  # noqa: E402  （config 已改好路径，再导入 app）

app.app.config.update(SECRET_KEY="e2e-secret-key")
app.init_db()

if __name__ == "__main__":
    try:
        app.app.run(host="127.0.0.1", port=8765, debug=False)
    finally:
        # 正常退出时清理临时库
        shutil.rmtree(TMP_DIR, ignore_errors=True)
