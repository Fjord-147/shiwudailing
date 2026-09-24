# -*- coding: utf-8 -*-
"""并发回归：多个导医同时登记时，失物编号不能重复、不能 500。

generate_code 是「先查最大序号再插入」，无并发控制；
items.code 有 UNIQUE 约束，撞了必须重试而不是 500。
"""
import re
import threading

import pytest


def _register_once():
    """单线程完整走一遍：登录 + AJAX 登记。返回 (status_code, body)。"""
    import app
    client = app.app.test_client()
    client.post("/login", data={"username": "liumin", "password": "liumin123"})
    resp = client.post(
        "/register",
        data={
            "name": "并发登记物品",
            "category": "其他",
            "storage_location": "导诊台",
        },
        headers={"X-Requested-With": "fetch"},
    )
    return resp.status_code, resp.get_json()


def test_concurrent_register_unique_codes(client, admin_client):
    """5 个线程同时登记：全部成功（200），编号互不重复。"""
    results = []
    errors = []

    def worker():
        try:
            results.append(_register_once())
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"有线程抛异常: {errors}"
    assert len(results) == 5, f"登记结果数不对: {len(results)}"

    codes = []
    for status, body in results:
        assert status == 200, f"登记返回 {status}: {body}"
        assert body["ok"] is True, f"登记失败: {body}"
        codes.append(body["item"]["code"])

    assert len(set(codes)) == 5, f"编号重复: {codes}"

    from conftest import db_conn
    conn = db_conn()
    count = conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"]
    conn.close()
    assert count == 5


def _found_claim_once(report_id):
    """单线程：登录 + 对一条报失执行 found_claim（登记+认领一步到位）。"""
    import app
    client = app.app.test_client()
    client.post("/login", data={"username": "liumin", "password": "liumin123"})
    resp = client.post(
        f"/api/report/{report_id}/found_claim",
        data={"claimer_name": "并发认领人", "feature_verified": "1"},
        headers={"X-Requested-With": "fetch"},
    )
    return resp.status_code, resp.get_json()


def test_concurrent_found_claim_unique_codes(client, admin_client):
    """found_claim 也往 items 表插记录，并发同样会撞编号：必须全部成功且不重复。"""
    # 造 5 条待查找报失
    for i in range(5):
        admin_client.post(
            "/report",
            data={
                "owner_name": f"失主{i}",
                "owner_phone": f"1390000000{i}",
                "item_name": f"物品{i}",
            },
        )
    from conftest import db_conn
    conn = db_conn()
    report_ids = [r["id"] for r in conn.execute("SELECT id FROM lost_reports ORDER BY id").fetchall()]
    conn.close()

    results = []
    errors = []

    def worker(rid):
        try:
            results.append(_found_claim_once(rid))
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    threads = [threading.Thread(target=worker, args=(rid,)) for rid in report_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"有线程抛异常: {errors}"
    assert len(results) == 5

    codes = []
    for status, body in results:
        assert status == 200, f"found_claim 返回 {status}: {body}"
        assert body["ok"] is True, f"found_claim 失败: {body}"
        m = re.search(r"编号 (\d{8}-\d{3})", body["msg"])
        assert m, f"消息里没有编号: {body}"
        codes.append(m.group(1))

    assert len(set(codes)) == 5, f"编号重复: {codes}"

    conn = db_conn()
    items = conn.execute("SELECT code, status FROM items WHERE source='患者报失'").fetchall()
    conn.close()
    assert len(items) == 5
    assert all(i["status"] == "已认领" for i in items)
