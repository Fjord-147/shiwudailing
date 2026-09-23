# -*- coding: utf-8 -*-
"""公众界面（无需登录）后端测试：首页、报失、隐私保护。"""
import json

from conftest import db_conn, seed_item


def test_public_index_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_public_index_shows_pending_item(client):
    seed_item(client, name="黑色真皮钱包", category="钱包")
    resp = client.get("/")
    assert resp.status_code == 200
    # 名称会脱敏（去颜色等特征词），但类别/图标仍在
    assert "钱包".encode() in resp.data


def test_public_index_hides_claimed_item(client):
    """已认领的物品不应出现在公众首页（无物品卡片，显示空态）。"""
    seed_item(client, name="雨伞", category="水杯/雨伞", status="已认领")
    resp = client.get("/")
    # 页面上有类别筛选栏（含"水杯/雨伞"字样是正常的），但不应有任何物品卡片链接
    assert "/public/item/".encode() not in resp.data
    assert "目前没有待认领的物品".encode() in resp.data


def test_public_index_category_filter(client):
    seed_item(client, name="公交卡", category="证件")
    seed_item(client, name="保温杯", category="水杯/雨伞")
    resp = client.get("/?category=证件")
    assert resp.status_code == 200


def test_public_report_page_renders(client):
    resp = client.get("/report")
    assert resp.status_code == 200


def test_public_report_requires_core_fields(client):
    resp = client.post(
        "/report",
        data={"owner_name": "", "owner_phone": "", "item_name": ""},
        follow_redirects=True,
    )
    assert "请填写姓名、电话、物品名称".encode() in resp.data


def test_public_report_creates_record(client):
    resp = client.post(
        "/report",
        data={
            "owner_name": "王先生",
            "owner_phone": "13800001111",
            "item_name": "身份证",
            "item_category": "证件",
            "description": "黑色卡套",
            "lost_location": "一楼大厅",
            "lost_time": "2099-01-01T09:00",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    conn = db_conn()
    row = conn.execute(
        "SELECT * FROM lost_reports WHERE owner_phone='13800001111'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["status"] == "待查找"


def test_public_report_other_location(client):
    resp = client.post(
        "/report",
        data={
            "owner_name": "李女士",
            "owner_phone": "13900002222",
            "item_name": "病历本",
            "lost_location": "__other__",
            "lost_location_other": "二楼楼梯口",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    conn = db_conn()
    row = conn.execute(
        "SELECT lost_location FROM lost_reports WHERE owner_phone='13900002222'"
    ).fetchone()
    conn.close()
    assert row["lost_location"] == "二楼楼梯口"


def test_public_cannot_see_owner_phone(client):
    """公众报失里的姓名电话绝不能出现在公众页面。"""
    client.post(
        "/report",
        data={
            "owner_name": "张三",
            "owner_phone": "13700003333",
            "item_name": "医保卡",
        },
    )
    for path in ["/", "/report"]:
        resp = client.get(path)
        assert "13700003333".encode() not in resp.data, path


def test_public_cannot_see_claimer_info(client):
    """已认领物品的认领人姓名/电话公众不可见。"""
    seed_item(
        client,
        name="手机",
        category="手机/电子产品",
        status="已认领",
        claimer_name="赵某某",
        claimer_phone="13600004444",
    )
    resp = client.get("/")
    assert "13600004444".encode() not in resp.data
    assert "赵某某".encode() not in resp.data


def test_pending_count_api_requires_login(client):
    resp = client.get("/api/reports/pending_count")
    assert resp.status_code == 302
