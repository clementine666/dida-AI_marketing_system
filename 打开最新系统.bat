@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 道旅营销协作系统 · 开发版

echo.
echo ========================================
echo   道旅营销协作系统（开发版）
echo   本文件夹即唯一项目目录
echo ========================================
echo.

echo [1/3] 释放 8000 端口...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
  taskkill /F /PID %%a >nul 2>&1
)

echo [2/3] 启动开发服务（后台）...
start "道旅营销协作系统-开发服务" /MIN cmd /c "py -3.11 scripts\run_dev.py"

echo [3/3] 等待服务就绪并打开浏览器...
set /a n=0
:wait_loop
set /a n+=1
if %n% gtr 30 goto open_browser
powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://localhost:8000/api/v2/health' -TimeoutSec 2; if ($r.features -contains 'query-profile-handoff') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 goto open_browser
timeout /t 1 /nobreak >nul
goto wait_loop

:open_browser
echo.
echo 浏览器将打开 http://localhost:8000/app
echo 配置保存在本目录 config\integrations.yaml
echo.
start "" "http://localhost:8000/app"
echo 若页面异常，请按 Ctrl+F5 强制刷新。
echo.
pause
