# -*- coding: utf-8 -*-
"""pytest 公共夹具。

关键设计：每个测试都用独立的临时 SQLite 库 + uploads 目录，
通过 monkeypatch 改 config.DB_PATH / config.UPLOAD_FOLDER 实现隔离，
绝不碰项目根目录里的真实 lostfound.db 和 uploads/。
"""
import os
import sqlite3
import sys

import pytest

# 保证能 import app / config（tests/ 在仓库根下）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402

_seed_counter = 0  # 让 seed_item 默认编号互不冲突


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Flask 测试客户端，挂临时数据库。"""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(config, "UPLOAD_FOLDER", str(tmp_path / "uploads"))
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

    import app
    app.app.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    app.init_db()

    with app.app.test_client() as c:
        yield c


@pytest.fixture()
def admin_client(client):
    """已登录管理员的测试客户端（用 config.USERS 里的第一个账号）。"""
    username, info = next(iter(config.USERS.items()))
    resp = client.post(
        "/login",
        data={"username": username, "password": info["password"]},
        follow_redirects=False,
    )
    assert resp.status_code == 302, "管理员登录失败，检查 config.USERS"
    return client


def db_conn():
    """直接开一条到当前测试库的 sqlite 连接（用于断言落库结果/造数据）。"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def seed_item(client, name="黑色钱包", category="钱包", status="待认领", **fields):
    """往 items 表直接插一条记录，返回 dict。字段缺省值与 init_db 对齐。"""
    global _seed_counter
    _seed_counter += 1
    defaults = {
        "code": fields.pop("code", f"20990101-{_seed_counter:03d}"),
        "name": name,
        "category": category,
        "description": "",
        "photo": None,
        "found_location": "一楼大厅",
        "found_time": "2099-01-01 10:00:00",
        "founder": "张护士",
        "status": status,
        "created_at": "2099-01-01 10:05:00",
        "claimer_name": None,
        "claimer_phone": None,
        "feature_verified": 0,
        "claimed_at": None,
        "operator": None,
        "hide_photo": 0,
        "claimer_photo": None,
        "claimer_group": None,
        "storage_location": "导诊台抽屉",
        "hidden_photos": None,
        "registered_by": "张护士",
    }
    defaults.update(fields)
    cols = ", ".join(defaults.keys())
    marks = ", ".join("?" for _ in defaults)
    conn = db_conn()
    cur = conn.execute(
        f"INSERT INTO items ({cols}) VALUES ({marks})", tuple(defaults.values())
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM items WHERE id=?", (cur.lastrowid,)
    ).fetchone()
    conn.close()
    return dict(row)
