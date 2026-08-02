# -*- coding: utf-8 -*-
"""门诊失物招领登记系统 - Flask 主程序

启动方式：
    python3 app.py
然后浏览器打开 http://127.0.0.1:8000

功能：
    1. 工作台首页（统计 + 待认领列表）
    2. 拾物登记（含拍照/上传照片）
    3. 认领登记（核对特征 + 录入失主信息）
    4. 失物总表（筛选 + 搜索）
    5. 统计导出（Excel）
登录：统一口令 + 选/填本人姓名留痕
"""

import os
import sqlite3
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, send_from_directory, flash, g,
)

import config
from openpyxl_export import export_items_to_excel

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 单文件最大 16MB

# 确保上传目录存在
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# 数据库
# ============================================================
def get_db():
    """每次请求获取一个连接，放到 g 上，请求结束关闭。"""
    if "db" not in g:
        g.db = sqlite3.connect(config.DB_PATH)
        g.db.row_factory = sqlite3.Row  # 查询结果像字典一样取值
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """启动时建表（已存在则跳过），并兼容旧库自动补字段。"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code           TEXT NOT NULL UNIQUE,   -- 失物编号 20260729-001
            name           TEXT NOT NULL,          -- 物品名称
            category       TEXT,                   -- 类别
            description    TEXT,                   -- 特征描述
            photo          TEXT,                   -- 照片相对路径
            found_location TEXT,                   -- 捡到地点
            found_time     TEXT,                   -- 捡到时间
            founder        TEXT,                   -- 捡到人
            status         TEXT NOT NULL DEFAULT '待认领',  -- 待认领/已认领
            created_at     TEXT NOT NULL,          -- 登记时间
            -- 认领时回填
            claimer_name   TEXT,                   -- 认领人姓名
            claimer_phone  TEXT,                   -- 认领人电话
            feature_verified INTEGER DEFAULT 0,    -- 特征已核实 0/1
            claimed_at     TEXT,                   -- 认领时间
            operator       TEXT,                   -- 经办人
            hide_photo     INTEGER DEFAULT 0       -- 1=敏感物品，公众界面隐藏照片
        )
    """)
    # 兼容旧库：若表已存在但没有 hide_photo 字段，自动补上
    cols = [r[1] for r in conn.execute("PRAGMA table_info(items)").fetchall()]
    if "hide_photo" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN hide_photo INTEGER DEFAULT 0")

    # 报失表（公众提交的"我丢了什么"）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lost_reports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at      TEXT NOT NULL,          -- 报失提交时间
            owner_name      TEXT NOT NULL,          -- 失主姓名
            owner_phone     TEXT NOT NULL,          -- 失主电话
            item_name       TEXT NOT NULL,          -- 丢失物品名称
            item_category   TEXT,                   -- 类别
            description     TEXT,                   -- 特征描述
            lost_location   TEXT,                   -- 丢失地点
            lost_time       TEXT,                   -- 丢失时间
            photo           TEXT,                   -- 报失照片（可选）
            status          TEXT NOT NULL DEFAULT '待查找',  -- 待查找/已找到/已忽略
            matched_item_id INTEGER,                -- 匹配到的失物ID（可空）
            note            TEXT,                   -- 管理员备注
            handled_by      TEXT,                   -- 处理人
            handled_at      TEXT                    -- 处理时间
        )
    """)
    conn.commit()
    conn.close()


# ============================================================
# 登录 / 口令
# ============================================================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            # 记住原地址，登录后跳回
            session["next_url"] = request.path
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    """模板里都能用到这些变量。"""
    return {
        "categories": config.CATEGORIES,
        "locations": config.LOCATIONS,
        "staff_names": config.STAFF_NAMES,
        "current_user": session.get("staff_name", ""),
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "").strip()
        staff_name = request.form.get("staff_name", "").strip()
        if password == config.ACCESS_PASSWORD and staff_name:
            session["logged_in"] = True
            session["staff_name"] = staff_name
            nxt = session.pop("next_url", None)
            return redirect(nxt or url_for("index"))
        flash("口令错误或未填写姓名，请重试。", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/switch_user")
def switch_user():
    """换人操作（不清口令，只重新选姓名）。"""
    if request.args.get("full"):
        session.clear()
        return redirect(url_for("login"))
    # 只换姓名：回登录页重新选
    session.pop("staff_name", None)
    session.pop("logged_in", None)
    return redirect(url_for("login"))


# ============================================================
# 工具函数
# ============================================================
def generate_code(conn):
    """生成失物编号：日期 + 当日三位序号，如 20260729-001。"""
    today = date.today().strftime("%Y%m%d")
    prefix = today + "-"
    # 查今天已有的最大序号
    row = conn.execute(
        "SELECT code FROM items WHERE code LIKE ? ORDER BY id DESC LIMIT 1",
        (prefix + "%",)
    ).fetchone()
    if row and row["code"].startswith(prefix):
        seq = int(row["code"].split("-")[-1]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


def allowed_photo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {
        "jpg", "jpeg", "png", "gif", "bmp", "webp"
    }


def save_photo(file_storage):
    """保存上传的照片，返回相对路径（用于 url_for uploads）。"""
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    # 用时间戳命名，避免重名
    fname = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{ext}"
    file_storage.save(os.path.join(config.UPLOAD_FOLDER, fname))
    return fname


def parse_dt(s):
    """字符串转 datetime，失败返回 None。"""
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ============================================================
# 路由：管理员工作台（原首页，移到 /admin）
# ============================================================
@app.route("/admin")
@login_required
def index():
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")

    today_count = db.execute(
        "SELECT COUNT(*) c FROM items WHERE substr(created_at,1,10)=?", (today,)
    ).fetchone()["c"]
    pending_count = db.execute(
        "SELECT COUNT(*) c FROM items WHERE status='待认领'"
    ).fetchone()["c"]
    month_returned = db.execute(
        "SELECT COUNT(*) c FROM items WHERE status='已认领' AND substr(claimed_at,1,7)=?",
        (date.today().strftime("%Y-%m"),)
    ).fetchone()["c"]
    # 待处理报失数（管理员提示）
    pending_reports = db.execute(
        "SELECT COUNT(*) c FROM lost_reports WHERE status='待查找'"
    ).fetchone()["c"]

    pending_items = db.execute(
        "SELECT * FROM items WHERE status='待认领' ORDER BY id DESC LIMIT 10"
    ).fetchall()

    return render_template("index.html",
                           today_count=today_count,
                           pending_count=pending_count,
                           month_returned=month_returned,
                           pending_reports=pending_reports,
                           pending_items=pending_items,
                           default_time=datetime.now().strftime("%Y-%m-%dT%H:%M"))


# ============================================================
# 路由：公众首页（公开，失主浏览被捡到的物品）
# ============================================================
@app.route("/")
def public_index():
    db = get_db()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()

    sql = "SELECT * FROM items WHERE status='待认领'"
    params = []
    if q:
        sql += " AND (code LIKE ? OR name LIKE ? OR description LIKE ? OR found_location LIKE ?)"
        params += [f"%{q}%"] * 4
    if cat:
        sql += " AND category=?"
        params.append(cat)
    sql += " ORDER BY id DESC"
    items = db.execute(sql, params).fetchall()
    return render_template("public_index.html", items=items, q=q, cat=cat)


# ============================================================
# 路由：公众报失页（公开，失主提交"我丢了什么"）
# ============================================================
@app.route("/report", methods=["GET", "POST"])
def public_report():
    db = get_db()
    if request.method == "POST":
        owner_name = request.form.get("owner_name", "").strip()
        owner_phone = request.form.get("owner_phone", "").strip()
        item_name = request.form.get("item_name", "").strip()
        if not (owner_name and owner_phone and item_name):
            flash("请填写姓名、电话、物品名称。", "error")
            return redirect(url_for("public_report"))

        category = request.form.get("item_category", "").strip()
        description = request.form.get("description", "").strip()
        lost_location = request.form.get("lost_location", "").strip()
        if lost_location == "__other__":
            lost_location = request.form.get("lost_location_other", "").strip()
        lost_time = request.form.get("lost_time", "").strip()

        # 处理报失照片（复用拍照/上传逻辑，但存同目录，仅管理员可见）
        photo_path = None
        photo_data = request.form.get("photo_data")
        file = request.files.get("photo_file")
        if photo_data and photo_data.startswith("data:image"):
            import base64
            header, b64 = photo_data.split(",", 1)
            ext = "png" if "png" in header else "jpeg"
            fname = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{ext}"
            with open(os.path.join(config.UPLOAD_FOLDER, fname), "wb") as f:
                f.write(base64.b64decode(b64))
            photo_path = fname
        elif file and file.filename and allowed_photo(file.filename):
            ext = file.filename.rsplit(".", 1)[1].lower()
            fname = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{ext}"
            file.save(os.path.join(config.UPLOAD_FOLDER, fname))
            photo_path = fname

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """INSERT INTO lost_reports
               (created_at, owner_name, owner_phone, item_name, item_category,
                description, lost_location, lost_time, photo, status)
               VALUES (?,?,?,?,?,?,?,?,?,'待查找')""",
            (now, owner_name, owner_phone, item_name, category,
             description, lost_location or None, lost_time or None, photo_path)
        )
        db.commit()
        flash("报失成功！我们会尽快帮您留意，找到后请到门诊导医台核对认领。", "success")
        return redirect(url_for("public_report"))

    default_time = datetime.now().strftime("%Y-%m-%dT%H:%M")
    return render_template("public_report.html", default_time=default_time)


# ============================================================
# 路由：报失处理台（管理员看报失列表 + 处理）
# ============================================================
@app.route("/reports", methods=["GET", "POST"])
@login_required
def reports():
    db = get_db()
    if request.method == "POST":
        # 处理一条报失：标记状态 + 备注 + 处理人
        report_id = request.form.get("report_id")
        action = request.form.get("action")
        note = request.form.get("note", "").strip()
        handled_by = session.get("staff_name", "")

        rep = db.execute("SELECT * FROM lost_reports WHERE id=?", (report_id,)).fetchone()
        if not rep:
            flash("报失记录不存在。", "error")
            return redirect(url_for("reports"))

        status_map = {"found": "已找到", "ignore": "已忽略", "reopen": "待查找"}
        new_status = status_map.get(action, rep["status"])
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """UPDATE lost_reports SET status=?, note=?, handled_by=?, handled_at=? WHERE id=?""",
            (new_status, note, handled_by, now, report_id)
        )
        db.commit()
        flash(f"报失已更新为「{new_status}」。", "success")
        return redirect(url_for("reports"))

    status = request.args.get("status", "待查找")
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM lost_reports WHERE 1=1"
    params = []
    if status != "all":
        sql += " AND status=?"
        params.append(status)
    if q:
        sql += " AND (owner_name LIKE ? OR owner_phone LIKE ? OR item_name LIKE ? OR description LIKE ?)"
        params += [f"%{q}%"] * 4
    sql += " ORDER BY id DESC"
    all_reports = db.execute(sql, params).fetchall()
    # 统计各状态数量
    counts = {
        "待查找": db.execute("SELECT COUNT(*) c FROM lost_reports WHERE status='待查找'").fetchone()["c"],
        "已找到": db.execute("SELECT COUNT(*) c FROM lost_reports WHERE status='已找到'").fetchone()["c"],
        "已忽略": db.execute("SELECT COUNT(*) c FROM lost_reports WHERE status='已忽略'").fetchone()["c"],
    }
    return render_template("reports.html", reports=all_reports, status=status,
                           q=q, counts=counts)


# ============================================================
# 路由：公开照片访问（公众界面用，受 hide_photo 控制）
# ============================================================
@app.route("/public/photo/<int:item_id>")
def public_photo(item_id):
    """公众访问的物品照片：若 hide_photo=1 或无照片，返回占位图，隐私由服务端强制。"""
    db = get_db()
    row = db.execute("SELECT photo, hide_photo FROM items WHERE id=?", (item_id,)).fetchone()
    if not row or not row["photo"] or row["hide_photo"]:
        # 返回占位图（1x1 透明 png，避免404破坏布局）
        import base64
        placeholder = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        from flask import Response
        return Response(placeholder, mimetype="image/png")
    return send_from_directory(config.UPLOAD_FOLDER, row["photo"])


@app.route("/public/item/<int:item_id>")
def public_item(item_id):
    """公众版物品详情：只返回非隐私字段（不含认领人姓名/电话等），且尊重 hide_photo。"""
    db = get_db()
    row = db.execute(
        "SELECT id, code, name, category, description, found_location, "
        "found_time, photo, hide_photo, status FROM items WHERE id=?",
        (item_id,)
    ).fetchone()
    if not row:
        return jsonify({"ok": False}), 404
    d = dict(row)
    # 隐藏照片的，对外不暴露 photo 字段（前端据此显示"请到导医台查看实物"）
    if d.get("hide_photo"):
        d["photo"] = None
    return jsonify({"ok": True, "item": d})


# ============================================================
# 路由：拾物登记
# ============================================================
@app.route("/register", methods=["GET", "POST"])
@login_required
def register():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        found_location = request.form.get("found_location", "").strip()
        if found_location == "__other__":
            found_location = request.form.get("found_location_other", "").strip()
        found_time = request.form.get("found_time", "").strip()
        founder = request.form.get("founder", "").strip()
        if founder == "__other__":
            founder = request.form.get("founder_other", "").strip()

        if not name:
            flash("请填写物品名称。", "error")
            return redirect(url_for("register"))

        # 处理照片
        photo_path = None
        photo_data = request.form.get("photo_data")  # 摄像头抓拍的 base64
        file = request.files.get("photo_file")       # 本地上传的文件
        if photo_data and photo_data.startswith("data:image"):
            import base64
            header, b64 = photo_data.split(",", 1)
            ext = "png" if "png" in header else "jpeg"
            fname = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{ext}"
            with open(os.path.join(config.UPLOAD_FOLDER, fname), "wb") as f:
                f.write(base64.b64decode(b64))
            photo_path = fname
        elif file and file.filename and allowed_photo(file.filename):
            photo_path = save_photo(file)

        code = generate_code(db)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hide_photo = 1 if request.form.get("hide_photo") else 0
        db.execute(
            """INSERT INTO items
               (code, name, category, description, photo, found_location,
                found_time, founder, status, created_at, hide_photo)
               VALUES (?,?,?,?,?,?,?,?,'待认领',?,?)""",
            (code, name, category, description, photo_path,
             found_location or None, found_time or None, founder or None,
             now, hide_photo)
        )
        db.commit()
        # AJAX 提交（工作台抽屉）：返回 JSON，前端弹提醒、不跳页
        if request.headers.get("X-Requested-With") == "fetch" or \
           request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            new_item = db.execute(
                "SELECT * FROM items WHERE code=?", (code,)
            ).fetchone()
            return jsonify({"ok": True, "item": dict(new_item)})
        # 传统整页提交（独立登记页）：保持原行为
        flash(f"登记成功！失物编号：{code}", "success")
        return redirect(url_for("register"))

    # GET：带一个默认时间
    default_time = datetime.now().strftime("%Y-%m-%dT%H:%M")
    return render_template("register.html", default_time=default_time)


@app.route("/api/pending")
@login_required
def pending_api():
    """返回最新待认领列表（工作台登记成功后局部刷新用）。"""
    db = get_db()
    items = db.execute(
        "SELECT * FROM items WHERE status='待认领' ORDER BY id DESC LIMIT 10"
    ).fetchall()
    return jsonify({"ok": True, "items": [dict(r) for r in items]})


# ============================================================
# 路由：认领登记
# ============================================================
@app.route("/claim", methods=["GET", "POST"])
@login_required
def claim():
    db = get_db()
    if request.method == "POST":
        item_id = request.form.get("item_id")
        claimer_name = request.form.get("claimer_name", "").strip()
        claimer_phone = request.form.get("claimer_phone", "").strip()
        feature_verified = 1 if request.form.get("feature_verified") else 0
        operator = request.form.get("operator", "").strip()
        if operator == "__other__":
            operator = request.form.get("operator_other", "").strip()

        item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            flash("物品不存在。", "error")
            return redirect(url_for("claim"))
        if item["status"] == "已认领":
            flash("该物品已被认领。", "error")
            return redirect(url_for("claim"))
        if not claimer_name:
            flash("请填写认领人姓名。", "error")
            return redirect(url_for("claim", code=item["code"]))
        if not feature_verified:
            flash("请勾选“已核对物品特征”。", "error")
            return redirect(url_for("claim", code=item["code"]))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """UPDATE items SET status='已认领', claimer_name=?, claimer_phone=?,
               feature_verified=?, claimed_at=?, operator=? WHERE id=?""",
            (claimer_name, claimer_phone, feature_verified, now, operator, item_id)
        )
        db.commit()
        flash(f"认领登记完成：{item['code']} 已归还给 {claimer_name}", "success")
        # 从工作台抽屉来 → 回工作台；从认领页来 → 回认领页
        return redirect(url_for("index"))

    # GET：可带 code 直接定位
    code = request.args.get("code", "").strip()
    q = request.args.get("q", "").strip()
    target_item = None
    if code:
        target_item = db.execute(
            "SELECT * FROM items WHERE code=? OR name LIKE ?",
            (code, f"%{code}%")
        ).fetchone()
    items = []
    if q:
        items = db.execute(
            """SELECT * FROM items WHERE status='待认领'
               AND (code LIKE ? OR name LIKE ? OR description LIKE ?)
               ORDER BY id DESC""",
            (f"%{q}%", f"%{q}%", f"%{q}%")
        ).fetchall()
    else:
        # 默认显示最近待认领
        items = db.execute(
            "SELECT * FROM items WHERE status='待认领' ORDER BY id DESC LIMIT 20"
        ).fetchall()

    return render_template("claim.html",
                           target_item=target_item,
                           items=items,
                           q=q, code=code)


@app.route("/api/claim/search")
@login_required
def claim_api():
    """工作台抽屉用的认领搜索接口，返回 JSON（仅待认领）。"""
    db = get_db()
    q = request.args.get("q", "").strip()
    if q:
        items = db.execute(
            """SELECT * FROM items WHERE status='待认领'
               AND (code LIKE ? OR name LIKE ? OR description LIKE ?)
               ORDER BY id DESC LIMIT 20""",
            (f"%{q}%", f"%{q}%", f"%{q}%")
        ).fetchall()
    else:
        items = db.execute(
            "SELECT * FROM items WHERE status='待认领' ORDER BY id DESC LIMIT 20"
        ).fetchall()
    return jsonify({"ok": True, "items": [dict(r) for r in items]})


# ============================================================
# 路由：失物总表
# ============================================================
@app.route("/list")
@login_required
def item_list():
    db = get_db()
    status = request.args.get("status", "all")
    q = request.args.get("q", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    sql = "SELECT * FROM items WHERE 1=1"
    params = []
    if status in ("待认领", "已认领"):
        sql += " AND status=?"
        params.append(status)
    if q:
        sql += " AND (code LIKE ? OR name LIKE ? OR category LIKE ? OR description LIKE ?)"
        params += [f"%{q}%"] * 4
    if date_from:
        sql += " AND substr(created_at,1,10)>=?"
        params.append(date_from)
    if date_to:
        sql += " AND substr(created_at,1,10)<=?"
        params.append(date_to)
    sql += " ORDER BY id DESC"

    items = db.execute(sql, params).fetchall()
    return render_template("list.html", items=items, status=status,
                           q=q, date_from=date_from, date_to=date_to)


# ============================================================
# 路由：详情（部分弹窗用）
# ============================================================
@app.route("/api/item/<int:item_id>")
@login_required
def api_item(item_id):
    db = get_db()
    row = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not row:
        return jsonify({"ok": False}), 404
    return jsonify({"ok": True, "item": dict(row)})


# ============================================================
# 路由：统计导出
# ============================================================
@app.route("/stats")
@login_required
def stats():
    db = get_db()
    date_from = request.args.get("date_from", "").strip() or \
        date.today().replace(day=1).strftime("%Y-%m-%d")
    date_to = request.args.get("date_to", "").strip() or \
        date.today().strftime("%Y-%m-%d")

    base = "SELECT COUNT(*) c FROM items WHERE substr(created_at,1,10) BETWEEN ? AND ?"
    found_count = db.execute(base, (date_from, date_to)).fetchone()["c"]
    returned_count = db.execute(
        base + " AND status='已认领'", (date_from, date_to)
    ).fetchone()["c"]
    pending_count = db.execute(
        base + " AND status='待认领'", (date_from, date_to)
    ).fetchone()["c"]

    # 按类别统计
    by_category = db.execute(
        """SELECT category, COUNT(*) c FROM items
           WHERE substr(created_at,1,10) BETWEEN ? AND ?
           GROUP BY category ORDER BY c DESC""",
        (date_from, date_to)
    ).fetchall()

    return render_template("stats.html",
                           date_from=date_from, date_to=date_to,
                           found_count=found_count,
                           returned_count=returned_count,
                           pending_count=pending_count,
                           by_category=by_category)


@app.route("/export")
@login_required
def export():
    db = get_db()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sql = "SELECT * FROM items WHERE 1=1"
    params = []
    if date_from:
        sql += " AND substr(created_at,1,10)>=?"
        params.append(date_from)
    if date_to:
        sql += " AND substr(created_at,1,10)<=?"
        params.append(date_to)
    sql += " ORDER BY id DESC"
    items = db.execute(sql, params).fetchall()
    return export_items_to_excel(items)


# ============================================================
# 静态：照片访问
# ============================================================
@app.route("/uploads/<path:filename>")
@login_required
def serve_upload(filename):
    return send_from_directory(config.UPLOAD_FOLDER, filename)


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    init_db()
    print("=" * 50)
    print("  门诊失物招领登记系统 已启动")
    print(f"  本机访问：  http://127.0.0.1:{config.PORT}")
    print(f"  其他电脑：  http://<本机IP>:{config.PORT}")
    print(f"  进入口令：  {config.ACCESS_PASSWORD}")
    print("=" * 50)
    app.run(host=config.HOST, port=config.PORT, debug=False)
