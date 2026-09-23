# -*- coding: utf-8 -*-
"""并发回归：多个导医同时登记时，失物编号不能重复、不能 500。

generate_code 是「先查最大序号再插入」，无并发控制；
items.code 有 UNIQUE 约束，撞了必须重试而不是 500。
"""
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
