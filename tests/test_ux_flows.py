# -*- coding: utf-8 -*-
"""UX 修复回归：公众入口文案、我的报失查询、帮助页、撤销登记闭环。"""
from collections import defaultdict, deque

import pytest

from conftest import db_conn, seed_item


@pytest.fixture(autouse=True)
def _fresh_rate_limiter(monkeypatch):
    """每个测试用独立的限流计数，避免全局配额串扰。"""
    import app
    monkeypatch.setattr(app, "_RATE_HITS", defaultdict(deque))


def _make_report(client, phone="13700009999", name="医保卡"):
    return client.post(
        "/report",
        data={"owner_name": "查询测试", "owner_phone": phone, "item_name": name},
    )


def test_public_entry_card_owner_oriented(client):
    """入口卡片面向失主，不再让拾物者误以为要网上登记。"""
    html = client.get("/").data.decode()
    assert "没找到？登记报失" in html
    assert "失主填写" in html
    assert "我捡到东西" not in html
    assert "捡到物品？请直接交到" in html
    # 新入口：查进度 / 帮助
    assert "/my_reports" in html
    assert "/help" in html


def test_my_reports_query_shows_own_progress(client):
    _make_report(client, phone="13700009999", name="医保卡")
    _make_report(client, phone="13700008888", name="钥匙")  # 别人的
    resp = client.post("/my_reports", data={"phone": "13700009999"})
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "医保卡" in html
    assert "待查找" in html
    assert "钥匙" not in html  # 不能看到别人的报失
    # 不泄露他人手机号
    assert "13700008888" not in html


def test_my_reports_no_result_friendly(client):
    resp = client.post("/my_reports", data={"phone": "19900000000"})
    assert "没有找到该手机号的报失记录" in resp.data.decode()


def test_help_page_renders(client):
    resp = client.get("/help")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "我是失主" in html
    assert "我是导医" in html
    assert "捡到物品" in html


def test_report_success_flash_mentions_progress_query(client):
    resp = client.post(
        "/report",
        data={"owner_name": "张三", "owner_phone": "13711110000", "item_name": "病历本"},
        follow_redirects=True,
    )
    assert "查询我的报失" in resp.data.decode()


def test_register_from_report_then_undo(admin_client):
    """登记入总表 → 撤销登记：物品删除、报失回到待查找（issue④闭环）。"""
    admin_client.post(
        "/report",
        data={"owner_name": "李四", "owner_phone": "13722220000", "item_name": "雨伞"},
    )
    conn = db_conn()
    rid = conn.execute("SELECT id FROM lost_reports LIMIT 1").fetchone()["id"]
    conn.close()

    # 登记入总表
    resp = admin_client.post(
        "/reports", data={"report_id": rid, "action": "register"}, follow_redirects=True
    )
    assert "已登记入失物总表" in resp.data.decode()
    conn = db_conn()
    item = conn.execute("SELECT * FROM items WHERE source='患者报失'").fetchone()
    rep = conn.execute("SELECT * FROM lost_reports WHERE id=?", (rid,)).fetchone()
    conn.close()
    assert item is not None
    assert rep["status"] == "已登记"
    assert rep["matched_item_id"] == item["id"]

    # 撤销登记
    resp = admin_client.post(
        "/reports", data={"report_id": rid, "action": "undo_register"},
        follow_redirects=True,
    )
    assert "已撤销登记" in resp.data.decode()
    conn = db_conn()
    item = conn.execute("SELECT * FROM items WHERE source='患者报失'").fetchone()
    rep = conn.execute("SELECT * FROM lost_reports WHERE id=?", (rid,)).fetchone()
    conn.close()
    assert item is None  # 总表里的重复记录已移除
    assert rep["status"] == "待查找"
    assert rep["matched_item_id"] is None


def test_undo_register_refused_when_item_claimed(admin_client):
    """已登记的物品被认领后，撤销登记必须被拒绝。"""
    admin_client.post(
        "/report",
        data={"owner_name": "王五", "owner_phone": "13733330000", "item_name": "耳机"},
    )
    conn = db_conn()
    rid = conn.execute("SELECT id FROM lost_reports LIMIT 1").fetchone()["id"]
    conn.close()
    admin_client.post("/reports", data={"report_id": rid, "action": "register"})
    conn = db_conn()
    item_id = conn.execute("SELECT id FROM items WHERE source='患者报失'").fetchone()["id"]
    conn.close()
    admin_client.post(
        "/claim",
        data={"item_id": item_id, "claimer_name": "王五", "feature_verified": "on"},
        headers={"X-Requested-With": "fetch"},
    )

    resp = admin_client.post(
        "/reports", data={"report_id": rid, "action": "undo_register"},
        follow_redirects=True,
    )
    assert "已被认领，不能撤销登记" in resp.data.decode()
    conn = db_conn()
    count = conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]
    conn.close()
    assert count == 1  # 物品仍在


def test_reports_page_registered_tag_not_mislabeled_as_ignored(admin_client):
    """已登记的报失不能显示成「已忽略」标签。"""
    admin_client.post(
        "/report",
        data={"owner_name": "赵六", "owner_phone": "13744440000", "item_name": "围巾"},
    )
    conn = db_conn()
    rid = conn.execute("SELECT id FROM lost_reports LIMIT 1").fetchone()["id"]
    conn.close()
    admin_client.post("/reports", data={"report_id": rid, "action": "register"})

    html = admin_client.get("/reports?status=已登记").data.decode()
    assert "已登记" in html
    # 抓卡片片段：已登记卡片内不应出现「已忽略」标签
    card = html.split("report-card")[1]
    assert "已忽略" not in card.split("report-actions")[0]


def test_claimed_item_hidden_from_public_index(client):
    """已认领物品不出现在公众首页（既有行为回归）。"""
    from conftest import seed_item as _seed
    _seed(client, name="围巾", status="已认领")
    html = client.get("/").data.decode()
    assert "/public/item/" not in html
