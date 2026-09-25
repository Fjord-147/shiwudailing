# -*- coding: utf-8 -*-
"""显示回归：datetime-local 入库的时间（2026-09-25T17:33）在管理端各页面
显示时必须把 T 换成空格。涉及工作台 / 总表 / 认领页 / 报失处理。"""
from conftest import seed_item

DT_RAW = "2026-09-25T17:33"


def test_list_time_without_t(admin_client):
    seed_item(admin_client, found_time=DT_RAW)
    html = admin_client.get("/list").data.decode()
    # 表格视图单元格：T 已换成空格（页面内嵌的 items JSON 供卡片视图用，属数据非显示）
    assert "<td>2026-09-25 17:33</td>" in html


def test_claim_page_time_without_t(admin_client):
    seed_item(admin_client, found_time=DT_RAW)
    html = admin_client.get("/claim").data.decode()
    assert "2026-09-25 17:33" in html
    assert DT_RAW not in html


def test_workbench_time_without_t(admin_client):
    seed_item(admin_client, found_time=DT_RAW)
    html = admin_client.get("/admin").data.decode()
    assert "2026-09-25 17:33" in html
    assert DT_RAW not in html


def test_reports_lost_time_without_t(admin_client):
    admin_client.post(
        "/report",
        data={
            "owner_name": "时间格式",
            "owner_phone": "13766668888",
            "item_name": "检查单",
            "lost_time": DT_RAW,
        },
    )
    html = admin_client.get("/reports").data.decode()
    assert "2026-09-25 17:33" in html
    assert DT_RAW not in html


def test_dt_filter_empty_value(admin_client):
    """空值经 dt 过滤器不能报错，正常显示占位符。"""
    seed_item(admin_client, found_time=None)
    html = admin_client.get("/list").data.decode()
    assert "—" in html
