# -*- coding: utf-8 -*-
"""登录 / 权限相关后端测试。"""
import config

from conftest import seed_item


def test_login_page_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_login_with_wrong_password_fails(client):
    resp = client.post(
        "/login",
        data={"username": "liumin", "password": "wrong-password"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "账号或密码错误".encode() in resp.data


def test_login_success_redirects_to_admin(client):
    resp = client.post(
        "/login",
        data={"username": "liumin", "password": "liumin123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/admin")


def test_login_unknown_user_fails(client):
    resp = client.post(
        "/login", data={"username": "nobody", "password": "x"}, follow_redirects=True
    )
    assert "账号或密码错误".encode() in resp.data


def test_admin_pages_require_login(client):
    """未登录访问后台页面应被重定向到 /login。"""
    for path in ["/admin", "/register", "/claim", "/list", "/reports", "/stats", "/export"]:
        resp = client.get(path)
        assert resp.status_code == 302, path
        assert "/login" in resp.headers["Location"], path


def test_admin_pages_accessible_after_login(admin_client):
    for path in ["/admin", "/register", "/claim", "/list", "/reports", "/stats"]:
        resp = admin_client.get(path)
        assert resp.status_code == 200, path


def test_logout_clears_session(admin_client):
    resp = admin_client.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
    resp = admin_client.get("/admin")
    assert resp.status_code == 302  # 退出后不能再进后台


def test_config_users_not_empty():
    """保底：至少配置一个管理员账号，否则后台无法进入。"""
    assert config.USERS, "config.USERS 不能为空"


def test_unclaim_api_requires_login(client):
    seed_item(client)
    resp = client.post("/api/item/1/unclaim")
    assert resp.status_code == 302
