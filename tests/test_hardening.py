# -*- coding: utf-8 -*-
"""安全加固回归：认领并发竞态、base64 解码保护、限流 GC、登录失败限流。"""
import base64
import threading
import time
from collections import defaultdict, deque

import pytest

from conftest import db_conn, seed_item


@pytest.fixture(autouse=True)
def _fresh_rate_limiter(monkeypatch):
    """每个测试用独立的限流计数，避免全局配额串扰。"""
    import app
    monkeypatch.setattr(app, "_RATE_HITS", defaultdict(deque))


def _claim_once(item_id, name):
    import app
    client = app.app.test_client()
    client.post("/login", data={"username": "liumin", "password": "liumin123"})
    resp = client.post(
        "/claim",
        data={"item_id": item_id, "claimer_name": name, "feature_verified": "on"},
        headers={"X-Requested-With": "fetch"},
    )
    return resp.get_json()


def test_concurrent_claim_only_one_wins(admin_client):
    """并发认领同一件物品：只能成功一次（修复前多个并发都能"成功"，互相覆盖）。"""
    admin_client.post(
        "/register",
        data={"name": "竞态物品", "category": "其他", "storage_location": "抽屉"},
        headers={"X-Requested-With": "fetch"},
    )
    conn = db_conn()
    item_id = conn.execute("SELECT id FROM items LIMIT 1").fetchone()["id"]
    conn.close()

    results = []
    errors = []

    def worker(i):
        try:
            results.append(_claim_once(item_id, f"认领人{i}"))
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"有线程抛异常: {errors}"
    oks = [r for r in results if r["ok"]]
    assert len(oks) == 1, f"并发认领成功了 {len(oks)} 次: {results}"

    conn = db_conn()
    row = conn.execute(
        "SELECT status, claimer_name, claimed_at FROM items WHERE id=?", (item_id,)
    ).fetchone()
    conn.close()
    assert row["status"] == "已认领"
    assert row["claimer_name"].startswith("认领人")
    # 只能有一个认领人落库，不能被并发覆盖
    assert len({r.get("msg", "") for r in oks}) == 1


def test_register_with_invalid_base64_not_500(admin_client):
    """photo_data 不是合法 base64 / 缺少逗号分隔：不能 500，应忽略坏图正常登记。"""
    resp = admin_client.post(
        "/register",
        data={
            "name": "坏图物品",
            "category": "其他",
            "storage_location": "抽屉",
            "photo_data": "data:image/png",  # 没有逗号：旧代码 split 直接 ValueError
        },
        headers={"X-Requested-With": "fetch"},
    )
    assert resp.status_code == 200, resp.data[:200]
    assert resp.get_json()["ok"] is True
    conn = db_conn()
    row = conn.execute("SELECT photo FROM items WHERE name='坏图物品'").fetchone()
    conn.close()
    assert row["photo"] is None  # 坏图被丢弃，登记本身成功


def test_report_with_invalid_base64_not_500(client):
    resp = client.post(
        "/report",
        data={
            "owner_name": "张三",
            "owner_phone": "13755556666",
            "item_name": "公交卡",
            "photo_data": "data:image/png;base64,!!!not-base64!!!",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "报失成功" in resp.data.decode()


def test_rate_limiter_gc_really_shrinks(monkeypatch):
    """超过阈值时，长时间无活动的 key 必须被清掉（旧清理逻辑形同虚设）。"""
    import app
    store = defaultdict(deque)
    monkeypatch.setattr(app, "_RATE_HITS", store)
    old = time.time() - 7200  # 两小时前的记录
    for i in range(6000):
        store[f"old:{i}"].append(old)
    # 一个活跃 key
    store["live"].append(time.time())

    app._rate_limited("trigger", max_hits=100, window_seconds=600)

    assert len(store) < 100, f"GC 未生效，仍有 {len(store)} 个 key"
    assert "live" in store  # 活跃 key 不能被误清


def test_login_rate_limit_after_repeated_failures(client):
    """同一账号连续登录失败 5 次后进入限流，防暴力破解。"""
    payload = {"username": "liumin", "password": "wrong"}
    for i in range(5):
        resp = client.post("/login", data=payload, follow_redirects=True)
        assert "账号或密码错误" in resp.data.decode(), f"第 {i+1} 次提示不对"

    resp = client.post("/login", data=payload, follow_redirects=True)
    html = resp.data.decode()
    assert "尝试次数过多" in html
    # 即使这次密码是对的也被限流挡住
    resp = client.post(
        "/login",
        data={"username": "liumin", "password": "liumin123"},
        follow_redirects=True,
    )
    assert "尝试次数过多" in resp.data.decode()


def test_login_other_user_not_affected_by_others_failures(client):
    """限流按 IP+账号 计数：其他账号的失败不影响本账号。"""
    import app
    app._RATE_HITS.clear()
    for _ in range(6):
        client.post("/login", data={"username": "nobody", "password": "x"})
    resp = client.post(
        "/login",
        data={"username": "liumin", "password": "liumin123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302  # liumin 不受影响
