@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo ==========================================
echo   西西桌面伴侣 - 一键停止
echo ==========================================
echo.

if not exist data\xixi.pid (
    echo [提示] 未找到西西 PID 文件；程序可能未运行。
    goto unload_model
)

set /p XIXI_PID=<data\xixi.pid
echo [停止] 正在关闭西西 PID %XIXI_PID%...
taskkill /PID %XIXI_PID% >nul 2>&1
if errorlevel 1 (
    echo [警告] 正常关闭未成功，尝试强制停止该 PID。
    taskkill /F /PID %XIXI_PID% >nul 2>&1
)
del /q data\xixi.pid >nul 2>&1

:unload_model
echo [停止] 正在卸载模型...
curl -s -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" -d "{\"model\":\"richardyoung/qwen3.6-27b-abliterated:latest\",\"prompt\":\"\",\"stream\":false,\"keep_alive\":0}" >nul 2>&1

echo.
echo ==========================================
echo   已停止
echo ==========================================
pause
