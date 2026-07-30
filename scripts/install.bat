@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo ==========================================
echo   西西桌面伴侣 - 一键安装
echo ==========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python。请先安装 Python 3.10+。
    pause
    exit /b 1
)

echo [1/5] Python 已找到
echo [2/5] 创建目录结构...
if not exist data mkdir data
if not exist logs mkdir logs
if not exist backups mkdir backups
if not exist assets mkdir assets

echo [3/5] 安装依赖...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败。
    pause
    exit /b 1
)

echo [4/5] 依赖安装完成
echo [5/5] 初始化数据库...
python -c "from core.database import Database; from core.config import Config; c=Config.load('config.yaml'); d=Database(c.get('database.path','data/xixi.db')); d.close(); print('数据库初始化完成')"
if errorlevel 1 (
    echo [错误] 数据库初始化失败。
    pause
    exit /b 1
)

echo.
echo [检查] Ollama 状态...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 Ollama。请从 https://ollama.com 下载安装。
    echo [提示] 安装后运行: ollama pull richardyoung/qwen3.6-27b-abliterated:latest
) else (
    echo [OK] Ollama 已安装
)

echo.
echo ==========================================
echo   安装完成！运行 scripts\start.bat
echo ==========================================
pause
