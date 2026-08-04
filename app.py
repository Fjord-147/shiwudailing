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
            hide_photo     INTEGER DEFAULT 0,      -- 1=敏感物品，公众界面隐藏照片
            claimer_photo  TEXT,                   -- 认领人照片（可选，老人等记不清电话时备查）
            claimer_group  TEXT,                   -- 认领人群：老人/小孩/青年/其他
            claimer_gender TEXT,                   -- 认领人性别：男/女
            storage_location TEXT,                 -- 存放位置（如导诊台2号抽屉）
            hidden_photos TEXT                     -- 隐藏的照片文件名（逗号分隔，公众看不到）
        )
    """)
    # 兼容旧库：若表已存在但缺字段，自动补上
    cols = [r[1] for r in conn.execute("PRAGMA table_info(items)").fetchall()]
    if "hide_photo" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN hide_photo INTEGER DEFAULT 0")
    if "claimer_photo" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN claimer_photo TEXT")
    if "claimer_group" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN claimer_group TEXT")
    if "claimer_gender" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN claimer_gender TEXT")
    if "storage_location" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN storage_location TEXT")
    if "hidden_photos" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN hidden_photos TEXT")

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
def _is_ajax():
    """判断是否为前端 fetch（AJAX）请求，决定返回 JSON 还是重定向。"""
    return request.headers.get("X-Requested-With") == "fetch"


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


def norm_date(s):
    """把多种日期格式归一化为 YYYY-MM-DD（用于数据库字符串比较）。
    支持：2026-07-12 / 2026/07/12 / 2026-7-12 / 2026/7/12 / 20260712
    解析失败返回原值（交给后续比较，不会报错）。"""
    if not s:
        return ""
    import re
    cleaned = s.strip().replace("/", "-")
    # 尝试 YYYY-MM-DD（含单位数月日）
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", cleaned)
    if m:
        y, mo, d = m.groups()
        try:
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        except ValueError:
            pass
    # 尝试 YYYYMMDD
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s.strip())
    if m:
        y, mo, d = m.groups()
        try:
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        except ValueError:
            pass
    return s.strip()  # 解析不了就原样返回


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
    rows = db.execute(sql, params).fetchall()
    # 算出每条是否有"非隐藏照片"供模板判断
    items = []
    for r in rows:
        d = dict(r)
        all_photos = [p.strip() for p in (d.get("photo") or "").split(",") if p.strip()]
        hidden = set(p.strip() for p in (d.get("hidden_photos") or "").split(",") if p.strip())
        d["has_public_photo"] = any(p not in hidden for p in all_photos)
        items.append(d)
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
    """公众访问物品照片（兼容旧前端）：返回第一张非隐藏照片。"""
    return public_photo_idx(item_id, 0)


@app.route("/public/item/<int:item_id>")
def public_item(item_id):
    """公众版物品详情：只返回非隐私字段，照片过滤掉隐藏的。"""
    db = get_db()
    row = db.execute(
        "SELECT id, code, name, category, description, found_location, "
        "found_time, photo, hidden_photos, status FROM items WHERE id=?",
        (item_id,)
    ).fetchone()
    if not row:
        return jsonify({"ok": False}), 404
    d = dict(row)
    # 过滤掉隐藏的照片，只把可公开的照片列表给前端
    all_photos = [p.strip() for p in (d.get("photo") or "").split(",") if p.strip()]
    hidden = set(p.strip() for p in (d.get("hidden_photos") or "").split(",") if p.strip())
    public_photos = [p for p in all_photos if p not in hidden]
    d["photos"] = public_photos   # 公众可见的照片列表
    d["photo"] = public_photos[0] if public_photos else None  # 兼容旧前端取首张
    d.pop("hidden_photos", None)  # 不暴露隐藏信息
    return jsonify({"ok": True, "item": d})


@app.route("/public/photo/<int:item_id>/<int:idx>")
def public_photo_idx(item_id, idx):
    """公众访问某张照片：按序号取该物品的非隐藏照片，越界或隐藏返回占位图。"""
    db = get_db()
    row = db.execute("SELECT photo, hidden_photos FROM items WHERE id=?", (item_id,)).fetchone()
    if not row:
        return _placeholder_img()
    all_photos = [p.strip() for p in (row["photo"] or "").split(",") if p.strip()]
    hidden = set(p.strip() for p in (row["hidden_photos"] or "").split(",") if p.strip())
    public_photos = [p for p in all_photos if p not in hidden]
    if idx < 0 or idx >= len(public_photos):
        return _placeholder_img()
    return send_from_directory(config.UPLOAD_FOLDER, public_photos[idx])


def _placeholder_img():
    """返回1x1透明PNG占位图。"""
    import base64
    from flask import Response
    placeholder = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return Response(placeholder, mimetype="image/png")


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

        storage_location = request.form.get("storage_location", "").strip()

        if not name:
            if _is_ajax():
                return jsonify({"ok": False, "msg": "请填写物品名称。"})
            flash("请填写物品名称。", "error")
            return redirect(url_for("register"))
        if not storage_location:
            if _is_ajax():
                return jsonify({"ok": False, "msg": "请填写存放位置，方便后续取物。"})
            flash("请填写存放位置。", "error")
            return redirect(url_for("register"))

        # 处理照片（支持多张，最终存逗号分隔的文件名）
        import base64 as _b64
        photo_files = []  # 收集所有保存成功的文件名

        # 1) 本地上传的文件（可多选）
        for upfile in request.files.getlist("photo_file"):
            if upfile and upfile.filename and allowed_photo(upfile.filename):
                photo_files.append(save_photo(upfile))
        # 2) 摄像头抓拍的 base64（前端可能传多张 photo_data，逗号分隔的多个 data:...）
        raw_photos = request.form.get("photo_data", "")
        if raw_photos:
            # 按逗号拆分多个 data:image（注意 base64 内部无逗号，split(',') 会破坏，
            # 所以前端用特殊分隔符 ||| 分隔多张）
            for one in raw_photos.split("|||"):
                one = one.strip()
                if one.startswith("data:image"):
                    header, b64 = one.split(",", 1)
                    ext = "png" if "png" in header else "jpeg"
                    fname = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{ext}"
                    with open(os.path.join(config.UPLOAD_FOLDER, fname), "wb") as f:
                        f.write(_b64.b64decode(b64))
                    photo_files.append(fname)
        photo_path = ",".join(photo_files) if photo_files else None

        # 解析隐藏的照片序号（前端按 后端顺序 传：先file后data），算出隐藏的文件名
        hidden_photos_set = set()
        for idx_str in request.form.get("hidden_photo_idx", "").split(","):
            idx_str = idx_str.strip()
            if idx_str.isdigit() and int(idx_str) < len(photo_files):
                hidden_photos_set.add(photo_files[int(idx_str)])
        hidden_photos = ",".join(sorted(hidden_photos_set)) if hidden_photos_set else None

        code = generate_code(db)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """INSERT INTO items
               (code, name, category, description, photo, found_location,
                found_time, founder, status, created_at, hide_photo, storage_location, hidden_photos)
               VALUES (?,?,?,?,?,?,?,?,'待认领',?,0,?,?)""",
            (code, name, category, description, photo_path,
             found_location or None, found_time or None, founder or None,
             now, storage_location or None, hidden_photos)
        )
        db.commit()
        # AJAX 提交（工作台抽屉）：返回 JSON，前端弹提醒、不跳页
        if _is_ajax():
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


@app.route("/api/search")
@login_required
def search_api():
    """工作台就地搜索：按编号/名称/特征搜（含待认领和已认领）。"""
    db = get_db()
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"ok": True, "items": []})
    items = db.execute(
        """SELECT * FROM items
           WHERE code LIKE ? OR name LIKE ? OR description LIKE ? OR category LIKE ?
           ORDER BY id DESC LIMIT 30""",
        (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")
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
        claimer_group = request.form.get("claimer_group", "").strip()   # 人群
        claimer_gender = request.form.get("claimer_gender", "").strip() # 性别
        feature_verified = 1 if request.form.get("feature_verified") else 0
        operator = request.form.get("operator", "").strip()
        if operator == "__other__":
            operator = request.form.get("operator_other", "").strip()

        item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            msg = "物品不存在。"
            if _is_ajax(): return jsonify({"ok": False, "msg": msg})
            flash(msg, "error"); return redirect(url_for("claim"))
        if item["status"] == "已认领":
            msg = "该物品已被认领。"
            if _is_ajax(): return jsonify({"ok": False, "msg": msg})
            flash(msg, "error"); return redirect(url_for("claim"))
        if not claimer_name:
            msg = "请填写认领人姓名。"
            if _is_ajax(): return jsonify({"ok": False, "msg": msg})
            flash(msg, "error"); return redirect(url_for("claim", code=item["code"]))
        if not feature_verified:
            msg = "请勾选“已核对物品特征”。"
            if _is_ajax(): return jsonify({"ok": False, "msg": msg})
            flash(msg, "error"); return redirect(url_for("claim", code=item["code"]))

        # 处理认领人照片（可选，给老人等记不清电话的留照备查）
        claimer_photo = None
        cp_data = request.form.get("claimer_photo_data")    # 拍照 base64
        cp_file = request.files.get("claimer_photo_file")   # 文件上传
        if cp_data and cp_data.startswith("data:image"):
            import base64 as _b64
            header, b64 = cp_data.split(",", 1)
            ext = "png" if "png" in header else "jpeg"
            fname = f"claimer_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{ext}"
            with open(os.path.join(config.UPLOAD_FOLDER, fname), "wb") as f:
                f.write(_b64.b64decode(b64))
            claimer_photo = fname
        elif cp_file and cp_file.filename and allowed_photo(cp_file.filename):
            ext = cp_file.filename.rsplit(".", 1)[1].lower()
            fname = f"claimer_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{ext}"
            cp_file.save(os.path.join(config.UPLOAD_FOLDER, fname))
            claimer_photo = fname

        # 认领时间：优先用前端传的 claimed_at（可手改），否则用当前时刻
        claimed_at_raw = request.form.get("claimed_at", "").strip()
        if claimed_at_raw:
            dt = parse_dt(claimed_at_raw.replace("T", " "))  # datetime-local 格式
            now = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """UPDATE items SET status='已认领', claimer_name=?, claimer_phone=?,
               feature_verified=?, claimed_at=?, operator=?, claimer_photo=?,
               claimer_group=?, claimer_gender=? WHERE id=?""",
            (claimer_name, claimer_phone, feature_verified, now, operator,
             claimer_photo, claimer_group or None, claimer_gender or None, item_id)
        )
        db.commit()
        msg = f"认领登记完成：{item['code']} 已归还给 {claimer_name}"
        # AJAX 提交（工作台抽屉）：返回 JSON
        if _is_ajax():
            return jsonify({"ok": True, "msg": msg, "item": dict(item)})
        flash(msg, "success")
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
    status = request.args.get("status", "待认领")  # 默认只看待认领
    q = request.args.get("q", "").strip()
    date_from = norm_date(request.args.get("date_from", ""))
    date_to = norm_date(request.args.get("date_to", ""))

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
    items = [dict(r) for r in items]  # 转 dict，供模板 tojson 序列化
    return render_template("list.html", items=items, status=status,
                           q=q, date_from=date_from, date_to=date_to)


# ============================================================
# 路由：认领管理（已认领物品 + 撤销/修改/删除）
# ============================================================
@app.route("/claims")
@login_required
def claims_manage():
    db = get_db()
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM items WHERE status='已认领'"
    params = []
    if q:
        sql += " AND (code LIKE ? OR name LIKE ? OR description LIKE ? OR claimer_name LIKE ? OR claimer_phone LIKE ?)"
        params += [f"%{q}%"] * 5
    sql += " ORDER BY claimed_at DESC"
    items = db.execute(sql, params).fetchall()
    items = [dict(r) for r in items]
    return render_template("claims_manage.html", items=items, q=q)


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


def _remove_photos(*fnames):
    """安全删除照片文件（忽略不存在）。"""
    import os as _os
    for fn in fnames:
        if not fn:
            continue
        # photo 字段可能是逗号分隔的多张
        for one in str(fn).split(","):
            one = one.strip()
            if one:
                try:
                    _os.remove(os.path.join(config.UPLOAD_FOLDER, one))
                except OSError:
                    pass


@app.route("/api/item/<int:item_id>/unclaim", methods=["POST"])
@login_required
def api_unclaim(item_id):
    """撤销认领：状态退回待认领，清空认领信息，删认领人照片。"""
    db = get_db()
    if request.form.get("confirm", "").strip() != "确认":
        return jsonify({"ok": False, "msg": "请输入“确认”二字以执行撤销。"})
    item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item:
        return jsonify({"ok": False, "msg": "物品不存在。"})
    db.execute(
        """UPDATE items SET status='待认领', claimer_name=NULL, claimer_phone=NULL,
           claimer_group=NULL, claimer_gender=NULL, claimed_at=NULL, operator=NULL,
           feature_verified=0, claimer_photo=NULL WHERE id=?""",
        (item_id,)
    )
    db.commit()
    _remove_photos(item["claimer_photo"])  # 删认领人照片
    return jsonify({"ok": True, "msg": f"已撤销认领：{item['code']} 退回待认领。"})


@app.route("/api/item/<int:item_id>/delete", methods=["POST"])
@login_required
def api_delete(item_id):
    """删除整条记录（含照片）。"""
    db = get_db()
    if request.form.get("confirm", "").strip() != "确认":
        return jsonify({"ok": False, "msg": "请输入“确认”二字以执行删除。"})
    item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item:
        return jsonify({"ok": False, "msg": "物品不存在。"})
    _remove_photos(item["photo"], item["claimer_photo"])  # 删物品照片+认领人照片
    db.execute("DELETE FROM items WHERE id=?", (item_id,))
    db.commit()
    return jsonify({"ok": True, "msg": f"已删除记录：{item['code']} {item['name']}。"})


@app.route("/api/item/<int:item_id>/edit-claim", methods=["POST"])
@login_required
def api_edit_claim(item_id):
    """修改认领信息（姓名/电话/人群/性别），不改状态和物品本身。"""
    db = get_db()
    item = db.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item:
        return jsonify({"ok": False, "msg": "物品不存在。"})
    if item["status"] != "已认领":
        return jsonify({"ok": False, "msg": "该物品尚未认领，无法修改认领信息。"})
    name = request.form.get("claimer_name", "").strip()
    phone = request.form.get("claimer_phone", "").strip()
    group = request.form.get("claimer_group", "").strip()
    gender = request.form.get("claimer_gender", "").strip()
    if not name:
        return jsonify({"ok": False, "msg": "认领人姓名不能为空。"})
    db.execute(
        """UPDATE items SET claimer_name=?, claimer_phone=?, claimer_group=?, claimer_gender=?
           WHERE id=?""",
        (name, phone or None, group or None, gender or None, item_id)
    )
    db.commit()
    return jsonify({"ok": True, "msg": "认领信息已更新。"})


# ============================================================
# 路由：统计导出
# ============================================================
@app.route("/stats")
@login_required
def stats():
    db = get_db()
    date_from = norm_date(request.args.get("date_from", "")) or \
        date.today().replace(day=1).strftime("%Y-%m-%d")
    date_to = norm_date(request.args.get("date_to", "")) or \
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
    date_from = norm_date(request.args.get("date_from", ""))
    date_to = norm_date(request.args.get("date_to", ""))
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
