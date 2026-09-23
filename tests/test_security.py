# -*- coding: utf-8 -*-
"""安全修复回归：已认领物品的照片/详情不得再从公众端点访问。

公众首页只展示「待认领」，但 /public/photo/<id> 与 /public/item/<id>
历史实现没校验 status，已认领物品的马赛克照片仍可被直接访问。
"""
import os
from collections import defaultdict, deque

import config

from conftest import db_conn, seed_item


def _make_photo(client, fname="sec_a.jpg"):
    from PIL import Image
    path = os.path.join(config.UPLOAD_FOLDER, fname)
    Image.new("RGB", (32, 32), (10, 200, 80)).save(path, "JPEG")
    return fname


def test_claimed_item_photo_not_public(admin_client, client):
    _make_photo(admin_client)
    item = seed_item(admin_client, photo="sec_a.jpg", status="已认领")
    resp = client.get(f"/public/photo/{item['id']}")
    # 已认领 → 占位 PNG，而不是马赛克 JPEG
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_pending_item_photo_still_public(admin_client, client):
    _make_photo(admin_client)
    item = seed_item(admin_client, photo="sec_a.jpg", status="待认领")
    resp = client.get(f"/public/photo/{item['id']}")
    assert resp.data[:2] == b"\xff\xd8"  # 马赛克 JPEG 正常


def test_claimed_item_detail_not_public(admin_client, client):
    item = seed_item(admin_client, status="已认领")
    resp = client.get(f"/public/item/{item['id']}")
    assert resp.status_code == 404


def test_pending_item_detail_public(admin_client, client):
    item = seed_item(admin_client, status="待认领")
    resp = client.get(f"/public/item/{item['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


# ========== ③ 报失限流 ==========

def test_report_rate_limit(client, monkeypatch):
    import app
    monkeypatch.setattr(app, "_RATE_HITS", defaultdict(deque))

    payload = {"owner_name": "张三", "owner_phone": "13700001111", "item_name": "医保卡"}
    # 前 5 次成功
    for i in range(5):
        resp = client.post("/report", data=payload, follow_redirects=True)
        assert "提交太频繁".encode() not in resp.data, f"第 {i+1} 次被误限流"

    # 第 6 次被限流（5 次/10 分钟）
    resp = client.post("/report", data=payload, follow_redirects=True)
    assert "提交太频繁".encode() in resp.data

    # 限流不区分内容，直接挡在写入之前：库里没有第 6 条
    conn = db_conn()
    count = conn.execute("SELECT COUNT(*) c FROM lost_reports").fetchone()["c"]
    conn.close()
    assert count == 5


# ========== ④ CSRF 同源校验 ==========

def test_csrf_rejects_cross_origin_post(client):
    resp = client.post(
        "/login",
        data={"username": "liumin", "password": "liumin123"},
        headers={"Origin": "http://evil.example.com"},
    )
    assert resp.status_code == 403


def test_csrf_rejects_cross_origin_referer(client):
    resp = client.post(
        "/report",
        data={"owner_name": "张三", "owner_phone": "13700000000", "item_name": "卡"},
        headers={"Referer": "http://evil.example.com/x"},
    )
    assert resp.status_code == 403


def test_csrf_allows_same_origin(client):
    resp = client.post(
        "/login",
        data={"username": "liumin", "password": "liumin123"},
        headers={"Origin": "http://localhost"},
        follow_redirects=False,
    )
    assert resp.status_code == 302  # 正常登录跳转


def test_csrf_allows_no_origin(client):
    """无 Origin/Referer 的请求（命令行、测试、旧设备）保持放行。"""
    resp = client.post(
        "/login",
        data={"username": "liumin", "password": "liumin123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_session_cookie_samesite_lax():
    import app
    assert app.app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
