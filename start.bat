@echo off
chcp 65001 >nul
REM 门诊失物招领系统 - Windows 一键启动脚本
REM 双击此文件即可启动服务

cd /d "%~dp0"

echo ========================================
echo   门诊失物招领登记系统 启动中...
echo ========================================

REM 检查 Python
where python >nul 2>nul
if errorlevel 1 (
    echo ❌ 未找到 Python，请先安装 Python 3
    echo    下载地址：https://www.python.org/downloads/
    echo    安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM 首次运行：创建虚拟环境并安装依赖
if not exist "venv\Scripts\python.exe" (
    echo 📦 首次运行，正在准备运行环境（约需1-2分钟，请稍候）...
    python -m venv venv
    venv\Scripts\python -m pip install --upgrade pip -q
    venv\Scripts\python -m pip install -r requirements.txt -q
    echo ✅ 环境准备完成
)

REM 启动
echo.
echo 🌐 服务即将启动，浏览器打开：
echo    本机：    http://127.0.0.1:8000
echo    其他电脑/手机：http://本机IP:8000
echo.
echo ⚠️  请勿关闭此窗口，关闭则服务停止
echo ========================================

REM 3秒后自动打开浏览器
timeout /t 3 >nul
start "" "http://127.0.0.1:8000"

venv\Scripts\python app.py
pause
