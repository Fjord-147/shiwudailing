# -*- coding: utf-8 -*-
"""部署回归：gunicorn 等 WSGI 服务器只 import app 模块、不执行 __main__，
因此建表（init_db）必须在 import 时就完成，不能只在 __main__ 里调用。

本测试用子进程模拟 gunicorn 的加载方式：只 import，不跑 __main__，
然后直接发起查库请求，必须正常而不是 500。
"""
import os
import subprocess
import sys
import textwrap

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_import_only_has_schema_like_gunicorn():
    code = textwrap.dedent(
        """
        import os, sys, tempfile
        sys.path.insert(0, {root!r})
        tmp = tempfile.mkdtemp()
        import config
        config.DB_PATH = os.path.join(tmp, "gunicorn_sim.db")
        config.UPLOAD_FOLDER = os.path.join(tmp, "up")
        os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

        import app  # 模拟 gunicorn：只 import，不执行 __main__

        # 不发请求先看表是否已建（gunicorn 启动后、首个请求前就必须有表）
        import sqlite3
        conn = sqlite3.connect(config.DB_PATH)
        tables = {{r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}}
        conn.close()
        assert {{"items", "lost_reports"}} <= tables, f"缺表: {{tables}}"

        # 首个查库请求必须正常（修复前这里 500：no such table: items）
        client = app.app.test_client()
        resp = client.get("/")
        assert resp.status_code == 200, resp.status_code
        print("IMPORT-ONLY-OK")
        """
    ).format(root=PROJECT_ROOT)

    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=60,
    )
    assert r.returncode == 0, f"子进程失败:\n{r.stdout}\n{r.stderr[-2000:]}"
    assert "IMPORT-ONLY-OK" in r.stdout
