# -*- coding: utf-8 -*-
"""P2 修复回归：编辑接口支持修改照片可见性（hidden_photos）。
P3 修复回归：已登录访问 /login 直接跳工作台。
"""
import os

import config

from conftest import db_conn, seed_item


def _make_photo(client, fname="test_a.jpg"):
    """在临时 uploads 目录生成一张真实照片文件（PIL），返回文件名。"""
    from PIL import Image
    path = os.path.join(config.UPLOAD_FOLDER, fname)
    Image.new("RGB", (64, 64), (200, 100, 50)).save(path, "JPEG")
    return fname


def _edit(admin_client, item_id, **fields):
    data = {"name": "测试物品", "hidden_photos": fields.pop("hidden_photos", None)}
    data.update(fields)
    if data["hidden_photos"] is None:
        data.pop("hidden_photos")
    return admin_client.post(f"/api/item/{item_id}/edit", data=data)


def _get_item(item_id):
    conn = db_conn()
    row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return dict(row)


def test_edit_accepts_hidden_photos(admin_client):
    _make_photo(admin_client, "a.jpg")
    _make_photo(admin_client, "b.jpg")
    item = seed_item(admin_client, photo="a.jpg,b.jpg")
    resp = _edit(admin_client, item["id"], hidden_photos="b.jpg")
    assert resp.get_json()["ok"] is True
    assert _get_item(item["id"])["hidden_photos"] == "b.jpg"


def test_edit_unhide_restores_empty(admin_client):
    _make_photo(admin_client, "a.jpg")
    item = seed_item(admin_client, photo="a.jpg", hidden_photos="a.jpg")
    resp = _edit(admin_client, item["id"], hidden_photos="")
    assert resp.get_json()["ok"] is True
    assert _get_item(item["id"])["hidden_photos"] is None


def test_edit_rejects_foreign_photo(admin_client):
    """hidden_photos 里混入不属于该物品的照片必须被拒绝，且数据不变。"""
    _make_photo(admin_client, "a.jpg")
    item = seed_item(admin_client, photo="a.jpg")
    resp = _edit(admin_client, item["id"], hidden_photos="a.jpg,../../etc/passwd")
    body = resp.get_json()
    assert body["ok"] is False
    assert "不属于" in body["msg"]
    assert _get_item(item["id"])["hidden_photos"] is None


def test_edit_without_hidden_photos_keeps_value(admin_client):
    """不带 hidden_photos 字段的普通编辑，不应清掉已有的隐藏设置。"""
    _make_photo(admin_client, "a.jpg")
    item = seed_item(admin_client, photo="a.jpg", hidden_photos="a.jpg")
    resp = _edit(admin_client, item["id"], name="改后的名字")
    assert resp.get_json()["ok"] is True
    updated = _get_item(item["id"])
    assert updated["name"] == "改后的名字"
    assert updated["hidden_photos"] == "a.jpg"


def test_public_photo_hidden_then_restored(admin_client, client):
    """隐藏后公众照片接口给占位图；取消隐藏后恢复给马赛克图。"""
    _make_photo(admin_client, "a.jpg")
    item = seed_item(admin_client, photo="a.jpg")

    # 可见 → 马赛克图（JPEG 魔数 FFD8，非占位 PNG）
    resp = client.get(f"/public/photo/{item['id']}")
    assert resp.status_code == 200
    assert resp.data[:2] == b"\xff\xd8"

    # 隐藏 → 1x1 占位 PNG
    _edit(admin_client, item["id"], hidden_photos="a.jpg")
    resp = client.get(f"/public/photo/{item['id']}")
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"

    # 恢复可见 → 马赛克图回来了
    _edit(admin_client, item["id"], hidden_photos="")
    resp = client.get(f"/public/photo/{item['id']}")
    assert resp.data[:2] == b"\xff\xd8"


def test_public_index_card_hides_photo_indicator(admin_client, client):
    _make_photo(admin_client, "a.jpg")
    item = seed_item(admin_client, photo="a.jpg")
    html = client.get("/").data.decode()
    assert "public/photo" in html  # 有照片时卡片挂照片

    _edit(admin_client, item["id"], hidden_photos="a.jpg")
    html = client.get("/").data.decode()
    assert "public/photo" not in html  # 全部隐藏后只显示占位图标


def test_login_redirects_when_logged_in(client):
    """P3：已登录再访问 /login 应 302 到工作台。"""
    client.post("/login", data={"username": "liumin", "password": "liumin123"})
    resp = client.get("/login")
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/admin")


def test_login_page_ok_when_anonymous(client):
    resp = client.get("/login")
    assert resp.status_code == 200
