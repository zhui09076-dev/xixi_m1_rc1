@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title 西西桌面伴侣
echo ==========================================
echo   西西桌面伴侣 - 一键启动
echo ==========================================
echo.

curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [警告] Ollama 服务未运行。尝试启动...
    start /min cmd /c "ollama serve"
    timeout /t 3 /nobreak >nul
)

echo [启动] 正在启动西西...
python main.py
if errorlevel 1 (
    echo.
    echo [错误] 启动失败。请检查 logs 目录。
    pause
    exit /b 1
)
