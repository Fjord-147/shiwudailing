# -*- coding: utf-8 -*-
"""门诊失物招领系统 - 配置文件

这里集中放需要改动的配置：口令、端口、导医名单、地点选项。
不用动 app.py，改这里就行。
"""

import os

# ============ 基础路径（一般不用改）============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lostfound.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

# ============ 服务端口 ============
# 本机访问：http://127.0.0.1:PORT
# 其他电脑访问：http://本机IP:PORT  （需同一局域网）
PORT = int(os.environ.get("PORT", 8000))
HOST = "0.0.0.0"  # 0.0.0.0 表示允许其他电脑连进来，不要改成 127.0.0.1

# ============ 统一进入口令（已废弃，保留兼容）============
ACCESS_PASSWORD = os.environ.get("LF_PASSWORD", "8888")

# Flask session 加密用。优先读环境变量 LF_SECRET_KEY，务必改成你自己的随机串。
SECRET_KEY = os.environ.get("LF_SECRET_KEY", "clinic-lost-found-2026-change-me")

# ============ 管理员账号（账号密码登录）============
# 格式："账号名": {"password": "密码", "name": "显示真名"}
# 以后加护士：复制一行，改账号密码和真名即可
USERS = {
    "liumin": {"password": "liumin123", "name": "刘敏"},
}

# ============ 物品类别（下拉选项）============
CATEGORIES = [
    "证件",
    "钥匙",
    "手机/电子产品",
    "钱包",
    "衣物",
    "病历/检查单",
    "水杯/雨伞",
    "其他",
]

# ============ 捡到地点（下拉选项，可在页面手动补）============
LOCATIONS = [
    "一楼导诊台",
    "一楼大厅",
    "二楼检验科",
    "二楼候诊区",
    "三楼诊室",
    "挂号收费处",
    "药房",
    "卫生间",
    "停车场",
    "其他",
]

# ============ 导医名单（认领/登记时选经办人用，可在页面手动补）============
STAFF_NAMES = [
    "张护士",
    "李护士",
    "王护士",
    "赵护士",
]
