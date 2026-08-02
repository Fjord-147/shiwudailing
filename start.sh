#!/bin/bash
# 门诊失物招领系统 - 启动脚本（通用，Linux/终端用）
cd "$(dirname "$0")"

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3"
    exit 1
fi

# 首次运行创建虚拟环境并装依赖
if [ ! -d "venv" ]; then
    echo "📦 首次运行，准备运行环境..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip -q
    ./venv/bin/pip install -r requirements.txt -q
    echo "✅ 环境准备完成"
fi

echo "🌐 启动服务：http://127.0.0.1:8000"
echo "⚠️  请勿关闭此窗口"
./venv/bin/python app.py
