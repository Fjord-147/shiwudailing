#!/bin/bash
# 门诊失物招领系统 - 一键启动脚本（macOS 双击运行）
# 双击此文件即可启动服务

cd "$(dirname "$0")"

echo "========================================"
echo "  门诊失物招领登记系统 启动中..."
echo "========================================"

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3（macOS 自带）"
    echo "按回车关闭..."
    read
    exit 1
fi

# 首次运行：创建虚拟环境并安装依赖
if [ ! -d "venv" ]; then
    echo "📦 首次运行，正在准备运行环境（约需1-2分钟，请稍候）..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip -q
    ./venv/bin/pip install -r requirements.txt -q
    echo "✅ 环境准备完成"
fi

# 启动
echo ""
echo "🌐 浏览器即将打开，也可手动访问："
echo "   本机：   http://127.0.0.1:8000"
echo "   其他电脑：http://<本机IP>:8000"
echo ""
echo "⚠️  请勿关闭此窗口，关闭则服务停止"
echo "========================================"

# 1.5秒后自动打开浏览器
( sleep 1.5 && open "http://127.0.0.1:8000" ) &

./venv/bin/python app.py
