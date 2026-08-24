#!/bin/bash
# 失物招领系统 每日自动备份（数据库 + 照片）
# 用法：由 crontab 每天自动调用；也手动执行：bash backup.sh
# 备份到 /opt/backups/lostfound/日期/，自动保留最近30天

set -e

APP_DIR=/opt/lostfound
BAK_ROOT=/opt/backups/lostfound
DATE=$(date +%Y-%m-%d)
DEST="$BAK_ROOT/$DATE"

mkdir -p "$DEST"

# 1) 数据库：用 sqlite 在线备份接口（安全，不锁库、不拷贝写到一半的文件）
"$APP_DIR/venv/bin/python" - "$APP_DIR/lostfound.db" "$DEST/lostfound.db" <<'PYEOF'
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
