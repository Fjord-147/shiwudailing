# -*- coding: utf-8 -*-
"""管理员业务流后端测试：登记 → 查询 → 认领 → 取消认领 / 删除。"""
import re

from conftest import db_conn, seed_item


def _register(admin_client, **overrides):
    data = {
        "name": "蓝色保温杯",
        "category": "水杯/雨伞",
        "description": "杯身有贴纸",
        "found_location": "一楼大厅",
        "found_time": "2099-01-01T10:00",
        "founder": "张护士",
        "storage_location": "导诊台1号抽屉",
    }
    data.update(overrides)
    return admin_client.post(
        "/register", data=data, headers={"X-Requested-With": "fetch"}
    )


def test_register_ajax_success(admin_client):
    resp = _register(admin_client)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    item = body["item"]
    # 失物编号格式：YYYYMMDD-NNN
    assert re.fullmatch(r"\d{8}-\d{3}", item["code"]), item["code"]
    assert item["status"] == "待认领"
    assert item["storage_location"] == "导诊台1号抽屉"


def test_register_requires_name(admin_client):
    resp = _register(admin_client, name="")
    assert resp.get_json()["ok"] is False


def test_register_requires_storage_location(admin_client):
    resp = _register(admin_client, storage_location="")
    assert resp.get_json()["ok"] is False


def test_register_generates_incrementing_codes(admin_client):
    _register(admin_client, name="物品A")
    _register(admin_client, name="物品B")
    conn = db_conn()
    codes = [r["code"] for r in conn.execute("SELECT code FROM items ORDER BY id").fetchall()]
    conn.close()
    nums = [int(c.split("-")[1]) for c in codes]
    assert nums[1] == nums[0] + 1


def test_claim_flow(admin_client):
    _register(admin_client)
    conn = db_conn()
    item_id = conn.execute("SELECT id FROM items LIMIT 1").fetchone()["id"]
    conn.close()

    resp = admin_client.post(
        "/claim",
        data={
            "item_id": item_id,
            "claimer_name": "王小明",
            "claimer_phone": "13500005555",
            "feature_verified": "on",
            "operator": "张护士",
        },
        headers={"X-Requested-With": "fetch"},
    )
    assert resp.get_json()["ok"] is True

    conn = db_conn()
    row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    assert row["status"] == "已认领"
    assert row["claimer_name"] == "王小明"
    assert row["feature_verified"] == 1


def test_claim_requires_feature_verified(admin_client):
    _register(admin_client)
    conn = db_conn()
    item_id = conn.execute("SELECT id FROM items LIMIT 1").fetchone()["id"]
    conn.close()
    resp = admin_client.post(
        "/claim",
        data={"item_id": item_id, "claimer_name": "某人"},
        headers={"X-Requested-With": "fetch"},
    )
    body = resp.get_json()
    assert body["ok"] is False
    assert "核对" in body["msg"]


def test_double_claim_rejected(admin_client):
    _register(admin_client)
    conn = db_conn()
    item_id = conn.execute("SELECT id FROM items LIMIT 1").fetchone()["id"]
    conn.close()
    payload = {
        "item_id": item_id,
        "claimer_name": "甲",
        "feature_verified": "on",
    }
    admin_client.post("/claim", data=payload, headers={"X-Requested-With": "fetch"})
    resp = admin_client.post(
        "/claim",
        data={"item_id": item_id, "claimer_name": "乙", "feature_verified": "on"},
        headers={"X-Requested-With": "fetch"},
    )
    assert resp.get_json()["ok"] is False
    conn = db_conn()
    name = conn.execute("SELECT claimer_name FROM items WHERE id=?", (item_id,)).fetchone()["claimer_name"]
    conn.close()
    assert name == "甲"  # 未被覆盖


def test_unclaim_and_delete_api(admin_client):
    _register(admin_client)
    conn = db_conn()
    item_id = conn.execute("SELECT id FROM items LIMIT 1").fetchone()["id"]
    conn.close()

    admin_client.post(
        "/claim",
        data={"item_id": item_id, "claimer_name": "甲", "feature_verified": "on"},
        headers={"X-Requested-With": "fetch"},
    )
    # 撤销认领需要输入「确认」二字
    resp = admin_client.post(f"/api/item/{item_id}/unclaim", data={"confirm": "确认"})
    assert resp.get_json()["ok"] is True
    conn = db_conn()
    row = conn.execute("SELECT status, claimer_name FROM items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    assert row["status"] == "待认领"
    assert row["claimer_name"] is None

    resp = admin_client.post(f"/api/item/{item_id}/delete", data={"confirm": "确认"})
    assert resp.get_json()["ok"] is True
    conn = db_conn()
    count = conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]
    conn.close()
    assert count == 0


def test_search_api(admin_client):
    seed_item(admin_client, name="AirPods耳机", category="手机/电子产品")
    seed_item(admin_client, name="棉外套", category="衣物", code="20990101-002")
    resp = admin_client.get("/api/search?q=AirPods")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert any("AirPods" in (i.get("name") or "") for i in body["items"])


def test_export_excel(admin_client):
    seed_item(admin_client)
    resp = admin_client.get("/export")
    assert resp.status_code == 200
    # xlsx 是 zip 容器，魔数 PK
    assert resp.data[:2] == b"PK"
    assert len(resp.data) > 1000


def test_stats_page_renders(admin_client):
    seed_item(admin_client)
    resp = admin_client.get("/stats")
    assert resp.status_code == 200
