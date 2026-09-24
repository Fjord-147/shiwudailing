#!/bin/bash
# 失物招领系统 每日自动备份（数据库 + 照片）
#
# 用法：
#   手动：bash backup.sh
#   定时：crontab -e 加一行，例如每天凌晨 3 点
#         0 3 * * * /path/to/待领处1/backup.sh >> /path/to/待领处1/backups/backup.log 2>&1
#
# 路径说明（与旧版的区别）：
#   APP_DIR  自动取【本脚本所在目录】——项目在桌面、/opt、还是 U 盘都能直接跑；
#            旧版写死 /opt/lostfound，在这台开发机上根本跑不起来。
#   BAK_ROOT 默认 $APP_DIR/backups，可用环境变量覆盖，例如：
#            BAK_ROOT=/opt/backups/lostfound bash backup.sh
#   Python   优先项目内 .venv，其次 venv，最后系统 python3。

set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAK_ROOT="${BAK_ROOT:-$APP_DIR/backups}"
DATE=$(date +%Y-%m-%d)
DEST="$BAK_ROOT/$DATE"

PY="$APP_DIR/.venv/bin/python"
[ -x "$PY" ] || PY="$APP_DIR/venv/bin/python"
[ -x "$PY" ] || PY="python3"

if [ ! -f "$APP_DIR/lostfound.db" ]; then
    echo "错误：找不到数据库 $APP_DIR/lostfound.db（脚本须放在项目根目录）" >&2
    exit 1
fi

mkdir -p "$DEST"

# 1) 数据库：用 sqlite 在线备份接口（安全，不锁库、不拷贝写到一半的文件）
"$PY" - "$APP_DIR/lostfound.db" "$DEST/lostfound.db" <<'PYEOF'
import sys, sqlite3
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect(src)
d = sqlite3.connect(dst)
s.backup(d)
d.close()
s.close()
print("数据库备份完成")
PYEOF

# 2) 照片目录（静态文件，直接复制）
if [ -d "$APP_DIR/uploads" ]; then
    cp -r "$APP_DIR/uploads" "$DEST/uploads"
    echo "照片备份完成"
fi

# 3) 清理30天前的旧备份（mindepth 1 确保不会删备份根目录本身）
find "$BAK_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +

echo "备份完成：$DEST"
